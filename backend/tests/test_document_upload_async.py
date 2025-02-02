"""Test document upload functionality"""
import pytest
from pathlib import Path
from uuid import uuid4
from fastapi import UploadFile

from app.services.document import DocumentService
from app.models.document import Document, DocumentStatus

@pytest.mark.asyncio
async def test_document_upload(async_session):
    """문서 업로드 테스트"""
    session = await anext(async_session)
    
    # 1. 테스트 파일 준비
    test_file_path = Path(__file__).parent / 'test_files' / 'test_document.txt'
    assert test_file_path.exists(), f"테스트 파일이 존재하지 않습니다: {test_file_path}"
    
    # 2. 문서 서비스 초기화
    document_service = DocumentService(session)
    
    # 3. 파일 업로드
    with open(test_file_path, 'rb') as f:
        content = f.read()
        file_size = len(content)
    
    project_id = uuid4()
    blob_name = f"projects/{project_id}/documents/{uuid4()}/test_document.txt"
    
    # 4. 구글 스토리지에 업로드
    storage_path = await document_service.storage.upload_file(content, blob_name)
    assert storage_path, "파일 업로드 실패"
    
    # 5. 문서 메타데이터 저장
    doc = Document(
        project_id=project_id,
        filename='test_document.txt',
        mime_type='text/plain',
        file_size=file_size,
        status=DocumentStatus.UPLOADED,
        file_path=storage_path
    )
    session.add(doc)
    await session.commit()
    
    # 6. 저장된 문서 확인
    saved_doc = await document_service.get_document(doc.id)
    assert saved_doc, "저장된 문서를 찾을 수 없음"
    assert saved_doc.file_size == file_size, "파일 크기가 일치하지 않음"
    assert saved_doc.file_path == storage_path, "저장 경로가 일치하지 않음"

if __name__ == "__main__":
    pytest.main(["-v", __file__])
