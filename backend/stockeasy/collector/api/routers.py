"""
증권 데이터 수집 서비스 API 라우터
"""
from fastapi import APIRouter, HTTPException, Depends, Query, Response
from fastapi.responses import JSONResponse
import gzip
import json
from typing import List, Optional, Dict, Any
from datetime import datetime

from stockeasy.collector.dependencies import get_data_collector
from stockeasy.collector.services.data_collector import DataCollectorService

from loguru import logger
# 주식 데이터 라우터( /api/v1/stock )
stock_router = APIRouter()


@stock_router.get("/list_for_stockai")
async def get_all_stock_list_for_stockai(
    gzip_enabled: bool = Query(False, description="gzip 압축 사용 (더 작은 크기)"),
    data_collector: DataCollectorService = Depends(get_data_collector)
):
    """
    전체 종목 리스트 조회 (code, name만) - 압축된 배열 형태로 반환
    
    - 기본: 압축된 배열 형태 (데이터 크기 50-70% 절약)
    - gzip_enabled=true: gzip 압축 적용 (추가 30-50% 절약)
    """
    try:
        stock_list = await data_collector.get_all_stock_list_for_stockai()
        
        # 항상 압축된 형태로 반환: 헤더와 데이터 배열 분리
        response_data = {
            "count": len(stock_list),
            "status": "success",
            "compressed": True,
            "gzip_enabled": gzip_enabled,
            "last_update_time": await data_collector.get_last_update_time("stockai"),
            "headers": ["code", "name", "market"],
            "data": [
                [stock["code"], stock["name"], stock.get("market", "")]
                for stock in stock_list
            ]
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
            "unit" : "1000000",
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

@stock_router.get("/charts/multiple")
async def get_multiple_stock_charts(
    symbols: str = Query(..., description="종목 코드들 (쉼표로 구분, 예: 005930,000660,035420)"),
    period: str = Query("1y", description="조회 기간 (1d, 1w, 1m, 3m, 6m, 1y, 2y, 5y)"),
    interval: str = Query("1d", description="간격 (1m, 5m, 15m, 30m, 1h, 1d, 1w, 1M)"),
    compressed: bool = Query(False, description="압축된 형태로 반환 (대량 데이터용)"),
    gzip_enabled: bool = Query(False, description="gzip 압축 사용 (더 작은 크기)"),
    data_collector: DataCollectorService = Depends(get_data_collector)
):
    """
    여러 종목의 차트 데이터 일괄 조회
    
    - symbols: 쉼표로 구분된 종목코드들 (최대 20개)
    - compressed=false: 표준 JSON 형태 (기본값)
    - compressed=true: 압축된 배열 형태 (데이터 크기 50-70% 절약)
    - gzip_enabled=true: gzip 압축 적용 (추가 30-50% 절약)
    """
    try:
        # 종목 코드 파싱 및 검증
        symbol_list = [s.strip() for s in symbols.split(",") if s.strip()]
        
        if not symbol_list:
            raise HTTPException(status_code=400, detail="최소 1개 이상의 종목 코드가 필요합니다")
        
        if len(symbol_list) > 20:
            raise HTTPException(status_code=400, detail="최대 20개까지의 종목만 조회 가능합니다")
        
        logger.info(f"여러 종목 차트 데이터 조회 시작: {symbol_list}")
        
        # 각 종목별로 차트 데이터 조회
        chart_results = {}
        failed_symbols = []
        
        for symbol in symbol_list:
            try:
                chart_data = await data_collector.get_chart_data(symbol, period, interval, compressed)
                chart_results[symbol] = {
                    "symbol": symbol,
                    "data": chart_data,
                    "status": "success"
                }
                logger.info(f"종목 {symbol} 차트 데이터 조회 성공")
            except Exception as e:
                logger.error(f"종목 {symbol} 차트 데이터 조회 실패: {e}")
                chart_results[symbol] = {
                    "symbol": symbol,
                    "data": None,
                    "status": "failed",
                    "error": str(e)
                }
                failed_symbols.append(symbol)
        
        response_data = {
            "symbols": symbol_list,
            "period": period,
            "interval": interval,
            "compressed": compressed,
            "gzip_enabled": gzip_enabled,
            "total_requested": len(symbol_list),
            "successful_count": len(symbol_list) - len(failed_symbols),
            "failed_count": len(failed_symbols),
            "failed_symbols": failed_symbols,
            "charts": chart_results,
            "status": "success" if len(failed_symbols) == 0 else "partial_success"
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
        logger.error(f"여러 종목 차트 데이터 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=f"여러 종목 차트 데이터 조회 실패: {str(e)}")


# ETF 데이터 라우터
etf_router = APIRouter()

@etf_router.get("/list")
async def get_etf_list(
    gzip_enabled: bool = Query(False, description="gzip 압축 사용 (더 작은 크기)"),
    data_collector: DataCollectorService = Depends(get_data_collector)
):
    """
    ETF 목록 조회 (항상 압축된 형태로 반환)
    
    - 압축된 배열 형태로 반환 (데이터 크기 50-70% 절약)
    - gzip_enabled=true: gzip 압축 적용 (추가 30-50% 절약)
    """
    try:
        etf_list = await data_collector.get_etf_list()
        
        # 항상 압축된 형태로 반환: 헤더와 데이터 배열 분리
        response_data = {
            "count": len(etf_list),
            "compressed": True,
            "gzip_enabled": gzip_enabled,
            "status": "success",
            "headers": ["code", "name"],
            "data": [
                [etf.get("code", ""), etf.get("name", "")]
                for etf in etf_list
            ]
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
        raise HTTPException(status_code=500, detail=f"ETF 목록 조회 실패: {str(e)}")

@etf_router.get("/components/{etf_code}")
async def get_etf_components(
    etf_code: str,
    gzip_enabled: bool = Query(False, description="gzip 압축 사용 (더 작은 크기)"),
    data_collector: DataCollectorService = Depends(get_data_collector)
):
    """
    ETF 구성종목 조회 (pykrx)
    
    - compressed=true: 표준 JSON 형태 (기본값)
    - compressed=true: 압축된 배열 형태 (데이터 크기 50-70% 절약)
    - gzip_enabled=true: gzip 압축 적용 (추가 30-50% 절약)
    """
    try:
        components = await data_collector.get_etf_components(etf_code)
        
        if components:
            # 압축된 형태로 반환: 헤더와 데이터 배열 분리
            response_data = {
                "etf_code": etf_code,
                "count": len(components),
                "compressed": True,
                "gzip_enabled": gzip_enabled,
                "status": "success",
                "headers": ["etf_code", "stock_code", "stock_name", "weight", "quantity", "market_value", "updated_date"],
                "data": [
                    [
                        component.get("etf_code", etf_code),
                        component.get("stock_code", ""),
                        component.get("stock_name", ""),
                        component.get("weight", 0),
                        component.get("quantity", 0),
                        component.get("market_value", 0),
                        component.get("updated_date", "")
                    ]
                    for component in components
                ]
            }
        else:
            # 표준 형태로 반환
            response_data = {
                "etf_code": etf_code,
                "components": components,
                "count": len(components),
                "compressed": False,
                "gzip_enabled": gzip_enabled,
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
    """ETF 구성종목 업데이트 수동 실행"""
    try:
        await data_collector.scheduler_service.trigger_etf_update_now()
        return {"message": "ETF 구성종목 업데이트가 시작되었습니다"}
    except Exception as e:
        logger.error(f"ETF 구성종목 업데이트 트리거 실패: {e}")
        raise HTTPException(status_code=500, detail=f"ETF 구성종목 업데이트 실패: {str(e)}")

@admin_router.post("/scheduler/trigger/today-chart")
async def trigger_today_chart_update(
    data_collector: DataCollectorService = Depends(get_data_collector)
):
    """스케줄러: 당일 차트 데이터 업데이트 즉시 실행"""
    try:
        await data_collector.scheduler_service.trigger_today_chart_update_now()
        return {"message": "당일 차트 데이터 업데이트 트리거 완료"}
    except Exception as e:
        logger.error(f"당일 차트 데이터 업데이트 트리거 실패: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"당일 차트 데이터 업데이트 트리거 실패: {str(e)}"
        )

@admin_router.post("/scheduler/trigger/today-supply")
async def trigger_today_supply_demand_update(
    data_collector: DataCollectorService = Depends(get_data_collector)
):
    """스케줄러: 당일 수급 데이터 업데이트 즉시 실행"""
    try:
        await data_collector.scheduler_service.trigger_today_supply_demand_update_now()
        return {"message": "당일 수급 데이터 업데이트 트리거 완료"}
    except Exception as e:
        logger.error(f"당일 수급 데이터 업데이트 트리거 실패: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"당일 수급 데이터 업데이트 트리거 실패: {str(e)}"
        )

@admin_router.post("/scheduler/trigger/adjustment-check")
async def trigger_adjustment_check(
    data_collector: DataCollectorService = Depends(get_data_collector)
):
    """수정주가 체크 수동 실행"""
    try:
        logger.info("수동 수정주가 체크 실행")
        await data_collector.scheduler_service.trigger_adjustment_check_now()
        return {
            "message": "수정주가 체크가 완료되었습니다"
        }
    except Exception as e:
        logger.error(f"수정주가 체크 트리거 실패: {e}")
        raise HTTPException(status_code=500, detail=f"수정주가 체크 실패: {str(e)}")

@admin_router.post("/scheduler/trigger/rs-update")
async def trigger_rs_update(
    data_collector: DataCollectorService = Depends(get_data_collector)
):
    """RS 데이터 업데이트 수동 실행"""
    try:
        logger.info("수동 RS 데이터 업데이트 실행")
        await data_collector.scheduler_service.trigger_rs_update_now()
        return {
            "message": "RS 데이터 업데이트가 완료되었습니다"
        }
    except Exception as e:
        logger.error(f"RS 데이터 업데이트 트리거 실패: {e}")
        raise HTTPException(status_code=500, detail=f"RS 데이터 업데이트 실패: {str(e)}")

@admin_router.get("/adjustment/stats")
async def get_adjustment_check_stats(
    data_collector: DataCollectorService = Depends(get_data_collector)
):
    """수정주가 체크 통계 조회"""
    try:
        stats = data_collector.get_adjustment_check_stats()
        return {
            "adjustment_stats": stats,
            "status": "success"
        }
    except Exception as e:
        logger.error(f"수정주가 체크 통계 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=f"수정주가 체크 통계 조회 실패: {str(e)}")

@admin_router.post("/adjustment/check")
async def check_adjustment_prices_for_stockai(
    batch_size: int = Query(100, description="배치 크기", ge=50, le=200),
    data_collector: DataCollectorService = Depends(get_data_collector)
):
    """stockai용 전종목 수정주가 체크 실행"""
    try:
        logger.info("stockai용 수정주가 체크 시작")
        result = await data_collector.check_adjustment_prices_for_stockai(batch_size=batch_size)
        return {
            "message": "수정주가 체크가 완료되었습니다",
            "result": result,
            "status": "success"
        }
    except Exception as e:
        logger.error(f"수정주가 체크 실패: {e}")
        raise HTTPException(status_code=500, detail=f"수정주가 체크 실패: {str(e)}")

@admin_router.post("/adjustment/cache/clear")
async def clear_adjustment_cache(
    days_to_keep: int = Query(30, description="보관할 일수", ge=1, le=90),
    data_collector: DataCollectorService = Depends(get_data_collector)
):
    """수정주가 캐시 정리"""
    try:
        data_collector.clear_old_adjustment_cache(days_to_keep=days_to_keep)
        return {
            "message": f"{days_to_keep}일 이전 수정주가 캐시가 정리되었습니다",
            "status": "success"
        }
    except Exception as e:
        logger.error(f"수정주가 캐시 정리 실패: {e}")
        raise HTTPException(status_code=500, detail=f"수정주가 캐시 정리 실패: {str(e)}")

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

# ===========================================
# 배치 수집 관련 API
# ===========================================

@admin_router.post("/batch/collect/today")
async def update_today_chart_data(
    batch_size: int = Query(100, description="배치 크기", ge=50, le=200),
    data_collector: DataCollectorService = Depends(get_data_collector)
):
    """
    당일 차트 데이터 업데이트 (ka10095 관심종목정보요청 사용)
    
    - 전종목의 당일 차트 데이터만 업데이트
    - 수정주가 정보가 메모리에 있으면 함께 저장
    - 배치 단위로 처리하여 API 제한 준수
    """
    try:
        result = await data_collector.update_today_chart_data(batch_size=batch_size)
        
        return {
            "success": True,
            "data": result,
            "message": result.get("message", "당일 차트 데이터 업데이트 완료")
        }
        
    except Exception as e:
        logger.error(f"당일 차트 데이터 업데이트 실패: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"당일 차트 데이터 업데이트 실패: {str(e)}"
        )

@admin_router.post("/batch/collect/today-supply")
async def update_today_supply_demand_data(
    batch_size: int = Query(50, description="배치 크기", ge=20, le=100),
    data_collector: DataCollectorService = Depends(get_data_collector)
):
    """
    당일 수급 데이터 업데이트
    
    - 전종목(stockai용)의 당일 수급 데이터만 업데이트
    - 배치 단위로 처리하여 API 제한 준수
    - 기존 데이터가 있으면 UPSERT로 업데이트
    """
    try:
        result = await data_collector.update_today_supply_demand_data(batch_size=batch_size)
        
        return {
            "success": True,
            "data": result,
            "message": result.get("message", "당일 수급 데이터 업데이트 완료")
        }
        
    except Exception as e:
        logger.error(f"당일 수급 데이터 업데이트 실패: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"당일 수급 데이터 업데이트 실패: {str(e)}"
        )

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

@admin_router.post("/batch/collect/chart/{symbol}")
async def collect_single_stock_chart_data(
    symbol: str,
    months_back: int = Query(24, description="수집할 개월 수", ge=1, le=60),
    force_update: bool = Query(False, description="기존 데이터 강제 업데이트 여부"),
    data_collector: DataCollectorService = Depends(get_data_collector)
):
    """
    특정 종목의 차트 데이터만 수집
    
    Args:
        symbol: 종목 코드 (예: 005930)
        months_back: 수집할 개월 수 (기본 24개월)
        force_update: 기존 데이터 강제 업데이트 여부 (기본 False)
    """
    try:
        logger.info(f"종목 {symbol} 차트 데이터 수집 시작: {months_back}개월, 강제업데이트={force_update}")
        
        # 날짜 범위 계산
        from datetime import datetime, timedelta
        end_date = datetime.now()
        start_date = end_date - timedelta(days=months_back * 30)
        start_date_str = start_date.strftime('%Y%m%d')
        end_date_str = end_date.strftime('%Y%m%d')
        
        # 키움 API에서 차트 데이터 조회
        if data_collector.settings.KIWOOM_APP_KEY != "test_api_key":
            chart_data = await data_collector.kiwoom_client.get_daily_chart_data(
                symbol, start_date_str, end_date_str
            )
        else:
            logger.warning(f"키움 API 키가 설정되지 않아 더미 데이터 사용")
            chart_data = []
        
        if not chart_data:
            return {
                "message": f"종목 {symbol}의 차트 데이터가 없습니다 (키움 API 응답 없음 또는 상장폐지/거래정지)",
                "symbol": symbol,
                "period": f"{start_date_str} ~ {end_date_str}",
                "total_records": 0,
                "api_calculated_records": 0,
                "calculation_coverage": "0/0",
                "months_back": months_back,
                "force_update": force_update,
                "status": "no_data"
            }
        
        # TimescaleDB에 저장할 데이터 변환
        from stockeasy.collector.schemas.timescale_schemas import StockPriceCreate, IntervalType
        
        def safe_float(value):
            """안전한 float 변환"""
            try:
                return float(value) if value and str(value).strip() else 0.0
            except (ValueError, TypeError):
                return 0.0
        
        def safe_int(value):
            """안전한 int 변환"""
            try:
                return int(value) if value and str(value).strip() else 0
            except (ValueError, TypeError):
                return 0
        
        stock_price_data = []
        for chart_item in chart_data:
            try:
                # 날짜 검증 및 파싱
                if not chart_item.date or not str(chart_item.date).strip():
                    logger.warning(f"빈 날짜 데이터 건너뜀 ({symbol})")
                    continue
                
                try:
                    chart_date = datetime.strptime(str(chart_item.date).strip(), '%Y%m%d')
                except ValueError as e:
                    logger.warning(f"날짜 파싱 실패 ({symbol}, {chart_item.date}): {e}")
                    continue
                
                # 가격 데이터 검증
                close_price = safe_float(chart_item.close)
                if close_price <= 0:
                    logger.debug(f"유효하지 않은 종가 데이터 건너뜀 ({symbol}, {chart_item.date}, 종가: {chart_item.close})")
                    continue
                
                # 키움 API에서 제공하는 계산값들 추출
                api_change_amount = safe_float(chart_item.change_amount) if hasattr(chart_item, 'change_amount') and chart_item.change_amount else None
                api_change_rate = safe_float(chart_item.change_rate) if hasattr(chart_item, 'change_rate') and chart_item.change_rate else None
                api_previous_close = safe_float(chart_item.previous_close) if hasattr(chart_item, 'previous_close') and chart_item.previous_close else None
                api_volume_change_percent = safe_float(chart_item.volume_change_percent) if hasattr(chart_item, 'volume_change_percent') and chart_item.volume_change_percent else None
                
                logger.debug(f"종목 {symbol} API 계산값: 변동금액={api_change_amount}, 변동률={api_change_rate}%, 전일종가={api_previous_close}, 거래량변동률={api_volume_change_percent}%")
                
                stock_price = StockPriceCreate(
                    time=chart_date,
                    symbol=symbol,
                    interval_type=IntervalType.ONE_DAY.value,
                    open=safe_float(chart_item.open),
                    high=safe_float(chart_item.high),
                    low=safe_float(chart_item.low),
                    close=close_price,
                    volume=safe_int(chart_item.volume),
                    trading_value=safe_int(chart_item.trading_value),
                    # 키움 API에서 제공하는 계산값들 활용
                    change_amount=api_change_amount,
                    price_change_percent=api_change_rate,
                    previous_close_price=api_previous_close,
                    volume_change_percent=api_volume_change_percent,
                    # updated_at 필드 추가 (UPSERT 시 갱신 보장)
                    updated_at=datetime.now()
                )
                stock_price_data.append(stock_price)
                
            except Exception as e:
                logger.warning(f"차트 데이터 변환 실패 ({symbol}, {getattr(chart_item, 'date', 'N/A')}): {e}")
                continue
        
        # TimescaleDB에 저장
        if stock_price_data:
            from stockeasy.collector.services.timescale_service import timescale_service
            
            if force_update:
                # 강제 업데이트시 기존 데이터 삭제 후 재생성
                await timescale_service.delete_stock_prices_by_symbol_period(
                    symbol, start_date, end_date
                )
            
            # 시간순으로 정렬하여 저장 (과거 → 현재)
            stock_price_data.sort(key=lambda x: x.time)
            
            # 거래량 변화량 계산 (전일 거래량과 비교)
            for i in range(1, len(stock_price_data)):
                current = stock_price_data[i]
                previous = stock_price_data[i-1]
                
                # 거래량 변화량 계산
                if previous.volume and previous.volume > 0:
                    volume_change = current.volume - previous.volume
                    current.volume_change = volume_change
                    
                    # 거래량 변화율이 API에서 제공되지 않는 경우 계산
                    if not current.volume_change_percent:
                        current.volume_change_percent = round((volume_change / previous.volume) * 100, 4) if previous.volume > 0 else 0
            
            await timescale_service.bulk_create_stock_prices_with_progress(
                stock_price_data,
                batch_size=1000
            )
            
            # 누락된 변동률 등 재계산 (개별 종목용)
            logger.info(f"종목 {symbol} 변동률 재계산 시작")
            await timescale_service.batch_calculate_for_new_data(
                symbols=[symbol],
                start_date=start_date
            )
            logger.info(f"종목 {symbol} 변동률 재계산 완료")
        
        # 키움 API 계산값 통계
        api_calculated_count = len([p for p in stock_price_data if p.change_amount is not None])
        
        return {
            "message": f"종목 {symbol} 차트 데이터 수집이 완료되었습니다",
            "symbol": symbol,
            "period": f"{start_date_str} ~ {end_date_str}",
            "total_records": len(stock_price_data),
            "api_calculated_records": api_calculated_count,
            "calculation_coverage": f"{api_calculated_count}/{len(stock_price_data)}" if stock_price_data else "0/0",
            "months_back": months_back,
            "force_update": force_update,
            "status": "success"
        }
        
    except Exception as e:
        logger.error(f"종목 {symbol} 차트 데이터 수집 실패: {e}")
        raise HTTPException(status_code=500, detail=f"종목 {symbol} 차트 데이터 수집 실패: {str(e)}")

@admin_router.post("/batch/collect/supply/{symbol}")
async def collect_single_stock_supply_data(
    symbol: str,
    months_back: int = Query(6, description="수집할 개월 수", ge=1, le=24),
    force_update: bool = Query(False, description="기존 데이터 강제 업데이트 여부"),
    data_collector: DataCollectorService = Depends(get_data_collector)
):
    """
    특정 종목의 수급 데이터만 수집
    
    Args:
        symbol: 종목 코드 (예: 005930)
        months_back: 수집할 개월 수 (기본 6개월)
        force_update: 기존 데이터 강제 업데이트 여부 (기본 False)
    """
    try:
        logger.info(f"종목 {symbol} 수급 데이터 수집 시작: {months_back}개월, 강제업데이트={force_update}")
        
        # 날짜 범위 계산
        from datetime import datetime, timedelta
        end_date = datetime.now()
        start_date = end_date - timedelta(days=months_back * 30)
        start_date_str = start_date.strftime('%Y%m%d')
        end_date_str = end_date.strftime('%Y%m%d')
        
        # 키움 API에서 수급 데이터 조회
        if data_collector.settings.KIWOOM_APP_KEY != "test_api_key":
            supply_data = await data_collector.kiwoom_client.get_daily_supply_demand_data(
                symbol, start_date_str, end_date_str
            )
        else:
            logger.warning(f"키움 API 키가 설정되지 않아 더미 데이터 사용")
            supply_data = []
        
        if not supply_data:
            return {
                "message": f"종목 {symbol}의 수급 데이터가 없습니다",
                "symbol": symbol,
                "period": f"{start_date_str} ~ {end_date_str}",
                "total_records": 0,
                "status": "success"
            }
        
        # TimescaleDB에 저장할 데이터 변환
        from stockeasy.collector.schemas.timescale_schemas import SupplyDemandCreate
        
        def safe_float_or_none(value):
            """안전한 float 변환 (None 허용)"""
            try:
                if value is None or str(value).strip() == '':
                    return None
                return float(value)
            except (ValueError, TypeError):
                return None
        
        def safe_int_or_none(value):
            """안전한 int 변환 (None 허용)"""
            try:
                if value is None or str(value).strip() == '':
                    return None
                return int(value)
            except (ValueError, TypeError):
                return None
        
        supply_demand_data = []
        for supply_item in supply_data:
            try:
                # 날짜 검증 및 파싱
                item_date = supply_item.get('date', '')
                if not item_date or not str(item_date).strip():
                    logger.warning(f"빈 날짜 데이터 건너뜀 ({symbol})")
                    continue
                
                try:
                    supply_date = datetime.strptime(str(item_date).strip(), '%Y%m%d')
                except ValueError as e:
                    logger.warning(f"날짜 파싱 실패 ({symbol}, {item_date}): {e}")
                    continue
                
                supply_demand = SupplyDemandCreate(
                    date=supply_date,
                    symbol=symbol,
                    current_price=safe_float_or_none(supply_item.get('current_price')),
                    price_change_sign=supply_item.get('price_change_sign'),
                    price_change=safe_float_or_none(supply_item.get('price_change')),
                    price_change_percent=safe_float_or_none(supply_item.get('price_change_percent')),
                    accumulated_volume=safe_int_or_none(supply_item.get('accumulated_volume')),
                    accumulated_value=safe_int_or_none(supply_item.get('accumulated_value')),
                    individual_investor=safe_int_or_none(supply_item.get('individual_investor')),
                    foreign_investor=safe_int_or_none(supply_item.get('foreign_investor')),
                    institution_total=safe_int_or_none(supply_item.get('institution_total')),
                    financial_investment=safe_int_or_none(supply_item.get('financial_investment')),
                    insurance=safe_int_or_none(supply_item.get('insurance')),
                    investment_trust=safe_int_or_none(supply_item.get('investment_trust')),
                    other_financial=safe_int_or_none(supply_item.get('other_financial')),
                    bank=safe_int_or_none(supply_item.get('bank')),
                    pension_fund=safe_int_or_none(supply_item.get('pension_fund')),
                    private_fund=safe_int_or_none(supply_item.get('private_fund')),
                    government=safe_int_or_none(supply_item.get('government')),
                    other_corporation=safe_int_or_none(supply_item.get('other_corporation')),
                    domestic_foreign=safe_int_or_none(supply_item.get('domestic_foreign'))
                )
                supply_demand_data.append(supply_demand)
                
            except Exception as e:
                logger.warning(f"수급 데이터 변환 실패 ({symbol}, {supply_item.get('date', 'N/A')}): {e}")
                continue
        
        # TimescaleDB에 저장
        if supply_demand_data:
            from stockeasy.collector.services.timescale_service import timescale_service
            
            if force_update:
                # 강제 업데이트시 기존 데이터 삭제 후 재생성
                await timescale_service.delete_supply_demand_by_symbol_period(
                    symbol, start_date, end_date
                )
            
            # 시간순으로 정렬하여 저장 (과거 → 현재)
            supply_demand_data.sort(key=lambda x: x.date)
            
            await timescale_service.bulk_create_supply_demand_with_progress(
                supply_demand_data,
                batch_size=1000
            )
        
        return {
            "message": f"종목 {symbol} 수급 데이터 수집이 완료되었습니다",
            "symbol": symbol,
            "period": f"{start_date_str} ~ {end_date_str}",
            "total_records": len(supply_demand_data),
            "months_back": months_back,
            "force_update": force_update,
            "status": "success"
        }
        
    except Exception as e:
        logger.error(f"종목 {symbol} 수급 데이터 수집 실패: {e}")
        raise HTTPException(status_code=500, detail=f"종목 {symbol} 수급 데이터 수집 실패: {str(e)}")

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

# ========================================
# ========================================
# RS(상대강도) 데이터 라우터
# ========================================

# RS 데이터 라우터
rs_router = APIRouter()

@rs_router.get("/list")
async def get_all_rs_data(
    compressed: bool = Query(False, description="압축된 형태로 반환 (대량 데이터용)"),
    gzip_enabled: bool = Query(False, description="gzip 압축 사용 (더 작은 크기)"),
    force_update: bool = Query(False, description="강제 업데이트 여부")
):
    """
    전체 종목의 RS(상대강도) 데이터 조회
    
    - compressed=false: 표준 JSON 형태 (기본값)
    - compressed=true: 압축된 배열 형태 (데이터 크기 50-70% 절약)
    - gzip_enabled=true: gzip 압축 적용 (추가 30-50% 절약)
    - force_update=true: 캐시 무시하고 구글 시트에서 최신 데이터 가져오기
    """
    try:
        from stockeasy.collector.services.rs_service import rs_service
        
        # RS 데이터 조회
        rs_data_list = await rs_service.get_all_rs_data(force_update=force_update)
        
        if compressed:
            # 압축된 형태로 응답
            response_data = await rs_service.create_compressed_response(rs_data_list)
        else:
            # 표준 형태로 응답
            response_data = await rs_service.create_standard_response(rs_data_list)
        
        # gzip 압축 적용
        if gzip_enabled:
            import json
            import gzip
            
            # JSON을 문자열로 변환 후 gzip 압축
            json_str = json.dumps(response_data.dict(), ensure_ascii=False, default=str)
            compressed_content = gzip.compress(json_str.encode('utf-8'))
            
            return Response(
                content=compressed_content,
                media_type="application/json",
                headers={
                    "Content-Encoding": "gzip",
                    "Content-Length": str(len(compressed_content))
                }
            )
        else:
            return response_data
            
    except Exception as e:
        logger.error(f"RS 데이터 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=f"RS 데이터 조회 실패: {str(e)}")

@rs_router.get("/multiple")
async def get_multiple_rs_data(
    codes: str = Query(..., description="종목 코드들 (쉼표로 구분, 예: 005930,000660,035420)"),
    compressed: bool = Query(False, description="압축된 형태로 반환"),
    gzip_enabled: bool = Query(False, description="gzip 압축 사용")
):
    """
    여러 종목의 RS(상대강도) 데이터 일괄 조회
    
    Args:
        codes: 쉼표로 구분된 종목코드들 (최대 50개)
        compressed: 압축된 형태로 반환 여부
        gzip_enabled: gzip 압축 사용 여부
    """
    try:
        from stockeasy.collector.services.rs_service import rs_service
        import json
        import gzip
        
        # 종목 코드 파싱 및 검증
        stock_codes = [code.strip() for code in codes.split(",") if code.strip()]
        
        if not stock_codes:
            raise HTTPException(status_code=400, detail="최소 1개 이상의 종목 코드가 필요합니다")
        
        if len(stock_codes) > 50:
            raise HTTPException(status_code=400, detail="최대 50개까지의 종목만 조회 가능합니다")
        
        logger.info(f"여러 종목 RS 데이터 조회 시작: {stock_codes}")
        
        # 여러 종목 RS 데이터 조회
        rs_results = await rs_service.get_multiple_rs_data(stock_codes)
        
        # 성공/실패 종목 분류
        successful_data = []
        failed_codes = []
        
        for code in stock_codes:
            if code in rs_results and rs_results[code] is not None:
                successful_data.append(rs_results[code])
            else:
                failed_codes.append(code)
        
        if compressed:
            # 압축된 형태로 응답
            response_data = {
                "total_requested": len(stock_codes),
                "successful_count": len(successful_data),
                "failed_count": len(failed_codes),
                "failed_codes": failed_codes,
                "compressed": True,
                "gzip_enabled": gzip_enabled,
                "headers": ["stock_code", "stock_name", "sector", "rs", "rs_1m", "rs_3m", "rs_6m", "mmt"],
                "data": [
                    [
                        rs_data.get("stock_code", ""),
                        rs_data.get("stock_name", ""),
                        rs_data.get("sector", ""),
                        rs_data.get("rs"),
                        rs_data.get("rs_1m"),
                        rs_data.get("rs_3m"),
                        rs_data.get("rs_6m"),
                        rs_data.get("mmt")
                    ]
                    for rs_data in successful_data
                ],
                "status": "success" if len(failed_codes) == 0 else "partial_success"
            }
        else:
            # 표준 형태로 응답
            response_data = {
                "total_requested": len(stock_codes),
                "successful_count": len(successful_data),
                "failed_count": len(failed_codes),
                "failed_codes": failed_codes,
                "compressed": False,
                "gzip_enabled": gzip_enabled,
                "data": successful_data,
                "status": "success" if len(failed_codes) == 0 else "partial_success"
            }
        
        if gzip_enabled:
            # JSON을 문자열로 변환 후 gzip 압축
            json_str = json.dumps(response_data, ensure_ascii=False, default=str)
            compressed_content = gzip.compress(json_str.encode('utf-8'))
            
            return Response(
                content=compressed_content,
                media_type="application/json",
                headers={
                    "Content-Encoding": "gzip",
                    "Content-Length": str(len(compressed_content))
                }
            )
        else:
            return response_data
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"여러 종목 RS 데이터 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=f"여러 종목 RS 데이터 조회 실패: {str(e)}")

@rs_router.get("/{stock_code}")
async def get_rs_data_by_code(
    stock_code: str
):
    """
    특정 종목의 RS(상대강도) 데이터 조회
    
    Args:
        stock_code: 종목코드 (예: 005930)
    """
    try:
        from stockeasy.collector.services.rs_service import rs_service
        from stockeasy.collector.schemas.rs_schemas import SingleRSDataResponse
        
        # 종목별 RS 데이터 조회
        rs_data = await rs_service.get_rs_data_by_code(stock_code)
        
        if rs_data is None:
            return SingleRSDataResponse(
                stock_code=stock_code,
                data=None,
                status="not_found",
                message=f"종목 {stock_code}의 RS 데이터를 찾을 수 없습니다"
            )
        
        return SingleRSDataResponse(
            stock_code=stock_code,
            data=rs_data,
            status="success",
            message="RS 데이터 조회 성공"
        )
        
    except Exception as e:
        logger.error(f"종목 {stock_code} RS 데이터 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=f"RS 데이터 조회 실패: {str(e)}")

@rs_router.post("/update")
async def update_rs_data(
    force_update: bool = Query(True, description="강제 업데이트 여부")
):
    """
    RS 데이터 수동 업데이트 (스케줄러 대신 사용 가능)
    
    - 구글 시트에서 최신 RS 데이터를 가져와서 캐시를 업데이트합니다
    - force_update=true: 캐시 무시하고 강제로 최신 데이터 가져오기
    """
    try:
        from stockeasy.collector.services.rs_service import rs_service
        from stockeasy.collector.schemas.rs_schemas import RSUpdateResponse
        
        # RS 데이터 업데이트 실행
        result = await rs_service.update_rs_data(force_update=force_update)
        
        return RSUpdateResponse(
            message=result["message"],
            updated_count=result["updated_count"],
            last_updated=result["last_updated"],
            status=result["status"]
        )
        
    except Exception as e:
        logger.error(f"RS 데이터 업데이트 실패: {e}")
        raise HTTPException(status_code=500, detail=f"RS 데이터 업데이트 실패: {str(e)}")

@rs_router.get("/stats/summary")
async def get_rs_data_stats():
    """
    RS 데이터 통계 및 상태 조회
    """
    try:
        from stockeasy.collector.services.rs_service import rs_service
        
        # 전체 데이터 조회 (캐시 사용)
        rs_data_list = await rs_service.get_all_rs_data(force_update=False)
        last_update = rs_service.get_last_update_time()
        
        # 통계 계산
        total_count = len(rs_data_list)
        rs_available_count = len([data for data in rs_data_list if data.rs is not None])
        rs_1m_available_count = len([data for data in rs_data_list if data.rs_1m is not None])
        sector_available_count = len([data for data in rs_data_list if data.sector is not None])
        
        return {
            "total_stocks": total_count,
            "rs_available": rs_available_count,
            "rs_1m_available": rs_1m_available_count,
            "sector_available": sector_available_count,
            "last_updated": last_update,
            "cache_status": "active" if rs_service._cache_data is not None else "empty",
            "status": "success"
        }
        
    except Exception as e:
        logger.error(f"RS 데이터 통계 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=f"RS 데이터 통계 조회 실패: {str(e)}")

# ========================================
# 업종 차트 관련 API (KOSPI, KOSDAQ)
# ========================================

@admin_router.post("/sector/collect/{sector_symbol}")
async def collect_sector_chart_data(
    sector_symbol: str,
    months_back: int = Query(24, description="수집할 개월 수", ge=1, le=60),
    force_update: bool = Query(False, description="기존 데이터 강제 업데이트 여부"),
    data_collector: DataCollectorService = Depends(get_data_collector)
):
    """
    업종 차트 데이터 수집 (KOSPI, KOSDAQ)
    
    Args:
        sector_symbol: 업종 심볼 (KOSPI, KOSDAQ)
        months_back: 수집할 개월 수 (기본 24개월)
        force_update: 기존 데이터 강제 업데이트 여부 (기본 False)
    """
    try:
        # 지원되는 업종 확인
        if sector_symbol.upper() not in ['KOSPI', 'KOSDAQ']:
            raise HTTPException(
                status_code=400, 
                detail="지원되지 않는 업종입니다. KOSPI 또는 KOSDAQ만 지원됩니다."
            )
        
        logger.info(f"업종 {sector_symbol} 차트 데이터 수집 시작: {months_back}개월, 강제업데이트={force_update}")
        
        result = await data_collector.collect_sector_chart_data(
            sector_symbol=sector_symbol.upper(),
            months_back=months_back,
            force_update=force_update
        )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"업종 {sector_symbol} 차트 데이터 수집 실패: {e}")
        raise HTTPException(status_code=500, detail=f"업종 {sector_symbol} 차트 데이터 수집 실패: {str(e)}")

@admin_router.post("/sector/collect/all")
async def collect_all_sector_chart_data(
    months_back: int = Query(24, description="수집할 개월 수", ge=1, le=60),
    force_update: bool = Query(False, description="기존 데이터 강제 업데이트 여부"),
    data_collector: DataCollectorService = Depends(get_data_collector)
):
    """
    전체 업종 차트 데이터 수집 (KOSPI, KOSDAQ)
    
    Args:
        months_back: 수집할 개월 수 (기본 24개월)
        force_update: 기존 데이터 강제 업데이트 여부 (기본 False)
    """
    try:
        logger.info(f"전체 업종 차트 데이터 수집 시작: {months_back}개월, 강제업데이트={force_update}")
        
        result = await data_collector.collect_all_sector_chart_data(
            months_back=months_back,
            force_update=force_update
        )
        
        return result
        
    except Exception as e:
        logger.error(f"전체 업종 차트 데이터 수집 실패: {e}")
        raise HTTPException(status_code=500, detail=f"전체 업종 차트 데이터 수집 실패: {str(e)}")

@stock_router.get("/sector/chart/{sector_symbol}")
async def get_sector_chart_data(
    sector_symbol: str,
    period: str = Query("1y", description="조회 기간 (1d, 1w, 1m, 3m, 6m, 1y, 2y, 5y)"),
    interval: str = Query("1d", description="간격 (1m, 5m, 15m, 30m, 1h, 1d, 1w, 1M)"),
    compressed: bool = Query(False, description="압축된 형태로 반환 (대량 데이터용)"),
    gzip_enabled: bool = Query(False, description="gzip 압축 사용 (더 작은 크기)"),
    data_collector: DataCollectorService = Depends(get_data_collector)
):
    """
    업종 차트 데이터 조회 (KOSPI, KOSDAQ)
    
    - compressed=false: 표준 JSON 형태 (기본값)
    - compressed=true: 압축된 배열 형태 (데이터 크기 50-70% 절약)
    - gzip_enabled=true: gzip 압축 적용 (추가 30-50% 절약)
    """
    try:
        # 지원되는 업종 확인
        if sector_symbol.upper() not in ['KOSPI', 'KOSDAQ']:
            raise HTTPException(
                status_code=400, 
                detail="지원되지 않는 업종입니다. KOSPI 또는 KOSDAQ만 지원됩니다."
            )
        
        # 기존 차트 데이터 조회 로직 재사용 (symbol을 업종 심볼로 전달)
        chart_data = await data_collector.get_chart_data(
            symbol=sector_symbol.upper(), 
            period=period, 
            interval=interval, 
            compressed=compressed
        )
        
        response_data = {
            "sector_symbol": sector_symbol.upper(),
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
                    "Content-Encoding": "gzip",
                    "Content-Length": str(len(compressed_content))
                }
            )
        else:
            return response_data
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"업종 {sector_symbol} 차트 데이터 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=f"업종 {sector_symbol} 차트 데이터 조회 실패: {str(e)}")

# ========================================
# 배치 계산 전용 엔드포인트
# ========================================

@admin_router.post("/batch/calculate/all")
async def batch_calculate_all_stocks(
    days_back: int = Query(30, description="계산할 일수", ge=1, le=1000),
    batch_size: int = Query(50, description="배치 크기", ge=5, le=200),
    data_collector: DataCollectorService = Depends(get_data_collector)
):
    """
    전종목 배치 계산 (변동률, 거래량 증감률, 전일종가 등)
    
    Args:
        days_back: 계산할 일수 (기본 30일)
        batch_size: 배치 크기 (기본 50)
    """
    try:
        logger.info(f"전종목 배치 계산 시작: {days_back}일, 배치크기={batch_size}")
        
        from stockeasy.collector.services.timescale_service import timescale_service
        
        # 전종목 심볼 리스트 가져오기
        stock_list = await data_collector.get_all_stock_list_for_stockai()
        symbols = [stock["code"] for stock in stock_list] if stock_list else None
        
        logger.info(f"전종목 배치 계산 대상: {len(symbols) if symbols else 0}개 종목")
        
        # 전종목 배치 계산 실행
        result = await timescale_service.batch_calculate_stock_price_changes(
            symbols=symbols,
            days_back=days_back,
            batch_size=batch_size
        )
        
        return {
            "message": "전종목 배치 계산이 완료되었습니다",
            "result": result,
            "status": "success"
        }
    except Exception as e:
        logger.error(f"전종목 배치 계산 실패: {e}")
        raise HTTPException(status_code=500, detail=f"전종목 배치 계산 실패: {str(e)}")

@admin_router.post("/batch/calculate/symbols")
async def batch_calculate_specific_symbols(
    symbols: str = Query(..., description="종목 코드들 (쉼표로 구분, 예: 005930,000660,035420)"),
    days_back: int = Query(30, description="계산할 일수", ge=1, le=365),
    batch_size: int = Query(20, description="배치 크기", ge=5, le=100),
    data_collector: DataCollectorService = Depends(get_data_collector)
):
    """
    특정 종목들 배치 계산
    
    Args:
        symbols: 쉼표로 구분된 종목코드들 (최대 100개)
        days_back: 계산할 일수 (기본 30일)
        batch_size: 배치 크기 (기본 20)
    """
    try:
        # 종목 코드 파싱 및 검증
        symbol_list = [s.strip() for s in symbols.split(",") if s.strip()]
        
        if not symbol_list:
            raise HTTPException(status_code=400, detail="최소 1개 이상의 종목 코드가 필요합니다")
        
        if len(symbol_list) > 100:
            raise HTTPException(status_code=400, detail="최대 100개까지의 종목만 계산 가능합니다")
        
        logger.info(f"특정 종목들 배치 계산 시작: {len(symbol_list)}개 종목, {days_back}일")
        
        from stockeasy.collector.services.timescale_service import timescale_service
        
        # 특정 종목들 배치 계산 실행
        result = await timescale_service.batch_calculate_stock_price_changes(
            symbols=symbol_list,
            days_back=days_back,
            batch_size=batch_size
        )
        
        return {
            "message": f"특정 종목들({len(symbol_list)}개) 배치 계산이 완료되었습니다",
            "symbols": symbol_list,
            "result": result,
            "status": "success"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"특정 종목들 배치 계산 실패: {e}")
        raise HTTPException(status_code=500, detail=f"특정 종목들 배치 계산 실패: {str(e)}")

@admin_router.post("/batch/calculate/{symbol}")
async def batch_calculate_single_symbol(
    symbol: str,
    days_back: int = Query(30, description="계산할 일수", ge=1, le=1000),
    data_collector: DataCollectorService = Depends(get_data_collector)
):
    """
    단일 종목 배치 계산
    
    Args:
        symbol: 종목 코드 (예: 005930)
        days_back: 계산할 일수 (기본 30일)
    """
    try:
        logger.info(f"종목 {symbol} 배치 계산 시작: {days_back}일")
        
        from stockeasy.collector.services.timescale_service import timescale_service
        
        # 단일 종목 배치 계산 실행
        result = await timescale_service.batch_calculate_stock_price_changes(
            symbols=[symbol],
            days_back=days_back,
            batch_size=1
        )
        
        return {
            "message": f"종목 {symbol} 배치 계산이 완료되었습니다",
            "symbol": symbol,
            "result": result,
            "status": "success"
        }
    except Exception as e:
        logger.error(f"종목 {symbol} 배치 계산 실패: {e}")
        raise HTTPException(status_code=500, detail=f"종목 {symbol} 배치 계산 실패: {str(e)}")

@admin_router.get("/batch/calculate/status")
async def get_batch_calculation_status():
    """배치 계산 상태 및 트리거 정보 조회"""
    try:
        from stockeasy.collector.services.timescale_service import timescale_service
        
        # 트리거 상태 확인
        trigger_status = await timescale_service.check_trigger_status()
        
        return {
            "trigger_status": trigger_status,
            "calculation_info": {
                "method": "API 호출 기반 배치 계산",
                "features": [
                    "기존 API 계산값 보존",
                    "NULL 값만 새로 계산", 
                    "COALESCE 함수로 안전한 업데이트",
                    "배치 단위 처리로 고성능"
                ]
            },
            "status": "success"
        }
    except Exception as e:
        logger.error(f"배치 계산 상태 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=f"배치 계산 상태 조회 실패: {str(e)}") 