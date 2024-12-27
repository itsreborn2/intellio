from typing import List
from pydantic_settings import BaseSettings
import os

class Settings(BaseSettings):
    # API Settings
    PROJECT_NAME: str = "Intellio API"
    API_V1_STR: str = "/api/v1"
    
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
    
    # Redis - from .env
    REDIS_URL: str
    
    # PGAdmin - from .env
    PGADMIN_EMAIL: str
    PGADMIN_PASSWORD: str
    
    # Google Cloud Storage - from .env
    GOOGLE_CLOUD_PROJECT: str = "intellio-document"
    GOOGLE_APPLICATION_CREDENTIALS: str = "app/credentials/intellio-document-5e9dd6681039.json"
    GOOGLE_DOCUMENT_AI_PROCESSOR_ID: str = "your-processor-id"  # Document AI 프로세서 ID
    GOOGLE_CLOUD_LOCATION: str
    GOOGLE_CLOUD_STORAGE_BUCKET: str
    GCS_BUCKET_NAME: str = "intellio-documents"
    
    # File Upload Settings
    ALLOWED_EXTENSIONS: set = {
        'txt', 'pdf', 'doc', 'docx', 'hwp', 'hwpx',
        'xls', 'xlsx', 'jpg', 'jpeg', 'png', 'tiff'
    }
    MAX_CONTENT_LENGTH: int = 16 * 1024 * 1024  # 16MB
    
    @property
    def GOOGLE_CLOUD_CREDENTIALS(self) -> str:
        with open(self.GOOGLE_APPLICATION_CREDENTIALS) as f:
            return f.read()
    
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
        env_file = ".env"
        env_file_encoding = 'utf-8'
        case_sensitive = True

settings = Settings()
