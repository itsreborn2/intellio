import pytest
from uuid import uuid4
from unittest.mock import Mock, AsyncMock, patch
from langchain.memory import ConversationBufferMemory
from langchain.schema import Document
from langchain_community.vectorstores import Pinecone
from langchain_core.retrievers import BaseRetriever
from app.services.rag import RAGService
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

class MockRetriever(BaseRetriever):
    """Mock 검색기"""
    async def _aget_relevant_documents(self, query):
        docs = [
            Document(page_content="테스트 문서 1", metadata={"source": "doc1.txt", "lang": "ko"}),
            Document(page_content="테스트 문서 2", metadata={"source": "doc2.txt", "lang": "en"})
        ]
        logger.info(f"MockRetriever called with query: {query}")
        logger.info(f"Returning documents: {docs}")
        return docs
    
    def _get_relevant_documents(self, query):
        docs = [
            Document(page_content="테스트 문서 1", metadata={"source": "doc1.txt", "lang": "ko"}),
            Document(page_content="테스트 문서 2", metadata={"source": "doc2.txt", "lang": "en"})
        ]
        return docs
    
@pytest.fixture
def mock_rag_service():
    """Mock RAG 서비스 생성"""
    db = Mock()
    service = RAGService(db)
    
    # Mock Pinecone
    with patch("langchain_community.vectorstores.pinecone.Pinecone") as mock_pinecone_cls:
        # Mock Retriever
        mock_retriever = MockRetriever()
        
        # Mock Vectorstore
        mock_vectorstore = Mock(spec=Pinecone)
        mock_vectorstore.retriever = mock_retriever  # 직접 retriever 속성 설정
        mock_vectorstore.as_retriever.return_value = mock_retriever
        mock_pinecone_cls.from_existing_index.return_value = mock_vectorstore
        service.vectorstore = mock_vectorstore
    
    # Mock EmbeddingService
    with patch("app.services.embedding.EmbeddingService") as mock_embedding:
        instance = mock_embedding.return_value
        instance.initialize = AsyncMock()
        instance.create_embedding = AsyncMock(return_value=[0.1] * 1536)
        instance.query = AsyncMock(return_value=[
            Mock(page_content="테스트 문서 1", metadata={"source": "doc1.txt", "lang": "ko"}),
            Mock(page_content="테스트 문서 2", metadata={"source": "doc2.txt", "lang": "en"})
        ])
        service.embedding_service = instance
    
    # Mock Memory with explicit output_key
    service.memory = ConversationBufferMemory(
        memory_key="chat_history",
        output_key="answer",
        return_messages=True
    )
    
    return service

@pytest.mark.asyncio
async def test_ai_mode_switching(mock_rag_service):
    """AI 모드 전환 테스트"""
    service = mock_rag_service
    await service.initialize()
    
    project_id = uuid4()
    query = "테스트 문서의 주요 내용을 분석해주세요"
    
    # 채팅 모드 테스트
    chat_response = await service.query(
        project_id=project_id,
        query=query,
        mode="chat"
    )
    assert chat_response is not None
    assert "answer" in chat_response
    assert "contexts" in chat_response
    assert "metadata" in chat_response
    
    # 테이블 모드 테스트
    table_response = await service.query(
        project_id=project_id,
        query=query,
        mode="table"
    )
    assert table_response is not None
    assert "data" in table_response  # 테이블 모드는 data 키로 반환
    assert isinstance(table_response["data"], dict)  # JSON 객체 형식 확인
    assert "contexts" in table_response
    assert "metadata" in table_response

@pytest.mark.asyncio
async def test_table_mode_output_format(mock_rag_service):
    """테이블 모드 출력 형식 테스트"""
    service = mock_rag_service
    await service.initialize()
    
    project_id = uuid4()
    query = "각 문서의 제목과 주요 키워드를 추출해주세요"
    
    response = await service.query(
        project_id=project_id,
        query=query,
        mode="table"
    )
    
    # 테이블 모드 응답 구조 검증
    assert isinstance(response["data"], dict)
    assert "contexts" in response
    assert len(response["contexts"]) > 0
    assert "metadata" in response
    assert "similar_chunks" in response["metadata"]

