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
    async def search_by_temp(self, question: str, stock_code:str, stock_name:str) -> str:
        """임시 검색 기능"""
        
        if not stock_code or not stock_name:
            logger.error("stock_code 또는 stock_name이 없습니다.")
            return ""
        
        vs_manager = VectorStoreManager(
            EmbeddingModelType.OPENAI_3_LARGE,   
            project_name="stockeasy",
            namespace=settings.PINECONE_NAMESPACE_STOCKEASY,
        )

        semantic_retriever = SemanticRetriever(config=SemanticRetrieverConfig(
                                                        min_score=0.6, # 최소 유사도 0.6 고정
                                                        ), vs_manager=vs_manager)
        filtersMetadata = { "report_type": '기업리포트', "stock_code": stock_code }
        all_chunks:RetrievalResult = await semantic_retriever.retrieve(
            query=question, 
            top_k=10,
            filters=filtersMetadata
        )
        logger.info(f"기업리포트 검색 결과: {len(all_chunks.documents)}개 문서 검색됨")

        for idx, doc in enumerate(all_chunks.documents[:3]):
            logger.warning(f"문서 #{idx}")
            score_str = f"{doc.score:.4f}" if doc.score is not None else "0.0000"
            logger.warning(f"- 유사도 점수: {score_str}")
            meta = doc.metadata.copy()
            meta.pop("coordinates")
            logger.warning(f"- 메타데이터: {json.dumps(meta, ensure_ascii=False)}")
            logger.warning(f"- 내용: {doc.page_content[:200]}...")  # 내용이 너무 길 수 있으므로 200자로 제한
        logger.info(f"검색된 총 청크 수: {len(all_chunks.documents)}")


        doc_contexts = []
        for i, doc in enumerate(all_chunks.documents):
            if not doc.page_content or doc.page_content.strip() == "":
                continue
            metadata = doc.metadata
            doc_contexts.append(
                #f"문서 ID: {metadata.get('document_id', 'N/A')}\n"
                #f"페이지: {metadata.get('page_number', 'N/A')}\n"
                f"내용: {doc.page_content}"
            )

        # 생성형AI에게 수집한 context를 바탕으로 query를 질문
        # 프롬프트 생성 및 응답
        today = datetime.now(ZoneInfo("Asia/Seoul")).strftime("%Y년 %m월 %d일")
        base_prompt = """당신은 문서를 분석하고 사용자의 질문에 답변하는 AI 어시스턴트입니다.
주어진 문서의 내용만을 기반으로 답변해야 하며, 문서에 없는 내용은 '관련 내용 없음' 을 응답해.

오늘 날짜 : {today}
"""
        user_prompt = """
문서 : {docs}

질문: {question}
"""
        prompt_context = base_prompt.format(today=today)# +  '\n-=-=-=-=-=-=-=-=-=-=-=-=-=\n'.join(doc_contexts)
        user_context = user_prompt.format(question=question, docs='\n-=-=-=-=-=-=-=-=-=-=-=-=-=\n'.join(doc_contexts) ) 
        
        #self.LLM.change_llm("openai", settings.OPENAI_API_KEY)
        self.LLM.change_llm("gemini", settings.GEMINI_API_KEY)
        
        message:AIMessage = self.LLM.generate(
                prompt_context=prompt_context,
                user_query=user_context,

            )
        
        return message.content
        
        


    