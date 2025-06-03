"""
스케줄러 서비스
종목 정보 자동 업데이트 등의 스케줄링 작업 관리
"""
import asyncio
from datetime import datetime, time
from typing import Optional, Dict, Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR

from loguru import logger
from stockeasy.collector.core.config import get_settings
from stockeasy.collector.core.logger import LoggerMixin, LogContext, log_scheduler_job

settings = get_settings()


class SchedulerService(LoggerMixin):
    """스케줄러 서비스"""
    
    def __init__(self, data_collector=None, cache_manager=None):
        self.scheduler = AsyncIOScheduler(timezone="Asia/Seoul")
        self.data_collector = data_collector
        self.cache_manager = cache_manager
        
        self._is_running = False
        self._job_stats = {
            "total_jobs": 0,
            "successful_jobs": 0,
            "failed_jobs": 0,
            "last_stock_update": None,
            "last_etf_update": None
        }
        
        # 이벤트 리스너 등록
        self.scheduler.add_listener(self._job_executed_listener, EVENT_JOB_EXECUTED)
        self.scheduler.add_listener(self._job_error_listener, EVENT_JOB_ERROR)
        
        logger.info("스케줄러 서비스 초기화 완료")
    
    async def start(self) -> None:
        """스케줄러 시작"""
        if self._is_running:
            logger.warning("스케줄러가 이미 실행 중입니다")
            return
        
        with LogContext(self.logger, "스케줄러 시작") as ctx:
            try:
                # 스케줄 작업 등록
                await self._register_jobs()
                
                # 스케줄러 시작
                self.scheduler.start()
                self._is_running = True
                
                ctx.log_progress("스케줄러 시작 완료")
                
            except Exception as e:
                ctx.logger.error(f"스케줄러 시작 실패: {e}")
                raise
    
    async def shutdown(self) -> None:
        """스케줄러 종료"""
        if not self._is_running:
            return
        
        with LogContext(self.logger, "스케줄러 종료") as ctx:
            try:
                self.scheduler.shutdown(wait=True)
                self._is_running = False
                
                ctx.log_progress("스케줄러 종료 완료")
                
            except Exception as e:
                ctx.logger.error(f"스케줄러 종료 중 오류: {e}")
    
    async def _register_jobs(self) -> None:
        """스케줄 작업 등록"""
        logger.info("스케줄 작업 등록 시작")
        
        # 1. 매일 아침 7시 30분: 전체 종목 리스트 업데이트
        self.scheduler.add_job(
            func=self._update_stock_list_job,
            trigger=CronTrigger(hour=7, minute=30),
            id="daily_stock_list_update",
            name="일일 종목 리스트 업데이트",
            replace_existing=True,
            max_instances=1
        )
        
        # 2. 매일 오전 8시: ETF 구성종목 업데이트
        self.scheduler.add_job(
            func=self._update_etf_components_job,
            trigger=CronTrigger(hour=8, minute=0),
            id="daily_etf_update",
            name="일일 ETF 구성종목 업데이트",
            replace_existing=True,
            max_instances=1
        )
        
        # 3. 매시간: 캐시 정리
        self.scheduler.add_job(
            func=self._cleanup_cache_job,
            trigger=CronTrigger(minute=0),  # 매시간 정각
            id="hourly_cache_cleanup",
            name="시간별 캐시 정리",
            replace_existing=True,
            max_instances=1
        )
        
        # 4. 주말 오후 6시: 전체 캐시 새로고침
        self.scheduler.add_job(
            func=self._full_cache_refresh_job,
            trigger=CronTrigger(day_of_week='sat', hour=18, minute=0),
            id="weekly_cache_refresh",
            name="주간 전체 캐시 새로고침",
            replace_existing=True,
            max_instances=1
        )
        
        logger.info("스케줄 작업 등록 완료")
    
    @log_scheduler_job("일일 종목 리스트 업데이트")
    async def _update_stock_list_job(self) -> None:
        """종목 리스트 업데이트 작업"""
        try:
            if not self.data_collector:
                logger.warning("데이터 수집 서비스가 없습니다")
                return
            
            # 키움 API에서 전체 종목 리스트 조회 (강제 새로고침)
            kiwoom_client = self.data_collector.kiwoom_client
            stock_list = await kiwoom_client.get_all_stock_list(force_refresh=True)
            stock_list_for_stockai = await self.kiwoom_client.get_stock_list_for_stockai(force_refresh=True)

            # 캐시에 저장
            if self.cache_manager:
                await self.cache_manager.set_cache(
                    "all_stock_list", 
                    stock_list, 
                    ttl=86400  # 24시간
                )
                
                # 캐시에 저장(stock ai)
                await self.cache_manager.set_cache(
                    "all_stock_list_for_stockai", 
                    stock_list_for_stockai, 
                    ttl=86400  # 24시간
                )

            
            # 통계 업데이트
            self._job_stats["last_stock_update"] = datetime.now()
            
            logger.success(f"종목 리스트 업데이트 완료: {len(stock_list)}개 종목")
            logger.success(f"[stock ai] 종목 리스트 업데이트 완료: {len(stock_list_for_stockai)}개 종목")

        except Exception as e:
            logger.error(f"종목 리스트 업데이트 실패: {e}")
            raise
    
    @log_scheduler_job("일일 ETF 구성종목 업데이트")
    async def _update_etf_components_job(self) -> None:
        """ETF 구성종목 업데이트 작업"""
        try:
            if not self.data_collector:
                logger.warning("데이터 수집 서비스가 없습니다")
                return
            
            # ETF 크롤러를 통한 구성종목 업데이트
            etf_crawler = self.data_collector.etf_crawler
            major_etf_list = etf_crawler.get_major_etf_list()
            
            updated_count = 0
            for etf_code, etf_name in major_etf_list.items():
                try:
                    components = await etf_crawler.get_etf_components(etf_code)
                    if components:
                        # 캐시에 저장
                        if self.cache_manager:
                            await self.cache_manager.set_etf_components(etf_code, components)
                        updated_count += 1
                    
                    # API 호출 간격 조절
                    await asyncio.sleep(1)
                    
                except Exception as e:
                    logger.error(f"ETF {etf_code} 구성종목 업데이트 실패: {e}")
                    continue
            
            # 통계 업데이트
            self._job_stats["last_etf_update"] = datetime.now()
            
            logger.success(f"ETF 구성종목 업데이트 완료: {updated_count}개 ETF")
            
        except Exception as e:
            logger.error(f"ETF 구성종목 업데이트 실패: {e}")
            raise
    
    @log_scheduler_job("시간별 캐시 정리")
    async def _cleanup_cache_job(self) -> None:
        """캐시 정리 작업"""
        try:
            if not self.cache_manager:
                return
            
            # 만료된 캐시 정리
            result = await self.cache_manager.cleanup_expired_cache()
            
            logger.info(f"캐시 정리 완료: {result}")
            
        except Exception as e:
            logger.error(f"캐시 정리 실패: {e}")
    
    @log_scheduler_job("주간 전체 캐시 새로고침")
    async def _full_cache_refresh_job(self) -> None:
        """전체 캐시 새로고침 작업"""
        try:
            if not self.data_collector:
                return
            
            # 강제 캐시 갱신
            await self.data_collector.force_cache_refresh()
            
            logger.success("전체 캐시 새로고침 완료")
            
        except Exception as e:
            logger.error(f"전체 캐시 새로고침 실패: {e}")
    
    def _job_executed_listener(self, event) -> None:
        """작업 성공 이벤트 리스너"""
        self._job_stats["total_jobs"] += 1
        self._job_stats["successful_jobs"] += 1
        
        logger.info(f"스케줄 작업 실행 완료: {event.job_id}")
    
    def _job_error_listener(self, event) -> None:
        """작업 실패 이벤트 리스너"""
        self._job_stats["total_jobs"] += 1
        self._job_stats["failed_jobs"] += 1
        
        logger.error(f"스케줄 작업 실행 실패: {event.job_id} - {event.exception}")
    
    def get_job_stats(self) -> Dict[str, Any]:
        """작업 통계 조회"""
        return {
            **self._job_stats,
            "is_running": self._is_running,
            "scheduled_jobs": [
                {
                    "id": job.id,
                    "name": job.name,
                    "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None
                }
                for job in self.scheduler.get_jobs()
            ]
        }
    
    async def trigger_stock_update_now(self) -> None:
        """즉시 종목 리스트 업데이트 실행"""
        logger.info("수동 종목 리스트 업데이트 실행")
        await self._update_stock_list_job()
    
    async def trigger_etf_update_now(self) -> None:
        """즉시 ETF 구성종목 업데이트 실행"""
        logger.info("수동 ETF 구성종목 업데이트 실행")
        await self._update_etf_components_job()
    
    def is_running(self) -> bool:
        """스케줄러 실행 상태 확인"""
        return self._is_running 