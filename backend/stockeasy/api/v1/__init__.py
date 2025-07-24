"""API 라우터 초기화

이 모듈은 FastAPI 라우터들을 초기화하고 등록합니다.
"""

import logging
from fastapi import APIRouter
from stockeasy.api.v1.telegram import telegram_router
from stockeasy.api.v1.chat import chat_router
from stockeasy.api.v1._internal_test import router as internal_test_router
from stockeasy.api.v1.financial_data import router as financial_data_router
from stockeasy.api.v1.stats import stats_router
from stockeasy.api.v1.stock_favorites import stock_favorites_router
from loguru import logger

# API v1 라우터
#root_router = APIRouter(prefix="/stockeasy", tags=["stockeasy"])
api_router_stockeasy = APIRouter(prefix="/stockeasy", tags=["stockeasy"])

logger = logging.getLogger(__name__)

# 텔레그램 라우터 등록
logger.info("텔레그램 라우터 등록 시작")
api_router_stockeasy.include_router(telegram_router)
logger.info("텔레그램 라우터 등록 완료")

# 채팅 라우터 등록
logger.info("채팅 라우터 등록 시작")
api_router_stockeasy.include_router(chat_router)
logger.info("채팅 라우터 등록 완료")

# 내부 테스트 라우터 등록
logger.info("내부 테스트 라우터 등록 시작")
api_router_stockeasy.include_router(internal_test_router)
logger.info("내부 테스트 라우터 등록 완료")

# 재무 데이터 라우터 등록
logger.info("재무 데이터 라우터 등록 시작")
api_router_stockeasy.include_router(financial_data_router)
logger.info("재무 데이터 라우터 등록 완료")

# 통계 라우터 등록
logger.info("통계 라우터 등록 시작")
api_router_stockeasy.include_router(stats_router)
logger.info("통계 라우터 등록 완료")

# 관심기업(즐겨찾기) 라우터 등록
logger.info("관심기업(즐겨찾기) 라우터 등록 시작")
api_router_stockeasy.include_router(stock_favorites_router)
logger.info("관심기업(즐겨찾기) 라우터 등록 완료")
