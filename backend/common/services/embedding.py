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
# 순환 참조 방지를 위해 직접 임포트하지 않고 typing에서 TYPE_CHECKING을 사용
from typing import TYPE_CHECKING

# TYPE_CHECKING은 런타임에는 False로 평가됨
if TYPE_CHECKING:
    from common.services.embedding_models import EmbeddingModelManager, EmbeddingProvider, EmbeddingProviderFactory, EmbeddingModelConfig, EmbeddingModelType
else:
    # enum은 순환 참조 없이 직접 가져올 수 있음
    from common.services.embedding_models import EmbeddingModelType

from langchain_core.embeddings import Embeddings

logger = logging.getLogger(__name__)

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
        
        # 토큰 사용량 정보 저장을 위한 속성
        self.last_token_usage = None
        
        # VectorStoreManager는 필요시 외부에서 생성하여 사용
        # (관련 코드 삭제)
        
    def change_model(self, model_type: EmbeddingModelType):
        # 지연 임포트: 필요할 때만 임포트
        from common.services.embedding_models import EmbeddingProviderFactory
        
        self.current_model_config = self.model_manager.get_model_config(model_type)
        self.provider = EmbeddingProviderFactory.create_provider(
            self.current_model_config.provider_name,
            self.current_model_config.name
        )
        logger.info(f"모델 변경: {model_type}")
    def get_model_name(self) -> str:
        return self.current_model_config.name
    
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
    def create_embeddings_batch_sync(self, texts: List[str], user_id: str = None, project_type: str = None) -> List[List[float]]:
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
            embeddings = self.provider.create_embeddings(texts=validated_texts, 
                                                         embeddings_task_type="RETRIEVAL_DOCUMENT", 
                                                         user_id=user_id, project_type=project_type)
            
            # 임베딩 품질 검사
            for i, emb in enumerate(embeddings):
                if not emb or len(emb) != self.current_model_config.dimension:
                    logger.error(f"잘못된 임베딩 차원 (인덱스 {i}): {len(emb) if emb else 0}")
                    continue
                    
            # 토큰 사용량 정보가 있으면 저장
            if hasattr(self.provider, 'last_token_usage') and self.provider.last_token_usage:
                self.last_token_usage = self.provider.last_token_usage
                logger.info(f"토큰 사용량 정보 저장: {self.last_token_usage}")
            
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
           
    def get_provider(self) -> Any:  # 타입 힌트를 Any로 변경
        return self.provider

    def get_embeddings_obj(self) -> Tuple[Embeddings, Embeddings]:
        return self.provider.get_embeddings_obj()