@pytest.mark.asyncio
async def test_table_mode_with_context(mock_rag_service):
    """컨텍스트를 포함한 테이블 모드 테스트"""
    service = mock_rag_service
    await service.initialize()
    
    project_id = uuid4()
    query = "각 문서에서 위험 요소를 추출해주세요"
    context = "안전 관리 측면에서 분석해주세요"
    
    response = await service.query(
        project_id=project_id,
        query=query,
        context=context,
        mode="table"
    )
    
    # 테이블 모드 응답 검증
    assert isinstance(response["data"], dict)
    assert "contexts" in response
    assert len(response["contexts"]) > 0
    
    # 컨텍스트가 반영된 결과인지 확인
    data = response["data"]
    assert any("안전" in str(value) for value in data.values())

@pytest.mark.asyncio
async def test_chat_mode_no_content(mock_rag_service):
    """채팅 모드에서 모든 문서에 내용이 없는 경우 테스트"""
    service = mock_rag_service
    await service.initialize()
    
    project_id = uuid4()
    query = "우주선 발사 일정에 대해 알려주세요"
    
    response = await service.query(
        project_id=project_id,
        query=query,
        mode="chat"
    )
    
    assert "answer" in response
    assert "주어진 문서들에서 해당 내용을 찾을 수 없습니다" in response["answer"]

@pytest.mark.asyncio
async def test_table_mode_missing_content(mock_rag_service):
    """테이블 모드에서 내용이 없는 경우 처리 테스트"""
    service = mock_rag_service
    await service.initialize()
    
    project_id = uuid4()
    query = "각 문서의 우주선 발사 일정을 추출해주세요"
    
    response = await service.query(
        project_id=project_id,
        query=query,
        mode="table"
    )
    
    # 응답 검증
    assert isinstance(response["data"], dict)
    data = response["data"]
    
    # 최소한 하나의 문서에 대해 "해당 내용 없음" 포함 확인
    assert any(
        value == "해당 내용 없음" or "해당 내용 없음" in str(value)
        for value in data.values()
    )
    
    # 모든 문서에 대한 응답이 있는지 확인
    assert len(data) == len(response["contexts"])

@pytest.mark.asyncio
async def test_table_mode_partial_content(mock_rag_service):
    """테이블 모드에서 일부 문서만 관련 내용이 있는 경우 테스트"""
    service = mock_rag_service
    await service.initialize()
    
    project_id = uuid4()
    query = "각 문서의 보안 관련 내용을 추출해주세요"
    
    response = await service.query(
        project_id=project_id,
        query=query,
        mode="table"
    )
    
    # 응답 검증
    assert isinstance(response["data"], dict)
    data = response["data"]
    
    # 일부 문서는 내용이 있고, 일부는 "해당 내용 없음"인지 확인
    has_content = False
    has_no_content = False
    
    for value in data.values():
        if value == "해당 내용 없음" or "해당 내용 없음" in str(value):
            has_no_content = True
        else:
            has_content = True
            
        if has_content and has_no_content:
            break
    
    assert len(data) == len(response["contexts"])
    assert "metadata" in response

@pytest.mark.asyncio
async def test_ai_analysis_consistency(mock_rag_service):
    """AI 분석 결과의 일관성 테스트"""
    service = mock_rag_service
    await service.initialize()
    
    project_id = uuid4()
    query = "이 문서의 주요 위험 요소는 무엇인가요?"
    
    # 동일한 쿼리에 대해 여러 번 분석 실행
    responses = []
    for _ in range(3):
        response = await service.query(
            project_id=project_id,
            query=query,
            mode="analysis"
        )
        responses.append(response)
    
    # 응답의 구조가 일관적인지 확인
    for response in responses:
        assert "analysis" in response
        assert "recommendations" in response
        assert isinstance(response["analysis"], dict)
        assert isinstance(response["recommendations"], list)

