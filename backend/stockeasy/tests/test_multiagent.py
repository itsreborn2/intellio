"""
멀티에이전트 시스템 테스트

이 모듈은 Stockeasy 멀티에이전트 시스템을 테스트하기 위한 스크립트를 제공합니다.
"""

import os
import sys



# 상위 디렉토리를 sys.path에 추가하여 모듈을 import할 수 있게 함
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import asyncio
import json
from loguru import logger
from datetime import datetime
import pytz
from typing import Dict, Any, List
from common.app import LoadEnvGlobal

LoadEnvGlobal()
# LangSmith 환경 변수 설정
os.environ["LANGCHAIN_TRACING"] = "true"
os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_PROJECT"] = "stockeasy_multiagent"
# LANGSMITH_API_KEY는 .env 파일에서 로드됨

from stockeasy.models.agent_io import QuestionAnalysisResult
from common.core.config import settings
# 로그 시간을 한국 시간으로 설정
logger.remove()  # 기존 핸들러 제거

# 한국 시간대 설정
KST = pytz.timezone('Asia/Seoul')

# 한국 시간으로 설정된 로거 추가 (간단한 형식으로 수정)
logger.add(
    sys.stdout,
    format="{time:YYYY-MM-DD HH:mm:ss} KST | {level: <8} | {name}:{line} - {message}",
    level="INFO",
    colorize=True,
)


# 로거 설정 이후에 모듈 임포트
from common.core.database import get_db_session
from stockeasy.graph.agent_registry import get_graph
from stockeasy.services.rag_service import StockRAGService


async def test_simple_query():
    """간단한 쿼리로 시스템 테스트"""
    _db = await get_db_session()
    rag_service = StockRAGService(_db)
    
    query = "파마리서치 좋나? 사까?"
    stock_code = "214450"
    stock_name = "파마리서치"
    
    logger.info(f"질문: {query}")
    
    result = await rag_service.analyze_stock(
        query=query,
        stock_code=stock_code,
        stock_name=stock_name,
        session_id="60a566aa-5eed-44ac-9380-1349f76259e7",
        user_id="blueslame@gmail.com"  # None이더라도 명시적으로 전달
        )
        
    
    # result의 모든 키값들 출력
    # print(f"# result 키값 목록:")
    # for key in result.keys():
    #     print(f" - {key}: {type(result[key])}")
    # print(f"-"*70)

    # print(f"="*70)
    # print(f"# 질문: {query}")
    # print(f"-"*70)
    # question_classification:QuestionAnalysisResult = result.get('question_classification', {})
    # classification = question_classification.get('classification', {})
    # data_requirements = question_classification.get("data_requirements", {})
    # print(f"분류 결과: {classification}")
    # print(f"데이터 요구사항: {data_requirements}")
    # print(f"-"*70)
    # print(f"## 응답: {result.get('formatted_response')}")
    
    return query, result


async def test_complex_query():
    """복잡한 쿼리로 시스템 테스트"""
    _db = await get_db_session()
    rag_service = StockRAGService(_db)
    
    query = "NAND 반도체 시장 전망과 관련해 삼성전자의 경쟁력은 어떤가요?"
    #query = "HBM 시장 전망과 관련해 삼성전자의 경쟁력은?"
    # stock_code = "005930"
    # stock_name = "삼성전자"
    #query = "러시아-우크라이나 전쟁의 종전으로 인해 방산업체들의 수익성을 분석해봐"
    query = "최근 실적이 어닝 서프가 나온 원인을 알려줘"
    stock_code = "012450"
    stock_name = "한화에어로스페이스"

    query = "효성중공업을 사고 싶은데, 건설부문이 마음에 걸리네. 니 생각은 어때?"
    stock_code = "298040"
    stock_name = "효성중공업"
    
    logger.info(f"테스트 쿼리: {query}")
    
    result = await rag_service.analyze_stock(
        query=query,
        stock_code=stock_code,
        stock_name=stock_name
    )
    
    #logger.info(f"분류 결과: {result.get('classification')}")
    #logger.info(f"요약 결과: {result.get('summary')}")
    
    # 트레이스 정보 확인
    if hasattr(rag_service.graph, 'memory_saver'):
        # storage 속성으로 저장된 데이터 확인
        if hasattr(rag_service.graph.memory_saver, 'storage'):
            thread_ids = list(rag_service.graph.memory_saver.storage.keys())
            logger.info(f"저장된 스레드 ID 목록: {thread_ids}")
    
    # result의 모든 키값들 출력
    
    
    return query, result


