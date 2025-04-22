import common.models  # 추가: 모든 모델 관계를 로드

from celery import Celery
from celery.schedules import crontab
from kombu import Queue, Exchange
from celery.signals import task_success, task_failure
import logging
from stockeasy.core.config import stockeasy_settings

logger = logging.getLogger(__name__)

# Celery 앱 초기화
celery = Celery(
    "stockeasy_worker",
    broker=stockeasy_settings.REDIS_URL,
    backend=stockeasy_settings.REDIS_URL,
    include=[
        "stockeasy.workers.telegram.collector_tasks",
        "stockeasy.workers.telegram.embedding_tasks",
        "stockeasy.workers.statistics.daily_tasks"
    ]
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
celery.conf.enable_utc = False  # UTC 비활성화
celery.conf.timezone = "Asia/Seoul"  # 서울 시간으로 설정

# Exchange 정의
telegram_exchange = Exchange('telegram-processing', type='direct')
embedding_exchange = Exchange('embedding-processing', type='direct')

# 큐 정의
celery.conf.task_queues = [
    Queue('telegram-processing', telegram_exchange, routing_key='telegram-processing'),
    Queue('embedding-processing', embedding_exchange, routing_key='embedding-processing'),
]

# 라우팅 설정
celery.conf.task_routes = {
    "stockeasy.workers.telegram.collector_tasks.*": {
        "queue": "telegram-processing",
        "routing_key": "telegram-processing"
    },
    "stockeasy.workers.telegram.embedding_tasks.*": {
        "queue": "embedding-processing",
        "routing_key": "embedding-processing"
    }
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
    result_backend=stockeasy_settings.CELERY_RESULT_BACKEND,
    result_expires=300,  # 5분
    
    # 로깅 설정
    worker_redirect_stdouts=False,
    worker_redirect_stdouts_level='INFO',
)

# 스케줄러 설정
celery.conf.beat_schedule = {
    'collect-telegram-messages': {
        'task': 'stockeasy.workers.telegram.collector_tasks.collect_messages',
        'schedule': crontab(minute='*/2'),  # 2분마다 실행
    },
    'process-new-messages': {
        'task': 'stockeasy.workers.telegram.embedding_tasks.process_new_messages',
        'schedule': crontab(minute='*/2'),  # 2분마다 실행
    },
    'cleanup-daily-messages': {
        'task': 'stockeasy.workers.telegram.collector_tasks.cleanup_daily_messages',
        'schedule': crontab(hour=23, minute=59),  # 매일 23:59에 실행
    },
    'generate-daily-statistics': {
        'task': 'stockeasy.workers.statistics.daily_tasks.generate_daily_stats',
        'schedule': crontab(hour=23, minute=55),  # 매일 23:55에 실행
    }
}
