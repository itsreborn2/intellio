import pytest
from typing import List, Dict
from backend_new.app.services.chunker_blocked import RAGOptimizedChunker, Chunk, ChunkMetadata
from app.services.llm import LLMService

class MockLLMService:
    """테스트용 LLM 서비스 모의 객체"""
    async def analyze(self, prompt: str) -> Dict:
        if "문서를 분석하여 RAG" in prompt:
            # 문서 구조 분석 응답
            return {
                "doc_type": "earnings_call",
                "sections": [
                    {
                        "type": "participants",
                        "start": 0,
                        "end": 200,
                        "importance": 8,
                        "key_terms": ["CEO", "CFO", "IR"],
                        "entities": {
                            "people": ["김철수", "이영희", "박지성"],
                            "organizations": ["회사"]
                        }
                    },
                    {
                        "type": "qa",
                        "start": 201,
                        "end": 400,
                        "importance": 9,
                        "key_terms": ["전략", "성장", "AI"],
                        "entities": {
                            "people": ["김철수"],
                            "topics": ["성장전략", "AI"]
                        }
                    }
                ],
                "entities": {
                    "people": ["김철수", "이영희", "박지성"],
                    "organizations": ["회사"],
                    "topics": ["성장전략", "AI"]
                },
                "chunking_strategy": {
                    "size": 200,
                    "preserve": ["participants", "qa"]
                }
            }
        elif "텍스트 청크를 RAG" in prompt:
            # 청크 최적화 응답
            return {
                "optimized_text": prompt.split("청크:")[-1].strip(),
                "key_terms": ["성장", "전략", "AI"],
                "info_density": 8,
                "context_needed": True
            }
        return {}

@pytest.fixture
def mock_llm_service():
    return MockLLMService()

@pytest.fixture
def chunker(mock_llm_service):
    return RAGOptimizedChunker(
        llm_service=mock_llm_service,
        chunk_size=500,
        chunk_overlap=100
    )

@pytest.mark.asyncio
async def test_document_structure_analysis(chunker):
    """문서 구조 분석 테스트"""
    test_doc = """
    Q4 2023 실적발표

    참가자:
    김철수 (최고경영자)
    이영희 (재무책임자)
    박지성 (IR담당)

    발표내용:
    김철수: 안녕하십니까, 2023년 4분기 실적발표를 시작하겠습니다.
    
    Q&A:
    질문 1: 내년 성장 전략은?
    답변: 우리는 AI 부문에 집중 투자할 계획입니다.
    """
    
    doc_structure = await chunker._analyze_document_structure(test_doc)
    
    assert doc_structure["doc_type"] == "earnings_call"
    assert len(doc_structure["sections"]) == 2
    assert "김철수" in doc_structure["entities"]["people"]
    assert "AI" in doc_structure["entities"]["topics"]

@pytest.mark.asyncio
async def test_chunk_optimization(chunker):
    """청크 최적화 테스트"""
    test_chunk = """
    질문 1: 내년 성장 전략은?
    답변: 우리는 AI 부문에 집중 투자할 계획입니다.
    """
    
    context = {
        "doc_type": "earnings_call",
        "section_type": "qa",
        "importance": 9
    }
    
    optimized = await chunker._optimize_chunk_content(test_chunk, context)
    
    assert "성장" in optimized["key_terms"]
    assert optimized["info_density"] > 5
    assert optimized["context_needed"] is True

@pytest.mark.asyncio
async def test_full_chunking_process(chunker):
    """전체 청킹 프로세스 테스트"""
    test_doc = """
    Q4 2023 실적발표

    참가자:
    김철수 (최고경영자)
    이영희 (재무책임자)
    박지성 (IR담당)

    발표내용:
    김철수: 안녕하십니까, 2023년 4분기 실적발표를 시작하겠습니다.
    
    Q&A:
    질문 1: 내년 성장 전략은?
    답변: 우리는 AI 부문에 집중 투자할 계획입니다.
    """
    
    chunks = await chunker.create_chunks(test_doc)
    
    assert len(chunks) > 0
    assert isinstance(chunks[0], Chunk)
    assert isinstance(chunks[0].metadata, ChunkMetadata)
    
    # 참가자 섹션 체크
    participants_chunk = next(
        (chunk for chunk in chunks 
         if chunk.metadata.section_type == "participants"),
        None
    )
    assert participants_chunk is not None
    assert "김철수" in participants_chunk.content
    assert participants_chunk.metadata.importance == 8
    
    # Q&A 섹션 체크
    qa_chunk = next(
        (chunk for chunk in chunks 
         if chunk.metadata.section_type == "qa"),
        None
    )
    assert qa_chunk is not None
    assert "성장 전략" in qa_chunk.content
    assert "AI" in qa_chunk.metadata.key_terms

@pytest.mark.asyncio
async def test_error_handling(chunker):
    """에러 처리 테스트"""
    # 빈 문서 테스트
    empty_doc = ""
    chunks = await chunker.create_chunks(empty_doc)
    assert len(chunks) == 0
    
    # 매우 긴 문서 테스트
    long_doc = "test " * 1000
    chunks = await chunker.create_chunks(long_doc)
    assert len(chunks) > 0
    
    # 특수 문자가 포함된 문서 테스트
    special_chars_doc = "테스트\n\n\t\r문서@#$%"
    chunks = await chunker.create_chunks(special_chars_doc)
    assert len(chunks) > 0
