from typing import List, Dict, Any, Optional
import numpy as np
from openai import OpenAI, AsyncOpenAI
from pinecone import Pinecone, ServerlessSpec
from datetime import datetime, timezone
import logging
from app.core.config import settings
from tenacity import retry, stop_after_attempt, wait_exponential
import json
import redis
import re
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

class EmbeddingService:
    def __init__(self):
        self.model = SentenceTransformer(settings.EMBEDDING_MODEL)
        self.redis = redis.Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT, db=0)
        self.chunk_size = 500
        self.metadata_patterns = {
            'securities_firm': [
                r'([가-힣A-Za-z\s&]+)증권',
                r'([가-힣A-Za-z\s&]+)\s*Investment\s*&\s*Securities',
                r'([가-힣A-Za-z\s&]+)\s*리서치센터',
                r'([가-힣A-Za-z\s&]+)\s*투자증권'
            ],
            'contract_parties': [
                r'계약\s*당사자[^\n]*?:\s*([^\n]+)',
                r'계약자[^\n]*?:\s*([^\n]+)',
                r'([가-힣A-Za-z\s&]+)와\(과\)\s*계약'
            ],
            'monetary_values': [
                r'금액[^\n]*?:\s*([0-9,]+)[만천억]?원',
                r'가격[^\n]*?:\s*([0-9,]+)[만천억]?원',
                r'평가액[^\n]*?:\s*([0-9,]+)[만천억]?원'
            ]
        }

    def _extract_metadata(self, text: str) -> Dict[str, Any]:
        """텍스트에서 메타데이터 추출"""
        metadata = {key: set() for key in self.metadata_patterns.keys()}
        
        for key, patterns in self.metadata_patterns.items():
            for pattern in patterns:
                matches = re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE)
                for match in matches:
                    value = match.group(1).strip()
                    if value:
                        metadata[key].add(value)
        
        # set을 list로 변환
        return {k: list(v) for k, v in metadata.items()}

    def _create_chunks(self, text: str, document_id: str) -> List[Dict[str, Any]]:
        """텍스트를 청크로 분할하고 메타데이터 추출"""
        chunks = []
        
        # 1. 전체 문서의 메타데이터 추출
        doc_metadata = self._extract_metadata(text)
        
        # 2. 문단 단위로 분할 (빈 줄 기준)
        paragraphs = re.split(r'\n\s*\n', text)
        
        current_chunk = ""
        current_metadata = {k: [] for k in self.metadata_patterns.keys()}
        
        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
                
            # 현재 문단의 메타데이터 추출
            para_metadata = self._extract_metadata(para)
            
            # 청크 크기 체크
            if len(current_chunk) + len(para) > self.chunk_size:
                if current_chunk:
                    # 청크 저장
                    chunks.append({
                        "content": current_chunk,
                        "document_id": document_id,
                        "metadata": {
                            # 현재 청크의 메타데이터와 전체 문서의 메타데이터 병합
                            k: list(set(current_metadata[k] + doc_metadata.get(k, [])))
                            for k in self.metadata_patterns.keys()
                        }
                    })
                # 새 청크 시작
                current_chunk = para
                current_metadata = para_metadata
            else:
                # 현재 청크에 문단 추가
                current_chunk = current_chunk + "\n\n" + para if current_chunk else para
                # 메타데이터 병합
                for k in self.metadata_patterns.keys():
                    current_metadata[k].extend(para_metadata.get(k, []))
        
        # 마지막 청크 처리
        if current_chunk:
            chunks.append({
                "content": current_chunk,
                "document_id": document_id,
                "metadata": {
                    k: list(set(current_metadata[k] + doc_metadata.get(k, [])))
                    for k in self.metadata_patterns.keys()
                }
            })
        
        return chunks

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    async def create_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """여러 텍스트의 임베딩을 한 번에 생성"""
        try:
            # 빈 텍스트 필터링
            valid_texts = [text.strip() for text in texts if text and text.strip()]
            if not valid_texts:
                return []
            
            all_embeddings = []
            
            # 배치 단위로 처리
            for i in range(0, len(valid_texts), 50):
                batch = valid_texts[i:i + 50]
                
                try:
                    # 임베딩 생성
                    embeddings = self.model.encode(batch, convert_to_tensor=True)
                    all_embeddings.extend(embeddings.cpu().numpy().tolist())
                    
                    logger.info(f"배치 처리 완료: {i+1}-{i+len(batch)}/{len(valid_texts)}")
                
                except Exception as e:
                    logger.error(f"배치 처리 실패 ({i}): {str(e)}")
                    raise
            
            return all_embeddings
            
        except Exception as e:
            logger.error(f"임베딩 생성 실패: {str(e)}")
            raise
            
    async def store_vectors(self, vectors: List[Dict[str, Any]]) -> bool:
        """비동기식 벡터 저장 메서드"""
        try:
            if not vectors:
                logger.warning("저장할 벡터 없음")
                return False

            # Pinecone 형식으로 변환
            pinecone_vectors = [
                {
                    "id": str(vector["id"]),
                    "values": vector["values"],
                    "metadata": vector["metadata"]
                }
                for vector in vectors
            ]

            # 벡터 저장
            logger.info(f"벡터 {len(vectors)}개 저장 중")
            pc = Pinecone(api_key=settings.PINECONE_API_KEY)
            index = pc.Index(settings.PINECONE_INDEX_NAME)
            index.upsert(vectors=pinecone_vectors)
            logger.info(f"벡터 {len(vectors)}개 저장 완료")
            return True

        except Exception as e:
            logger.error(f"벡터 저장 실패: {str(e)}")
            raise
            
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    async def create_embedding_with_retry(self, text: str) -> List[float]:
        """단일 텍스트의 임베딩을 생성 (이전 버전과의 호환성 유지)"""
        try:
            embeddings = await self.create_embeddings_batch([text])
            return embeddings[0] if embeddings else None
        except Exception as e:
            logger.error(f"임베딩 생성 실패: {str(e)}")
            raise
            
    async def create_embedding(self, text: str) -> List[float]:
        """임베딩 생성"""
        try:
            if not text or not text.strip():
                logger.warning("Empty text provided for embedding")
                return None
                
            embedding = await self.create_embedding_with_retry(text)
            if embedding is None:
                logger.error("Failed to create embedding - got None result")
                return None
                
            return embedding
            
        except Exception as e:
            logger.error(f"Failed to create embedding: {str(e)}")
            return None

    async def search_similar(
        self, 
        query: str, 
        document_ids: List[str] = None,
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """유사도 검색 + 메타데이터 활용"""
        # 기존 유사도 검색 로직
        chunks = await self._search_similar_base(query, document_ids, top_k)
        
        # 메타데이터 기반 필터링/정렬
        if chunks:
            # 쿼리 분석해서 어떤 메타데이터가 필요한지 확인
            required_metadata = self._analyze_query_for_metadata(query)
            
            if required_metadata:
                # 메타데이터 포함된 청크 우선
                chunks.sort(key=lambda x: sum(
                    1 for k in required_metadata 
                    if x.get("metadata", {}).get(k)
                ), reverse=True)
        
        return chunks

    def _analyze_query_for_metadata(self, query: str) -> List[str]:
        """쿼리 분석하여 필요한 메타데이터 타입 반환"""
        required = []
        
        # 증권사 관련
        if re.search(r'증권사|리서치|투자증권', query):
            required.append('securities_firm')
            
        # 계약 당사자 관련
        if re.search(r'계약|당사자|계약자', query):
            required.append('contract_parties')
            
        # 금액 관련
        if re.search(r'금액|가격|평가액', query):
            required.append('monetary_values')
            
        return required

    async def _search_similar_base(
        self, 
        query: str, 
        document_ids: List[str] = None,
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """기본 유사도 검색 로직"""
        try:
            # 쿼리 임베딩 생성
            query_embedding = await self.create_embedding_with_retry(query)
            if not query_embedding:
                raise ValueError("Failed to create query embedding")
            
            # 필터 조건 설정
            filter_dict = {}
            if document_ids:
                filter_dict["document_id"] = {"$in": document_ids}
                
            # Pinecone에서 유사한 벡터 검색
            pc = Pinecone(api_key=settings.PINECONE_API_KEY)
            index = pc.Index(settings.PINECONE_INDEX_NAME)
            results = index.query(
                vector=query_embedding,
                top_k=top_k,
                include_metadata=True,
                filter=filter_dict
            )
            
            # 결과 정리
            similar_chunks = []
            for match in results.matches:
                similar_chunks.append({
                    "chunk_id": match.id,
                    "score": match.score,
                    "text": match.metadata.get("text", ""),
                    "document_id": match.metadata.get("document_id", ""),
                    "chunk_index": match.metadata.get("chunk_index", -1)
                })
                
            return similar_chunks
            
        except Exception as e:
            logger.error(f"유사 문서 검색 실패: {str(e)}")
            raise

    async def store_embeddings(
        self,
        document_id: str,
        chunk_texts: List[str],
        metadata: dict = None
    ) -> List[str]:
        """청크의 임베딩을 생성하고 Pinecone에 저장"""
        chunk_ids = []
        current_batch = []
        batch_size = 100

        try:
            logger.info(f"Starting to process embeddings for document {document_id} with {len(chunk_texts)} chunks")
            
            for i, text in enumerate(chunk_texts):
                embedding = await self.create_embedding_with_retry(text)
                chunk_id = f"{document_id}_chunk_{i}"
                # 기존 메타데이터에 doc_id 추가
                chunk_metadata = {
                    **(metadata or {}),
                    "document_id": str(document_id),  # 명시적으로 문자열로 변환
                    "chunk_index": i,
                    "text": text  # 청크 텍스트를 메타데이터에 추가
                }
                current_batch.append({
                    "id": chunk_id,
                    "values": embedding,
                    "metadata": chunk_metadata
                })
                chunk_ids.append(chunk_id)
                
                if len(current_batch) >= batch_size:
                    logger.info(f"Storing batch of {len(current_batch)} embeddings")
                    await self.store_vectors(current_batch)
                    current_batch = []

            if current_batch:
                logger.info(f"Storing final batch of {len(current_batch)} embeddings")
                await self.store_vectors(current_batch)

            logger.info(f"Successfully processed and stored {len(chunk_ids)} embeddings for document {document_id}")

        except Exception as e:
            logger.error(f"Error processing embeddings for document {document_id}: {str(e)}")
            raise

        return chunk_ids

    async def query_embeddings(self, query_embedding: List[float], top_k: int = 5) -> List[Dict]:
        """임베딩으로 유사한 문서 검색"""
        try:
            pc = Pinecone(api_key=settings.PINECONE_API_KEY)
            index = pc.Index(settings.PINECONE_INDEX_NAME)
            results = index.query(
                vector=query_embedding,
                top_k=top_k,
                include_metadata=True
            )
            return results.matches
        except Exception as e:
            logger.error(f"임베딩 검색 중 오류 발생: {str(e)}")
            raise
            
    async def get_document_chunks(self, doc_id: str) -> List[Dict[str, Any]]:
        """문서 ID에 해당하는 모든 청크 가져오기"""
        try:
            # Pinecone에서 문서 ID로 필터링하여 모든 청크 검색
            pc = Pinecone(api_key=settings.PINECONE_API_KEY)
            index = pc.Index(settings.PINECONE_INDEX_NAME)
            results = index.query(
                vector=[0] * 1536,  # 더미 벡터
                top_k=10000,  # 충분히 큰 값
                include_metadata=True,
                filter={"document_id": str(doc_id)}  # 문서 ID로 필터링
            )
            
            # 청크 인덱스 순서대로 정렬
            chunks = sorted([
                {
                    "chunk_id": match.id,
                    "text": match.metadata.get("text", ""),
                    "chunk_index": match.metadata.get("chunk_index", -1)
                }
                for match in results.matches
            ], key=lambda x: x["chunk_index"])
            
            return chunks
            
        except Exception as e:
            logger.error(f"문서 청크 조회 실패 (문서 ID: {doc_id}): {str(e)}")
            return []

    async def get_first_chunk(self, document_id: str) -> Optional[Dict[str, Any]]:
        """문서의 첫 번째 청크 반환"""
        try:
            # Redis에서 문서의 모든 청크 가져오기
            chunks = await self.redis.get(f"doc:{document_id}:chunks")
            if chunks:
                chunks = json.loads(chunks)
                if chunks:
                    # 첫 번째 청크 반환
                    return chunks[0]
            return None
        except Exception as e:
            logger.error(f"첫 번째 청크 가져오기 실패: {str(e)}")
            return None

    async def delete_embeddings(self, embedding_ids: List[str]) -> None:
        """임베딩 삭제"""
        try:
            if not embedding_ids:
                return
                
            # Pinecone에서 임베딩 삭제
            pc = Pinecone(api_key=settings.PINECONE_API_KEY)
            index = pc.Index(settings.PINECONE_INDEX_NAME)
            index.delete(ids=embedding_ids)
            logger.info(f"임베딩 삭제 완료: {len(embedding_ids)}개")
            
        except Exception as e:
            logger.error(f"임베딩 삭제 중 오류 발생: {str(e)}")
            raise

    async def clear_index(self) -> None:
        """인덱스의 모든 벡터 삭제"""
        try:
            pc = Pinecone(api_key=settings.PINECONE_API_KEY)
            index = pc.Index(settings.PINECONE_INDEX_NAME)
            index.delete(delete_all=True)
            logger.info("Pinecone 인덱스 초기화 완료")
        except Exception as e:
            logger.error(f"인덱스 초기화 중 오류 발생: {str(e)}")
            raise