async def test_no_data_query():
    """데이터가 없는 쿼리로 시스템 테스트"""
    _db = await get_db_session()
    rag_service = StockRAGService(_db)
    
    query = "2050년 미래 우주산업에서 삼성전자의 포지션은?"
    stock_code = "005930"
    stock_name = "삼성전자"
    
    logger.info(f"테스트 쿼리: {query}")
    
    result = await rag_service.analyze_stock(
        query=query,
        stock_code=stock_code,
        stock_name=stock_name
    )
    
    logger.info(f"분류 결과: {result.get('classification')}")
    logger.info(f"요약 결과: {result.get('summary')}")
    
    return query, result


async def test_without_stock_info():
    """종목 정보 없이 시스템 테스트"""
    _db = await get_db_session()
    rag_service = StockRAGService(_db)
    
    query = "삼성전자 최근 실적은 어떤가요?"
    
    logger.info(f"테스트 쿼리: {query}")
    
    result = await rag_service.analyze_stock(
        query=query
    )
    
    logger.info(f"분류 결과: {result.get('classification')}")
    logger.info(f"요약 결과: {result.get('summary')}")
    
    return query, result


async def main():

    #settings.POSTGRES_PORT = 5433
    """테스트 메인 함수"""
    logger.info("=== Stockeasy 멀티에이전트 시스템 테스트 시작 ===")
    
    try:
        result1 = None
        result2 = None
        result3 = None
        result4 = None
        query1 = None
        query2 = None
        query3 = None
        query4 = None
        
        # 테스트 케이스 실행
        logger.info("\n=== 테스트 1: 간단한 쿼리 ===")

        query1, result1 = await test_simple_query()
        
        logger.info("\n=== 테스트 2: 복잡한 쿼리 ===")
        #query2, result2 = await test_complex_query()
        
        #logger.info("\n=== 테스트 3: 데이터 없는 쿼리 ===")
        #query3, result3 = await test_no_data_query()
        
        #logger.info("\n=== 테스트 4: 종목 정보 없는 쿼리 ===")
        #query4,result4 = await test_without_stock_info()
        
        logger.info("=== 테스트 완료 ===")

        query_result_pairs = [
            (query1, result1),
            (query2, result2),
            (query3, result3),
            (query4, result4)
        ]
# # result 키값 목록:
#  - query: <class 'str'>
#  - stock_code: <class 'str'>
#  - stock_name: <class 'str'>
#  - session_id: <class 'str'>
#  - user_context: <class 'dict'>
#  - conversation_history: <class 'list'>
#  - question_analysis: <class 'dict'>
#  - execution_plan: <class 'dict'>
#  - agent_results: <class 'dict'>
#  - retrieved_data: <class 'dict'>
#  - summary: <class 'str'>
#  - formatted_response: <class 'str'>
#  - errors: <class 'list'>
#  - metrics: <class 'dict'>
#  - processing_status: <class 'dict'>
        for query, result in query_result_pairs:
            if result is None:
                continue

            print(f"*"*70)
            print(f"## 질문: {query}")
            print(f"-"*70)
            question_classification:QuestionAnalysisResult = result.get('question_analysis', {})
            classification = question_classification.get('classification', {})
            data_requirements = question_classification.get("data_requirements", {})
            # classification의 각 키값이 True인것만 출력
            data_on = {k: v for k, v in data_requirements.items() if v}
            print(f"* 분류 결과: {classification}")
            print(f"* 데이터 요구사항: {data_on}")
            print(f"-"*70)
            #print(f"### 응답: \n{result.get('formatted_response')}")
            print(f"\n{result.get('formatted_response')}")
        
        # 결과 저장 (선택 사항)
        # save_results({
        #     "simple_query": result1,
        #     "complex_query": result2,
        #     "no_data_query": result3,
        #     "without_stock_info": result4
        # })
    except Exception as e:
        logger.error(f"테스트 실행 중 오류 발생: {str(e)}", exc_info=True)


def save_results(results: Dict[str, Any]):
    """테스트 결과를 JSON 파일로 저장"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"test_results_{timestamp}.json"
    
    # 직렬화 가능한 형태로 변환
    serializable_results = {}
    for key, result in results.items():
        serializable_results[key] = {
            "summary": result.get("summary", ""),
            "question_classification": result.get("question_classification", {}),
            "error": result.get("error", "")
        }
    
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(serializable_results, f, ensure_ascii=False, indent=2)
    
    logger.info(f"테스트 결과 저장됨: {filename}")


if __name__ == "__main__":
    # 테스트 실행
    asyncio.run(main()) 