import asyncio
from celery import shared_task
from dotenv import load_dotenv
from doceasy.core.celery_app import celery
from loguru import logger
import json
import os
from doceasy.services.prompts.table_prompt import TablePrompt
from doceasy.services.prompts.base import  LLMModels
from celery.signals import worker_ready
import threading

@worker_ready.connect
def init_worker(**kwargs):
    """Celery worker 초기화 시 실행되는 함수"""
    load_dotenv(override=True)
    logger.info(f"RAG Worker 초기화 [ProcessID: {os.getpid()}]")
    gemini_api = LLMModels() 
    #gemini_api.initialize(settings.GEMINI_API_KEY)

@shared_task(
    name="doceasy.workers.rag.analyze_table_mode_task",
    queue="rag-processing",
    max_retries=3,
    soft_time_limit=30,
    time_limit=35
)
def analyze_table_mode_task(chunk_content, query, keywords, query_analysis):
    """테이블 분석 작업을 수행하는 Celery task
        Args:
        content: 분석할 테이블 내용. 문서의 청크 내용이 들어있음.
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
    logger.info(f"Content length: {len(chunk_content) if chunk_content else 0}")
    

    try:
        table_prompt = TablePrompt()
        logger.info(f"테이블 분석 태스크 시작 [ThreadID: {threading.get_ident()}, ProcessID: {os.getpid()}]")
        logger.info(f"컨텐츠 길이: {len(chunk_content)}, 쿼리: {query}")
        
        result = table_prompt.analyze(
            chunk_content=chunk_content,
            user_query=query,
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
