import asyncio
from celery import shared_task
from app.core.celery_app import celery
from loguru import logger
import json
import os
from app.services.prompts.table_prompt import TablePrompt
from app.services.prompts.base import GeminiAPI, GeminiLangChain
from app.core.config import settings
from celery.signals import worker_ready
import threading

@worker_ready.connect
def init_worker(**kwargs):
    """Celery worker 초기화 시 실행되는 함수"""
    logger.info(f"RAG Worker 초기화 [ProcessID: {os.getpid()}]")
    gemini_api = GeminiLangChain()
    gemini_api.initialize(settings.GEMINI_API_KEY)

@shared_task(
    name="app.workers.rag.analyze_mode_task",
    queue="rag-processing",
    max_retries=3,
    soft_time_limit=30,
    time_limit=35
)
def analyze_mode_task(content, query, keywords, query_analysis):
    """테이블 분석 작업을 수행하는 Celery task
        Args:
        content: 분석할 테이블 내용
        query: 사용자 질의
        keywords: 키워드 정보 (선택)
        query_analysis: 질의 분석 정보 (선택)
        
    Returns:
        str: 분석 결과 (JSON 형식)
    """
    logger.info("="*50)
    logger.info("analyze_mode_task")
    logger.info(f"Query: {query}")
    logger.info(f"Keywords: {json.dumps(keywords, ensure_ascii=False)}")
    logger.info(f"Content length: {len(content) if content else 0}")
    

    try:
        table_prompt = TablePrompt()
        logger.info(f"테이블 분석 태스크 시작 [ThreadID: {threading.get_ident()}, ProcessID: {os.getpid()}]")
        logger.info(f"컨텐츠 길이: {len(content)}, 쿼리: {query}")
        
        result = table_prompt.analyze(
            content=content,
            query=query,
            keywords=keywords,
            query_analysis=query_analysis
        )
        logger.info(f"Result type: {type(result)}")
        logger.info("="*50)
        return result
            
    except Exception as e:
        logger.error(f"분석 작업 중 오류 발생: {str(e)}")
        logger.info("="*50)
        raise

# @shared_task(
#     name="app.workers.rag.analyze_mode_task",
#     queue="rag-processing",
#     max_retries=3,
#     soft_time_limit=30,
#     time_limit=35
# )
# def analyze_mode_task(content, query, keywords, query_analysis):
#     """테이블 분석 작업을 수행하는 Celery task"""
#     logger.info("="*50)
#     logger.info("analyze_mode_task 시작")
#     logger.info(f"Query: {query}")
#     logger.info(f"Keywords: {json.dumps(keywords, ensure_ascii=False)}")
#     logger.info(f"Content length: {len(content) if content else 0}")
    
#     try:
#         table_prompt = TablePrompt()
#         logger.info("TablePrompt 인스턴스 생성 완료")
        
#         # 새로운 이벤트 루프 생성
#         loop = asyncio.new_event_loop()
#         asyncio.set_event_loop(loop)
#         logger.info("이벤트 루프 생성 완료")
        
#         try:
#             # 비동기 함수 실행
#             result = loop.run_until_complete(
#                 table_prompt.analyze_async(
#                     content=content,
#                     query=query,
#                     keywords=keywords,
#                     query_analysis=query_analysis
#                 )
#             )
#             logger.info(f"Result type: {type(result)}")
#             logger.info("="*50)
#             return result
            
#         except Exception as e:
#             logger.error(f"분석 작업 중 오류 발생: {str(e)}")
#             raise
#         finally:
#             loop.close()
#             logger.info("이벤트 루프 종료")
            
#     except Exception as e:
#         logger.error(f"Task 실행 중 오류 발생: {str(e)}")
#         logger.info("="*50)
#         raise