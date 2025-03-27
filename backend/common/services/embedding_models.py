from enum import Enum
from typing import Dict, Optional, List, Union, Tuple, Any, Callable, Awaitable
from pydantic import BaseModel, Field, ConfigDict
from abc import ABC, abstractmethod
from openai import AsyncOpenAI, OpenAI
import asyncio

from langchain_google_vertexai.embeddings import VertexAIEmbeddings
from langchain_core.embeddings import Embeddings
from langchain_openai import OpenAIEmbeddings
import numpy as np
from common.core.config import settings
import tiktoken
from transformers import AutoTokenizer
from tokenizers import Tokenizer
import logging
import nltk
import google.api_core.exceptions
import tenacity
import re
import torch
from uuid import UUID
from common.services.token_usage_service import save_token_usage, ProjectType, TokenType
from sqlalchemy.ext.asyncio import AsyncSession
# 임포트 추가
import inspect
from contextlib import asynccontextmanager, contextmanager
from google.oauth2 import service_account
try:
    from langchain_community.callbacks.manager import get_openai_callback
except ImportError:
    try:
        # 이전 버전 지원
        from langchain.callbacks import get_openai_callback
        import warnings
        warnings.warn(
            "langchain.callbacks에서 get_openai_callback을 임포트하는 것은 deprecated되었습니다. "
            "langchain_community.callbacks.manager에서 임포트하도록 수정하세요.",
            DeprecationWarning
        )
    except ImportError:
        logger = logging.getLogger(__name__)
        logger.warning("LangChain 콜백 모듈을 임포트할 수 없습니다.")
        
        # 더미 컨텍스트 매니저 생성
        @contextmanager
        def get_openai_callback():
            class DummyCallback:
                def __init__(self):
                    self.prompt_tokens = 0
                    self.completion_tokens = 0
                    self.total_tokens = 0
                    self.total_cost = 0.0
            yield DummyCallback()

# 타입 힌트를 위한 조건부 임포트
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from common.services.token_usage_service import TokenUsageTracker

logger = logging.getLogger(__name__)

# 글로벌 토큰 사용량 저장 큐
class TokenUsageQueue:
    """
    토큰 사용량 데이터를 저장하는 큐
    저장 요청은 큐에 추가되고, 백그라운드 태스크에서 처리됨
    """
    _instance = None
    _lock = asyncio.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._queue = asyncio.Queue()
            cls._instance._task = None
            cls._instance._initialized = False
            cls._instance._session_factory = None
        return cls._instance
    
    async def initialize(self, session_factory: Callable[[], Awaitable[Any]]):
        """
        큐 초기화 및 백그라운드 처리 태스크 시작
        
        Args:
            session_factory: 데이터베이스 세션을 생성하는 비동기 팩토리 함수
        """
        if not self._initialized:
            async with self._lock:
                if not self._initialized:
                    self._session_factory = session_factory
                    self._task = asyncio.create_task(self._process_queue())
                    self._initialized = True
                    logger.info("토큰 사용량 저장 큐 초기화 완료")
    
    async def add_usage(self, user_id: UUID, project_type: str, token_type: str, 
                       model_name: str, token_data: Dict[str, Any]):
        """
        토큰 사용량 데이터를 큐에 추가
        
        Args:
            user_id: 사용자 ID
            project_type: 프로젝트 유형
            token_type: 토큰 유형
            model_name: 모델 이름
            token_data: 토큰 사용량 데이터
        """
        if not self._initialized:
            logger.warning("토큰 사용량 큐가 초기화되지 않았습니다")
            return
            
        await self._queue.put({
            "user_id": user_id,
            "project_type": project_type,
            "token_type": token_type,
            "model_name": model_name,
            "token_data": token_data
        })
        logger.debug(f"토큰 사용량 데이터가 큐에 추가됨 ({user_id}, {project_type}, {token_type})")
    
    async def _process_queue(self):
        """큐에 있는 토큰 사용량 데이터를 처리하는 백그라운드 태스크"""
        try:
            logger.info("토큰 사용량 처리 태스크 시작")
            while True:
                try:
                    # 큐에서 데이터 가져오기
                    usage_data = await self._queue.get()
                    
                    # 지연 임포트 - 실제 사용 시점에만 임포트
                    from common.services.token_usage_service import save_token_usage, ProjectType, TokenType
                    
                    try:
                        # 세션 생성
                        if self._session_factory:
                            async for db in self._session_factory():
                                try:
                                    # 토큰 사용량 저장
                                    await save_token_usage(
                                        db=db,
                                        user_id=usage_data["user_id"],
                                        project_type=ProjectType(usage_data["project_type"]),
                                        token_type=TokenType(usage_data["token_type"]),
                                        model_name=usage_data["model_name"],
                                        token_data=usage_data["token_data"]
                                    )
                                    logger.debug(f"토큰 사용량 데이터 저장 완료: {usage_data['user_id']}")
                                except Exception as db_error:
                                    logger.error(f"토큰 사용량 저장 중 오류 발생: {str(db_error)}")
                                finally:
                                    # 태스크 완료 표시
                                    self._queue.task_done()
                                # 세션은 한 번만 가져오면 됨
                                break
                        else:
                            logger.error("세션 팩토리가 설정되지 않았습니다")
                            self._queue.task_done()
                    except Exception as e:
                        logger.error(f"토큰 사용량 처리 중 오류 발생: {str(e)}")
                        self._queue.task_done()
                except asyncio.CancelledError:
                    # 태스크가 취소된 경우
                    logger.info("토큰 사용량 처리 태스크가 취소되었습니다")
                    return
                except Exception as e:
                    # 예외 발생 시 로깅하고 계속 진행
                    logger.error(f"토큰 사용량 큐 처리 중 예외 발생: {str(e)}")
                    continue
        except asyncio.CancelledError:
            logger.info("토큰 사용량 처리 태스크가 취소되었습니다")
        except Exception as e:
            logger.error(f"토큰 사용량 처리 태스크에서 예외 발생: {str(e)}")
    
    async def shutdown(self):
        """백그라운드 태스크 종료 및 남은 작업 처리"""
        if self._task and not self._task.done():
            # 남은 작업 처리 대기
            await self._queue.join()
            # 태스크 취소
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                logger.info("토큰 사용량 처리 태스크가 정상적으로 종료되었습니다")
            finally:
                self._task = None
                self._initialized = False

