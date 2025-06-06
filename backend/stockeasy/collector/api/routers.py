"""
증권 데이터 수집 서비스 API 라우터
"""
from fastapi import APIRouter, HTTPException, Depends, Query, Response
from fastapi.responses import JSONResponse
import gzip
import json
from typing import List, Optional, Dict, Any
from datetime import datetime

from stockeasy.collector.dependencies import get_data_collector, get_cache_manager
from stockeasy.collector.services.data_collector import DataCollectorService
from stockeasy.collector.services.cache_manager import CacheManager

from loguru import logger
# 주식 데이터 라우터( /api/v1/stock )
stock_router = APIRouter()


@stock_router.get("/list_for_stockai")
async def get_all_stock_list_for_stockai(
    data_collector: DataCollectorService = Depends(get_data_collector)
):
    """전체 종목 리스트 조회 (code, name만)"""
    try:
        stock_list = await data_collector.get_all_stock_list_for_stockai()
        return {
            "count": len(stock_list),
            "status": "success",
            "last_update_time": await data_collector.get_last_update_time("stockai"),
            "stocks": stock_list
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"종목 리스트 조회 실패: {str(e)}")


@stock_router.get("/list")
async def get_all_stock_list(
    data_collector: DataCollectorService = Depends(get_data_collector)
):
    """전체 종목 리스트 조회 (code, name만)"""
    try:
        stock_list = await data_collector.get_all_stock_list()
        return {
            "count": len(stock_list),
            "status": "success",
            "stocks": stock_list
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"종목 리스트 조회 실패: {str(e)}")

@stock_router.get("/search")
async def search_stocks(
    keyword: str = Query(..., description="검색할 종목명 키워드"),
    limit: int = Query(20, description="결과 제한 수", ge=1, le=100),
    data_collector: DataCollectorService = Depends(get_data_collector)
):
    """종목명으로 종목 검색"""
    try:
        results = await data_collector.search_stocks_by_name(keyword, limit)
        return {
            "keyword": keyword,
            "stocks": results,
            "count": len(results),
            "status": "success"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"종목 검색 실패: {str(e)}")

@stock_router.get("/list/refresh")
async def refresh_stock_list(
    data_collector: DataCollectorService = Depends(get_data_collector)
):
    """종목 리스트 강제 새로고침"""
    try:
        result = await data_collector.force_refresh_stock_list()
        return {
            "message": "종목 리스트 새로고침 완료",
            "result": result,
            "status": "success"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"종목 리스트 새로고침 실패: {str(e)}")

@stock_router.get("/price/{symbol}")
async def get_stock_price(
    symbol: str,
    data_collector: DataCollectorService = Depends(get_data_collector)
):
    """실시간 주식 가격 조회"""
    try:
        price_data = await data_collector.get_realtime_price(symbol)
        return {
            "symbol": symbol,
            "data": price_data,
            "status": "success"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"가격 데이터 조회 실패: {str(e)}")

@stock_router.get("/info/{symbol}")
async def get_stock_info(
    symbol: str,
    data_collector: DataCollectorService = Depends(get_data_collector)
):
    """종목 기본정보 조회 (키움 API)"""
    try:
        stock_info = await data_collector.get_stock_info_by_code(symbol)
        logger.info(f"종목 정보 조회: {stock_info}")
        if not stock_info:
            raise HTTPException(status_code=404, detail="종목 정보를 찾을 수 없습니다")
        
        return {
            "symbol": symbol,
            "data": stock_info,
            "status": "success"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"종목 정보 조회 실패: {str(e)}")

