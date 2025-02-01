"""텔레그램 메시지 검색 및 요약을 위한 RAG 서비스

이 모듈은 텔레그램 메시지에 대한 검색과 요약 기능을 제공합니다.
Pinecone을 사용하여 벡터 검색을 수행하고, LangChain을 사용하여 요약을 생성합니다.
"""

from typing import List, Optional
from loguru import logger
from app.services.telegram.embedding import EmbeddingService
from app.core.config import settings
from langchain.chat_models import ChatVertexAI
from langchain.prompts import ChatPromptTemplate

class RAGService:
    """텔레그램 메시지 RAG 서비스"""

    def __init__(self):
        """RAG 서비스 초기화
        
        - EmbeddingService: 벡터 검색을 위한 서비스
        - ChatVertexAI: 요약 생성을 위한 LLM
        """
        self.embedding_service = EmbeddingService()
        self.llm = ChatVertexAI(
            model_name="chat-bison",
            max_output_tokens=1024,
            temperature=0.1
        )
        
        # 요약을 위한 프롬프트 템플릿
        self.summary_prompt = ChatPromptTemplate.from_messages([
            ("system", "다음 텔레그램 메시지들을 간단하게 요약해주세요. 중요한 정보와 핵심 내용을 포함해야 합니다."),
            ("user", "{messages}")
        ])

    async def search_messages(self, query: str, k: int = 5) -> List[str]:
        """쿼리와 관련된 텔레그램 메시지를 검색합니다.
        
        Args:
            query (str): 검색 쿼리
            k (int): 검색할 메시지 수
            
        Returns:
            List[str]: 검색된 메시지 목록
        """
        # 쿼리 임베딩
        query_embedding = await self.embedding_service.get_embeddings([query])
        
        # Pinecone에서 유사한 메시지 검색
        results = await self.embedding_service.search(
            index_name="telegram",
            query_embedding=query_embedding[0],
            top_k=k
        )
        
        # 메시지 텍스트 추출
        messages = [result.metadata.get("text", "") for result in results]
        return messages

    async def summarize(self, messages: List[str]) -> str:
        """메시지 목록을 요약합니다.
        
        Args:
            messages (List[str]): 요약할 메시지 목록
            
        Returns:
            str: 요약된 내용
        """
        # 메시지들을 하나의 문자열로 결합
        messages_text = "\n".join([f"- {msg}" for msg in messages])
        
        # 프롬프트 생성
        chain = self.summary_prompt | self.llm
        
        # 요약 생성
        response = await chain.ainvoke({"messages": messages_text})
        return response.content
