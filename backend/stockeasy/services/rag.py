from datetime import datetime
import json
from typing import List
from loguru import logger
import re
from functools import wraps
import asyncio
from typing import TypeVar, Callable, Any
from zoneinfo import ZoneInfo

from common.services.embedding_models import EmbeddingModelType
from common.services.retrievers.models import RetrievalResult
from common.services.retrievers.semantic import SemanticRetriever, SemanticRetrieverConfig
from common.services.vector_store_manager import VectorStoreManager
from stockeasy.services.telegram.question_classifier import QuestionClassifierService
from common.utils.util import async_retry, dict_to_formatted_str
from stockeasy.services.embedding import StockeasyEmbeddingService
from common.services.llm_models import LLMModels
from common.core.config import settings
from langchain_core.messages import AIMessage
from stockeasy.services.telegram.rag import TelegramRAGService

# 멀티에이전트 이전의 RAG 서비스
# 추후 사용하지 않을 예정.
class StockeasyRAGService:
    """텔레그램 메시지 RAG 서비스"""

    def __init__(self):
        """RAG 서비스 초기화
        
        - TelegramEmbeddingService: 텔레그램 메시지 검색을 위한 서비스
        - ChatVertexAI: 요약 생성을 위한 LLM
        """
        self.embedding_service = StockeasyEmbeddingService()
        self.LLM = LLMModels()
        logger.info("StockeasyRAGService 초기화 완료")

    async def user_question(self, stock_code: str, stock_name: str, query: str) -> str:
        """쿼리와 관련된 텔레그램 메시지를 검색합니다.
        
        Args:
            query (str): 검색할 쿼리

        """
        logger.info(f"StockeasyRAGService.user_question 호출 - 쿼리: {query}")
        try:
            # 1. 질문 분류
            logger.info("질문 분류 시작")
            question_classifier = QuestionClassifierService()
            classification = question_classifier.classify_question(query, stock_code, stock_name)
            
            logger.info(f"==== 질문 분류 결과 ====")
            logger.info(dict_to_formatted_str(classification.to_dict_with_labels()))

            answer_list = []
            #2. 분류 결과에 따른 DB 검색
            # search_results = await rag_service.search_by_classification(
            #     question=request.question,
            #     classification=classification
            # )
            #여러가지 RAG에 질의 후 종합답변 생성?
            # 기업리포트 검색
            answer = await self.search_by_temp(query, stock_code, stock_name)
            answer_list.append("기업리포트 검색 결과")
            answer_list.append(answer)

            # 텔레그램 메시지 검색
            logger.info("텔레그램 메시지 검색 시작")
            telegram_rag = TelegramRAGService()
            
            answer = await telegram_rag.search_messages(
                query=query,
                stock_code=stock_code,
                stock_name=stock_name,
                classification=classification
            )
            logger.info(f"텔레그램 메시지 검색 결과: {len(answer)}개 메시지 검색됨")

            # 3. LLM에 질의하여 답변 생성
            logger.info("답변 생성 시작")
            summary = await telegram_rag.summarize(
                query=query,
                found_messages=answer,
                stock_code=stock_code,
                stock_name=stock_name,
                classification=classification
            )
            logger.info(f"답변 생성 완료: {summary[:100]}...")

            answer_list.append("\n\n텔레그램 메시지 검색 결과")
            answer_list.append(summary)

            return "\n".join(answer_list)
        except Exception as e:
            logger.error(f"user_question 처리 중 오류 발생: {str(e)}", exc_info=True)
            raise
    
        


    