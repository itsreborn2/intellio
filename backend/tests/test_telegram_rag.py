"""텔레그램 RAG 서비스 테스트"""

import pytest
from datetime import datetime, timezone
from unittest.mock import Mock, patch, AsyncMock

from stockeasy.services.telegram.rag import TelegramRAGService
from common.services.retrievers.models import Document, RetrievalResult

# 테스트 데이터
TEST_MESSAGES = [
    {
        "content": "삼성전자 시간외 매수세 유입. 기관 순매수 1,000억 돌파. 주가 +2.5% 상승",
        "created_at": "2024-03-15T09:30:00+00:00",  # UTC 시간으로 변경
        "score": 0.85
    },
    {
        "content": "현대차 실적 발표. 영업이익 2조원 상회, 전년비 15% 증가. 신차 효과 긍정적",
        "created_at": "2024-03-15T10:00:00+00:00",  # UTC 시간으로 변경
        "score": 0.78
    },
    {
        "content": "(미확인) SK하이닉스 대규모 투자 계획 검토 중. 30조원 규모",
        "created_at": "2024-03-15T10:30:00+00:00",  # UTC 시간으로 변경
        "score": 0.72
    }
]

@pytest.fixture
def rag_service():
    """RAG 서비스 fixture"""
    return TelegramRAGService()

@pytest.fixture
def mock_retrieval_result():
    """검색 결과 mock 데이터"""
    documents = []
    for msg in TEST_MESSAGES:
        doc = Document(
            page_content=msg["content"],
            metadata={"created_at": msg["created_at"]},
            score=msg["score"]
        )
        documents.append(doc)
    return RetrievalResult(documents=documents)

@pytest.mark.asyncio
async def test_search_messages(rag_service, mock_retrieval_result):
    """메시지 검색 테스트"""
    # VectorStoreManager와 SemanticRetriever를 모킹
    with patch("stockeasy.services.telegram.rag.VectorStoreManager") as mock_vs_manager, \
         patch("stockeasy.services.telegram.rag.SemanticRetriever") as mock_retriever:
        
        # SemanticRetriever의 retrieve 메서드가 mock_retrieval_result를 반환하도록 설정
        mock_retriever_instance = Mock()
        mock_retriever_instance.retrieve = AsyncMock(return_value=mock_retrieval_result)
        mock_retriever.return_value = mock_retriever_instance
        
        # 검색 실행
        query = "삼성전자 실적"
        results = await rag_service.search_messages(query, k=2)
        
        # 결과 검증
        assert len(results) == 2
        assert "삼성전자" in results[0]  # 첫 번째 결과가 삼성전자 관련
        assert all("[" in msg and "]" in msg for msg in results)  # 모든 메시지가 시간 정보 포함

@pytest.mark.asyncio
async def test_summarize(rag_service):
    """메시지 요약 테스트"""
    # LLMModels를 모킹
    mock_response = Mock()
    mock_response.content = """[시장 동향]
- 삼성전자 +2.5% 상승, 기관 순매수 1,000억
- 현대차 실적 호조, 영업이익 2조원(+15% YoY)

[주요 이벤트]
- 현대차 실적 발표: 신차 효과로 실적 개선
- SK하이닉스 대규모 투자 계획 검토중 (미확인)

[투자 시사점]
- IT/자동차 업종 전반적 강세
- 기관 매수세 지속 주목 필요"""
    
    with patch.object(rag_service.LLM, 'agenerate', new_callable=AsyncMock) as mock_generate:
        mock_generate.return_value = mock_response
        
        # 테스트 메시지 준비
        messages = [f"[{msg['created_at']}] {msg['content']}" for msg in TEST_MESSAGES]
        
        # 요약 실행
        summary = await rag_service.summarize(messages)
        
        # 결과 검증
        assert summary is not None
        assert "[시장 동향]" in summary
        assert "[주요 이벤트]" in summary
        assert "[투자 시사점]" in summary
        assert "삼성전자" in summary
        assert "현대차" in summary
        assert "(미확인)" in summary  # 미확인 정보 표시 확인

@pytest.mark.asyncio
async def test_empty_messages_summary(rag_service):
    """빈 메시지 목록 요약 테스트"""
    summary = await rag_service.summarize([])
    assert summary == "관련된 메시지를 찾을 수 없습니다."

@pytest.mark.asyncio
async def test_message_importance_calculation(rag_service):
    """메시지 중요도 계산 테스트"""
    # 수치 정보와 중요 키워드 모두 포함
    msg1 = "삼성전자 주가 5% 상승, 8만원 돌파, 실적 발표"
    importance1 = rag_service._calculate_message_importance(msg1)
    assert importance1 >= 0.8  # 수치(0.4) + 키워드(0.2) + 길이(0.2)
    
    # 중요 키워드만 포함
    msg2 = "반도체 업종 실적 발표 예정"
    importance2 = rag_service._calculate_message_importance(msg2)
    assert 0.3 <= importance2 <= 0.6  # 키워드(0.2) + 길이(0.2)
    
    # 일반 메시지
    msg3 = "오늘 날씨가 좋네요"
    importance3 = rag_service._calculate_message_importance(msg3)
    assert importance3 <= 0.2  # 길이 가중치만

@pytest.mark.asyncio
async def test_dynamic_threshold(rag_service):
    """동적 임계값 계산 테스트"""
    # 짧은 쿼리
    short_query = "삼성전자"
    threshold1 = rag_service._calculate_dynamic_threshold(short_query)
    assert threshold1 > 0.6  # 짧은 쿼리는 더 엄격한 임계값
    
    # 긴 쿼리
    long_query = "삼성전자의 지난 분기 실적과 향후 전망에 대한 상세한 분석 자료를 찾고 있습니다"
    threshold2 = rag_service._calculate_dynamic_threshold(long_query)
    assert threshold2 < threshold1  # 긴 쿼리는 더 관대한 임계값
    
    # 중요 키워드 포함 쿼리
    important_query = "삼성전자 실적 발표"
    threshold3 = rag_service._calculate_dynamic_threshold(important_query)
    assert threshold3 > 0.6  # 중요 키워드 포함시 더 엄격한 임계값 