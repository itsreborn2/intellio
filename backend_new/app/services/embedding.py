from typing import List, Dict, Any
import numpy as np
from openai import OpenAI, AsyncOpenAI
from pinecone import Pinecone, ServerlessSpec
from datetime import datetime, timezone
import logging
from app.core.config import settings
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)

class EmbeddingService:
    def __init__(self):
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
        self.async_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        pc = Pinecone(api_key=settings.PINECONE_API_KEY)
        self.index = pc.Index(settings.PINECONE_INDEX_NAME)
        self.batch_size = 50

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
            for i in range(0, len(valid_texts), self.batch_size):
                batch = valid_texts[i:i + self.batch_size]
                
                try:
                    # OpenAI API 비동기 호출
                    response = await self.async_client.embeddings.create(
                        model="text-embedding-ada-002",
                        input=batch
                    )
                    
                    if not response.data:
                        logger.error(f"임베딩 생성 실패: 응답 데이터 없음 (배치 {i})")
                        continue
                        
                    # 임베딩 추출 및 저장
                    batch_embeddings = [item.embedding for item in response.data]
                    all_embeddings.extend(batch_embeddings)
                    
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
            self.index.upsert(vectors=pinecone_vectors)
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
        """OpenAI API를 사용하여 텍스트의 임베딩 생성"""
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
        top_k: int = 5,
        document_ids: List[str] = None
    ) -> List[Dict[str, Any]]:
        """질문과 유사한 문서 청크를 검색합니다.
        
        Args:
            query: 검색 쿼리
            top_k: 반환할 최대 결과 수
            document_ids: 검색할 문서 ID 목록 (None이면 모든 문서에서 검색)
        """
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
            results = self.index.query(
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
            results = self.index.query(
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
            results = self.index.query(
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

    async def delete_embeddings(self, embedding_ids: List[str]) -> None:
        """임베딩 삭제"""
        try:
            if not embedding_ids:
                return
                
            # Pinecone에서 임베딩 삭제
            self.index.delete(ids=embedding_ids)
            logger.info(f"임베딩 삭제 완료: {len(embedding_ids)}개")
            
        except Exception as e:
            logger.error(f"임베딩 삭제 중 오류 발생: {str(e)}")
            raise

    async def clear_index(self) -> None:
        """인덱스의 모든 벡터 삭제"""
        try:
            self.index.delete(delete_all=True)
            logger.info("Pinecone 인덱스 초기화 완료")
        except Exception as e:
            logger.error(f"인덱스 초기화 중 오류 발생: {str(e)}")
            raise
