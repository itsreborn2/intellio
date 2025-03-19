"""멀티에이전트 시스템 병렬 처리 성능 테스트

이 모듈은 Stockeasy 멀티에이전트 시스템의 병렬 처리 성능을 테스트합니다.
특히 검색 에이전트들의 순차 실행과 병렬 실행의 성능 차이를 측정합니다.
"""

import pytest
import asyncio
import time
from typing import Dict, Any, List
from loguru import logger

from stockeasy.graph.agent_registry import agent_registry, get_graph
from stockeasy.services.rag_service import TelegramRAGLangraphService
from stockeasy.services.telegram.question_classifier import QuestionClassification


def create_test_classification(question_type: int = 4, answer_level: int = 1) -> QuestionClassification:
    """테스트용 질문 분류 객체 생성"""
    classification = QuestionClassification()
    classification.질문주제 = question_type  # 4: 기타 (모든 에이전트 사용)
    classification.답변수준 = answer_level    # 1: 중간 수준의 상세함
    return classification


@pytest.mark.asyncio
async def test_parallel_vs_sequential():
    """병렬 처리와 순차 처리의 성능 비교 테스트"""
    # 서비스 초기화
    rag_service = TelegramRAGLangraphService()
    
    # 테스트 쿼리 (모든 에이전트가 실행되는 복합 쿼리)
    query = "삼성전자의 실적과 전망, 재무상태, 반도체 산업 동향에 대해 알려주세요"
    stock_code = "005930"
    stock_name = "삼성전자"
    
    # 분류 결과 설정 (모든 에이전트 사용)
    classification = create_test_classification(question_type=4, answer_level=2)
    
    # 병렬 처리 실행 및 시간 측정
    start_time = time.time()
    parallel_result = await rag_service.search_and_summarize(
        query=query,
        stock_code=stock_code,
        stock_name=stock_name,
        classification=classification
    )
    parallel_time = time.time() - start_time
    
    logger.info(f"병렬 처리 완료 시간: {parallel_time:.2f}초")
    
    # 검증
    assert parallel_result is not None
    assert "summary" in parallel_result
    assert parallel_result["summary"], "요약 내용이 비어있지 않아야 합니다"
    
    # 결과 로깅
    logger.info(f"병렬 처리 응답 길이: {len(parallel_result['summary'])}")
    if "processing_time" in parallel_result:
        logger.info(f"내부 측정 처리 시간: {parallel_result['processing_time']:.2f}초")
    
    # 성능 개선 확인 (내부 메트릭이 있는 경우)
    if "metrics" in parallel_result:
        metrics = parallel_result["metrics"]
        
        # 개별 에이전트 처리 시간 확인
        agent_times = []
        if "telegram_retriever_time" in metrics:
            agent_times.append(metrics["telegram_retriever_time"])
            logger.info(f"텔레그램 검색 시간: {metrics['telegram_retriever_time']:.2f}초")
        
        if "report_analyzer_time" in metrics:
            agent_times.append(metrics["report_analyzer_time"])
            logger.info(f"기업리포트 분석 시간: {metrics['report_analyzer_time']:.2f}초")
            
        if "financial_analyzer_time" in metrics:
            agent_times.append(metrics["financial_analyzer_time"])
            logger.info(f"재무제표 분석 시간: {metrics['financial_analyzer_time']:.2f}초")
            
        if "industry_analyzer_time" in metrics:
            agent_times.append(metrics["industry_analyzer_time"])
            logger.info(f"산업 분석 시간: {metrics['industry_analyzer_time']:.2f}초")
        
        # 통합 에이전트 시간
        if "knowledge_integrator_time" in metrics:
            logger.info(f"지식 통합 시간: {metrics['knowledge_integrator_time']:.2f}초")
        
        # 병렬화 성능 이점 계산
        if agent_times:
            max_agent_time = max(agent_times)
            sum_agent_times = sum(agent_times)
            theoretical_speedup = sum_agent_times / max_agent_time
            logger.info(f"이론적 속도 향상: {theoretical_speedup:.2f}배 (순차 {sum_agent_times:.2f}초 vs 병렬 {max_agent_time:.2f}초)")


@pytest.mark.asyncio
async def test_multiple_queries():
    """여러 쿼리에 대한 평균 성능 측정"""
    # 서비스 초기화
    rag_service = TelegramRAGLangraphService()
    
    # 테스트 쿼리 목록
    test_queries = [
        {
            "query": "삼성전자 실적은 어떤가요?",
            "stock_code": "005930",
            "stock_name": "삼성전자",
            "type": 0  # 종목기본정보
        },
        {
            "query": "카카오의 미래 전망은 어떤가요?",
            "stock_code": "035720",
            "stock_name": "카카오",
            "type": 1  # 전망
        },
        {
            "query": "SK하이닉스의 재무상태는 어떤가요?",
            "stock_code": "000660",
            "stock_name": "SK하이닉스",
            "type": 2  # 재무분석
        },
        {
            "query": "자동차 산업 전망은 어떤가요?",
            "stock_code": "005380",
            "stock_name": "현대차",
            "type": 3  # 산업동향
        }
    ]
    
    # 각 쿼리 실행 및 시간 측정
    total_time = 0
    for i, test_case in enumerate(test_queries):
        # 분류 결과 설정
        classification = create_test_classification(
            question_type=test_case["type"], 
            answer_level=1
        )
        
        # 실행 및 시간 측정
        start_time = time.time()
        result = await rag_service.search_and_summarize(
            query=test_case["query"],
            stock_code=test_case["stock_code"],
            stock_name=test_case["stock_name"],
            classification=classification
        )
        query_time = time.time() - start_time
        total_time += query_time
        
        # 결과 확인
        assert result is not None
        assert "summary" in result
        
        # 로깅
        logger.info(f"쿼리 {i+1} 실행 시간: {query_time:.2f}초")
        logger.info(f"쿼리: {test_case['query']}")
        logger.info(f"응답 길이: {len(result['summary'])}")
    
    # 평균 시간 계산
    avg_time = total_time / len(test_queries)
    logger.info(f"평균 실행 시간: {avg_time:.2f}초")


if __name__ == "__main__":
    # 직접 실행 시 테스트 수행
    asyncio.run(test_parallel_vs_sequential())
    asyncio.run(test_multiple_queries()) 