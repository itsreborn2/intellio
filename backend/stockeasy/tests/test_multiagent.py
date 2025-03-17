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
from stockeasy.services.telegram.rag_service import StockRAGService


async def test_simple_query():
    """간단한 쿼리로 시스템 테스트"""
    _db = await get_db_session()
    rag_service = StockRAGService(_db)
    
    query = "삼성전자 최근 실적은 어떤가요?"
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
    
    return result


async def test_complex_query():
    """복잡한 쿼리로 시스템 테스트"""
    _db = await get_db_session()
    rag_service = StockRAGService(_db)
    
    query = "NAND 반도체 시장 전망과 관련해 삼성전자의 경쟁력은 어떤가요?"
    #query = "HBM 시장 전망과 관련해 삼성전자의 경쟁력은?"
    
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
    
    # 트레이스 정보 확인
    if hasattr(rag_service.graph, 'memory_saver'):
        # storage 속성으로 저장된 데이터 확인
        if hasattr(rag_service.graph.memory_saver, 'storage'):
            thread_ids = list(rag_service.graph.memory_saver.storage.keys())
            logger.info(f"저장된 스레드 ID 목록: {thread_ids}")
    
    return result


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
    
    return result


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
    
    return result


async def main():
    """테스트 메인 함수"""
    logger.info("=== Stockeasy 멀티에이전트 시스템 테스트 시작 ===")
    
    try:
        # 테스트 케이스 실행
        logger.info("\n=== 테스트 1: 간단한 쿼리 ===")
        result1 = await test_simple_query()
        
        #logger.info("\n=== 테스트 2: 복잡한 쿼리 ===")
        #result2 = await test_complex_query()
        
        #logger.info("\n=== 테스트 3: 데이터 없는 쿼리 ===")
        #result3 = await test_no_data_query()
        
        #logger.info("\n=== 테스트 4: 종목 정보 없는 쿼리 ===")
        #result4 = await test_without_stock_info()
        
        logger.info("=== 테스트 완료 ===")
        
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