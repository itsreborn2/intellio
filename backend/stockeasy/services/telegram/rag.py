"""텔레그램 메시지 검색 및 요약을 위한 RAG 서비스

이 모듈은 텔레그램 메시지에 대한 검색과 요약 기능을 제공합니다.
벡터 DB를 사용하여 의미 기반 검색을 수행하고, LangChain을 사용하여 요약을 생성합니다.
"""

from typing import Any, Dict, List
from loguru import logger
from datetime import datetime, timezone, timedelta
import re
from zoneinfo import ZoneInfo

from stockeasy.services.telegram.question_classifier import QuestionClassification
from common.utils.util import async_retry
from common.services.llm_models import LLMModels
from common.services.retrievers.models import RetrievalResult
from common.services.vector_store_manager import VectorStoreManager
from common.services.retrievers.semantic import SemanticRetriever, SemanticRetrieverConfig
from .embedding import TelegramEmbeddingService
from common.core.config import settings
from langchain_core.messages import AIMessage


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
3. 질문과 관련 없는 메세지는 제외하세요.
4. 구체적인 수치나 통계는 정확히 인용하세요.
5. 메시지 작성자의 주관적 의견과 객관적 사실을 구분하세요.
6. 요약은 명확하고 간결하게 작성하되, 중요한 세부사항은 포함하세요.
7. 채널명, 채널이름은 반드시 제거하세요.
"""

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
    def MakeUserPrompt(self, query: str, stock_code: str, stock_name: str, classification: QuestionClassification= None) -> str:
        """질문 분류 결과에 따라 적절한 사용자 프롬프트를 생성합니다.
        
        Args:
            query (str): 검색 쿼리
            stock_code (str): 종목 코드
        """
        user_prompt = f"""
종목코드: {stock_code}
종목명: {stock_name}
질문: {query}
"""
        return user_prompt
        
    
    @async_retry(retries=3, delay=1.0, exceptions=(Exception,))
    async def search_messages(self, query: str, stock_code: str, stock_name: str, classification: QuestionClassification= None) -> List[str]:
        """쿼리와 관련된 텔레그램 메시지를 검색합니다.
        
        Args:
            query (str): 검색 쿼리
            stock_code (str): 종목 코드
            stock_name (str): 종목 이름
            classification (QuestionClassification): 질문 분류 결과
            k (int): 검색할 메시지 수
            
        Returns:
            List[str]: 검색된 메시지 목록
            
        Raises:
            SearchError: 검색 중 오류 발생 시
        """
        try:
            k = 5
            match classification.답변수준:
                case 0:
                    k = 5
                case 1:
                    k = 15
                case 2:
                    k = 20
                case _:
                    k = 10
            # 주제에 따라서 유사도 점수를 조절해야할듯

            if classification.질문주제 == 0: #종목 기본정보. 정확하게.
                dynamic_threshold = 0.7
            elif classification.질문주제 == 1: #전망 관련. 좀 더 넓게.
                dynamic_threshold = 0.5
            else: #기타
                dynamic_threshold = 0.3
            # 동적 임계값 계산
            #dynamic_threshold = self._calculate_dynamic_threshold(query)
            
            vs_manager = VectorStoreManager(embedding_model_type=self.embedding_service.get_model_type(),
                                            project_name="stockeasy",
                                            namespace=settings.PINECONE_NAMESPACE_STOCKEASY_TELEGRAM)

            semantic_retriever = SemanticRetriever(config=SemanticRetrieverConfig(
                                                        min_score=dynamic_threshold,
                                                        ), vs_manager=vs_manager)
        
            retrieval_result:RetrievalResult = await semantic_retriever.retrieve(
                query= self.MakeUserPrompt(query, stock_code, stock_name, classification),
                top_k=k * 2,
            )
            
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
                    
                formatted_time = message_created_at.strftime("%Y-%m-%d %H:%M")
                formatted_message = f"[{formatted_time}] {message}"
                processed_messages.append((formatted_message, final_score))
                seen_messages.append(message)
                
            processed_messages.sort(key=lambda x: x[1], reverse=True)
            return [msg for msg, _ in processed_messages[:k]]
            
        except Exception as e:
            error_msg = f"메시지 검색 중 오류 발생: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise Exception(error_msg) from e

    def MakeSummaryPrompt(self, classification: QuestionClassification) -> str:
        """질문 분류 결과에 따라 적절한 요약 프롬프트를 생성합니다.
        
        Args:
            classification (QuestionClassification): 질문 분류 결과
            
        Returns:
            str: 생성된 요약 프롬프트
        """
        # 기본 프롬프트 템플릿
        base_prompt = self.summary_prompt.rstrip()
        return base_prompt
        # 아래 프롬프트는 나중에 보완할것.
        
        # 종목 정보가 있는 경우 추가
        stock_info = ""
        if classification.종목명 or classification.종목코드:
            stock_name = classification.종목명 or "해당 종목"
            stock_code = f"({classification.종목코드})" if classification.종목코드 else ""
            stock_info = f"\n\n대상 종목: {stock_name} {stock_code}\n"
        
        # 주제에 따른 프롬프트 조정
        topic_prompt = ""
        if classification.질문주제 == 0:  # 종목기본정보
            topic_prompt = f"""
