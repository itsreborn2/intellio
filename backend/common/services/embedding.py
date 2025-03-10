from typing import List, Dict, Any, Tuple
#import numpy as np
#from openai import OpenAI, AsyncOpenAI
#from pinecone import Pinecone, PodSpec, ServerlessSpec

import logging
import re
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from common.utils.util import measure_time_async
import openai
from openai import OpenAIError, Timeout
from common.services.embedding_models import EmbeddingModelManager, EmbeddingProvider, EmbeddingProviderFactory, EmbeddingModelConfig, EmbeddingModelType
from langchain_core.embeddings import Embeddings

logger = logging.getLogger(__name__)

class EmbeddingService:
    def __init__(self, model_type: EmbeddingModelType = EmbeddingModelType.OPENAI_3_LARGE):
        self.batch_size = 100  # 임베딩 처리의 안정성을 위해 배치 크기 축소 (50 -> 20)
        self.model_manager = EmbeddingModelManager()
        #self.current_model = self.model_manager.get_default_model() # 기본 모델은 openai
        #self.current_model = self.model_manager.get_model(EmbeddingModelType.OPENAI_ADA_002) # 구글 다국어 모델\
        self.current_model_config = self.model_manager.get_model_config(model_type) # 구글 다국어 모델
        #self.current_model = self.model_manager.get_model(EmbeddingModelType.KAKAO_EMBEDDING) # 구글 다국어 모델
        
        # 현재 모델에 맞는 제공자 생성
        self.provider = EmbeddingProviderFactory.create_provider(
            self.current_model_config.provider_name,
            self.current_model_config.name
        )
        
        #self.create_pinecone_index(self.current_model)
    def change_model(self, model_type: EmbeddingModelType):
        self.current_model_config = self.model_manager.get_model_config(model_type)
        self.provider = EmbeddingProviderFactory.create_provider(
            self.current_model_config.provider_name,
            self.current_model_config.name
        )
        logger.info(f"모델 변경: {model_type}")
        
    def get_model_type(self) -> EmbeddingModelType:
        return EmbeddingModelType(self.current_model_config.name)
        
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    async def create_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """텍스트 배치의 임베딩을 생성"""
        try:
            # texts는 사용자의 프롬프트 1개 일수도 있고, 문서의 청크 여러개 일수도 있음.
            if not texts:
                return []
                
            # 텍스트 유효성 검사
            validated_texts = []
            for text in texts:
                if not text or not text.strip():
                    logger.warning("빈 텍스트 건너뜀")
                    continue
                validated_texts.append(text.strip())
            
            if not validated_texts:
                return []
            
            # 제공자를 통해 임베딩 생성
            embeddings = await self.provider.create_embeddings_async(validated_texts)
            
            # 임베딩 품질 검사
            for i, emb in enumerate(embeddings):
                if not emb or len(emb) != self.current_model_config.dimension:
                    logger.error(f"잘못된 임베딩 차원 (인덱스 {i}): {len(emb) if emb else 0}")
                    continue
            
            return embeddings
            
        except Exception as e:
            logger.error(f"임베딩 생성 중 오류 발생: {str(e)}")
            raise

    @retry(
        stop=stop_after_attempt(3),  # 최대 3번 시도
        wait=wait_exponential(multiplier=1, min=4, max=10),  # 지수 백오프
        retry=retry_if_exception_type(Timeout)  # 타임아웃 예외 시 재시도
    )
    def create_embeddings_batch_sync(self, texts: List[str]) -> List[List[float]]:
        """텍스트 배치의 임베딩을 생성 (동기 버전)"""
        try:
            if not texts:
                return []
                
            # 텍스트 유효성 검사
            validated_texts = []
            for text in texts:
                if not text or not text.strip():
                    logger.warning("빈 텍스트 건너뜀")
                    continue
                validated_texts.append(text.strip())
            
            if not validated_texts:
                return []
            
            # 제공자를 통해 임베딩 생성
            embeddings = self.provider.create_embeddings(validated_texts, embeddings_task_type="RETRIEVAL_DOCUMENT")
            
            # 임베딩 품질 검사
            for i, emb in enumerate(embeddings):
                if not emb or len(emb) != self.current_model_config.dimension:
                    logger.error(f"잘못된 임베딩 차원 (인덱스 {i}): {len(emb) if emb else 0}")
                    continue
            
            return embeddings
            
        except Exception as e:
            logger.error(f"임베딩 생성 중 오류 발생: {str(e)}")
            raise
    

    
    async def create_single_embedding_async(self, query: str) -> List[float]:
        """단일 텍스트에 대한 임베딩을 생성하고 검증"""
        try:
            if not query or not query.strip():
                logger.error("빈 쿼리 문자열")
                raise ValueError("쿼리 문자열이 비어있습니다")

            embeddings = await self.provider.create_embeddings_async([query.strip()], embeddings_task_type="RETRIEVAL_QUERY")
            
            # 임베딩 결과 검증
            if not embeddings or len(embeddings) == 0:
                logger.error("임베딩 생성 결과가 비어있음")
                raise ValueError("임베딩 생성 실패")
                
            embedding = embeddings[0]
            
            # 임베딩 벡터 검증
            if not isinstance(embedding, list) or len(embedding) != self.current_model_config.dimension:
                logger.error(f"잘못된 임베딩 형식 또는 차원: {len(embedding) if isinstance(embedding, list) else type(embedding)}")
                raise ValueError("잘못된 임베딩 형식")
            
            return embedding
        except Exception as e:
                logger.error(f"단일 임베딩 생성 실패: {str(e)}")
                raise
    def create_single_embedding(self, query: str) -> List[float]:
        """단일 텍스트에 대한 임베딩을 생성하고 검증 (동기 버전)"""
        try:
            if not query or not query.strip():
                logger.error("빈 쿼리 문자열")
                raise ValueError("쿼리 문자열이 비어있습니다")
            #  embeddings_task_type="RETRIEVAL_QUERY"
            embeddings = self.provider.create_embeddings([query.strip()], embeddings_task_type="RETRIEVAL_QUERY")
            
            # 임베딩 결과 검증
            if not embeddings or len(embeddings) == 0:
                logger.error("임베딩 생성 결과가 비어있음")
                raise ValueError("임베딩 생성 실패")
                
            embedding = embeddings[0]
            
            # 임베딩 벡터 검증
            if not isinstance(embedding, list) or len(embedding) != self.current_model_config.dimension:
                logger.error(f"잘못된 임베딩 형식 또는 차원: {len(embedding) if isinstance(embedding, list) else type(embedding)}")
                raise ValueError("잘못된 임베딩 형식")
                
            return embedding
            
        except Exception as e:
            logger.error(f"단일 임베딩 생성 실패: {str(e)}")
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
        min_score: float = 0.5,
        use_context: bool = True,
        context_window: int = 2,
        document_ids: List[str] = None
    ) -> List[Dict[str, Any]]:
        """질문과 유사한 문서 청크를 검색합니다."""
        try:
            logger.info(f"유사 문서 검색 시작 - 쿼리: {query}")
            
            # 쿼리 임베딩 생성. 프롬프트 조절하는 과정은 없네.
            query_embedding = await self.create_single_embedding_async(query)
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
                search_response = self.pinecone_index.query(
                    namespace="",
                    vector=query_embedding,
                    top_k=top_k * 5,  # 필터링을 위해 더 많은 결과 요청
                    filter=filter_dict if filter_dict else None,
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
                        "score": getattr(match, 'score', 0),  # score 속성이 없으면 0 반환
                        "metadata": match.metadata
                    }
                    formatted_results.append(result)
                    logger.debug(f"매치 정보 - ID: {match.id}, 점수: {match.score:.4f}")
                
                # score 기준으로 내림차순 정렬
                formatted_results.sort(key=lambda x: x["score"], reverse=True)

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
        

    def get_provider(self) -> EmbeddingProvider:
        return self.provider

    def get_embeddings_obj(self) -> Tuple[Embeddings, Embeddings]:
        return self.provider.get_embeddings_obj()
