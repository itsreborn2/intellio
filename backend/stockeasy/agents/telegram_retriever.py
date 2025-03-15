"""
텔레그램 메시지 검색 에이전트

이 모듈은 사용자 질문에 관련된 텔레그램 메시지를 검색하는 에이전트를 정의합니다.
기존 TelegramRAGService의 search_messages 기능을 에이전트 형태로 구현합니다.
"""

from typing import Dict, Any, List
from loguru import logger
from datetime import datetime, timezone, timedelta
import re
from zoneinfo import ZoneInfo

from stockeasy.agents.base import BaseAgent
from stockeasy.services.telegram.embedding import TelegramEmbeddingService
from common.services.vector_store_manager import VectorStoreManager
from common.services.retrievers.semantic import SemanticRetriever, SemanticRetrieverConfig
from common.services.retrievers.models import RetrievalResult
from common.core.config import settings
from stockeasy.models.agent_io import AgentState, RetrievedMessage


class TelegramRetrieverAgent(BaseAgent):
    """텔레그램 메시지 검색 에이전트"""
    
    def __init__(self):
        """에이전트 초기화"""
        super().__init__("telegram_retriever")
        self.embedding_service = TelegramEmbeddingService()
    
    async def process(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        텔레그램 메시지 검색 수행
        
        Args:
            state: 현재 상태 (query, classification, stock_code, stock_name 등 포함)
            
        Returns:
            업데이트된 상태 (retrieved_messages 추가)
        """
        try:
            query = state.get("query", "")
            stock_code = state.get("stock_code")
            stock_name = state.get("stock_name")
            classification = state.get("classification")
            
            if not all([query, classification]):
                return {
                    **state,
                    "retrieved_data": {
                        **state.get("retrieved_data", {}),
                        "telegram": []
                    },
                    "telegram_messages": [],
                    "processing_status": {
                        **state.get("processing_status", {}),
                        "telegram_retriever": "insufficient_input"
                    }
                }
            
            # 임계값 설정
            if classification.get("질문주제") == 0:  # 종목 기본정보
                dynamic_threshold = 0.7
            elif classification.get("질문주제") == 1:  # 전망 관련
                dynamic_threshold = 0.5
            else:  # 기타
                dynamic_threshold = 0.3
                
            # 검색할 메시지 수 설정
            k = self._get_message_count(classification)
            
            # 메시지 검색 수행
            messages = await self._search_messages(
                query, stock_code, stock_name, classification, 
                k, dynamic_threshold
            )
            
            # 상태 업데이트
            return {
                **state,
                "retrieved_data": {
                    **state.get("retrieved_data", {}),
                    "telegram": messages
                },
                "telegram_messages": messages,
                "processing_status": {
                    **state.get("processing_status", {}),
                    "telegram_retriever": "completed"
                }
            }
            
        except Exception as e:
            logger.error(f"텔레그램 메시지 검색 중 오류 발생: {e}", exc_info=True)
            errors = state.get("errors", [])
            errors.append({
                "agent": self.get_name(),
                "error": str(e),
                "type": type(e).__name__,
                "timestamp": datetime.now()
            })
            
            return {
                **state,
                "errors": errors,
                "retrieved_data": {
                    **state.get("retrieved_data", {}),
                    "telegram": []
                },
                "telegram_messages": [],
                "processing_status": {
                    **state.get("processing_status", {}),
                    "telegram_retriever": "error"
                }
            }
    
    def _get_message_count(self, classification) -> int:
        """분류에 따른 검색 메시지 수 결정"""
        answer_level = classification.get("답변수준", 1)
        match answer_level:
            case 0: return 5
            case 1: return 15
            case 2: return 20
            case _: return 10
    
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
        seoul_tz = timezone(timedelta(hours=9), 'Asia/Seoul')
        
        # naive datetime인 경우 서버 로컬 시간(Asia/Seoul)으로 간주
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=ZoneInfo("Asia/Seoul"))
            
        # now도 timezone 정보를 포함하도록 수정
        now = datetime.now(seoul_tz)
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

    def _make_user_prompt(self, query: str, stock_code: str, stock_name: str, classification: Dict[str, Any]) -> str:
        """질문 분류 결과에 따라 적절한 사용자 프롬프트를 생성합니다.
        
        Args:
            query (str): 검색 쿼리
            stock_code (str): 종목 코드
            stock_name (str): 종목명
            classification: 질문 분류 결과
            
        Returns:
            str: 생성된 프롬프트
        """
        user_prompt = f"""
종목코드: {stock_code or ''}
종목명: {stock_name or ''}
질문: {query}
"""
        return user_prompt
    
    async def _search_messages(self, query: str, stock_code: str, stock_name: str, 
                              classification: Dict[str, Any], k: int, threshold: float) -> List[RetrievedMessage]:
        """메시지 검색 수행
        
        Args:
            query: 사용자 질문
            stock_code: 종목 코드
            stock_name: 종목명
            classification: 질문 분류 결과
            k: 검색할 메시지 수
            threshold: 유사도 임계값
            
        Returns:
            검색된 메시지 목록
        """
        try:
            # Pinecone 벡터 스토어 연결
            vs_manager = VectorStoreManager(
                embedding_model_type=self.embedding_service.get_model_type(),
                project_name="stockeasy",
                namespace=settings.PINECONE_NAMESPACE_STOCKEASY_TELEGRAM
            )

            # 시맨틱 검색 설정
            semantic_retriever = SemanticRetriever(
                config=SemanticRetrieverConfig(min_score=threshold),
                vs_manager=vs_manager
            )
                    
            # 검색 수행
            retrieval_result: RetrievalResult = await semantic_retriever.retrieve(
                query=self._make_user_prompt(query, stock_code, stock_name, classification), 
                top_k=k * 2,
            )
            
            # 결과 처리
            processed_messages = []
            seen_messages = []  # 중복 검사를 위한 메시지 목록
            
            for doc in retrieval_result.documents:
                message = doc.page_content
                message_created_at = datetime.fromisoformat(doc.metadata["message_created_at"])
                    
                importance = self._calculate_message_importance(message)
                time_weight = self._calculate_time_weight(message_created_at)
                similarity_weight = doc.score if doc.score is not None else 0.5
                
                # 최종 점수 계산 (유사도 50%, 중요도 30%, 시간 20%)
                final_score = (similarity_weight * 0.5) + (importance * 0.3) + (time_weight * 0.2)
                
                if self._is_duplicate(message, seen_messages):
                    continue
                
                # 결과 메시지 생성
                retrieved_message: RetrievedMessage = {
                    "content": message,
                    "created_at": message_created_at,
                    "score": float(final_score),
                    "source": "telegram",
                    "metadata": doc.metadata
                }
                    
                processed_messages.append((retrieved_message, final_score))
                seen_messages.append(message)
            
            # 점수 기준 정렬
            processed_messages.sort(key=lambda x: x[1], reverse=True)
            
            # 최종 결과 반환
            return [msg for msg, _ in processed_messages[:k]]
            
        except Exception as e:
            logger.error(f"메시지 검색 중 오류 발생: {str(e)}", exc_info=True)
            raise Exception(f"메시지 검색 중 오류: {str(e)}") 