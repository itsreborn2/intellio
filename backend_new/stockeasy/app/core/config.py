from pydantic_settings import BaseSettings
from pydantic import Extra
import os

class Settings(BaseSettings):
    # 기본 설정
    PROJECT_NAME: str = "StockEasy Telegram Service"
    VERSION: str = "0.1.0"
    
    # Telegram 설정
    TELEGRAM_API_ID: str
    TELEGRAM_API_HASH: str
    TELEGRAM_PHONE: str
    TELEGRAM_CHANNEL_IDS: str = "channel1"  # 기본값 설정
    TELEGRAM_SESSION_NAME: str = "stockeasy_telegram_session"  # 텔레그램 세션 파일 이름

    @property
    def telegram_channel_list(self) -> list[str]:
        return self.TELEGRAM_CHANNEL_IDS.split(',') if self.TELEGRAM_CHANNEL_IDS else []
    
    # Pinecone 설정
    PINECONE_API_KEY: str
    PINECONE_ENVIRONMENT: str
    PINECONE_INDEX_NAME: str = "telegram"

    # Redis 설정
    REDIS_URL: str = "redis://localhost:6379"

    # 데이터베이스 설정
    POSTGRES_USER: str = "intellio_user"
    POSTGRES_PASSWORD: str = "intellio123"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: str = "5433"  # 메인 프로젝트와 동일한 포트 사용
    POSTGRES_DB: str = "intellio"  # 메인 프로젝트와 동일한 DB 사용

    # GCS(Google Cloud Storage) 설정
    GCS_BUCKET_NAME: str
    GCS_CREDENTIALS_PATH: str = "credentials/gcs-service-account.json"
    GCS_PROJECT_ID: str
    GCS_TELEGRAM_FOLDER: str = "telegram"  # GCS 내의 텔레그램 파일 저장 경로

    # Google Vertex AI 설정
    GOOGLE_PROJECT_ID_VERTEXAI: str  # Vertex AI용 프로젝트 ID
    GOOGLE_LOCATION_VERTEXAI: str = "asia-northeast3"  # Vertex AI 리전 (도쿄)
    GOOGLE_APPLICATION_CREDENTIALS_VERTEXAI: str  # Vertex AI 인증 파일 경로

    @property
    def SQLALCHEMY_DATABASE_URI(self) -> str:
        """PostgreSQL 데이터베이스 연결 URI
        
        Returns:
            str: 데이터베이스 연결 문자열 (예: postgresql+psycopg2://user:pass@localhost:5433/intellio)
        """
        return f"postgresql+psycopg2://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    # Celery 설정
    @property
    def CELERY_BROKER_URL(self) -> str:
        return self.REDIS_URL + "/0"
    
    @property
    def CELERY_RESULT_BACKEND(self) -> str:
        return self.REDIS_URL + "/0"

    class Config:
        env_file = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.env"))
        case_sensitive = True
        extra = Extra.ignore  # 추가 환경변수 무시

settings = Settings()