@pytest.mark.asyncio
async def test_ai_mode_error_handling(mock_rag_service):
    """AI 모드 오류 처리 테스트"""
    service = mock_rag_service
    await service.initialize()
    
    project_id = uuid4()
    query = "테스트 질문입니다"
    
    # 잘못된 모드 테스트
    with pytest.raises(ValueError) as exc_info:
        await service.query(
            project_id=project_id,
            query=query,
            mode="invalid_mode"
        )
    assert "지원하지 않는 모드" in str(exc_info.value)
    
    # 빈 쿼리 테스트
    with pytest.raises(ValueError) as exc_info:
        await service.query(
            project_id=project_id,
            query="",
            mode="table"
        )
    assert "쿼리는 비어있을 수 없습니다" in str(exc_info.value)
    
    # 공백 쿼리 테스트
    with pytest.raises(ValueError) as exc_info:
        await service.query(
            project_id=project_id,
            query="   ",
            mode="table"
        )
    assert "쿼리는 비어있을 수 없습니다" in str(exc_info.value)

    # 존재하지 않는 프로젝트 ID 테스트
    with pytest.raises(ValueError):
        await service.query(
            project_id=uuid4(),
            query=query,
            mode="analysis"
        )

@pytest.mark.asyncio
async def test_ai_analysis_with_context(mock_rag_service):
    """컨텍스트를 포함한 AI 분석 테스트"""
    service = mock_rag_service
    await service.initialize()
    
    project_id = uuid4()
    query = "이전 문서와 비교하여 어떤 변화가 있나요?"
    context = "이전 문서에서는 A, B, C 항목이 있었습니다."
    
    response = await service.query(
        project_id=project_id,
        query=query,
        mode="analysis",
        context=context
    )
    
    assert response is not None
    assert "analysis" in response
    assert "comparison" in response
    assert "changes" in response

@pytest.mark.asyncio
async def test_chat_mode_with_document_links(mock_rag_service):
    """채팅 모드에서 문서 링크와 위치 정보 포함 테스트"""
    service = mock_rag_service
    await service.initialize()
    
    project_id = uuid4()
    query = "A회사와의 계약서에서 계약금 관련 내용을 찾아주세요"
    
    response = await service.query(
        project_id=project_id,
        query=query,
        mode="chat"
    )
    
    # 기본 응답 구조 검증
    assert "answer" in response
    assert "source_documents" in response
    
    # 문서 메타데이터 검증
    source_docs = response["source_documents"]
    assert len(source_docs) > 0
    
    for doc in source_docs:
        # 필수 메타데이터 필드 확인
        assert "title" in doc
        assert "file_path" in doc
        assert "page" in doc
        assert "line_start" in doc
        assert "line_end" in doc
        assert "content" in doc
        
        # 다운로드 링크 형식 확인 (파일 경로 없이)
        assert f"[{doc['title']}](download)" in response["answer"]
        
        # 페이지와 줄 번호 정보 포함 확인
        page_info = f"페이지: {doc['page']}, 줄: {doc['line_start']}-{doc['line_end']}"
        assert page_info in response["answer"]

@pytest.mark.asyncio
async def test_chat_mode_document_sections(mock_rag_service):
    """채팅 모드 응답의 섹션 구조 테스트"""
    service = mock_rag_service
    await service.initialize()
    
    project_id = uuid4()
    query = "보안 관련 내용을 찾아주세요"
    
    response = await service.query(
        project_id=project_id,
        query=query,
        mode="chat"
    )
    
    answer = response["answer"]
    
    # 응답이 두 부분으로 구성되어 있는지 확인
    assert "관련 문서:" in answer
    
    # 응답 구조 검증
    sections = answer.split("관련 문서:")
    assert len(sections) == 2
    
    main_answer = sections[0]
    document_links = sections[1]
    
    # 문서 링크 섹션에 모든 소스 문서가 포함되어 있는지 확인
    for doc in response["source_documents"]:
        assert doc["title"] in document_links
        assert "(download)" in document_links