특히 {stock_name}에 관하여 다음 사항에 중점을 두고 요약해주세요:
- {stock_name}에 관한 기본 정보
- {stock_name} 이외의 다른 종목, 기타 정보는 반드시 제외
- 최근 발표된 실적 및 재무제표 관련 정보
- 주요 재무 지표(PER, PBR, ROE 등)에 대한 언급
- 배당 정책 및 배당률 관련 정보"""
        elif classification.질문주제 == 1:  # 전망
            topic_prompt = f"""
특히 {stock_name}에 관하여 다음 사항에 중점을 두고 요약해주세요:
- {stock_name}의 미래 성장 가능성 및 시장 전망
- 애널리스트들의 투자 의견 및 목표가
- {stock_name} 속한 산업/섹터의 전망 및 경쟁 상황.
- {stock_name} 속하지 않은 다른 섹터의 정보는 반드시 제외.
- 최근 발표된 중장기 전략 및 사업 계획"""
        else:  # 기타
            topic_prompt = f"""
특히 다음 사항에 중점을 두고 요약해주세요:
- {stock_name}에 관한 주요 정보 및 이슈
- 시장 전반적인 동향 및 해당 종목과의 관계
- 투자자들의 주요 관심사 및 논의 주제"""
            
        
        # 답변 수준에 따른 프롬프트 조정
        answer_level_prompt = ""
        if classification.답변수준 == 0:  # 간단한답변
            answer_level_prompt = """
요약은 간결하게 작성하고, 핵심 정보만 포함해주세요. 가능한 100자 이내로 요약해주세요."""
        elif classification.답변수준 == 1:  # 긴설명요구
            answer_level_prompt = """
요약은 상세하게 작성하고, 배경 정보와 근거를 포함해주세요. 필요한 경우 섹션을 나누어 구조화된 형태로 작성해주세요."""
        elif classification.답변수준 == 2:  # 종합적판단
            answer_level_prompt = """
요약은 다양한 관점과 변수를 고려하여 종합적으로 작성해주세요. 상반된 의견이 있다면 균형있게 다루고, 각 의견의 근거를 함께 제시해주세요."""
        else:  # 웹검색
            answer_level_prompt = """
요약은 최신 정보를 중심으로 작성하고, 추가 정보 검색이 필요한 부분은 명시해주세요."""
        
        # 출력 형식 프롬프트 구성
        output_format = "\n\n출력 형식:"
        
        if classification.답변수준 >= 0:
            output_format += """
[종목 분석]
- 주요 종목별 가격 변동 및 이슈
- 업종별 주요 동향
"""
        if classification.답변수준 >= 1:
            output_format += """
[시장 동향]
- 핵심 가격 변동 및 거래량 정보
- 주요 투자자별 매매 동향
"""
        if classification.답변수준 >= 2:
            output_format += """
[전문가 의견]
- 주요 애널리스트 및 전문가 견해
- 투자 전략 및 추천
"""
        if classification.질문주제 >= 2:  # 기타 정보
            output_format += """
