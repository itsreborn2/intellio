import os
import sys
import pytest
from pathlib import Path

# Add the project root directory to Python path
project_root = str(Path(__file__).parent.parent)
sys.path.insert(0, project_root)

from app.services.extractor import DocumentExtractor

@pytest.fixture
def test_files_dir():
    return Path(__file__).parent / 'test_files'

def test_image_extraction(test_files_dir):
    """이미지 파일 텍스트 추출 테스트"""
    extractor = DocumentExtractor()
    
    # 테스트할 이미지 포맷과 MIME 타입
    image_formats = [
        ('jpg', 'image/jpeg'),
        ('png', 'image/png'),
        ('tiff', 'image/tiff')
    ]
    
    expected_text = "인텔리오 테스트\nIntellIO Test\n2024년"
    
    for ext, mime_type in image_formats:
        file_path = test_files_dir / f'test_document.{ext}'
        
        print(f"\n테스트: {ext.upper()} 파일 추출")
        with open(file_path, 'rb') as f:
            content = f.read()
        
        text = extractor.extract_text(content, mime_type)
        assert text is not None, f"{ext.upper()} 파일 추출 실패"
        assert len(text) > 0, f"{ext.upper()} 파일에서 텍스트가 추출되지 않음"
        
        print(f"추출된 텍스트({ext.upper()}):\n{text}")
        
        # 예상 텍스트가 포함되어 있는지 확인 (대소문자 무시)
        assert "인텔리오" in text, f"{ext.upper()} 파일에서 '인텔리오' 텍스트를 찾을 수 없음"
        # OCR 오류를 고려하여 'IntellIO' 또는 'IntelllO'를 허용
        assert any(word in text for word in ["IntellIO", "IntelllO"]), f"{ext.upper()} 파일에서 'IntellIO' 텍스트를 찾을 수 없음"
        assert "2024" in text, f"{ext.upper()} 파일에서 '2024' 텍스트를 찾을 수 없음"

if __name__ == '__main__':
    pytest.main(['-v', __file__])