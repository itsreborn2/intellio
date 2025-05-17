import sys
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from starlette import status
from common.core.config import settings
from dotenv import load_dotenv
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
    logger.info("애플리케이션 시작됨")
    
    # 토큰 사용량 추적 큐 초기화
    try:
        from common.services.token_usage_service import TokenUsageQueue
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
        from common.services.token_usage_service import TokenUsageQueue
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


@app.exception_handler(AuthenticationRedirectException)
async def authentication_redirect_handler(request: Request, exc: AuthenticationRedirectException):
    """인증 리다이렉트 예외 핸들러"""
    return RedirectResponse(
        url=exc.redirect_url,
        status_code=status.HTTP_303_SEE_OTHER
    )