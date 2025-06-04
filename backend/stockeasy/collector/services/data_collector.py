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
    ChartDataPoint
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
                    "change_rate": round(((current_price - base_price) / base_price) * 100, 2),
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
                "change_rate": round(((current_price - base_price) / base_price) * 100, 2),
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
    
    async def get_supply_demand_data(self, symbol: str, date_str: str) -> Optional[Dict[str, Any]]:
        """수급 데이터 조회"""
        try:
            # 키움 API에서 조회
            if self.settings.KIWOOM_APP_KEY != "test_api_key":
                supply_demand = await self.kiwoom_client.get_supply_demand(symbol, date_str)
                if supply_demand:
                    return {
                        "date": supply_demand.dt,
                        "symbol": supply_demand.stk_cd,
                        "foreign_amount": supply_demand.frg_amt,
                        "institution_amount": supply_demand.ins_amt,
                        "personal_amount": supply_demand.pns_amt
                    }
            
            # 더미 데이터 반환
            return {
                "date": date_str,
                "symbol": symbol,
                "foreign_amount": "1000000000",
                "institution_amount": "-500000000",
                "personal_amount": "200000000"
            }
            
        except Exception as e:
            self.logger.error(f"수급 데이터 조회 실패 [{symbol}, {date_str}]: {e}")
            return None
    
    async def get_chart_data(self, symbol: str, period: str, interval: str) -> Optional[ChartDataResponse]:
        """차트 데이터 조회"""
        try:
            # TODO: 키움 API에서 차트 데이터 조회 (현재는 더미 데이터)
            dummy_data = await self._generate_dummy_chart_data(symbol, period, interval)
            return dummy_data
            
        except Exception as e:
            self.logger.error(f"차트 데이터 조회 실패 [{symbol}, {period}, {interval}]: {e}")
            return None
    
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
                    "change_rate": round(((current_price - base_price) / base_price) * 100, 2),
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
    
    async def _generate_dummy_chart_data(self, symbol: str, period: str, interval: str) -> ChartDataResponse:
        """더미 차트 데이터 생성"""
        # 기간에 따른 데이터 포인트 수 결정
        if period == "1d":
            points = 390  # 1일 1분봉
            start_time = datetime.now().replace(hour=9, minute=0, second=0, microsecond=0)
            time_delta = timedelta(minutes=1)
        elif period == "1w":
            points = 7  # 1주 일봉
            start_time = datetime.now() - timedelta(days=7)
            time_delta = timedelta(days=1)
        else:
            points = 30  # 1개월 일봉
            start_time = datetime.now() - timedelta(days=30)
            time_delta = timedelta(days=1)
        
        # 더미 데이터 생성
        base_price = 70000 if symbol == "005930" else 50000
        data_points = []
        
        for i in range(points):
            timestamp = start_time + (time_delta * i)
            
            # 간단한 랜덤 워크
            price_change = (hash(f"{symbol}{i}") % 200 - 100) * 10
            current_price = base_price + price_change
            
            data_points.append(ChartDataPoint(
                timestamp=timestamp,
                open=current_price,
                high=current_price + (hash(f"{symbol}{i}high") % 100) * 10,
                low=current_price - (hash(f"{symbol}{i}low") % 100) * 10,
                close=current_price + (hash(f"{symbol}{i}close") % 50 - 25) * 10,
                volume=hash(f"{symbol}{i}vol") % 1000000
            ))
        
        # 종목명 조회
        symbol_name = await self.cache_manager.get_symbol_name(symbol) or "Unknown"
        
        return ChartDataResponse(
            symbol=symbol,
            name=symbol_name,
            period=period,
            interval=interval,
            data=data_points,
            total_count=len(data_points)
        )
    
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
                    "change_rate": 0.59 + (hash(str(datetime.now().second)) % 200 - 100) / 100
                },
                {
                    "index_code": "KOSDAQ",
                    "index_name": "코스닥",
                    "current_value": 850.5 + (hash(str(datetime.now().hour)) % 50 - 25),
                    "change_amount": -8.3 + (hash(str(datetime.now().minute)) % 10 - 5),
                    "change_rate": -0.97 + (hash(str(datetime.now().second)) % 100 - 50) / 100
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
