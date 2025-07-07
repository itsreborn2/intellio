"""
증권 데이터 수집 서비스 설정 관리
"""
import os
from functools import lru_cache
from pathlib import Path
from typing import List, Optional

from pydantic import Field
from pydantic_settings import BaseSettings


# 현재 파일 기준으로 collector 디렉토리 경로 계산
CURRENT_DIR = Path(__file__).parent.parent  # collector 디렉토리
ROOT_DIR = CURRENT_DIR.parent.parent.parent  # 프로젝트 루트 디렉토리

# 환경 변수 파일 경로들 (존재하는 파일들만)
ENV_FILES = []
potential_env_files = [
    CURRENT_DIR / ".env.development",
    CURRENT_DIR / ".env.production", 
    CURRENT_DIR / ".env.local",
    CURRENT_DIR / ".env",
    ROOT_DIR / ".env.development",
    ROOT_DIR / ".env"
]

for env_file in potential_env_files:
    if env_file.exists():
        ENV_FILES.append(str(env_file))

# print(f"환경 변수 파일 검색 중...")
# print(f"collector 디렉토리: {CURRENT_DIR}")
# print(f"루트 디렉토리: {ROOT_DIR}")
# print(f"발견된 환경 변수 파일: {ENV_FILES}")


class Settings(BaseSettings):
    """애플리케이션 설정"""
    
    # 기본 설정
    DEBUG: bool = Field(default=False, env="DEBUG")
    ENV: str = Field(default="production", env="ENV")
    SERVICE_NAME: str = "stock-data-collector"
    ENABLE_MEMORY_TRACKING: bool = Field(default=True, env="ENABLE_MEMORY_TRACKING")
    
    # API 설정
    API_V1_STR: str = Field(default="/api/v1", env="API_V1_STR")
    PROJECT_NAME: str = Field(default="Intellio", env="PROJECT_NAME")
    FASTAPI_URL: str = Field(default="http://localhost:8000", env="FASTAPI_URL")
    
    # 서비스 URL 설정
    INTELLIO_URL: str = Field(default="http://localhost:3000", env="INTELLIO_URL")
    DOCEASY_URL: str = Field(default="http://localhost:3010", env="DOCEASY_URL")
    STOCKEASY_URL: str = Field(default="http://localhost:3020", env="STOCKEASY_URL")
    
    # 데이터베이스 상세 설정
    POSTGRES_USER: str = Field(default="intellio_user_dev", env="POSTGRES_USER")
    POSTGRES_PASSWORD: str = Field(default="!it*Korea^2025", env="POSTGRES_PASSWORD")
    POSTGRES_DB: str = Field(default="intellio_dev", env="POSTGRES_DB")
    POSTGRES_HOST: str = Field(default="postgres", env="POSTGRES_HOST")
    POSTGRES_PORT: int = Field(default=5432, env="POSTGRES_PORT")
    
    # PgBouncer 설정
    PGBOUNCER_HOST: str = Field(default="pgbouncer", env="PGBOUNCER_HOST")
    PGBOUNCER_PORT: int = Field(default=6432, env="PGBOUNCER_PORT")
    
    # TimescaleDB 설정 (새로 추가)
    TIMESCALE_HOST: str = Field(default="pgbouncer-timescale", env="TIMESCALE_HOST")
    TIMESCALE_PORT: int = Field(default=6432, env="TIMESCALE_PORT")
    TIMESCALE_USER: str = Field(..., env="TIMESCALE_USER")
    TIMESCALE_PASSWORD: str = Field(..., env="TIMESCALE_PASSWORD")
    TIMESCALE_DB: str = Field(default="stockeasy_collector", env="TIMESCALE_DB")
    
    @property
    def TIMESCALE_DATABASE_URL(self) -> str:
        """TimescaleDB 동기 연결 URL"""
        return f"postgresql+psycopg2://{self.TIMESCALE_USER}:{self.TIMESCALE_PASSWORD}@{self.TIMESCALE_HOST}:{self.TIMESCALE_PORT}/{self.TIMESCALE_DB}"
    
    @property
    def TIMESCALE_ASYNC_DATABASE_URL(self) -> str:
        """TimescaleDB 비동기 연결 URL"""
        return f"postgresql+asyncpg://{self.TIMESCALE_USER}:{self.TIMESCALE_PASSWORD}@{self.TIMESCALE_HOST}:{self.TIMESCALE_PORT}/{self.TIMESCALE_DB}"
    
    # 데이터베이스 설정
    DATABASE_URL: str = Field(default="postgresql://intellio:intellio123@postgres:5432/intellio", env="DATABASE_URL")
    
    # Redis 상세 설정
    REDIS_HOST: str = Field(default="redis", env="REDIS_HOST")
    REDIS_PORT: int = Field(default=6379, env="REDIS_PORT")
    REDIS_URL: str = Field(default="redis://redis:6379/0", env="REDIS_URL")
    REDIS_PASSWORD: Optional[str] = Field(default=None, env="REDIS_PASSWORD")
    
    # API 키 설정 (테스트용 기본값)
    KIWOOM_APP_KEY: str = Field(default="test_app_key", env="KIWOOM_APP_KEY")
    KIWOOM_SECRET_KEY: str = Field(default="test_secret_key", env="KIWOOM_SECRET_KEY")
    
    # Telegram 설정
    TELEGRAM_SESSION_NAME: str = Field(default="telegram_collector", env="TELEGRAM_SESSION_NAME")
    TELEGRAM_API_ID: str = Field(default="22508254", env="TELEGRAM_API_ID")
    TELEGRAM_API_HASH: str = Field(default="cdd455d868a2405d47eb3d98733a28ee", env="TELEGRAM_API_HASH")
    
    # 타임존 설정
    TZ: str = Field(default="Asia/Seoul", env="TZ")
    
    # API 호출 제한 설정
    MAX_API_CALLS_PER_SECOND: int = Field(default=10, env="MAX_API_CALLS_PER_SECOND")
    MAX_API_CALLS_PER_MINUTE: int = Field(default=600, env="MAX_API_CALLS_PER_MINUTE")
    MAX_API_CALLS_PER_HOUR: int = Field(default=10000, env="MAX_API_CALLS_PER_HOUR")
    MAX_CONCURRENT_REQUESTS: int = Field(default=5, env="MAX_CONCURRENT_REQUESTS")
    
    # 데이터 수집 설정
    AUTO_START_REALTIME: bool = Field(default=False, env="AUTO_START_REALTIME")
    REALTIME_UPDATE_INTERVAL: int = Field(default=1, env="REALTIME_UPDATE_INTERVAL")  # 초
    BATCH_UPDATE_INTERVAL: int = Field(default=300, env="BATCH_UPDATE_INTERVAL")  # 초 (5분)
    
    # 캐시 설정
    CACHE_TTL_REALTIME: int = Field(default=60, env="CACHE_TTL_REALTIME")  # 실시간 데이터 TTL (초)
    CACHE_TTL_DAILY: int = Field(default=3600, env="CACHE_TTL_DAILY")  # 일간 데이터 TTL (초)
    CACHE_TTL_ETF: int = Field(default=86400, env="CACHE_TTL_ETF")  # ETF 구성종목 TTL (초)
    
    # CORS 설정
    ALLOWED_ORIGINS: List[str] = Field(
        default=[
            "http://localhost:3000",
            "http://localhost:3010",
            "http://localhost:3020",
            "http://localhost:8000",
            "http://localhost:8001",
            "https://intellio.co.kr",
            "https://doceasy.intellio.co.kr",
            "https://stockeasy.intellio.kr"
        ],
        env="ALLOWED_ORIGINS"
    )
    BACKEND_CORS_ORIGINS: List[str] = Field(
        default=["http://localhost:3000", "http://localhost:3010", "http://localhost:3020"],
        env="BACKEND_CORS_ORIGINS"
    )
    
    # 로깅 설정
    LOG_LEVEL: str = Field(default="INFO", env="LOG_LEVEL")
    LOG_FORMAT: str = Field(
        default="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        env="LOG_FORMAT"
    )
    
    # 시장 시간 설정
    MARKET_OPEN_TIME: str = Field(default="09:00", env="MARKET_OPEN_TIME")
    MARKET_CLOSE_TIME: str = Field(default="15:30", env="MARKET_CLOSE_TIME")
    
    # 데이터 저장 설정
    SAVE_TO_DB: bool = Field(default=True, env="SAVE_TO_DB")
    SAVE_HISTORICAL_DATA: bool = Field(default=True, env="SAVE_HISTORICAL_DATA")
    
    # ETF 크롤링 설정
    ETF_CRAWL_ENABLED: bool = Field(default=True, env="ETF_CRAWL_ENABLED")
    ETF_CRAWL_INTERVAL: int = Field(default=86400, env="ETF_CRAWL_INTERVAL")  # 하루
    NAVER_ETF_BASE_URL: str = Field(
        default="https://finance.naver.com/api/sise/etfItemList.nhn",
        env="NAVER_ETF_BASE_URL"
    )
    
    # 모니터링 설정
    PROMETHEUS_ENABLED: bool = Field(default=True, env="PROMETHEUS_ENABLED")
    PROMETHEUS_PORT: int = Field(default=9090, env="PROMETHEUS_PORT")
    
    # WebSocket 설정
    WEBSOCKET_ENABLED: bool = Field(default=True, env="WEBSOCKET_ENABLED")
    WEBSOCKET_PORT: int = Field(default=8002, env="WEBSOCKET_PORT")
    
    # gRPC 설정
    GRPC_ENABLED: bool = Field(default=False, env="GRPC_ENABLED")
    GRPC_PORT: int = Field(default=8001, env="GRPC_PORT")
    
    # 알림 설정
    SLACK_WEBHOOK_URL: Optional[str] = Field(default=None, env="SLACK_WEBHOOK_URL")
    EMAIL_ALERTS_ENABLED: bool = Field(default=False, env="EMAIL_ALERTS_ENABLED")
    
    # 성능 설정
    REQUEST_TIMEOUT: int = Field(default=30, env="REQUEST_TIMEOUT")
    
    # 데이터 품질 설정
    DATA_VALIDATION_ENABLED: bool = Field(default=True, env="DATA_VALIDATION_ENABLED")
    OUTLIER_DETECTION_ENABLED: bool = Field(default=True, env="OUTLIER_DETECTION_ENABLED")

    class Config:
        case_sensitive = True
        env_file_encoding = 'utf-8'
        env_file = ENV_FILES
        extra = "ignore"  # 추가 환경변수 무시


@lru_cache()
def get_settings() -> Settings:
    """설정 인스턴스 반환 (캐시됨)"""
    s = Settings() 
    print(f"키움 API 키 로드됨: {s.KIWOOM_APP_KEY}")
    print(f"환경 변수 ENV: {s.ENV}")
    print(f"디버그 모드: {s.DEBUG}")
    print(f"TimescaleDB 설정: {s.TIMESCALE_USER}")
    print(f"TIMESCALE_PASSWORD: {s.TIMESCALE_PASSWORD}")
    print(f"TIMESCALE_DATABASE_URL: {s.TIMESCALE_DATABASE_URL}")
    print(f"TIMESCALE_ASYNC_DATABASE_URL: {s.TIMESCALE_ASYNC_DATABASE_URL}")
    return s 