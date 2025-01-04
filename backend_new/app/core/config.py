from typing import List
from pydantic_settings import BaseSettings
import os
import logging

logger = logging.getLogger(__name__)

class Settings(BaseSettings):
    # API Settings
    PROJECT_NAME: str = "Intellio API"
    API_V1_STR: str = "/api/v1"
    FASTAPI_URL:str = "http://localhost:8000"
    
    # 프론트엔드 URL
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:3000")
    
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
    
    
    # JWT Settings
    JWT_SECRET: str
    
    # OpenAI Settings - from .env
    OPENAI_API_KEY: str
    OPENAI_SYSTEM_PROMPT: str | None = None
    OPENAI_DOCUMENT_PROMPT: str | None = None
    OPENAI_SUMMARY_PROMPT: str | None = None
    
    # Google AI (Gemini) Settings
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    
    # Redis - from .env
    REDIS_URL: str
    
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
    KAKAO_CLIENT_ID: str = os.getenv("KAKAO_CLIENT_ID", "")
    KAKAO_CLIENT_SECRET: str = os.getenv("KAKAO_CLIENT_SECRET", "")
    KAKAO_REDIRECT_URI: str = os.getenv("KAKAO_REDIRECT_URI", f"{FRONTEND_URL}/api/v1/auth/kakao/callback")

    # Google OAuth
    GOOGLE_OAUTH_CLIENT_ID: str = os.getenv("GOOGLE_OAUTH_CLIENT_ID", "")
    GOOGLE_OAUTH_CLIENT_SECRET: str = os.getenv("GOOGLE_OAUTH_CLIENT_SECRET", "")
    GOOGLE_OAUTH_REDIRECT_URI: str = os.getenv("GOOGLE_OAUTH_REDIRECT_URI", f"{FRONTEND_URL}/api/v1/auth/google/callback")

    # Naver
    NAVER_CLIENT_ID: str = os.getenv("NAVER_CLIENT_ID", "")
    NAVER_CLIENT_SECRET: str = os.getenv("NAVER_CLIENT_SECRET", "")
    NAVER_REDIRECT_URI: str = os.getenv("NAVER_REDIRECT_URI")
    NAVER_STATE: str = os.getenv("NAVER_STATE", "RANDOM_STATE")

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

    class Config:
        env_file = ".env" #예전위치.
        #env_file = "../../.env"  # 프로젝트 루트의 .env 파일 참조
        env_file_encoding = 'utf-8'
        case_sensitive = True

settings = Settings()
