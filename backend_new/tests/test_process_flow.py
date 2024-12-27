import sys
from pathlib import Path

# Add the project root directory to Python path
project_root = str(Path(__file__).parent.parent)
sys.path.insert(0, project_root)

import pytest
from uuid import UUID
from fastapi.testclient import TestClient
from app.main import app
from app.models.document import DocumentStatus
from app.workers.document import process_documents_batch

def test_document_processing():
    """문서 처리 플로우 테스트"""
    # 1. 테스트 파일 준비
    test_file_path = Path(__file__).parent / 'test_files' / 'test_document.txt'
    assert test_file_path.exists(), f"테스트 파일이 존재하지 않습니다: {test_file_path}"
    
    with open(test_file_path, 'rb') as f:
        content = f.read()

    # 2. 문서 업로드
    with TestClient(app) as client:
        files = {'files': ('test_document.txt', content, 'text/plain')}
        response = client.post('/api/v1/documents/upload', files=files)
        assert response.status_code == 200, f"업로드 실패: {response.text}"
        
        result = response.json()
        project_id = result['project_id']
        document_id = result['document_ids'][0]

        # 3. 문서 상태 확인 (UPLOADED)
        response = client.get(f'/api/v1/documents/{document_id}')
        assert response.status_code == 200
        doc_info = response.json()
        assert doc_info['status'] == DocumentStatus.UPLOADED.value

        # 4. 문서 처리 시작
        process_documents_batch([str(document_id)])

        # 5. 문서 상태 재확인 (PROCESSED)
        response = client.get(f'/api/v1/documents/{document_id}')
        assert response.status_code == 200
        doc_info = response.json()
        assert doc_info['status'] == DocumentStatus.PROCESSED.value

        # 6. 청크 데이터 확인
        response = client.get(f'/api/v1/documents/{document_id}/chunks')
        assert response.status_code == 200
        chunks = response.json()
        assert len(chunks) > 0, "문서 청크가 생성되지 않았습니다"

if __name__ == '__main__':
    pytest.main([__file__, "-v"])
