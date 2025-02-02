import pytest
from uuid import UUID, uuid4
from unittest.mock import Mock, patch, AsyncMock
from sqlalchemy.orm import Session

from app.services.rag import RAGService
from app.core.config import settings

def create_mock_service():
    """테스트용 RAG 서비스 생성"""
    db = Mock(spec=Session)
    service = RAGService(db)
    
    # Mock EmbeddingService
    with patch("app.services.embedding.EmbeddingService") as mock:
        instance = mock.return_value
        instance.initialize = AsyncMock()
        instance.create_embedding = AsyncMock(return_value=[0.1] * 1536)
        service.embedding_service = instance
    
    # Mock Vectorstore
    mock_vectorstore = Mock()
    mock_vectorstore.as_retriever = Mock(return_value=Mock())
    service.vectorstore = mock_vectorstore
    
    return service

@pytest.mark.asyncio
async def test_chat_query():
    """채팅 쿼리 테스트"""
    # 서비스 초기화
    service = create_mock_service()
    await service.initialize()
    
    # 테스트 데이터 준비
    project_id = uuid4()
    query = "테스트 질문입니다."
    
    # Mock 응답 설정
    mock_result = {
        "answer": "테스트 답변입니다.",
        "source_documents": [
            Mock(page_content="문서1", metadata={"source": "test1.txt"}),
            Mock(page_content="문서2", metadata={"source": "test2.txt"})
        ]
    }
    
    # Chain 호출 Mock 설정
    chain_mock = AsyncMock()
    chain_mock.ainvoke = AsyncMock(return_value=mock_result)
    
    with patch("langchain.chains.ConversationalRetrievalChain.from_llm", return_value=chain_mock):
        # 쿼리 실행
        result = await service.query(project_id, query, mode="chat")
        
        # 결과 검증
        assert result["answer"] == mock_result["answer"]
        assert len(result["contexts"]) == 2
        assert result["metadata"]["model"] == "gpt-4-1106-preview"
        assert len(result["metadata"]["similar_chunks"]) == 2

@pytest.mark.asyncio
async def test_table_query():
    """표 쿼리 테스트"""
    # 서비스 초기화
    service = create_mock_service()
    await service.initialize()
    
    # 테스트 데이터 준비
    project_id = uuid4()
    query = "표 형식으로 정리해주세요."
    
    # Mock 응답 설정
    mock_result = {
        "answer": '{"columns": ["항목", "내용"], "data": [["항목1", "내용1"], ["항목2", "내용2"]]}',
        "source_documents": [
            Mock(page_content="문서1", metadata={"source": "test1.txt"}),
            Mock(page_content="문서2", metadata={"source": "test2.txt"})
        ]
    }
    
    # Chain 호출 Mock 설정
    chain_mock = AsyncMock()
    chain_mock.ainvoke = AsyncMock(return_value=mock_result)
    
    with patch("langchain.chains.ConversationalRetrievalChain.from_llm", return_value=chain_mock):
        # 쿼리 실행
        result = await service.query(project_id, query, mode="table")
        
        # 결과 검증
        assert result["data"] == mock_result["answer"]
        assert len(result["contexts"]) == 2
        assert result["metadata"]["model"] == "gpt-4-1106-preview"
        assert len(result["metadata"]["similar_chunks"]) == 2

@pytest.mark.asyncio
async def test_invalid_mode():
    """잘못된 모드 테스트"""
    # 서비스 초기화
    service = create_mock_service()
    await service.initialize()
    
    # 테스트 데이터 준비
    project_id = uuid4()
    query = "테스트 질문입니다."
    
    # 잘못된 모드로 쿼리 실행
    with pytest.raises(ValueError, match="지원하지 않는 모드"):
        await service.query(project_id, query, mode="invalid")

@pytest.mark.asyncio
async def test_chat_with_context():
    """채팅 쿼리 테스트 (컨텍스트 포함)"""
    # 서비스 초기화
    service = create_mock_service()
    await service.initialize()
    
    # 테스트 데이터 준비
    project_id = uuid4()
    query = "테스트 질문입니다."
    context = "이것은 테스트 컨텍스트입니다."
    
    # Mock 응답 설정
    mock_result = {
        "answer": "컨텍스트를 고려한 답변입니다.",
        "source_documents": [
            Mock(page_content="문서1", metadata={"source": "test1.txt"})
        ]
    }
    
    # Chain 호출 Mock 설정
    chain_mock = AsyncMock()
    chain_mock.ainvoke = AsyncMock(return_value=mock_result)
    
    with patch("langchain.chains.ConversationalRetrievalChain.from_llm", return_value=chain_mock):
        # 쿼리 실행
        result = await service.query(project_id, query, mode="chat", context=context)
        
        # 결과 검증
        assert result["answer"] == mock_result["answer"]
        assert len(result["contexts"]) == 1
        assert result["metadata"]["model"] == "gpt-4-1106-preview"
        assert len(result["metadata"]["similar_chunks"]) == 1
