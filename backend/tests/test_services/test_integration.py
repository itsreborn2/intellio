import pytest
from pathlib import Path
from app.services.embedding import EmbeddingService
from app.services.rag import RAGService
from sqlalchemy.orm import Session
from unittest.mock import Mock, patch, AsyncMock
from langchain_core.documents import Document

class MockRetriever:
    def __init__(self, **kwargs):
        self.search_kwargs = kwargs.get("search_kwargs", {})
    
    async def ainvoke(self, *args, **kwargs):
        return [
            Document(
                page_content="머신러닝은 AI의 한 분야로, 데이터로부터 패턴을 학습하여 새로운 데이터에 대해 예측을 수행합니다.",
                metadata={"source": "sample_document.txt"}
            )
        ]
    
    def get_relevant_documents(self, *args, **kwargs):
        return [
            Document(
                page_content="머신러닝은 AI의 한 분야로, 데이터로부터 패턴을 학습하여 새로운 데이터에 대해 예측을 수행합니다.",
                metadata={"source": "sample_document.txt"}
            )
        ]

class MockVectorStore:
    def as_retriever(self, **kwargs):
        return MockRetriever(**kwargs)

@pytest.mark.asyncio
async def test_full_pipeline():
    """전체 RAG 파이프라인 테스트"""
    # 1. 테스트 문서 로드
    test_file = Path(__file__).parent.parent / "test_data" / "sample_document.txt"
    with open(test_file, "r", encoding="utf-8") as f:
        document_text = f.read()
    
    # 2. Mock 임베딩 서비스 설정
    with patch("app.services.embedding.EmbeddingService") as mock_embedding:
        instance = mock_embedding.return_value
        instance.initialize = AsyncMock()
        instance.create_embedding = AsyncMock(return_value=[0.1] * 1536)
        instance.upsert_texts = AsyncMock()
        embedding_service = instance
        
        # 3. 문서를 청크로 나누고 임베딩
        chunks = [document_text]
        metadata = [{"id": "1", "source": "sample_document.txt"}]
        await embedding_service.upsert_texts(chunks, metadata)
        
        # 4. RAG 서비스 초기화 (Mock 사용)
        mock_db = Mock(spec=Session)
        rag_service = RAGService(mock_db)
        rag_service.vectorstore = MockVectorStore()  # Mock 벡터 스토어 사용
        
        # 5. 다양한 모드로 쿼리 테스트
        
        # 5.1 채팅 모드 테스트
        chat_query = "머신러닝이란 무엇인가요?"
        chat_result = await rag_service.query(
            project_id="test_project",
            query=chat_query,
            mode="chat"
        )
        assert chat_result is not None
        assert isinstance(chat_result, dict)
        assert "answer" in chat_result
        
        # 5.2 테이블 모드 테스트
        table_query = "AI의 주요 분야를 알려주세요"
        table_result = await rag_service.query(
            project_id="test_project",
            query=table_query,
            mode="table"
        )
        assert table_result is not None
        assert "data" in table_result
        assert "contexts" in table_result
        assert "metadata" in table_result
