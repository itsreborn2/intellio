"""
증권 데이터 수집 서비스 API 라우터
"""
from fastapi import APIRouter, HTTPException, Depends, Query
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
    date: str = Query(default=None, description="조회할 날짜 (YYYYMMDD), 미입력시 오늘"),
    data_collector: DataCollectorService = Depends(get_data_collector)
):
    """종목 수급 데이터 조회 (키움 API)"""
    try:
        if not date:
            date = datetime.now().strftime("%Y%m%d")
        
        supply_demand = await data_collector.get_supply_demand_data(symbol, date)
        if not supply_demand:
            raise HTTPException(status_code=404, detail="수급 데이터를 찾을 수 없습니다")
        
        return {
            "symbol": symbol,
            "date": date,
            "data": supply_demand,
            "status": "success"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"수급 데이터 조회 실패: {str(e)}")

@stock_router.get("/chart/{symbol}")
async def get_stock_chart(
    symbol: str,
    period: str = "1d",
    interval: str = "1m",
    data_collector: DataCollectorService = Depends(get_data_collector)
):
    """주식 차트 데이터 조회"""
    try:
        chart_data = await data_collector.get_chart_data(symbol, period, interval)
        return {
            "symbol": symbol,
            "period": period,
            "interval": interval,
            "data": chart_data,
            "status": "success"
        }
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