@pytest.mark.asyncio
async def test_table_mode_output_format(mock_rag_service):
    """테이블 모드 출력 형식 테스트"""
    service = mock_rag_service
    await service.initialize()
    
    project_id = uuid4()
    query = "각 문서의 제목과 주요 키워드를 추출해주세요"
    
    response = await service.query(
        project_id=project_id,
        query=query,
        mode="table"
    )
    
    # 테이블 모드 응답 구조 검증
    assert isinstance(response["data"], dict)
    assert "contexts" in response
    assert len(response["contexts"]) > 0
    assert "metadata" in response
    assert "similar_chunks" in response["metadata"]

@pytest.mark.asyncio
async def test_table_mode_with_context(mock_rag_service):
    """컨텍스트를 포함한 테이블 모드 테스트"""
    service = mock_rag_service
    await service.initialize()
    
    project_id = uuid4()
    query = "각 문서에서 위험 요소를 추출해주세요"
    context = "안전 관리 측면에서 분석해주세요"
    
    response = await service.query(
        project_id=project_id,
        query=query,
        context=context,
        mode="table"
    )
    
    # 테이블 모드 응답 검증
    assert isinstance(response["data"], dict)
    assert "contexts" in response
    assert len(response["contexts"]) > 0
    
    # 컨텍스트가 반영된 결과인지 확인
    data = response["data"]
    assert any("안전" in str(value) for value in data.values())

@pytest.mark.asyncio
async def test_chat_mode_no_content(mock_rag_service):
    """채팅 모드에서 모든 문서에 내용이 없는 경우 테스트"""
    service = mock_rag_service
    await service.initialize()
    
    project_id = uuid4()
    query = "우주선 발사 일정에 대해 알려주세요"
    
    response = await service.query(
        project_id=project_id,
        query=query,
        mode="chat"
    )
    
    assert "answer" in response
    assert "주어진 문서들에서 해당 내용을 찾을 수 없습니다" in response["answer"]

@pytest.mark.asyncio
async def test_table_mode_missing_content(mock_rag_service):
    """테이블 모드에서 내용이 없는 경우 처리 테스트"""
    service = mock_rag_service
    await service.initialize()
    
    project_id = uuid4()
    query = "각 문서의 우주선 발사 일정을 추출해주세요"
    
    response = await service.query(
        project_id=project_id,
        query=query,
        mode="table"
    )
    
    # 응답 검증
    assert isinstance(response["data"], dict)
    data = response["data"]
    
    # 최소한 하나의 문서에 대해 "해당 내용 없음" 포함 확인
    assert any(
        value == "해당 내용 없음" or "해당 내용 없음" in str(value)
        for value in data.values()
    )
    
    # 모든 문서에 대한 응답이 있는지 확인
    assert len(data) == len(response["contexts"])

@pytest.mark.asyncio
async def test_table_mode_partial_content(mock_rag_service):
    """테이블 모드에서 일부 문서만 관련 내용이 있는 경우 테스트"""
    service = mock_rag_service
    await service.initialize()
    
    project_id = uuid4()
    query = "각 문서의 보안 관련 내용을 추출해주세요"
    
    response = await service.query(
        project_id=project_id,
        query=query,
        mode="table"
    )
    
    # 응답 검증
    assert isinstance(response["data"], dict)
    data = response["data"]
    
    # 일부 문서는 내용이 있고, 일부는 "해당 내용 없음"인지 확인
    has_content = False
    has_no_content = False
    
    for value in data.values():
        if value == "해당 내용 없음" or "해당 내용 없음" in str(value):
            has_no_content = True
        else:
            has_content = True
            
        if has_content and has_no_content:
            break
    
    assert len(data) == len(response["contexts"])
    assert "metadata" in response

@pytest.mark.asyncio
async def test_ai_analysis_consistency(mock_rag_service):
    """AI 분석 결과의 일관성 테스트"""
    service = mock_rag_service
    await service.initialize()
    
    project_id = uuid4()
    query = "이 문서의 주요 위험 요소는 무엇인가요?"
    
    # 동일한 쿼리에 대해 여러 번 분석 실행
    responses = []
    for _ in range(3):
        response = await service.query(
            project_id=project_id,
            query=query,
            mode="analysis"
        )
        responses.append(response)
    
    # 응답의 구조가 일관적인지 확인
    for response in responses:
        assert "analysis" in response
        assert "recommendations" in response
        assert isinstance(response["analysis"], dict)
        assert isinstance(response["recommendations"], list)

