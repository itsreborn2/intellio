import asyncio
from celery import shared_task
from app.core.celery_app import celery
from loguru import logger
import json
import os
from app.services.prompts.table_prompt import TablePrompt
from app.services.prompts.base import  LLMModels
from app.core.config import settings
from celery.signals import worker_ready
import threading

@worker_ready.connect
def init_worker(**kwargs):
    """Celery worker 초기화 시 실행되는 함수"""
    logger.info(f"RAG Worker 초기화 [ProcessID: {os.getpid()}]")
    gemini_api = LLMModels() 
    #gemini_api.initialize(settings.GEMINI_API_KEY)

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
