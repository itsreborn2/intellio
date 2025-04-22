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

    async def upload_from_filename(self, destination_blob_name: str, source_file_path: str) -> str:
        """로컬 파일을 구글 클라우드 스토리지에 업로드
        
        Args:
            destination_blob_name: 저장될 파일 경로
            source_file_path: 업로드할 로컬 파일 경로
            
        Returns:
            업로드된 파일의 경로
            
        Raises:
            FileNotFoundError: 로컬 파일이 존재하지 않을 경우
            RuntimeError: 업로드 실패 시
        """
        import os
        
        # 파일 존재 여부 확인
        if not os.path.exists(source_file_path):
            logger.error(f"Local file not found: {source_file_path}")
            raise FileNotFoundError(f"Local file not found: {source_file_path}")
            
        logger.info(f"Uploading file from {source_file_path} to: {destination_blob_name}")
        blob = self.bucket.blob(destination_blob_name)
        loop = asyncio.get_event_loop()
        
        try:
            await loop.run_in_executor(
                None,
                partial(blob.upload_from_filename, source_file_path)
            )
            logger.info(f"File uploaded successfully: {destination_blob_name}")
            return blob.name
        except Exception as e:
            logger.error(f"Failed to upload file: {str(e)}")
            raise RuntimeError(f"Failed to upload file to {destination_blob_name}: {str(e)}")

    async def upload_from_BytesIO(self, destination_blob_name: str, bytes_io_obj, content_type: Optional[str] = None) -> str:
        """BytesIO 객체에서 파일을 구글 클라우드 스토리지에 업로드
        
        Args:
            destination_blob_name: 저장될 파일 경로
            bytes_io_obj: io.BytesIO 객체
            content_type: 파일의 MIME 타입 (예: 'image/jpeg', 'application/pdf')
            
        Returns:
            업로드된 파일의 경로
            
        Raises:
            ValueError: BytesIO 객체가 유효하지 않을 경우
            RuntimeError: 업로드 실패 시
        """
        from io import BytesIO
        
        # BytesIO 객체 유효성 검사
        if not isinstance(bytes_io_obj, BytesIO):
            logger.error(f"Invalid BytesIO object: {type(bytes_io_obj)}")
            raise ValueError(f"Expected BytesIO object, got {type(bytes_io_obj)}")
            
        logger.info(f"Uploading BytesIO object to: {destination_blob_name}")
        blob = self.bucket.blob(destination_blob_name)
        
        # 현재 위치 저장 후 처음으로 이동
        current_pos = bytes_io_obj.tell()
        bytes_io_obj.seek(0)
        
        loop = asyncio.get_event_loop()
        
        try:
            # content_type이 제공된 경우 설정
            if content_type:
                upload_func = partial(
                    blob.upload_from_file, 
                    bytes_io_obj, 
                    content_type=content_type
                )
            else:
                upload_func = partial(
                    blob.upload_from_file, 
                    bytes_io_obj
                )
                
            await loop.run_in_executor(None, upload_func)
            
            # 원래 위치로 복원
            bytes_io_obj.seek(current_pos)
            
            logger.info(f"BytesIO object uploaded successfully: {destination_blob_name}")
            return blob.name
        except Exception as e:
            # 원래 위치로 복원 시도
            try:
                bytes_io_obj.seek(current_pos)
            except:
                pass
                
            logger.error(f"Failed to upload BytesIO object: {str(e)}")
            raise RuntimeError(f"Failed to upload BytesIO object to {destination_blob_name}: {str(e)}")

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
                expiration=datetime.now() + timedelta(seconds=expires_in),
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
    
    async def move_file(self, source_blob_name: str, destination_blob_name: str) -> str:
        """
        GCS 버킷 내에서 파일을 이동시킵니다 (복사 후 원본 삭제).
        
        Args:
            source_blob_name (str): 이동할 원본 파일 경로
            destination_blob_name (str): 이동 대상 경로
            
        Returns:
            str: 이동 전 원본 파일 경로
            
        Raises:
            RuntimeError: 원본 파일이 존재하지 않는 경우
        """
        if source_blob_name == destination_blob_name:
            print(f"원본 파일과 대상 파일이 동일합니다. {source_blob_name}")
            return source_blob_name
        # 원본 파일 확인
        source_blob = self.bucket.blob(source_blob_name)
        loop = asyncio.get_event_loop()
        
        # 원본 파일 존재 여부 확인
        exists = await loop.run_in_executor(None, source_blob.exists)
        if not exists:
            raise RuntimeError(f"원본 파일 {source_blob_name}이(가) 스토리지에 존재하지 않습니다")
        
        # 대상 파일 객체 생성
        destination_blob = self.bucket.blob(destination_blob_name)
        
        # 복사 작업 수행
        await loop.run_in_executor(
            None,
            self.bucket.copy_blob,
            source_blob,
            self.bucket,
            destination_blob_name
        )
        
        # 원본 파일 삭제
        await loop.run_in_executor(None, source_blob.delete)
        
        print(f"파일 이동 완료: {source_blob_name} -> {destination_blob_name}")
        return source_blob_name
    
    def move_file_sync(self, source_blob_name: str, destination_blob_name: str, bLog: bool = True) -> str:
        """
        GCS 버킷 내에서 파일을 이동시킵니다 (복사 후 원본 삭제).
        
        Args:
            source_blob_name (str): 이동할 원본 파일 경로
            destination_blob_name (str): 이동 대상 경로
            
        Returns:
            str: 이동 전 원본 파일 경로
            
        Raises:
            RuntimeError: 원본 파일이 존재하지 않는 경우
        """
        if source_blob_name == destination_blob_name:
            print(f"원본 파일과 대상 파일이 동일합니다. {source_blob_name}")
            return source_blob_name
        
        # 원본 파일 확인
        source_blob = self.bucket.blob(source_blob_name)
        
        # 원본 파일 존재 여부 확인 (동기 방식)
        if not source_blob.exists():
            raise RuntimeError(f"원본 파일 {source_blob_name}이(가) 스토리지에 존재하지 않습니다")
        
        # 대상 파일 객체 생성
        destination_blob = self.bucket.blob(destination_blob_name)
        
        # 복사 작업 수행 (동기 방식)
        self.bucket.copy_blob(source_blob, self.bucket, destination_blob_name)
        
        # 원본 파일 삭제 (동기 방식)
        source_blob.delete()
        if bLog:
            print(f"파일 이동 완료: {source_blob_name} -> {destination_blob_name}")
        return source_blob_name
