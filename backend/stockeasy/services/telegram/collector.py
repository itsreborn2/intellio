"""텔레그램 메시지 수집 서비스

이 모듈은 텔레그램 채널에서 메시지를 수집하고 데이터베이스에 저장하는 기능을 제공합니다.
주요 기능:
1. 텔레그램 채널 메시지 수집
2. 첨부 파일 다운로드 및 GCS 업로드
3. 메시지 임베딩 생성
"""

from telethon import TelegramClient
from telethon.tl.types import Channel, Message, Document
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert
from typing import List, Optional, Dict, Any
import logging
import asyncio
import os
import io
import json
from pathlib import Path
from loguru import logger
from sqlalchemy import select

from common.core.config import settings
from stockeasy.models.telegram_message import TelegramMessage
from common.services.storage import GoogleCloudStorageService

# 로깅 설정


class CollectorService:
    """텔레그램 메시지 수집 서비스
    
    Telethon 클라이언트를 사용하여 채널별로 최신 메시지를 수집하고 데이터베이스에 저장합니다.
    수집된 메시지는 자동으로 임베딩되어 벡터 데이터베이스에 저장됩니다.
    중복 메시지는 자동으로 처리됩니다.
    """
    
    # 허용할 문서 파일 MIME 타입 정의
    ALLOWED_DOCUMENT_MIME_TYPES = {
        # PDF
        'application/pdf',
        
        # Microsoft Office
        'application/msword',  # doc
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',  # docx
        'application/vnd.ms-excel',  # xls
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',  # xlsx
        'application/vnd.ms-powerpoint',  # ppt
        'application/vnd.openxmlformats-officedocument.presentationml.presentation',  # pptx
        
        # OpenDocument
        'application/vnd.oasis.opendocument.text',  # odt
        'application/vnd.oasis.opendocument.spreadsheet',  # ods
        'application/vnd.oasis.opendocument.presentation',  # odp
        
        # Text
        'text/plain',
        'text/csv',
        'text/markdown',
        
        # RTF
        'application/rtf',
    }

    def __init__(self, db: Session):
        """
        Args:
            db (Session): SQLAlchemy 데이터베이스 세션
        """
        self.db = db
        self.client = None
        self.last_collection = {}  # 채널별 마지막 수집 시간 저장
        
        try:
            self.storage_service = GoogleCloudStorageService(
                project_id=settings.GOOGLE_CLOUD_PROJECT,
                bucket_name=settings.GOOGLE_CLOUD_STORAGE_BUCKET_STOCKEASY,
                credentials_path=settings.GOOGLE_APPLICATION_CREDENTIALS
            )
            logger.info("GCS 서비스 초기화 성공")
        except Exception as e:
            logger.error(f"GCS 서비스 초기화 실패: {str(e)}")
            raise
        logger.info("CollectorService 초기화 완료")
        self._load_channel_config()  # 채널 설정 로드

    def _load_channel_config(self):
        """텔레그램 채널 설정을 JSON 파일에서 로드"""
        try:
            json_path = Path(__file__).parent.parent.parent / 'telegram_channels.json'
            logger.info(f"_load_channel_config: {json_path}")
            if not json_path.exists():
                logger.error(f"Channel config file not found: {json_path}")
                settings.TELEGRAM_CHANNEL_IDS = []
                return

            try:
                with open(json_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    data = json.loads(content)
                    channel_data = data.get('channels', [])
                    
                    channels = [
                        {
                            "name": channel["name"],
                            "channel_id": channel["channel_id"],
                            "channel_name": channel.get("channel_name") or channel.get("user_name", ""),
                            "public": channel["public"]
                        }
                        for channel in channel_data
                        if "channel_id" in channel
                    ]
                    
                    # 설정에 저장하기 전에 유효성 검사
                    if not channels:
                        logger.warning("No valid channels found in config file")
                    
                    # 기존 설정과 비교하여 변경사항이 있을 때만 업데이트
                    if settings.TELEGRAM_CHANNEL_IDS != channels:
                        settings.TELEGRAM_CHANNEL_IDS = channels
                        logger.info(f"Updated {len(channels)} telegram channels from config file")
                        
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse channel config JSON: {str(e)}")
                settings.TELEGRAM_CHANNEL_IDS = []
            except Exception as e:
                logger.error(f"Failed to load channel config: {str(e)}")
                settings.TELEGRAM_CHANNEL_IDS = []
        except Exception as e:
            logger.error(f"Error in _load_channel_config: {str(e)}")
            settings.TELEGRAM_CHANNEL_IDS = []

    async def _init_client(self) -> bool:
        """텔레그램 클라이언트 초기화"""
        if self.client is None:
            logger.info(f"텔레그램 클라이언트 초기화 시작 : {settings.TELEGRAM_SESSION_NAME}, {settings.TELEGRAM_API_ID}, {settings.TELEGRAM_API_HASH}")
            try:
                self.client = TelegramClient(
                    settings.TELEGRAM_SESSION_NAME,
                    settings.TELEGRAM_API_ID,
                    settings.TELEGRAM_API_HASH,
                    #system_version="4.16.30-vxCUSTOM"
                )
                await self.client.start()

                if not await self.client.is_user_authorized():
                    logger.warning(f"[Telegram Collector] 인증되지 않았습니다. 로컬에서 인증 후 telegram_collector.session 파일 생성 후 빌드가 필요합니다.")
                    return False
                logger.info("텔레그램 클라이언트 초기화 성공")
                return True
            except Exception as e:
                logger.error(f"텔레그램 클라이언트 초기화 실패: {str(e)}")
                raise
        
        return True

    async def _ensure_client_started(self):
        """클라이언트가 시작되지 않았다면 시작합니다."""
        if not self.client.is_connected():
            logger.info("텔레그램 클라이언트 시작")
            await self.client.start()
            logger.info("텔레그램 클라이언트 시작 성공")
    def user_authorized(self):
        return self.client.is_user_authorized()

    async def _process_message(self, message: Message, channel: Channel, channel_public: bool) -> Optional[Dict[str, Any]]:
        """단일 메시지를 처리하여 Dict 객체로 변환합니다.
        
        Args:
            message (Message): Telethon 메시지 객체
            channel (Channel): 메시지가 속한 채널
            
        Returns:
            Optional[Dict[str, Any]]: 처리된 메시지 객체 또는 None
        """
        try:
            # 메시지 디버깅을 위한 상세 로깅
            logger.info(f"메시지 ID {message.id} 분석,추출 시작")
            if message.text is not None:
                if len(message.text) > 50:
                    tt = message.text[:50]
                else:
                    tt = message.text
                if len(tt) > 0:
                    logger.info(f"message.text: {tt}")
            #logger.info(f"message.text: {message.text!r}")
            #logger.info(f"message.message: {message.message!r}")
            #logger.info(f"message.raw_text: {message.raw_text!r}")
            #logger.info(f"message.media: {message.media!r}")
            
            # 전달된 메시지 확인
            is_forwarded = False
            forward_from_name = None
            forward_from_id = None
            if hasattr(message, 'fwd_from') and message.fwd_from:
                is_forwarded = True
                # 전달된 메시지의 원본 발신자 정보 추출
                if hasattr(message.fwd_from, 'from_name') and message.fwd_from.from_name:
                    forward_from_name = message.fwd_from.from_name
                
                if hasattr(message.fwd_from, 'from_id') and message.fwd_from.from_id:
                    # 원본이 채널인 경우 (channel_id 속성이 있는 경우)
                    if hasattr(message.fwd_from.from_id, 'channel_id'):
                        channel_id_from_msg = message.fwd_from.from_id.channel_id
                        forward_from_id = str(channel_id_from_msg)
                        
                        # 이 채널이 우리가 수집하는 채널 목록에 있는지 확인
                        # 채널 ID를 정규화(normalization)하여 비교
                        normalized_channel_id_from_msg = abs(int(channel_id_from_msg))
                        
                        for channel_info in settings.TELEGRAM_CHANNEL_IDS:
                            # settings의 channel_id도 정규화
                            try:
                                normalized_channel_id = abs(int(channel_info['channel_id']))
                                if normalized_channel_id == normalized_channel_id_from_msg:
                                    #logger.info(f"수집 대상 채널({channel_info['name']})에서 전달된 메시지는 건너뜁니다.")
                                    return None  # 이 메시지는 건너뜁니다
                            except (ValueError, TypeError):
                                continue  # channel_id가 정수로 변환될 수 없는 경우 무시
                    
                    # 원본이 사용자인 경우 (user_id 속성이 있는 경우)
                    elif hasattr(message.fwd_from.from_id, 'user_id'):
                        forward_from_id = str(message.fwd_from.from_id.user_id)
                    # 기타 다른 경우
                    else:
                        forward_from_id = str(message.fwd_from.from_id)
                
                logger.info(f"전달된 메시지 감지: {forward_from_name or '알 수 없음'}({forward_from_id or '알 수 없음'})")
            
            # 메시지 텍스트 추출
            message_text = ""
            if message.text:
                message_text = message.text
            elif message.message:
                message_text = message.message
            elif message.raw_text:
                message_text = message.raw_text
            
            if not message_text.strip():
                #logger.warning(f"메시지 ID {message.id}의 텍스트가 비어있습니다")
                if message.media:
                    message_text = f"(미디어 메시지: {type(message.media).__name__})"
                else:
                    message_text = "(내용 없음)"

            # 메시지 타입 결정
            message_type = 'text'
            has_media = False
            if message.media:
                has_media = True
                message_type = type(message.media).__name__.lower()

            # 발신자 정보 추출
            sender_id = None
            sender_name = None
            if message.sender:
                sender_id = str(message.sender.id)
                if hasattr(message.sender, 'title'):  # 채널이나 그룹인 경우
                    sender_name = message.sender.title
                else:  # 일반 사용자인 경우
                    sender_name = message.sender.first_name
                    if hasattr(message.sender, 'last_name') and message.sender.last_name:
                        sender_name += f" {message.sender.last_name}"

            # 문서 정보 추출 및 GCS 업로드
            has_document = False
            document_name = None
            document_gcs_path = None
            document_mime_type = None
            document_size = None
            
            if message.document:
                document = message.document
                document_mime_type = document.mime_type
                
                # MIME 타입이 허용된 문서 타입인지 확인
                if document_mime_type not in self.ALLOWED_DOCUMENT_MIME_TYPES:
                    #logger.debug(f"허용되지 않은 문서 타입입니다: {document_mime_type}")
                    return None
                
                try:
                    has_document = True
                    
                    # 문서 속성 안전하게 추출
                    document_name = None
                    if document.attributes:
                        for attr in document.attributes:
                            if hasattr(attr, 'file_name') and attr.file_name:
                                document_name = attr.file_name
                                break
                    
                    if not document_name:
                        # 파일명이 없는 경우 mime_type과 timestamp로 생성
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        ext = document.mime_type.split('/')[-1] if document.mime_type else 'bin'
                        document_name = f"document_{timestamp}.{ext}"
                    
                    document_size = document.size
                    
                    logger.info(f"문서 다운로드 시작: {document_name}")
                    # 문서 다운로드
                    file_data = io.BytesIO()
                    await message.download_media(file=file_data)
                    file_data.seek(0)  # 파일 포인터를 처음으로 이동
                    
                    # 로컬 저장 경로 생성
                    use_gcs = True
                    if use_gcs:
                        dev_folder = "dev/" if settings.ENV == "development" else ""
                        public_folder = "공식/" if channel_public else "비공식/"
                        target_path = f"Stockeasy/collected_auto/탤래그램/{dev_folder}{public_folder}{datetime.now().strftime('%Y-%m-%d')}/"
                        
                        target_full_path = target_path + document_name

                        document_gcs_path = await self.storage_service.upload_from_BytesIO(target_full_path, file_data)
                        logger.info(f"문서 GCS 저장 성공: {document_gcs_path}")
                    else:
                        date_folder = message.date.strftime("%Y-%m-%d")
                        local_dir = f"telegram_files/{date_folder}"
                        os.makedirs(local_dir, exist_ok=True)
                        local_path = f"{local_dir}/{document_name}"
                        document_gcs_path = local_path
                        
                        # 로컬에 파일 저장
                        with open(local_path, 'wb') as f:
                            f.write(file_data.getvalue())
                        logger.info(f"문서 로컬 저장 성공: {local_path}")
                    
                except Exception as e:
                    logger.error(f"문서 처리 중 오류 발생 (message_id: {message.id}): {str(e)}")
                    has_document = False
                    document_name = None
                    document_gcs_path = None
                    document_mime_type = None
                    document_size = None

            # timezone 처리
            seoul_tz = timezone(timedelta(hours=9), 'Asia/Seoul')
            message_created_at = message.date.astimezone(seoul_tz)  # 텔레그램 메세지 생성시간
            collected_at = datetime.now()  # 수집 시간
            
            # Dict 객체 생성
            return {
                "message_id": message.id,
                "channel_id": str(channel.id),
                "channel_title": channel.title,
                "message_type": message_type,
                "sender_id": sender_id,
                "sender_name": sender_name,
                "message_text": message_text,
                "message_created_at": message_created_at,
                "collected_at": collected_at,
                "is_embedded": False,
                "has_media": has_media,
                "has_document": has_document,
                "document_name": document_name,
                "document_gcs_path": document_gcs_path,
                "document_mime_type": document_mime_type,
                "document_size": document_size,
                "is_forwarded": is_forwarded,
                "forward_from_name": forward_from_name,
                "forward_from_id": forward_from_id
            }
            
        except Exception as e:
            logger.error(f"메시지 처리 중 오류 발생: {str(e)}", exc_info=True)
            return None
            
    async def collect_channel_messages(self, channel_info: Dict[str, Any], limit: int = 100) -> List[Dict[str, Any]]:
        """특정 채널의 메시지를 수집합니다.
        
        Args:
            channel_info (Dict[str, Any]): 수집할 채널 정보
            limit (int, optional): 수집할 최대 메시지 수. Defaults to 100.
            
        Returns:
            List[Dict[str, Any]]: 수집된 메시지 목록
        """
        try:
            
            limit = 200
            channel_name = channel_info['name']
            channel_id = channel_info['channel_id']
            channel_username = channel_info['channel_name']
            channel_public = channel_info['public']

            #logger.info(f"채널 '{channel_name}'({channel_id}) : 메시지 수집 시작")

            # username이 있으면 먼저 시도
            if channel_username and '@' not in channel_username:
                channel_username = f'@{channel_username}'
                
            try:
                logger.info(f"[{channel_name}] channel username으로 채널 검색 시도: {channel_username}")
                channel = await self.client.get_entity(channel_username)
            except ValueError:
                # username으로 실패하면 채널 ID로 시도
                logger.info(f"[{channel_name}] 채널 ID로 검색 시도: {channel_id}")
                # 채널 ID 처리 (음수로 변환)
                numeric_channel_id = int(channel_id)
                if numeric_channel_id > 0:
                    numeric_channel_id = -numeric_channel_id
                
                from telethon.tl.types import PeerChannel
                channel = await self.client.get_entity(PeerChannel(numeric_channel_id))
                
            #logger.info(f"채널 정보 가져오기 성공: {channel.title} (ID: {channel.id})")
            
            # 현재 시간 (UTC)
            now = datetime.now()
            
            # 마지막 수집 시간 가져오기
            last_collection_time = self.last_collection.get(channel_id)
            
            # 메시지 수집
            messages = []
            existing_msg_list = []
            async for message in self.client.iter_messages(channel, limit=limit):
                try:
                    # 메시지 시간이 마지막 수집 시간보다 이전이면 중단
                    if last_collection_time and message.date <= last_collection_time:
                        logger.info(f"마지막 수집 시간({last_collection_time})보다 이전 메시지입니다. 수집을 중단합니다.")
                        break
                        
                    # DB에 이미 존재하는 메시지인지 확인 (SQLAlchemy 2.0 스타일)
                    stmt = select(TelegramMessage).where(
                        TelegramMessage.message_id == message.id,
                        TelegramMessage.channel_id == str(channel.id)
                    )
                    existing_message = self.db.execute(stmt).scalar_one_or_none()
                    
                    if existing_message:
                        existing_msg_list.append(message.id)
                        #logger.info(f"메시지 ID {message.id}는 이미 DB에 존재합니다. 건너뜁니다.")
                        continue

                    # 메시지 처리
                    processed_message = await self._process_message(message, channel, channel_public)
                    if processed_message:
                        messages.append(processed_message)
                except Exception as e:
                    logger.error(f"메시지 처리 중 오류 발생: {str(e)}", exc_info=True)
                    continue

            # 수집된 메시지 ID 범위 로깅
            # if existing_msg_list:
            #     logger.debug(f"메시지 ID [ {existing_msg_list[-1]} - {existing_msg_list[0]} ]는 이미 DB에 존재합니다.")

            # 데이터베이스에 메시지 저장
            try:
                # 트랜잭션 시작
                for msg in messages:
                    # 중복 체크를 위한 upsert 수행
                    stmt = insert(TelegramMessage).values(**msg)
                    stmt = stmt.on_conflict_do_nothing(
                        index_elements=['message_id', 'channel_id']
                    )
                    self.db.execute(stmt)
                
                # 변경사항 커밋
                self.db.commit()
                
                # 마지막 수집 시간 업데이트
                self.last_collection[channel_id] = now
                
                logger.info(f"채널 '{channel_name}' : 총 {len(messages)}개의 메시지 저장")
                return messages
                
            except Exception as e:
                logger.error(f"메시지 일괄 저장 중 오류 발생: {str(e)}", exc_info=True)
                self.db.rollback()  # 오류 발생시 롤백
                raise
                
        except Exception as e:
            logger.exception(f"메시지 수집 중 오류 발생: {str(e)}", exc_info=True)
            raise
        finally:
            pass


    async def collect_all_channels(self) -> List[Dict[str, Any]]:
        """모든 설정된 채널에서 메시지를 수집합니다.
        
        Returns:
            List[Dict[str, Any]]: 수집된 전체 메시지 목록
        """
        try:
            # 매 실행마다 채널 설정을 새로 로드
            self._load_channel_config()
            logger.info("채널 설정 새로 로드 완료")

            b = await self._init_client() # 텔레 클라이언트 여기서 초기화.
            if not b:
                return []

            all_messages = []
            
            for channel_info in settings.TELEGRAM_CHANNEL_IDS:
                try:
                    messages = await self.collect_channel_messages(channel_info)
                    all_messages.extend(messages)
                except Exception as e:
                    logger.error(f"채널 메시지 수집 중 오류 발생: {str(e)}", exc_info=True)
                    continue
                
            return all_messages
        except Exception as e:
            logger.error(f"전체 채널 수집 중 오류 발생: {str(e)}", exc_info=True)
            return []
        finally:
            # 클라이언트 연결 종료 보장
            try:
                await self.db_close()
            except Exception as e:
                logger.error(f"클라이언트 연결 종료 중 오류 발생: {str(e)}", exc_info=True)
            

    async def db_close(self):
        """클라이언트 연결을 종료합니다."""
        if self.client.is_connected():
            logger.info("텔레그램 클라이언트 연결 종료")
            await self.client.disconnect()
            logger.info("텔레그램 클라이언트 연결 종료 성공")
