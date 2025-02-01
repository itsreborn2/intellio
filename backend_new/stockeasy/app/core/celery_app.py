from celery import Celery
from celery.schedules import crontab
from kombu import Queue, Exchange
from celery.signals import task_success, task_failure
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)

# Celery 앱 초기화
celery = Celery(
    "stockeasy",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.workers.telegram.collector_tasks", "app.workers.telegram.embedding_tasks"]
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
telegram_exchange = Exchange('telegram', type='direct')

# 큐 정의
celery.conf.task_queues = [
    Queue('telegram', telegram_exchange, routing_key='telegram'),
]

# 라우팅 설정
celery.conf.task_routes = {
    "app.workers.telegram.*": {"queue": "telegram", "routing_key": "telegram"},
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
    task_soft_time_limit=240,  # 4분
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    
    # 결과 설정
    result_expires=300,  # 5분
    
    # 로깅 설정
    worker_redirect_stdouts=False,
    worker_redirect_stdouts_level='INFO',
)

# 스케줄러 설정
celery.conf.beat_schedule = {
    'collect-telegram-messages': {
        'task': 'app.workers.telegram.collector_tasks.collect_messages',
        'schedule': crontab(minute='*/5', hour='7-19'),  # 07:00~19:00 5분마다
    },
    'collect-telegram-messages-night': {
        'task': 'app.workers.telegram.collector_tasks.collect_messages',
        'schedule': crontab(minute='0', hour='20-23,0-6'),  # 20:00~06:00 1시간마다
    },
    'cleanup-telegram-messages': {
        'task': 'app.workers.telegram.collector_tasks.cleanup_daily_messages',
        'schedule': crontab(minute=59, hour=23),  # 매일 23:59
    }
}
