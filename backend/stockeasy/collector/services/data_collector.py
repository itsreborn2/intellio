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
                component_dicts = [component.dict() for component in components]
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
            # TODO: 실제 API에서 지수 데이터 조회
            dummy_indices = [
                {
                    "index_code": "KOSPI",
                    "index_name": "코스피",
                    "current_value": 2580.0 + (hash(str(datetime.now().hour)) % 100 - 50),
                    "change_amount": 15.2 + (hash(str(datetime.now().minute)) % 20 - 10),
                    "price_change_percent": 0.59 + (hash(str(datetime.now().second)) % 200 - 100) / 100
                },
                {
                    "index_code": "KOSDAQ",
                    "index_name": "코스닥",
                    "current_value": 850.5 + (hash(str(datetime.now().hour)) % 50 - 25),
                    "change_amount": -8.3 + (hash(str(datetime.now().minute)) % 10 - 5),
                    "price_change_percent": -0.97 + (hash(str(datetime.now().second)) % 100 - 50) / 100
                }
            ]
            
            return dummy_indices
            
        except Exception as e:
            self.logger.error(f"지수 데이터 조회 실패: {e}")
            return []
    
    # ===========================================
    # 통계 및 관리
    # ===========================================
    
    async def get_collection_stats(self) -> Dict[str, Any]:
        """수집 통계 조회"""
        try:
            # 캐시 통계
            cache_stats = await self.cache_manager.get_cache_stats()
            
            # API 호출 통계
            api_stats = {}
            for window in ["minute", "hour", "day"]:
                api_stats[f"calls_per_{window}"] = await self.cache_manager.get_api_call_count("kiwoom", window)
            
            # 키움 API 통계
            kiwoom_stats = self.kiwoom_client.get_stats()
            
            # ETF 크롤러 통계
            etf_stats = self.etf_crawler.get_stats()
            
            # 스케줄러 통계
            scheduler_stats = self.scheduler_service.get_job_stats()
            
            return {
                "collection_stats": self._stats,
                "cache_stats": cache_stats,
                "api_stats": api_stats,
                "kiwoom_stats": kiwoom_stats,
                "etf_stats": etf_stats,
                "scheduler_stats": scheduler_stats,
                "realtime_status": {
                    "is_running": self._realtime_running,
                    "active_tasks": len([t for t in self._collection_tasks if not t.done()])
                }
            }
            
        except Exception as e:
            self.logger.error(f"통계 조회 실패: {e}")
            return {}
    
    async def update_symbol_mappings(self) -> Dict[str, int]:
        """종목 코드-이름 매핑 업데이트"""
        try:
            # 키움 API에서 종목 목록 조회 (실제 구현 시)
            if self.settings.KIWOOM_APP_KEY != "test_api_key":
                # TODO: 키움 API에서 전체 종목 목록 조회
                pass
            
            # 현재는 기본 종목만 업데이트
            await self._load_initial_symbols()
            
            # ETF 목록도 업데이트
            await self._initialize_etf_data()
            
            return {
                "updated_stocks": self._stats["cached_symbols"],
                "updated_etfs": len(self.etf_crawler.get_major_etf_list())
            }
            
        except Exception as e:
            self.logger.error(f"종목 매핑 업데이트 실패: {e}")
            return {}
    
    async def force_cache_refresh(self) -> None:
        """캐시 강제 갱신"""
        try:
            self.logger.info("캐시 강제 갱신 시작")
            
            # 실시간 데이터 캐시 클리어
            await self.cache_manager.clear_realtime_cache()
            
            # 종목 매핑 재로드
            await self.update_symbol_mappings()
            
            # ETF 구성종목 캐시 클리어
            for etf_code in self.etf_crawler.get_major_etf_list().keys():
                await self.cache_manager.delete_cache_key(f"etf_components:{etf_code}")
            
            self.logger.info("캐시 강제 갱신 완료")
            
        except Exception as e:
            self.logger.error(f"캐시 강제 갱신 실패: {e}")
            raise
    
    async def get_all_stock_list_for_stockai(self) -> List[Dict[str, str]]:
        """
        전체 종목 리스트 조회 (stock ai용)
        우선주, 각종 ETF, ETN등 제외
        
        Returns:
            List[Dict[str, str]]: [{"code": "005930", "name": "삼성전자"}, ...]
        """
        try:
            # 캐시에서 먼저 조회
            cached_list = await self.cache_manager.get_cache("all_stock_list_for_stockai")
            if cached_list:
                # 전체 종목 정보를 반환
                result = []
                for stock_info in cached_list.values():
                    result.append(stock_info)
                
                self.logger.info(f"캐시에서 종목 리스트 반환: {len(result)}개")
                return result
            
            # 캐시에 없으면 키움 API에서 조회 (Dict 형태로 받음)
            self.logger.info("캐시에 종목 리스트가 없어 키움 API에서 조회")
            stock_dict = await self.kiwoom_client.get_all_stock_list_for_stockai()
            
            # 키움 API에서 조회한 결과를 캐시에 저장 (Dict 형태 그대로)
            if stock_dict:
                # 캐시에 저장 (24시간 TTL)
                await self.cache_manager.set_cache(
                    "all_stock_list_for_stockai",
                    stock_dict,
                    ttl=86400  # 24시간
                )
                
                self.logger.info(f"키움 API에서 조회한 종목 리스트를 캐시에 저장: {len(stock_dict)}개")
                
                # List 형태로 변환해서 반환
                result = list(stock_dict.values())
                return result
            
            return []
            
        except Exception as e:
            self.logger.error(f"전체 종목 리스트 조회 실패: {e}")
            return []
        
    async def get_all_stock_list(self) -> List[Dict[str, str]]:
        """
        전체 종목 리스트 조회 (프론트엔드용)
        
        Returns:
            List[Dict[str, str]]: [{"code": "005930", "name": "삼성전자"}, ...]
        """
        try:
            # 캐시에서 먼저 조회
            cached_list = await self.cache_manager.get_cache("all_stock_list")
            if cached_list:
                # 전체 종목 정보를 반환
                result = []
                for stock_info in cached_list.values():
                    result.append(stock_info)
                
                self.logger.info(f"캐시에서 종목 리스트 반환: {len(result)}개")
                return result
            
            # 캐시에 없으면 키움 API에서 조회 (Dict 형태로 받음)
            self.logger.info("캐시에 종목 리스트가 없어 키움 API에서 조회")
            stock_dict = await self.kiwoom_client.get_all_stock_list()
            
            # 키움 API에서 조회한 결과를 캐시에 저장 (Dict 형태 그대로)
            if stock_dict:
                # 캐시에 저장 (24시간 TTL)
                await self.cache_manager.set_cache(
                    "all_stock_list",
                    stock_dict,
                    ttl=86400  # 24시간
                )
                
                self.logger.info(f"키움 API에서 조회한 종목 리스트를 캐시에 저장: {len(stock_dict)}개")
                
                # List 형태로 변환해서 반환
                result = list(stock_dict.values())
                return result
            
            return []
            
        except Exception as e:
            self.logger.error(f"전체 종목 리스트 조회 실패: {e}")
            return []
    
    async def get_stock_info_by_code(self, code: str) -> Optional[Dict[str, Any]]:
        """
        종목코드로 종목 정보 조회
        
        Args:
            code (str): 종목코드
            
        Returns:
            Optional[Dict[str, Any]]: 종목 정보 또는 None
        """
        try:
            # 캐시에서 먼저 조회
            cached_list = await self.cache_manager.get_cache("all_stock_list")
            if cached_list and code in cached_list:
                self.logger.info(f"캐시에서 종목 정보 조회: {cached_list[code]}")
                return cached_list[code]
            
            # 캐시에 없으면 개별 조회
            info = await self.get_stock_info(code)
            self.logger.info(f"get_stock_info_by_code: {info}")
            return info
            
        except Exception as e:
            self.logger.error(f"종목 정보 조회 실패 [{code}]: {e}")
            return None
    
    async def search_stocks_by_name(self, keyword: str, limit: int = 20) -> List[Dict[str, str]]:
        """
        종목명으로 종목 검색
        
        Args:
            keyword (str): 검색 키워드
            limit (int): 결과 제한 수
            
        Returns:
            List[Dict[str, str]]: 검색 결과
        """
        try:
            # 전체 종목 리스트에서 검색
            cached_list = await self.cache_manager.get_cache("all_stock_list")
            if not cached_list:
                # 캐시에 없으면 키움 API에서 조회
                all_stocks = await self.kiwoom_client.get_all_stock_list()
                cached_list = all_stocks
            
            # 키워드로 필터링
            results = []
            keyword_lower = keyword.lower()
            
            for stock_info in cached_list.values():
                if keyword_lower in stock_info["name"].lower():
                    results.append(stock_info)
                    
                    if len(results) >= limit:
                        break
            
            self.logger.info(f"종목 검색 결과: '{keyword}' -> {len(results)}개")
            return results
            
        except Exception as e:
            self.logger.error(f"종목 검색 실패 [{keyword}]: {e}")
            return []
    
    async def force_refresh_stock_list(self) -> Dict[str, int]:
        """
        종목 리스트 강제 새로고침
        
        Returns:
            Dict[str, int]: 업데이트 결과
        """
        try:
            self.logger.info("종목 리스트 강제 새로고침 시작")
            
            # 키움 API에서 강제 새로고침
            stock_list = await self.kiwoom_client.get_all_stock_list(force_refresh=True)
            
            # 캐시에 저장
            await self.cache_manager.set_cache(
                "all_stock_list", 
                stock_list, 
                ttl=86400  # 24시간
            )
            
            stock_list_for_stockai = await self.kiwoom_client.get_all_stock_list_for_stockai(force_refresh=True)
            # 캐시에 저장(stock ai)
            await self.cache_manager.set_cache(
                "all_stock_list_for_stockai", 
                stock_list_for_stockai, 
                ttl=86400  # 24시간
            )
            
            # CSV 파일로 저장
            await self._save_stock_list_to_csv(stock_list_for_stockai)
            
            self.logger.info(f"종목 리스트 강제 새로고침 완료: {len(stock_list)}개")
            self.logger.info(f"stock ai용 종목 리스트 강제 새로고침 완료: {len(stock_list_for_stockai)}개")
            
            return {
                "total_stocks": len(stock_list),
                "update_time": int(datetime.now().timestamp())
            }
            
        except Exception as e:
            self.logger.error(f"종목 리스트 강제 새로고침 실패: {e}")
            return {"total_stocks": 0, "update_time": 0}
    
    async def _save_stock_list_to_csv(self, stock_list_data: Dict[str, Dict[str, str]]) -> None:
        """
        종목 리스트를 CSV 파일로 저장
        
        Args:
            stock_list_data: 종목 리스트 데이터
        """
        try:
            # CSV 파일 저장 경로 설정
            csv_dir = "data/csv"
            os.makedirs(csv_dir, exist_ok=True)
            
            # 파일명에 타임스탬프 추가
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            csv_filename = f"stock_list_for_stockai_{timestamp}.csv"
            csv_filepath = os.path.join(csv_dir, csv_filename)
            
            # 최신 파일명도 생성 (덮어쓰기용)
            latest_csv_filepath = os.path.join(csv_dir, "stock_list_for_stockai_latest.csv")
            
            # 데이터를 리스트로 변환
            stock_list = list(stock_list_data.values())
            
            if not stock_list:
                self.logger.warning("저장할 종목 데이터가 없습니다")
                return
            
            # CSV 파일 작성
            with open(csv_filepath, 'w', newline='', encoding='utf-8-sig') as csvfile:
                # 첫 번째 항목의 키를 필드명으로 사용
                fieldnames = stock_list[0].keys()
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                
                # 헤더 작성
                writer.writeheader()
                
                # 데이터 작성
                writer.writerows(stock_list)
            
            # 최신 파일로도 복사
            with open(latest_csv_filepath, 'w', newline='', encoding='utf-8-sig') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(stock_list)
            
            self.logger.info(f"종목 리스트 CSV 파일 저장 완료: {csv_filepath}")
            self.logger.info(f"최신 종목 리스트 CSV 파일 저장 완료: {latest_csv_filepath}")
            self.logger.info(f"저장된 종목 수: {len(stock_list)}개")
            
        except Exception as e:
            self.logger.error(f"종목 리스트 CSV 파일 저장 실패: {e}")
            raise
    
    async def get_last_update_time(self, update_type: str) -> Optional[datetime]:
        """
        키움 API의 마지막 업데이트 시간 조회
        
        Args:
            update_type (str): 업데이트 유형 ("stockai" 또는 "stock")
            
        Returns:
            Optional[datetime]: 마지막 업데이트 시간 또는 None
        """
        try:
            if update_type == "stockai":
                return getattr(self.kiwoom_client, '_last_stockai_update', None)
            elif update_type == "stock":
                return getattr(self.kiwoom_client, '_last_stock_update', None)
            else:
                self.logger.warning(f"잘못된 update_type: {update_type}")
                return None
                
        except Exception as e:
            self.logger.error(f"마지막 업데이트 시간 조회 실패 [{update_type}]: {e}")
            return None
    
    async def get_all_last_update_times(self) -> Dict[str, Optional[datetime]]:
        """
        모든 마지막 업데이트 시간 조회
        
        Returns:
            Dict[str, Optional[datetime]]: 모든 업데이트 시간
        """
        try:
            return {
                "stockai_update": await self.get_last_update_time("stockai"),
                "stock_update": await self.get_last_update_time("stock")
            }
            
        except Exception as e:
            self.logger.error(f"모든 마지막 업데이트 시간 조회 실패: {e}")
            return {"stockai_update": None, "stock_update": None}
    
    # ===========================================
    # 대량 배치 수집 메서드
    # ===========================================
    
    async def collect_all_stock_chart_data(
        self,
        months_back: int = 24,
        batch_size: int = 50,
        progress_callback=None
    ) -> Dict[str, Any]:
        """
        전종목 일봉 차트 데이터 수집 (24개월)
        
        Args:
            months_back: 수집할 개월 수 (기본 24개월)
            batch_size: 배치 크기 (동시 처리할 종목 수)
            progress_callback: 진행상황 콜백 함수
            
        Returns:
            Dict: 수집 결과
        """
        with LogContext(self.logger, f"전종목 일봉 차트 데이터 수집 ({months_back}개월)") as ctx:
            try:
                # 전종목 리스트 조회
                all_stocks = await self.get_all_stock_list_for_stockai()
                
                if not all_stocks:
                    raise Exception("종목 리스트가 비어있습니다")
                
                # 날짜 계산
                from datetime import datetime, timedelta
                end_date = datetime.now()
                start_date = end_date - timedelta(days=months_back * 30)  # 대략 계산
                start_date_str = start_date.strftime('%Y%m%d')
                end_date_str = end_date.strftime('%Y%m%d')
                
                ctx.log_progress(f"수집 대상: {len(all_stocks)}개 종목")
                ctx.log_progress(f"기간: {start_date_str} ~ {end_date_str}")
                
                total_stocks = len(all_stocks)
                processed_stocks = 0
                success_stocks = 0
                error_stocks = 0
                total_records = 0
                
                # 배치 단위로 처리
                for i in range(0, total_stocks, batch_size):
                    batch_stocks = all_stocks[i:i + batch_size]
                    symbols = [stock["code"] for stock in batch_stocks]
                    
                    try:
                        # 키움 API에서 차트 데이터 조회
                        if self.settings.KIWOOM_APP_KEY != "test_api_key":
                            chart_data_dict = await self.kiwoom_client.get_multiple_chart_data(
                                symbols, start_date_str, end_date_str
                            )
                        else:
                            ctx.logger.warning(f"키움 API 키가 설정되지 않아 배치 {i//batch_size + 1} 건너뜀")
                            continue
                        
                        # TimescaleDB 저장용 데이터 변환
                        stock_price_data = []
                        for symbol, chart_data in chart_data_dict.items():
                            for chart_item in chart_data:
                                try:
                                    stock_price = StockPriceCreate(
                                        time=datetime.strptime(chart_item.date, '%Y%m%d') if hasattr(chart_item, 'date') else datetime.now(),
                                        symbol=symbol,
                                        interval_type=IntervalType.ONE_DAY.value,
                                        open=float(chart_item.open or 0) if hasattr(chart_item, 'open') else 0.0,
                                        high=float(chart_item.high or 0) if hasattr(chart_item, 'high') else 0.0,
                                        low=float(chart_item.low or 0) if hasattr(chart_item, 'low') else 0.0,
                                        close=float(chart_item.close or 0) if hasattr(chart_item, 'close') else 0.0,
                                        volume=int(chart_item.volume or 0) if hasattr(chart_item, 'volume') else 0,
                                        trading_value=int(chart_item.trading_value or 0) if hasattr(chart_item, 'trading_value') else 0
                                    )
                                    stock_price_data.append(stock_price)
                                except Exception as e:
                                    ctx.logger.warning(f"차트 데이터 변환 실패 ({symbol}): {e}")
                                    continue
                        
                                                # TimescaleDB에 저장 (트리거 없음 - 순수 고속 삽입)
                        if stock_price_data:
                            # 1단계: 원본 데이터 고속 삽입 (트리거 완전 제거됨)
                            await timescale_service.bulk_create_stock_prices_with_progress(
                                stock_price_data,
                                batch_size=2000,  # 트리거 없음으로 큰 배치 크기 가능
                                progress_callback=None
                            )
                            total_records += len(stock_price_data)
                            
                            # 2단계: 변동률 등 배치 계산 (새로 삽입된 데이터만)
                            batch_symbols = list(set([price.symbol for price in stock_price_data]))
                            try:
                                calc_result = await timescale_service.batch_calculate_for_new_data(
                                    symbols=batch_symbols
                                )
                                ctx.logger.info(f"배치 계산 완료: {calc_result.get('total_updated', 0)}건 업데이트")
                            except Exception as e:
                                ctx.logger.warning(f"배치 계산 실패 (데이터는 정상 저장됨): {e}")
                        
                        success_stocks += len([s for s in symbols if s in chart_data_dict and chart_data_dict[s]])
                        
                    except Exception as e:
                        ctx.logger.error(f"배치 처리 실패 (배치 {i//batch_size + 1}): {e}")
                        error_stocks += len(symbols)
                    
                    processed_stocks += len(symbols)
                    
                    # 진행상황 알림
                    if progress_callback:
                        progress = (processed_stocks / total_stocks) * 100
                        await progress_callback(
                            processed_stocks, total_stocks, progress, 
                            success_stocks, error_stocks, total_records
                        )
                    
                    ctx.log_progress(f"진행상황: {processed_stocks}/{total_stocks} 종목 처리 완료")
                    
                    # 배치 간 추가 대기 (API 제한 준수)
                    await asyncio.sleep(0.5)
                
                result = {
                    "success": True,
                    "total_stocks": total_stocks,
                    "success_stocks": success_stocks,
                    "error_stocks": error_stocks,
                    "total_records": total_records,
                    "start_date": start_date_str,
                    "end_date": end_date_str,
                    "message": f"전종목 차트 데이터 수집 완료: {success_stocks}/{total_stocks} 종목, {total_records}건"
                }
                
                ctx.log_progress(f"전종목 차트 데이터 수집 완료: {success_stocks}/{total_stocks} 종목, {total_records}건")
                return result
                
            except Exception as e:
                ctx.logger.error(f"전종목 차트 데이터 수집 실패: {e}")
                raise

    async def collect_all_supply_demand_data(
        self,
        months_back: int = 6,
        batch_size: int = 20,
        progress_callback=None
    ) -> Dict[str, Any]:
        """
        전종목 수급 데이터 수집 (6개월)
        
        Args:
            months_back: 수집할 개월 수 (기본 6개월)
            batch_size: 배치 크기 (동시 처리할 종목 수)
            progress_callback: 진행상황 콜백 함수
            
        Returns:
            Dict: 수집 결과
        """
        with LogContext(self.logger, f"전종목 수급 데이터 수집 ({months_back}개월)") as ctx:
            try:
                # 전종목 리스트 조회
                all_stocks = await self.get_all_stock_list_for_stockai()
                
                if not all_stocks:
                    raise Exception("종목 리스트가 비어있습니다")
                
                # 날짜 계산
                from datetime import datetime, timedelta
                end_date = datetime.now()
                start_date = end_date - timedelta(days=months_back * 30)  # 대략 계산
                start_date_str = start_date.strftime('%Y%m%d')
                end_date_str = end_date.strftime('%Y%m%d')
                
                ctx.log_progress(f"수집 대상: {len(all_stocks)}개 종목")
                ctx.log_progress(f"기간: {start_date_str} ~ {end_date_str}")
                
                total_stocks = len(all_stocks)
                processed_stocks = 0
                success_stocks = 0
                error_stocks = 0
                total_records = 0
                
                # 배치 단위로 처리 (수급 데이터는 더 작은 배치로)
                for i in range(0, total_stocks, batch_size):
                    batch_stocks = all_stocks[i:i + batch_size]
                    symbols = [stock["code"] for stock in batch_stocks]
                    
                    try:
                        # 키움 API에서 수급 데이터 조회
                        if self.settings.KIWOOM_APP_KEY != "test_api_key":
                            supply_data_dict = await self.kiwoom_client.get_multiple_supply_demand_data(
                                symbols, start_date_str, end_date_str
                            )
                        else:
                            ctx.logger.warning(f"키움 API 키가 설정되지 않아 배치 {i//batch_size + 1} 건너뜀")
                            continue
                        
                        # TimescaleDB 저장용 데이터 변환
                        supply_demand_data = []
                        for symbol, supply_data in supply_data_dict.items():
                            for supply_item in supply_data:
                                try:
                                    supply_demand = SupplyDemandCreate(
                                        date=datetime.strptime(supply_item['date'], '%Y%m%d'),
                                        symbol=symbol,
                                        current_price=float(supply_item.get('current_price', 0)) if supply_item.get('current_price') else None,
                                        price_change_sign=supply_item.get('price_change_sign'),
                                        price_change=float(supply_item.get('price_change', 0)) if supply_item.get('price_change') else None,
                                        price_change_percent=float(supply_item.get('price_change_percent', 0)) if supply_item.get('price_change_percent') else None,
                                        accumulated_volume=int(supply_item.get('accumulated_volume', 0)) if supply_item.get('accumulated_volume') else None,
                                        accumulated_value=int(supply_item.get('accumulated_value', 0)) if supply_item.get('accumulated_value') else None,
                                        individual_investor=int(supply_item.get('individual_investor', 0)) if supply_item.get('individual_investor') else None,
                                        foreign_investor=int(supply_item.get('foreign_investor', 0)) if supply_item.get('foreign_investor') else None,
                                        institution_total=int(supply_item.get('institution_total', 0)) if supply_item.get('institution_total') else None,
                                        financial_investment=int(supply_item.get('financial_investment', 0)) if supply_item.get('financial_investment') else None,
                                        insurance=int(supply_item.get('insurance', 0)) if supply_item.get('insurance') else None,
                                        investment_trust=int(supply_item.get('investment_trust', 0)) if supply_item.get('investment_trust') else None,
                                        other_financial=int(supply_item.get('other_financial', 0)) if supply_item.get('other_financial') else None,
                                        bank=int(supply_item.get('bank', 0)) if supply_item.get('bank') else None,
                                        pension_fund=int(supply_item.get('pension_fund', 0)) if supply_item.get('pension_fund') else None,
                                        private_fund=int(supply_item.get('private_fund', 0)) if supply_item.get('private_fund') else None,
                                        government=int(supply_item.get('government', 0)) if supply_item.get('government') else None,
                                        other_corporation=int(supply_item.get('other_corporation', 0)) if supply_item.get('other_corporation') else None,
                                        domestic_foreign=int(supply_item.get('domestic_foreign', 0)) if supply_item.get('domestic_foreign') else None
                                    )
                                    supply_demand_data.append(supply_demand)
                                except Exception as e:
                                    ctx.logger.warning(f"수급 데이터 변환 실패 ({symbol}): {e}")
                                    continue
                        
                        # TimescaleDB에 저장
                        if supply_demand_data:
                            await timescale_service.bulk_create_supply_demand_with_progress(
                                supply_demand_data,
                                batch_size=500,
                                progress_callback=None
                            )
                            total_records += len(supply_demand_data)
                        else:
                            ctx.logger.info(f"수급 데이터 없음: {symbols}")
                        
                        success_stocks += len([s for s in symbols if s in supply_data_dict and supply_data_dict[s]])
                        
                    except Exception as e:
                        ctx.logger.error(f"배치 처리 실패 (배치 {i//batch_size + 1}): {e}")
                        error_stocks += len(symbols)
                    
                    processed_stocks += len(symbols)
                    
                    # 진행상황 알림
                    if progress_callback:
                        progress = (processed_stocks / total_stocks) * 100
                        await progress_callback(
                            processed_stocks, total_stocks, progress, 
                            success_stocks, error_stocks, total_records
                        )
                    
                    ctx.log_progress(f"진행상황: {processed_stocks}/{total_stocks} 종목 처리 완료")
                    
                    # 배치 간 추가 대기 (API 제한 준수)
                    await asyncio.sleep(1.0)
                
                result = {
                    "success": True,
                    "total_stocks": total_stocks,
                    "success_stocks": success_stocks,
                    "error_stocks": error_stocks,
                    "total_records": total_records,
                    "start_date": start_date_str,
                    "end_date": end_date_str,
                    "message": f"전종목 수급 데이터 수집 완료: {success_stocks}/{total_stocks} 종목, {total_records}건"
                }
                
                ctx.log_progress(f"전종목 수급 데이터 수집 완료: {success_stocks}/{total_stocks} 종목, {total_records}건")
                return result
                
            except Exception as e:
                ctx.logger.error(f"전종목 수급 데이터 수집 실패: {e}")
                raise

    async def _generate_dummy_supply_data_for_symbols(
        self, 
        symbols: List[str], 
        start_date: datetime, 
        end_date: datetime
    ) -> Dict[str, List[Dict[str, Any]]]:
        """종목별 더미 수급 데이터 생성"""
        dummy_data = {}
        
        for symbol in symbols:
            supply_data = []
            current_date = start_date
            
            while current_date <= end_date:
                # 주말 제외
                if current_date.weekday() < 5:
                    date_str = current_date.strftime('%Y%m%d')
                    
                    supply_item = {
                        'date': date_str,
                        'symbol': symbol,
                        'current_price': 50000 + (hash(f"{symbol}{date_str}") % 50000),
                        'price_change_sign': '+' if hash(f"{symbol}{date_str}sign") % 2 else '-',
                        'price_change': hash(f"{symbol}{date_str}change") % 5000,
                        'price_change_percent': (hash(f"{symbol}{date_str}percent") % 1000) / 100,
                        'accumulated_volume': hash(f"{symbol}{date_str}vol") % 10000000,
                        'accumulated_value': hash(f"{symbol}{date_str}value") % 1000000000000,
                        'individual_investor': hash(f"{symbol}{date_str}individual") % 1000000000,
                        'foreign_investor': hash(f"{symbol}{date_str}foreign") % 1000000000,
                        'institution_total': hash(f"{symbol}{date_str}institution") % 1000000000,
                        'financial_investment': hash(f"{symbol}{date_str}financial") % 500000000,
                        'insurance': hash(f"{symbol}{date_str}insurance") % 100000000,
                        'investment_trust': hash(f"{symbol}{date_str}trust") % 300000000,
                        'other_financial': hash(f"{symbol}{date_str}other") % 100000000,
                        'bank': hash(f"{symbol}{date_str}bank") % 50000000,
                        'pension_fund': hash(f"{symbol}{date_str}pension") % 200000000,
                        'private_fund': hash(f"{symbol}{date_str}private") % 150000000,
                        'government': hash(f"{symbol}{date_str}government") % 50000000,
                        'other_corporation': hash(f"{symbol}{date_str}corp") % 100000000,
                        'domestic_foreign': hash(f"{symbol}{date_str}domestic") % 500000000
                    }
                    
                    supply_data.append(supply_item)
                
                current_date += timedelta(days=1)
            
            dummy_data[symbol] = supply_data
        
        return dummy_data

    async def get_batch_collection_status(self) -> Dict[str, Any]:
        """배치 수집 상태 조회"""
        try:
            # TimescaleDB 통계 조회
            timescale_stats = await timescale_service.get_statistics()
            
            # 종목별 데이터 건수 조회
            stock_price_counts = await timescale_service.get_data_count_by_symbol("stock_prices")
            supply_demand_counts = await timescale_service.get_data_count_by_symbol("supply_demand")
            
            return {
                "timescale_stats": timescale_stats,
                "stock_price_counts": stock_price_counts,
                "supply_demand_counts": supply_demand_counts,
                "last_update": datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"배치 수집 상태 조회 실패: {e}")
            return {}

    async def start_batch_collection_job(
        self,
        collect_chart_data: bool = True,
        collect_supply_data: bool = True,
        chart_months: int = 24,
        supply_months: int = 6
    ) -> Dict[str, Any]:
        """
        대량 배치 수집 작업 시작
        
        Args:
            collect_chart_data: 차트 데이터 수집 여부
            collect_supply_data: 수급 데이터 수집 여부
            chart_months: 차트 데이터 수집 개월 수
            supply_months: 수급 데이터 수집 개월 수
            
        Returns:
            Dict: 작업 시작 결과
        """
        try:
            self.logger.info("대량 배치 수집 작업 시작")
            
            results = {}
            
            if collect_chart_data:
                self.logger.info(f"차트 데이터 수집 시작 ({chart_months}개월)")
                chart_result = await self.collect_all_stock_chart_data(
                    months_back=chart_months,
                    batch_size=30
                )
                results["chart_data"] = chart_result
            
            if collect_supply_data:
                self.logger.info(f"수급 데이터 수집 시작 ({supply_months}개월)")
                supply_result = await self.collect_all_supply_demand_data(
                    months_back=supply_months,
                    batch_size=15
                )
                results["supply_data"] = supply_result
            
            self.logger.info("대량 배치 수집 작업 완료")
            
            return {
                "success": True,
                "message": "대량 배치 수집 작업이 성공적으로 완료되었습니다",
                "results": results,
                "completed_at": datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"대량 배치 수집 작업 실패: {e}")
            return {
                "success": False,
                "message": f"대량 배치 수집 작업 실패: {str(e)}",
                "failed_at": datetime.now().isoformat()
            }

    async def _create_standard_supply_demand_response(
        self, 
        supply_demand_data, 
        symbol: str, 
        symbol_name: str, 
        start_date: str, 
        end_date: str
    ) -> SupplyDemandResponse:
        """표준 JSON 형태의 수급 데이터 응답 생성"""
        from datetime import timezone, timedelta
        
        korea_tz = timezone(timedelta(hours=9))  # UTC+9 한국 표준시
        
        supply_demand_points = []
        for data_point in supply_demand_data:
            # UTC 시간을 한국 시간으로 변환
            korea_time = data_point.date.replace(tzinfo=timezone.utc).astimezone(korea_tz) if hasattr(data_point.date, 'replace') else data_point.date
            
            supply_demand_points.append({
                "date": korea_time.strftime('%Y-%m-%d') if hasattr(korea_time, 'strftime') else str(data_point.date),
                "current_price": float(data_point.current_price) if data_point.current_price else None,
                "price_change_sign": data_point.price_change_sign,
                "price_change": float(data_point.price_change) if data_point.price_change else None,
                "price_change_percent": float(data_point.price_change_percent) if data_point.price_change_percent else None,
                "accumulated_volume": int(data_point.accumulated_volume) if data_point.accumulated_volume else None,
                "accumulated_value": int(data_point.accumulated_value) if data_point.accumulated_value else None,
                "individual_investor": int(data_point.individual_investor) if data_point.individual_investor else None,
                "foreign_investor": int(data_point.foreign_investor) if data_point.foreign_investor else None,
                "institution_total": int(data_point.institution_total) if data_point.institution_total else None,
                "financial_investment": int(data_point.financial_investment) if data_point.financial_investment else None,
                "insurance": int(data_point.insurance) if data_point.insurance else None,
                "investment_trust": int(data_point.investment_trust) if data_point.investment_trust else None,
                "other_financial": int(data_point.other_financial) if data_point.other_financial else None,
                "bank": int(data_point.bank) if data_point.bank else None,
                "pension_fund": int(data_point.pension_fund) if data_point.pension_fund else None,
                "private_fund": int(data_point.private_fund) if data_point.private_fund else None,
                "government": int(data_point.government) if data_point.government else None,
                "other_corporation": int(data_point.other_corporation) if data_point.other_corporation else None,
                "domestic_foreign": int(data_point.domestic_foreign) if data_point.domestic_foreign else None
            })
        
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
        """압축된 형태의 수급 데이터 응답 생성"""
        from datetime import timezone, timedelta
        
        korea_tz = timezone(timedelta(hours=9))  # UTC+9 한국 표준시
        
        # 스키마 정의 (수급 데이터 필드들)
        schema = {
            "fields": [
                "date", "current_price", "price_change_sign", "price_change", "price_change_percent",
                "accumulated_volume", "accumulated_value", "individual_investor", "foreign_investor",
                "institution_total", "financial_investment", "insurance", "investment_trust",
                "other_financial", "bank", "pension_fund", "private_fund", "government",
                "other_corporation", "domestic_foreign"
            ],
            "types": [
                "date", "decimal", "string", "decimal", "decimal", 
                "integer", "integer", "integer", "integer", 
                "integer", "integer", "integer", "integer",
                "integer", "integer", "integer", "integer", "integer",
                "integer", "integer"
            ]
        }
        
        # 압축된 데이터 배열 생성 (소수점 2자리 제한으로 추가 절약)
        compressed_data = []
        for data_point in supply_demand_data:
            # UTC 시간을 한국 시간으로 변환
            korea_time = data_point.date.replace(tzinfo=timezone.utc).astimezone(korea_tz) if hasattr(data_point.date, 'replace') else data_point.date
            
            compressed_data.append([
                korea_time.strftime('%Y-%m-%d') if hasattr(korea_time, 'strftime') else str(data_point.date),
                round(float(data_point.current_price), 2) if data_point.current_price else None,
                data_point.price_change_sign,
                round(float(data_point.price_change), 2) if data_point.price_change else None,
                round(float(data_point.price_change_percent), 2) if data_point.price_change_percent else None,
                int(data_point.accumulated_volume) if data_point.accumulated_volume else None,
                int(data_point.accumulated_value) if data_point.accumulated_value else None,
                int(data_point.individual_investor) if data_point.individual_investor else None,
                int(data_point.foreign_investor) if data_point.foreign_investor else None,
                int(data_point.institution_total) if data_point.institution_total else None,
                int(data_point.financial_investment) if data_point.financial_investment else None,
                int(data_point.insurance) if data_point.insurance else None,
                int(data_point.investment_trust) if data_point.investment_trust else None,
                int(data_point.other_financial) if data_point.other_financial else None,
                int(data_point.bank) if data_point.bank else None,
                int(data_point.pension_fund) if data_point.pension_fund else None,
                int(data_point.private_fund) if data_point.private_fund else None,
                int(data_point.government) if data_point.government else None,
                int(data_point.other_corporation) if data_point.other_corporation else None,
                int(data_point.domestic_foreign) if data_point.domestic_foreign else None
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
