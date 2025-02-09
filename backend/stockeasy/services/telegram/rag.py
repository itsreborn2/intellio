"""텔레그램 메시지 검색 및 요약을 위한 RAG 서비스

이 모듈은 텔레그램 메시지에 대한 검색과 요약 기능을 제공합니다.
벡터 DB를 사용하여 의미 기반 검색을 수행하고, LangChain을 사용하여 요약을 생성합니다.
"""

from typing import List, Optional
from loguru import logger
from datetime import datetime, timezone, timedelta

from common.services.llm_models import LLMModels
from common.services.retrievers.models import RetrievalResult
from common.services.vector_store_manager import VectorStoreManager
from common.services.retrievers.semantic import SemanticRetriever, SemanticRetrieverConfig
from .embedding import TelegramEmbeddingService
from common.core.config import settings
from langchain_core.messages import AIMessage

class RAGService:
    """텔레그램 메시지 RAG 서비스"""

    def __init__(self):
        """RAG 서비스 초기화
        
        - TelegramEmbeddingService: 텔레그램 메시지 검색을 위한 서비스
        - ChatVertexAI: 요약 생성을 위한 LLM
        """
        self.embedding_service = TelegramEmbeddingService()

        # 싱글톤 인스턴스. LLMModels이 싱글톤인데, 
        # 서비스별로 다른 LLM을 사용하는 경우가 있다면 싱글톤을 해제하고, 더 상위 클래스에서 싱글턴이던 뭐던 처리해야됨.
        # 서비스별로 RAG는 독립적으로 작동해야함.
        self.LLM = LLMModels()  
        
        # 요약을 위한 프롬프트 템플릿
        self.summary_prompt = """당신은 텔레그램 메시지를 요약하는 전문가입니다.
주어진 메시지들을 분석하여 다음 사항을 고려해 요약해주세요:

1. 메시지의 시간 순서를 고려하여 사건의 흐름을 파악하세요.
2. 중복되는 정보는 한 번만 포함하세요.
3. 구체적인 수치나 통계는 정확히 인용하세요.
4. 메시지 작성자의 주관적 의견과 객관적 사실을 구분하세요.
5. 요약은 명확하고 간결하게 작성하되, 중요한 세부사항은 포함하세요.

출력 형식:
- 3-4문단으로 구성된 요약문을 작성하세요.
- 각 문단은 2-3문장으로 구성하세요.
- 시간 순서나 주제별로 내용을 구조화하세요."""


    async def search_messages(self, query: str, k: int = 5) -> List[str]:
        """쿼리와 관련된 텔레그램 메시지를 검색합니다.
        
        Args:
            query (str): 검색 쿼리
            k (int): 검색할 메시지 수
            
        Returns:
            List[str]: 검색된 메시지 목록
        """
        # # 쿼리 임베딩
        # query_embedding = await self.embedding_service.get_single_embedding_async(query)
        
        # # Pinecone에서 유사한 메시지 검색
        # results = await self.embedding_service.search_similar(
        #     query=query,
        #     #index_name="telegram",
        #     top_k=k
        # )

        vs_manager = VectorStoreManager(embedding_model_type=self.embedding_service.get_model_type(),
                                        namespace=settings.PINECONE_NAMESPACE_STOCKEASY)

        semantic_retriever = SemanticRetriever(config=SemanticRetrieverConfig(
                                                        min_score=0.6, # 최소 유사도 0.6 고정
                                                        ), vs_manager=vs_manager)

                
        retrieval_result:RetrievalResult = await semantic_retriever.retrieve(
            query=query, 
            top_k=k,
        )
        
        # 메시지 포맷팅 (시간 정보만 포함)
        messages = []
        for doc in retrieval_result.documents:
            created_at = datetime.fromisoformat(doc.metadata["created_at"]).strftime("%Y-%m-%d %H:%M")
            text = doc.page_content
            messages.append(f"[{created_at}] {text}")

        return messages

    async def summarize(self, messages: List[str]) -> str:
        """메시지 목록을 요약합니다.
        
        Args:
            messages (List[str]): 요약할 메시지 목록
            
        Returns:
            str: 요약된 내용
        """
        try:
            if not messages:
                return "관련된 메시지를 찾을 수 없습니다."
            
            # 메시지들을 하나의 문자열로 결합
            messages_text = "\n".join([f"- {msg}" for msg in messages])
            
            # 프롬프트 생성 및 요약 실행
            #chain = self.summary_prompt | self.llm
            #response = await chain.ainvoke({"messages": messages_text})
            response:AIMessage = await self.LLM.agenerate(user_query=messages_text, prompt_context=self.summary_prompt)

            return response.content
            
        except Exception as e:
            logger.error(f"메시지 요약 중 오류 발생: {str(e)}")
            return "요약 생성 중 오류가 발생했습니다."
