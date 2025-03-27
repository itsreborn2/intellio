"""
텔레그램 메시지 검색 에이전트 모듈

이 모듈은 사용자 질문에 관련된 텔레그램 메시지를 검색하는 에이전트 클래스를 구현합니다.
기존 텔레그램 검색 기능을 QuestionAnalyzerAgent의 결과를 활용하도록 개선합니다.
"""

import re
import json
import asyncio
import hashlib
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from loguru import logger
from typing import Dict, List, Any, Optional, Set, cast, Union


from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import JsonOutputParser
#from sqlalchemy import UUID
from uuid import UUID
from stockeasy.prompts.telegram_prompts import TELEGRAM_SUMMARY_PROMPT
from common.services.agent_llm import get_agent_llm, get_llm_for_agent
from common.utils.util import async_retry
from common.core.config import settings
from stockeasy.services.telegram.embedding import TelegramEmbeddingService
from common.models.token_usage import ProjectType

from common.services.vector_store_manager import VectorStoreManager
from common.services.retrievers.semantic import SemanticRetriever, SemanticRetrieverConfig
from common.services.retrievers.models import RetrievalResult
from stockeasy.models.agent_io import RetrievedAllAgentData, RetrievedTelegramMessage
from langchain_core.messages import AIMessage
from stockeasy.agents.base import BaseAgent
from sqlalchemy.ext.asyncio import AsyncSession

