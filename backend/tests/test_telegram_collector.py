"""텔레그램 메시지 수집 서비스 테스트"""

from datetime import datetime, timezone
from typing import AsyncGenerator, Any, AsyncIterator
import io
import pytest
import pytest_asyncio
from unittest.mock import Mock, patch
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from stockeasy.services.telegram.collector import CollectorService
from stockeasy.models.telegram_message import TelegramMessage
from common.services.storage import GoogleCloudStorageService
from telethon import TelegramClient
from common.core.config import settings
from common.core.database import get_db_async

# 테스트를 위한 설정 오버라이드
settings.GCS_TELEGRAM_FOLDER = "telegram/test"

# 실제 테스트 채널 정보
TEST_CHANNELS = [
    "usastock_young",  # 미국주식/리딩방
    "maddingStock",    # 매딩의 종목방
    "bornlupin"        # 본루팡
]

@pytest_asyncio.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """테스트용 DB 세션 fixture"""
    async for session in get_db_async():
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

@pytest_asyncio.fixture(scope="function")
async def collector_service(
    db_session: AsyncSession,
) -> AsyncIterator[CollectorService]:
    """CollectorService fixture"""
    service = CollectorService(db_session)
    await service._init_client()
    yield service
    await service.close()

@pytest.mark.asyncio
async def test_collect_real_channels(
    collector_service: CollectorService
) -> None:
    """실제 채널에서 메시지 수집 테스트"""
    async for session in get_db_async():
        try:
            for channel_id in TEST_CHANNELS:
                # 수집 전 메시지 수 확인
                stmt = select(func.count()).select_from(TelegramMessage).where(
                    TelegramMessage.channel_id == channel_id
                )
                result = await session.execute(stmt)
                before_count = result.scalar()

                # 메시지 수집
                messages = await collector_service.collect_channel_messages(channel_id, limit=5)

                # 결과 검증
                assert messages is not None
                assert len(messages) > 0

                # DB에 저장된 메시지 수 확인
                stmt = select(func.count()).select_from(TelegramMessage).where(
                    TelegramMessage.channel_id == channel_id
                )
                result = await session.execute(stmt)
                after_count = result.scalar()

                # 메시지가 실제로 저장되었는지 확인
                #assert after_count > before_count

                # 각 메시지 형식 검증
                for msg in messages:
                    assert "message_id" in msg
                    assert "channel_id" in msg
                    assert "channel_title" in msg
                    assert "message_text" in msg
                    assert "created_at" in msg
                    assert "collected_at" in msg

                    # DB에 저장된 메시지 확인
                    stmt = select(TelegramMessage).where(
                        TelegramMessage.message_id == msg["message_id"],
                        TelegramMessage.channel_id == msg["channel_id"]
                    )
                    result = await session.execute(stmt)
                    saved_msg = result.scalar_one_or_none()
                    assert saved_msg is not None

                    # 메시지 내용 로깅
                    print(f"\n채널: {msg['channel_title']}")
                    print(f"시간: {msg['created_at']}")
                    print(f"내용: {msg['message_text'][:100]}...")
                    print(f"첨부파일: {'있음' if msg.get('has_document') else '없음'}")
                    if msg.get('has_document'):
                        print(f"문서명: {msg.get('document_name')}")
                        print(f"문서 경로: {msg.get('document_gcs_path')}")

            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

@pytest.mark.asyncio
async def test_process_single_message(
    collector_service: CollectorService
) -> None:
    """단일 메시지 처리 테스트"""
    # 실제 채널에서 메시지 가져오기
    channel = await collector_service.client.get_entity(TEST_CHANNELS[0])
    messages = await collector_service.client.get_messages(channel, limit=1)

    if not messages:
        pytest.skip("채널에서 메시지를 가져올 수 없습니다.")

    message = messages[0]
    result = await collector_service._process_message(message, channel)

    # 결과 검증
    assert result is not None
    assert result["message_id"] == message.id
    assert result["channel_id"] == str(channel.id)
    assert result["channel_title"] == channel.title
    assert result["message_text"] is not None
    assert isinstance(result["created_at"], datetime)
    assert isinstance(result["collected_at"], datetime)

    # 메시지 내용 출력
    print(f"\n처리된 메시지:")
    print(f"채널: {result['channel_title']}")
    print(f"시간: {result['created_at']}")
    print(f"내용: {result['message_text']}")


@pytest.mark.asyncio
async def test_process_message_with_document(
    collector_service: CollectorService
) -> None:
    """문서가 첨부된 메시지 처리 테스트"""
    # 실제 채널에서 문서가 첨부된 메시지 찾기
    for channel_id in TEST_CHANNELS:
        channel = await collector_service.client.get_entity(channel_id)
        async for message in collector_service.client.iter_messages(channel, limit=50):
            if message.document:
                result = await collector_service._process_message(message, channel)

                # 문서 정보 검증
                assert result is not None
                assert result["has_document"] is True
                assert result["document_name"] is not None
                assert result["document_mime_type"] is not None
                assert result["document_size"] is not None
                assert result["document_gcs_path"] is not None

                # 결과 출력
                print(f"\n문서 첨부 메시지 처리 결과:")
                print(f"채널: {result['channel_title']}")
                print(f"문서명: {result['document_name']}")
                print(f"MIME 타입: {result['document_mime_type']}")
                print(f"저장 경로: {result['document_gcs_path']}")
                return

    pytest.skip("테스트 채널에서 문서가 첨부된 메시지를 찾을 수 없습니다.")


