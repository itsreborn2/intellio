from pydantic import Extra
from common.core.config import CommonSettings
import os

class StockeasySettings(CommonSettings):
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

stockeasy_settings = StockeasySettings()