class TelegramRetrieverAgent(BaseAgent):
    """텔레그램 메시지 검색 에이전트"""
    
    def __init__(self, name: Optional[str] = None, db: Optional[AsyncSession] = None):
        """
        텔레그램 메시지 검색 에이전트 초기화
        
        Args:
            name: 에이전트 이름 (지정하지 않으면 클래스명 사용)
            db: 데이터베이스 세션 객체 (선택적)
        """
        super().__init__(name, db)
        self.retrieved_str = "telegram_messages"
        self.embedding_service = TelegramEmbeddingService()
        self.llm, self.model_name, self.provider = get_llm_for_agent("telegram_retriever_agent")
        self.agent_llm = get_agent_llm("telegram_retriever_agent")
        self.parser = JsonOutputParser()
        logger.info(f"TelegramRetrieverAgent initialized with provider: {self.provider}, model: {self.model_name}")
    
    async def process(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        사용자 쿼리와 분류 정보를 기반으로 텔레그램 메시지를 검색합니다.
        
        Args:
            state: 현재 상태 정보를 포함하는 딕셔너리
            
        Returns:
            업데이트된 상태 딕셔너리
        """
        try:
            # 성능 측정 시작
            start_time = datetime.now()
            logger.info("TelegramRetrieverAgent starting processing")
            
            # 현재 쿼리 및 세션 정보 추출
            query = state.get("query", "")
            
            # 질문 분석 결과 추출 (새로운 구조)
            question_analysis = state.get("question_analysis", {})
            entities = question_analysis.get("entities", {})
            classification = question_analysis.get("classification", {})
            data_requirements = question_analysis.get("data_requirements", {})
            keywords = question_analysis.get("keywords", [])
            detail_level = question_analysis.get("detail_level", "보통")
            
            # 엔티티에서 종목 정보 추출
            stock_code = entities.get("stock_code", state.get("stock_code"))
            stock_name = entities.get("stock_name", state.get("stock_name"))
            sector = entities.get("sector", "")
            
            if not query:
                logger.warning("Empty query provided to TelegramRetrieverAgent")
                self._add_error(state, "검색 쿼리가 제공되지 않았습니다.")
                return state
            
            logger.info(f"TelegramRetrieverAgent processing query: {query}")
            #logger.info(f"Classification data: {classification}")
            #logger.info(f"State keys: {state.keys()}")
            #logger.info(f"Entities: {entities}")
            #logger.info(f"Data requirements: {data_requirements}")
            
            # 동적 임계값 및 메시지 수 설정
            threshold = self._calculate_dynamic_threshold(classification)
            message_count = self._get_message_count(classification)
            
            # 검색 쿼리 생성 (보다 정확한 검색을 위해 클래스 및 의도 정보 활용)
            search_query = self._make_search_query(query, stock_code, stock_name, classification, sector)
            
            user_context = state.get("user_context", {})
            user_id = user_context.get("user_id", None)

            # 메시지 검색 실행
            messages:List[RetrievedTelegramMessage] = await self._search_messages(
                user_id=user_id,
                search_query= search_query,
                k=message_count, 
                threshold=threshold
            )
            
            
            # 메세지 요약
            summary = await self.summarize(query, stock_code, stock_name, messages, classification, user_id)

            # 검색 결과가 없는 경우
            if not messages:
                logger.warning("텔레그램 메시지 검색 결과가 없습니다.")
                
                # 실행 시간 계산
                end_time = datetime.now()
                duration = (end_time - start_time).total_seconds()
                
                # 새로운 구조로 상태 업데이트 (결과 없음)
                state["agent_results"] = state.get("agent_results", {})
                state["agent_results"]["telegram_retriever"] = {
                    "agent_name": "telegram_retriever",
                    "status": "partial_success",
                    "data": [],
                    "error": None,
                    "execution_time": duration,
                    "metadata": {
                        "message_count": 0,
                        "threshold": threshold
                    }
                }
                
                # 타입 주석을 사용한 데이터 할당
                if "retrieved_data" not in state:
                    state["retrieved_data"] = {}
                retrieved_data = cast(RetrievedAllAgentData, state["retrieved_data"])
                telegram_messages: List[RetrievedTelegramMessage] = []
                retrieved_data["telegram_messages"] = telegram_messages
                
                state["processing_status"] = state.get("processing_status", {})
                state["processing_status"]["telegram_retriever"] = "completed_no_data"
                
                # 메트릭 기록
                state["metrics"] = state.get("metrics", {})
                state["metrics"]["telegram_retriever"] = {
                    "start_time": start_time,
                    "end_time": end_time,
                    "duration": duration,
                    "status": "completed_no_data",
                    "error": None,
                    "model_name": self.model_name
                }
                
                logger.info(f"TelegramRetrieverAgent completed in {duration:.2f} seconds, found 0 messages")
                return state
                
            # 수행 시간 계산
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            # 새로운 구조로 상태 업데이트
            state["agent_results"] = state.get("agent_results", {})
            state["agent_results"]["telegram_retriever"] = {
                "agent_name": "telegram_retriever",
                "status": "success",
                "data": {
                    "summary": summary,
                    "messages": messages
                },
                "error": None,
                "execution_time": duration,
                "metadata": {
                    "message_count": len(messages),
                    "threshold": threshold
                }
            }
            
            # 타입 주석을 사용한 데이터 할당
            if "retrieved_data" not in state:
                state["retrieved_data"] = {}
            retrieved_data = cast(RetrievedAllAgentData, state["retrieved_data"])

            retrieved_data[self.retrieved_str] = {
                    "summary": summary,
                    "messages": messages
                }
            
            state["processing_status"] = state.get("processing_status", {})
            state["processing_status"]["telegram_retriever"] = "completed"
            
            # 메트릭 기록
            state["metrics"] = state.get("metrics", {})
            state["metrics"]["telegram_retriever"] = {
                "start_time": start_time,
                "end_time": end_time,
                "duration": duration,
                "status": "completed",
                "error": None,
                "model_name": self.model_name
            }
            
            logger.info(f"TelegramRetrieverAgent completed in {duration:.2f} seconds, found {len(messages)} messages")
            return state
            
        except Exception as e:
            logger.exception(f"Error in TelegramRetrieverAgent: {str(e)}")
            self._add_error(state, f"텔레그램 메시지 검색 에이전트 오류: {str(e)}")
            
            # 오류 상태 업데이트
            state["agent_results"] = state.get("agent_results", {})
            state["agent_results"]["telegram_retriever"] = {
                "agent_name": "telegram_retriever",
                "status": "failed",
                "data": [],
                "error": str(e),
                "execution_time": 0,
                "metadata": {}
            }
            
            # 타입 주석을 사용한 데이터 할당
            if "retrieved_data" not in state:
                state["retrieved_data"] = {}
            retrieved_data = cast(RetrievedAllAgentData, state["retrieved_data"])
            retrieved_data[self.retrieved_str] = {"summary": "", "messages": "" }
            
            state["processing_status"] = state.get("processing_status", {})
            state["processing_status"]["telegram_retriever"] = "error"
            
            return state
    @async_retry(retries=2, delay=2.0, exceptions=(Exception,))
    async def summarize(self, query:str, stock_code: str, stock_name: str, found_messages: List[RetrievedTelegramMessage], classification: Dict[str, Any], user_id: Optional[Union[str, UUID]] = None) -> str:
        """메시지 목록을 요약합니다.
        
        Args:
            query: 사용자 질문
            stock_code: 종목 코드
            stock_name: 종목명
            found_messages: 요약할 메시지 목록
            classification: 질문 분류 결과
            user_id: 사용자 ID (문자열 또는 UUID 객체)
            
        Returns:
            str: 요약된 내용
            
        Raises:
            SummarizeError: 요약 생성 중 오류 발생 시
        """
        try:
            if not found_messages:
                return "관련된 메시지를 찾을 수 없습니다."
            
            # 각 메시지에서 content와 message_created_at만 추출하여 정렬된 형태로 표시
            formatted_messages = []
            for msg in found_messages:
                created_at = msg["message_created_at"].strftime("%Y-%m-%d %H:%M")
                content = msg["content"]
                formatted_messages.append(f"[{created_at}] {content}")
            
            # 형식화된 메시지를 구분선으로 연결
            messages_text = "\n------\n".join(formatted_messages)
            messages_text += f"\n\n-------\n사용자 질문: {query}\n종목코드:{stock_code}\n종목명:{stock_name}"
            
            # 질문 분류 결과에 따라 프롬프트 생성
            prompt_context = self.MakeSummaryPrompt(classification)
            
            # 프롬프트와 메시지를 하나의 문자열로 결합
            combined_prompt = f"{prompt_context}\n\n내용: \n{messages_text}"
            
            # UUID 변환 로직: 문자열이면 UUID로 변환, UUID 객체면 그대로 사용, None이면 None
            parsed_user_id = UUID(user_id) if isinstance(user_id, str) else user_id
            
            # agent_llm로 호출
            response:AIMessage = await self.agent_llm.ainvoke_with_fallback(
                input=combined_prompt, 
                user_id=parsed_user_id, 
                project_type=ProjectType.STOCKEASY, 
                db=self.db
            )

            if not response or not response.content:
                raise Exception("LLM이 빈 응답을 반환했습니다.")

            return response.content
            
        except Exception as e:
            error_msg = f"메시지 요약 중 오류 발생: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise Exception(error_msg) from e
        
    def MakeSummaryPrompt(self, classification: Dict[str, Any]) -> str:
        """질문 분류 결과에 따라 적절한 요약 프롬프트를 생성합니다.
        
        Args:
            classification (QuestionClassification): 질문 분류 결과
            
        Returns:
            str: 생성된 요약 프롬프트
        """
        # 기본 프롬프트 템플릿
        base_prompt = TELEGRAM_SUMMARY_PROMPT
        
        # 1. 주요 의도(primary_intent)에 따른 프롬프트 추가
        primary_intent = classification.get("primary_intent", "기타")
        intent_prompt = ""
        
        if primary_intent == "종목기본정보":
            intent_prompt = """
종목 기본 정보에 관한 질문입니다. 다음 사항에 중점을 두어 요약하세요:
- 해당 종목의 사업 영역, 주요 제품/서비스
- 시가총액, 주가 등 기본 주식 정보
- 주요 경영진 및 지배구조 관련 정보
- 시장 내 위치 및 경쟁사 대비 특징
"""
        elif primary_intent == "성과전망":
            intent_prompt = """
해당 종목의 성과 및 전망에 관한 질문입니다. 다음 사항에 중점을 두어 요약하세요:
- 실적 발표 및 향후 전망에 관한 내용
- 애널리스트들의 목표가 및 투자의견
- 매출, 영업이익, 순이익 등 주요 재무 지표 예측
- 미래 성장 동력 및 위험 요소
"""
        elif primary_intent == "재무분석":
            intent_prompt = """
재무 분석에 관한 질문입니다. 다음 사항에 중점을 두어 요약하세요:
- 주요 재무제표 수치 및 비율 분석
- 동종 업계 대비 재무 건전성
- 수익성, 성장성, 안정성 관련 지표
- 실적 변화의 주요 요인
"""
        elif primary_intent == "산업동향":
            intent_prompt = """
산업 동향에 관한 질문입니다. 다음 사항에 중점을 두어 요약하세요:
- 해당 산업의 최근 트렌드 및 변화
- 정부 정책 및 규제 환경 영향
- 산업 내 주요 경쟁사 동향
- 기술 변화 및 혁신 정보
"""
        
        # 2. 질문 복잡도(complexity)에 따른 요약 깊이 조정
        complexity = classification.get("complexity", "중간")
        complexity_prompt = ""
        
        if complexity == "단순":
            complexity_prompt = """
간결하고 직접적인 요약을 제공하세요. 핵심 정보 중심으로 1-3문장 정도로 요약하는 것이 적절합니다.
"""
        elif complexity == "중간":
            complexity_prompt = """
균형 잡힌 요약을 제공하세요. 중요 정보와 세부 사항을 적절히 포함하며, 5-7문장 정도의 요약이 적절합니다.
"""
        elif complexity == "복합":
            complexity_prompt = """
상세한 요약을 제공하세요. 다양한 측면의 정보를 포함하고, 상반된 견해가 있다면 함께 제시하세요. 
여러 단락으로 구성된 포괄적인 요약이 적절합니다.
"""
        elif complexity == "전문가급":
            complexity_prompt = """
심층적이고 전문적인 분석 요약을 제공하세요. 다음을 포함해야 합니다:
- 다양한 시각과 의견의 종합
- 정보 간 상호 관계 및 인과관계 분석
- 장기적/단기적 영향 구분
- 시장 전문가의 다양한 관점 비교
- 데이터 기반 근거와 전망 제시
"""
        
        # 3. 기대하는 답변 유형(expected_answer_type)에 따른 조정
        answer_type = classification.get("expected_answer_type", "사실형")
        answer_type_prompt = ""
        
        if answer_type == "사실형":
            answer_type_prompt = """
사실에 기반한 객관적인 정보 중심으로 요약하세요. 주관적인 의견이나 추측은 최소화하고, 
실제 발생한 사건, 공식 발표, 검증된 데이터를 중심으로 응답하세요.
"""
        elif answer_type == "추론형":
            answer_type_prompt = """
주어진 정보를 바탕으로 논리적 추론을 제공하세요. 근거가 되는 사실을 먼저 제시한 후, 
그로부터 도출할 수 있는 합리적인 추론을 전개하세요.
"""
        elif answer_type == "비교형":
            answer_type_prompt = """
비교 분석을 중심으로 요약하세요. 다양한 관점, 의견, 데이터 간의 차이점과 공통점을 
체계적으로 대조하여 제시하세요.
"""
        elif answer_type == "예측형":
            answer_type_prompt = """
미래 전망에 초점을 맞춰 요약하세요. 현재 정보를 바탕으로 향후 발생 가능한 시나리오를 
제시하되, 각 전망의 확실성 정도를 함께 표현하세요.
"""
        elif answer_type == "설명형":
            answer_type_prompt = """
개념과 관계를 명확히 설명하는 요약을 제공하세요. 복잡한 정보를 체계적으로 정리하고, 
인과관계와 상호작용을 이해하기 쉽게 설명하세요.
"""
        
        # 최종 프롬프트 구성
        additional_prompt = f"""
{intent_prompt}

{complexity_prompt}

{answer_type_prompt}

종합적으로, 이 메시지들을 분석하여 질문에 대한 명확하고 유용한 답변을 제공하세요.
답변 시에는 메시지의 신뢰도, 최신성, 관련성을 고려하여 가중치를 부여하세요.
"""
        
        # 기본 프롬프트에 추가 지시사항 결합
        final_prompt = base_prompt + additional_prompt
        
        return final_prompt
    
    def _add_error(self, state: Dict[str, Any], error_message: str) -> None:
        """
        상태 객체에 오류 정보를 추가합니다.
        
        Args:
            state: 상태 객체
            error_message: 오류 메시지
        """
        state["errors"] = state.get("errors", [])
        state["errors"].append({
            "agent": "telegram_retriever",
            "error": error_message,
            "type": "processing_error",
            "timestamp": datetime.now(),
            "context": {"query": state.get("query", "")}
        })
    
    def _calculate_dynamic_threshold(self, classification: Dict[str, Any]) -> float:
        """
        질문 복잡도에 따른 동적 유사도 임계값 계산
        
        Args:
            classification: 분류 결과
            
        Returns:
            유사도 임계값
        """
        complexity = classification.get("complexity", "중간")
        
        # 복잡도에 따른 임계값 설정
        if complexity == "단순":
            return 0.5  # 단순 질문일수록 높은 임계값 (정확한 결과 필요)
        elif complexity == "중간":
            return 0.35
        elif complexity == "복합":
            return 0.25
        else:  # "전문가급"
            return 0.21  # 복잡한 질문일수록 낮은 임계값 (폭넓은 결과 수집)
    
    def _get_message_count(self, classification: Dict[str, Any]) -> int:
        """
        복잡도에 따른 검색 메시지 수 결정
        
        Args:
            classification: 분류 결과
            
        Returns:
            검색할 메시지 수
        """
        complexity = classification.get("complexity", "중간")
        
        if complexity == "단순":
            return 5
        elif complexity == "중간":
            return 10
        elif complexity == "복합":
            return 15
        else:  # "전문가급"
            return 20
    
    def _calculate_message_importance(self, message: str) -> float:
        """
        메시지의 중요도를 계산합니다.
        
        Args:
            message: 중요도를 계산할 메시지
            
        Returns:
            0~1 사이의 중요도 점수
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
    
    def _is_duplicate(self, message: str, seen_messages: Set[str]) -> bool:
        """
        메시지가 이미 처리된 메시지 중 중복인지 확인합니다.
        
        Args:
            message: 검사할 메시지
            seen_messages: 이미 처리된 메시지 해시 집합
            
        Returns:
            중복 여부
        """
        # 메시지 해시 생성
        message_hash = self._get_message_hash(message)
        
        # 중복 확인
        if message_hash in seen_messages:
            return True
            
        return False
    
    def _calculate_time_weight(self, created_at: datetime) -> float:
        """
        메시지 생성 시간 기반의 가중치를 계산합니다.
        
        Args:
            created_at: 메시지 생성 시간 (datetime 객체)
            
        Returns:
            시간 기반 가중치 (0.4 ~ 1.0)
        """
        try:
            seoul_tz = timezone(timedelta(hours=9), 'Asia/Seoul')
        
            # naive datetime인 경우 서버 로컬 시간(Asia/Seoul)으로 간주
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=ZoneInfo("Asia/Seoul"))
                
            # now도 timezone 정보를 포함하도록 수정
            now = datetime.now(seoul_tz)
            delta = now - created_at
            
            # 시간 차이에 따른 가중치 설정
            if delta.days < 1:  # 24시간 이내
                return 1.0
            elif delta.days < 7:  # 1주일 이내
                return 0.9
            elif delta.days < 14:  # 2주일 이내
                return 0.8
            elif delta.days < 30:  # 1개월 이내
                return 0.6
            else:  # 1개월 이상
                return 0.4
                
        except Exception as e:
            logger.warning(f"시간 가중치 계산 오류: {str(e)}")
            return 0.5  # 오류 시 중간값 반환
    
    def _make_search_query(self, query: str, stock_code: Optional[str], 
                          stock_name: Optional[str], classification: Dict[str, Any],
                          sector: Optional[str] = None) -> str:
        """
        검색 쿼리를 구성합니다.
        
        Args:
            query: 원본 사용자 쿼리
            stock_code: 종목 코드
            stock_name: 종목 이름
            classification: 질문 분류 정보
            sector: 산업 섹터 정보
            
        Returns:
            검색을 위한 향상된 쿼리 문자열
        """
        # 분류 정보에서 관련 데이터 추출
        primary_intent = classification.get("primary_intent", "")
        secondary_intent = classification.get("secondary_intent", "")
        time_frame = classification.get("time_frame", "")
        aspect = classification.get("aspect", "")
        
        # 중요 키워드 추출 (검색 쿼리 강화에 사용)
        important_keywords = []
        
        # 주요 의도를 기반으로 키워드 추가
        if primary_intent == "현재가치":
            important_keywords.extend(["현재가", "주가", "시세", "시가총액"])
        elif primary_intent == "성과전망":
            important_keywords.extend(["전망", "예측", "기대", "목표가"])
        elif primary_intent == "투자의견":
            important_keywords.extend(["투자의견", "매수", "매도", "보유", "추천"])
        elif primary_intent == "재무정보":
            important_keywords.extend(["실적", "매출", "영업이익", "순이익", "재무"])
        elif primary_intent == "기업정보":
            important_keywords.extend(["기업", "사업", "제품", "서비스"])
        
        # 시간 프레임을 기반으로 키워드 추가
        if time_frame == "과거":
            important_keywords.extend(["지난", "이전", "과거"])
        elif time_frame == "현재":
            important_keywords.extend(["현재", "지금", "오늘"])
        elif time_frame == "미래":
            important_keywords.extend(["향후", "전망", "예상", "미래"])
        
        # 종목 정보가 있는 경우 쿼리에 추가
        query_parts = [query]
        
        if stock_name:
            query_parts.append(stock_name)
        
        if stock_code:
            query_parts.append(stock_code)
            
        if sector:
            query_parts.append(sector)
        
        # 분류에서 중요 정보가 있을 경우 쿼리에 포함 (상위 3개만)
        enhanced_query = " ".join(query_parts)
        
        return enhanced_query
    
    @async_retry(retries=3, delay=1.0, exceptions=(Exception,))
    async def _search_messages(self, search_query: str, k: int, threshold: float, user_id: Optional[Union[str, UUID]] = None) -> List[RetrievedTelegramMessage]:
        """
        텔레그램 메시지 검색을 수행합니다.
        
        Args:
            search_query: 검색 쿼리
            k: 검색할 메시지 수
            threshold: 유사도 임계값
            user_id: 사용자 ID (문자열 또는 UUID 객체)
            
        Returns:
            검색된 텔레그램 메시지 목록
        """
        try:
            logger.info(f"Generated search query: {search_query}")
            
            # 임베딩 모델을 사용하여 쿼리 벡터 생성
            # embeddings = TelegramEmbeddingModel(model_type="remote")
            
            # # 텔레그램 검색 인덱스에서 검색 수행
            # retriever = TelegramRetriever(embeddings)
            # retriever.filter_by_threshold(threshold)
            
            # 초기 검색은 더 많은 결과를 가져온 후 필터링
            initial_k = min(k * 3, 30)  # 적어도 원하는 k의 3배, 최대 30개까지
            
            # Pinecone 벡터 스토어 연결
            vs_manager = VectorStoreManager(
                embedding_model_type=self.embedding_service.get_model_type(),
                project_name="stockeasy",
                namespace=settings.PINECONE_NAMESPACE_STOCKEASY_TELEGRAM
            )

            # UUID 변환 로직: 문자열이면 UUID로 변환, UUID 객체면 그대로 사용, None이면 None
            parsed_user_id = UUID(user_id) if isinstance(user_id, str) else user_id

            # 시맨틱 검색 설정
            semantic_retriever = SemanticRetriever(
                config=SemanticRetrieverConfig(min_score=threshold,
                                               user_id=parsed_user_id,
                                               project_type=ProjectType.STOCKEASY
                                               ),
                vs_manager=vs_manager
            )
                    
            # 검색 수행
            result: RetrievalResult = await semantic_retriever.retrieve(
                query=search_query, 
                top_k=initial_k,#k * 2,
            )
            
            if len(result.documents) == 0:
                logger.warning(f"No telegram messages found for query: {search_query}")
                return []
                
            # 결과가 너무 적은 경우 임계값 낮춰서 다시 시도
            # if len(result) < 3 and threshold > 0.3:
            #     logger.info(f"Few results ({len(result)}), lowering threshold to 0.3")
            #     retriever.filter_by_threshold(0.3)
            #     result = await retriever.get_relevant_messages(search_query, k=initial_k)
                
            # if not result:
            #     logger.warning("Still no telegram messages found after lowering threshold")
            #     return []
                
            logger.info(f"Found {len(result.documents)} telegram messages")
            
            # 중복 메시지 필터링 및 점수 계산
            processed_messages = []
            seen_messages = set()  # 중복 확인용
            
            for doc in result.documents:
                doc_metadata = doc.metadata
                content = doc.page_content# doc_metadata.get("text", "")
                
                # 내용이 없거나 너무 짧은 메시지 제외
                if not content or len(content) < 20:
                    continue
                
                normalized_content = re.sub(r'\s+', ' ', content).strip().lower()
                # 중복 메시지 확인
                if self._is_duplicate(normalized_content, seen_messages):
                    logger.info(f"중복 메시지 제외: {normalized_content[:50]}")
                    continue

                
                    
                seen_messages.add(self._get_message_hash(normalized_content))
                
                # 메시지 중요도 계산
                importance_score = self._calculate_message_importance(content)
                
                # 시간 기반 가중치 계산
                message_created_at = datetime.fromisoformat(doc.metadata["message_created_at"])
                time_weight = self._calculate_time_weight(message_created_at)
                
                # 최종 점수 = 유사도 * 중요도 * 시간 가중치
                #final_score = doc.score * importance_score * time_weight
                final_score = (doc.score * 0.5) + (importance_score * 0.3) + (time_weight * 0.2)
                # 메시지 데이터 구성
                message:RetrievedTelegramMessage = {
                    "content": content,
                    #"channel_name": doc_metadata.get("channel_title", "알 수 없음"), # 그러나 숨겨야함
                    "message_created_at": message_created_at,
                    "final_score": final_score,
                    "metadata": doc_metadata
                }
                
                processed_messages.append(message)
            
            # 최종 점수 기준으로 정렬하고 상위 k개 선택
            processed_messages.sort(key=lambda x: x["final_score"], reverse=True)
            logger.info(f"최종 점수 기준으로 정렬된 메시지 수: {len(processed_messages)}")
            result_messages = processed_messages[:k]
            
            # 점수 분포 정규화
            if result_messages:
                max_score = max(msg["final_score"] for msg in result_messages)
                min_score = min(msg["final_score"] for msg in result_messages)
                score_range = max_score - min_score if max_score > min_score else 1.0
                
                for msg in result_messages:
                    msg["normalized_score"] = (msg["final_score"] - min_score) / score_range
            
            return result_messages
            
        except Exception as e:
            logger.exception(f"Error searching telegram messages: {str(e)}")
            raise 

    def _get_message_hash(self, content: str) -> str:
        """
        메시지 내용의 해시값을 생성합니다.
        
        Args:
            content: 메시지 내용
            
        Returns:
            메시지 해시값
        """
        # 메시지 전처리 (공백 제거, 소문자 변환)
        normalized_content = re.sub(r'\s+', ' ', content).strip().lower()
        
        # 너무 긴 메시지는 앞부분만 사용
        if len(normalized_content) > 200:
            normalized_content = normalized_content[:200]
            
        # SHA-256 해시 생성하여 반환
        return hashlib.sha256(normalized_content.encode('utf-8')).hexdigest() 