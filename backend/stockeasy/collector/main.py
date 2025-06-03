"""
증권 데이터 수집 서비스 메인 애플리케이션
"""
import asyncio
from contextlib import asynccontextmanager
from typing import Dict, Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from loguru import logger

from stockeasy.collector.core.config import get_settings
from stockeasy.collector.core.logger import get_logger
from stockeasy.collector.services.data_collector import DataCollectorService
from stockeasy.collector.services.cache_manager import CacheManager
from stockeasy.collector import dependencies

settings = get_settings()

# 전역 서비스 인스턴스
data_collector: DataCollectorService = None
cache_manager: CacheManager = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """애플리케이션 생명주기 관리"""
    global data_collector, cache_manager
    
    try:
        logger.info("증권 데이터 수집 서비스 시작 중...")
        
        # 캐시 매니저 초기화
        cache_manager = CacheManager()
        await cache_manager.initialize()
        dependencies.set_cache_manager(cache_manager)
        
        # 데이터 수집 서비스 초기화 (스케줄러 포함)
        data_collector = DataCollectorService(cache_manager)
        await data_collector.initialize()
        dependencies.set_data_collector(data_collector)
        
        # 실시간 데이터 수집 시작
        if settings.AUTO_START_REALTIME:
            asyncio.create_task(data_collector.start_realtime_collection())
        
        logger.info("증권 데이터 수집 서비스 시작 완료 (스케줄러 포함)")
        logger.info("매일 아침 7시 30분에 자동으로 종목 리스트가 업데이트됩니다.")
        
        yield  # 애플리케이션 실행
        
    except Exception as e:
        logger.error(f"서비스 시작 중 오류 발생: {e}")
        raise
    finally:
        logger.info("증권 데이터 수집 서비스 종료 중...")
        
        # 정리 작업
        if data_collector:
            await data_collector.shutdown()
        if cache_manager:
            await cache_manager.close()
        
        logger.info("증권 데이터 수집 서비스 종료 완료")


# FastAPI 애플리케이션 생성
app = FastAPI(
    title="증권 데이터 수집 서비스",
    description="키움증권 REST API를 이용한 주식 데이터 수집 및 제공",
    version="1.0.0",
    lifespan=lifespan
)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# UTF-8 인코딩 미들웨어 추가
@app.middleware("http")
async def add_charset_middleware(request, call_next):
    """JSON 응답에 charset=utf-8 추가"""
    response = await call_next(request)
    
    # JSON 응답인 경우 charset 추가
    if response.headers.get("content-type") == "application/json":
        response.headers["content-type"] = "application/json; charset=utf-8"
    
    return response


# 라우터 등록 (import를 여기서 해서 순환 import 방지)
from stockeasy.collector.api.routers import stock_router, etf_router, market_router, admin_router

app.include_router(stock_router, prefix="/api/v1/stock", tags=["주식"])
app.include_router(etf_router, prefix="/api/v1/etf", tags=["ETF"])
app.include_router(market_router, prefix="/api/v1/market", tags=["시장"])
app.include_router(admin_router, prefix="/api/v1/admin", tags=["관리"])


@app.get("/")
async def root():
    """서비스 상태 확인"""
    return {
        "service": "증권 데이터 수집 서비스",
        "status": "running",
        "version": "1.0.0"
    }


@app.get("/health")
async def health_check():
    """헬스 체크"""
    try:
        # 데이터 수집 서비스 상태 확인
        collector_status = "healthy" if data_collector and data_collector.is_healthy() else "unhealthy"
        
        # 캐시 매니저 상태 확인
        cache_status = "healthy" if cache_manager and await cache_manager.is_healthy() else "unhealthy"
        
        overall_status = "healthy" if collector_status == "healthy" and cache_status == "healthy" else "unhealthy"
        
        return {
            "status": overall_status,
            "services": {
                "data_collector": collector_status,
                "cache_manager": cache_status
            },
            "timestamp": asyncio.get_event_loop().time()
        }
    except Exception as e:
        logger.error(f"헬스 체크 중 오류 발생: {e}")
        raise HTTPException(status_code=500, detail="헬스 체크 실패")


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """전역 예외 처리"""
    logger.error(f"예외 발생: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "내부 서버 오류가 발생했습니다."}
    )


# 전역 서비스 접근 함수는 dependencies 모듈로 이동됨


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8001,
        reload=settings.DEBUG,
        log_level="info"
    ) 