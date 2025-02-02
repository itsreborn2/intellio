import requests
import os
from pathlib import Path
import time

def test_document_upload():
    # 1. 프로젝트 생성
    project_data = {
        'name': '문서 업로드 테스트 프로젝트',
        'description': '문서 업로드 테스트를 위한 프로젝트입니다.'
    }
    response = requests.post('http://localhost:8000/api/v1/projects/', json=project_data)
    assert response.status_code == 200, f"프로젝트 생성 실패: {response.text}"
    project_id = response.json()['id']
    print(f"프로젝트가 생성되었습니다. ID: {project_id}")

    # 2. 테스트 문서 경로 설정
    test_file_path = Path(__file__).parent / 'test_files' / 'test_document.pdf'
    assert test_file_path.exists(), f"테스트 파일이 존재하지 않습니다: {test_file_path}"
    print(f"테스트 파일이 준비되었습니다: {test_file_path}")

    # 3. 문서 업로드
    with open(test_file_path, 'rb') as f:
        files = {'files': ('test_document.pdf', f, 'application/pdf')}
        response = requests.post(
            f'http://localhost:8000/api/v1/documents/upload/{project_id}',
            files=files
        )
    
    assert response.status_code == 200, f"업로드 실패: {response.text}"
    result = response.json()
    assert 'document_ids' in result
    document_id = result['document_ids'][0]
    print(f"문서가 업로드되었습니다. ID: {document_id}")

    # 4. 문서 상태 확인 (최대 30초 대기)
    max_attempts = 30
    for attempt in range(max_attempts):
        response = requests.get(f'http://localhost:8000/api/v1/documents/{document_id}/status')
        assert response.status_code == 200, f"상태 확인 실패: {response.text}"
        status = response.json()
        print(f"문서 상태 ({attempt+1}/{max_attempts}): {status}")
        
        if status.get('status') == 'COMPLETED':
            print("문서 처리가 완료되었습니다!")
            break
        elif status.get('status') == 'FAILED':
            raise Exception("문서 처리가 실패했습니다.")
        
        time.sleep(1)  # 1초 대기
    else:
        print("시간 초과: 문서 처리가 완료되지 않았습니다.")

if __name__ == '__main__':
    test_document_upload()
