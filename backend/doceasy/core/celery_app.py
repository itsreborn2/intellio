import os
from celery import Celery
from celery.schedules import crontab
from kombu import Queue, Exchange
from celery.signals import task_success, task_failure
import logging

logger = logging.getLogger(__name__)

# Redis 연결 설정
redis_host = os.getenv("REDIS_HOST", "redis")
redis_port = os.getenv("REDIS_PORT", "6379")
redis_url = f"redis://{redis_host}:{redis_port}/0"

# 환경 변수 로깅
logger.info("=== Celery Environment Variables ===")
logger.info(f"REDIS_HOST: {redis_host}")
logger.info(f"REDIS_PORT: {redis_port}")
logger.info(f"REDIS_URL: {redis_url}")
logger.info("================================")

# Celery 앱 초기화
celery = Celery(
    "app",
    broker=redis_url,
    backend=redis_url,
    include=["doceasy.workers.document", "doceasy.workers.project", "doceasy.workers.rag"]
)

logger.info(f"Using Redis URL: {redis_url}")

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
document_exchange = Exchange('document-processing', type='direct')
main_exchange = Exchange('main-queue', type='direct')
rag_exchange = Exchange('rag-processing', type='direct')
# 큐 정의
celery.conf.task_queues = [
    Queue('document-processing', document_exchange, routing_key='document-processing'),
    Queue('main-queue', main_exchange, routing_key='main-queue'),
    Queue('rag-processing', rag_exchange, routing_key='rag-processing'),
]

# 라우팅 설정
celery.conf.task_routes = {
    "doceasy.workers.document.*": {"queue": "document-processing", "routing_key": "document-processing"},
    "doceasy.workers.project.*": {"queue": "main-queue", "routing_key": "main-queue"},
    "doceasy.workers.rag.*": {"queue": "rag-processing", "routing_key": "rag-processing"},
    "doceasy.worker.celery_worker:process_document_chucking": "main-queue"
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
    task_time_limit=300,  # 1시간
    task_soft_time_limit=300,  # 50분
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    
    # 결과 설정
    result_backend=redis_url,
    result_expires=300,  # 5분
    
    # 로깅 설정
    worker_redirect_stdouts=False,
    worker_redirect_stdouts_level='INFO',
)

# 스케줄러 설정은 common/core/celery_app.py로 이동됨
# 프로젝트 관리와 관련된 공통 작업은 common에서 중앙 집중적으로 관리
