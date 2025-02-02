import sys
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.models.document import DocumentStatus
from app.services.extractor import DocumentExtractor

def test_upload_and_extract():
    """문서 업로드 및 텍스트 추출 테스트"""
    # 1. 테스트 파일 준비
    test_file_path = Path(__file__).parent / 'test_files' / 'test_document.txt'
    assert test_file_path.exists(), f"테스트 파일이 존재하지 않습니다: {test_file_path}"
    
    with open(test_file_path, 'rb') as f:
        content = f.read()

    with TestClient(app) as client:
        # 2. 임시 프로젝트 생성
        project_data = {
            "name": "Test Project",
            "description": "Test project for document upload",
            "is_temporary": True,
            "retention_period": "FIVE_DAYS"
        }
        response = client.post('/api/v1/projects/', json=project_data)
        assert response.status_code == 200, f"프로젝트 생성 실패: {response.text}"
        project_id = response.json()['id']

        # 3. 문서 업로드 - FastAPI TestClient 형식으로 수정
        from io import BytesIO
        file = ('files', ('test_document.txt', BytesIO(content), 'text/plain'))
        response = client.post(
            f'/api/v1/projects/{project_id}/documents',
            files=[file]
        )
        assert response.status_code == 200, f"업로드 실패: {response.text}"
        
        result = response.json()
        document_id = result['document_ids'][0]

        # 4. 업로드된 문서의 상태 확인
        response = client.get(f'/api/v1/documents/{document_id}/status')
        assert response.status_code == 200, f"문서 상태 확인 실패: {response.text}"
        doc_info = response.json()
        
        # 5. 직접 텍스트 추출 테스트
        extractor = DocumentExtractor()
        extracted_text = extractor.extract_text(content, 'text/plain')
        assert extracted_text is not None, "텍스트 추출 실패"
        assert len(extracted_text) > 0, "추출된 텍스트가 비어있습니다"
        print(f"\n추출된 텍스트:\n{extracted_text}")

if __name__ == '__main__':
    pytest.main(['-v', __file__])
