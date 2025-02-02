import pytest
import os
from pathlib import Path
from datetime import datetime
import pandas as pd
from uuid import uuid4
from tempfile import SpooledTemporaryFile
from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.storage import StorageService
from app.services.document import DocumentService
from app.services.rag import RAGService
from app.services.embedding import EmbeddingService

@pytest.fixture
def test_excel_file():
    # 테스트용 Excel 파일 생성
    df = pd.DataFrame({
        'Name': ['John Doe', 'Jane Smith'],
        'Age': [30, 25],
        'Department': ['IT', 'HR']
    })
    
    file_path = Path('test_data.xlsx')
    df.to_excel(file_path, index=False)
    yield file_path
    
    # 테스트 후 파일 삭제
    if file_path.exists():
        file_path.unlink()

class MockUploadFile(UploadFile):
    def __init__(self, filename: str):
        # 파일을 바로 읽어서 SpooledTemporaryFile에 저장
        spooled = SpooledTemporaryFile()
        with open(filename, 'rb') as f:
            spooled.write(f.read())
        spooled.seek(0)
        
        super().__init__(
            filename=os.path.basename(filename),
            file=spooled,
            headers={"content-type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}
        )
        
    async def read(self, size: int = -1) -> bytes:
        """파일 내용 읽기"""
        self.file.seek(0)
        return self.file.read()

class MockStorageService:
    """Mock Storage Service for testing"""
    def __init__(self):
        self.files = {}  # 테스트용 파일 저장소

    async def upload_file(self, file_content: bytes, destination_blob_name: str) -> str:
        """파일 업로드 모의 구현"""
        try:
            if not isinstance(file_content, bytes):
                raise ValueError("file_content must be bytes")
            
            # 파일 저장 시뮬레이션
            self.files[destination_blob_name] = file_content
            return destination_blob_name
            
        except Exception as e:
            raise RuntimeError(f"Failed to upload file to {destination_blob_name}: {str(e)}")

    async def get_download_url(self, blob_name: str) -> str:
        """다운로드 URL 모의 구현"""
        if blob_name in self.files:
            return f"mock://storage/{blob_name}"
        return None

@pytest.mark.asyncio
async def test_excel_processing_pipeline(async_session):
    """엑셀 파일 처리 파이프라인 테스트"""
    session = await anext(async_session)
    try:
        # 1. 테스트 파일 준비
        test_file_path = Path(__file__).parent / 'test_files' / 'test_data.xlsx'
        assert test_file_path.exists(), f"테스트 파일이 존재하지 않습니다: {test_file_path}"

        # 2. 문서 서비스 초기화 (Mock Storage Service 사용)
        document_service = DocumentService(session)
        document_service.storage = MockStorageService()

        # 3. 테스트 파일 업로드
        mock_file = MockUploadFile(str(test_file_path))
        project_id = uuid4()

        document_ids = await document_service.upload_documents(
            project_id=project_id,
            files=[mock_file]
        )

        # 4. 결과 확인
        assert document_ids and len(document_ids) > 0, "문서 생성 실패"
        document = await document_service.get_document(document_ids[0])
        assert document, "문서 조회 실패"

        print(f"문서 생성 성공: {document.id}")
        print(f"문서 상태: {document.status}")
        print(f"저장 경로: {document.file_path}")

    except Exception as e:
        pytest.fail(f"테스트 실패: {str(e)}")

if __name__ == "__main__":
    pytest.main(["-v", __file__])
