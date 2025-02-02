import pytest
from pathlib import Path
from datetime import datetime
from app.services.storage import StorageService

@pytest.mark.asyncio
async def test_storage_upload():
    """구글 클라우드 스토리지 업로드 테스트"""
    try:
        # 1. 테스트 파일 경로 설정
        test_file_path = Path(__file__).parent / 'test_files' / 'test_document.txt'
        assert test_file_path.exists(), f"테스트 파일이 존재하지 않습니다: {test_file_path}"
        
        # 2. 파일 읽기
        with open(test_file_path, 'rb') as f:
            file_content = f.read()
        
        # 3. Storage Service를 통한 업로드
        storage_service = StorageService()
        current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
        destination_blob_name = f"test_uploads/{current_time}_test_document.txt"
        
        storage_path = await storage_service.upload_file(
            file_content=file_content,
            destination_blob_name=destination_blob_name
        )
        
        # 4. 결과 확인
        assert storage_path, "파일 업로드 실패"
        print(f"파일 업로드 성공: {storage_path}")
        
        # 5. 업로드된 파일 URL 가져오기
        download_url = await storage_service.get_download_url(storage_path)
        assert download_url, "다운로드 URL 생성 실패"
        print(f"다운로드 URL: {download_url}")
        
    except Exception as e:
        pytest.fail(f"테스트 실패: {str(e)}")

if __name__ == "__main__":
    pytest.main(["-v", __file__])
