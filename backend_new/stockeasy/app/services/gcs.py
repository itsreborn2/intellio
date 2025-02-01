"""
Google Cloud Storage 관련 서비스
"""

from google.cloud import storage
from google.auth import load_credentials_from_file
import os
import logging
from datetime import datetime
from typing import Optional, BinaryIO
from app.core.config import settings

logger = logging.getLogger(__name__)

class GCSService:
    """Google Cloud Storage 서비스
    
    GCS에 파일을 업로드하고 관리하는 서비스입니다.
    """
    
    def __init__(self):
        """GCS 클라이언트 초기화"""
        try:
            # 서비스 계정 인증 정보 로드
            credentials, project = load_credentials_from_file(settings.GCS_CREDENTIALS_PATH)
            
            # GCS 클라이언트 초기화
            self.client = storage.Client(
                credentials=credentials,
                project=project or settings.GCS_PROJECT_ID
            )
            
            # 버킷 가져오기
            self.bucket = self.client.bucket(settings.GCS_BUCKET_NAME)
            
        except Exception as e:
            logger.error(f"GCS 클라이언트 초기화 실패: {str(e)}")
            raise
            
    def upload_file(self, 
                   file_obj: BinaryIO, 
                   destination_path: str, 
                   content_type: Optional[str] = None
                   ) -> str:
        """파일을 GCS에 업로드합니다.
        
        Args:
            file_obj (BinaryIO): 업로드할 파일 객체
            destination_path (str): GCS에 저장될 경로 (예: telegram/channel_id/file.txt)
            content_type (Optional[str]): 파일의 MIME 타입
            
        Returns:
            str: 업로드된 파일의 GCS 경로
        """
        try:
            # Blob 객체 생성
            blob = self.bucket.blob(destination_path)
            
            # 파일 업로드
            blob.upload_from_file(
                file_obj,
                content_type=content_type,
                timeout=300  # 5분 타임아웃
            )
            
            logger.info(f"파일 업로드 성공: {destination_path}")
            return destination_path
            
        except Exception as e:
            logger.error(f"파일 업로드 실패: {str(e)}")
            raise
            
    def generate_download_url(self, gcs_path: str, expires_in: int = 3600) -> str:
        """파일 다운로드 URL을 생성합니다.
        
        Args:
            gcs_path (str): GCS 파일 경로
            expires_in (int): URL 만료 시간 (초)
            
        Returns:
            str: 서명된 다운로드 URL
        """
        try:
            blob = self.bucket.blob(gcs_path)
            url = blob.generate_signed_url(
                version="v4",
                expiration=datetime.timedelta(seconds=expires_in),
                method="GET"
            )
            return url
            
        except Exception as e:
            logger.error(f"다운로드 URL 생성 실패: {str(e)}")
            raise