# 토큰 사용량 추적 헬퍼 함수
def track_token_usage_bg(
    user_id: Optional[UUID] = None,
    project_type: Optional[str] = None,
    token_type: Optional[str] = None,
    model_name: Optional[str] = None
):
    """
    토큰 사용량을 비동기적으로 백그라운드에서 추적하기 위한 데코레이터
    
    사용 예시:
    
    @track_token_usage_bg(project_type="doceasy", token_type="embedding")
    async def create_embeddings_async(self, texts: List[str], user_id: UUID = None) -> List[List[float]]:
        # 함수 구현...
        # 토큰 사용량은 자동으로 수집되어 백그라운드에서 저장됨
    
    """
    def decorator(func):
        if asyncio.iscoroutinefunction(func):
            # 비동기 함수인 경우
            async def wrapper(*args, **kwargs):
                # 파라미터에서 필요한 값 추출
                _user_id = kwargs.get('user_id', user_id)
                _project_type = kwargs.get('project_type', project_type)
                _token_type = kwargs.get('token_type', token_type) or "embedding"  # 기본값
                _model_name = kwargs.get('model_name', None)
                logger.info(f"[track_token_usage_bg][async] _user_id: {_user_id}, _project_type: {_project_type}, _token_type: {_token_type}, _model_name: {_model_name}")
                # 모델 이름이 없으면 클래스 인스턴스에서 가져오기
                if not _model_name and len(args) > 0 and hasattr(args[0], 'model_name'):
                    _model_name = args[0].model_name
                
                if _user_id and _project_type:
                    # LangChain 콜백 핸들러를 사용하여 토큰 수집
                    try:
                        # OpenAI 포맷의 토큰 콜백
                        with get_openai_callback() as cb:
                            # 원래 함수 실행
                            result = await func(*args, **kwargs)
                            
                            # 토큰 사용량 데이터 수집
                            token_data = {
                                "prompt_tokens": cb.prompt_tokens,
                                "completion_tokens": cb.completion_tokens if _token_type == "llm" else None,
                                "total_tokens": cb.total_tokens,
                                "total_cost": cb.total_cost
                            }
                            
                            # 백그라운드에서 토큰 사용량 저장
                            queue = TokenUsageQueue()
                            await queue.add_usage(
                                user_id=_user_id,
                                project_type=_project_type,
                                token_type=_token_type,
                                model_name=_model_name,
                                token_data=token_data
                            )
                            
                            return result
                    except (NameError, ImportError):
                        # 콜백 핸들러를 가져올 수 없는 경우, 원래 함수만 실행
                        logger.warning("OpenAI 콜백 핸들러를 가져올 수 없어 토큰 추적 없이 실행합니다")
                        return await func(*args, **kwargs)
                else:
                    # 필요한 파라미터가 없는 경우, 원래 함수만 실행
                    return await func(*args, **kwargs)
        else:
            # 동기 함수인 경우
            def wrapper(*args, **kwargs):
                # 파라미터에서 필요한 값 추출
                _user_id = kwargs.get('user_id', user_id)
                _project_type = kwargs.get('project_type', project_type)
                _token_type = kwargs.get('token_type', token_type) or "embedding"  # 기본값
                _model_name = kwargs.get('model_name', None)
                logger.info(f"[track_token_usage_bg][sync] _user_id: {_user_id}, _project_type: {_project_type}, _token_type: {_token_type}, _model_name: {_model_name}")
                # 모델 이름이 없으면 클래스 인스턴스에서 가져오기
                if not _model_name and len(args) > 0 and hasattr(args[0], 'model_name'):
                    _model_name = args[0].model_name
                
                # 원래 함수 실행
                result = func(*args, **kwargs)
                logger.warning(f"임베딩 결과 객체 구조: {dir(result)}")
                # 필요한 파라미터가 있고 이벤트 루프가 실행 중인 경우
                if _user_id and _project_type:
                    try:
                        # 비동기 함수를 실행하기 위한 코드
                        async def process_token_usage():
                            # OpenAI 토큰 정보가 있는 경우
                            if hasattr(result, "usage_metadata"):
                                
                                # 토큰 사용량 데이터 수집
                                token_data = {
                                    "prompt_tokens": result.usage.prompt_tokens,
                                    "completion_tokens": result.usage.completion_tokens if hasattr(result.usage, "completion_tokens") else None,
                                    "total_tokens": result.usage.total_tokens,
                                    "total_cost": 0.0  # 비용 계산 로직 필요
                                }
                                logger.info(f"토큰 정보: {token_data}")
                                
                                # 백그라운드에서 토큰 사용량 저장
                                queue = TokenUsageQueue()
                                await queue.add_usage(
                                    user_id=_user_id,
                                    project_type=_project_type,
                                    token_type=_token_type,
                                    model_name=_model_name,
                                    token_data=token_data
                                )
                            else:
                                logger.info("토큰 사용량 정보가 없습니다, no usage_metadata")
                        
                        # 이벤트 루프가 실행 중인지 확인
                        try:
                            loop = asyncio.get_event_loop()
                            if loop.is_running():
                                # 이벤트 루프가 실행 중이면 태스크 생성
                                asyncio.create_task(process_token_usage())
                            else:
                                # 이벤트 루프가 실행 중이 아니면 별도로 실행
                                asyncio.run(process_token_usage())
                        except RuntimeError:
                            logger.warning("이벤트 루프를 가져올 수 없어 토큰 사용량 저장을 건너뜁니다")
                    except Exception as e:
                        logger.error(f"토큰 사용량 처리 중 오류 발생: {str(e)}")
                
                return result
        
        # 래퍼 함수에 원래 함수의 메타데이터 복사
        wrapper.__name__ = func.__name__
        wrapper.__doc__ = func.__doc__
        wrapper.__annotations__ = func.__annotations__
        
        return wrapper
    
    return decorator

