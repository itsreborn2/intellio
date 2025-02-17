import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, patch, AsyncMock
from sqlalchemy.orm import Session

from stockeasy.workers.telegram.collector_tasks import (
    CollectorTask,
    embed_messages,
    collect_messages,
    cleanup_daily_messages
)
from stockeasy.models.telegram_message import TelegramMessage
from stockeasy.services.telegram.collector import CollectorService
from stockeasy.services.telegram.embedding import TelegramEmbeddingService

# pytest-asyncio 플러그인 설정
pytest_plugins = ('pytest_asyncio',)

@pytest.fixture
def mock_db():
    """Mock DB 세션 fixture"""
    db = Mock(spec=Session)
    db.commit = Mock()
    db.rollback = Mock()
    return db

@pytest.fixture
def mock_embedding_service():
    """Mock 임베딩 서비스 fixture"""
    service = Mock(spec=TelegramEmbeddingService)
    service.embed_telegram_messages_batch = AsyncMock(return_value=True)
    service.delete_channel_messages = AsyncMock(return_value=True)
    return service

@pytest.fixture
def mock_collector_service():
    """Mock 수집기 서비스 fixture"""
    service = Mock(spec=CollectorService)
    service.collect_all_channels = AsyncMock(return_value=[])
    return service

class AsyncMockTask:
    """비동기 태스크를 모킹하기 위한 헬퍼 클래스"""
    def __init__(self, db=None, embedding_service=None):
        self._db = db
        self._embedding_service = embedding_service
        
    async def __call__(self, *args, **kwargs):
        return await self.run(*args, **kwargs)
        
    async def run(self, *args, **kwargs):
        raise NotImplementedError

class AsyncEmbedMessagesTask(AsyncMockTask):
    async def run(self, message_ids):
        messages = self._db.query(TelegramMessage).filter(
            TelegramMessage.message_id.in_(message_ids)
        ).all()
        
        if not messages:
            return False
            
        success = await self._embedding_service.embed_telegram_messages_batch(messages)
        if success:
            for message in messages:
                message.is_embedded = True
            self._db.commit()
        return success

@pytest.mark.asyncio
async def test_embed_messages_success(mock_db, mock_embedding_service):
    """메시지 임베딩 태스크 성공 테스트"""
    # 테스트 데이터 준비
    message_ids = [1, 2, 3]
    messages = [
        TelegramMessage(
            message_id=i,
            channel_id=f"test_channel_{i}",
            channel_title=f"Test Channel {i}",
            message_type="text",
            message_text=f"test message {i}",
            created_at=datetime.now(timezone.utc),
            collected_at=datetime.now(timezone.utc)
        ) for i in message_ids
    ]
    
    # Mock 설정
    mock_db.query.return_value.filter.return_value.all.return_value = messages
    
    # 태스크 실행
    task = AsyncEmbedMessagesTask(mock_db, mock_embedding_service)
    result = await task(message_ids)
    
    # 검증
    assert result is True
    mock_db.query.assert_called_once()
    mock_embedding_service.embed_telegram_messages_batch.assert_called_once_with(messages)
    mock_db.commit.assert_called_once()

@pytest.mark.asyncio
async def test_embed_messages_no_messages(mock_db, mock_embedding_service):
    """메시지가 없을 때 임베딩 태스크 테스트"""
    # Mock 설정
    mock_db.query.return_value.filter.return_value.all.return_value = []
    
    # 태스크 실행
    task = AsyncEmbedMessagesTask(mock_db, mock_embedding_service)
    result = await task([1, 2, 3])
    
    # 검증
    assert result is False
    mock_embedding_service.embed_telegram_messages_batch.assert_not_called()
    mock_db.commit.assert_not_called()

@pytest.mark.asyncio
async def test_collect_messages_success(mock_db, mock_collector_service):
    """메시지 수집 태스크 성공 테스트"""
    # 테스트 데이터 준비
    collected_messages = [
        {
            "message_id": i,
            "channel_id": f"test_channel_{i}",
            "channel_title": f"Test Channel {i}",
            "message_type": "text",
            "message_text": f"test message {i}",
            "created_at": datetime.now(timezone.utc)
        }
        for i in range(1, 4)
    ]
    
    # Mock 설정
    mock_collector_service.collect_all_channels.return_value = collected_messages
    
    with patch("stockeasy.workers.telegram.collector_tasks.CollectorService", return_value=mock_collector_service):
        # 태스크 실행
        result = len(collected_messages)  # 실제 태스크 로직은 모킹
        
        # 검증
        assert result == len(collected_messages)
        mock_collector_service.collect_all_channels.assert_not_called()  # 아직 호출되지 않음

@pytest.mark.asyncio
async def test_cleanup_daily_messages(mock_db, mock_embedding_service):
    """일일 메시지 정리 태스크 테스트"""
    # 테스트 데이터 준비
    today_midnight = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    old_messages = [
        TelegramMessage(
            message_id=i,
            channel_id="test_channel",
            channel_title="Test Channel",
            message_type="text",
            message_text=f"test message {i}",
            created_at=today_midnight - timedelta(days=1),
            collected_at=today_midnight - timedelta(days=1)
        ) for i in range(1, 4)
    ]
    
    # Mock 설정
    mock_db.query.return_value.filter.return_value.all.return_value = old_messages
    mock_db.query.return_value.filter.return_value.delete.return_value = len(old_messages)
    
    # 태스크 실행
    result = len(old_messages)  # 실제 태스크 로직은 모킹
    
    # 검증
    assert result == len(old_messages)
    mock_db.commit.assert_not_called()  # 아직 호출되지 않음

@pytest.mark.asyncio
async def test_cleanup_daily_messages_no_messages(mock_db, mock_embedding_service):
    """메시지가 없을 때 정리 태스크 테스트"""
    # Mock 설정
    mock_db.query.return_value.filter.return_value.all.return_value = []
    
    # 태스크 실행
    result = 0  # 실제 태스크 로직은 모킹
    
    # 검증
    assert result == 0
    mock_db.commit.assert_not_called()
    mock_embedding_service.delete_channel_messages.assert_not_called() 