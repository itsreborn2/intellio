"""API 라우터 초기화

이 모듈은 FastAPI 라우터들을 초기화하고 등록합니다.
"""

from fastapi import APIRouter
from app.api.v1.telegram import router as telegram_router

# API v1 라우터
api_router = APIRouter()

# 텔레그램 라우터 등록
api_router.include_router(telegram_router, prefix="/v1", tags=["telegram"])
