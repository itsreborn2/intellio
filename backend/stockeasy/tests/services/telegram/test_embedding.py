"""텔레그램 임베딩 서비스 테스트

이 모듈은 TelegramEmbeddingService의 기능을 테스트합니다.
주요 테스트 항목:
1. 메타데이터 생성
2. 메시지 임베딩
3. 메시지 검색
4. 메시지 삭제
"""

import pytest
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any
from unittest.mock import Mock, patch, AsyncMock

from app.models.telegram_message import TelegramMessage
from app.services.telegram.embedding import TelegramEmbeddingService
from app.core.config import settings

@pytest.fixture
def embedding_service():
    """임베딩 서비스 fixture"""
    return TelegramEmbeddingService(namespace="test")

@pytest.fixture
def sample_message():
    """테스트용 메시지 fixture"""
    return TelegramMessage(
        message_id=12345,
        channel_id="test_channel",
        channel_title="Test Channel",
        message_type="text",
        sender_id="user123",
        sender_name="Test User",
        message_text="This is a test message with sufficient length for embedding.",
        created_at=datetime.now(timezone.utc),
        collected_at=datetime.now(timezone.utc),
        is_embedded=False,
        has_media=False,
        has_document=False
    )

@pytest.fixture
def sample_document_message():
    """문서가 첨부된 테스트 메시지 fixture"""
    return TelegramMessage(
        message_id=12346,
        channel_id="test_channel",
        channel_title="Test Channel",
        message_type="document",
        sender_id="user123",
        sender_name="Test User",
        message_text="Test message with document",
        created_at=datetime.now(timezone.utc),
        collected_at=datetime.now(timezone.utc),
        is_embedded=False,
        has_media=True,
        has_document=True,
        document_name="test.pdf",
        document_gcs_path="telegram/2024-03-20/test.pdf",
        document_mime_type="application/pdf",
        document_size=1024
    )

@pytest.mark.asyncio
async def test_create_telegram_metadata(embedding_service, sample_message):
    """메타데이터 생성 테스트"""
    metadata = embedding_service._create_telegram_metadata(sample_message)
    
    assert metadata["channel_id"] == sample_message.channel_id
    assert metadata["channel_name"] == sample_message.channel_title
    assert metadata["message_id"] == sample_message.message_id
    assert metadata["message_type"] == sample_message.message_type
    assert metadata["sender_id"] == sample_message.sender_id
    assert metadata["sender_name"] == sample_message.sender_name
    assert metadata["has_media"] == sample_message.has_media
    assert metadata["has_document"] == sample_message.has_document
    assert "document_name" not in metadata

@pytest.mark.asyncio
async def test_create_telegram_metadata_with_document(embedding_service, sample_document_message):
    """문서가 있는 메시지의 메타데이터 생성 테스트"""
    metadata = embedding_service._create_telegram_metadata(sample_document_message)
    
    assert metadata["has_document"] is True
    assert metadata["document_name"] == sample_document_message.document_name
    assert metadata["document_gcs_path"] == sample_document_message.document_gcs_path
    assert metadata["document_mime_type"] == sample_document_message.document_mime_type
    assert metadata["document_size"] == sample_document_message.document_size

@pytest.mark.asyncio
async def test_prepare_text_for_embedding(embedding_service, sample_message):
    """임베딩용 텍스트 준비 테스트"""
    text = embedding_service._prepare_text_for_embedding(sample_message)
    assert text == sample_message.message_text
    
    # 짧은 텍스트 테스트
    sample_message.message_text = "short"
    assert embedding_service._prepare_text_for_embedding(sample_message) is None
    
    # 문서 정보 포함 테스트
    sample_message.message_text = "Test message with document"
    sample_message.has_document = True
    sample_message.document_name = "test.pdf"
    text = embedding_service._prepare_text_for_embedding(sample_message)
    assert "test.pdf" in text

@pytest.mark.asyncio
async def test_embed_telegram_message(embedding_service, sample_message):
    """단일 메시지 임베딩 테스트"""
    with patch.object(embedding_service.vector_store, 'store_vectors_async', new_callable=AsyncMock) as mock_store:
        mock_store.return_value = True
        with patch.object(embedding_service, 'create_embeddings_batch', new_callable=AsyncMock) as mock_embed:
            mock_embed.return_value = [[0.1] * 768]  # 가상의 임베딩 벡터
            
            success = await embedding_service.embed_telegram_message(sample_message)
            assert success is True
            mock_embed.assert_called_once()
            mock_store.assert_called_once()

@pytest.mark.asyncio
async def test_search_messages(embedding_service):
    """메시지 검색 테스트"""
    test_query = "test search"
    test_channel = "test_channel"
    test_type = "text"
    test_sender = "user123"
    start_date = datetime.now(timezone.utc) - timedelta(days=7)
    end_date = datetime.now(timezone.utc)
    
    with patch.object(embedding_service.vector_store, 'similarity_search', new_callable=AsyncMock) as mock_search:
        # 가상의 검색 결과 생성
        mock_result = Mock()
        mock_result.page_content = "Test message content"
        mock_result.similarity = 0.95
        mock_result.metadata = {
            "channel_id": test_channel,
            "channel_name": "Test Channel",
            "message_id": 12345,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "message_type": test_type,
            "sender_id": test_sender,
            "sender_name": "Test User",
            "has_media": False,
            "has_document": False
        }
        mock_search.return_value = [mock_result]
        
        # 검색 실행
        results = await embedding_service.search_messages(
            query=test_query,
            channel_id=test_channel,
            message_type=test_type,
            sender_id=test_sender,
            has_media=False,
            has_document=False,
            start_date=start_date,
            end_date=end_date,
            limit=10
        )
        
        assert len(results) == 1
        result = results[0]
        assert result["channel_id"] == test_channel
        assert result["message_type"] == test_type
        assert result["sender_id"] == test_sender
        assert result["score"] == 0.95
        
        # 필터 검증
        mock_search.assert_called_once()
        call_args = mock_search.call_args[1]
        assert call_args["query"] == test_query
        assert call_args["metadata_filters"]["channel_id"] == test_channel
        assert call_args["metadata_filters"]["message_type"] == test_type
        assert call_args["metadata_filters"]["sender_id"] == test_sender
        assert call_args["limit"] == 10

@pytest.mark.asyncio
async def test_delete_channel_messages(embedding_service):
    """채널 메시지 삭제 테스트"""
    test_channel = "test_channel"
    before_date = datetime.now(timezone.utc) - timedelta(days=90)
    
    with patch.object(embedding_service.vector_store, 'delete_documents_by_embedding_id_async', new_callable=AsyncMock) as mock_delete:
        mock_delete.return_value = True
        
        success = await embedding_service.delete_channel_messages(
            channel_id=test_channel,
            before_date=before_date
        )
        
        assert success is True
        mock_delete.assert_called_once() 