@stock_router.get("/supply-demand/{symbol}")
async def get_supply_demand(
    symbol: str,
    start_date: str = Query(default=None, description="시작일 (YYYYMMDD), 미입력시 오늘"),
    end_date: str = Query(default=None, description="종료일 (YYYYMMDD), 미입력시 start_date와 동일"),
    compressed: bool = Query(False, description="압축된 형태로 반환 (대량 데이터용)"),
    gzip_enabled: bool = Query(False, description="gzip 압축 사용 (더 작은 크기)"),
    data_collector: DataCollectorService = Depends(get_data_collector)
):
    """
    종목 수급 데이터 조회 (기간별)
    
    - compressed=false: 표준 JSON 형태 (기본값)
    - compressed=true: 압축된 배열 형태 (데이터 크기 50-70% 절약)
    - gzip_enabled=true: gzip 압축 적용 (추가 30-50% 절약)
    """
    try:
        if not start_date:
            start_date = datetime.now().strftime("%Y%m%d")
        
        supply_demand = await data_collector.get_supply_demand_data(
            symbol, start_date, end_date, compressed
        )
        if not supply_demand:
            raise HTTPException(status_code=404, detail="수급 데이터를 찾을 수 없습니다")
        
        response_data = {
            "symbol": symbol,
            "start_date": start_date,
            "end_date": end_date or start_date,
            "compressed": compressed,
            "gzip_enabled": gzip_enabled,
            "data": supply_demand,
            "status": "success"
        }
        
        if gzip_enabled:
            # JSON을 문자열로 변환 후 gzip 압축
            json_str = json.dumps(response_data, ensure_ascii=False, default=str)
            compressed_content = gzip.compress(json_str.encode('utf-8'))
            
            return Response(
                content=compressed_content,
                media_type="application/json",
                headers={
                    "Content-Encoding": "gzip", # 여기서 gzip 을 알려줘야, 프론트에서 자동 압축해제 가능.
                    "Content-Length": str(len(compressed_content))
                }
            )
        else:
            return response_data
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"수급 데이터 조회 실패: {str(e)}")

@stock_router.get("/chart/{symbol}")
async def get_stock_chart(
    symbol: str,
    period: str = Query("1y", description="조회 기간 (1d, 1w, 1m, 3m, 6m, 1y, 2y, 5y)"),
    interval: str = Query("1d", description="간격 (1m, 5m, 15m, 30m, 1h, 1d, 1w, 1M)"),
    compressed: bool = Query(False, description="압축된 형태로 반환 (대량 데이터용)"),
    gzip_enabled: bool = Query(False, description="gzip 압축 사용 (더 작은 크기)"),
    data_collector: DataCollectorService = Depends(get_data_collector)
):
    """
    주식 차트 데이터 조회
    
    - compressed=false: 표준 JSON 형태 (기본값)
    - compressed=true: 압축된 배열 형태 (데이터 크기 50-70% 절약)
    - gzip_enabled=true: gzip 압축 적용 (추가 30-50% 절약)
    """
    try:
        chart_data = await data_collector.get_chart_data(symbol, period, interval, compressed)
        
        response_data = {
            "symbol": symbol,
            "period": period,
            "interval": interval,
            "compressed": compressed,
            "gzip_enabled": gzip_enabled,
            "data": chart_data,
            "status": "success"
        }
        
        if gzip_enabled:
            # JSON을 문자열로 변환 후 gzip 압축
            json_str = json.dumps(response_data, ensure_ascii=False, default=str)
            compressed_content = gzip.compress(json_str.encode('utf-8'))
            
            return Response(
                content=compressed_content,
                media_type="application/json",
                headers={
                    "Content-Encoding": "gzip", # 여기서 gzip 을 알려줘야, 프론트에서 자동 압축해제 가능.
                    "Content-Length": str(len(compressed_content))
                }
            )
        else:
            return response_data
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"차트 데이터 조회 실패: {str(e)}")


# ETF 데이터 라우터
etf_router = APIRouter()

@etf_router.get("/list")
async def get_etf_list(
    data_collector: DataCollectorService = Depends(get_data_collector)
):
    """ETF 목록 조회"""
    try:
        etf_list = await data_collector.get_etf_list()
        return {
            "etfs": etf_list,
            "count": len(etf_list),
            "status": "success"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"ETF 목록 조회 실패: {str(e)}")

@etf_router.get("/components/{etf_code}")
async def get_etf_components(
    etf_code: str,
    data_collector: DataCollectorService = Depends(get_data_collector)
):
    """ETF 구성종목 조회 (pykrx)"""
    try:
        components = await data_collector.get_etf_components(etf_code)
        return {
            "etf_code": etf_code,
            "components": components,
            "count": len(components),
            "status": "success"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"ETF 구성종목 조회 실패: {str(e)}")

