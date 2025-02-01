"""텔레그램 메시지 수집 서비스

이 모듈은 텔레그램 채널에서 메시지를 수집하고 데이터베이스에 저장하는 기능을 제공합니다.
주요 기능:
1. 텔레그램 채널 메시지 수집
2. 첨부 파일 다운로드 및 GCS 업로드
3. 메시지 임베딩 생성
"""

from telethon import TelegramClient
from telethon.tl.types import Channel, Message, Document
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert
from typing import List, Optional, Dict, Any
import logging
import asyncio
import os
import io

from app.core.config import settings
from app.models.telegram_message import TelegramMessage
from app.services.telegram.embedding import EmbeddingService
from app.services.gcs import GCSService

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CollectorService:
    """텔레그램 메시지 수집 서비스
    
    Telethon 클라이언트를 사용하여 채널별로 최신 메시지를 수집하고 데이터베이스에 저장합니다.
    수집된 메시지는 자동으로 임베딩되어 벡터 데이터베이스에 저장됩니다.
    중복 메시지는 자동으로 처리됩니다.
    """
    
    def __init__(self, db: Session):
        """
        Args:
            db (Session): SQLAlchemy 데이터베이스 세션
        """
        self.db = db
        self.client = None
        self.last_collection = {}  # 채널별 마지막 수집 시간 저장
        try:
            self.gcs_service = GCSService()  # GCS 서비스 초기화
            logger.info("GCS 서비스 초기화 성공")
        except Exception as e:
            logger.error(f"GCS 서비스 초기화 실패: {str(e)}")
            raise
        logger.info("CollectorService 초기화 완료")

    async def _init_client(self):
        """텔레그램 클라이언트 초기화"""
        if self.client is None:
            logger.info("텔레그램 클라이언트 초기화 시작")
            try:
                self.client = TelegramClient(
                    settings.TELEGRAM_SESSION_NAME,
                    settings.TELEGRAM_API_ID,
                    settings.TELEGRAM_API_HASH,
                    system_version="4.16.30-vxCUSTOM"
                )
                await self.client.start(phone=settings.TELEGRAM_PHONE)
                logger.info("텔레그램 클라이언트 초기화 성공")
            except Exception as e:
                logger.error(f"텔레그램 클라이언트 초기화 실패: {str(e)}")
                raise

    async def _ensure_client_started(self):
        """클라이언트가 시작되지 않았다면 시작하고 로그인합니다."""
        if not self.client.is_connected():
            logger.info("텔레그램 클라이언트 시작")
            await self.client.start(phone=settings.TELEGRAM_PHONE)
            logger.info("텔레그램 클라이언트 시작 성공")

    async def _process_message(self, message: Message, channel: Channel) -> Optional[Dict[str, Any]]:
        """단일 메시지를 처리하여 Dict 객체로 변환합니다.
        
        Args:
            message (Message): Telethon 메시지 객체
            channel (Channel): 메시지가 속한 채널
            
        Returns:
            Optional[Dict[str, Any]]: 처리된 메시지 객체 또는 None
        """
        try:
            # 메시지 디버깅을 위한 상세 로깅
            logger.info(f"메시지 ID {message.id} 처리 시작")
            logger.info(f"message.text: {message.text!r}")
            logger.info(f"message.message: {message.message!r}")
            logger.info(f"message.raw_text: {message.raw_text!r}")
            logger.info(f"message.media: {message.media!r}")
            
            # 메시지 텍스트 추출
            message_text = ""
            if message.text:
                message_text = message.text
            elif message.message:
                message_text = message.message
            elif message.raw_text:
                message_text = message.raw_text
            
            if not message_text.strip():
                logger.warning(f"메시지 ID {message.id}의 텍스트가 비어있습니다")
                if message.media:
                    message_text = f"(미디어 메시지: {type(message.media).__name__})"
                else:
                    message_text = "(내용 없음)"

            # 문서 정보 추출 및 GCS 업로드
            has_document = False
            document_name = None
            document_gcs_path = None
            document_mime_type = None
            document_size = None
            
            if message.document:
                try:
                    has_document = True
                    document = message.document
                    document_name = document.attributes[-1].file_name
                    document_mime_type = document.mime_type
                    document_size = document.size
                    
                    logger.info(f"문서 다운로드 시작: {document_name}")
                    # 문서 다운로드 및 GCS 업로드
                    file_data = io.BytesIO()
                    await message.download_media(file=file_data)
                    file_data.seek(0)  # 파일 포인터를 처음으로 이동
                    
                    # GCS 경로 생성 (예: telegram/YYYY-MM-DD/file.txt)
                    date_folder = message.date.strftime("%Y-%m-%d")
                    gcs_path = f"{settings.GCS_TELEGRAM_FOLDER}/{date_folder}/{document_name}"
                    
                    # GCS에 업로드
                    document_gcs_path = self.gcs_service.upload_file(
                        file_obj=file_data,
                        destination_path=gcs_path,
                        content_type=document_mime_type
                    )
                    logger.info(f"문서 GCS 업로드 성공: {gcs_path}")
                    
                except Exception as e:
                    logger.error(f"문서 처리 중 오류 발생 (message_id: {message.id}): {str(e)}")
                    # 문서 처리 실패 시에도 메시지는 저장하도록 함
                    has_document = False
                    document_name = None
                    document_gcs_path = None
                    document_mime_type = None
                    document_size = None
            
            # Dict 객체 생성
            return {
                "message_id": message.id,
                "channel_id": str(channel.id),
                "channel_name": channel.title,
                "message_text": message_text,
                "created_at": message.date.replace(tzinfo=timezone.utc),
                "collected_at": datetime.now(timezone.utc),
                "has_document": has_document,
                "document_name": document_name,
                "document_gcs_path": document_gcs_path,
                "document_mime_type": document_mime_type,
                "document_size": document_size
            }
            
        except Exception as e:
            logger.error(f"메시지 처리 중 오류 발생: {str(e)}")
            return None
            
    async def collect_channel_messages(self, channel_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """특정 채널의 메시지를 수집합니다.
        
        Args:
            channel_id (str): 수집할 채널 ID
            limit (int, optional): 수집할 최대 메시지 수. Defaults to 100.
            
        Returns:
            List[Dict[str, Any]]: 수집된 메시지 목록
        """
        try:
            logger.info(f"채널 {channel_id}에서 메시지 수집 시작")
            await self._init_client()
            
            # 채널 정보 가져오기
            channel = await self.client.get_entity(channel_id)
            logger.info(f"채널 정보 가져오기 성공: {channel.title}")
            
            # 현재 시간 (UTC)
            now = datetime.now(timezone.utc)
            
            # 마지막 수집 시간 가져오기
            last_collection_time = self.last_collection.get(channel_id)
            
            # 메시지 수집
            messages = []
            async for message in self.client.iter_messages(channel, limit=limit):
                try:
                    # 메시지 시간이 마지막 수집 시간보다 이전이면 중단
                    if last_collection_time and message.date <= last_collection_time:
                        break
                        
                    # 메시지 처리
                    processed_message = await self._process_message(message, channel)
                    if processed_message:
                        messages.append(processed_message)
                except Exception as e:
                    logger.error(f"메시지 처리 중 오류 발생: {str(e)}")
                    continue
            
            # 데이터베이스에 메시지 저장
            for msg in messages:
                try:
                    # 중복 체크를 위한 upsert 수행
                    stmt = insert(TelegramMessage).values(**msg)
                    stmt = stmt.on_conflict_do_nothing(
                        index_elements=['message_id', 'channel_id']
                    )
                    self.db.execute(stmt)
                except Exception as e:
                    logger.error(f"메시지 저장 중 오류 발생: {str(e)}")
                    continue
            
            # 변경사항 커밋
            self.db.commit()
            
            # 마지막 수집 시간 업데이트
            self.last_collection[channel_id] = now
            
            logger.info(f"총 {len(messages)}개의 메시지 수집 및 저장 완료")
            return messages
            
        except Exception as e:
            logger.error(f"메시지 수집 중 오류 발생: {str(e)}")
            raise

    async def collect_all_channels(self) -> List[Dict[str, Any]]:
        """모든 설정된 채널에서 메시지를 수집합니다.
        
        Returns:
            List[Dict[str, Any]]: 수집된 전체 메시지 목록
        """
        all_messages = []
        
        for channel_id in settings.TELEGRAM_CHANNEL_IDS:
            messages = await self.collect_channel_messages(channel_id)
            all_messages.extend(messages)
            
        return all_messages
        
    async def close(self):
        """클라이언트 연결을 종료합니다."""
        if self.client.is_connected():
            logger.info("텔레그램 클라이언트 연결 종료")
            await self.client.disconnect()
            logger.info("텔레그램 클라이언트 연결 종료 성공")
