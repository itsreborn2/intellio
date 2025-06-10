"""
데이터 수집 서비스
키움증권 API 연동 및 데이터 처리
"""
import asyncio
import csv
import os
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Any
from decimal import Decimal

from loguru import logger
from stockeasy.collector.core.config import get_settings
from stockeasy.collector.core.logger import LoggerMixin, LogContext
from stockeasy.collector.services.cache_manager import CacheManager
from stockeasy.collector.services.kiwoom_client import KiwoomAPIClient
from stockeasy.collector.services.etf_crawler import ETFCrawler
from stockeasy.collector.services.scheduler_service import SchedulerService
from stockeasy.collector.schemas.stock_schemas import (
    StockRealtimeCreate,
    ChartDataRequest,
    ChartDataResponse,
    ChartDataPoint,
    CompressedChartDataResponse,
    SupplyDemandResponse,
    CompressedSupplyDemandResponse
)
from stockeasy.collector.services.timescale_service import timescale_service
from stockeasy.collector.schemas.timescale_schemas import (
    StockPriceCreate,
    SupplyDemandCreate,
    IntervalType
)


class DataCollectorService(LoggerMixin):
    """데이터 수집 서비스"""
    
    def __init__(self, cache_manager: CacheManager):
        self.settings = get_settings()
        self.cache_manager = cache_manager
        
        # 외부 API 클라이언트
        self.kiwoom_client = KiwoomAPIClient()
        self.etf_crawler = ETFCrawler()
        
        # 스케줄러 서비스
        self.scheduler_service = SchedulerService(
            data_collector=self,
            cache_manager=cache_manager
        )
        
        self._initialized = False
        self._realtime_running = False
        self._collection_tasks = []
        
        # API 호출 제한 관리
        max_concurrent = getattr(self.settings, 'MAX_CONCURRENT_REQUESTS', 5)
        self._api_call_semaphore = asyncio.Semaphore(max_concurrent)
        self._last_api_call = {}
        
        # 통계
        self._stats = {
            "total_api_calls": 0,
            "successful_calls": 0,
            "failed_calls": 0,
            "last_update": None,
            "cached_symbols": 0,
            "kiwoom_stats": {},
            "etf_stats": {},
            "scheduler_stats": {}
        }
        
        # 수정주가 임시 메모리 저장소 추가
        self._adjustment_data_cache = {
            "last_check_date": None,  # 마지막 체크 날짜
            "adjusted_stocks": {},    # {종목코드: {adjustment_type, adjustment_ratio, adjustment_event, check_date}}
            "check_history": []       # 체크 이력 (최대 30일 보관)
        }
    
    async def initialize(self) -> None:
        """데이터 수집 서비스 초기화"""
        if self._initialized:
            return
        
        with LogContext(self.logger, "데이터 수집 서비스 초기화") as ctx:
            try:
                # 기본 종목 리스트 로드
                await self._load_initial_symbols()
                
                # ETF 목록 초기화
                await self._initialize_etf_data()
                
                # 스케줄러 서비스 시작
                await self.scheduler_service.start()
                
                self._initialized = True
                ctx.log_progress("데이터 수집 서비스 초기화 완료")
                
            except Exception as e:
                ctx.logger.error(f"데이터 수집 서비스 초기화 실패: {e}")
                raise
    
    async def shutdown(self) -> None:
        """서비스 종료"""
        with LogContext(self.logger, "데이터 수집 서비스 종료") as ctx:
            try:
                # 스케줄러 서비스 종료
                await self.scheduler_service.shutdown()
                
                # 실시간 수집 중지
                await self.stop_realtime_collection()
                
                # 실행 중인 태스크 취소
                for task in self._collection_tasks:
                    if not task.done():
                        task.cancel()
                        try:
                            await task
                        except asyncio.CancelledError:
                            pass
                
                # 외부 클라이언트 정리
                await self.kiwoom_client.close()
                
                ctx.log_progress("데이터 수집 서비스 종료 완료")
                
            except Exception as e:
                ctx.logger.error(f"데이터 수집 서비스 종료 중 오류: {e}")
    
    def is_healthy(self) -> bool:
        """서비스 상태 확인"""
        return self._initialized
    
    # ===========================================
    # 실시간 데이터 수집
    # ===========================================
    
    async def start_realtime_collection(self) -> None:
        """실시간 데이터 수집 시작"""
        if self._realtime_running:
            self.logger.warning("실시간 데이터 수집이 이미 실행 중입니다")
            return
        
        self.logger.info("실시간 데이터 수집 시작")
        self._realtime_running = True
        
        # 실시간 수집 태스크 시작
        task = asyncio.create_task(self._realtime_collection_loop())
        self._collection_tasks.append(task)
    
    async def stop_realtime_collection(self) -> None:
        """실시간 데이터 수집 중지"""
        if not self._realtime_running:
            return
        
        self.logger.info("실시간 데이터 수집 중지")
        self._realtime_running = False
        
        # 관련 태스크 취소
        for task in self._collection_tasks[:]:
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                self._collection_tasks.remove(task)
    
    async def _realtime_collection_loop(self) -> None:
        """실시간 데이터 수집 루프"""
        while self._realtime_running:
            try:
                # 키움 API에서 실시간 데이터 수집 (또는 더미 데이터)
                if self.settings.KIWOOM_APP_KEY != "test_api_key":
                    await self._collect_kiwoom_realtime_data()
                else:
                    await self._collect_dummy_realtime_data()
                
                await asyncio.sleep(self.settings.REALTIME_UPDATE_INTERVAL)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"실시간 데이터 수집 중 오류: {e}")
                await asyncio.sleep(5)  # 오류 시 5초 대기
    
    async def _collect_kiwoom_realtime_data(self) -> None:
        """키움 API에서 실시간 데이터 수집"""
        # 대표 종목들
        symbols = ["005930", "000660", "035420", "005380", "068270"]
        
        try:
            # 키움 API에서 종목 기본정보 조회
            stock_infos = await self.kiwoom_client.get_multiple_stock_info(symbols)
            
            realtime_data = {}
            for stock_info in stock_infos:
                symbol = stock_info.stk_cd
                
                # 더미 가격 데이터 (실제로는 다른 API로 실시간 가격 조회)
                base_price = 70000 if symbol == "005930" else 50000
                current_price = base_price + (hash(f"{symbol}{datetime.now().minute}") % 10000 - 5000)
                
                realtime_data[symbol] = {
                    "symbol": symbol,
                    "name": stock_info.stk_nm,
                    "current_price": current_price,
                    "change_amount": current_price - base_price,
                    "price_change_percent": round(((current_price - base_price) / base_price) * 100, 2),
                    "volume": hash(f"{symbol}{datetime.now().second}") % 1000000,
                    "trading_value": current_price * (hash(f"{symbol}{datetime.now().second}") % 1000000),
                    "last_update": datetime.now(),
                    "trade_time": datetime.now(),
                    "market": stock_info.mkt_gb,
                    "stock_type": stock_info.stk_gb
                }
            
            # 캐시에 저장
            await self.cache_manager.bulk_set_realtime_data(realtime_data)
            
            self._stats["last_update"] = datetime.now()
            self._stats["successful_calls"] += 1
            self.logger.debug(f"키움 API 실시간 데이터 업데이트: {len(realtime_data)}개 종목")
            
        except Exception as e:
            self._stats["failed_calls"] += 1
            self.logger.error(f"키움 API 실시간 데이터 수집 실패: {e}")
            # 실패 시 더미 데이터로 대체
            await self._collect_dummy_realtime_data()
    
    async def _collect_dummy_realtime_data(self) -> None:
        """더미 실시간 데이터 수집 (테스트용)"""
        # 대표 종목들의 더미 데이터
        dummy_symbols = ["005930", "000660", "035420", "005380", "068270"]
        
        realtime_data = {}
        for symbol in dummy_symbols:
            # 더미 데이터 생성
            base_price = 70000 if symbol == "005930" else 50000
            current_price = base_price + (hash(f"{symbol}{datetime.now().minute}") % 10000 - 5000)
            
            realtime_data[symbol] = {
                "symbol": symbol,
                "current_price": current_price,
                "change_amount": current_price - base_price,
                "price_change_percent": round(((current_price - base_price) / base_price) * 100, 2),
                "volume": hash(f"{symbol}{datetime.now().second}") % 1000000,
                "trading_value": current_price * (hash(f"{symbol}{datetime.now().second}") % 1000000),
                "last_update": datetime.now(),
                "trade_time": datetime.now()
            }
        
        # 캐시에 저장
        await self.cache_manager.bulk_set_realtime_data(realtime_data)
        
        self._stats["last_update"] = datetime.now()
        self.logger.debug(f"더미 실시간 데이터 업데이트: {len(realtime_data)}개 종목")
    
    # ===========================================
    # 데이터 조회 메서드
    # ===========================================
    
    async def get_realtime_price(self, symbol: str) -> Optional[Dict[str, Any]]:
        """실시간 가격 데이터 조회"""
        try:
            # 캐시에서 조회
            cached_data = await self.cache_manager.get_realtime_data(symbol)
            if cached_data:
                return cached_data
            
            # 캐시에 없으면 API에서 조회
            api_data = await self._fetch_realtime_price_from_api(symbol)
            if api_data:
                await self.cache_manager.set_realtime_data(symbol, api_data)
                return api_data
            
            return None
            
        except Exception as e:
            self.logger.error(f"실시간 가격 조회 실패 [{symbol}]: {e}")
            return None
    
    async def get_stock_info(self, symbol: str) -> Optional[Dict[str, Any]]:
        """개별 종목 기본정보 조회 (키움 API)"""
        try:
            # 키움 API에서 조회
            self.logger.info(f"[kiwoom] get_stock_info : {symbol}")
            if self.settings.KIWOOM_APP_KEY != "test_api_key":
                stock_info = await self.kiwoom_client.get_stock_info(symbol)
                if stock_info:
                    return {
                        "symbol": stock_info.stk_cd,
                        "name": stock_info.stk_nm,
                        "market": stock_info.mkt_gb,
                        "stock_type": stock_info.stk_gb,
                        "listing_date": stock_info.lst_dt,
                        "total_shares": stock_info.stk_cnt,
                        "par_value": stock_info.par_pr
                    }
            
            # 더미 데이터 반환
            return {
                "symbol": symbol,
                "name": f"종목_{symbol}",
                "market": "KOSPI",
                "stock_type": "ST",
                "listing_date": "20100101",
                "total_shares": "1000000000",
                "par_value": "500"
            }
            
        except Exception as e:
            self.logger.error(f"종목 기본정보 조회 실패 [{symbol}]: {e}")
            return None
    
    async def get_supply_demand_data(
        self, 
        symbol: str, 
        start_date: str,
        end_date: str = None,
        compressed: bool = False
    ) -> Optional[SupplyDemandResponse]:
        """수급 데이터 조회 (기간별, 실제 TimescaleDB에서 조회)"""
        try:
            from datetime import datetime, timedelta
            
            # end_date가 없으면 start_date와 동일하게 설정
            if not end_date:
                end_date = start_date
            
            # 문자열을 datetime으로 변환
            start_dt = datetime.strptime(start_date, '%Y%m%d')
            end_dt = datetime.strptime(end_date, '%Y%m%d')
            
            # TimescaleDB에서 수급 데이터 조회
            supply_demand_data = await timescale_service.get_supply_demand_data(
                symbol=symbol,
                start_date=start_dt,
                end_date=end_dt
            )
            
            if not supply_demand_data:
                self.logger.warning(f"수급 데이터 없음 [{symbol}, {start_date}~{end_date}]")
                return None
            
            # 종목명 조회
            symbol_name = await self.cache_manager.get_symbol_name(symbol) or "Unknown"
            
            # 압축 형태 요청 시
            if compressed:
                return await self._create_compressed_supply_demand_response(
                    supply_demand_data, symbol, symbol_name, start_date, end_date
                )
            
            # 기본 JSON 형태
            return await self._create_standard_supply_demand_response(
                supply_demand_data, symbol, symbol_name, start_date, end_date
            )
            
        except Exception as e:
            self.logger.error(f"수급 데이터 조회 실패 [{symbol}, {start_date}~{end_date}]: {e}")
            return None
    
    async def get_chart_data(
        self, 
        symbol: str, 
        period: str, 
        interval: str, 
        compressed: bool = False
    ) -> Optional[ChartDataResponse]:
        """차트 데이터 조회 (실제 TimescaleDB에서 조회)"""
        try:
            # period와 interval을 기반으로 날짜 범위 계산
            from datetime import datetime, timedelta
            
            end_date = datetime.now()
            
            # period에 따른 시작일 계산
            if period == "1d":
                start_date = end_date - timedelta(days=1)
            elif period == "1w":
                start_date = end_date - timedelta(weeks=1)
            elif period == "1m":
                start_date = end_date - timedelta(days=30)
            elif period == "3m":
                start_date = end_date - timedelta(days=90)
            elif period == "6m":
                start_date = end_date - timedelta(days=180)
            elif period == "1y":
                start_date = end_date - timedelta(days=365)
            elif period == "2y":
                start_date = end_date - timedelta(days=730)
            elif period == "5y":
                start_date = end_date - timedelta(days=1825)
            else:
                start_date = end_date - timedelta(days=30)  # 기본값: 1개월
            
            # interval을 IntervalType으로 변환
            interval_mapping = {
                "1m": IntervalType.ONE_MINUTE,
                "5m": IntervalType.FIVE_MINUTE,
                "15m": IntervalType.FIFTEEN_MINUTE,
                "30m": IntervalType.THIRTY_MINUTE,
                "1h": IntervalType.ONE_HOUR,
                "1d": IntervalType.ONE_DAY,
                "1w": IntervalType.ONE_WEEK,
                "1M": IntervalType.ONE_MONTH
            }
            interval_type = interval_mapping.get(interval, IntervalType.ONE_DAY)
            
            # TimescaleDB에서 캔들 데이터 조회
            candle_response = await timescale_service.get_candle_data(
                symbol=symbol,
                start_date=start_date,
                end_date=end_date,
                interval_type=interval_type
            )
            
            if not candle_response or not candle_response.data:
                self.logger.warning(f"차트 데이터 없음 [{symbol}, {period}, {interval}]")
                return None
            
            # 종목명 조회
            symbol_name = await self.cache_manager.get_symbol_name(symbol) or "Unknown"
            
            # 압축 형태 요청 시
            if compressed:
                return await self._create_compressed_chart_response(
                    candle_response, symbol, symbol_name, period, interval
                )
            
            # 기본 JSON 형태
            return await self._create_standard_chart_response(
                candle_response, symbol, symbol_name, period, interval
            )
            
        except Exception as e:
            self.logger.error(f"차트 데이터 조회 실패 [{symbol}, {period}, {interval}]: {e}")
            return None
    
    async def _create_standard_chart_response(
        self, 
        candle_response, 
        symbol: str, 
        symbol_name: str, 
        period: str, 
        interval: str
    ) -> ChartDataResponse:
        """표준 JSON 형태의 차트 응답 생성"""
        from datetime import timezone, timedelta
        
        korea_tz = timezone(timedelta(hours=9))  # UTC+9 한국 표준시
        
        chart_points = []
        for candle in candle_response.data:
            # UTC 시간을 한국 시간으로 변환
            korea_time = candle.time.replace(tzinfo=timezone.utc).astimezone(korea_tz)
            
            chart_points.append(ChartDataPoint(
                timestamp=korea_time,
                open=candle.open,
                high=candle.high,
                low=candle.low,
                close=candle.close,
                volume=candle.volume
            ))
        
        return ChartDataResponse(
            symbol=symbol,
            name=symbol_name,
            period=period,
            interval=interval,
            data=chart_points,
            total_count=len(chart_points)
        )
    
    async def _create_compressed_chart_response(
        self, 
        candle_response, 
        symbol: str, 
        symbol_name: str, 
        period: str, 
        interval: str
    ) -> CompressedChartDataResponse:
        """압축된 형태의 차트 응답 생성"""
        from datetime import timezone, timedelta
        
        korea_tz = timezone(timedelta(hours=9))  # UTC+9 한국 표준시
        
        # 스키마 정의
        schema = {
            "fields": ["timestamp", "open", "high", "low", "close", "volume"],
            "types": ["datetime", "decimal", "decimal", "decimal", "decimal", "integer"]
        }
        
        # 압축된 데이터 배열 생성
        compressed_data = []
        for candle in candle_response.data:
            # UTC 시간을 한국 시간으로 변환
            korea_time = candle.time.replace(tzinfo=timezone.utc).astimezone(korea_tz)
            
            compressed_data.append([
                korea_time.isoformat(),
                float(candle.open) if candle.open else None,
                float(candle.high) if candle.high else None,
                float(candle.low) if candle.low else None,
                float(candle.close) if candle.close else None,
                int(candle.volume) if candle.volume else None
            ])
        
        return CompressedChartDataResponse(
            symbol=symbol,
            name=symbol_name,
            period=period,
            interval=interval,
            schema=schema,
            data=compressed_data,
            total_count=len(compressed_data)
        )
    
    # ===========================================
    # ETF 관련 메서드
    # ===========================================
    
    async def get_etf_components(self, etf_code: str) -> List[Dict[str, Any]]:
        """ETF 구성종목 조회"""
        try:
            # 캐시에서 조회
            cached_components = await self.cache_manager.get_etf_components(etf_code)
            if cached_components:
                return cached_components
            
            # ETF 크롤러에서 조회
            components = await self.etf_crawler.get_etf_components(etf_code)
            
            # 캐시에 저장
            if components:
                component_dicts = [component.model_dump() for component in components]
                await self.cache_manager.set_etf_components(etf_code, component_dicts)
                return component_dicts
            
            return []
            
        except Exception as e:
            self.logger.error(f"ETF 구성종목 조회 실패 [{etf_code}]: {e}")
            return []
    
    async def refresh_etf_components(self, etf_code: str) -> None:
        """ETF 구성종목 갱신"""
        with LogContext(self.logger, f"ETF 구성종목 갱신: {etf_code}") as ctx:
            try:
                # 캐시 무효화
                await self.cache_manager.delete_cache_key(f"etf_components:{etf_code}")
                
                # 새로 조회
                components = await self.get_etf_components(etf_code)
                
                ctx.log_progress(f"ETF 구성종목 갱신 완료: {len(components)}개")
                
            except Exception as e:
                ctx.logger.error(f"ETF 구성종목 갱신 실패: {e}")
                raise
    
    async def update_all_etf_components(self) -> Dict[str, int]:
        """모든 주요 ETF 구성종목 업데이트"""
        try:
            # ETF 크롤러를 통해 업데이트
            results = await self.etf_crawler.update_all_etf_components()
            
            # 캐시 무효화 및 새로운 데이터 캐싱
            for etf_code, component_count in results.items():
                if component_count > 0:
                    await self.cache_manager.delete_cache_key(f"etf_components:{etf_code}")
                    # 새 데이터는 다음 조회 시 자동으로 캐싱됨
            
            self.logger.info(f"모든 ETF 구성종목 업데이트 완료: {len(results)}개 ETF")
            return results
            
        except Exception as e:
            self.logger.error(f"ETF 구성종목 업데이트 실패: {e}")
            return {}
    
    async def get_etf_list(self) -> List[Dict[str, str]]:
        """ETF 목록 조회"""
        try:
            # 주요 ETF 목록 반환
            major_etfs = self.etf_crawler.get_major_etf_list()
            return [{"code": code, "name": name} for code, name in major_etfs.items()]
            
        except Exception as e:
            self.logger.error(f"ETF 목록 조회 실패: {e}")
            return []
    
    # ===========================================
    # 내부 메서드 (API 호출, 더미 데이터 등)
    # ===========================================
    
    async def _load_initial_symbols(self) -> None:
        """초기 종목 리스트 로드"""
        # TODO: 실제 API에서 종목 리스트 조회
        dummy_symbols = {
            "005930": "삼성전자",
        }
        
        await self.cache_manager.bulk_set_symbol_mappings(dummy_symbols)
        self._stats["cached_symbols"] = len(dummy_symbols)
        
        self.logger.info(f"초기 종목 리스트 로드 완료: {len(dummy_symbols)}개")
    
    async def _fetch_realtime_price_from_api(self, symbol: str) -> Optional[Dict[str, Any]]:
        """API에서 실시간 가격 조회 (TODO: 실제 구현)"""
        async with self._api_call_semaphore:
            try:
                # API 호출 제한 체크
                await self._check_api_rate_limit()
                
                # TODO: 실제 키움 API 호출
                await self.cache_manager.increment_api_call_count("kiwoom")
                self._stats["total_api_calls"] += 1
                
                # 더미 데이터 반환
                base_price = 70000 if symbol == "005930" else 50000
                current_price = base_price + (hash(f"{symbol}{datetime.now().minute}") % 5000 - 2500)
                
                return {
                    "symbol": symbol,
                    "current_price": current_price,
                    "change_amount": current_price - base_price,
                    "price_change_percent": round(((current_price - base_price) / base_price) * 100, 2),
                    "volume": hash(f"{symbol}") % 1000000,
                    "last_update": datetime.now(),
                    "trade_time": datetime.now()
                }
                
            except Exception as e:
                self._stats["failed_calls"] += 1
                raise e
    
    async def _check_api_rate_limit(self) -> None:
        """API 호출 제한 체크"""
        now = datetime.now()
        
        # 초당 호출 제한
        current_second_calls = await self.cache_manager.get_api_call_count("kiwoom", "minute")
        if current_second_calls >= self.settings.MAX_API_CALLS_PER_SECOND:
            await asyncio.sleep(1)
        
        # 분당 호출 제한
        current_minute_calls = await self.cache_manager.get_api_call_count("kiwoom", "hour")
        if current_minute_calls >= self.settings.MAX_API_CALLS_PER_MINUTE:
            await asyncio.sleep(60)
    
    async def _initialize_etf_data(self) -> None:
        """ETF 목록 초기화"""
        try:
            # ETF 크롤러에서 주요 ETF 목록 로드
            major_etfs = self.etf_crawler.get_major_etf_list()
            
            # 캐시에 저장 (ETF 코드 -> 이름 매핑)
            await self.cache_manager.bulk_set_symbol_mappings(major_etfs)
            self._stats["cached_symbols"] += len(major_etfs)
            
            self.logger.info(f"초기 ETF 리스트 로드 완료: {len(major_etfs)}개")
            
        except Exception as e:
            self.logger.error(f"ETF 목록 초기화 실패: {e}")
    
    # ===========================================
    # 시장 데이터 메서드
    # ===========================================
    
    async def get_market_status(self) -> Dict[str, Any]:
        """시장 상태 조회"""
        try:
            # 캐시에서 조회
            cached_status = await self.cache_manager.get_market_status("KOSPI")
            if cached_status:
                return cached_status
            
            # TODO: 실제 API에서 시장 상태 조회
            current_time = datetime.now()
            is_weekend = current_time.weekday() >= 5
            is_market_hours = (
                current_time.hour >= 9 and 
                (current_time.hour < 15 or (current_time.hour == 15 and current_time.minute <= 30))
            )
            
            status = "closed"
            if not is_weekend and is_market_hours:
                status = "open"
            elif not is_weekend and current_time.hour < 9:
                status = "pre_market"
            elif not is_weekend and current_time.hour > 15:
                status = "after_market"
            
            market_status = {
                "market": "KOSPI",
                "status": status,
                "current_time": current_time.isoformat(),
                "market_open_time": "09:00",
                "market_close_time": "15:30",
                "is_trading_day": not is_weekend
            }
            
            # 캐시에 저장 (5분 TTL)
            await self.cache_manager.set_market_status("KOSPI", market_status, 300)
            
            return market_status
            
        except Exception as e:
            self.logger.error(f"시장 상태 조회 실패: {e}")
            return {}
    
    async def get_market_indices(self) -> List[Dict[str, Any]]:
        """주요 지수 조회"""
        try:
            # 캐시에서 먼저 조회
            cached_indices = await self.cache_manager.get_market_indices()
            if cached_indices and cached_indices.get('indices'):
                self.logger.info("캐시에서 시장 지수 정보 반환")
                return cached_indices['indices']
            
            # 키움 API에서 시장 지수 조회
            indices_list = []
            
            # 코스피(001)와 코스닥(101) 지수 조회
            market_codes = [
                {'code': '001', 'name': '코스피'},
                {'code': '101', 'name': '코스닥'}
            ]
            
            for market in market_codes:
                try:
                    # ka20003 API로 전업종지수 조회
                    market_data = await self.kiwoom_client.get_market_indices(market['code'])
                    
                    if market_data:
                        # 안전한 숫자 변환 함수
                        def safe_float(value, default=0.0):
                            try:
                                if value is None or value == '':
                                    return default
                                # +/- 기호와 쉼표 제거
                                clean_value = str(value).replace(',', '').replace('+', '').replace('-', '')
                                return float(clean_value) if clean_value else default
                            except (ValueError, TypeError):
                                return default
                        
                        def safe_int(value, default=0):
                            try:
                                if value is None or value == '':
                                    return default
                                # 쉼표 제거
                                clean_value = str(value).replace(',', '')
                                return int(clean_value) if clean_value else default
                            except (ValueError, TypeError):
                                return default
                        
                        # 전일대비 변동금액 (부호 유지)
                        change_amount_value = 0.0
                        if market_data.pred_pre:
                            try:
                                # +/- 부호 확인하고 부호 유지
                                pred_pre_str = str(market_data.pred_pre)
                                if pred_pre_str.startswith('-'):
                                    change_amount_value = -safe_float(pred_pre_str[1:])
                                elif pred_pre_str.startswith('+'):
                                    change_amount_value = safe_float(pred_pre_str[1:])
                                else:
                                    change_amount_value = safe_float(pred_pre_str)
                            except Exception:
                                change_amount_value = 0.0
                        
                        # 등락률 (부호 유지)
                        change_percent_value = 0.0
                        if market_data.flu_rt:
                            try:
                                flu_rt_str = str(market_data.flu_rt)
                                if flu_rt_str.startswith('-'):
                                    change_percent_value = -safe_float(flu_rt_str[1:])
                                elif flu_rt_str.startswith('+'):
                                    change_percent_value = safe_float(flu_rt_str[1:])
                                else:
                                    change_percent_value = safe_float(flu_rt_str)
                            except Exception:
                                change_percent_value = 0.0
                        
                        # 응답 데이터를 우리 형식으로 변환
                        index_info = {
                            'index_code': market_data.stk_cd,
                            'index_name': market_data.stk_nm,
                            'current_value': safe_float(market_data.cur_prc),
                            'change_amount': change_amount_value,
                            'price_change_percent': change_percent_value,
                            'trading_volume': safe_int(market_data.trde_qty),
                            'trading_value': safe_int(market_data.trde_prica),
                            'upper_limit_stocks': safe_int(market_data.upl),
                            'rising_stocks': safe_int(market_data.rising),
                            'unchanged_stocks': safe_int(market_data.stdns),
                            'falling_stocks': safe_int(market_data.fall),
                            'lower_limit_stocks': safe_int(market_data.lst),
                            'listed_stocks': safe_int(market_data.flo_stk_num),
                            'updated_at': datetime.now().isoformat()
                        }
                        indices_list.append(index_info)
                        self.logger.info(f"시장 지수 조회 성공: {market['name']} ({market_data.stk_cd})")
                    else:
                        self.logger.warning(f"시장 지수 데이터 없음: {market['name']} ({market['code']})")
                        
                except Exception as e:
                    self.logger.error(f"시장 지수 조회 실패 ({market['name']}): {e}")
                    continue
            
            if indices_list:
                # Redis에 15분 TTL로 저장
                cache_data = {
                    'indices': indices_list,
                    'cached_at': datetime.now().isoformat()
                }
                await self.cache_manager.set_market_indices(cache_data, ttl=900)  #15분, 30분(1800)
                self.logger.info(f"시장 지수 정보 Redis 저장 완료: {len(indices_list)}개")
                
                return indices_list
            else:
                self.logger.warning("시장 지수 조회 결과가 없습니다")
                return []
            
        except Exception as e:
            self.logger.error(f"지수 데이터 조회 실패: {e}")
            return []
    
    async def check_adjustment_prices_for_stockai(self, batch_size: int = 100) -> Dict[str, Any]:
        """stockai용 전종목 수정주가 체크"""
        try:
            from datetime import datetime, timedelta
            today = datetime.now().date()
            today_str = today.strftime('%Y%m%d')
            
            # 이미 오늘 체크했는지 확인
            last_check_date = self._adjustment_data_cache.get("last_check_date")
            if last_check_date == today_str:
                self.logger.info(f"오늘({today_str}) 수정주가 체크가 이미 완료됨")
                return self.get_adjustment_check_stats()
            
            # 전체 종목 리스트 가져오기
            stock_list = await self.get_all_stock_list_for_stockai()
            symbols = [stock["code"] for stock in stock_list] if stock_list else []
            
            if not symbols:
                raise ValueError("종목 리스트를 가져올 수 없습니다")
            
            total_stocks = len(symbols)
            adjusted_stocks = 0
            checked_stocks = 0
            errors = 0
            
            self.logger.info(f"수정주가 체크 시작: {total_stocks}개 종목")
            
            # 배치별로 처리
            for i in range(0, total_stocks, batch_size):
                batch_symbols = symbols[i:i + batch_size]
                
                for symbol in batch_symbols:
                    try:
                        # 키움 API에서 차트 데이터 조회 (최근 2일)
                        end_date = datetime.now()
                        start_date = end_date - timedelta(days=2)
                        end_date_str = end_date.strftime('%Y%m%d')
                        start_date_str = start_date.strftime('%Y%m%d')
                        
                        # 차트 데이터에서 수정주가 정보 확인
                        chart_data = await self.kiwoom_client.get_daily_chart_data(symbol, start_date_str, end_date_str)
                        
                        if chart_data:
                            # 수정주가 이벤트가 있는지 확인
                            for data_point in chart_data:
                                if hasattr(data_point, 'adjustment_type') and data_point.adjustment_type:
                                    adjustment_type = data_point.adjustment_type
                                    if adjustment_type and adjustment_type != '0':
                                        # 수정주가 정보 저장
                                        self._adjustment_data_cache["adjusted_stocks"][symbol] = {
                                            "date": data_point.date,
                                            "type": adjustment_type,
                                            "ratio": getattr(data_point, 'adjustment_ratio', ''),
                                            "event": getattr(data_point, 'adjustment_event', ''),
                                            "found_at": today.isoformat()
                                        }
                                        adjusted_stocks += 1
                                        self.logger.info(f"종목 {symbol}: 수정주가 발견 (타입: {adjustment_type})")
                                        break
                                        
                        if symbol not in self._adjustment_data_cache["adjusted_stocks"]:
                            self.logger.debug(f"종목 {symbol}: 수정주가 정보 없음")
                        
                        checked_stocks += 1
                        
                        # API 호출 제한 (초당 4.8회)
                        await asyncio.sleep(1.0 / 4.8)
                        
                    except Exception as e:
                        errors += 1
                        self.logger.error(f"종목 {symbol} 수정주가 체크 실패: {e}")
                        continue
                
                # 배치 완료 로그
                progress = min((i + batch_size) / total_stocks * 100, 100)
                self.logger.info(f"수정주가 체크 진행률: {progress:.1f}% ({checked_stocks}/{total_stocks})")
            
            # 체크 이력 저장
            check_result = {
                "check_date": today_str,
                "total_stocks": total_stocks,
                "checked_stocks": checked_stocks,
                "adjusted_stocks": adjusted_stocks,
                "errors": errors,
                "check_time": today.isoformat()
            }
            
            self._adjustment_data_cache["check_history"].append(check_result)
            self._adjustment_data_cache["last_check_date"] = today_str
            
            # 최대 30일 이력만 보관
            if len(self._adjustment_data_cache["check_history"]) > 30:
                self._adjustment_data_cache["check_history"] = self._adjustment_data_cache["check_history"][-30:]
            
            self.logger.info(f"수정주가 체크 완료: {adjusted_stocks}개 종목에서 수정주가 발견")
            
            return {
                "message": f"수정주가 체크 완료: {adjusted_stocks}개 종목에서 수정주가 발견",
                "total_stocks": total_stocks,
                "checked_stocks": checked_stocks,
                "adjusted_stocks": adjusted_stocks,
                "errors": errors,
                "status": "completed"
            }
            
        except Exception as e:
            self.logger.error(f"수정주가 체크 실패: {e}")
            return {
                "message": f"수정주가 체크 실패: {str(e)}",
                "total_stocks": 0,
                "checked_stocks": 0,
                "adjusted_stocks": 0,
                "errors": 1,
                "status": "failed"
            }
    
    def get_adjustment_check_stats(self) -> Dict[str, Any]:
        """수정주가 체크 통계 조회"""
        return {
            "last_check_date": self._adjustment_data_cache.get("last_check_date"),
            "total_adjusted_stocks": len(self._adjustment_data_cache["adjusted_stocks"]),
            "adjusted_stocks": dict(self._adjustment_data_cache["adjusted_stocks"]),
            "check_history": self._adjustment_data_cache["check_history"][-10:],  # 최근 10회만
            "cache_stats": {
                "total_cached_stocks": len(self._adjustment_data_cache["adjusted_stocks"]),
                "total_history_entries": len(self._adjustment_data_cache["check_history"])
            }
        }

    async def collect_sector_chart_data(
        self,
        sector_symbol: str,  # 'KOSPI' 또는 'KOSDAQ'
        months_back: int = 24,
        force_update: bool = False
    ) -> Dict[str, Any]:
        """
        업종 차트 데이터 수집 (KOSPI, KOSDAQ)
        
        Args:
            sector_symbol: 'KOSPI' 또는 'KOSDAQ'
            months_back: 수집할 개월 수 (기본 24개월)
            force_update: 기존 데이터 강제 업데이트 여부
        """
        try:
            # 업종 코드 매핑
            sector_code_map = {
                'KOSPI': '001',   # 종합(KOSPI)
                'KOSDAQ': '101'   # 종합(KOSDAQ)
            }
            
            if sector_symbol not in sector_code_map:
                raise ValueError(f"지원되지 않는 업종: {sector_symbol} (KOSPI, KOSDAQ만 지원)")
            
            sector_code = sector_code_map[sector_symbol]
            
            # 날짜 범위 계산
            from datetime import datetime, timedelta
            end_date = datetime.now()
            start_date = end_date - timedelta(days=months_back * 30)
            start_date_str = start_date.strftime('%Y%m%d')
            end_date_str = end_date.strftime('%Y%m%d')
            
            self.logger.info(f"업종 차트 데이터 수집 시작: {sector_symbol} ({sector_code}), {start_date_str} ~ {end_date_str}")
            
            # 키움 API에서 업종 차트 데이터 조회
            if self.settings.KIWOOM_APP_KEY != "test_api_key":
                sector_data = await self.kiwoom_client.get_sector_chart_data(
                    sector_code, start_date_str, end_date_str
                )
            else:
                self.logger.warning(f"키움 API 키가 설정되지 않아 더미 데이터 사용")
                sector_data = []
            
            if not sector_data:
                return {
                    "message": f"업종 {sector_symbol}의 차트 데이터가 없습니다",
                    "sector_symbol": sector_symbol,
                    "period": f"{start_date_str} ~ {end_date_str}",
                    "total_records": 0,
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
            
            def convert_sector_price(value):
                """
                업종 차트 가격 데이터 변환 (소수점 2자리 복원)
                예: 287185 -> 2871.85, 77120 -> 771.20
                
                Args:
                    value: 문자열 또는 숫자형 가격 데이터
                    
                Returns:
                    float: 소수점이 복원된 가격
                """
                try:
                    if value is None or str(value).strip() == '':
                        return 0.0
                    
                    # 문자열을 정수로 변환 후 100으로 나누어 소수점 복원
                    raw_value = str(value).strip()
                    if not raw_value.isdigit():
                        # 이미 소수점이 있는 경우는 그대로 사용
                        return float(raw_value)
                    
                    # 정수 형태인 경우 100으로 나누어 소수점 복원
                    integer_value = int(raw_value)
                    converted_value = integer_value / 100.0
                    
                    # 변환이 실제로 일어난 경우에만 로깅 (소수점 복원)
                    if integer_value >= 100:  # 실질적인 변환이 일어난 경우
                        self.logger.debug(f"업종 가격 변환: {raw_value} -> {converted_value}")
                    
                    return converted_value
                    
                except (ValueError, TypeError) as e:
                    self.logger.warning(f"업종 가격 변환 실패 ({value}): {e}")
                    return 0.0
            
            stock_price_data = []
            for sector_item in sector_data:
                try:
                    # 날짜 검증 및 파싱
                    if not sector_item.dt or not str(sector_item.dt).strip():
                        self.logger.warning(f"빈 날짜 데이터 건너뜀 ({sector_symbol})")
                        continue
                    
                    try:
                        chart_date = datetime.strptime(str(sector_item.dt).strip(), '%Y%m%d')
                    except ValueError as e:
                        self.logger.warning(f"날짜 파싱 실패 ({sector_symbol}, {sector_item.dt}): {e}")
                        continue
                    
                    # 업종 차트 가격 데이터 변환 (소수점 2자리 복원)
                    open_price = convert_sector_price(sector_item.open_pric)
                    high_price = convert_sector_price(sector_item.high_pric)
                    low_price = convert_sector_price(sector_item.low_pric)
                    close_price = convert_sector_price(sector_item.cur_prc)
                    previous_close = convert_sector_price(sector_item.pred_close_pric)
                    
                    # 가격 데이터 검증
                    if close_price <= 0:
                        self.logger.debug(f"유효하지 않은 종가 데이터 건너뜀 ({sector_symbol}, {sector_item.dt}, 원본 종가: {sector_item.cur_prc}, 변환 종가: {close_price})")
                        continue
                    
                    # 전일 종가 및 변동 계산
                    change_amount = None
                    change_rate = None
                    
                    if previous_close > 0 and close_price > 0:
                        change_amount = close_price - previous_close
                        change_rate = round((change_amount / previous_close) * 100, 4)
                    
                    # 업종 가격 변환 결과 로깅 (샘플링)
                    if len(stock_price_data) < 5:  # 처음 5개 데이터만 로깅
                        self.logger.info(f"업종 {sector_symbol} {sector_item.dt} 가격 변환 예시: 시가 {sector_item.open_pric}->{open_price}, 고가 {sector_item.high_pric}->{high_price}, 저가 {sector_item.low_pric}->{low_price}, 종가 {sector_item.cur_prc}->{close_price}")
                    
                    stock_price = StockPriceCreate(
                        time=chart_date,
                        symbol=sector_symbol,  # 'KOSPI' 또는 'KOSDAQ'으로 저장
                        interval_type=IntervalType.ONE_DAY.value,
                        open=open_price,
                        high=high_price,
                        low=low_price,
                        close=close_price,
                        volume=safe_int(sector_item.trde_qty),
                        trading_value=safe_int(sector_item.trde_prica),
                        change_amount=change_amount,
                        price_change_percent=change_rate,
                        previous_close_price=previous_close,
                        # 업종 분류 정보
                        major_industry_type=getattr(sector_item, 'bic_inds_tp', None),
                        minor_industry_type=getattr(sector_item, 'sm_inds_tp', None),
                        stock_info=getattr(sector_item, 'stk_infr', None)
                        # updated_at은 TimescaleService에서 자동 설정됨 (현재 UTC 시간)
                    )
                    stock_price_data.append(stock_price)
                    
                except Exception as e:
                    self.logger.warning(f"업종 차트 데이터 변환 실패 ({sector_symbol}, {getattr(sector_item, 'dt', 'N/A')}): {e}")
                    continue
            
            # TimescaleDB에 저장
            if stock_price_data:
                from stockeasy.collector.services.timescale_service import timescale_service
                
                if force_update:
                    # 강제 업데이트시 기존 데이터 삭제 후 재생성
                    await timescale_service.delete_stock_prices_by_symbol_period(
                        sector_symbol, start_date, end_date
                    )
                
                # 시간순으로 정렬하여 저장 (과거 → 현재)
                stock_price_data.sort(key=lambda x: x.time)
                
                # 업종 차트 데이터는 강제 UPSERT 사용 (가격 변환 보장)
                from stockeasy.collector.schemas.timescale_schemas import BulkStockPriceCreate
                
                await timescale_service.bulk_create_stock_prices_with_upsert(
                    BulkStockPriceCreate(prices=stock_price_data)
                )
                
                # 변동률 재계산 (업종 데이터용)
                self.logger.info(f"업종 {sector_symbol} 변동률 재계산 시작")
                await timescale_service.batch_calculate_for_new_data(
                    symbols=[sector_symbol],
                    start_date=start_date
                )
                self.logger.info(f"업종 {sector_symbol} 변동률 재계산 완료")
            
            # 변환된 가격 데이터 통계 (첫 번째와 마지막 데이터) 및 UPSERT 확인
            if stock_price_data:
                first_data = stock_price_data[0]
                last_data = stock_price_data[-1]
                self.logger.info(f"업종 {sector_symbol} 가격 변환 및 UPSERT 완료 - 첫째: {first_data.time.strftime('%Y-%m-%d')} 종가 {first_data.close}, 마지막: {last_data.time.strftime('%Y-%m-%d')} 종가 {last_data.close}, 총 {len(stock_price_data)}건")
                self.logger.info(f"업종 {sector_symbol} updated_at 필드 갱신됨: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            
            return {
                "message": f"업종 {sector_symbol} 차트 데이터 수집이 완료되었습니다",
                "sector_symbol": sector_symbol,
                "sector_code": sector_code,
                "period": f"{start_date_str} ~ {end_date_str}",
                "total_records": len(stock_price_data),
                "months_back": months_back,
                "force_update": force_update,
                "price_conversion": "소수점 2자리 복원 적용",
                "status": "success"
            }
            
        except Exception as e:
            self.logger.error(f"업종 {sector_symbol} 차트 데이터 수집 실패: {e}")
            return {
                "message": f"업종 {sector_symbol} 차트 데이터 수집 실패: {str(e)}",
                "sector_symbol": sector_symbol,
                "total_records": 0,
                "status": "failed"
            }

    async def collect_all_sector_chart_data(
        self,
        months_back: int = 24,
        force_update: bool = False
    ) -> Dict[str, Any]:
        """
        전체 업종 차트 데이터 수집 (KOSPI, KOSDAQ)
        
        Args:
            months_back: 수집할 개월 수 (기본 24개월)
            force_update: 기존 데이터 강제 업데이트 여부
        """
        try:
            self.logger.info(f"전체 업종 차트 데이터 수집 시작: {months_back}개월")
            
            sectors = ['KOSPI', 'KOSDAQ']
            results = {}
            
            for sector in sectors:
                self.logger.info(f"업종 {sector} 차트 데이터 수집 시작")
                
                result = await self.collect_sector_chart_data(
                    sector_symbol=sector,
                    months_back=months_back,
                    force_update=force_update
                )
                
                results[sector] = result
                
                # API 호출 간격 조절 (키움 API 제약)
                await asyncio.sleep(0.21)
            
            # 전체 결과 요약
            total_records = sum(result.get('total_records', 0) for result in results.values())
            success_count = len([r for r in results.values() if r.get('status') == 'success'])
            
            return {
                "message": f"전체 업종 차트 데이터 수집 완료: {success_count}/{len(sectors)}개 성공",
                "total_sectors": len(sectors),
                "successful_sectors": success_count,
                "total_records": total_records,
                "sector_results": results,
                "months_back": months_back,
                "force_update": force_update,
                "status": "success" if success_count == len(sectors) else "partial_success"
            }
            
        except Exception as e:
            self.logger.error(f"전체 업종 차트 데이터 수집 실패: {e}")
            return {
                "message": f"전체 업종 차트 데이터 수집 실패: {str(e)}",
                "total_sectors": 0,
                "successful_sectors": 0,
                "total_records": 0,
                "status": "failed"
            }

    async def _create_standard_supply_demand_response(
        self, 
        supply_demand_data, 
        symbol: str, 
        symbol_name: str, 
        start_date: str, 
        end_date: str
    ) -> SupplyDemandResponse:
        """표준 JSON 형태의 수급 응답 생성"""
        from datetime import timezone, timedelta
        from stockeasy.collector.schemas.stock_schemas import SupplyDemandDataPoint
        
        korea_tz = timezone(timedelta(hours=9))  # UTC+9 한국 표준시
        
        supply_demand_points = []
        for data in supply_demand_data:
            # UTC 시간을 한국 시간으로 변환
            korea_time = data.date.replace(tzinfo=timezone.utc).astimezone(korea_tz)
            
            supply_demand_points.append(SupplyDemandDataPoint(
                timestamp=korea_time,
                current_price=data.current_price,
                price_change_sign=data.price_change_sign,
                price_change=data.price_change,
                price_change_percent=data.price_change_percent,
                accumulated_volume=data.accumulated_volume,
                accumulated_value=data.accumulated_value,
                individual_investor=data.individual_investor,
                foreign_investor=data.foreign_investor,
                institution_total=data.institution_total,
                financial_investment=data.financial_investment,
                insurance=data.insurance,
                investment_trust=data.investment_trust,
                other_financial=data.other_financial,
                bank=data.bank,
                pension_fund=data.pension_fund,
                private_fund=data.private_fund,
                government=data.government,
                other_corporation=data.other_corporation,
                domestic_foreign=data.domestic_foreign
            ))
        
        return SupplyDemandResponse(
            symbol=symbol,
            name=symbol_name,
            start_date=start_date,
            end_date=end_date,
            data=supply_demand_points,
            total_count=len(supply_demand_points)
        )
    
    async def _create_compressed_supply_demand_response(
        self, 
        supply_demand_data, 
        symbol: str, 
        symbol_name: str, 
        start_date: str, 
        end_date: str
    ) -> CompressedSupplyDemandResponse:
        """압축된 형태의 수급 응답 생성"""
        from datetime import timezone, timedelta
        
        korea_tz = timezone(timedelta(hours=9))  # UTC+9 한국 표준시
        
        # 스키마 정의 (TimescaleDB SupplyDemand 모델 기반)
        schema = {
            "fields": [
                "timestamp", "current_price", "price_change_sign", "price_change", "price_change_percent",
                "accumulated_volume", "accumulated_value", "individual_investor", "foreign_investor", 
                "institution_total", "financial_investment", "insurance", "investment_trust", 
                "other_financial", "bank", "pension_fund", "private_fund", "government", 
                "other_corporation", "domestic_foreign"
            ],
            "types": [
                "datetime", "decimal", "string", "decimal", "decimal",
                "integer", "integer", "integer", "integer", 
                "integer", "integer", "integer", "integer", 
                "integer", "integer", "integer", "integer", "integer", 
                "integer", "integer"
            ]
        }
        
        # 압축된 데이터 배열 생성
        compressed_data = []
        for data in supply_demand_data:
            # UTC 시간을 한국 시간으로 변환
            korea_time = data.date.replace(tzinfo=timezone.utc).astimezone(korea_tz)
            
            compressed_data.append([
                korea_time.isoformat(),
                float(data.current_price) if data.current_price else None,
                data.price_change_sign,
                float(data.price_change) if data.price_change else None,
                float(data.price_change_percent) if data.price_change_percent else None,
                int(data.accumulated_volume) if data.accumulated_volume else None,
                int(data.accumulated_value) if data.accumulated_value else None,
                int(data.individual_investor) if data.individual_investor else None,
                int(data.foreign_investor) if data.foreign_investor else None,
                int(data.institution_total) if data.institution_total else None,
                int(data.financial_investment) if data.financial_investment else None,
                int(data.insurance) if data.insurance else None,
                int(data.investment_trust) if data.investment_trust else None,
                int(data.other_financial) if data.other_financial else None,
                int(data.bank) if data.bank else None,
                int(data.pension_fund) if data.pension_fund else None,
                int(data.private_fund) if data.private_fund else None,
                int(data.government) if data.government else None,
                int(data.other_corporation) if data.other_corporation else None,
                int(data.domestic_foreign) if data.domestic_foreign else None
            ])
        
        return CompressedSupplyDemandResponse(
            symbol=symbol,
            name=symbol_name,
            start_date=start_date,
            end_date=end_date,
            schema=schema,
            data=compressed_data,
            total_count=len(compressed_data)
        )