@etf_router.post("/components/{etf_code}/refresh")
async def refresh_etf_components(
    etf_code: str,
    data_collector: DataCollectorService = Depends(get_data_collector)
):
    """ETF 구성종목 갱신"""
    try:
        await data_collector.refresh_etf_components(etf_code)
        return {
            "etf_code": etf_code,
            "message": "ETF 구성종목 갱신 완료",
            "status": "success"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"ETF 구성종목 갱신 실패: {str(e)}")

@etf_router.post("/components/refresh-all")
async def refresh_all_etf_components(
    data_collector: DataCollectorService = Depends(get_data_collector)
):
    """모든 주요 ETF 구성종목 일괄 갱신"""
    try:
        results = await data_collector.update_all_etf_components()
        total_components = sum(results.values())
        
        return {
            "message": "모든 ETF 구성종목 갱신 완료",
            "results": results,
            "total_etfs": len(results),
            "total_components": total_components,
            "status": "success"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"ETF 일괄 갱신 실패: {str(e)}")


# 시장 데이터 라우터
market_router = APIRouter()

@market_router.get("/status")
async def get_market_status(
    data_collector: DataCollectorService = Depends(get_data_collector)
):
    """시장 상태 조회"""
    try:
        market_status = await data_collector.get_market_status()
        return {
            "market_status": market_status,
            "status": "success"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"시장 상태 조회 실패: {str(e)}")

@market_router.get("/indices")
async def get_market_indices(
    data_collector: DataCollectorService = Depends(get_data_collector)
):
    """주요 지수 조회"""
    try:
        indices = await data_collector.get_market_indices()
        return {
            "indices": indices,
            "status": "success"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"지수 데이터 조회 실패: {str(e)}")


# 관리용 라우터
admin_router = APIRouter()

@admin_router.post("/scheduler/start")
async def start_scheduler(
    data_collector: DataCollectorService = Depends(get_data_collector)
):
    """스케줄러 시작"""
    try:
        await data_collector.scheduler_service.start()
        return {
            "message": "스케줄러 시작됨",
            "status": "success"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"스케줄러 시작 실패: {str(e)}")

@admin_router.post("/scheduler/stop")
async def stop_scheduler(
    data_collector: DataCollectorService = Depends(get_data_collector)
):
    """스케줄러 중지"""
    try:
        await data_collector.scheduler_service.shutdown()
        return {
            "message": "스케줄러 중지됨",
            "status": "success"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"스케줄러 중지 실패: {str(e)}")

@admin_router.get("/scheduler/stats")
async def get_scheduler_stats(
    data_collector: DataCollectorService = Depends(get_data_collector)
):
    """스케줄러 통계 조회"""
    try:
        stats = data_collector.scheduler_service.get_job_stats()
        return {
            "scheduler_stats": stats,
            "status": "success"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"스케줄러 통계 조회 실패: {str(e)}")

@admin_router.post("/scheduler/trigger/stocks")
async def trigger_stock_update(
    data_collector: DataCollectorService = Depends(get_data_collector)
):
    """즉시 종목 리스트 업데이트 실행"""
    try:
        await data_collector.scheduler_service.trigger_stock_update_now()
        return {
            "message": "종목 리스트 업데이트 실행 완료",
            "status": "success"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"종목 리스트 업데이트 실행 실패: {str(e)}")

@admin_router.post("/scheduler/trigger/etf")
async def trigger_etf_update(
    data_collector: DataCollectorService = Depends(get_data_collector)
):
    """즉시 ETF 구성종목 업데이트 실행"""
    try:
        await data_collector.scheduler_service.trigger_etf_update_now()
        return {
            "message": "ETF 구성종목 업데이트 실행 완료",
            "status": "success"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"ETF 구성종목 업데이트 실행 실패: {str(e)}")

@admin_router.post("/start-collection")
async def start_realtime_collection(
    data_collector: DataCollectorService = Depends(get_data_collector)
):
    """실시간 데이터 수집 시작"""
    try:
        await data_collector.start_realtime_collection()
        return {
            "message": "실시간 데이터 수집 시작됨",
            "status": "success"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"실시간 수집 시작 실패: {str(e)}")

