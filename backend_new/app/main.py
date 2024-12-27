from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging
from contextlib import asynccontextmanager

from app.api.v1 import api_router
from app.core.config import settings
from app.models.base import Base
from app.core.database import engine

# 모든 모델을 임포트하여 매핑이 이루어지도록 합니다
from app.models.project import Project
from app.models.document import Document, DocumentChunk

# 로깅 설정
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("app")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """애플리케이션 라이프사이클 관리"""
    # 시작 시 실행
    logger.info("애플리케이션 시작됨")
    yield
    # 종료 시 실행
    logger.info("애플리케이션 종료됨")

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    debug=True,  # 디버그 모드 활성화
    lifespan=lifespan
)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # 개발 환경
        "http://127.0.0.1:3000",
        settings.FRONTEND_URL,    # 프로덕션 환경 (settings에서 설정)
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def log_requests(request, call_next):
    """요청과 응답을 로깅하는 미들웨어"""
    logger.debug(f"Request path: {request.url.path}")
    logger.debug(f"Request method: {request.method}")
    logger.debug(f"Request headers: {request.headers}")
    
    response = await call_next(request)
    
    logger.debug(f"Response status: {response.status_code}")
    return response

# API 라우터 등록
app.include_router(api_router, prefix=settings.API_V1_STR)

@app.get("/")
async def root():
    """Root endpoint"""
    return {"message": "Welcome to Intellio API"}
