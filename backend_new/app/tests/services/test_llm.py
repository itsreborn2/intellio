import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.services.llm import LLMService

@pytest.fixture
def llm_service():
    """LLM 서비스 인스턴스를 생성하는 fixture"""
    with patch('google.generativeai.configure'), \
         patch('google.generativeai.GenerativeModel'):
        service = LLMService()
        return service

@pytest.mark.asyncio
async def test_analyze_empty_prompt(llm_service):
    """빈 프롬프트 테스트"""
    result = await llm_service.analyze("")
    assert "error" in result
    assert result["error"] == "프롬프트가 비어있습니다."

@pytest.mark.asyncio
async def test_analyze_valid_json_response(llm_service):
    """올바른 JSON 응답 테스트"""
    # 모의 응답 설정
    mock_response = MagicMock()
    mock_response.text = '{"result": "테스트 성공"}'
    llm_service.model.generate_content_async = AsyncMock(return_value=mock_response)
    
    result = await llm_service.analyze("테스트 프롬프트")
    assert result == {"result": "테스트 성공"}

@pytest.mark.asyncio
async def test_analyze_invalid_json_response(llm_service):
    """잘못된 JSON 응답 테스트"""
    # 모의 응답 설정
    mock_response = MagicMock()
    mock_response.text = 'invalid json'
    llm_service.model.generate_content_async = AsyncMock(return_value=mock_response)
    
    result = await llm_service.analyze("테스트 프롬프트")
    assert "error" in result
    assert "raw_response" in result

@pytest.mark.asyncio
async def test_optimize_text(llm_service):
    """텍스트 최적화 테스트"""
    # 모의 응답 설정
    mock_response = MagicMock()
    mock_response.text = '''{
        "optimized_text": "최적화된 테스트 텍스트",
        "key_terms": ["테스트", "최적화"],
        "info_density": 8,
        "requires_context": false
    }'''
    llm_service.model.generate_content_async = AsyncMock(return_value=mock_response)
    
    result = await llm_service.optimize_text("테스트 텍스트")
    assert "optimized_text" in result
    assert "key_terms" in result
    assert "info_density" in result
    assert "requires_context" in result

@pytest.mark.asyncio
async def test_optimize_text_with_context(llm_service):
    """컨텍스트가 있는 텍스트 최적화 테스트"""
    context = {"document_type": "article", "topic": "AI"}
    
    # 모의 응답 설정
    mock_response = MagicMock()
    mock_response.text = '''{
        "optimized_text": "컨텍스트가 포함된 최적화 텍스트",
        "key_terms": ["AI", "최적화"],
        "info_density": 9,
        "requires_context": true
    }'''
    llm_service.model.generate_content_async = AsyncMock(return_value=mock_response)
    
    result = await llm_service.optimize_text("테스트 텍스트", context)
    assert result["optimized_text"] == "컨텍스트가 포함된 최적화 텍스트"
    assert "AI" in result["key_terms"]
