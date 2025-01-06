import logging
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

# ANSI 이스케이프 코드를 사용한 색상 정의
class ColorFormatter(logging.Formatter):
    """컬러 로그 포맷터"""
    
    # 로그 레벨별 색상 정의
    COLORS = {
        'DEBUG': '\033[36m',    # 청록색
        'INFO': '\033[32m',     # 초록색
        'WARNING': '\033[33m',   # 노란색
        'ERROR': '\033[31m',    # 빨간색
        'CRITICAL': '\033[41m',  # 빨간 배경
    }
    RESET = '\033[0m'  # 색상 초기화

    def format(self, record):
        # Windows 터미널에서도 색상이 표시되도록 설정
        if sys.platform == 'win32':
            import ctypes
            kernel32 = ctypes.windll.kernel32
            kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)

        # 원본 값 백업
        original_asctime = record.asctime if hasattr(record, 'asctime') else None
        original_name = record.name

        # asctime 설정 (없는 경우 생성)
        if not hasattr(record, 'asctime'):
            record.asctime = self.formatTime(record)

        # levelname에 따른 색상 선택
        color = self.COLORS.get(record.levelname, '')
        
        # time과 name에 levelname 기반 색상 적용
        record.asctime = f"{color}{record.asctime}{self.RESET}"
        record.name = f"{color}{record.name}{self.RESET}"
        
        # 포맷팅
        result = super().format(record)

        # 원본 값 복원
        # if original_asctime:
        #     record.asctime = original_asctime
        record.name = original_name
        
        return result


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

# 로그 파일 설정
log_file_path = os.path.join(log_dir, 'app.log')
log_handler = logging.handlers.RotatingFileHandler(
    filename=log_file_path, maxBytes=10*1024*1024, backupCount=5, encoding='utf-8'
)

logger = logging.getLogger("app")

# 콘솔 핸들러 설정 (컬러 포맷터 사용)
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(ColorFormatter('%(asctime)s/%(name)s - %(message)s'))

# 파일 핸들러 설정 (일반 포맷터 사용)
log_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))

logging.basicConfig(
    #level=logging.INFO,
    handlers=[
        console_handler,  # 컬러 포맷터가 적용된 콘솔 출력
        log_handler      # 일반 포맷터가 적용된 파일 출력
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
