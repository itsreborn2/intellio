import os
import pytest
from pathlib import Path

from app.services.extractor import DocumentExtractor

@pytest.fixture
def extractor():
    """DocumentExtractor 인스턴스를 생성하는 fixture"""
    return DocumentExtractor()

@pytest.fixture
def test_files_dir():
    """테스트 파일 디렉토리 경로를 반환하는 fixture"""
    return Path(__file__).parent / 'test_files'

def test_text_extraction(extractor, test_files_dir):
    """일반 텍스트 파일 추출 테스트"""
    file_path = test_files_dir / 'test_document.txt'
    with open(file_path, 'rb') as f:
        content = f.read()
    
    text = extractor.extract_text(content, 'text/plain')
    assert text is not None
    assert len(text) > 0
    print(f"\n추출된 텍스트:\n{text}")

def test_pdf_extraction(extractor, test_files_dir):
    """PDF 파일 추출 테스트"""
    file_path = test_files_dir / 'test_document.pdf'
    with open(file_path, 'rb') as f:
        content = f.read()
    
    text = extractor.extract_text(content, 'application/pdf')
    assert text is not None
    assert len(text) > 0
    print(f"\n추출된 텍스트(PDF):\n{text}")

def test_docx_extraction(extractor, test_files_dir):
    """DOCX 파일 추출 테스트"""
    file_path = test_files_dir / 'test_document.docx'
    with open(file_path, 'rb') as f:
        content = f.read()
    
    text = extractor.extract_text(content, 'application/vnd.openxmlformats-officedocument.wordprocessingml.document')
    assert text is not None
    assert len(text) > 0
    print(f"\n추출된 텍스트(DOCX):\n{text}")

def test_doc_extraction(extractor, test_files_dir):
    """DOC 파일 추출 테스트"""
    file_path = test_files_dir / 'test_document.doc'
    with open(file_path, 'rb') as f:
        content = f.read()
    
    text = extractor.extract_text(content, 'application/msword')
    assert text is not None
    assert len(text) > 0
    print(f"\n추출된 텍스트(DOC):\n{text}")
    
    # 기본 텍스트 포함 확인
    assert "this is a test word document" in text.lower()
    # 한글 텍스트 포함 확인
    assert "한글도 포함되어 있습니다" in text

def test_excel_extraction(extractor, test_files_dir):
    """Excel 파일 추출 테스트"""
    file_path = test_files_dir / 'test_data.xlsx'
    with open(file_path, 'rb') as f:
        content = f.read()
    
    text = extractor.extract_text(content, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    assert text is not None
    assert len(text) > 0
    print(f"\n추출된 텍스트(Excel):\n{text}")

def test_hwp_extraction(extractor, test_files_dir):
    """HWP 파일 추출 테스트"""
    file_path = test_files_dir / 'test_document.hwp'
    with open(file_path, 'rb') as f:
        content = f.read()
    
    text = extractor.extract_text(content, 'application/x-hwp')
    assert text is not None
    assert len(text) > 0
    print(f"\n추출된 텍스트(HWP):\n{text[:500]}...")  # 처음 500자만 출력
    
    # 문서에 포함될 것으로 예상되는 텍스트 확인
    assert "사업계획서" in text
    assert "미라재가" in text

if __name__ == '__main__':
    pytest.main(['-v', __file__])