class EmbeddingModelType(str, Enum):
    #OPENAI_ADA_002 = "text-embedding-ada-002"
    #OPENAI_ADA_002 = "text-embedding-3-small"
    OPENAI_ADA_002 = "text-embedding-ada-002"
    OPENAI_3_LARGE = "text-embedding-3-large"
    GOOGLE_MULTI_LANG = "text-multilingual-embedding-002"
    GOOGLE_EN = "text-embedding-005"
    KAKAO_EMBEDDING = "kf-deberta"
    UPSTAGE = "upstage-embedding-v1"
    BGE_M3 = "dragonkue/bge-m3-ko"


class EmbeddingModelConfig(BaseModel):
    name: str
    dimension: int
    provider_name: EmbeddingModelType
    description: Optional[str] = None
    max_tokens: Optional[int] = None
    
class EmbeddingModelManager:
    def __init__(self):
        self.models: Dict[str, EmbeddingModelConfig] = {
            EmbeddingModelType.OPENAI_ADA_002: EmbeddingModelConfig(
                name=EmbeddingModelType.OPENAI_ADA_002,
                dimension=3072 if EmbeddingModelType.OPENAI_ADA_002 == "text-embedding-3-large" else 1536,
                provider_name=EmbeddingModelType.OPENAI_ADA_002,
                description="OpenAI의 범용 임베딩 모델",
                max_tokens=8191 #전체 입력 토큰만 봄.
            ),
            EmbeddingModelType.OPENAI_3_LARGE: EmbeddingModelConfig(
                name=EmbeddingModelType.OPENAI_3_LARGE,
                dimension=3072,
                provider_name=EmbeddingModelType.OPENAI_3_LARGE,
                description="OpenAI 임베딩 Large 3",
                max_tokens=8191 #전체 입력 토큰만 봄.
            ),
            EmbeddingModelType.GOOGLE_MULTI_LANG : EmbeddingModelConfig(
                name=EmbeddingModelType.GOOGLE_MULTI_LANG ,
                dimension=768,
                provider_name=EmbeddingModelType.GOOGLE_MULTI_LANG,
                description="Google의 다국어 지원 임베딩 모델",
                max_tokens=2048 # 청크단위 2048이내, 전체 토큰 20000이내
            ),
            EmbeddingModelType.GOOGLE_EN: EmbeddingModelConfig(
                name=EmbeddingModelType.GOOGLE_EN,
                # text-embedding-preview-0815최신 임베딩 모델이라는데..
                dimension=768,
                provider_name=EmbeddingModelType.GOOGLE_EN,
                description="Google의 영어 임베딩 모델",
                max_tokens=2048
            ),
            EmbeddingModelType.KAKAO_EMBEDDING: EmbeddingModelConfig(
                name=EmbeddingModelType.KAKAO_EMBEDDING,
                dimension=768,
                provider_name=EmbeddingModelType.KAKAO_EMBEDDING,
                description="Kakao의 한국어 임베딩 모델",
                max_tokens=512
            ),
            EmbeddingModelType.UPSTAGE: EmbeddingModelConfig(
                name=EmbeddingModelType.UPSTAGE,
                dimension=4096, # 수정필요
                provider_name=EmbeddingModelType.UPSTAGE,
                description="Upstage의 임베딩 모델",
                max_tokens=4000
            ),
            EmbeddingModelType.BGE_M3: EmbeddingModelConfig(
                name=EmbeddingModelType.BGE_M3,
                dimension=1024,
                provider_name=EmbeddingModelType.BGE_M3,
                description="BGE-M3 임베딩 모델",
                max_tokens=8190
            )
        }
        
    def get_model_config(self, model_name: str | EmbeddingModelType) -> Optional[EmbeddingModelConfig]:
        """모델 이름으로 모델 설정 조회
        Args:
            model_name: 모델 이름 (문자열 또는 EmbeddingModelType enum)
        Returns:
            Optional[EmbeddingModelConfig]: 모델 설정 정보. 없으면 None 반환
        """
        try:
            # 문자열이 입력된 경우 EmbeddingModelType으로 변환
            if isinstance(model_name, str):
                model_key = EmbeddingModelType(model_name)
            else:
                model_key = model_name
                
            return self.models.get(model_key)
            
        except ValueError as e:
            logger.warning(f"Invalid model_name: {model_name}. Error: {str(e)}")
            return None
    
    def get_default_model(self) -> EmbeddingModelConfig:
        """기본 임베딩 모델 반환 (OpenAI)"""
        return self.models["text-embedding-ada-002"]
    
    def get_multilingual_model(self) -> EmbeddingModelConfig:
        """다국어 지원 모델 반환 (Google)"""
        return self.models["text-multilingual-embedding-002"]
    
    def add_model(self, config: EmbeddingModelConfig) -> None:
        """새로운 임베딩 모델 추가"""
        self.models[config.name] = config
    
    def list_models(self) -> Dict[str, EmbeddingModelConfig]:
        """등록된 모든 모델 조회"""
        return self.models
    

