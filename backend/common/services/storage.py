import json
import logging
from datetime import datetime, timedelta
from typing import Optional
import asyncio
from functools import partial
from google.cloud import storage
from google.oauth2 import service_account

from common.core.config import settings

logger = logging.getLogger(__name__)

class GoogleCloudStorageService:
    def __init__(self, project_id: str, bucket_name: str, credentials_path: str):
        """구글 클라우드 스토리지 서비스 초기화
        
        Args:
            project_id: 구글 클라우드 프로젝트 ID
            bucket_name: 버킷 이름
            credentials_json: 서비스 계정 인증 정보 (JSON 문자열)
        """
        try:
            if not credentials_path:
                raise ValueError("Google Cloud credentials not found")
                
            credentials = service_account.Credentials.from_service_account_file(
                credentials_path
            )
            self.client = storage.Client(
                project=project_id,
                credentials=credentials
            )
            self.bucket = self.client.bucket(bucket_name)
            logger.info(f"StorageService initialized with bucket: {bucket_name}")
        except Exception as e:
            logger.error(f"Failed to initialize StorageService: {str(e)}")
            raise RuntimeError(f"Failed to initialize Google Cloud Storage: {str(e)}")

    async def upload_file(self, destination_blob_name: str, file_content: bytes) -> str:
        """파일을 구글 클라우드 스토리지에 업로드
        
        Args:
            destination_blob_name: 저장될 파일 경로
            file_content: 파일 내용
            
        Returns:
            업로드된 파일의 경로
            
        Raises:
            RuntimeError: 업로드 실패 시
        """
        logger.info(f"Uploading file to: {destination_blob_name}")
        blob = self.bucket.blob(destination_blob_name)
        loop = asyncio.get_event_loop()
        try:
            await loop.run_in_executor(
                None,
                partial(blob.upload_from_string, file_content)
            )
            logger.info(f"File uploaded successfully: {destination_blob_name}")
            return blob.name
        except Exception as e:
            logger.error(f"Failed to upload file: {str(e)}")
            raise RuntimeError(f"Failed to upload file to {destination_blob_name}: {str(e)}")

    async def get_download_url(self, blob_name: str, expires_in: int = 3600) -> Optional[str]:
        """파일 다운로드 URL 생성"""
        blob = self.bucket.blob(blob_name)
        loop = asyncio.get_event_loop()
        exists = await loop.run_in_executor(None, blob.exists)
        if not exists:
            return None
            
        url = await loop.run_in_executor(
            None,
            partial(
                blob.generate_signed_url,
                version="v4",
                expiration=datetime.utcnow() + timedelta(seconds=expires_in),
                method="GET"
            )
        )
        return url

    async def delete_file(self, blob_name: str) -> bool:
        """파일 삭제"""
        blob = self.bucket.blob(blob_name)
        loop = asyncio.get_event_loop()
        exists = await loop.run_in_executor(None, blob.exists)
        if not exists:
            return False
        await loop.run_in_executor(None, blob.delete)
        return True

    async def download_file(self, blob_name: str) -> bytes:
        """파일 다운로드"""
        blob = self.bucket.blob(blob_name)
        loop = asyncio.get_event_loop()
        exists = await loop.run_in_executor(None, blob.exists)
        if not exists:
            raise RuntimeError(f"File {blob_name} does not exist in storage")
            
        content = await loop.run_in_executor(
            None,
            blob.download_as_bytes
        )
        return content
