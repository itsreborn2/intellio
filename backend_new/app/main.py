import logging

# SQLAlchemy 로깅 완전 비활성화
logging.getLogger('sqlalchemy').setLevel(logging.ERROR)
logging.getLogger('sqlalchemy.engine').setLevel(logging.ERROR)
logging.getLogger('sqlalchemy.engine.base.Engine').setLevel(logging.ERROR)

import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging
from contextlib import asynccontextmanager
from logging.config import dictConfig
import sys
from app.api.v1 import api_router
from app.core.config import settings
from app.models.base import Base
from app.core.database import engine
from logging.handlers import RotatingFileHandler
import os

# 모든 모델을 임포트하여 매핑이 이루어지도록 합니다
from app.models.project import Project
from app.models.document import Document, DocumentChunk

# 로그 디렉토리 생성 (기존 코드)
log_dir = "logs"
try:
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
except Exception as e:
    print(f"로그 디렉토리 생성 실패: {e}")

# 로깅 설정
log_file_path = os.path.join(log_dir, "app.log") # 로그 파일 경로 설정
log_handler = logging.handlers.RotatingFileHandler( # RotatingFileHandler 추가
    filename=log_file_path, maxBytes=10*1024*1024, backupCount=5, encoding='utf-8' # 10MB 파일, 5개 백업
)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
log_handler.setFormatter(formatter)

logger = logging.getLogger("app")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout), # 콘솔 출력
        log_handler # 파일 출력 추가
    ]
)

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
    lifespan=lifespan,
    redirect_slashes=False  # 슬래시 리다이렉션 비활성화
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