@admin_router.post("/stop-collection")
async def stop_realtime_collection(
    data_collector: DataCollectorService = Depends(get_data_collector)
):
    """실시간 데이터 수집 중지"""
    try:
        await data_collector.stop_realtime_collection()
        return {
            "message": "실시간 데이터 수집 중지됨",
            "status": "success"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"실시간 수집 중지 실패: {str(e)}")

@admin_router.get("/stats")
async def get_collection_stats(
    data_collector: DataCollectorService = Depends(get_data_collector)
):
    """수집 통계 조회"""
    try:
        stats = await data_collector.get_collection_stats()
        return {
            "stats": stats,
            "status": "success"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"통계 조회 실패: {str(e)}")

@admin_router.post("/update-symbols")
async def update_symbol_mappings(
    data_collector: DataCollectorService = Depends(get_data_collector)
):
    """종목 코드-이름 매핑 업데이트"""
    try:
        result = await data_collector.update_symbol_mappings()
        return {
            "message": "종목 매핑 업데이트 완료",
            "result": result,
            "status": "success"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"종목 매핑 업데이트 실패: {str(e)}")

@admin_router.post("/cache/refresh")
async def force_cache_refresh(
    data_collector: DataCollectorService = Depends(get_data_collector)
):
    """캐시 강제 갱신"""
    try:
        await data_collector.force_cache_refresh()
        return {
            "message": "캐시 강제 갱신 완료",
            "status": "success"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"캐시 갱신 실패: {str(e)}")

@admin_router.get("/kiwoom/stats")
async def get_kiwoom_stats(
    data_collector: DataCollectorService = Depends(get_data_collector)
):
    """키움 API 통계 조회"""
    try:
        stats = await data_collector.get_collection_stats()
        kiwoom_stats = stats.get("kiwoom_stats", {})
        
        return {
            "kiwoom_stats": kiwoom_stats,
            "status": "success"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"키움 API 통계 조회 실패: {str(e)}")

@admin_router.get("/etf/stats")
async def get_etf_crawler_stats(
    data_collector: DataCollectorService = Depends(get_data_collector)
):
    """ETF 크롤러 통계 조회"""
    try:
        stats = await data_collector.get_collection_stats()
        etf_stats = stats.get("etf_stats", {})
        
        return {
            "etf_stats": etf_stats,
            "status": "success"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"ETF 크롤러 통계 조회 실패: {str(e)}")

# ========================================
# 대량 배치 수집 엔드포인트
# ========================================

@admin_router.post("/batch/collect/start")
async def start_batch_collection(
    collect_chart_data: bool = Query(True, description="차트 데이터 수집 여부"),
    collect_supply_data: bool = Query(True, description="수급 데이터 수집 여부"),
    chart_months: int = Query(24, description="차트 데이터 수집 개월 수", ge=1, le=60),
    supply_months: int = Query(6, description="수급 데이터 수집 개월 수", ge=1, le=24),
    data_collector: DataCollectorService = Depends(get_data_collector)
):
    """
    전종목 대량 배치 수집 시작
    
    Args:
        collect_chart_data: 차트 데이터 수집 여부 (기본 True)
        collect_supply_data: 수급 데이터 수집 여부 (기본 True)
        chart_months: 차트 데이터 수집 개월 수 (기본 24개월)
        supply_months: 수급 데이터 수집 개월 수 (기본 6개월)
    """
    try:
        logger.info(f"대량 배치 수집 시작 요청: 차트({chart_months}개월)={collect_chart_data}, 수급({supply_months}개월)={collect_supply_data}")
        
        result = await data_collector.start_batch_collection_job(
            collect_chart_data=collect_chart_data,
            collect_supply_data=collect_supply_data,
            chart_months=chart_months,
            supply_months=supply_months
        )
        
        return {
            "message": "대량 배치 수집 작업이 시작되었습니다",
            "result": result,
            "status": "success"
        }
    except Exception as e:
        logger.error(f"대량 배치 수집 시작 실패: {e}")
        raise HTTPException(status_code=500, detail=f"대량 배치 수집 시작 실패: {str(e)}")

