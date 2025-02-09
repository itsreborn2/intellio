"""텔레그램 메시지 검색 및 요약을 위한 RAG 서비스

이 모듈은 텔레그램 메시지에 대한 검색과 요약 기능을 제공합니다.
벡터 DB를 사용하여 의미 기반 검색을 수행하고, LangChain을 사용하여 요약을 생성합니다.
"""

from typing import List
from loguru import logger
from datetime import datetime, timezone, timedelta
import re
from functools import wraps
import asyncio
from typing import TypeVar, Callable, Any

from common.services.llm_models import LLMModels
from common.services.retrievers.models import RetrievalResult
from common.services.vector_store_manager import VectorStoreManager
from common.services.retrievers.semantic import SemanticRetriever, SemanticRetrieverConfig
from .embedding import TelegramEmbeddingService
from common.core.config import settings
from langchain_core.messages import AIMessage

T = TypeVar('T')

def async_retry(
    retries: int = 3,
    delay: float = 1.0,
    backoff_factor: float = 2.0,
    exceptions: tuple = (Exception,)
) -> Callable:
    """비동기 함수에 대한 재시도 데코레이터

    Args:
        retries (int): 최대 재시도 횟수
        delay (float): 초기 대기 시간(초)
        backoff_factor (float): 대기 시간 증가 계수
        exceptions (tuple): 재시도할 예외 목록

    Returns:
        Callable: 데코레이터 함수
    """
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exception = None
            wait_time = delay

            for attempt in range(retries + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt == retries:
                        logger.error(
                            f"함수 {func.__name__} 실행 실패 (최대 재시도 횟수 초과)\n"
                            f"에러: {str(e)}\n"
                            f"Args: {args}\n"
                            f"Kwargs: {kwargs}",
                            exc_info=True
                        )
                        raise
                    
                    logger.warning(
                        f"함수 {func.__name__} 실행 실패 (시도 {attempt + 1}/{retries + 1})\n"
                        f"에러: {str(e)}\n"
                        f"대기 시간: {wait_time}초"
                    )
                    
                    await asyncio.sleep(wait_time)
                    wait_time *= backoff_factor
            
            raise last_exception
        return wrapper
    return decorator


class TelegramRAGService:
    """텔레그램 메시지 RAG 서비스"""

    def __init__(self):
        """RAG 서비스 초기화
        
        - TelegramEmbeddingService: 텔레그램 메시지 검색을 위한 서비스
        - ChatVertexAI: 요약 생성을 위한 LLM
        """
        self.embedding_service = TelegramEmbeddingService()
        self.LLM = LLMModels()
        
        # 요약을 위한 프롬프트 템플릿
        self.summary_prompt = """당신은 금융 시장과 주식 관련 텔레그램 메시지를 분석하고 요약하는 전문가입니다.
주어진 메시지들을 분석하여 다음 사항을 고려해 요약해주세요:

1. 메시지의 시간 순서를 고려하여 사건의 흐름을 파악하세요.
2. 중복되는 정보는 한 번만 포함하세요.
3. 구체적인 수치나 통계는 정확히 인용하세요.
4. 메시지 작성자의 주관적 의견과 객관적 사실을 구분하세요.
5. 요약은 명확하고 간결하게 작성하되, 중요한 세부사항은 포함하세요.

출력 형식:
[시장 동향]
- 핵심 가격 변동 및 거래량 정보
- 주요 투자자별 매매 동향

[주요 이벤트]
- 실적/공시 관련 정보
- 시장 영향을 미친 주요 뉴스

[투자 시사점]
- 주요 투자 의사결정 관련 정보
- 향후 주시해야 할 포인트

* 모든 수치 정보는 정확한 값과 함께 변동률(%)도 표시
* 시간 정보는 반드시 포함
* 검증되지 않은 정보는 '(미확인)' 표시"""

    def _calculate_message_importance(self, message: str) -> float:
        """메시지의 중요도를 계산합니다.

        Args:
            message (str): 중요도를 계산할 메시지

        Returns:
            float: 0~1 사이의 중요도 점수
        """
        importance_score = 0.0
        
        # 1. 금액/수치 정보 포함 여부 (40%)
        if re.search(r'[0-9]+(?:,[0-9]+)*(?:\.[0-9]+)?%?원?', message):
            importance_score += 0.4
            
        # 2. 주요 키워드 포함 여부 (40%)
        important_keywords = [
            '실적', '공시', '매출', '영업이익', '순이익',
            '계약', '특허', '인수', '합병', 'M&A',
            '상한가', '하한가', '급등', '급락',
            '목표가', '투자의견', '리포트'
        ]
        keyword_count = sum(1 for keyword in important_keywords if keyword in message)
        if keyword_count > 0:
            importance_score += min(0.4, keyword_count * 0.2)  # 키워드당 0.2점, 최대 0.4점
        
        # 3. 메시지 길이 가중치 (20%)
        msg_length = len(message)
        if 50 <= msg_length <= 500:
            importance_score += 0.2
        elif 20 <= msg_length < 50 or 500 < msg_length <= 1000:
            importance_score += 0.1
            
        return importance_score

    def _is_duplicate(self, message: str, existing_messages: List[str], threshold: float = 0.8) -> bool:
        """메시지의 중복 여부를 확인합니다.

        Args:
            message (str): 검사할 메시지
            existing_messages (List[str]): 기존 메시지 목록
            threshold (float): 중복 판단 임계값

        Returns:
            bool: 중복 여부
        """
        from difflib import SequenceMatcher
        
        for existing_msg in existing_messages:
            similarity = SequenceMatcher(None, message, existing_msg).ratio()
            if similarity > threshold:
                return True
        return False

    def _calculate_time_weight(self, created_at: datetime) -> float:
        """시간 기반 가중치를 계산합니다.

        Args:
            created_at (datetime): 메시지 생성 시간

        Returns:
            float: 0~1 사이의 가중치 값
        """
        # created_at이 naive datetime인 경우 UTC로 가정
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
            
        now = datetime.now(timezone.utc)
        time_diff = now - created_at
        
        # 24시간 이내: 0.8 ~ 1.0
        if time_diff <= timedelta(hours=24):
            return 1.0 - (time_diff.total_seconds() / (24 * 3600)) * 0.2
            
        # 1주일 이내: 0.6 ~ 0.8
        elif time_diff <= timedelta(days=7):
            days_old = time_diff.total_seconds() / (24 * 3600)
            return 0.8 - ((days_old - 1) / 6) * 0.2
            
        # 1달 이내: 0.4 ~ 0.6
        elif time_diff <= timedelta(days=30):
            days_old = time_diff.total_seconds() / (24 * 3600)
            return 0.6 - ((days_old - 7) / 23) * 0.2
            
        # 1달 이상: 0.4
        else:
            return 0.4

    def _calculate_dynamic_threshold(self, query: str) -> float:
        """쿼리 특성에 따른 동적 임계값을 계산합니다.

        Args:
            query (str): 검색 쿼리

        Returns:
            float: 계산된 임계값
        """
        base_threshold = 0.6
        
        # 1. 쿼리 길이에 따른 조정
        query_length = len(query)
        if query_length < 10:
            base_threshold += 0.1  # 짧은 쿼리는 더 엄격하게
        elif query_length > 50:
            base_threshold -= 0.1  # 긴 쿼리는 더 관대하게
            
        # 2. 특정 키워드 포함 여부에 따른 조정
        important_keywords = ['실적', '공시', '매출', '영업이익', '순이익', '계약', '특허']
        if any(keyword in query for keyword in important_keywords):
            base_threshold += 0.05  # 중요 키워드 포함 시 더 엄격하게
            
        # 3. 수치 포함 여부에 따른 조정
        if re.search(r'[0-9]+(?:,[0-9]+)*(?:\.[0-9]+)?%?원?', query):
            base_threshold += 0.05  # 수치 포함 시 더 엄격하게
            
        return min(max(base_threshold, 0.4), 0.9)  # 0.4 ~ 0.9 사이로 제한

    @async_retry(retries=3, delay=1.0, exceptions=(Exception,))
    async def search_messages(self, query: str, k: int = 5) -> List[str]:
        """쿼리와 관련된 텔레그램 메시지를 검색합니다.
        
        Args:
            query (str): 검색 쿼리
            k (int): 검색할 메시지 수
            
        Returns:
            List[str]: 검색된 메시지 목록
            
        Raises:
            SearchError: 검색 중 오류 발생 시
        """
        try:
            # 동적 임계값 계산
            dynamic_threshold = self._calculate_dynamic_threshold(query)
            
            vs_manager = VectorStoreManager(embedding_model_type=self.embedding_service.get_model_type(),
                                          namespace=settings.PINECONE_NAMESPACE_STOCKEASY)

            semantic_retriever = SemanticRetriever(config=SemanticRetrieverConfig(
                                                        min_score=dynamic_threshold,
                                                        ), vs_manager=vs_manager)
                    
            retrieval_result:RetrievalResult = await semantic_retriever.retrieve(
                query=query, 
                top_k=k * 2,
            )
            
            processed_messages = []
            seen_messages = []  # 중복 검사를 위한 메시지 목록
            
            for doc in retrieval_result.documents:
                message = doc.page_content
                created_at = datetime.fromisoformat(doc.metadata["created_at"])
                    
                importance = self._calculate_message_importance(message)
                time_weight = self._calculate_time_weight(created_at)
                similarity_weight = doc.score if doc.score is not None else 0.5
                
                # 최종 점수 계산 (유사도 50%, 중요도 30%, 시간 20%)
                final_score = (similarity_weight * 0.5) + (importance * 0.3) + (time_weight * 0.2)
                
                if self._is_duplicate(message, seen_messages):
                    continue
                    
                formatted_time = created_at.strftime("%Y-%m-%d %H:%M")
                formatted_message = f"[{formatted_time}] {message}"
                processed_messages.append((formatted_message, final_score))
                seen_messages.append(message)
                
            processed_messages.sort(key=lambda x: x[1], reverse=True)
            return [msg for msg, _ in processed_messages[:k]]
            
        except Exception as e:
            error_msg = f"메시지 검색 중 오류 발생: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise Exception(error_msg) from e

    @async_retry(retries=2, delay=2.0, exceptions=(Exception,))
    async def summarize(self, messages: List[str]) -> str:
        """메시지 목록을 요약합니다.
        
        Args:
            messages (List[str]): 요약할 메시지 목록
            
        Returns:
            str: 요약된 내용
            
        Raises:
            SummarizeError: 요약 생성 중 오류 발생 시
        """
        try:
            if not messages:
                return "관련된 메시지를 찾을 수 없습니다."
            
            messages_text = "\n".join([f"- {msg}" for msg in messages])
            
            response:AIMessage = await self.LLM.agenerate(
                user_query=messages_text, 
                prompt_context=self.summary_prompt
            )

            if not response or not response.content:
                raise Exception("LLM이 빈 응답을 반환했습니다.")

            return response.content
            
        except Exception as e:
            error_msg = f"메시지 요약 중 오류 발생: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise Exception(error_msg) from e