########################################################
# 임베딩 factory and provider
########################################################
class TokenCounter:
    """토큰 카운팅을 위한 유틸리티 클래스"""
    
    @staticmethod
    def count_tokens_openai(text: str, model: str = "text-embedding-ada-002") -> int:
        """OpenAI 모델의 토큰 수 계산"""
        try:
            encoding = tiktoken.encoding_for_model(model)
            return len(encoding.encode(text))
        except Exception as e:
            logger.warning(f"토큰 카운팅 실패 (OpenAI): {str(e)}")
            # 실패시 문자 길이로 대략적 계산 (안전을 위해 약간 높게)
            return len(text.split()) * 2

    @staticmethod
    def count_tokens_google(text: str) -> int:
        """Google 모델의 토큰 수 계산
        Google의 임베딩 모델은 2048 토큰을 지원하며,
        대략적으로 단어 기준으로 계산합니다.
        """
        try:
            # 공백을 기준으로 단어를 분리하고 구두점도 고려
            words = re.findall(r'\b\w+\b|[.,!?;]', text)
            # 구글 모델의 토큰화는 대략 단어당 1.3개의 토큰을 사용
            estimated_tokens = int(len(words) * 1.3)
            return estimated_tokens
        except Exception as e:
            logger.warning(f"토큰 카운팅 실패 (Google): {str(e)}")
            # 실패시 더 보수적으로 계산
            return len(text.split()) * 2

    @staticmethod
    def count_tokens_upstage(text:str) -> int:
        tokenizer = Tokenizer.from_pretrained("upstage/solar-pro-tokenizer")
        enc = tokenizer.encode(text)
        inv_vocab = {v: k for k, v in tokenizer.get_vocab().items()}
        tokens = [inv_vocab[token_id] for token_id in enc.ids]
        return len(tokens)

class EmbeddingProvider(ABC):
    """임베딩 제공자의 추상 기본 클래스"""
    
    def __init__(self, model_name: str, max_tokens: int):
        self.model_name = model_name
        self.max_tokens = max_tokens
    
    def split_text_by_tokens(self, text: str) -> List[str]:
        """토큰 제한을 초과하는 텍스트를 분할"""
        try:
            sentences = nltk.sent_tokenize(text)
        except LookupError:
            nltk.download('punkt')
            sentences = nltk.sent_tokenize(text)
        except Exception as e:
            logger.warning(f"문장 분할 실패: {str(e)}")
            sentences = text.split(". ")

        chunks = []
        current_chunk = []
        current_tokens = 0

        for sentence in sentences:
            sentence = sentence.strip()
            tokens = self.count_tokens(sentence)

            if tokens > self.max_tokens:
                logger.warning(f"문장이 토큰 제한({self.max_tokens}) 초과: {tokens} tokens, 문장 길이로 분할 시도.")
                # 문장이 너무 길 경우, 오류 발생 또는 추가 처리 필요
                if len(sentence) > self.max_tokens * 3 : # max_tokens의 3배 이상일 경우 분할 포기
                    logger.error(f"문장 길이가 너무 길어 분할 불가: {len(sentence)} 문자")
                    continue
                else:
                    chunks.extend([sentence[i:i+self.max_tokens*3] for i in range(0, len(sentence), self.max_tokens*3)])
                continue

            if current_tokens + tokens <= self.max_tokens:
                current_chunk.append(sentence)
                current_tokens += tokens
            else:
                chunks.append(" ".join(current_chunk))
                current_chunk = [sentence]
                current_tokens = tokens

        if current_chunk:
            chunks.append(" ".join(current_chunk))

        return chunks

    def validate_and_split_texts(self, texts: List[str]) -> List[List[str]]:
        """범용 토큰 검증 및 분할 (전체 토큰 합만 체크)"""
        total_tokens = sum(self.count_tokens(text) for text in texts)
        logger.info(f"범용 토큰 총합: {total_tokens}. 제한: {self.max_tokens}")
        if total_tokens <= self.max_tokens:
            return [texts]  # 전체 토큰이 제한 이내면 그대로 반환
            
        # 토큰 제한 초과시 분할 처리
        batches = []
        current_batch = []
        current_tokens = 0
        
        for text in texts:
            text = text.strip()
            if not text:
                continue
                
            tokens = self.count_tokens(text)
            if current_tokens + tokens <= self.max_tokens:
                current_batch.append(text)
                current_tokens += tokens
            else:
                if current_batch:
                    batches.append(current_batch)  # Max_tokens 초과 batches에 추가해두고
                current_batch = [text]  # 새로운 배치 시작
                current_tokens = tokens
                
        if current_batch:
            batches.append(current_batch)
            
        return batches
    @abstractmethod
    def get_embeddings_obj(self) -> Tuple[Embeddings, Embeddings]:
        """임베딩 객체 반환, [Sync, Async]"""
        pass

    @abstractmethod
    async def create_embeddings_async(
        self, 
        texts: List[str], 
        embeddings_task_type: str = "RETRIEVAL_DOCUMENT", 
        user_id: Optional[UUID] = None, 
        project_type: Optional[str] = None
    ) -> List[List[float]]:
        """텍스트 리스트의 임베딩을 비동기로 생성"""
        pass

    @abstractmethod
    def create_embeddings(
        self, 
        texts: List[str], 
        embeddings_task_type: str = "RETRIEVAL_QUERY", 
        user_id: Optional[UUID] = None, 
        project_type: Optional[str] = None
    ) -> List[List[float]]:
        """텍스트 리스트의 임베딩을 동기로 생성"""
        pass

    @abstractmethod
    def count_tokens(self, text: str) -> int:
        """텍스트의 토큰 수를 계산"""
        pass

