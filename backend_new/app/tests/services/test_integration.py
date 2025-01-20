"""통합 테스트"""

import pytest
import asyncio
from pathlib import Path
import mimetypes
from app.services.extractor import DocumentExtractor
from app.services.chunker import RAGOptimizedChunker
from app.services.llm import LLMService
from app.services.rag import RAGService

@pytest.fixture
def test_doc_path():
    return r"C:\Users\itsre\OneDrive\바탕 화면\새 폴더\새 폴더\NVIDIA 어닝콜 FY25.2Q.docx"

@pytest.fixture
def llm_service():
    return LLMService()

@pytest.fixture
def chunker(llm_service):
    return RAGOptimizedChunker(llm_service=llm_service)

@pytest.fixture
def extractor():
    return DocumentExtractor()

@pytest.fixture
def rag_service():
    return RAGService()

@pytest.mark.asyncio
async def test_full_pipeline(test_doc_path, extractor, chunker, rag_service):
    """전체 파이프라인 테스트"""
    
    # 1. 문서 추출
    print("\n1. 문서 추출 테스트")
    mime_type = mimetypes.guess_type(test_doc_path)[0] or 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    
    with open(test_doc_path, 'rb') as f:
        content = f.read()
    
    doc_text = extractor.extract_text(content, mime_type)
    assert doc_text, "문서 추출 실패"
    print(f"추출된 텍스트 길이: {len(doc_text)} 자")
    print("\n추출된 텍스트 내용:")
    print("-" * 80)
    print(doc_text[:1000] + "...")  # 처음 1000자만 출력
    print("-" * 80)
    
    # 2. 문서 청킹
    print("\n2. 문서 청킹 테스트")
    
    # 2.1 문서 구조 분석
    doc_structure = await chunker._analyze_document_structure(doc_text)
    print("\n문서 구조 분석 결과:")
    print("-" * 80)
    print(doc_structure)
    print("-" * 80)
    
    # 2.2 청크 생성
    chunks = await chunker.process_document(doc_text)
    assert chunks, "문서 청킹 실패"
    print(f"생성된 청크 수: {len(chunks)}")
    
    # 청크 내용 출력
    print("\n청크 샘플:")
    for i, chunk in enumerate(chunks[:3], 1):
        print(f"\n청크 {i}:")
        print(f"섹션 타입: {chunk.metadata.section_type}")
        print(f"중요도: {chunk.metadata.importance}")
        print(f"키워드: {chunk.metadata.key_terms}")
        print(f"내용 일부: {chunk.content[:200]}...")
    
    # 3. 다양한 쿼리 테스트
    print("\n3. 쿼리 테스트")
    test_queries = [
        "참가자 명단을 알려주세요",
        "매출액은 얼마인가요?",
        "AI 관련 전략에 대해 설명해주세요",
        "주요 고객사는 어디인가요?"
    ]
    
    for query in test_queries:
        print(f"\n쿼리: {query}")
        # 쿼리 정규화
        normalized_query = rag_service._normalize_query(query)
        print(f"정규화된 쿼리: {normalized_query}")
        
        # 쿼리 분석
        query_analysis = rag_service._analyze_query(normalized_query)
        print(f"쿼리 분석: {query_analysis}")
        
        # 관련 청크 필터링
        filtered_chunks = rag_service._filter_chunks_by_query(chunks, query_analysis)
        print(f"관련 청크 수: {len(filtered_chunks)}")
        if filtered_chunks:
            print(f"첫 번째 관련 청크 내용: {filtered_chunks[0].content[:200]}...")

if __name__ == "__main__":
    asyncio.run(test_full_pipeline())