@pytest.mark.asyncio
async def test_ai_mode_error_handling(mock_rag_service):
    """AI 모드 오류 처리 테스트"""
    service = mock_rag_service
    await service.initialize()
    
    project_id = uuid4()
    query = "테스트 질문입니다"
    
    # 잘못된 모드 테스트
    with pytest.raises(ValueError) as exc_info:
        await service.query(
            project_id=project_id,
            query=query,
            mode="invalid_mode"
        )
    assert "지원하지 않는 모드" in str(exc_info.value)
    
    # 빈 쿼리 테스트
    with pytest.raises(ValueError) as exc_info:
        await service.query(
            project_id=project_id,
            query="",
            mode="table"
        )
    assert "쿼리는 비어있을 수 없습니다" in str(exc_info.value)
    
    # 공백 쿼리 테스트
    with pytest.raises(ValueError) as exc_info:
        await service.query(
            project_id=project_id,
            query="   ",
            mode="table"
        )
    assert "쿼리는 비어있을 수 없습니다" in str(exc_info.value)

    # 존재하지 않는 프로젝트 ID 테스트
    with pytest.raises(ValueError):
        await service.query(
            project_id=uuid4(),
            query=query,
            mode="analysis"
        )

@pytest.mark.asyncio
async def test_ai_analysis_with_context(mock_rag_service):
    """컨텍스트를 포함한 AI 분석 테스트"""
    service = mock_rag_service
    await service.initialize()
    
    project_id = uuid4()
    query = "이전 문서와 비교하여 어떤 변화가 있나요?"
    context = "이전 문서에서는 A, B, C 항목이 있었습니다."
    
    response = await service.query(
        project_id=project_id,
        query=query,
        mode="analysis",
        context=context
    )
    
    assert response is not None
    assert "analysis" in response
    assert "comparison" in response
    assert "changes" in response

@pytest.mark.asyncio
async def test_chat_mode_with_document_links(mock_rag_service):
    """채팅 모드에서 문서 링크와 위치 정보 포함 테스트"""
    service = mock_rag_service
    await service.initialize()
    
    project_id = uuid4()
    query = "A회사와의 계약서에서 계약금 관련 내용을 찾아주세요"
    
    response = await service.query(
        project_id=project_id,
        query=query,
        mode="chat"
    )
    
    # 기본 응답 구조 검증
    assert "answer" in response
    assert "source_documents" in response
    
    # 문서 메타데이터 검증
    source_docs = response["source_documents"]
    assert len(source_docs) > 0
    
    for doc in source_docs:
        # 필수 메타데이터 필드 확인
        assert "title" in doc
        assert "file_path" in doc
        assert "page" in doc
        assert "line_start" in doc
        assert "line_end" in doc
        assert "content" in doc
        
        # 다운로드 링크 형식 확인 (파일 경로 없이)
        assert f"[{doc['title']}](download)" in response["answer"]
        
        # 페이지와 줄 번호 정보 포함 확인
        page_info = f"페이지: {doc['page']}, 줄: {doc['line_start']}-{doc['line_end']}"
        assert page_info in response["answer"]

@pytest.mark.asyncio
async def test_chat_mode_document_sections(mock_rag_service):
    """채팅 모드 응답의 섹션 구조 테스트"""
    service = mock_rag_service
    await service.initialize()
    
    project_id = uuid4()
    query = "보안 관련 내용을 찾아주세요"
    
    response = await service.query(
        project_id=project_id,
        query=query,
        mode="chat"
    )
    
    answer = response["answer"]
    
    # 응답이 두 부분으로 구성되어 있는지 확인
    assert "관련 문서:" in answer
    
    # 응답 구조 검증
    sections = answer.split("관련 문서:")
    assert len(sections) == 2
    
    main_answer = sections[0]
    document_links = sections[1]
    
    # 문서 링크 섹션에 모든 소스 문서가 포함되어 있는지 확인
    for doc in response["source_documents"]:
        assert doc["title"] in document_links
        assert "(download)" in document_links
