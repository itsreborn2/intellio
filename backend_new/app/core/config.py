from typing import List
from pydantic_settings import BaseSettings
import os
from loguru import logger
from functools import lru_cache


def detect_file_encoding(file_path):
    """파일의 인코딩을 자동으로 감지"""
    import chardet
    
    with open(file_path, 'rb') as file:
        raw = file.read()
        result = chardet.detect(raw)
        return result['encoding']

class Settings(BaseSettings):
    # 환경 설정
    ENV: str = os.getenv("ENV", "development")  # development 또는 production

    # API Settings
    PROJECT_NAME: str = "Intellio API"
    API_V1_STR: str = "/api/v1"
    FASTAPI_URL:str = "http://localhost:8000"
    
    # 프론트엔드 URL
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:3000")
    
    # 쿠키 설정
    COOKIE_DOMAIN: str = os.getenv("COOKIE_DOMAIN", "localhost")
    COOKIE_SECURE: bool = ENV == "production"  # production에서만 True

    # 데이터베이스
    POSTGRES_SERVER: str = os.getenv("POSTGRES_SERVER", "localhost")
    
    # Database - from .env
    DATABASE_URL: str
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str
    POSTGRES_HOST: str
    POSTGRES_PORT: str
    
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
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_URL: str = "redis://localhost:6379"
    REDIS_CACHE_EXPIRE: int = 3600  # 1시간
    
    # PGAdmin - from .env
    PGADMIN_EMAIL: str
    PGADMIN_PASSWORD: str
    
    # Google Cloud Storage - from .env
    GOOGLE_CLOUD_PROJECT: str = os.getenv("GOOGLE_CLOUD_PROJECT", "intellio-document")
    GOOGLE_APPLICATION_CREDENTIALS: str = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "")
    GOOGLE_DOCUMENT_AI_PROCESSOR_ID: str = os.getenv("GOOGLE_DOCUMENT_AI_PROCESSOR_ID", "")
    GOOGLE_CLOUD_LOCATION: str = os.getenv("GOOGLE_CLOUD_LOCATION", "")
    GOOGLE_CLOUD_STORAGE_BUCKET: str = os.getenv("GOOGLE_CLOUD_STORAGE_BUCKET", "")
    GCS_BUCKET_NAME: str = os.getenv("GCS_BUCKET_NAME", "")

    # Google Cloud for Vertex AI
    GOOGLE_PROJECT_ID_VERTEXAI: str = os.getenv("GOOGLE_PROJECT_ID_VERTEXAI", "")
    GOOGLE_LOCATION_VERTEXAI: str = os.getenv("GOOGLE_LOCATION_VERTEXAI", "")
    GOOGLE_APPLICATION_CREDENTIALS_VERTEXAI: str = os.getenv("GOOGLE_APPLICATION_CREDENTIALS_VERTEXAI", "")

    def get_google_cloud_credentials(self) -> str:
        """Google Cloud 인증 정보를 파일에서 읽어옴"""
        try:
            with open(self.GOOGLE_APPLICATION_CREDENTIALS) as f:
                return f.read()
        except Exception as e:
            logger.error(f"Failed to read Google Cloud credentials: {str(e)}")
            return ""
    
    # OAuth Settings
    # Kakao
    KAKAO_OAUTH_CLIENT_ID: str = os.getenv("KAKAO_OAUTH_CLIENT_ID", "")
    KAKAO_OAUTH_CLIENT_SECRET: str = os.getenv("KAKAO_OAUTH_CLIENT_SECRET", "")
    KAKAO_OAUTH_REDIRECT_URI: str = os.getenv("KAKAO_OAUTH_REDIRECT_URI", f"{FRONTEND_URL}/api/v1/auth/kakao/callback")

    # Google OAuth
    GOOGLE_OAUTH_CLIENT_ID: str = os.getenv("GOOGLE_OAUTH_CLIENT_ID", "")
    GOOGLE_OAUTH_CLIENT_SECRET: str = os.getenv("GOOGLE_OAUTH_CLIENT_SECRET", "")
    GOOGLE_OAUTH_REDIRECT_URI: str = os.getenv("GOOGLE_OAUTH_REDIRECT_URI", f"{FRONTEND_URL}/api/v1/auth/google/callback")

    # Naver
    NAVER_OAUTH_CLIENT_ID: str = os.getenv("NAVER_OAUTH_CLIENT_ID", "")
    NAVER_OAUTH_CLIENT_SECRET: str = os.getenv("NAVER_OAUTH_CLIENT_SECRET", "")
    NAVER_OAUTH_REDIRECT_URI: str = os.getenv("NAVER_OAUTH_REDIRECT_URI", f"{FRONTEND_URL}/api/v1/auth/naver/callback")
    NAVER_OAUTH_STATE: str = os.getenv("NAVER_OAUTH_STATE", "RANDOM_STATE")

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

    # Google Cloud Settings
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

    # Pinecone Settings
    PINECONE_API_KEY: str
    PINECONE_ENVIRONMENT: str = "us-east-1"
    PINECONE_INDEX_NAME: str = "intellio-embeddings"
    
    # Admin Test
    ADMIN_TEST_USER_ID: str = "admin_test"
    ADMIN_TEST_API_KEY: str = "test_key_123"
    ALLOW_ANONYMOUS: bool = True
    
    # Document Processing
    UPLOAD_DIR: str = "./uploads"
    CACHE_DIR: str = "./cache"
    
    # CORS
    BACKEND_CORS_ORIGINS: List[str] = ["*"]

    ###############
    ## RAG Settings
    ###############
    # Text Splitter

    TEXT_SPLITTER:str = os.getenv("TEXT_SPLITTER", "recursive")
    CHUNK_SIZE:int = int(os.getenv("CHUNK_SIZE", "1000"))
    CHUNK_OVERLAP:int = int(os.getenv("CHUNK_OVERLAP", "200"))

    # LangSmith
    LANGCHAIN_TRACING_V2:str = os.getenv("LANGCHAIN_TRACING_V2", "true")
    LANGCHAIN_ENDPOINT:str = os.getenv("LANGCHAIN_ENDPOINT", "https://api.smith.langchain.com")
    LANGCHAIN_API_KEY:str = os.getenv("LANGCHAIN_API_KEY", "")
    LANGCHAIN_PROJECT:str = os.getenv("LANGCHAIN_PROJECT", "intellio_doceasy_base")

    model_config = {
        "env_file": ".env",
        "case_sensitive": True,
        "env_file_encoding": "utf-8"
    }

    def __init__(self, **kwargs):
        env_file = self.model_config.get("env_file", ".env")
        if os.path.exists(env_file):
            encoding = detect_file_encoding(env_file)
            self.model_config["env_file_encoding"] = encoding
            #logger.info(f"Load Complete env_file : {env_file}, [ProcessID: {os.getpid()}]")
        else:
            logger.error(f"환경 변수 파일을 찾을 수 없습니다: {env_file}")
        super().__init__(**kwargs)

@lru_cache()
def get_settings() -> Settings:
    """싱글톤 패턴으로 Settings 인스턴스를 반환"""
    return Settings()

settings = get_settings()

