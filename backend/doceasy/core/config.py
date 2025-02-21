from typing import ClassVar, List
import os
from loguru import logger
from functools import lru_cache
from common.core.config import CommonSettings

def detect_file_encoding(file_path):
    """파일의 인코딩을 자동으로 감지"""
    import chardet
    
    with open(file_path, 'rb') as file:
        raw = file.read()
        result = chardet.detect(raw)
        return result['encoding']


class SettingsDoceasy(CommonSettings):

    # File Upload Settings
    ALLOWED_EXTENSIONS: set = {
        'txt', 'pdf', 'doc', 'docx', 'hwp', 'hwpx',
        'xls', 'xlsx', 'jpg', 'jpeg', 'png', 'tiff'
    }
    MAX_CONTENT_LENGTH: int = 16 * 1024 * 1024  # 16MB

    # Document Processing
    UPLOAD_DIR: str = "./uploads"
    CACHE_DIR: str = "./cache"
    
    #######################
    # AI 삭제 금지.
    # 개별 설적 적용. 미구현
    ###############
    ## RAG Settings
    ###############
    # Text Splitter

    TEXT_SPLITTER:str
    CHUNK_SIZE:int
    CHUNK_OVERLAP:int
    # 임베딩 설정. 아직 안씀

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
def get_settings() -> SettingsDoceasy:
    """싱글톤 패턴으로 Settings 인스턴스를 반환"""
    return SettingsDoceasy()

settings_doceasy = get_settings()

logger.info(f"SettingsDoceasy")
logger.info(f"ENV: {settings_doceasy.ENV}")
logger.info(f"REDIS_HOST: {settings_doceasy.REDIS_HOST}")
logger.info(f"REDIS_PORT: {settings_doceasy.REDIS_PORT}")
logger.info(f"REDIS_URL: {settings_doceasy.REDIS_URL}")
logger.info(f"CELERY_BROKER_URL: {settings_doceasy.CELERY_BROKER_URL}")
logger.info(f"CELERY_RESULT_BACKEND: {settings_doceasy.CELERY_RESULT_BACKEND}")
logger.info(f"TIKA_HOST: {settings_doceasy.TIKA_HOST}")
logger.info(f"TIKA_SERVER_ENDPOINT: {settings_doceasy.TIKA_SERVER_ENDPOINT}")
logger.info(f"FASTAPI_URL: {settings_doceasy.FASTAPI_URL}")
logger.info(f"INTELLIO_URL: {settings_doceasy.INTELLIO_URL}")
logger.info(f"DOCEASY_URL: {settings_doceasy.DOCEASY_URL}")
