from typing import List
from loguru import logger
from datetime import datetime, timezone, timedelta
import re
from functools import wraps
import asyncio
from typing import TypeVar, Callable, Any
from zoneinfo import ZoneInfo

from stockeasy.services.telegram.question_classifier import QuestionClassifierService
from common.utils.util import async_retry, dict_to_formatted_str
from stockeasy.services.embedding import StockeasyEmbeddingService
from common.services.llm_models import LLMModels
from common.services.retrievers.models import RetrievalResult
from common.services.vector_store_manager import VectorStoreManager
from common.services.retrievers.semantic import SemanticRetriever, SemanticRetrieverConfig
from common.core.config import settings
from langchain_core.messages import AIMessage

from stockeasy.services.telegram.rag import TelegramRAGService

class StockeasyRAGService:
    """텔레그램 메시지 RAG 서비스"""

    def __init__(self):
        """RAG 서비스 초기화
        
        - TelegramEmbeddingService: 텔레그램 메시지 검색을 위한 서비스
        - ChatVertexAI: 요약 생성을 위한 LLM
        """
        self.embedding_service = StockeasyEmbeddingService()
        self.LLM = LLMModels()

    async def user_question(self, query: str) -> List[str]:
        """쿼리와 관련된 텔레그램 메시지를 검색합니다.
        
        Args:
            query (str): 검색할 쿼리

        """
        # 1. 질문 분류
        question_classifier = QuestionClassifierService()
        classification = question_classifier.classify_question(query)
        
        logger.info(f"==== 질문 분류 결과 ====")
        logger.info( dict_to_formatted_str(classification.to_dict_with_labels()) )

        # 2. 분류 결과에 따른 DB 검색
        # search_results = await rag_service.search_by_classification(
        #     question=request.question,
        #     classification=classification
        # )
        # 여러가지 RAG에 질의 후 종합답변 생성?


        # 텔레그램 메시지 검색
        telegram_rag = TelegramRAGService()
        answer = await telegram_rag.search_messages(
            query=query,
            classification=classification
        )

        # 3. LLM에 질의하여 답변 생성
        summary = await telegram_rag.summarize(
            messages=answer,
            classification=classification
        )

        return summary


    