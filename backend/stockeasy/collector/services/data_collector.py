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

# 공통 유틸리티 함수 import
from common.utils.util import safe_float, safe_int, safe_price_float, safe_float_or_none, safe_int_or_none


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
                volume=candle.volume,
                price_change_percent=candle.price_change_percent
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
            "fields": ["timestamp", "open", "high", "low", "close", "volume", "price_change_percent"],
            "types": ["datetime", "decimal", "decimal", "decimal", "decimal", "integer", "decimal"]
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
                int(candle.volume) if candle.volume else None,
                float(candle.price_change_percent) if candle.price_change_percent is not None else None
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
                {'code': '001', 'name': 'KOSPI'},
                {'code': '101', 'name': 'KOSDAQ'}
            ]
            
            for market in market_codes:
                try:
                    # ka20003 API로 전업종지수 조회
                    market_data = await self.kiwoom_client.get_market_indices(market['code'])
                    
                    if market_data:
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
            cached_data = await self.cache_manager.get_cache("all_stock_list_for_stockai")
            if cached_data:
                # 메타데이터 구조인지 확인
                if isinstance(cached_data, dict) and "data" in cached_data:
                    stock_dict = cached_data["data"]
                else:
                    # 기존 형태의 캐시 데이터 (하위 호환성)
                    stock_dict = cached_data
                
                # 전체 종목 정보를 반환
                result = []
                for stock_info in stock_dict.values():
                    result.append(stock_info)
                
                self.logger.info(f"캐시에서 종목 리스트 반환: {len(result)}개")
                return result
            
            # 캐시에 없으면 키움 API에서 조회 (Dict 형태로 받음)
            self.logger.info("캐시에 종목 리스트가 없어 키움 API에서 조회")
            stock_dict = await self.kiwoom_client.get_all_stock_list_for_stockai()
            
            # 키움 API에서 조회한 결과를 캐시에 저장 (메타데이터 포함)
            if stock_dict:
                # 메타데이터와 함께 저장
                cache_data = {
                    "data": stock_dict,
                    "metadata": {
                        "updated_at": datetime.now().isoformat(),
                        "total_count": len(stock_dict),
                        "source": "kiwoom_api"
                    }
                }
                
                # 캐시에 저장 (24시간 TTL)
                await self.cache_manager.set_cache(
                    "all_stock_list_for_stockai",
                    cache_data,
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
            cached_data = await self.cache_manager.get_cache("all_stock_list")
            if cached_data:
                # 메타데이터 구조인지 확인
                if isinstance(cached_data, dict) and "data" in cached_data:
                    stock_dict = cached_data["data"]
                else:
                    # 기존 형태의 캐시 데이터 (하위 호환성)
                    stock_dict = cached_data
                
                # 전체 종목 정보를 반환
                result = []
                for stock_info in stock_dict.values():
                    result.append(stock_info)
                
                self.logger.info(f"캐시에서 종목 리스트 반환: {len(result)}개")
                return result
            
            # 캐시에 없으면 키움 API에서 조회 (Dict 형태로 받음)
            self.logger.info("캐시에 종목 리스트가 없어 키움 API에서 조회")
            stock_dict = await self.kiwoom_client.get_all_stock_list()
            
            # 키움 API에서 조회한 결과를 캐시에 저장 (메타데이터 포함)
            if stock_dict:
                # 메타데이터와 함께 저장
                cache_data = {
                    "data": stock_dict,
                    "metadata": {
                        "updated_at": datetime.now().isoformat(),
                        "total_count": len(stock_dict),
                        "source": "kiwoom_api"
                    }
                }
                
                # 캐시에 저장 (24시간 TTL)
                await self.cache_manager.set_cache(
                    "all_stock_list",
                    cache_data,
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
        종목코드로 종목 상세 정보 조회 (개별 캐싱 적용)
        
        Args:
            code (str): 종목코드
            
        Returns:
            Optional[Dict[str, Any]]: 종목 상세 정보 또는 None
        """
        try:
            # 개별 종목 상세 정보 캐시에서 먼저 조회
            cache_key = f"stock_basic_info:{code}"
            cached_info = await self.cache_manager.get_cache(cache_key)
            
            if cached_info:
                self.logger.info(f"캐시에서 종목 상세 정보 조회: {code}")
                return cached_info
            
            # 캐시에 없으면 키움 API에서 개별 조회
            self.logger.info(f"[kiwoom] get_stock_info : {code}")
            stock_info = await self.kiwoom_client.get_stock_info(code)
            
            if stock_info:
                cached_data = await self.cache_manager.get_cache("all_stock_list_for_stockai")
                
                # 캐시 데이터에서 해당 종목의 market 정보 찾기
                market = 'KOSPI'  # 기본값
                if cached_data and 'data' in cached_data:
                    # data는 [code, name, market] 형태의 배열들
                    data_list = cached_data['data']
                    market = data_list[code]['market']
                
                stock_info['market'] = market
                # 캐시에 저장 (1시간 TTL)
                await self.cache_manager.set_cache(
                    cache_key,
                    stock_info,
                    ttl=3600  # 1시간
                )
                self.logger.info(f"종목 상세 정보 캐시 저장 완료: {code}")
                
            self.logger.info(f"get_stock_info_by_code: {stock_info}")
            return stock_info
            
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
            cached_data = await self.cache_manager.get_cache("all_stock_list")
            if cached_data:
                # 메타데이터 구조인지 확인
                if isinstance(cached_data, dict) and "data" in cached_data:
                    cached_list = cached_data["data"]
                else:
                    # 기존 형태의 캐시 데이터 (하위 호환성)
                    cached_list = cached_data
            else:
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
            
            # 캐시에 저장 (메타데이터 포함)
            cache_data = {
                "data": stock_list,
                "metadata": {
                    "updated_at": datetime.now().isoformat(),
                    "total_count": len(stock_list),
                    "source": "kiwoom_api_force_refresh"
                }
            }
            await self.cache_manager.set_cache(
                "all_stock_list", 
                cache_data, 
                ttl=86400  # 24시간
            )
            
            stock_list_for_stockai = await self.kiwoom_client.get_all_stock_list_for_stockai(force_refresh=True)
            # 캐시에 저장(stock ai) - 메타데이터 포함
            cache_data_stockai = {
                "data": stock_list_for_stockai,
                "metadata": {
                    "updated_at": datetime.now().isoformat(),
                    "total_count": len(stock_list_for_stockai),
                    "source": "kiwoom_api_force_refresh"
                }
            }
            await self.cache_manager.set_cache(
                "all_stock_list_for_stockai", 
                cache_data_stockai, 
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
        마지막 업데이트 시간 조회 (캐시 메타데이터 우선, 키움 API 보조)
        
        Args:
            update_type (str): 업데이트 유형 ("stockai" 또는 "stock")
            
        Returns:
            Optional[datetime]: 마지막 업데이트 시간 또는 None
        """
        try:
            # 1. 먼저 캐시에서 메타데이터 조회
            if update_type == "stockai":
                cache_key = "all_stock_list_for_stockai"
                cache_data = await self.cache_manager.get_cache(cache_key)
                if cache_data and isinstance(cache_data, dict) and 'metadata' in cache_data:
                    updated_at = cache_data['metadata'].get('updated_at')
                    if updated_at:
                        return datetime.fromisoformat(updated_at) if isinstance(updated_at, str) else updated_at
                
                # 캐시에 메타데이터가 없으면 키움 클라이언트에서 조회
                return getattr(self.kiwoom_client, '_last_stockai_update', None)
                
            elif update_type == "stock":
                cache_key = "all_stock_list"
                cache_data = await self.cache_manager.get_cache(cache_key)
                if cache_data and isinstance(cache_data, dict) and 'metadata' in cache_data:
                    updated_at = cache_data['metadata'].get('updated_at')
                    if updated_at:
                        return datetime.fromisoformat(updated_at) if isinstance(updated_at, str) else updated_at
                
                # 캐시에 메타데이터가 없으면 키움 클라이언트에서 조회
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
        force_update: bool = False,
        progress_callback=None
    ) -> Dict[str, Any]:
        """
        전종목 일봉 차트 데이터 수집 (Producer-Consumer 패턴으로 성능 최적화)
        
        Args:
            months_back: 수집할 개월 수 (기본 24개월)
            batch_size: 배치 크기 (동시 처리할 종목 수)
            force_update: 기존 데이터 강제 덮어쓰기 여부 (전체 테이블 삭제 후 재생성)
            progress_callback: 진행상황 콜백 함수
            
        Returns:
            Dict: 수집 결과
        """
        with LogContext(self.logger, f"전종목 일봉 차트 데이터 수집 ({months_back}개월) - 큐 기반" + (" [강제 업데이트]" if force_update else "")) as ctx:
            try:
                # timescale_service import (스코프 문제 해결)
                from stockeasy.collector.services.timescale_service import timescale_service
                
                # force_update=True일 때 전체 테이블 삭제
                if force_update:
                    ctx.log_progress("강제 업데이트 모드: 전체 주가 데이터 테이블 TRUNCATE 시작")
                    delete_result = await timescale_service.delete_all_stock_prices()
                    ctx.log_progress(f"전체 주가 데이터 테이블 TRUNCATE 완료")
                
                # 전종목 리스트 조회
                all_stocks = await self.get_all_stock_list_for_stockai()
                
                if not all_stocks:
                    raise Exception("종목 리스트가 비어있습니다")
                
                # 날짜 계산
                from datetime import datetime, timedelta
                import asyncio
                end_date = datetime.now()
                start_date = end_date - timedelta(days=months_back * 30)
                start_date_str = start_date.strftime('%Y%m%d')
                end_date_str = end_date.strftime('%Y%m%d')
                
                ctx.log_progress(f"수집 대상: {len(all_stocks)}개 종목")
                ctx.log_progress(f"기간: {start_date_str} ~ {end_date_str}")
                
                total_stocks = len(all_stocks)
                
                # 공유 상태 관리
                stats = {
                    "processed_stocks": 0,
                    "success_stocks": 0,
                    "error_stocks": 0,
                    "total_records": 0,
                    "api_finished": False
                }
                
                # 큐 생성 (메모리 기반 - 최대 큐 크기 제한으로 메모리 보호)
                data_queue = asyncio.Queue(maxsize=10)  # 최대 10개 배치만 메모리에 보관
                
                async def api_producer():
                    """API 호출해서 데이터를 큐에 넣는 Producer"""
                    try:
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
                                
                                # 데이터 변환
                                stock_price_data = []
                                for symbol, chart_data in chart_data_dict.items():
                                    for chart_item in chart_data:
                                        try:
                                            # 안전한 변환 함수들 (공통 함수 사용)
                                            
                                            # 키움 API에서 제공하는 계산값들 추출
                                            api_change_amount = safe_float(chart_item.change_amount) if hasattr(chart_item, 'change_amount') else None
                                            api_change_rate = safe_float(chart_item.change_rate) if hasattr(chart_item, 'change_rate') else None
                                            api_previous_close = safe_float(chart_item.previous_close) if hasattr(chart_item, 'previous_close') else None
                                            api_volume_change_percent = safe_float(chart_item.volume_change_percent) if hasattr(chart_item, 'volume_change_percent') else None
                                            
                                            # volume_change_percent 값 제한 (NUMERIC(10,4) 오버플로우 방지)
                                            if api_volume_change_percent is not None:
                                                if abs(api_volume_change_percent) > 999999.9999:
                                                    self.logger.warning(f"종목 {symbol} 날짜 {chart_item.date}: volume_change_percent 값이 너무 큼 ({api_volume_change_percent}), 999999.9999로 제한")
                                                    api_volume_change_percent = 999999.9999 if api_volume_change_percent > 0 else -999999.9999
                                            
                                            # 수정주가 관련 필드 추출
                                            api_adjustment_type = getattr(chart_item, 'adjustment_type', None)
                                            api_adjustment_ratio = safe_float(getattr(chart_item, 'adjustment_ratio', None))
                                            api_adjustment_event = getattr(chart_item, 'adjustment_event', None)
                                            
                                            stock_price = StockPriceCreate(
                                                time=datetime.strptime(chart_item.date, '%Y%m%d') if hasattr(chart_item, 'date') else datetime.now(),
                                                symbol=symbol,
                                                interval_type=IntervalType.ONE_DAY.value,
                                                open=safe_float(chart_item.open),
                                                high=safe_float(chart_item.high),
                                                low=safe_float(chart_item.low),
                                                close=safe_float(chart_item.close),
                                                volume=safe_int(chart_item.volume),
                                                trading_value=safe_int(chart_item.trading_value),
                                                # 키움 API에서 제공하는 계산값들 활용
                                                change_amount=api_change_amount,
                                                price_change_percent=api_change_rate,
                                                previous_close_price=api_previous_close,
                                                volume_change_percent=api_volume_change_percent,
                                                # 수정주가 관련 정보
                                                adjusted_price_type=api_adjustment_type,
                                                adjustment_ratio=api_adjustment_ratio,
                                                adjusted_price_event=api_adjustment_event,
                                                # updated_at 필드 추가 (UPSERT 시 갱신 보장)
                                                updated_at=datetime.now()
                                            )
                                            stock_price_data.append(stock_price)
                                        except Exception as e:
                                            ctx.logger.warning(f"차트 데이터 변환 실패 ({symbol}): {e}")
                                            continue
                                
                                # 큐에 데이터 추가 (배치 정보 포함)
                                if stock_price_data:
                                    batch_info = {
                                        "data": stock_price_data,
                                        "symbols": symbols,
                                        "batch_num": i//batch_size + 1
                                    }
                                    await data_queue.put(batch_info)
                                    ctx.logger.info(f"API Producer: 배치 {i//batch_size + 1} 큐에 추가 ({len(stock_price_data)}건)")
                                
                                stats["processed_stocks"] += len(symbols)
                                success_count = len([s for s in symbols if s in chart_data_dict and chart_data_dict[s]])
                                stats["success_stocks"] += success_count
                                
                            except Exception as e:
                                ctx.logger.error(f"API Producer 배치 처리 실패 (배치 {i//batch_size + 1}): {e}")
                                stats["error_stocks"] += len(symbols)
                            
                            # API 제한 준수
                            await asyncio.sleep(0.3)
                        
                        # Producer 완료 신호
                        stats["api_finished"] = True
                        await data_queue.put(None)  # 종료 신호
                        ctx.log_progress("API Producer 완료")
                        
                    except Exception as e:
                        ctx.logger.error(f"API Producer 실패: {e}")
                        stats["api_finished"] = True
                        await data_queue.put(None)  # 종료 신호
                
                async def db_consumer():
                    """큐에서 데이터를 꺼내서 DB에 저장하는 Consumer"""
                    try:
                        while True:
                            # 큐에서 데이터 가져오기
                            batch_info = await data_queue.get()
                            
                            # 종료 신호 확인
                            if batch_info is None:
                                ctx.log_progress("DB Consumer 종료 신호 수신")
                                break
                            
                            try:
                                stock_price_data = batch_info["data"]
                                symbols = batch_info["symbols"]
                                batch_num = batch_info["batch_num"]
                                
                                # 대량 데이터를 작은 배치로 나누어 처리 (스키마 제한 10,000개 준수)
                                max_batch_size = 5000  # 안전한 배치 크기
                                total_processed = 0
                                
                                for i in range(0, len(stock_price_data), max_batch_size):
                                    sub_batch = stock_price_data[i:i + max_batch_size]
                                    
                                    # TimescaleDB에 저장 (force_update 모드에 따라 다른 방식 사용)
                                    if force_update:
                                        # 강제 업데이트 모드: 단순 INSERT (충돌 시 NOTHING)
                                        from stockeasy.collector.schemas.timescale_schemas import BulkStockPriceCreate
                                        await timescale_service.bulk_create_stock_prices(
                                            BulkStockPriceCreate(prices=sub_batch)
                                        )
                                        ctx.logger.info(f"DB Consumer [강제모드]: 배치 {batch_num}-{i//max_batch_size + 1} 단순 INSERT 완료 ({len(sub_batch)}건)")
                                    else:
                                        # 일반 모드: 기존 방식 (ON CONFLICT DO NOTHING)
                                        await timescale_service.bulk_create_stock_prices_with_progress(
                                            sub_batch,
                                            batch_size=2000,
                                            progress_callback=None
                                        )
                                        ctx.logger.info(f"DB Consumer: 배치 {batch_num}-{i//max_batch_size + 1} 저장 완료 ({len(sub_batch)}건)")
                                    
                                    total_processed += len(sub_batch)
                                
                                stats["total_records"] += total_processed
                                ctx.logger.info(f"DB Consumer: 배치 {batch_num} 전체 처리 완료 ({total_processed}건, {len(stock_price_data) // max_batch_size + 1}개 서브배치)")
                                
                                # 변동률 등 배치 계산 (force_update 모드에서는 스킵)
                                if not force_update:
                                    batch_symbols = list(set([price.symbol for price in stock_price_data]))
                                    try:
                                        calc_result = await timescale_service.batch_calculate_for_new_data(
                                            symbols=batch_symbols
                                        )
                                        ctx.logger.info(f"DB Consumer: 배치 {batch_num} 계산 완료: {calc_result.get('total_updated', 0)}건")
                                    except Exception as e:
                                        ctx.logger.warning(f"배치 계산 실패 (데이터는 정상 저장됨): {e}")
                                
                            except Exception as e:
                                ctx.logger.error(f"DB Consumer 배치 처리 실패: {e}")
                            
                            # 진행상황 알림
                            if progress_callback:
                                progress = (stats["processed_stocks"] / total_stocks) * 100
                                await progress_callback(
                                    stats["processed_stocks"], total_stocks, progress,
                                    stats["success_stocks"], stats["error_stocks"], stats["total_records"]
                                )
                            
                            data_queue.task_done()
                        
                        ctx.log_progress("DB Consumer 완료")
                        
                    except Exception as e:
                        ctx.logger.error(f"DB Consumer 실패: {e}")
                
                # Producer와 Consumer를 병렬 실행
                ctx.log_progress("Producer-Consumer 병렬 처리 시작")
                producer_task = asyncio.create_task(api_producer())
                consumer_task = asyncio.create_task(db_consumer())
                
                # 두 태스크 완료 대기
                await asyncio.gather(producer_task, consumer_task)
                
                # 전체 배치 수집 완료 후 최종 배치 계산 실행 (force_update 모드에서는 스킵)
                if not force_update:
                    ctx.log_progress("전체 수집 완료 후 최종 배치 계산 시작")
                    try:
                        # 성공적으로 수집된 종목들에 대해 최종 배치 계산
                        successful_symbols = []
                        if stats["success_stocks"] > 0:
                            # 실제 DB에서 데이터가 있는 종목들을 조회
                            from stockeasy.collector.services.timescale_service import timescale_service
                            from sqlalchemy import text
                            from stockeasy.collector.core.timescale_database import get_timescale_session_context
                            
                            async with get_timescale_session_context() as session:
                                symbols_query = text("""
                                    SELECT DISTINCT symbol 
                                    FROM stock_prices 
                                    WHERE time >= :start_date::date 
                                    AND time <= :end_date::date
                                    ORDER BY symbol
                                """)
                                result_symbols = await session.execute(symbols_query, {
                                    'start_date': start_date_str[:4] + '-' + start_date_str[4:6] + '-' + start_date_str[6:8],
                                    'end_date': end_date_str[:4] + '-' + end_date_str[4:6] + '-' + end_date_str[6:8]
                                })
                                successful_symbols = [row[0] for row in result_symbols.fetchall()]
                        
                        if successful_symbols:
                            ctx.log_progress(f"최종 배치 계산 대상: {len(successful_symbols)}개 종목")
                            final_calc_result = await timescale_service.batch_calculate_stock_price_changes(
                                symbols=successful_symbols,
                                days_back=(datetime.strptime(end_date_str, '%Y%m%d') - datetime.strptime(start_date_str, '%Y%m%d')).days + 1,
                                batch_size=50
                            )
                            ctx.log_progress(f"최종 배치 계산 완료: {final_calc_result.get('total_updated', 0)}건 업데이트")
                        else:
                            ctx.log_progress("최종 배치 계산 대상 없음")
                            
                    except Exception as e:
                        ctx.logger.warning(f"최종 배치 계산 실패 (데이터 수집은 정상 완료): {e}")
                else:
                    ctx.log_progress("강제 업데이트 모드: 후처리 배치 계산 스킵")
                
                result = {
                    "success": True,
                    "total_stocks": total_stocks,
                    "success_stocks": stats["success_stocks"],
                    "error_stocks": stats["error_stocks"],
                    "total_records": stats["total_records"],
                    "start_date": start_date_str,
                    "end_date": end_date_str,
                    "force_update": force_update,
                    "final_calculation_symbols": len(successful_symbols) if not force_update and 'successful_symbols' in locals() else 0,
                    "message": f"전종목 차트 데이터 수집 완료 (큐 기반{'[강제 업데이트]' if force_update else ''}): {stats['success_stocks']}/{total_stocks} 종목, {stats['total_records']}건"
                }
                
                ctx.log_progress(f"전종목 차트 데이터 수집 완료 (큐 기반{'[강제 업데이트]' if force_update else ''}): {stats['success_stocks']}/{total_stocks} 종목, {stats['total_records']}건")
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
        전종목 수급 데이터 수집 (Producer-Consumer 패턴으로 성능 최적화)
        
        Args:
            months_back: 수집할 개월 수 (기본 6개월)
            batch_size: 배치 크기 (동시 처리할 종목 수)
            progress_callback: 진행상황 콜백 함수
            
        Returns:
            Dict: 수집 결과
        """
        with LogContext(self.logger, f"전종목 수급 데이터 수집 ({months_back}개월) - 큐 기반") as ctx:
            try:
                # 전종목 리스트 조회
                all_stocks = await self.get_all_stock_list_for_stockai()
                
                if not all_stocks:
                    raise Exception("종목 리스트가 비어있습니다")
                
                # 날짜 계산
                from datetime import datetime, timedelta
                import asyncio
                end_date = datetime.now()
                start_date = end_date - timedelta(days=months_back * 30)
                start_date_str = start_date.strftime('%Y%m%d')
                end_date_str = end_date.strftime('%Y%m%d')
                
                ctx.log_progress(f"수집 대상: {len(all_stocks)}개 종목")
                ctx.log_progress(f"기간: {start_date_str} ~ {end_date_str}")
                
                total_stocks = len(all_stocks)
                
                # 공유 상태 관리
                stats = {
                    "processed_stocks": 0,
                    "success_stocks": 0,
                    "error_stocks": 0,
                    "total_records": 0,
                    "api_finished": False
                }
                
                # 큐 생성 (수급 데이터는 더 작은 큐 크기)
                data_queue = asyncio.Queue(maxsize=5)  # 최대 5개 배치만 메모리에 보관
                
                async def api_producer():
                    """API 호출해서 데이터를 큐에 넣는 Producer"""
                    try:
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
                                
                                # 데이터 변환
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
                                
                                # 큐에 데이터 추가
                                if supply_demand_data:
                                    batch_info = {
                                        "data": supply_demand_data,
                                        "symbols": symbols,
                                        "batch_num": i//batch_size + 1
                                    }
                                    await data_queue.put(batch_info)
                                    ctx.logger.info(f"API Producer: 배치 {i//batch_size + 1} 큐에 추가 ({len(supply_demand_data)}건)")
                                
                                stats["processed_stocks"] += len(symbols)
                                success_count = len([s for s in symbols if s in supply_data_dict and supply_data_dict[s]])
                                stats["success_stocks"] += success_count
                                
                            except Exception as e:
                                ctx.logger.error(f"API Producer 배치 처리 실패 (배치 {i//batch_size + 1}): {e}")
                                stats["error_stocks"] += len(symbols)
                            
                            # API 제한 준수 (수급 데이터는 더 긴 대기)
                            await asyncio.sleep(0.8)
                        
                        # Producer 완료 신호
                        stats["api_finished"] = True
                        await data_queue.put(None)  # 종료 신호
                        ctx.log_progress("API Producer 완료")
                        
                    except Exception as e:
                        ctx.logger.error(f"API Producer 실패: {e}")
                        stats["api_finished"] = True
                        await data_queue.put(None)  # 종료 신호
                
                async def db_consumer():
                    """큐에서 데이터를 꺼내서 DB에 저장하는 Consumer"""
                    try:
                        while True:
                            # 큐에서 데이터 가져오기
                            batch_info = await data_queue.get()
                            
                            # 종료 신호 확인
                            if batch_info is None:
                                ctx.log_progress("DB Consumer 종료 신호 수신")
                                break
                            
                            try:
                                supply_demand_data = batch_info["data"]
                                symbols = batch_info["symbols"] 
                                batch_num = batch_info["batch_num"]
                                
                                # TimescaleDB에 저장
                                await timescale_service.bulk_create_supply_demand_with_progress(
                                    supply_demand_data,
                                    batch_size=500,
                                    progress_callback=None
                                )
                                stats["total_records"] += len(supply_demand_data)
                                
                                ctx.logger.info(f"DB Consumer: 배치 {batch_num} 저장 완료 ({len(supply_demand_data)}건)")
                                
                            except Exception as e:
                                ctx.logger.error(f"DB Consumer 배치 처리 실패: {e}")
                            
                            # 진행상황 알림
                            if progress_callback:
                                progress = (stats["processed_stocks"] / total_stocks) * 100
                                await progress_callback(
                                    stats["processed_stocks"], total_stocks, progress,
                                    stats["success_stocks"], stats["error_stocks"], stats["total_records"]
                                )
                            
                            data_queue.task_done()
                        
                        ctx.log_progress("DB Consumer 완료")
                        
                    except Exception as e:
                        ctx.logger.error(f"DB Consumer 실패: {e}")
                
                # Producer와 Consumer를 병렬 실행
                ctx.log_progress("Producer-Consumer 병렬 처리 시작")
                producer_task = asyncio.create_task(api_producer())
                consumer_task = asyncio.create_task(db_consumer())
                
                # 두 태스크 완료 대기
                await asyncio.gather(producer_task, consumer_task)
                
                result = {
                    "success": True,
                    "total_stocks": total_stocks,
                    "success_stocks": stats["success_stocks"],
                    "error_stocks": stats["error_stocks"],
                    "total_records": stats["total_records"],
                    "start_date": start_date_str,
                    "end_date": end_date_str,
                    "message": f"전종목 수급 데이터 수집 완료 (큐 기반): {stats['success_stocks']}/{total_stocks} 종목, {stats['total_records']}건"
                }
                
                ctx.log_progress(f"전종목 수급 데이터 수집 완료 (큐 기반): {stats['success_stocks']}/{total_stocks} 종목, {stats['total_records']}건")
                return result
                
            except Exception as e:
                ctx.logger.error(f"전종목 수급 데이터 수집 실패: {e}")
                raise
    
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
            
            # SupplyDemandDataPoint 객체 생성 (timestamp 필드 사용)
            from stockeasy.collector.schemas.stock_schemas import SupplyDemandDataPoint
            
            supply_demand_point = SupplyDemandDataPoint(
                timestamp=korea_time,  # timestamp 필드 사용
                current_price=float(data_point.current_price) if data_point.current_price else None,
                price_change_sign=data_point.price_change_sign,
                price_change=float(data_point.price_change) if data_point.price_change else None,
                price_change_percent=float(data_point.price_change_percent) if data_point.price_change_percent else None,
                accumulated_volume=int(data_point.accumulated_volume) if data_point.accumulated_volume else None,
                accumulated_value=int(data_point.accumulated_value) if data_point.accumulated_value else None,
                individual_investor=int(data_point.individual_investor) if data_point.individual_investor else None,
                foreign_investor=int(data_point.foreign_investor) if data_point.foreign_investor else None,
                institution_total=int(data_point.institution_total) if data_point.institution_total else None,
                financial_investment=int(data_point.financial_investment) if data_point.financial_investment else None,
                insurance=int(data_point.insurance) if data_point.insurance else None,
                investment_trust=int(data_point.investment_trust) if data_point.investment_trust else None,
                other_financial=int(data_point.other_financial) if data_point.other_financial else None,
                bank=int(data_point.bank) if data_point.bank else None,
                pension_fund=int(data_point.pension_fund) if data_point.pension_fund else None,
                private_fund=int(data_point.private_fund) if data_point.private_fund else None,
                government=int(data_point.government) if data_point.government else None,
                other_corporation=int(data_point.other_corporation) if data_point.other_corporation else None,
                domestic_foreign=int(data_point.domestic_foreign) if data_point.domestic_foreign else None
            )
            
            supply_demand_points.append(supply_demand_point)
        
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
    
    async def update_today_chart_data(self, batch_size: int = 100, scheduler_mode: bool = False) -> Dict[str, Any]:
        """당일 차트 데이터만 업데이트 (관심종목정보요청 ka10095 사용, 메모리의 수정주가 정보 포함)"""
        from stockeasy.collector.services.timescale_service import timescale_service
        from stockeasy.collector.schemas.timescale_schemas import StockPriceCreate, IntervalType
        
        # 스케줄러 모드일 때 키움 클라이언트 로그 레벨 임시 변경
        original_log_level = None
        if scheduler_mode:
            # 키움 클라이언트에 스케줄러 모드 설정
            self.kiwoom_client._scheduler_mode = True
        
        today = datetime.now()
        today_str = today.strftime('%Y%m%d')
        
        # 스케줄러 모드에서도 중요한 정보는 로깅
        start_log_msg = f"당일 차트 데이터 업데이트 시작 - 오늘: {today_str} ({today.strftime('%A')})"
        if scheduler_mode:
            self.logger.info(f"[스케줄러] {start_log_msg}")
        else:
            self.logger.info(start_log_msg)
        
        try:
            # 전체 종목 리스트 조회
            stock_list = await self.get_all_stock_list_for_stockai()
            if not stock_list:
                return {
                    "message": "종목 리스트가 비어있습니다",
                    "total_stocks": 0,
                    "updated_stocks": 0,
                    "with_adjustment": 0,
                    "errors": 0,
                    "date": today_str,
                    "status": "completed"
                }
            
            total_stocks = len(stock_list)
            updated_stocks = 0
            with_adjustment = 0
            errors = 0
            
            if not scheduler_mode:
                self.logger.info(f"당일 차트 데이터 업데이트 시작 (ka10095): 총 {total_stocks}개 종목, 배치크기: {batch_size}")
            else:
                self.logger.info(f"[스케줄러] 당일 차트 데이터 업데이트 시작: {total_stocks}개 종목")

            # 안전한 변환 함수들 (공통 함수 사용)
            
            def clean_price_data(value):
                """주가 데이터에서 +/- 기호 제거 및 절댓값 반환"""
                if not value or str(value).strip() == '':
                    return 0.0
                try:
                    # 문자열에서 +/- 기호 제거 후 절댓값 반환
                    clean_str = str(value).replace(',', '').replace('+', '').replace('-', '')
                    return float(clean_str) if clean_str else 0.0
                except (ValueError, TypeError):
                    return 0.0
            
            def safe_change_data(value):
                """변화율 데이터에서 부호 유지하여 안전하게 변환"""
                if not value or str(value).strip() == '':
                    return 0.0
                try:
                    # 콤마만 제거하고 +/- 기호는 유지
                    clean_str = str(value).replace(',', '')
                    result = float(clean_str) if clean_str else 0.0
                    
                    # NUMERIC(10,4) 오버플로우 방지 - 거래량 변화율 제한
                    if abs(result) > 999999.9999:
                        self.logger.warning(f"변화율 값이 너무 큼 ({result}), 999999.9999로 제한")
                        result = 999999.9999 if result > 0 else -999999.9999
                    
                    return result
                except (ValueError, TypeError):
                    return 0.0
            
            # 종목 코드만 추출
            all_symbols = [stock["code"] for stock in stock_list]
            
            # 100개씩 배치 단위로 처리 (ka10095 최대 100개 제한)
            for i in range(0, len(all_symbols), batch_size):
                batch_symbols = all_symbols[i:i + batch_size]
                stock_price_data = []
                
                try:
                    # 키움 API에서 관심종목정보요청(ka10095)으로 배치 조회
                    if self.settings.KIWOOM_APP_KEY != "test_api_key":
                        batch_data = await self.kiwoom_client.get_realtime_stock_prices_batch(
                            batch_symbols, today_str
                        )
                        
                        # 각 종목별 데이터 처리
                        for symbol in batch_symbols:
                            try:
                                if symbol not in batch_data:
                                    if not scheduler_mode:
                                        self.logger.debug(f"종목 {symbol}: ka10095 응답에 데이터 없음")
                                    continue
                                
                                chart_item = batch_data[symbol]
                                
                                # 날짜 검증 및 파싱 강화
                                if not chart_item.date or not str(chart_item.date).strip():
                                    if not scheduler_mode:
                                        self.logger.debug(f"종목 {symbol}: 날짜 데이터 없음")
                                    continue
                                
                                try:
                                    chart_date = datetime.strptime(str(chart_item.date).strip(), '%Y%m%d')
                                except ValueError as e:
                                    if not scheduler_mode:
                                        self.logger.warning(f"종목 {symbol}: 날짜 파싱 실패 ({chart_item.date}): {e}")
                                    continue
                                
                                # 오늘 날짜 확인 강화
                                chart_date_str = chart_date.strftime('%Y%m%d')
                                if chart_date_str != today_str:
                                    if not scheduler_mode:
                                        self.logger.debug(f"종목 {symbol}: 오늘 날짜가 아님 ({chart_date_str} != {today_str})")
                                    continue
                                
                                # 가격 데이터 검증 (종가 우선, 없으면 현재가, +/- 기호 제거)
                                close_price = clean_price_data(chart_item.close)
                                if close_price <= 0:
                                    continue
                                
                                # 메모리에서 수정주가 정보 조회
                                adjustment_info = self.get_stored_adjustment_info(symbol)
                                adjustment_type = None
                                adjustment_ratio = None
                                adjustment_event = None
                                
                                if adjustment_info:
                                    adjustment_type = adjustment_info.get("adjustment_type")
                                    adjustment_ratio = adjustment_info.get("adjustment_ratio")
                                    adjustment_event = adjustment_info.get("adjustment_event")
                                    with_adjustment += 1
                                    if not scheduler_mode:
                                        self.logger.debug(f"종목 {symbol} 메모리에서 수정주가 정보 조회: type={adjustment_type}, ratio={adjustment_ratio}, event={adjustment_event}")
                                elif not scheduler_mode:
                                    self.logger.debug(f"종목 {symbol}: 메모리에 수정주가 정보 없음")
                                
                                # TimescaleDB용 데이터 생성 (주가 데이터는 +/- 기호 제거)
                                stock_price = StockPriceCreate(
                                    time=chart_date,
                                    symbol=symbol,
                                    interval_type=IntervalType.ONE_DAY.value,
                                    open=clean_price_data(chart_item.open),
                                    high=clean_price_data(chart_item.high),
                                    low=clean_price_data(chart_item.low),
                                    close=clean_price_data(chart_item.close),
                                    volume=safe_int(chart_item.volume),
                                    trading_value=safe_int(chart_item.trading_value),
                                    # ka10095에서 제공하는 계산값들 (변화율은 부호 유지)
                                    change_amount=safe_change_data(chart_item.change_amount),
                                    price_change_percent=safe_change_data(chart_item.change_rate),
                                    previous_close_price=clean_price_data(chart_item.previous_close),
                                    volume_change_percent=safe_change_data(chart_item.volume_change_percent),
                                    # 수정주가 정보 추가 (메모리에서 조회한 정보)
                                    adjusted_price_type=adjustment_type,
                                    adjustment_ratio=adjustment_ratio,
                                    adjusted_price_event=adjustment_event,
                                    # 전일대비기호 추가
                                    price_change_sign=getattr(chart_item, 'change_sign', None),
                                    # updated_at 필드 추가 (UPSERT 시 갱신 보장)
                                    updated_at=datetime.now()
                                )
                                stock_price_data.append(stock_price)
                                updated_stocks += 1
                                
                            except Exception as e:
                                errors += 1
                                if not scheduler_mode:
                                    self.logger.error(f"종목 {symbol} 데이터 처리 실패: {e}")
                                continue
                    
                except Exception as e:
                    if not scheduler_mode:
                        self.logger.error(f"배치 {i//batch_size + 1} ka10095 API 호출 실패: {e}")
                    errors += len(batch_symbols)
                
                # 배치 데이터를 TimescaleDB에 저장 (배치별 upsert 방식)
                if stock_price_data:
                    try:
                        # 수정주가 정보 보존 UPSERT 방식 (DELETE 없음, 튜플 제한 문제 해결)
                        await timescale_service.upsert_today_stock_prices(
                            stock_price_data,
                            target_date=today,
                            batch_size=50  # 적절한 배치 크기로 조정
                        )
                        
                        if not scheduler_mode:
                            self.logger.info(f"배치 {i//batch_size + 1} DB upsert 완료: {len(stock_price_data)}건 (수정주가 정보 보존)")
                        
                    except Exception as e:
                        if not scheduler_mode:
                            self.logger.error(f"배치 {i//batch_size + 1} DB upsert 실패: {e}")
                
                # 진행률 로그 (스케줄러 모드에서는 5% 단위로만)
                progress = min((i + batch_size) / len(all_symbols) * 100, 100)
                if scheduler_mode:
                    # 스케줄러 모드에서는 5% 단위로만 로그
                    if progress % 5 < (batch_size / len(all_symbols) * 100):
                        self.logger.info(f"[스케줄러] 당일 차트 데이터 업데이트 진행률: {progress:.0f}%")
                else:
                    self.logger.info(f"당일 차트 데이터 업데이트 진행률: {progress:.1f}% ({updated_stocks}/{total_stocks})")
                
                # API 호출 제한 준수 (초당 4.8회 = 0.208초 간격)
                if i + batch_size < len(all_symbols):
                    await asyncio.sleep(0.21)  # 키움 API 제약: 초당 4.8회
            
            if scheduler_mode:
                self.logger.info(f"[스케줄러] 당일 차트 데이터 업데이트 완료: {updated_stocks}/{total_stocks}개 종목 (수정주가 포함: {with_adjustment}개, 오류: {errors}개)")
            else:
                self.logger.info(f"당일 차트 데이터 업데이트 완료 (ka10095): {updated_stocks}개 종목 (수정주가 포함: {with_adjustment}개)")
            
            return {
                "message": f"당일 차트 데이터 업데이트 완료 (ka10095): {updated_stocks}개 종목 (수정주가 포함: {with_adjustment}개)",
                "total_stocks": total_stocks,
                "updated_stocks": updated_stocks,
                "with_adjustment": with_adjustment,
                "errors": errors,
                "date": today_str,
                "status": "completed"
            }
            
        except Exception as e:
            error_msg = f"당일 차트 데이터 업데이트 실패 (ka10095): {e}"
            if scheduler_mode:
                self.logger.error(f"[스케줄러] {error_msg}")
            else:
                self.logger.error(error_msg)
            return {
                "message": error_msg,
                "total_stocks": 0,
                "updated_stocks": 0,
                "with_adjustment": 0,
                "errors": 1,
                "date": today_str,
                "status": "failed"
            }
        finally:
            # 스케줄러 모드에서 변경한 로그 레벨 복원
            if scheduler_mode and original_log_level is not None and hasattr(self.kiwoom_client, 'logger'):
                self.kiwoom_client.logger.setLevel(original_log_level)
            # 스케줄러 모드에서 변경한 설정 복원
            if scheduler_mode:
                self.kiwoom_client._scheduler_mode = False
    
    async def update_today_supply_demand_data(self, batch_size: int = 50, scheduler_mode: bool = False) -> Dict[str, Any]:
        """당일 수급 데이터만 업데이트 (전종목)"""
        from stockeasy.collector.services.timescale_service import timescale_service
        from stockeasy.collector.schemas.timescale_schemas import SupplyDemandCreate
        
        # 스케줄러 모드일 때 키움 클라이언트 로그 레벨 임시 변경
        original_log_level = None
        if scheduler_mode:
            # 키움 클라이언트에 스케줄러 모드 설정
            self.kiwoom_client._scheduler_mode = True
        
        today = datetime.now()
        today_str = today.strftime('%Y%m%d')
        
        try:
            # 전체 종목 리스트 조회 (stockai용)
            stock_list = await self.get_all_stock_list_for_stockai()
            if not stock_list:
                return {
                    "message": "종목 리스트가 비어있습니다",
                    "total_stocks": 0,
                    "updated_stocks": 0,
                    "errors": 0,
                    "status": "completed"
                }
            
            total_stocks = len(stock_list)
            updated_stocks = 0
            errors = 0
            
            if not scheduler_mode:
                self.logger.info(f"당일 수급 데이터 업데이트 시작: 총 {total_stocks}개 종목, 배치크기: {batch_size}")
            else:
                self.logger.info(f"[스케줄러] 당일 수급 데이터 업데이트 시작: {total_stocks}개 종목")
            
            # 안전한 변환 함수들 (공통 함수 사용)
            # (safe_float_or_none, safe_int_or_none 사용)
            
            # 종목 코드만 추출
            all_symbols = [stock["code"] for stock in stock_list]
            
            # 배치 단위로 처리
            for i in range(0, len(all_symbols), batch_size):
                batch_symbols = all_symbols[i:i + batch_size]
                supply_demand_data = []
                
                try:
                    # 키움 API에서 당일 수급 데이터 조회
                    if self.settings.KIWOOM_APP_KEY != "test_api_key":
                        supply_data_dict = await self.kiwoom_client.get_multiple_supply_demand_data(
                            batch_symbols, today_str, today_str
                        )
                        
                        # 각 종목별 데이터 처리
                        for symbol in batch_symbols:
                            symbol_has_data = False  # 종목별 데이터 존재 여부 추적
                            try:
                                if symbol not in supply_data_dict:
                                    if not scheduler_mode:
                                        self.logger.debug(f"종목 {symbol}: 수급 데이터 없음")
                                    continue
                                
                                supply_data = supply_data_dict[symbol]
                                
                                # 당일 데이터만 처리
                                for supply_item in supply_data:
                                    try:
                                        # 날짜 검증
                                        if not supply_item.get('date') or supply_item['date'] != today_str:
                                            continue
                                        
                                        # 수급 데이터 생성
                                        supply_demand = SupplyDemandCreate(
                                            date=today,
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
                                        symbol_has_data = True  # 데이터가 있음을 표시
                                        
                                    except Exception as e:
                                        if not scheduler_mode:
                                            self.logger.warning(f"종목 {symbol} 수급 데이터 변환 실패: {e}")
                                        continue
                                
                                # 종목별로 한 번만 카운터 증가 (실제 데이터가 있는 경우에만)
                                if symbol_has_data:
                                    updated_stocks += 1
                                        
                            except Exception as e:
                                errors += 1
                                if not scheduler_mode:
                                    self.logger.error(f"종목 {symbol} 수급 데이터 처리 실패: {e}")
                                continue
                    
                except Exception as e:
                    if not scheduler_mode:
                        self.logger.error(f"배치 {i//batch_size + 1} 수급 데이터 API 호출 실패: {e}")
                    errors += len(batch_symbols)
                
                # 배치 데이터를 TimescaleDB에 저장 (UPSERT 방식)
                if supply_demand_data:
                    try:
                        await timescale_service.upsert_today_supply_demand_data(
                            supply_demand_data,
                            target_date=today,
                            batch_size=25  # 수급 데이터는 더 작은 배치 크기
                        )
                        
                        if not scheduler_mode:
                            self.logger.info(f"배치 {i//batch_size + 1} 수급 데이터 UPSERT 완료: {len(supply_demand_data)}건")
                        
                    except Exception as e:
                        if not scheduler_mode:
                            self.logger.error(f"배치 {i//batch_size + 1} 수급 데이터 UPSERT 실패: {e}")
                
                # 진행률 로그 (스케줄러 모드에서는 5% 단위로만)
                progress = min((i + batch_size) / len(all_symbols) * 100, 100)
                if scheduler_mode:
                    # 스케줄러 모드에서는 5% 단위로만 로그
                    if progress % 5 < (batch_size / len(all_symbols) * 100):
                        self.logger.info(f"[스케줄러] 당일 수급 데이터 업데이트 진행률: {progress:.0f}%")
                else:
                    self.logger.info(f"당일 수급 데이터 업데이트 진행률: {progress:.1f}% ({updated_stocks}/{total_stocks})")
                
                # API 호출 제한 준수 (수급 데이터는 더 긴 간격)
                if i + batch_size < len(all_symbols):
                    await asyncio.sleep(0.8)  # 수급 데이터 API 제약
            
            if scheduler_mode:
                self.logger.info(f"[스케줄러] 당일 수급 데이터 업데이트 완료: {updated_stocks}/{total_stocks}개 종목 (오류: {errors}개)")
            else:
                self.logger.info(f"당일 수급 데이터 업데이트 완료: {updated_stocks}개 종목")
            
            return {
                "message": f"당일 수급 데이터 업데이트 완료: {updated_stocks}개 종목",
                "total_stocks": total_stocks,
                "updated_stocks": updated_stocks,
                "errors": errors,
                "date": today_str,
                "status": "completed"
            }
            
        except Exception as e:
            error_msg = f"당일 수급 데이터 업데이트 실패: {e}"
            if scheduler_mode:
                self.logger.error(f"[스케줄러] {error_msg}")
            else:
                self.logger.error(error_msg)
            return {
                "message": error_msg,
                "total_stocks": 0,
                "updated_stocks": 0,
                "errors": 1,
                "status": "failed"
            }
        finally:
            # 스케줄러 모드에서 변경한 로그 레벨 복원
            if scheduler_mode and original_log_level is not None and hasattr(self.kiwoom_client, 'logger'):
                self.kiwoom_client.logger.setLevel(original_log_level)
            # 스케줄러 모드에서 변경한 설정 복원
            if scheduler_mode:
                self.kiwoom_client._scheduler_mode = False
    
    # ===========================================
    # 수정주가 관련 메서드들
    # ===========================================
    
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
    
    def get_stored_adjustment_info(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        메모리에서 종목의 수정주가 정보 조회
        
        Args:
            symbol (str): 종목코드
            
        Returns:
            Optional[Dict[str, Any]]: 수정주가 정보 또는 None
        """
        try:
            return self._adjustment_data_cache["adjusted_stocks"].get(symbol)
        except Exception as e:
            self.logger.error(f"수정주가 정보 조회 실패 [{symbol}]: {e}")
            return None
    
    def store_adjustment_info(self, symbol: str, adjustment_info: Dict[str, Any]) -> None:
        """
        메모리에 종목의 수정주가 정보 저장
        
        Args:
            symbol (str): 종목코드
            adjustment_info (Dict[str, Any]): 수정주가 정보
        """
        try:
            self._adjustment_data_cache["adjusted_stocks"][symbol] = adjustment_info
            self.logger.debug(f"수정주가 정보 저장 완료 [{symbol}]: {adjustment_info}")
        except Exception as e:
            self.logger.error(f"수정주가 정보 저장 실패 [{symbol}]: {e}")
    
    def clear_adjustment_cache(self) -> None:
        """수정주가 캐시 초기화"""
        try:
            self._adjustment_data_cache["adjusted_stocks"].clear()
            self._adjustment_data_cache["last_check_date"] = None
            self.logger.info("수정주가 캐시 초기화 완료")
        except Exception as e:
            self.logger.error(f"수정주가 캐시 초기화 실패: {e}")

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
            
            # 안전한 변환 함수들 (공통 함수 사용)
            
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
