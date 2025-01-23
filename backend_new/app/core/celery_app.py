from celery import Celery
from celery.schedules import crontab
from kombu import Queue, Exchange
from celery.signals import task_success, task_failure
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)

# 문서 상태 상수
DOCUMENT_STATUS = {
    'REGISTERED': 'REGISTERED',
    'UPLOADING': 'UPLOADING',
    'UPLOADED': 'UPLOADED',
    'PROCESSING': 'PROCESSING',
    'COMPLETED': 'COMPLETED',
    'PARTIAL': 'PARTIAL',
    'ERROR': 'ERROR',
    'DELETED': 'DELETED'
}

# Celery 앱 초기화
celery = Celery(
    "app",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["app.workers.document", "app.workers.project", "app.workers.rag"]
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
    "app.workers.document.*": {"queue": "document-processing", "routing_key": "document-processing"},
    "app.workers.project.*": {"queue": "main-queue", "routing_key": "main-queue"},
    "app.workers.rag.*": {"queue": "rag-processing", "routing_key": "rag-processing"},
    "app.worker.celery_worker:process_document_chucking": "main-queue"
}

# Celery 설정
celery.conf.broker_connection_retry_on_startup = True  # 시작 시 브로커 연결 재시도 활성화
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
    result_backend='redis://localhost:6379/0',
    result_expires=300,  # 5분
    
    # 로깅 설정
    worker_redirect_stdouts=False,
    worker_redirect_stdouts_level='INFO',
)

# 스케줄러 설정
celery.conf.beat_schedule = {
    "cleanup-expired-projects": {
        "task": "app.workers.project.cleanup_expired_projects",
        "schedule": crontab(hour="0", minute="0"),  # 매일 자정에 실행
    },
    "update-retention-periods": {
        "task": "app.workers.project.update_retention_periods",
        "schedule": crontab(hour="*", minute="0"),  # 매시간 실행
    },
}
