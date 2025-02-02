import pytest
import requests
import time
from pathlib import Path
from typing import Optional, Dict, Any

BASE_URL = "http://localhost:8000/api/v1"

class TestFullPipeline:
    # 클래스 레벨 변수로 변경
    project_id = None
    document_id = None
    
    @classmethod
    def setup_class(cls):
        """전체 테스트 시작 전 한 번만 실행"""
        cls.test_file_path = Path(__file__).parent / 'test_files' / 'test_document.pdf'
        
    def test_01_create_temporary_project(self):
        """임시 프로젝트 생성 테스트"""
        project_data = {
            'name': '파이프라인 테스트 프로젝트',
            'description': '전체 파이프라인 테스트',
            'is_temporary': True
        }
        response = requests.post(f'{BASE_URL}/projects/', json=project_data)
        assert response.status_code == 200, f"프로젝트 생성 실패: {response.text}"
        
        result = response.json()
        assert 'id' in result, "프로젝트 ID가 없습니다"
        TestFullPipeline.project_id = result['id']  # 클래스 변수에 저장
        print(f"\n임시 프로젝트 생성됨: {TestFullPipeline.project_id}")

    def test_02_upload_document(self):
        """문서 업로드 테스트"""
        assert TestFullPipeline.project_id, "프로젝트 ID가 없습니다"
        
        # 1. 파일 존재 확인
        print(f"\n테스트 파일 경로: {self.test_file_path}")
        assert self.test_file_path.exists(), f"테스트 파일이 없습니다: {self.test_file_path}"
        print(f"파일 크기: {self.test_file_path.stat().st_size} bytes")
        
        # 2. 파일 업로드
        with open(self.test_file_path, 'rb') as f:
            content = f.read()
            print(f"읽은 파일 크기: {len(content)} bytes")
            f.seek(0)
            
            files = [('files', ('test_document.pdf', f, 'application/pdf'))]
            print(f"\n업로드 URL: {BASE_URL}/documents/upload/{TestFullPipeline.project_id}")
            print(f"업로드 파일: {files}")
            
            response = requests.post(
                f'{BASE_URL}/documents/upload/{TestFullPipeline.project_id}',
                files=files
            )
        
        # 3. 응답 확인
        print(f"\n응답 상태 코드: {response.status_code}")
        print(f"응답 내용: {response.text}")
        
        assert response.status_code == 200, f"문서 업로드 실패: {response.text}"
        
        result = response.json()
        assert result.get('success', False), f"문서 업로드 실패: {result.get('error', '알 수 없는 오류')}"
        assert 'document_ids' in result, "응답에 document_ids가 없습니다"
        assert len(result['document_ids']) > 0, "문서 ID가 없습니다"
        
        # document_id를 클래스 변수에 저장
        TestFullPipeline.document_id = result['document_ids'][0]
        print(f"\n문서 업로드됨: {TestFullPipeline.document_id}")

    def test_03_verify_document_registered(self):
        """문서 등록 상태 확인"""
        assert TestFullPipeline.document_id, "문서 ID가 없습니다"
        self._wait_for_status('REGISTERED', timeout=5)

    def test_04_verify_document_processing(self):
        """문서 처리 과정 확인"""
        assert TestFullPipeline.document_id, "문서 ID가 없습니다"
        
        # 각 상태를 순서대로 확인
        expected_states = [
            'UPLOADED',
            'DOWNLOADING',
            'EXTRACTING',
            'CHUNKING',
            'EMBEDDING',
            'PROCESSED'
        ]
        
        for expected_state in expected_states:
            status = self._wait_for_status(expected_state, timeout=30)
            if status.get('status') == 'FAILED':
                error_msg = status.get('error_message', '알 수 없는 오류')
                pytest.fail(f"문서 처리 실패: {error_msg}")

    def test_05_verify_chunks(self):
        """청크 생성 확인"""
        assert TestFullPipeline.document_id, "문서 ID가 없습니다"
        
        response = requests.get(f'{BASE_URL}/documents/{TestFullPipeline.document_id}')
        assert response.status_code == 200, "문서 정보 조회 실패"
        
        document = response.json()
        assert document['chunks_count'] > 0, "청크가 생성되지 않았습니다"
        print(f"\n생성된 청크 수: {document['chunks_count']}")

    def _wait_for_status(self, expected_status: str, timeout: int = 30) -> Optional[Dict[str, Any]]:
        """특정 상태가 될 때까지 대기"""
        start_time = time.time()
        while time.time() - start_time < timeout:
            response = requests.get(f'{BASE_URL}/documents/{TestFullPipeline.document_id}/status')
            if response.status_code == 200:
                status = response.json()
                current_status = status.get('status')
                print(f"현재 상태: {current_status}")
                
                if current_status == expected_status:
                    return status
                elif current_status == 'FAILED':
                    pytest.fail(f"문서 처리 실패: {status.get('error_message', '알 수 없는 오류')}")
                    
            time.sleep(1)
        
        pytest.fail(f"{timeout}초 동안 {expected_status} 상태가 되지 않았습니다")
        return None

if __name__ == '__main__':
    pytest.main([__file__, '-v'])
