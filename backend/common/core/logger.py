"""로깅 설정 모듈"""

import logging
import sys
from typing import Any
from loguru import logger
import json
from datetime import datetime

from common.core.config import settings

# loguru 로거 설정
class Formatter:
    """로그 포맷터"""
    def __init__(self) -> None:
        self.padding = 0
        self.fmt = "{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}\n{exception}"

    def format(self, record: Any) -> str:
        """로그 메시지 포맷"""
        # 예외 정보가 있는 경우 스택 트레이스 포함
        if record["exception"]:
            record["exception"] = "\n" + record["exception"]
        else:
            record["exception"] = ""
        return self.fmt

# 기본 로거 설정
logger.remove()  # 기본 핸들러 제거
logger.add(
    sys.stdout,
    format=Formatter().format,
    level="DEBUG" if settings.DEBUG else "INFO",
    colorize=True,
)

# 파일 로깅 설정
if settings.LOG_FILE:
    logger.add(
        settings.LOG_FILE,
        rotation="1 day",    # 매일 로그 파일 교체
        retention="30 days", # 30일간 보관
        compression="zip",   # 이전 로그 압축
        format=Formatter().format,
        level="INFO",
    )

# JSON 로깅 설정
if settings.JSON_LOGS:
    logger.add(
        "logs/json/app.json",
        format=lambda record: json.dumps({
            "timestamp": record["time"].strftime("%Y-%m-%d %H:%M:%S"),
            "level": record["level"].name,
            "message": record["message"],
            "module": record["name"],
            "function": record["function"],
            "line": record["line"],
            "exception": record["exception"]
        }) + "\n",
        level="INFO",
        rotation="1 day",
        retention="30 days",
        compression="zip",
    )

# FastAPI 로깅과 통합
logging.getLogger("uvicorn.access").handlers = [logging.NullHandler()]
logging.getLogger("uvicorn.error").handlers = [logging.NullHandler()]

# 전역 로거 설정
def setup_logging() -> None:
    """전역 로깅 설정"""
    logging.getLogger().handlers = [logging.NullHandler()]
    logging.getLogger("uvicorn").handlers = []
