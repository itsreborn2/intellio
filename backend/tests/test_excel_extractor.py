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

def test_xlsx_extraction(test_files_dir):
    """XLSX 파일 추출 테스트"""
    extractor = DocumentExtractor()
    file_path = test_files_dir / 'test_document.xlsx'
    
    with open(file_path, 'rb') as f:
        content = f.read()
    
    text = extractor.extract_text(content, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    assert text is not None
    assert len(text) > 0
    print(f"\n추출된 텍스트(XLSX):\n{text[:500]}...")  # 처음 500자만 출력
    
    # 문서에 포함될 것으로 예상되는 텍스트 확인
    assert "예산" in text or "본예산" in text

if __name__ == '__main__':
    pytest.main(['-v', __file__])