@admin_router.post("/batch/collect/chart")
async def collect_chart_data_only(
    months_back: int = Query(24, description="수집할 개월 수", ge=1, le=60),
    batch_size: int = Query(50, description="배치 크기", ge=10, le=100),
    data_collector: DataCollectorService = Depends(get_data_collector)
):
    """
    전종목 차트 데이터만 수집
    
    Args:
        months_back: 수집할 개월 수 (기본 24개월)
        batch_size: 배치 크기 (기본 50)
    """
    try:
        logger.info(f"차트 데이터 수집 시작: {months_back}개월, 배치크기={batch_size}")
        
        result = await data_collector.collect_all_stock_chart_data(
            months_back=months_back,
            batch_size=batch_size
        )
        
        return {
            "message": "차트 데이터 수집이 완료되었습니다",
            "result": result,
            "status": "success"
        }
    except Exception as e:
        logger.error(f"차트 데이터 수집 실패: {e}")
        raise HTTPException(status_code=500, detail=f"차트 데이터 수집 실패: {str(e)}")

@admin_router.post("/batch/collect/supply")
async def collect_supply_data_only(
    months_back: int = Query(6, description="수집할 개월 수", ge=1, le=24),
    batch_size: int = Query(20, description="배치 크기", ge=5, le=50),
    data_collector: DataCollectorService = Depends(get_data_collector)
):
    """
    전종목 수급 데이터만 수집
    
    Args:
        months_back: 수집할 개월 수 (기본 6개월)
        batch_size: 배치 크기 (기본 20)
    """
    try:
        logger.info(f"수급 데이터 수집 시작: {months_back}개월, 배치크기={batch_size}")
        
        result = await data_collector.collect_all_supply_demand_data(
            months_back=months_back,
            batch_size=batch_size
        )
        
        return {
            "message": "수급 데이터 수집이 완료되었습니다",
            "result": result,
            "status": "success"
        }
    except Exception as e:
        logger.error(f"수급 데이터 수집 실패: {e}")
        raise HTTPException(status_code=500, detail=f"수급 데이터 수집 실패: {str(e)}")

