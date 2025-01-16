import pytest
from unittest.mock import patch, AsyncMock
from app.services.prompt_manager import PromptManager, PromptMode
from app.core.config import settings

# 테스트용 문서 샘플
TEST_CONTRACT = """
제1조 (계약의 목적)
본 계약은 갑과 을 사이의 업무 위탁에 관한 사항을 정함을 목적으로 한다.

제2조 (계약기간)
본 계약의 기간은 2024년 1월 1일부터 2024년 12월 31일까지로 한다.

제3조 (계약금액)
1. 본 계약의 총 금액은 금 1억원(₩100,000,000)으로 한다.
2. 지급방법은 다음과 같다:
   - 계약금: 3천만원 (계약 체결 시)
   - 중도금: 4천만원 (6개월 후)
   - 잔금: 3천만원 (계약 종료 시)
"""

TEST_REPORT = """
2023년 4분기 실적 보고서

1. 주요 성과
- 매출액: 전년 대비 15% 증가
- 영업이익: 20억원 달성
- 신규 고객: 500명 유치

2. 문제점
- 고객 이탈률 5% 증가
- 운영비용 상승

3. 개선 계획
- 고객 서비스 강화
- 비용 절감 방안 수립
"""

@pytest.mark.asyncio
async def test_process_contract():
    """계약서 분석 테스트 - Gemini API 성공 케이스"""
    manager = PromptManager(
        openai_api_key="test-openai-key",
        gemini_api_key="test-gemini-key",
        gemini_url="https://test-url"
    )
    
    context = {
        "query": "계약 기간과 금액을 알려주세요.",
        "content": TEST_CONTRACT
    }
    
    # API 호출 모의 처리
    with patch('aiohttp.ClientSession.post') as mock_post:
        mock_post.return_value.__aenter__.return_value.json.return_value = {
            "candidates": [{
                "content": {
                    "parts": [{
                        "text": """
                        계약 분석 결과:
                        1. 계약 기간: 2024년 1월 1일부터 2024년 12월 31일까지
                        2. 계약 금액: 총 1억원
                           - 계약금: 3천만원
                           - 중도금: 4천만원
                           - 잔금: 3천만원
                        """
                    }]
                }
            }]
        }
        
        response = await manager.process_prompt(PromptMode.CHAT, context)
        assert response is not None
        assert len(response) > 0
        assert "2024년" in response
        assert "1억원" in response

@pytest.mark.asyncio
async def test_process_contract_fallback():
    """계약서 분석 테스트 - Gemini API 실패 시 OpenAI 폴백"""
    manager = PromptManager(
        openai_api_key="test-openai-key",
        gemini_api_key="test-gemini-key",
        gemini_url="https://test-url"
    )
    
    context = {
        "query": "계약 기간과 금액을 알려주세요.",
        "content": TEST_CONTRACT
    }
    
    # Gemini API 실패 모의 처리
    with patch('aiohttp.ClientSession.post') as mock_gemini:
        mock_gemini.return_value.__aenter__.return_value.json.return_value = {
            "error": {"message": "API Error"}
        }
        
        # OpenAI API 응답 모의 처리
        mock_completion = AsyncMock()
        mock_completion.choices = [
            AsyncMock(message=AsyncMock(content="""
                계약서 분석 결과 (OpenAI):
                1. 계약 기간: 2024년 1월 1일부터 2024년 12월 31일까지
                2. 계약 금액: 총 1억원
                   - 계약금: 3천만원
                   - 중도금: 4천만원
                   - 잔금: 3천만원
                """))
        ]
        
        # OpenAI 클라이언트 모킹
        with patch.object(manager.openai_client, 'chat') as mock_chat:
            mock_chat.completions = AsyncMock()
            mock_chat.completions.create = AsyncMock(return_value=mock_completion)
            
            response = await manager.process_prompt(PromptMode.CHAT, context)
            assert response is not None
            assert len(response) > 0
            assert "2024년" in response
            assert "1억원" in response
            assert "OpenAI" in response  # OpenAI 응답임을 확인

@pytest.mark.asyncio
async def test_process_report():
    """보고서 분석 테스트"""
    manager = PromptManager(
        openai_api_key="test-openai-key",
        gemini_api_key="test-gemini-key",
        gemini_url="https://test-url"
    )
    
    context = {
        "query": "매출과 영업이익 현황을 분석해주세요.",
        "content": TEST_REPORT
    }
    
    # API 호출 모의 처리
    with patch('aiohttp.ClientSession.post') as mock_post:
        mock_post.return_value.__aenter__.return_value.json.return_value = {
            "candidates": [{
                "content": {
                    "parts": [{
                        "text": """
                        실적 분석 결과:
                        1. 매출 성과
                           - 전년 대비 15% 증가
                        2. 영업이익
                           - 20억원 달성
                        """
                    }]
                }
            }]
        }
        
        response = await manager.process_prompt(PromptMode.CHAT, context)
        assert response is not None
        assert len(response) > 0
        assert "15%" in response
        assert "20억원" in response

@pytest.mark.asyncio
async def test_cache_hit():
    """캐시 히트 테스트"""
    manager = PromptManager(
        openai_api_key="test-openai-key",
        gemini_api_key="test-gemini-key",
        gemini_url="https://test-url"
    )
    
    context = {
        "document_id": "test-doc-1",
        "query": "계약 기간과 금액을 알려주세요.",
        "content": TEST_CONTRACT
    }
    
    # 첫 번째 호출 - API 사용
    with patch('aiohttp.ClientSession.post') as mock_post:
        mock_post.return_value.__aenter__.return_value.json.return_value = {
            "candidates": [{
                "content": {
                    "parts": [{
                        "text": "캐시 테스트 응답"
                    }]
                }
            }]
        }
        
        response1 = await manager.process_prompt(PromptMode.CHAT, context)
        assert response1 == "캐시 테스트 응답"
        
    # 두 번째 호출 - 캐시 사용
    with patch('aiohttp.ClientSession.post') as mock_post:
        # API가 호출되면 다른 응답을 반환하도록 설정
        mock_post.return_value.__aenter__.return_value.json.return_value = {
            "candidates": [{
                "content": {
                    "parts": [{
                        "text": "다른 응답"
                    }]
                }
            }]
        }
        
        response2 = await manager.process_prompt(PromptMode.CHAT, context)
        # 캐시된 이전 응답이 반환되어야 함
        assert response2 == "캐시 테스트 응답"
        # API가 호출되지 않았는지 확인
        mock_post.assert_not_called()
