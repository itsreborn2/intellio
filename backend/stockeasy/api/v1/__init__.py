"""API 라우터 초기화

이 모듈은 FastAPI 라우터들을 초기화하고 등록합니다.
"""

from fastapi import APIRouter
from stockeasy.api.v1.telegram import telegram_router
import logging

logger = logging.getLogger(__name__)

# API v1 라우터
stockeasy_router = APIRouter()

# 텔레그램 라우터 등록
logger.info("텔레그램 라우터 등록 시작")
stockeasy_router.include_router(telegram_router)
logger.info("텔레그램 라우터 등록 완료")
