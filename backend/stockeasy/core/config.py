from typing import ClassVar
from pydantic import Extra
from common.core.config import CommonSettings
import os
from functools import lru_cache
import logging

logger = logging.getLogger(__name__)

def detect_file_encoding(file_path):
    """파일의 인코딩을 자동으로 감지"""
    import chardet
    
    with open(file_path, 'rb') as file:
        raw = file.read()
        result = chardet.detect(raw)
        return result['encoding']
    
class StockeasySettings(CommonSettings):
    # 기본 설정
    PROJECT_NAME: str = "StockEasy Telegram Service"
    VERSION: str = "0.1.0"
    
    # Telegram 설정
    TELEGRAM_API_ID: str
    TELEGRAM_API_HASH: str
    #TELEGRAM_PHONE: str
    #TELEGRAM_CHANNEL_IDS: str = "channel1"  # 기본값 설정
    TELEGRAM_SESSION_NAME: str

    
    # Celery 설정
    @property
    def CELERY_BROKER_URL(self) -> str:
        return self.REDIS_URL + "/0"
    
    @property
    def CELERY_RESULT_BACKEND(self) -> str:
        return self.REDIS_URL + "/0"

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
            #logger.info(f"Load Complete env_file : {env_file}, [ProcessID: {os.getpid()}]")
        else:
            logger.error(f"환경 변수 파일을 찾을 수 없습니다: {env_file}")
        super().__init__(**kwargs)

      

# 설정 인스턴스 생성

@lru_cache()
def get_settings() -> StockeasySettings:
    """싱글톤 패턴으로 Settings 인스턴스를 반환"""
    return StockeasySettings()

stockeasy_settings = get_settings()