class OpenAIEmbeddingProvider(EmbeddingProvider):
    def __init__(self, model_name: str, max_tokens: int = 8191):
        self.model_name = model_name
        self.max_tokens = max_tokens
        self.client = OpenAI(
            api_key=settings.OPENAI_API_KEY
        )
        self.async_client = AsyncOpenAI(
            api_key=settings.OPENAI_API_KEY
        )
        self.encoder = tiktoken.encoding_for_model(model_name)
        
        # 마지막 토큰 사용량 저장 속성
        self.last_token_usage = None
        
        # 임베딩 요청 배치 크기 제한
        self.max_batch_size = 100  # OpenAI 권장 배치 크기

    def count_tokens(self, text: str) -> int:
        return TokenCounter.count_tokens_openai(text, self.model_name)
        
    def get_embeddings_obj(self) -> Tuple[Embeddings, Embeddings]:
        return self.client, self.client
    
    async def create_embeddings_async(
        self, 
        texts: List[str], 
        embeddings_task_type: str = "RETRIEVAL_DOCUMENT", 
        user_id: Optional[UUID] = None, 
        project_type: Optional[str] = None,
        db: Optional[AsyncSession] = None
    ) -> List[List[float]]:
        """비동기적으로 임베딩 생성"""
        if not texts:
            return []
            
        all_embeddings = []
        batches = [texts[i:i + self.max_batch_size] for i in range(0, len(texts), self.max_batch_size)]
        
        # 토큰 사용량 누적을 위한 변수들
        total_tokens = 0
        total_prompt_tokens = 0
        
        for batch in batches:
            try:
                # 비동기 클라이언트 생성
                # OpenAI API 직접 호출
                response = await self.async_client.embeddings.create(
                    model=self.model_name,
                    input=batch
                )
                
                # 임베딩 데이터 추출
                batch_embeddings = [item.embedding for item in response.data]
                all_embeddings.extend(batch_embeddings)
                
                # 토큰 사용량 누적
                if user_id and project_type:
                    total_tokens += response.usage.total_tokens
                    total_prompt_tokens += response.usage.prompt_tokens
                    logger.info(f"OpenAI[Async] 임베딩 토큰 사용량: {response.usage.total_tokens} (누적 {total_tokens})")
                
            except Exception as e:
                logger.error(f"OpenAI 임베딩 생성 실패: {str(e)}")
                raise
        
        # 모든 배치 처리 후 누적된 토큰 사용량 저장
        if user_id and project_type and total_tokens > 0:
            # 토큰 사용량 데이터 구성
            self.last_token_usage = {
                "prompt_tokens": total_prompt_tokens,
                "completion_tokens": None,
                "total_tokens": total_tokens,
                "total_cost": 0.0  # 비용 계산 로직 필요시 추가
            }
            logger.info(f"OpenAI[Async] 임베딩 총 토큰 사용량: {total_tokens} (prompt: {total_prompt_tokens})")
            
            # 토큰 사용량을 큐에 추가
            if db:
                try:
                    await save_token_usage(
                        db=db,
                        user_id=user_id,
                        project_type=ProjectType(project_type),
                        token_type=TokenType.EMBEDDING,
                        model_name=self.model_name,
                        token_data=self.last_token_usage
                    )
                except Exception as e:
                    logger.error(f"토큰 사용량 저장 실패: {str(e)}")
        
        return all_embeddings
    
    def create_embeddings(
        self, 
        texts: List[str], 
        embeddings_task_type: str = "RETRIEVAL_QUERY", 
        user_id: Optional[UUID] = None, 
        project_type: Optional[str] = None,
        db: Optional[AsyncSession] = None
    ) -> List[List[float]]:
        """동기적으로 임베딩 생성"""
        # 텍스트가 없으면 빈 배열 반환
        if not texts:
            return []
            
        all_embeddings = []
        batches = [texts[i:i + self.max_batch_size] for i in range(0, len(texts), self.max_batch_size)]
        
        # 토큰 사용량 누적을 위한 변수들
        total_tokens = 0
        total_prompt_tokens = 0
        
        for batch in batches:
            try:
                response = self.client.embeddings.create(
                    model=self.model_name,
                    input=batch
                )
                
                batch_embeddings = [item.embedding for item in response.data]
                all_embeddings.extend(batch_embeddings)
                
                # 토큰 사용량 누적
                if user_id and project_type:
                    total_tokens += response.usage.total_tokens
                    total_prompt_tokens += response.usage.prompt_tokens
                    logger.info(f"OpenAI[Sync] 임베딩 토큰 사용량: {response.usage.total_tokens} (누적 {total_tokens})")
                
            except Exception as e:
                logger.error(f"OpenAI 임베딩 생성 실패: {str(e)}")
                raise
        
        # 모든 배치 처리 후 누적된 토큰 사용량 저장
        if user_id and project_type and total_tokens > 0:
            # 토큰 사용량 데이터 구성
            self.last_token_usage = {
                "prompt_tokens": total_prompt_tokens,
                "completion_tokens": 0,
                "total_tokens": total_tokens,
                "total_cost": 0.0  # 비용 계산 로직 필요시 추가
            }
            logger.info(f"OpenAI[Sync] 임베딩 총 토큰 사용량: {total_tokens} (prompt: {total_prompt_tokens})")
        
        return all_embeddings

