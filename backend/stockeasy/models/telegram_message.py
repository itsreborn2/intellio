"""
# TODO: 채널 관리 시스템 개선 계획
# 1. TelegramChannel 모델 추가
#    - channel_id (고유 식별자)
#    - name (채널 이름)
#    - description (설명)
#    - is_active (활성화 여부)
#    - last_collected_at (마지막 수집 시간)
#    - created_at, updated_at
#
# 2. API 엔드포인트 구현
#    - GET /api/telegram/channels/ (채널 목록)
#    - POST /api/telegram/channels/ (채널 추가)
#    - PUT /api/telegram/channels/{id}/toggle (활성화/비활성화)
#
# 3. 수집기(collector.py) 수정
#    - 데이터베이스에서 활성화된 채널 목록 조회
#    - 채널별 마지막 수집 시간 업데이트
#
# 4. 관리 UI 구현 (선택사항)
#    - 채널 목록 표시
#    - 채널 추가/삭제
#    - 채널 활성화/비활성화
#    - 수집 상태 모니터링
"""

from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
from datetime import datetime
from common.models.base import Base

class TelegramMessage(Base):
    """텔레그램 메시지 모델
    
    Attributes:
        id (int): 내부 관리용 ID
        message_id (int): 텔레그램 메시지 ID
        channel_id (str): 채널 ID
        channel_title (str): 채널 이름
        message_type (str): 메시지 타입 (text, photo, video 등)
        sender_id (str): 발신자 ID
        sender_name (str): 발신자 이름
        message_text (str): 메시지 내용
        created_at (datetime): 메시지 작성 시간
        collected_at (datetime): 수집된 시간
        is_embedded (bool): 임베딩 완료 여부
        has_media (bool): 미디어 첨부 여부
        has_document (bool): 문서 첨부 여부
        document_name (str): 첨부된 문서 이름
        document_gcs_path (str): GCS에 저장된 파일 경로
        document_mime_type (str): 파일의 MIME 타입
        document_size (int): 파일 크기 (바이트)
    """
    __tablename__ = 'telegram_messages'

    id = Column(Integer, primary_key=True, index=True)
    message_id = Column(Integer, index=True, nullable=False)
    channel_id = Column(String, index=True, nullable=False)
    channel_title = Column(String, nullable=False)
    message_type = Column(String, nullable=False, default='text')
    sender_id = Column(String, nullable=True)
    sender_name = Column(String, nullable=True)
    message_text = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False)
    collected_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    is_embedded = Column(Boolean, default=False, nullable=False)
    has_media = Column(Boolean, default=False, nullable=False)
    
    # 문서 관련 필드
    has_document = Column(Boolean, default=False, nullable=False)
    document_name = Column(String, nullable=True)
    document_gcs_path = Column(String, nullable=True)  # GCS에 저장된 파일 경로
    document_mime_type = Column(String, nullable=True)  # 파일의 MIME 타입
    document_size = Column(Integer, nullable=True)      # 파일 크기 (바이트)

    __table_args__ = (
        # 메시지 ID와 채널 ID의 조합으로 유니크 제약
        Index('ix_telegram_messages_msg_channel', 'message_id', 'channel_id', unique=True),
    )