@admin_router.get("/batch/status")
async def get_batch_collection_status(
    data_collector: DataCollectorService = Depends(get_data_collector)
):
    """배치 수집 상태 조회"""
    try:
        status = await data_collector.get_batch_collection_status()
        return {
            "batch_status": status,
            "status": "success"
        }
    except Exception as e:
        logger.error(f"배치 수집 상태 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=f"배치 수집 상태 조회 실패: {str(e)}")

# ========================================
# TimescaleDB 관리 엔드포인트
# ========================================

@admin_router.get("/timescale/health")
async def get_timescale_health():
    """TimescaleDB 헬스체크"""
    try:
        from stockeasy.collector.services.timescale_service import timescale_service
        health = await timescale_service.health_check()
        return {
            "timescale_health": health,
            "status": "success"
        }
    except Exception as e:
        logger.error(f"TimescaleDB 헬스체크 실패: {e}")
        raise HTTPException(status_code=500, detail=f"TimescaleDB 헬스체크 실패: {str(e)}")

@admin_router.get("/timescale/stats")
async def get_timescale_stats():
    """TimescaleDB 통계 조회"""
    try:
        from stockeasy.collector.services.timescale_service import timescale_service
        stats = await timescale_service.get_statistics()
        return {
            "timescale_stats": stats,
            "status": "success"
        }
    except Exception as e:
        logger.error(f"TimescaleDB 통계 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=f"TimescaleDB 통계 조회 실패: {str(e)}")

@admin_router.get("/timescale/data-count/{table_name}")
async def get_data_count_by_table(
    table_name: str,
    symbol: Optional[str] = Query(None, description="종목코드 (선택사항)")
):
    """테이블별 데이터 건수 조회"""
    try:
        from stockeasy.collector.services.timescale_service import timescale_service
        
        if table_name not in ["stock_prices", "supply_demand"]:
            raise HTTPException(status_code=400, detail="지원되지 않는 테이블명입니다")
        
        data_count = await timescale_service.get_data_count_by_symbol(table_name, symbol)
        return {
            "data_count": data_count,
            "status": "success"
        }
    except Exception as e:
        logger.error(f"데이터 건수 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=f"데이터 건수 조회 실패: {str(e)}")

@admin_router.get("/timescale/duplicates/{table_name}")
async def check_duplicate_data(
    table_name: str,
    symbol: Optional[str] = Query(None, description="종목코드 (선택사항)")
):
    """중복 데이터 체크"""
    try:
        from stockeasy.collector.services.timescale_service import timescale_service
        
        if table_name not in ["stock_prices", "supply_demand"]:
            raise HTTPException(status_code=400, detail="지원되지 않는 테이블명입니다")
        
        duplicates = await timescale_service.check_duplicate_data(table_name, symbol)
        return {
            "duplicates": duplicates,
            "status": "success"
        }
    except Exception as e:
        logger.error(f"중복 데이터 체크 실패: {e}")
        raise HTTPException(status_code=500, detail=f"중복 데이터 체크 실패: {str(e)}")

@admin_router.post("/timescale/cleanup/{table_name}")
async def cleanup_old_data(
    table_name: str,
    days_to_keep: int = Query(730, description="보관할 일수", ge=30, le=3650)
):
    """오래된 데이터 정리"""
    try:
        from stockeasy.collector.services.timescale_service import timescale_service
        
        if table_name not in ["stock_prices", "supply_demand"]:
            raise HTTPException(status_code=400, detail="지원되지 않는 테이블명입니다")
        
        result = await timescale_service.cleanup_old_data(table_name, days_to_keep)
        return {
            "cleanup_result": result,
            "status": "success"
        }
    except Exception as e:
        logger.error(f"데이터 정리 실패: {e}")
        raise HTTPException(status_code=500, detail=f"데이터 정리 실패: {str(e)}")

@admin_router.get("/debug/supply-demand/{symbol}")
async def debug_supply_demand_data(
    symbol: str,
    limit: int = Query(10, description="조회할 데이터 수", ge=1, le=100)
):
    """수급 데이터 디버깅용 조회"""
    try:
        from stockeasy.collector.services.timescale_service import timescale_service
        from sqlalchemy import text
        from stockeasy.collector.core.timescale_database import get_timescale_session_context
        
        async with get_timescale_session_context() as session:
            # 전체 건수 조회
            count_query = text("SELECT COUNT(*) FROM supply_demand WHERE symbol = :symbol")
            count_result = await session.execute(count_query, {"symbol": symbol})
            total_count = count_result.scalar()
            
            # 최신 데이터 조회
            data_query = text("""
                SELECT date, symbol, current_price, individual_investor, foreign_investor, institution_total 
                FROM supply_demand 
                WHERE symbol = :symbol 
                ORDER BY date DESC 
                LIMIT :limit
            """)
            data_result = await session.execute(data_query, {"symbol": symbol, "limit": limit})
            data = data_result.fetchall()
            
            # 날짜 범위 조회
            range_query = text("""
                SELECT MIN(date) as min_date, MAX(date) as max_date 
                FROM supply_demand 
                WHERE symbol = :symbol
            """)
            range_result = await session.execute(range_query, {"symbol": symbol})
            date_range = range_result.fetchone()
            
            return {
                "symbol": symbol,
                "total_count": total_count,
                "date_range": {
                    "min_date": str(date_range.min_date) if date_range else None,
                    "max_date": str(date_range.max_date) if date_range else None
                } if date_range else None,
                "sample_data": [
                    {
                        "date": str(row.date),
                        "symbol": row.symbol,
                        "current_price": float(row.current_price) if row.current_price else None,
                        "individual_investor": int(row.individual_investor) if row.individual_investor else None,
                        "foreign_investor": int(row.foreign_investor) if row.foreign_investor else None,
                        "institution_total": int(row.institution_total) if row.institution_total else None
                    } for row in data
                ],
                "status": "success"
            }
            
    except Exception as e:
        logger.error(f"수급 데이터 디버깅 실패: {e}")
        raise HTTPException(status_code=500, detail=f"수급 데이터 디버깅 실패: {str(e)}") 