class UpstageEmbeddingProvider(EmbeddingProvider):
    def __init__(self, model_name: str, max_tokens: int = 8191):
        super().__init__(model_name, max_tokens)
        # 업스테이지는 OpenAI 호환 API를 제공하므로 OpenAIEmbeddings 사용 가능
        self.api_key = settings.UPSTAGE_API_KEY
        self.client = OpenAI(api_key=self.api_key, base_url="https://api.upstage.ai/v1")
        self.async_client = AsyncOpenAI(api_key=self.api_key, base_url="https://api.upstage.ai/v1")
        
        # 마지막 토큰 사용량 저장 속성
        self.last_token_usage = None

    # embedding-query : Solar-based Query Embedding model with a 4k context limit. This model is optimized for embedding user's question in information-seeking tasks such as retrieval & reranking.
    # embedding-passage : Solar-based Passage Embedding model with a 4k context limit. This model is optimized for embedding documents or texts to be searched.
    # Upstage's embedding API can process texts in batches.
    # You can send a text array instead of a single text to API endpoint for batch processing. 
    # In most cases, batch processing is faster and more efficient than processing items one by one. 
    # One batch request can contain up to 100 texts, \
    # and the total number of tokens in the array(tokens per each request) should be less than 204,800.
    def count_tokens(self, text: str) -> int:
        return TokenCounter.count_tokens_upstage(text)
    
    def get_embeddings_obj(self) -> Tuple[Embeddings, Embeddings]:
        """임베딩 객체 반환, [Sync, Async]"""
        return self.client, self.client
    
    @track_token_usage_bg(token_type="embedding")
    async def create_embeddings_async(
        self, 
        texts: List[str], 
        embeddings_task_type: str = "RETRIEVAL_QUERY",
        user_id: Optional[UUID] = None,
        project_type: Optional[str] = None,
        db: Optional[AsyncSession] = None
    ) -> List[List[float]]:
        if not texts:
            return []
            
        all_embeddings = []
        
        # 토큰 사용량 누적을 위한 변수들
        total_tokens = 0
        total_prompt_tokens = 0
        
        # Text 분할 필요 시 처리
        batches = self.validate_and_split_texts(texts)
        for batch in batches:
            try:
                # 비동기 클라이언트 생성
                # OpenAI API 직접 호출
                response = await self.async_client.embeddings.create(
                    model="embedding-query",
                    input=batch
                )
                
                # 임베딩 데이터 추출
                batch_embeddings = [item.embedding for item in response.data]
                all_embeddings.extend(batch_embeddings)
                
                # 토큰 사용량 누적
                if user_id and project_type:
                    total_tokens += response.usage.total_tokens
                    total_prompt_tokens += response.usage.prompt_tokens
                    logger.info(f"Upstage[Async] 임베딩 토큰 사용량: {response.usage.total_tokens} (누적 {total_tokens})")
                
            except Exception as e:
                logger.error(f"Upstage 임베딩 생성 실패: {str(e)}")
                raise
        
        # 모든 배치 처리 후 누적된 토큰 사용량 저장
        if user_id and project_type and total_tokens > 0:
            # 토큰 사용량 데이터 구성
            self.last_token_usage = {
                "prompt_tokens": total_prompt_tokens,
                "completion_tokens": None,
                "total_tokens": total_tokens,
                "total_cost": 0.0  # 비용 계산 로직 필요시 추가
            }
            logger.info(f"Upstage[Async] 임베딩 총 토큰 사용량: {total_tokens} (prompt: {total_prompt_tokens})")
        
        return all_embeddings

    def create_embeddings(
        self, 
        texts: List[str], 
        embeddings_task_type: str = "RETRIEVAL_QUERY",
        user_id: Optional[UUID] = None,
        project_type: Optional[str] = None
    ) -> List[List[float]]:
        all_embeddings = []
        
        # 토큰 사용량 누적을 위한 변수들
        total_tokens = 0
        total_prompt_tokens = 0
        
        # Text 분할 필요 시 처리
        batches = self.validate_and_split_texts(texts)
        for batch in batches:
            try:
                # OpenAI API 직접 호출
                response = self.client.embeddings.create(
                    model="embedding-query",
                    input=batch
                )
                
                # 임베딩 데이터 추출
                batch_embeddings = [item.embedding for item in response.data]
                all_embeddings.extend(batch_embeddings)
                
                # 토큰 사용량 누적
                if user_id and project_type:
                    total_tokens += response.usage.total_tokens
                    total_prompt_tokens += response.usage.prompt_tokens
                    logger.info(f"Upstage[Sync] 임베딩 토큰 사용량: {response.usage.total_tokens} (누적 {total_tokens})")
                
            except Exception as e:
                logger.error(f"Upstage 임베딩 생성 실패: {str(e)}")
                raise
        
        # 모든 배치 처리 후 누적된 토큰 사용량 저장
        if user_id and project_type and total_tokens > 0:
            # 토큰 사용량 데이터 구성
            self.last_token_usage = {
                "prompt_tokens": total_prompt_tokens,
                "completion_tokens": 0,
                "total_tokens": total_tokens,
                "total_cost": 0.0  # 비용 계산 로직 필요시 추가
            }
            logger.info(f"Upstage[Sync] 임베딩 총 토큰 사용량: {total_tokens} (prompt: {total_prompt_tokens})")
        
        return all_embeddings

class BGE_M3_EmbeddingProvider(EmbeddingProvider):
    def __init__(self, model_name: str, max_tokens: int = 8191):
        from sentence_transformers import SentenceTransformer
        super().__init__(model_name, max_tokens)
        self.model = SentenceTransformer(model_name)
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        
    def count_tokens(self, text: str) -> int:
        try:
            tokens = self.tokenizer.encode(text)
            return len(tokens)
        except Exception as e:
            logger.warning(f"BGE_M3 토크나이저 토큰 카운팅 실패: {str(e)}")
            # 실패시 문자 길이로 대략적 계산
            return len(text.split()) * 2
    
    
    
    def get_embeddings_obj(self) -> Tuple[Embeddings, Embeddings]:
        """임베딩 객체 반환, [Sync, Async]"""
        return self.model, self.model   
        
    def create_embeddings(
        self, 
        texts: List[str], 
        embeddings_task_type: str = "RETRIEVAL_QUERY",
        user_id: Optional[UUID] = None,
        project_type: Optional[str] = None
    ) -> List[List[float]]:
        try:
            batches = self.validate_and_split_texts(texts)
            logger.info(f"BGE-M3 임베딩 생성 시작: {len(batches)} 배치")
            
            all_embeddings = []
            for batch in batches:
                batch_embeddings = self.model.encode(batch).tolist()
                all_embeddings.extend(batch_embeddings)
            
            return all_embeddings
        except Exception as e:
            logger.error(f"BGE-M3 임베딩 생성 실패 (동기): {str(e)}")
            raise
        
    async def create_embeddings_async(
        self, 
        texts: List[str], 
        embeddings_task_type: str = "RETRIEVAL_QUERY",
        user_id: Optional[UUID] = None,
        project_type: Optional[str] = None
    ) -> List[List[float]]:
        try:
            batches = self.validate_and_split_texts(texts)
            logger.info(f"BGE-M3 임베딩 생성 시작 (비동기): {len(batches)} 배치")
            
            all_embeddings = []
            for batch in batches:
                batch_embeddings = await asyncio.to_thread(self.model.encode, batch)
                all_embeddings.extend(batch_embeddings.tolist())
            
            return all_embeddings
        except Exception as e:
            logger.error(f"BGE-M3 임베딩 생성 실패 (비동기): {str(e)}")
            raise

