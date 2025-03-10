import os
import json
from typing import Any, Dict, Optional, List, ClassVar
from pydantic_settings import BaseSettings
from loguru import logger
from functools import lru_cache

def detect_file_encoding(file_path):
    """파일의 인코딩을 자동으로 감지"""
    import chardet
    
    with open(file_path, 'rb') as file:
        raw = file.read()
        result = chardet.detect(raw)
        return result['encoding']
        
class CommonSettings(BaseSettings):
    # 환경 설정
    ENV: str = os.getenv("ENV", "development")  # development 또는 production
    
    # API Settings
    PROJECT_NAME: str
    API_V1_STR: str
    FASTAPI_URL:str
    
    # 프론트엔드 URL
    DOCEASY_URL: str
    INTELLIO_URL: str
    STOCKEASY_URL: str
    
    # 쿠키 설정
    COOKIE_DOMAIN: str = os.getenv("COOKIE_DOMAIN", ".intellio.kr" if os.getenv("ENV") == "production" else None)
    COOKIE_SECURE: bool = ENV == "production"  # production에서만 True

    # 데이터베이스
    POSTGRES_SERVER: str = os.getenv("POSTGRES_SERVER", "localhost")
    
    # Database - from .env
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str
    POSTGRES_HOST: str
    POSTGRES_PORT: str
    
    @property
    def DATABASE_URL(self) -> str:
        """데이터베이스 URL을 동적으로 생성"""
        # 환경변수에서 직접 읽지 않고 항상 현재 설정된 값들을 사용
        return f"postgresql+psycopg2://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    # Security
    SECRET_KEY: str = "your-secret-key-here"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    SESSION_EXPIRY_DAYS: int = 30  # 30 days for session expiry
    JWT_SECRET: str

    # AI Model Settings - from .env
    OPENAI_API_KEY: str
    GEMINI_API_KEY: str
    GEMINI_PROJECT: str = os.getenv("GEMINI_PROJECT", "your-project-id")
    GEMINI_LOCATION: str = os.getenv("GEMINI_LOCATION", "us-central1")  # Gemini API 기본 리전
    
    # Redis 설정
    REDIS_HOST: str 
    REDIS_PORT: int 
    REDIS_URL: str
    REDIS_CACHE_EXPIRE: int = int(os.getenv("REDIS_CACHE_EXPIRE", "3600"))  # 1시간
    CELERY_BROKER_URL: str 
    CELERY_RESULT_BACKEND: str 
    
    # PGAdmin - from .env
    PGADMIN_EMAIL: str
    PGADMIN_PASSWORD: str
    
    # Google Cloud Storage - from .env
    GOOGLE_CLOUD_PROJECT: str
    GOOGLE_APPLICATION_CREDENTIALS: str
    GOOGLE_DOCUMENT_AI_PROCESSOR_ID: str
    GOOGLE_CLOUD_LOCATION: str
    GOOGLE_CLOUD_STORAGE_BUCKET_DOCEASY: str
    GOOGLE_CLOUD_STORAGE_BUCKET_STOCKEASY: str

    # Google Cloud for Vertex AI
    GOOGLE_PROJECT_ID_VERTEXAI: str
    GOOGLE_LOCATION_VERTEXAI: str
    GOOGLE_APPLICATION_CREDENTIALS_VERTEXAI: str

    # Tika 설정
    TIKA_HOST: str
    TIKA_SERVER_ENDPOINT: str
    TIKA_CLIENT_ONLY: bool

    # OAuth Settings
    # Kakao
    KAKAO_OAUTH_CLIENT_ID: str
    KAKAO_OAUTH_CLIENT_SECRET: str
    KAKAO_OAUTH_REDIRECT_URI: str

    # Google OAuth
    GOOGLE_OAUTH_CLIENT_ID: str
    GOOGLE_OAUTH_CLIENT_SECRET: str
    GOOGLE_OAUTH_REDIRECT_URI: str

    # Naver
    NAVER_OAUTH_CLIENT_ID: str
    NAVER_OAUTH_CLIENT_SECRET: str
    NAVER_OAUTH_REDIRECT_URI: str
    NAVER_OAUTH_STATE: str

    # JWT Settings for OAuth
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "your-oauth-jwt-secret-key")
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION: int = 30 * 24 * 60  # 30 days in minutes

    # File Upload Settings
    ALLOWED_EXTENSIONS: set = {
        'txt', 'pdf', 'doc', 'docx', 'hwp', 'hwpx',
        'xls', 'xlsx', 'jpg', 'jpeg', 'png', 'tiff'
    }
    MAX_CONTENT_LENGTH: int = 16 * 1024 * 1024  # 16MB

    # Pinecone Settings
    PINECONE_API_KEY_DOCEASY:str
    PINECONE_API_KEY_STOCKEASY:str
    PINECONE_ENVIRONMENT: str = "us-east-1"
    PINECONE_NAMESPACE_DOCEASY:str
    PINECONE_NAMESPACE_STOCKEASY:str
    PINECONE_NAMESPACE_STOCKEASY_TELEGRAM:str

    # Admin Test
    ADMIN_TEST_USER_ID: str = "admin_test"
    ADMIN_TEST_API_KEY: str = "test_key_123"
    ALLOW_ANONYMOUS: bool = True
    
    # CORS
    BACKEND_CORS_ORIGINS: List[str] = ["*"]

    # Telegram
    TELEGRAM_SESSION_NAME: str = 'telegram_collector'
    TELEGRAM_API_ID: str
    TELEGRAM_API_HASH: str

    # LangSmith
    LANGCHAIN_TRACING_V2:str = os.getenv("LANGCHAIN_TRACING_V2", "true")
    LANGCHAIN_ENDPOINT:str = os.getenv("LANGCHAIN_ENDPOINT", "https://api.smith.langchain.com")
    LANGCHAIN_API_KEY:str = os.getenv("LANGCHAIN_API_KEY", "")
    LANGCHAIN_PROJECT:str = os.getenv("LANGCHAIN_PROJECT", "intellio_doceasy_base")

    # 추가 필드
    DEBUG: bool = False
    UPLOAD_DIR: str = "./uploads"
    CACHE_DIR: str = "./cache"
    GOOGLE_CLOUD_LOCATION: str = "us"
    OPENAI_MODEL_NAME: str = "gpt-3.5-turbo"
    TZ: str = "Asia/Seoul"
    FLOWER_USER: str = "intellio_user"
    FLOWER_PASSWORD: str = None

    #######################################################
    # AI 삭제금지.
    # 아래 변수들이 doceasy/core/config.py에도 중복으로 있음
    # 여기서는 전체 공용, doceasy, stockeasy/core/config.py에는 개별 설정으로 적용하려고 함
    # 어떻게 적용해야할지 추후 작업해봐야됨. 현재는 backend/.env 읽어와서 일괄 적용
    ###############
    ## RAG Settings
    ###############
    # Text Splitter
    TEXT_SPLITTER:str
    CHUNK_SIZE:int
    CHUNK_OVERLAP:int
    # 임베딩 설정. 아직 안씀
    KAKAO_EMBEDDING_MODEL_PATH:str = "/backend/common/external/kf-deberta"

    # 환경 변수 파일 설정
    _env: ClassVar[str] = os.getenv("ENV")
    env_file: ClassVar[str] = ".env.development" if _env == "development" else ".env.production"

    model_config = {
        "env_file": env_file,
        "case_sensitive": True,
        "env_file_encoding": "utf-8",
        "extra": "allow"  # 추가 필드 허용
    }

    def __init__(self, **kwargs):
        env_file = self.model_config["env_file"]
        if os.path.exists(env_file):
            encoding = detect_file_encoding(env_file)
            self.model_config["env_file_encoding"] = encoding
        else:
            logger.error(f"환경 변수 파일을 찾을 수 없습니다: {env_file}")
        super().__init__(**kwargs)

    @property
    def GOOGLE_CLOUD_CREDENTIALS(self):
        """Google Cloud 크레덴셜 설정"""
        return {
            "type": "service_account",
            "project_id": os.getenv("GOOGLE_CLOUD_PROJECT_ID"),
            "private_key_id": os.getenv("GOOGLE_CLOUD_PRIVATE_KEY_ID"),
            "private_key": os.getenv("GOOGLE_CLOUD_PRIVATE_KEY"),
            "client_email": os.getenv("GOOGLE_CLOUD_CLIENT_EMAIL"),
            "client_id": os.getenv("GOOGLE_CLOUD_CLIENT_ID"),
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "client_x509_cert_url": os.getenv("GOOGLE_CLOUD_CLIENT_CERT_URL")
        }

