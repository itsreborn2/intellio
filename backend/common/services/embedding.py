from typing import List, Dict, Any, Tuple
#import numpy as np
#from openai import OpenAI, AsyncOpenAI
#from pinecone import Pinecone, PodSpec, ServerlessSpec

from loguru import logger
import re
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
#from common.utils.util import measure_time_async
import openai
from openai import OpenAIError, Timeout
from .embedding_models import EmbeddingModelManager, EmbeddingProvider, EmbeddingProviderFactory, EmbeddingModelConfig, EmbeddingModelType
from langchain_core.embeddings import Embeddings

# logger = logging.getLogger(__name__)

class EmbeddingService:
    def __init__(self, model_type: EmbeddingModelType = EmbeddingModelType.OPENAI_3_LARGE):
        # 지연 임포트: 실제 초기화 시에만 필요한 클래스 임포트
        from common.services.embedding_models import EmbeddingModelManager, EmbeddingProviderFactory
        
        self.batch_size = 100  # 임베딩 처리의 안정성을 위해 배치 크기 축소 (50 -> 20)
        self.model_manager = EmbeddingModelManager()
        self.current_model_config = self.model_manager.get_model_config(model_type) # 구글 다국어 모델
        
        # 현재 모델에 맞는 제공자 생성
        self.provider = EmbeddingProviderFactory.create_provider(
            self.current_model_config.provider_name,
            self.current_model_config.name
        )
        
        #self.create_pinecone_index(self.current_model)
    async def aclose(self):
        """비동기 임베딩 제공자의 리소스를 정리합니다."""
        try:
            if hasattr(self.provider, 'aclose') and callable(self.provider.aclose):
                await self.provider.aclose()
                logger.info(f"임베딩 제공자 {self.current_model_config.provider_name} 리소스 정리 완료")
            else:
                logger.warning(f"임베딩 제공자 {self.current_model_config.provider_name}에 aclose 메서드가 없습니다.")
        except Exception as e:
            logger.error(f"임베딩 제공자 리소스 정리 중 오류 발생: {str(e)}")
    
    def close(self):
        """동기 임베딩 제공자의 리소스를 정리합니다."""
        if hasattr(self.provider, 'close') and callable(self.provider.close):
            try:
                self.provider.close()
                #logger.info(f"임베딩 제공자 {self.current_model_config.provider_name} 동기 리소스 정리 완료")
            except Exception as e:
                logger.error(f"임베딩 제공자 동기 리소스 정리 중 오류 발생: {str(e)}")
    
    def __del__(self):
        """소멸자. 객체가 소멸할 때 동기 리소스를 정리합니다."""
        self.close()
        #if hasattr(self.provider, 'aclose') and callable(self.provider.aclose):
            #logger.warning(f"임베딩 제공자 {self.current_model_config.provider_name}의 비동기 리소스는 명시적으로 aclose()를 호출해야 합니다.")
            
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
        retry=retry_if_exception_type((Timeout, openai.APITimeoutError, openai.APIError, openai.RateLimitError))  # 타임아웃 예외 시 재시도
    )
    def create_embeddings_batch_sync(self, texts: List[str], user_id: str = None, project_type: str = None, existing_db_session = None) -> List[List[float]]:
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
            
            # 제공자를 통해 임베딩 생성 - 기존 세션 전달
            embeddings = self.provider.create_embeddings(
                texts=validated_texts, 
                embeddings_task_type="RETRIEVAL_DOCUMENT", 
                user_id=user_id, 
                project_type=project_type,
                existing_db_session=existing_db_session
            )
            
            # 임베딩 품질 검사
            for i, emb in enumerate(embeddings):
                if not emb or len(emb) != self.current_model_config.dimension:
                    logger.error(f"잘못된 임베딩 차원 (인덱스 {i}): {len(emb) if emb else 0}")
                    continue
            
            return embeddings

        except (openai.APITimeoutError, Timeout) as e:
            logger.error(f"OpenAI 타임아웃 발생: {str(e)}")
            raise
        except openai.RateLimitError as e:
            logger.error(f"OpenAI 레이트 리밋 발생: {str(e)}")
            raise
        except openai.APIError as e:
            logger.error(f"OpenAI API 오류: {str(e)}")
            raise        
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
           
    def get_provider(self) -> Any:  # 타입 힌트를 Any로 변경
        return self.provider

    def get_embeddings_obj(self) -> Tuple[Embeddings, Embeddings]:
        return self.provider.get_embeddings_obj()