class GoogleEmbeddingProvider(EmbeddingProvider):
    _instance = None
    _lock = asyncio.Lock()  # 비동기 환경에서의 thread-safe를 위한 lock
    _is_initialized = False
    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super().__new__(cls)
        return cls._instance
    def __init__(self, model_name: str, max_tokens: int = 2048):
        if not self._is_initialized:
            super().__init__(model_name, max_tokens)
            
            self.__class__._is_initialized = True
        self._initialize_model(model_name, max_tokens)

    def _initialize_model(self, model_name, max_tokens):
        """모델 초기화 로직"""
        try:
            project_id = settings.GOOGLE_PROJECT_ID_VERTEXAI
            location = settings.GOOGLE_LOCATION_VERTEXAI
            credentials_path = settings.GOOGLE_APPLICATION_CREDENTIALS_VERTEXAI
            
            if not project_id:
                raise ValueError("GOOGLE_PROJECT_ID_VERTEXAI 환경 변수가 설정되지 않았습니다.")
            
            # 서비스 계정 키 JSON 파일로부터 credentials 객체 생성
            credentials = service_account.Credentials.from_service_account_file(credentials_path)
            #vertexai.init(project=project_id, location=location, credentials=credentials)
            
            # 임베딩 모델 로드
            #self.model = TextEmbeddingModel.from_pretrained(model_name)
            self.model = VertexAIEmbeddings(
                                    model=model_name,
                                    location=location,
                                    credentials=credentials)
            logger.info(f"Google Embedding 모델 초기화 완료 : {model_name}")
        except Exception as e:
            logger.error(f"Google Embedding 모델 초기화 실패: {str(e)}")
            raise
        
    def get_embeddings_obj(self) -> Tuple[Embeddings, Embeddings]:
        """임베딩 객체 반환, [Sync, Async]"""
        return self.model, self.model

    def count_tokens(self, text: str) -> int:
        return TokenCounter.count_tokens_google(text)    
    
    async def create_embeddings_async(
        self, 
        texts: List[str], 
        embeddings_task_type: str = "RETRIEVAL_DOCUMENT",
        user_id: Optional[UUID] = None,
        project_type: Optional[str] = None,
        db: Optional[AsyncSession] = None
    ) -> List[List[float]]:
        """Google Vertex AI는 현재 비동기를 직접 지원하지 않아 동기 메서드를 호출"""
        return await asyncio.to_thread(self.create_embeddings, texts, embeddings_task_type, user_id, project_type, db)
    
    def create_embeddings(self, texts: List[str], embeddings_task_type: str = "RETRIEVAL_QUERY", user_id: Optional[UUID] = None, project_type: Optional[str] = None, db: Optional[AsyncSession] = None) -> List[List[float]]:
        """텍스트 임베딩 생성"""
        all_embeddings = []
        
        # Google 임베딩은 배치 처리가 필요함
        batches = self.validate_and_split_texts(texts)
        
        for batch in batches:
            try:
                # 임베딩 생성
                embeddings_batch = self._embed_batch(batch, embeddings_task_type)
                all_embeddings.extend(embeddings_batch)
                
            except Exception as e:
                logger.error(f"Google 임베딩 생성 실패: {str(e)}")
                raise
        
        return all_embeddings

    @tenacity.retry(
        stop=tenacity.stop_after_attempt(3), # 최대 3회 재시도
        wait=tenacity.wait_exponential(multiplier=1, min=4, max=10), # 지수 백오프
        retry=tenacity.retry_if_exception_type(google.api_core.exceptions.GoogleAPIError), # Google API 오류 시 재시도
        reraise=True # 마지막 시도 실패 시 예외 발생
    )
    def _embed_batch(self, batch: List[str], embeddings_task_type: str = "RETRIEVAL_QUERY") -> List[List[float]]:
        """배치 임베딩 생성 및 재시도 로직"""
        try:
            #  embeddings_task_type: [str] optional embeddings task type,
            #     one of the following
            #         RETRIEVAL_QUERY	- Text is a query
            #                           in a search/retrieval setting.
            #         RETRIEVAL_DOCUMENT - Text is a document
            #                              in a search/retrieval setting.
            #         SEMANTIC_SIMILARITY - Embeddings will be used
            #                               for Semantic Textual Similarity (STS).
            #         CLASSIFICATION - Embeddings will be used for classification.
            #         CLUSTERING - Embeddings will be used for clustering.
            #         The following are only supported on preview models:
            #         QUESTION_ANSWERING
            #         FACT_VERIFICATION
            # 배치 전체를 한 번에 요청
            #embeddings = self.model.get_embeddings(batch)
            embeddings = self.model.embed(batch, embeddings_task_type=embeddings_task_type)

            # 임베딩 값 추출
            #return [embedding.values for embedding in embeddings]
            return embeddings
        except google.api_core.exceptions.GoogleAPIError as e:
            
            # str(e)가  429 Quota 문자열을 포함하고 있다면 아래 코드 수행
            try:
                if "429 Quota" in str(e):
                    logger.error("429 Quota 오류 발생. 리전 us-central1로 변경")
                    credentials_path = settings.GOOGLE_APPLICATION_CREDENTIALS_VERTEXAI
                    credentials = service_account.Credentials.from_service_account_file(credentials_path)
                    
                    self.model = VertexAIEmbeddings(
                                            model=self.model_name,
                                            location='us-central1',
                                            credentials=credentials)
                    
                    embeddings = self.model.embed(batch, embeddings_task_type=embeddings_task_type)
                    return embeddings
            except google.api_core.exceptions.GoogleAPIError as e:
                logger.error(f"Google 임베딩 API 리전 변경 후 오류 {str(e)} | 배치 크기: {len(batch)}")
                raise
            logger.error(f"Google 임베딩 API 오류1: {str(e)} | 배치 크기: {len(batch)}")
            raise

    def validate_and_split_texts(self, texts: List[str]) -> List[List[str]]:
        """구글 모델용 토큰 분할"""
        #OpenAI 모델은 List[str]이 8191 이내면 됨. 개별 str취급안함. 
        #구글 모델은 List[str]은 20000 토큰, 개별 str당 2048 토큰 이내.
        #str은 청크단위.
        batches = []
        current_batch = []
        current_tokens = 0

        for text in texts:
            if not text or not text.strip():
                continue

            text = text.strip()
            tokens = self.count_tokens(text)

            if tokens > self.max_tokens:
                logger.warning(f"텍스트가 토큰 제한({self.max_tokens})을 초과하여 분할 처리함: {tokens} tokens")
                split_texts = self.split_text_by_tokens(text)
                for split_text in split_texts:
                    split_tokens = self.count_tokens(split_text) # 분할된 텍스트의 토큰 수를 계산
                    if current_tokens + split_tokens <= self.max_tokens:
                        current_batch.append(split_text)
                        current_tokens += split_tokens
                    else:
                        batches.append(current_batch)
                        current_batch = [split_text]
                        current_tokens = split_tokens
                continue # 분할된 텍스트 처리를 완료했으므로 다음 텍스트로 넘어감

            if current_tokens + tokens <= self.max_tokens:
                current_batch.append(text)
                current_tokens += tokens
            else:
                batches.append(current_batch)
                current_batch = [text]
                current_tokens = tokens

        if current_batch:
            batches.append(current_batch)

        return batches

