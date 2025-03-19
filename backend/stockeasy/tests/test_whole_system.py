"""Stockeasy 멀티에이전트 시스템 통합 테스트

이 모듈은 Stockeasy 멀티에이전트 시스템의 통합 테스트를 위한 코드입니다.
특히 전체 에이전트 그래프와 워크플로우가 정상적으로 동작하는지 검증합니다.
"""

import pytest
import asyncio
from typing import Dict, Any, List
from loguru import logger

from stockeasy.graph.agent_registry import agent_registry, get_graph
from stockeasy.services.telegram.rag_service import TelegramRAGLangraphService


@pytest.mark.asyncio
async def test_basic_inquiry():
    """기본 정보 조회 테스트"""
    # 서비스 초기화
    rag_service = TelegramRAGLangraphService()
    
    # 테스트 쿼리
    query = "삼성전자 실적은 어떤가요?"
    stock_code = "005930"
    stock_name = "삼성전자"
    
    # 쿼리 실행
    response = await rag_service.search_and_summarize(query, stock_code, stock_name)
    
    # 검증
    assert response is not None
    assert "summary" in response
    assert response["summary"], "요약 내용이 비어있지 않아야 합니다"
    
    logger.info(f"응답: {response['summary']}")
    logger.info(f"사용된 메시지 수: {len(response.get('retrieved_messages', []))}")


@pytest.mark.asyncio
async def test_outlook_inquiry():
    """전망 관련 조회 테스트"""
    # 서비스 초기화
    rag_service = TelegramRAGLangraphService()
    
    # 테스트 쿼리
    query = "카카오의 미래 전망은 어떤가요?"
    stock_code = "035720"
    stock_name = "카카오"
    
    # 쿼리 실행
    response = await rag_service.search_and_summarize(query, stock_code, stock_name)
    
    # 검증
    assert response is not None
    assert "summary" in response
    assert response["summary"], "요약 내용이 비어있지 않아야 합니다"
    
    logger.info(f"응답: {response['summary']}")
    logger.info(f"사용된 메시지 수: {len(response.get('retrieved_messages', []))}")


@pytest.mark.asyncio
async def test_financial_inquiry():
    """재무 정보 조회 테스트"""
    # 서비스 초기화
    rag_service = TelegramRAGLangraphService()
    
    # 테스트 쿼리
    query = "SK하이닉스의 재무상태는 어떤가요?"
    stock_code = "000660"
    stock_name = "SK하이닉스"
    
    # 쿼리 실행
    response = await rag_service.search_and_summarize(query, stock_code, stock_name)
    
    # 검증
    assert response is not None
    assert "summary" in response
    assert response["summary"], "요약 내용이 비어있지 않아야 합니다"
    
    logger.info(f"응답: {response['summary']}")
    logger.info(f"사용된 메시지 수: {len(response.get('retrieved_messages', []))}")


@pytest.mark.asyncio
async def test_industry_inquiry():
    """산업 동향 조회 테스트"""
    # 서비스 초기화
    rag_service = TelegramRAGLangraphService()
    
    # 테스트 쿼리
    query = "자동차 산업 전망은 어떤가요?"
    stock_code = "005380"  # 현대차 코드
    stock_name = "현대차"
    
    # 쿼리 실행
    response = await rag_service.search_and_summarize(query, stock_code, stock_name)
    
    # 검증
    assert response is not None
    assert "summary" in response
    assert response["summary"], "요약 내용이 비어있지 않아야 합니다"
    
    logger.info(f"응답: {response['summary']}")
    logger.info(f"사용된 메시지 수: {len(response.get('retrieved_messages', []))}")


@pytest.mark.asyncio
async def test_error_handling():
    """오류 처리 테스트"""
    # 서비스 초기화
    rag_service = TelegramRAGLangraphService()
    
    # 테스트 쿼리 (존재하지 않는 종목)
    query = "존재하지 않는 종목의 전망은?"
    stock_code = "999999"
    stock_name = "존재하지않는종목"
    
    # 쿼리 실행
    response = await rag_service.search_and_summarize(query, stock_code, stock_name)
    
    # 검증 - 에러가 발생해도 응답은 반환되어야 함
    assert response is not None
    assert "summary" in response
    
    logger.info(f"오류 처리 응답: {response['summary']}")
    logger.info(f"오류 정보: {response.get('error', '없음')}")


if __name__ == "__main__":
    asyncio.run(test_basic_inquiry())
    asyncio.run(test_outlook_inquiry())
    asyncio.run(test_financial_inquiry())
    asyncio.run(test_industry_inquiry())
    asyncio.run(test_error_handling()) 