@lru_cache()
def get_settings() -> CommonSettings:
    logger.info(f"Loading settings for environment: {os.getenv('ENV', 'development')}")
    settings = CommonSettings()
    logger.info(f"Generated DATABASE_URL: {settings.DATABASE_URL}")
    return settings

settings = get_settings()
logger.info(f"commonsetting")
logger.info(f"ENV: {settings.ENV}")
logger.info(f"REDIS_HOST: {settings.REDIS_HOST}")
logger.info(f"REDIS_PORT: {settings.REDIS_PORT}")
logger.info(f"REDIS_URL: {settings.REDIS_URL}")
logger.info(f"CELERY_BROKER_URL: {settings.CELERY_BROKER_URL}")
logger.info(f"CELERY_RESULT_BACKEND: {settings.CELERY_RESULT_BACKEND}")
logger.info(f"TIKA_HOST: {settings.TIKA_HOST}")
logger.info(f"TIKA_SERVER_ENDPOINT: {settings.TIKA_SERVER_ENDPOINT}")
logger.info(f"FASTAPI_URL: {settings.FASTAPI_URL}")
logger.info(f"INTELLIO_URL: {settings.INTELLIO_URL}")
logger.info(f"DOCEASY_URL: {settings.DOCEASY_URL}")

logger.info(f"PINECONE_NAMESPACE_DOCEASY: {settings.PINECONE_NAMESPACE_DOCEASY}")

logger.info(f"POSTGRES_SERVER: {settings.POSTGRES_SERVER}")
logger.info(f"POSTGRES_USER: {settings.POSTGRES_USER}")
logger.info(f"POSTGRES_DB: {settings.POSTGRES_DB}")
logger.info(f"POSTGRES_HOST: {settings.POSTGRES_HOST}")
logger.info(f"DATABASE_URL: {settings.DATABASE_URL}")