class KakaoEmbeddingProvider(EmbeddingProvider):
    """카카오 임베딩 모델 제공자"""
    def __init__(self, model_name: str, max_tokens: int = 512):
        super().__init__(model_name, max_tokens)
        self.tokenizer = AutoTokenizer.from_pretrained(settings.KAKAO_EMBEDDING_MODEL_PATH)
        self.model = None  # 실제 모델은 필요할 때 로드
    
    def get_embeddings_obj(self) -> Tuple[Embeddings, Embeddings]:
        """임베딩 객체 반환, [Sync, Async]"""
        return self.model, self.model
    
    def count_tokens(self, text: str) -> int:
        """카카오 토크나이저를 사용하여 토큰 수 계산"""
        try:
            tokens = self.tokenizer.encode(text)
            return len(tokens)
        except Exception as e:
            logger.warning(f"카카오 토크나이저 토큰 카운팅 실패: {str(e)}")
            # 실패시 문자 길이로 대략적 계산
            return len(text.split()) * 2
            
    async def create_embeddings_async(
        self, 
        texts: List[str], 
        embeddings_task_type: str = "RETRIEVAL_QUERY",
        user_id: Optional[UUID] = None,
        project_type: Optional[str] = None
    ) -> List[List[float]]:
        """비동기 임베딩 생성 (동기 메서드를 비동기로 래핑)"""
        return await asyncio.to_thread(self.create_embeddings, texts, embeddings_task_type, user_id, project_type)
    
    def create_embeddings(
        self, 
        texts: List[str], 
        embeddings_task_type: str = "RETRIEVAL_QUERY",
        user_id: Optional[UUID] = None,
        project_type: Optional[str] = None
    ) -> List[List[float]]:
        """카카오 임베딩 생성"""
        try:
            if self.model is None:
                from transformers import AutoModel
                self.model = AutoModel.from_pretrained(settings.KAKAO_EMBEDDING_MODEL_PATH)
                
            batches = self.validate_and_split_texts(texts)
            logger.info(f"카카오 임베딩 생성 시작: {len(batches)} 배치")
            all_embeddings = []
            
            for batch in batches:
                # 토크나이징
                inputs = self.tokenizer(batch, padding=True, truncation=True, return_tensors="pt", max_length=self.max_tokens)
                
                # 임베딩 생성
                with torch.no_grad():
                    outputs = self.model(**inputs)
                    # [CLS] 토큰의 임베딩을 사용 (문장 전체의 의미를 대표)
                    embeddings = outputs.last_hidden_state[:, 0, :].numpy()
                    all_embeddings.extend(embeddings.tolist())
            
            return all_embeddings
            
        except Exception as e:
            logger.error(f"카카오 임베딩 생성 실패: {str(e)}")
            raise

class EmbeddingProviderFactory:
    """임베딩 제공자 팩토리"""
    
    @staticmethod
    def create_provider(provider_type: str | EmbeddingModelType, model_name: str) -> EmbeddingProvider:
        # provider_type이 문자열인 경우 EmbeddingModelType으로 변환 시도
        if isinstance(provider_type, str):
            try:
                provider_type = EmbeddingModelType(provider_type)
            except ValueError:
                raise ValueError(f"지원하지 않는 제공자 타입: {provider_type}")
            
        # 이제 provider_type은 항상 EmbeddingModelType
        if provider_type == EmbeddingModelType.OPENAI_ADA_002 or provider_type == EmbeddingModelType.OPENAI_3_LARGE:
            return OpenAIEmbeddingProvider(model_name)
        elif provider_type == EmbeddingModelType.GOOGLE_MULTI_LANG or provider_type == EmbeddingModelType.GOOGLE_EN:
            return GoogleEmbeddingProvider(model_name)
        elif provider_type == EmbeddingModelType.KAKAO_EMBEDDING:
            return KakaoEmbeddingProvider(model_name)
        elif provider_type == EmbeddingModelType.UPSTAGE:
            return UpstageEmbeddingProvider(model_name)
        elif provider_type == EmbeddingModelType.BGE_M3:
            return BGE_M3_EmbeddingProvider(model_name)
        else:
            raise ValueError(f"지원하지 않는 제공자 타입: {provider_type}")