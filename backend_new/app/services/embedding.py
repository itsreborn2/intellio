from typing import List, Dict, Any
import numpy as np
from openai import OpenAI, AsyncOpenAI
from pinecone import Pinecone
import logging
import re
from app.core.config import settings
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from app.utils.common import measure_time_async
import openai
from openai import OpenAIError, Timeout
logger = logging.getLogger(__name__)

class EmbeddingService:
    def __init__(self):
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
        self.async_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        pc = Pinecone(api_key=settings.PINECONE_API_KEY)
        self.index = pc.Index(settings.PINECONE_INDEX_NAME)
        self.batch_size = 20  # 임베딩 처리의 안정성을 위해 배치 크기 축소 (50 -> 20)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    async def create_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """텍스트 배치의 임베딩을 생성"""
        try:
            # 빈 텍스트 필터링
            valid_texts = [text for text in texts if text and text.strip()]
            if not valid_texts:
                logger.warning("임베딩 생성 실패: 유효한 텍스트가 없음")
                return []
                
            logger.debug(f"임베딩 생성 시작: 총 {len(valid_texts)}개 텍스트")
            all_embeddings = []
            
            # 배치 단위로 처리
            for i in range(0, len(valid_texts), self.batch_size):
                batch = valid_texts[i:i + self.batch_size]
                batch_size = len(batch)
                logger.debug(f"배치 처리 시작 ({i+1}-{i+batch_size}/{len(valid_texts)})")
                
                try:
                    # OpenAI API 비동기 호출
                    logger.debug(f"OpenAI API 호출 - 배치 크기: {batch_size}")
                    response = await self.async_client.embeddings.create(
                        model="text-embedding-ada-002",  
                        input=batch
                    )
                    
                    if not response.data:
                        logger.error(f"임베딩 생성 실패: 응답 데이터 없음 (배치 {i})")
                        continue
                        
                    # 임베딩 추출 및 저장
                    batch_embeddings = [item.embedding for item in response.data]
                    
                    # 임베딩 품질 체크
                    for j, emb in enumerate(batch_embeddings):
                        if not emb or len(emb) != 1536:  
                            logger.error(f"잘못된 임베딩 차원 (배치 {i}, 인덱스 {j}): {len(emb) if emb else 0}")
                            continue
                    
                    all_embeddings.extend(batch_embeddings)
                    logger.info(f"배치 처리 완료: {i+1}-{i+batch_size}/{len(valid_texts)}")
                    logger.info(f"임베딩 생성됨: {len(batch_embeddings)}개")
                
                except Exception as e:
                    logger.error(f"배치 처리 중 오류 발생 (배치 {i}): {str(e)}")
                    continue
            
            logger.info(f"전체 임베딩 생성 완료: {len(all_embeddings)}개")
            return all_embeddings
            
        except Exception as e:
            logger.error(f"임베딩 생성 실패: {str(e)}")
            return []

    @retry(
        stop=stop_after_attempt(3),  # 최대 3번 시도
        wait=wait_exponential(multiplier=1, min=4, max=10),  # 지수 백오프
        retry=retry_if_exception_type(Timeout)  # 타임아웃 예외 시 재시도
    )
    def create_embeddings_batch_sync(self, texts: List[str]) -> List[List[float]]:
        """텍스트 배치의 임베딩을 생성"""
        try:
            # 빈 텍스트 필터링
            valid_texts = [text for text in texts if text and text.strip()]
            if not valid_texts:
                logger.warning("임베딩 생성 실패: 유효한 텍스트가 없음")
                return []
                
            logger.debug(f"임베딩 생성 시작: 총 {len(valid_texts)}개 텍스트")
            all_embeddings = []
            
            # 배치 단위로 처리
            for i in range(0, len(valid_texts), self.batch_size):
                batch = valid_texts[i:i + self.batch_size]
                batch_size = len(batch)
                logger.debug(f"배치 처리 시작 ({i+1}-{i+batch_size}/{len(valid_texts)})")
                
                try:
                    # OpenAI API 비동기 호출
                    logger.debug(f"OpenAI API 호출 - 배치 크기: {batch_size}")
                    response = self.client.embeddings.create(
                        model="text-embedding-ada-002",  
                        input=batch,
                        timeout=5  # 타임아웃 설
                    )
                    
                    if not response.data:
                        logger.error(f"임베딩 생성 실패: 응답 데이터 없음 (배치 {i})")
                        continue
                        
                    # 임베딩 추출 및 저장
                    batch_embeddings = [item.embedding for item in response.data]
                    
                    # 임베딩 품질 체크
                    for j, emb in enumerate(batch_embeddings):
                        if not emb or len(emb) != 1536:  
                            logger.error(f"잘못된 임베딩 차원 (배치 {i}, 인덱스 {j}): {len(emb) if emb else 0}")
                            continue
                    
                    all_embeddings.extend(batch_embeddings)
                    logger.info(f"배치 처리 완료: {i+1}-{i+batch_size}/{len(valid_texts)}")
                    logger.info(f"임베딩 생성됨: {len(batch_embeddings)}개")
                
                except Exception as e:
                    logger.error(f"배치 처리 중 오류 발생 (배치 {i}): {str(e)}")
                    continue
            
            logger.info(f"전체 임베딩 생성 완료: {len(all_embeddings)}개")
            return all_embeddings
            
        except Exception as e:
            logger.error(f"임베딩 생성 실패: {str(e)}")
            return []

    def store_vectors(self, vectors: List[Dict]) -> bool:
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
    def create_embedding_with_retry_sync(self, text: str) -> List[float]:
        """재시도 로직이 포함된 임베딩 생성"""
        try:
            embeddings = self.create_embeddings_batch_sync([text])
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
    @measure_time_async
    async def search_similar(
        self, 
        query: str, 
        top_k: int = 7,
        min_score: float = 0.6,
        use_context: bool = True,
        context_window: int = 2,
        document_ids: List[str] = None
    ) -> List[Dict[str, Any]]:
        """질문과 유사한 문서 청크를 검색합니다."""
        try:
            logger.info(f"유사 문서 검색 시작 - 쿼리: {query}")
            
            # 쿼리 임베딩 생성
            query_embedding = await self.create_embedding_with_retry(query)
            #query_embedding = self.create_embedding_with_retry_sync(query)
            if not query_embedding:
                logger.error("쿼리 임베딩 생성 실패")
                return []

                
            # 필터 설정
            filter_dict = {}
            if document_ids:
                filter_dict["document_id"] = {"$in": document_ids}
                logger.debug(f"문서 필터 설정: {document_ids}")

            # Pinecone 검색 실행
            logger.info(f"Pinecone 검색 시작 (top_k: {top_k}, min_score: {min_score})")
            try:
                search_response = self.index.query(
                    vector=query_embedding,
                    top_k=top_k * 5,  # 필터링을 위해 더 많은 결과 요청
                    filter=filter_dict,
                    include_metadata=True
                )
                
                if not search_response.matches:
                    logger.warning("검색 결과 없음")
                    return []
                    
                logger.info(f"검색된 총 매치 수: {len(search_response.matches)}")
                for match in search_response.matches[:3]:
                    logger.info(f"매치 - ID: {match.id}, 점수: {match.score:.4f}")
                
                # 유사도 점수로 필터링
                filtered_results = [
                    match for match in search_response.matches 
                    if match.score >= min_score
                ]
                
                if not filtered_results:
                    logger.warning(f"최소 유사도({min_score}) 이상의 결과 없음")
                    return []
                
                logger.debug(f"필터링된 결과: {len(filtered_results)}개")
                
                # 상위 K개만 선택
                top_results = filtered_results[:top_k]
                
                # 결과 포맷팅
                formatted_results = []
                for match in top_results:
                    result = {
                        "id": match.id,
                        "score": match.score,
                        "metadata": match.metadata
                    }
                    formatted_results.append(result)
                    logger.debug(f"매치 정보 - ID: {match.id}, 점수: {match.score:.4f}")
                
                return formatted_results
                
            except Exception as e:
                logger.error(f"Pinecone 검색 실패: {str(e)}")
                return []
            
        except Exception as e:
            logger.error(f"유사 문서 검색 실패: {str(e)}")
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
