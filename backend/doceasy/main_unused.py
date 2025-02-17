import logging
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging
from contextlib import asynccontextmanager
from logging.config import dictConfig
import sys
from doceasy.api.v1 import api_router_doceasy
from common.core.config import settings
from dotenv import load_dotenv
import os

# 환경변수를 가장 먼저 로드
load_dotenv(override=True)


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
from doceasy.models.project import Project
from doceasy.models.document import Document, DocumentChunk

# 로그 디렉토리 생성 (기존 코드)
log_dir = "logs"
try:
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
except Exception as e:
    print(f"로그 디렉토리 생성 실패: {e}")

# 로깅 설정
logging_config = {
    "version": 1,
    "disable_existing_loggers": True,
    "formatters": {
        "color": {
            "()": ColorFormatter,
            "format": "%(asctime)s/%(name)s - %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S"
        },
        "file": {
            "format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S"
        }
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "color",
            "level": "INFO"
        },
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "formatter": "file",
            "filename": "logs/doceasy.log",
            "maxBytes": 10485760,  # 10MB
            "backupCount": 5,
            "encoding": "utf-8",
            "level": "INFO"
        }
    },
    "loggers": {
        "app": {
            "handlers": ["console", "file"],
            "level": "INFO",
            "propagate": False
        },
        "sqlalchemy.engine": {
            "handlers": ["console", "file"],
            "level": "WARNING",
            "propagate": False
        },
        "uvicorn": {
            "handlers": ["console", "file"],
            "level": "WARNING",
            "propagate": False
        }
    },
    "root": {
        "handlers": ["console", "file"],
        "level": "WARNING"
    }
}

# 로깅 설정 적용
dictConfig(logging_config)

# SQLAlchemy 로그 레벨 설정
logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """애플리케이션 라이프사이클 관리"""
    # 시작 시 실행
    logger = logging.getLogger("app")
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
doceasy.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # 개발 환경
        "http://127.0.0.1:3000",
        settings.DOCEASY_URL,    # 프로덕션 환경 (settings에서 설정)
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@doceasy.middleware("http")
async def log_requests(request, call_next):
    """요청과 응답을 로깅하는 미들웨어"""
    logger = logging.getLogger("app")
    logger.debug(f"Request path: {request.url.path}")
    logger.debug(f"Request method: {request.method}")
    logger.debug(f"Request headers: {request.headers}")
    
    response = await call_next(request)
    
    logger.debug(f"Response status: {response.status_code}")
    return response

# API 라우터 등록
doceasy.include_router(api_router_doceasy, prefix=settings.API_V1_STR)

@doceasy.get("/")
async def root():
    """Root endpoint"""
    return {"message": "Welcome to Intellio API"}
