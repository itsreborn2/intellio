from celery import Celery
from celery.schedules import crontab
from kombu import Queue, Exchange
from celery.signals import task_success, task_failure
import logging
from common.core.config import settings

logger = logging.getLogger(__name__)

# Celery 앱 초기화
celery = Celery(
    "common",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["common.workers.project", "common.workers.system"]
)

@task_success.connect
def handle_task_success(sender=None, **kwargs):
    """태스크 성공 시 처리"""
    if sender and hasattr(sender, 'request'):
        logger.info(f"Task {sender.request.id} completed successfully")

@task_failure.connect
def handle_task_failure(sender=None, exception=None, **kwargs):
    """태스크 실패 시 처리"""
    if sender and hasattr(sender, 'request'):
        logger.error(f"Task {sender.request.id} failed: {str(exception)}")

# 태스크 자동 발견
celery.autodiscover_tasks()

# Exchange 정의
main_exchange = Exchange('common-main', type='direct')
system_exchange = Exchange('common-system', type='direct')

# 큐 정의
celery.conf.task_queues = [
    Queue('common-main', main_exchange, routing_key='common-main'),
    Queue('common-system', system_exchange, routing_key='common-system'),
]

# 라우팅 설정
celery.conf.task_routes = {
    "common.workers.project.*": {"queue": "common-main", "routing_key": "common-main"},
    "common.workers.system.*": {"queue": "common-system", "routing_key": "common-system"},
}

# Celery 설정
celery.conf.broker_connection_retry_on_startup = True
celery.conf.update(
    # 브로커 설정
    broker_transport_options={
        'visibility_timeout': 3600,  # 1시간
        'socket_timeout': 30,
        'socket_connect_timeout': 30,
        'socket_keepalive': True,
        'retry_on_timeout': True
    },
    
    # 워커 설정
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=50,
    worker_max_memory_per_child=200000,  # 200MB
    
    # 태스크 설정
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=300,  # 5분
    task_soft_time_limit=300,  # 5분
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    
    # 결과 설정
    result_backend=settings.REDIS_URL,
    result_expires=300,  # 5분
    
    # 로깅 설정
    worker_redirect_stdouts=False,
    worker_redirect_stdouts_level='INFO',
)

# 스케줄러 설정
celery.conf.beat_schedule = {
    "cleanup-expired-projects": {
        "task": "common.workers.project.cleanup_expired_projects",
        "schedule": crontab(hour="0", minute="0"),  # 매일 자정에 실행
    },
    "update-retention-periods": {
        "task": "common.workers.project.update_retention_periods",
        "schedule": crontab(hour="*", minute="0"),  # 매시간 실행
    },
    "system-health-check": {
        "task": "common.workers.system.check_system_health",
        "schedule": crontab(minute="*/5"),  # 5분마다 실행
    },
    "cleanup-expired-sessions": {
        "task": "common.workers.system.cleanup_expired_sessions",
        "schedule": crontab(hour="*/6"),  # 6시간마다 실행
    },
} 