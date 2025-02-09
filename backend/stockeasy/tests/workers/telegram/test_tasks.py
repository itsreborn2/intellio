"""텔레그램 워커 태스크 테스트

이 모듈은 텔레그램 메시지 수집 및 임베딩 태스크를 테스트합니다.
주요 테스트 항목:
1. 메시지 임베딩 태스크
2. 메시지 수집 태스크
3. 메시지 정리 태스크
"""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, patch, AsyncMock, MagicMock
import asyncio

from app.workers.telegram.collector_tasks import embed_messages, collect_messages, cleanup_daily_messages
from app.workers.telegram.embedding_tasks import process_new_messages
from app.models.telegram_message import TelegramMessage
from app.services.telegram.embedding import TelegramEmbeddingService
from app.services.telegram.collector import CollectorService

@pytest.fixture
def sample_messages():
    """테스트용 메시지 리스트 fixture"""
    return [
        TelegramMessage(
            message_id=i,
            channel_id="test_channel",
            channel_title="Test Channel",
            message_type="text",
            sender_id="user123",
            sender_name="Test User",
            message_text=f"Test message {i}",
            created_at=datetime.now(timezone.utc),
            collected_at=datetime.now(timezone.utc),
            is_embedded=False,
            has_media=False,
            has_document=False
        )
        for i in range(1, 4)
    ]

@pytest.mark.asyncio
async def test_process_new_messages(sample_messages):
    """새 메시지 임베딩 처리 태스크 테스트"""
    # DB 세션 모의 객체 생성
    mock_session = MagicMock()
    mock_session.query.return_value.filter.return_value.limit.return_value.all.return_value = sample_messages
    
    # 임베딩 서비스 모의 객체 생성
    mock_embedding_service = AsyncMock()
    mock_embedding_service.embed_telegram_messages_batch.return_value = True
    
    # 태스크 객체 생성 및 속성 설정
    task = process_new_messages
    task._db = mock_session
    task._embedding_service = mock_embedding_service
    
    # 태스크 실행
    result = await task(batch_size=10)
    
    # 검증
    assert result == len(sample_messages)
    mock_embedding_service.embed_telegram_messages_batch.assert_called_once_with(sample_messages)
    for msg in sample_messages:
        assert msg.is_embedded is True

@pytest.mark.asyncio
async def test_embed_messages():
    """메시지 임베딩 태스크 테스트"""
    message_ids = [1, 2, 3]
    
    # DB 세션 모의 객체 생성
    mock_session = MagicMock()
    mock_messages = [
        TelegramMessage(message_id=i, channel_id="test", message_text=f"test {i}")
        for i in message_ids
    ]
    mock_session.query.return_value.filter.return_value.all.return_value = mock_messages
    
    # 임베딩 서비스 모의 객체 생성
    mock_embedding_service = AsyncMock()
    mock_embedding_service.embed_telegram_messages_batch.return_value = True
    
    # 태스크 객체 생성 및 속성 설정
    task = embed_messages
    task._db = mock_session
    task._embedding_service = mock_embedding_service
    
    # 태스크 실행
    result = task(message_ids)
    
    # 검증
    assert result is True
    for msg in mock_messages:
        assert msg.is_embedded is True
    mock_session.commit.assert_called_once()

@pytest.mark.asyncio
async def test_collect_messages():
    """메시지 수집 태스크 테스트"""
    # 수집 서비스 모의 객체 생성
    mock_collector = AsyncMock()
    collected_messages = [
        {"message_id": i, "channel_id": "test"} for i in range(1, 4)
    ]
    mock_collector.collect_all_channels.return_value = collected_messages
    
    # DB 세션 모의 객체 생성
    mock_session = MagicMock()
    
    with patch('app.workers.telegram.collector_tasks.CollectorService', return_value=mock_collector):
        # 태스크 객체 생성 및 속성 설정
        task = collect_messages
        task._db = mock_session
        
        # 태스크 실행
        result = task()
        
        # 검증
        assert result == len(collected_messages)
        mock_collector.collect_all_channels.assert_called_once()

@pytest.mark.asyncio
async def test_cleanup_daily_messages():
    """메시지 정리 태스크 테스트"""
    # 현재 시간 기준 설정
    today_midnight = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    ninety_days_ago = today_midnight - timedelta(days=90)
    
    # 테스트용 메시지 생성
    old_messages = [
        TelegramMessage(
            message_id=i,
            channel_id="test_channel",
            created_at=ninety_days_ago - timedelta(days=1),
            collected_at=ninety_days_ago - timedelta(days=1)
        )
        for i in range(1, 4)
    ]
    
    # DB 세션 모의 객체 생성
    mock_session = MagicMock()
    mock_session.query.return_value.filter.return_value.all.return_value = old_messages
    mock_session.query.return_value.filter.return_value.delete.return_value = len(old_messages)
    
    # 임베딩 서비스 모의 객체 생성
    mock_embedding_service = AsyncMock()
    mock_embedding_service.delete_channel_messages.return_value = True
    
    # 태스크 객체 생성 및 속성 설정
    task = cleanup_daily_messages
    task._db = mock_session
    task._embedding_service = mock_embedding_service
    
    # 태스크 실행
    result = task()
    
    # 검증
    assert result == len(old_messages)
    mock_embedding_service.delete_channel_messages.assert_called_with(
        channel_id="test_channel",
        before_date=ninety_days_ago
    )
    mock_session.commit.assert_called_once() 