[기타 정보]
- 경제 지표 및 정책 관련 소식
- 국제 시장 동향 및 영향
- 금리, 비트코인 등 금융 시장 전반적인 동향"""
        
        # 최종 프롬프트 조합
        final_prompt = base_prompt + stock_info + topic_prompt + answer_level_prompt + output_format
        
        return final_prompt

    @async_retry(retries=2, delay=2.0, exceptions=(Exception,))
    async def summarize(self, query:str, stock_code: str, stock_name: str, found_messages: List[str], classification: QuestionClassification) -> str:
        """메시지 목록을 요약합니다.
        
        Args:
            messages (List[str]): 요약할 메시지 목록
            classification (QuestionClassification): 질문 분류 결과
            
        Returns:
            str: 요약된 내용
            
        Raises:
            SummarizeError: 요약 생성 중 오류 발생 시
        """
        try:
            if not found_messages:
                return "관련된 메시지를 찾을 수 없습니다."
            
            messages_text = "\n-=-=-=-=-=-=-=-=-=-=-\n".join([f"- {msg}" for msg in found_messages])
            messages_text += "\n\n-------\n" + self.MakeUserPrompt(query, stock_code, stock_name, classification)
            # 질문 분류 결과에 따라 프롬프트 생성
            prompt_context = self.MakeSummaryPrompt(classification)
            
            #print(prompt_context)
            response:AIMessage = await self.LLM.agenerate(
                user_query=messages_text, 
                prompt_context=prompt_context
            )

            if not response or not response.content:
                raise Exception("LLM이 빈 응답을 반환했습니다.")

            return response.content
            
        except Exception as e:
            error_msg = f"메시지 요약 중 오류 발생: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise Exception(error_msg) from e
        
    async def test_func(self) -> List[str]:
        """has_document 메타데이터가 true인 메시지만 검색합니다.
        
        Returns:
            List[str]: 검색된 메시지 목록
            
        Raises:
            Exception: 검색 중 오류 발생 시
        """
        try:
            vs_manager = VectorStoreManager(embedding_model_type=self.embedding_service.get_model_type(),
                                            project_name="stockeasy",
                                            namespace=settings.PINECONE_NAMESPACE_STOCKEASY)

            # 메타데이터 필터 설정 - document_gcs_path 필드가 존재하고 비어있지 않은 문서만 검색
            metadata_filter = {
                "document_gcs_path": {"$ne": ""}
            }
            
            semantic_retriever = SemanticRetriever(config=SemanticRetrieverConfig(
                                                        min_score=0.22,
                                                        metadata_filter=metadata_filter
                                                        ), vs_manager=vs_manager)
                    
            retrieval_result:RetrievalResult = await semantic_retriever.retrieve(
                query="아무거나 뽑아봐", 
                top_k=10,
            )
            
            # 결과 처리
            processed_messages = []
            seen_messages = []  # 중복 검사를 위한 메시지 목록
            
            for doc in retrieval_result.documents:
                message = doc.page_content
                
                # 메타데이터에서 document_gcs_path 확인 (이중 체크)
                document_gcs_path = doc.metadata.get("document_gcs_path", "")
                if not document_gcs_path:
                    logger.warning("document_gcs_path가 비어있는 문서입니다.")
                    continue

                message_created_at = datetime.fromisoformat(doc.metadata["message_created_at"])
                    
                message_type = doc.metadata.get("message_type", "알 수 없음")
                formatted_time = message_created_at.strftime("%Y-%m-%d %H:%M")
                formatted_message = f"[{formatted_time}] 타입: {message_type}, 문서경로: {document_gcs_path}, 내용: {message}"
                processed_messages.append((formatted_message, 0))
                seen_messages.append(message)

            
            processed_messages.sort(key=lambda x: x[1], reverse=True)
            # k 변수가 정의되지 않았으므로 10으로 고정
            k = 10
            return [msg for msg, _ in processed_messages[:k]]
            
        except Exception as e:
            error_msg = f"document_gcs_path 메타데이터 필터링 검색 중 오류 발생: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise Exception(error_msg) from e
