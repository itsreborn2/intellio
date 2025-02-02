import requests
import time
from pathlib import Path

def test_document_pipeline():
    # 1. 프로젝트 생성
    project_data = {
        'name': '문서 처리 파이프라인 테스트',
        'description': '문서 업로드부터 텍스트 추출까지 전체 파이프라인을 테스트합니다.'
    }
    response = requests.post('http://localhost:8000/api/v1/projects/', json=project_data)
    assert response.status_code == 200, f"프로젝트 생성 실패: {response.text}"
    project_id = response.json()['id']
    print(f"프로젝트 생성됨: {project_id}")

    # 2. 문서 업로드
    test_file_path = Path(__file__).parent / 'test_files' / 'test_document.txt'
    with open(test_file_path, 'rb') as f:
        files = {'files': ('test_document.txt', f, 'text/plain')}
        response = requests.post(
            f'http://localhost:8000/api/v1/documents/upload/{project_id}',
            files=files
        )
    assert response.status_code == 200, f"문서 업로드 실패: {response.text}"
    result = response.json()
    document_id = result['document_ids'][0]
    print(f"문서 업로드됨: {document_id}")

    # 3. 처리 상태 확인 (최대 30초 대기)
    max_retries = 30
    for i in range(max_retries):
        response = requests.get(f'http://localhost:8000/api/v1/documents/{document_id}/status')
        if response.status_code == 200:
            status = response.json()
            print(f"처리 상태: {status}")
            if status.get('status') in ['PROCESSED', 'FAILED']:
                break
        time.sleep(1)  # 1초 대기

if __name__ == '__main__':
    test_document_pipeline()
