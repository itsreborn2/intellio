import sys
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from starlette import status
from common.core.config import settings
from dotenv import load_dotenv
import logging
from logging.config import dictConfig
from contextlib import asynccontextmanager
import os
from common.core.exceptions import AuthenticationRedirectException
from loguru import logger

def LoadEnvGlobal():
    # ENV에 따른 환경변수 파일 로드
    env = os.getenv("ENV", "development")
    env_file = f".env.{env}"

    logger.info(f"[LoadEnvGlobal] Loading environment : {env_file}")
    if os.path.exists(env_file):
        load_dotenv(env_file, override=True)
    else:
        logger.warning(f"Environment file {env_file} not found!")

LoadEnvGlobal()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """애플리케이션 라이프사이클 관리"""
    # 시작 시 실행
    logger = logging.getLogger("app")
    logger.info("애플리케이션 시작됨")
    
    # 토큰 사용량 추적 큐 초기화
    try:
        from common.services.embedding_models import TokenUsageQueue
        from common.core.deps import get_db
        
        # 토큰 사용량 큐 초기화
        token_queue = TokenUsageQueue()
        await token_queue.initialize(session_factory=get_db)
        logger.info("토큰 사용량 추적 큐가 초기화되었습니다")
    except Exception as e:
        logger.error(f"토큰 사용량 추적 큐 초기화 실패: {str(e)}")
    
    yield
    
    # 종료 시 실행
    try:
        # 토큰 사용량 큐 종료
        from common.services.embedding_models import TokenUsageQueue
        token_queue = TokenUsageQueue()
        await token_queue.shutdown()
        logger.info("토큰 사용량 추적 큐가 종료되었습니다")
    except Exception as e:
        logger.error(f"토큰 사용량 추적 큐 종료 실패: {str(e)}")
        
    logger.info("애플리케이션 종료됨")

# FastAPI 애플리케이션 인스턴스 생성
app = FastAPI(
    title=settings.PROJECT_NAME,
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
        "http://localhost:3010",  # 개발 환경
        "http://127.0.0.1:3010",
        "http://localhost:3020",  # 개발 환경
        "http://127.0.0.1:3020",
        "https://intellio.kr",     # 추가
        "https://www.intellio.kr", # 추가
        "https://doceasy.intellio.kr",  # 추가
        "https://stockeasy.intellio.kr", # 추가
        settings.DOCEASY_URL,
        settings.INTELLIO_URL,
        settings.STOCKEASY_URL
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Set-Cookie", "Authorization", "X-Requested-With"],
    expose_headers=["Set-Cookie"],
)


@app.middleware("http")
async def log_requests(request, call_next):
    """요청과 응답을 로깅하는 미들웨어"""
    logger = logging.getLogger("app")
    logger.debug(f"Request path: {request.url.path}")
    logger.debug(f"Request method: {request.method}")
    logger.debug(f"Request headers: {request.headers}")
    
    response = await call_next(request)
    
    logger.debug(f"Response status: {response.status_code}")
    return response


# 헬스 체크 엔드포인트
@app.get("/health", tags=["Health"])
async def health_check():
    return {"status": "ok"}


# 로그 디렉토리 생성 (기존 코드)
log_dir = "logs"
try:
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
except Exception as e:
    print(f"로그 디렉토리 생성 실패: {e}")



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
            "filename": "logs/app.log",
            "maxBytes": 10485760,  # 10MB
            "backupCount": 5,
            "encoding": "utf-8",
            "level": "INFO"
        }
    },
    "loggers": {
        "common": {
            "handlers": ["console", "file"],
            "level": "INFO",
            "propagate": False
        },
        "doceasy": {
            "handlers": ["console", "file"],
            "level": "INFO",
            "propagate": False
        },
        "stockeasy": {
            "handlers": ["console", "file"],
            "level": "INFO",
            "propagate": False
        },
        
        "uvicorn": {
            "handlers": ["console", "file"],
            "level": "INFO",
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

@app.exception_handler(AuthenticationRedirectException)
async def authentication_redirect_handler(request: Request, exc: AuthenticationRedirectException):
    """인증 리다이렉트 예외 핸들러"""
    return RedirectResponse(
        url=exc.redirect_url,
        status_code=status.HTTP_303_SEE_OTHER
    )