"""API 라우터 초기화

이 모듈은 FastAPI 라우터들을 초기화하고 등록합니다.
"""

from fastapi import APIRouter
from stockeasy.api.v1.telegram import telegram_router
from stockeasy.api.v1.root_router import router
from stockeasy.api.v1._internal_test import router as internal_test_router
from loguru import logger

# API v1 라우터
#root_router = APIRouter(prefix="/stockeasy", tags=["stockeasy"])
api_router_stockeasy = APIRouter(prefix="/stockeasy", tags=["stockeasy"])

logger.info("루트 라우터 등록 시작")
api_router_stockeasy.include_router(router)
logger.info("루트 라우터 등록 완료")

# 텔레그램 라우터 등록
logger.info("텔레그램 라우터 등록 시작")
api_router_stockeasy.include_router(telegram_router)
logger.info("텔레그램 라우터 등록 완료")

# 내부 테스트 라우터 등록
logger.info("내부 테스트 라우터 등록 시작")
api_router_stockeasy.include_router(internal_test_router)
logger.info("내부 테스트 라우터 등록 완료")
