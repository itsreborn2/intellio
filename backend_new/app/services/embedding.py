from typing import List, Dict, Any
import numpy as np
from openai import OpenAI, AsyncOpenAI
from pinecone import Pinecone, ServerlessSpec
import logging
import re
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
        """텍스트 배치의 임베딩을 생성"""
        try:
            # 빈 텍스트 필터링
            valid_texts = [text for text in texts if text and text.strip()]
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
                    logger.error(f"배치 처리 중 오류 발생: {str(e)}")
                    raise
            
            return all_embeddings
            
        except Exception as e:
            logger.error(f"임베딩 생성 실패: {str(e)}")
            raise

    async def store_vectors(self, vectors: List[Dict]) -> bool:
        """벡터를 Pinecone에 저장"""
        try:
            if not vectors:
                logger.warning("저장할 벡터가 없습니다")
                return False

            # Pinecone 형식으로 변환
            pinecone_vectors = []
            for vector in vectors:
                if not all(k in vector for k in ["id", "values", "metadata"]):
                    logger.error(f"잘못된 벡터 형식: {vector.keys()}")
                    continue
                pinecone_vectors.append(vector)

            # 벡터 저장
            logger.info(f"벡터 {len(vectors)}개 저장 중")
            self.index.upsert(vectors=pinecone_vectors)
            logger.info(f"벡터 {len(vectors)}개 저장 완료")
            return True

        except Exception as e:
            logger.error(f"벡터 저장 실패: {str(e)}")
            return False

    async def create_embedding_with_retry(self, text: str) -> List[float]:
        """재시도 로직이 포함된 임베딩 생성"""
        try:
            embeddings = await self.create_embeddings_batch([text])
            return embeddings[0] if embeddings else []
        except Exception as e:
            logger.error(f"임베딩 생성 실패 (재시도 후): {str(e)}")
            raise
            
    async def create_embedding(self, text: str) -> List[float]:
        """OpenAI API를 사용하여 텍스트의 임베딩 생성"""
        try:
            if not text or not text.strip():
                logger.warning("Empty text provided for embedding")
                return []
                
            response = await self.async_client.embeddings.create(
                model="text-embedding-ada-002",
                input=text.strip()
            )
            
            return response.data[0].embedding
            
        except Exception as e:
            logger.error(f"Error creating embedding: {str(e)}")
            raise

    async def search_similar(
        self, 
        query: str, 
        top_k: int = 5,
        min_score: float = 0.7,
        use_context: bool = True,
        context_window: int = 2,
        document_ids: List[str] = None
    ) -> List[Dict[str, Any]]:
        """질문과 유사한 문서 청크를 검색합니다.
        
        Args:
            query: 검색 쿼리
            top_k: 반환할 최대 결과 수
            min_score: 최소 유사도 점수 (0.0 ~ 1.0)
            use_context: 문맥 고려 여부
            context_window: 고려할 주변 청크의 수
            document_ids: 검색할 문서 ID 목록 (None이면 모든 문서에서 검색)
        """
        try:
            # 쿼리 임베딩 생성
            query_embedding = await self.create_embedding_with_retry(query)
            if not query_embedding:
                return []
                
            # 필터 설정
            filter_dict = {}
            if document_ids:
                filter_dict["document_id"] = {"$in": document_ids}

            # 제목 검색을 위한 필터 추가
            company_patterns = [
                r'기업명|회사명|법인명|상호',
                r'([가-힣A-Za-z\s&]+)(주식회사|㈜|주식회사|[Cc]orp\.?|[Cc]orporation|[Cc]ompany|[Ii]nc\.?)',
                r'([가-힣A-Za-z\s&]+)(그룹|[Gg]roup)',
            ]
            
            is_company_query = any(re.search(pattern, query, re.IGNORECASE) for pattern in company_patterns)
            
            # Pinecone에서 유사한 벡터 검색
            results = self.index.query(
                vector=query_embedding,
                top_k=top_k * (2 if use_context else 1),  # 문맥 고려시 더 많은 결과 조회
                include_metadata=True,
                filter=filter_dict
            )
            
            # 결과 필터링 및 정렬
            filtered_matches = []
            for match in results.matches:
                # 최소 유사도 점수 체크
                if match.score < min_score:
                    continue
                    
                # 메타데이터 포함
                chunk = {
                    "id": match.id,
                    "score": match.score,
                    "content": match.metadata.get("text", ""),
                    "metadata": match.metadata
                }
                
                # 기업명 쿼리인 경우 제목 우선 순위 부여
                if is_company_query:
                    title = match.metadata.get("title", "")
                    if any(re.search(pattern, title, re.IGNORECASE) for pattern in company_patterns):
                        chunk["score"] *= 1.5  # 제목 매칭 시 점수 가중치
                        
                filtered_matches.append(chunk)
            
            # 점수 기준 정렬
            filtered_matches.sort(key=lambda x: x["score"], reverse=True)
            
            # 상위 K개만 선택
            top_matches = filtered_matches[:top_k]
            
            # 문맥 추가
            if use_context and top_matches:
                return await self._add_context_chunks(top_matches, context_window)
            
            return top_matches
            
        except Exception as e:
            logger.error(f"유사 청크 검색 중 오류 발생: {str(e)}")
            return []
            
    async def _add_context_chunks(
        self,
        chunks: List[Dict[str, Any]],
        context_window: int
    ) -> List[Dict[str, Any]]:
        """주변 청크의 문맥을 추가"""
        context_chunks = []
        
        for chunk in chunks:
            doc_id = chunk["metadata"].get("document_id", "")
            chunk_idx = chunk["metadata"].get("chunk_index", 0)
            
            # 현재 청크 추가
            context_chunks.append(chunk)
            
            try:
                # 이전 청크들 가져오기
                start_idx = max(0, chunk_idx - context_window)
                prev_chunks = await self._get_document_chunks_by_range(
                    doc_id, start_idx, chunk_idx
                )
                context_chunks.extend(prev_chunks)
                
                # 다음 청크들 가져오기
                next_chunks = await self._get_document_chunks_by_range(
                    doc_id, chunk_idx + 1, chunk_idx + context_window + 1
                )
                context_chunks.extend(next_chunks)
                
            except Exception as e:
                logger.warning(f"문맥 청크 추가 실패: {str(e)}")
                continue
        
        # 중복 제거 및 정렬
        unique_chunks = {chunk["id"]: chunk for chunk in context_chunks}
        return list(unique_chunks.values())
        
    async def _get_document_chunks_by_range(
        self,
        doc_id: str,
        start_idx: int,
        end_idx: int
    ) -> List[Dict[str, Any]]:
        """문서의 특정 범위 청크 조회"""
        try:
            # 범위 검증
            if start_idx >= end_idx:
                return []
                
            # Pinecone 쿼리
            results = self.index.query(
                vector=[0.0] * 1536,  # 더미 벡터
                top_k=max(1, end_idx - start_idx),  # 최소 1 보장
                include_metadata=True,
                filter={
                    "document_id": doc_id,
                    "chunk_index": {"$gte": start_idx, "$lt": end_idx}
                }
            )
            
            chunks = []
            for match in results.matches:
                chunks.append({
                    "id": match.id,
                    "score": 0.0,  # 문맥 청크는 점수 0으로 설정
                    "content": match.metadata.get("text", ""),
                    "metadata": match.metadata
                })
            
            # 청크 인덱스로 정렬
            chunks.sort(key=lambda x: x["metadata"].get("chunk_index", 0))
            return chunks
            
        except Exception as e:
            logger.error(f"청크 범위 조회 실패: {str(e)}")
            return []

    async def get_document_chunks(self, doc_id: str) -> List[Dict[str, Any]]:
        """특정 문서의 모든 청크를 가져옵니다."""
        try:
            # 문서 ID로 필터링하여 모든 청크 검색
            results = self.index.query(
                vector=[0] * 1536,  # 더미 벡터
                top_k=10000,  # 충분히 큰 값
                include_metadata=True,
                filter={"document_id": doc_id}
            )
            
            # 결과 형식화
            chunks = []
            for match in results.matches:
                chunk = {
                    "id": match.id,
                    "content": match.metadata.get("text", ""),
                    "metadata": match.metadata
                }
                chunks.append(chunk)
                
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
            logger.error(f"임베딩 삭제 실패: {str(e)}")

    async def clear_index(self) -> None:
        """인덱스의 모든 벡터 삭제"""
        try:
            self.index.delete(delete_all=True)
            logger.info("Pinecone 인덱스 초기화 완료")
        except Exception as e:
            logger.error(f"인덱스 초기화 중 오류 발생: {str(e)}")
