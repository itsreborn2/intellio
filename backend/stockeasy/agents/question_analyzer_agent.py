"""
질문 분석기 에이전트 모듈

이 모듈은 사용자 질문을 분석하여 의도, 엔티티, 키워드 등의
중요한 정보를 추출하는 QuestionAnalyzerAgent 클래스를 구현합니다.
"""

import asyncio
import json
import os
import re
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional
from typing import Optional as PydanticOptional

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate
from loguru import logger
from pydantic import BaseModel, Field, validator
from sqlalchemy.ext.asyncio import AsyncSession

from common.core.config import settings
from common.core.redis import async_redis_client  # AsyncRedisClient 클래스 대신 싱글톤 인스턴스를 가져옵니다.
from common.models.token_usage import ProjectType
from common.services.agent_llm import get_agent_llm

# from langchain_tavily import TavilySearch
from common.services.tavily import TavilyService
from common.utils.util import extract_json_from_text, remove_json_block
from stockeasy.agents.base import BaseAgent
from stockeasy.models.agent_io import QuestionAnalysisResult
from stockeasy.prompts.question_analyzer_prompts import PROMPT_DYNAMIC_GENERAL_TOC, PROMPT_DYNAMIC_TOC, SYSTEM_PROMPT, format_question_analyzer_prompt
from stockeasy.services.financial.stock_info_service import StockInfoService


class Entities(BaseModel):
    """추출된 엔티티 정보"""

    stock_name: PydanticOptional[str] = Field(None, description="종목명 또는 null")
    stock_code: PydanticOptional[str] = Field(None, description="종목코드 또는 null")
    sector: PydanticOptional[str] = Field(None, description="종목이 속한 산업/섹터 또는 null")
    subgroup: PydanticOptional[List[str]] = Field(None, description="종목이 속한 subgroup 또는 null")
    time_range: PydanticOptional[str] = Field(None, description="시간범위 또는 null")
    financial_metric: PydanticOptional[str] = Field(None, description="재무지표 또는 null")
    competitor: PydanticOptional[str] = Field(None, description="경쟁사 또는 null")
    product: PydanticOptional[str] = Field(None, description="제품/서비스 또는 null")

    @validator("subgroup", pre=True)
    def validate_subgroup(cls, v):
        """subgroup 필드의 안전한 처리를 위한 validator"""
        if v is None or v == "null" or v == "":
            return None
        if isinstance(v, str):
            # 문자열인 경우 JSON 파싱 시도
            try:
                import json

                parsed = json.loads(v)
                if isinstance(parsed, list):
                    return parsed
            except (json.JSONDecodeError, ValueError):
                pass
            # JSON 파싱 실패 시 빈 리스트 반환
            return None
        if isinstance(v, list):
            return v
        return None


class Classification(BaseModel):
    """질문 분류 정보"""

    primary_intent: Literal["종목기본정보", "성과전망", "재무분석", "산업동향", "기타"] = Field(
        ...,
        description=(
            "사용자 질문의 핵심 의도입니다. 반드시 다음 중 하나를 선택해야 합니다: "
            "'종목기본정보'(회사 개요, 현재 주가 등 단순 정보), "
            "'성과전망'(미래 실적 예측, 목표 주가 등 예측/전망), "
            "'재무분석'(재무제표 수치, 비율 분석 등 상세 분석), "
            "'산업동향'(관련 산업/시장 분석, 경쟁사 비교 등), "
            "'기타'(위 범주에 속하지 않거나 분류하기 어려운 경우). "
            "질문의 의도가 모호하다면 가장 적절하다고 판단되는 하나를 선택하거나 '기타'로 분류하세요."
        ),
    )
    complexity: Literal["단순", "중간", "복합", "전문가급"] = Field(
        ...,
        description=(
            "질문의 복잡도 수준입니다. 반드시 다음 중 하나를 선택해야 합니다: "
            "'단순'(단일 정보 요청, 예: '현재 주가 얼마야?'), "
            "'중간'(여러 정보 결합 또는 간단한 분석 요구, 예: '최근 1년 주가 추이와 주요 이슈 알려줘'), "
            "'복합'(다각적 분석, 비교, 깊은 이해 요구, 예: '경쟁사 대비 재무 건전성과 성장 전망 분석해줘'), "
            "'전문가급'(매우 심층적인 분석, 특정 모델링/가정 요구, 예: 'DCF 모델 기반으로 향후 5년 예상 주가 산출해줘'). "
            "질문의 요구사항과 분석 깊이를 고려하여 가장 적합한 수준을 선택하세요."
        ),
    )
    expected_answer_type: Literal["사실형", "추론형", "비교형", "예측형", "설명형", "종합형"] = Field(
        ...,
        description=(
            "사용자가 기대하는 답변의 유형입니다. 반드시 다음 중 하나를 선택해야 합니다: "
            "'사실형'(객관적인 데이터나 정보 전달, 예: '작년 매출액은?'), "
            "'추론형'(주어진 정보 기반의 논리적 추론/해석, 예: '최근 실적 발표가 주가에 미칠 영향은?'), "
            "'비교형'(둘 이상의 대상을 비교 분석, 예: 'A사와 B사의 수익성 비교'), "
            "'예측형'(미래 상태나 결과 예측, 예: '다음 분기 실적 전망은?'), "
            "'설명형'(개념, 원인, 과정 등에 대한 설명, 예: 'PER이 무엇인가요?'), "
            "'종합형'(여러 유형의 정보를 종합하여 제공). "
            "질문의 핵심 요구사항에 맞춰 가장 적합한 답변 유형을 선택하세요."
        ),
    )


class DataRequirements(BaseModel):
    """데이터 요구사항"""

    telegram_needed: bool = Field(..., description="텔레그램 데이터 필요 여부")
    reports_needed: bool = Field(..., description="리포트 데이터 필요 여부")
    financial_statements_needed: bool = Field(..., description="재무제표 데이터 필요 여부")
    industry_data_needed: bool = Field(..., description="산업 데이터 필요 여부")
    confidential_data_needed: bool = Field(..., description="비공개 자료 필요 여부")
    revenue_data_needed: bool = Field(False, description="매출 및 수주 현황 데이터 필요 여부")
    web_search_needed: bool = Field(False, description="웹 검색 데이터 필요 여부,기본False")
    technical_analysis_needed: bool = Field(False, description="기술적 분석 데이터 필요 여부")


class QuestionAnalysis(BaseModel):
    """질문 분석 결과"""

    entities: Entities = Field(..., description="추출된 엔티티 정보")
    classification: Classification = Field(..., description="질문 분류 정보")
    data_requirements: DataRequirements = Field(..., description="필요한 데이터 소스 정보")
    keywords: List[str] = Field(..., description="중요 키워드 목록")
    detail_level: Literal["간략", "보통", "상세"] = Field(..., description="요구되는 상세도")


class ConversationContextAnalysis(BaseModel):
    """대화 컨텍스트 분석 결과"""

    requires_context: bool = Field(..., description="이전 대화 컨텍스트가 필요한지 여부")
    is_followup_question: bool = Field(..., description="이전 질문에 대한 후속 질문인지 여부")
    referenced_context: PydanticOptional[str] = Field(None, description="참조하는 대화 컨텍스트 (있는 경우)")
    relation_to_previous: Literal["독립적", "직접참조", "간접참조", "확장", "수정"] = Field(..., description="이전 대화와의 관계")
    is_conversation_closing: bool = Field(False, description="대화 마무리를 뜻하는 인사말인지 여부")
    closing_type: PydanticOptional[Literal["긍정적", "중립적", "부정적"]] = Field(None, description="마무리 인사 유형")
    closing_response: PydanticOptional[str] = Field(None, description="마무리 인사에 대한 응답 메시지")
    reasoning: str = Field(..., description="판단에 대한 이유 설명")
    is_different_stock: bool = Field(False, description="이전 질문과 다른 종목에 관한 질문인지 여부")
    previous_stock_name: PydanticOptional[str] = Field(None, description="이전 질문에서 언급된 종목명")
    previous_stock_code: PydanticOptional[str] = Field(None, description="이전 질문에서 언급된 종목코드")
    stock_relation: PydanticOptional[Literal["동일종목", "종목비교", "다른종목", "알수없음"]] = Field(None, description="이전 종목과의 관계")


# 새로운 모델 클래스 추가
class SubsectionModel(BaseModel):
    """
    하위 섹션을 위한 구조화된 출력 포맷
    """

    subsection_id: str = Field(description="하위 섹션 ID (예: section_2_1)")
    title: str = Field(description="하위 섹션 제목 (예: 2.1 하위 섹션 제목)")
    description: Optional[str] = Field(default=None, description="하위 섹션에서 다룰 내용의 간략한 설명")


class SectionModel(BaseModel):
    """
    섹션을 위한 구조화된 출력 포맷
    """

    section_id: str = Field(description="섹션 ID (예: section_1)")
    title: str = Field(description="섹션 제목 (예: 1. 핵심 요약)")
    description: Optional[str] = Field(default=None, description="섹션에서 다룰 내용의 간략한 설명")
    subsections: List[SubsectionModel] = Field(default_factory=list, description="하위 섹션 목록")


class DynamicTocOutput(BaseModel):
    """
    동적 목차 생성 결과를 위한 구조화된 출력 포맷
    """

    title: str = Field(description="보고서 제목 (질문과 기업명을 반영)")
    sections: List[Dict[str, Any]] = Field(description="보고서 섹션 정보")


class QuestionAnalyzerAgent(BaseAgent):
    """
    사용자 질문을 분석하는 에이전트

    이 에이전트는 사용자의 질문을 분석하여 다음을 수행합니다:
    1. 종목코드/종목명 등 엔티티 추출
    2. 질문의 의도 분류
    3. 필요한 데이터 유형 식별
    4. 키워드 추출
    """

    def __init__(self, name: Optional[str] = None, db: Optional[AsyncSession] = None):
        """
        질문 분석 에이전트 초기화

        Args:
            name: 에이전트 이름 (지정하지 않으면 클래스명 사용)
            db: 데이터베이스 세션 객체 (선택적)
        """
        super().__init__(name, db)
        self.agent_llm = get_agent_llm("question_analyzer_agent")
        self.agent_llm_lite = get_agent_llm("gemini-2.5-flash-lite")  # get_agent_llm("gemini-2.0-flash-lite")
        logger.info(f"QuestionAnalyzerAgent initialized with provider: {self.agent_llm.get_provider()}, model: {self.agent_llm.get_model_name()}")
        self.prompt_template = SYSTEM_PROMPT

        # self.tavily_search = TavilySearch(api_key=settings.TAVILY_API_KEY)
        self.tavily_service = TavilyService()
        self.redis_client = async_redis_client  # 직접 인스턴스를 생성하는 대신 싱글톤 인스턴스를 사용합니다.

        # 기술적 분석 관련 키워드 정의
        self.technical_analysis_keywords = {
            # 차트 패턴 키워드
            "chart_patterns": [
                "차트",
                "패턴",
                "지지선",
                "저항선",
                "추세선",
                "삼각형패턴",
                "머리어깨",
                "쌍바닥",
                "쌍천정",
                "역삼각형",
                "깃발패턴",
                "페넌트",
                "웨지",
                "채널",
                "돌파",
                "이탈",
                "반전",
                "지지",
                "저항",
                "추세",
                "상승추세",
                "하락추세",
                "횡보",
            ],
            # 기술적 지표 키워드
            "technical_indicators": [
                "RS",
                "상대강도",
                "MACD",
                "볼린저밴드",
                "이동평균선",
                "스토캐스틱",
                "이동평균",
                "단순이동평균",
                "지수이동평균",
                "SMA",
                "EMA",
                "가격이동평균",
                "거래량",
                "거래량지표",
                "OBV",
                "출래량균형지표",
                "모멘텀",
                "CCI",
                "윌리엄스R",
                "피보나치",
                "일목균형표",
                "엔벨로프",
                "ADX",
                "방향성지수",
            ],
            # 매매 신호 키워드
            "trading_signals": [
                "매수신호",
                "매도신호",
                "골든크로스",
                "데드크로스",
                "과매수",
                "과매도",
                "매수타이밍",
                "매도타이밍",
                "진입신호",
                "청산신호",
                "신호",
                "크로스",
                "상향돌파",
                "하향돌파",
                "신호강도",
                "매매포지션",
            ],
            # 가격 움직임 키워드
            "price_movements": [
                "가격움직임",
                "주가흐름",
                "상승세",
                "하락세",
                "횡보장세",
                "급등",
                "급락",
                "조정",
                "반등",
                "반락",
                "변동성",
                "고점",
                "저점",
                "신고가",
                "신저가",
                "갭상승",
                "갭하락",
                "가격대",
                "구간",
                "레벨",
            ],
            # 시장 분석 키워드
            "market_analysis": ["기술적분석", "차트분석", "테크니컬분석", "기술분석", "차트해석", "기술적관점", "차트상", "기술적요인", "차트패턴분석", "기술적신호"],
        }

    async def process(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        사용자 질문을 분석하여 중요 정보를 추출하고 상태를 업데이트합니다.

        Args:
            state: 현재 상태 정보를 포함하는 딕셔너리

        Returns:
            업데이트된 상태 딕셔너리
        """
        try:
            # 성능 측정 시작
            start_time = datetime.now()
            logger.info("QuestionAnalyzerAgent starting processing")

            # 현재 사용자 쿼리 추출
            query = state.get("query", "")
            stock_code = state.get("stock_code", "")
            stock_name = state.get("stock_name", "")
            logger.info(f"query[{stock_name},{stock_code}] : {query}")

            if not query:
                logger.warning("Empty query provided to QuestionAnalyzerAgent")
                self._add_error(state, "질문이 비어 있습니다.")
                return state

            # 일반 질문 모드일 때 처리
            if stock_code == "general":
                logger.info("일반 질문 모드: 종목 독립적 분석 수행")
                return await self._handle_general_question(state, query, start_time)

            # state["agent_results"] = state.get("agent_results", {})
            # user_id 추출
            user_context = state.get("user_context", {})
            user_id = user_context.get("user_id", None)
            user_email = user_context.get("user_email", None)

            # 대화 기록 확인
            conversation_history = state.get("conversation_history", [])
            logger.info(f"대화 기록 타입: {type(conversation_history)}, 길이: {len(conversation_history) if isinstance(conversation_history, list) else '알 수 없음'}")

            has_valid_history = False  # 강제 비활성화

            if has_valid_history:
                logger.info(f"대화 기록 있음: {len(conversation_history)}개 메시지")
                context_analysis = await self.analyze_conversation_context(query, conversation_history, stock_name, stock_code, user_id)
                context_analysis_result = context_analysis.model_dump()  # dict

                # 분석 결과 상태에 저장
                state["context_analysis"] = context_analysis_result

                # 대화 마무리 인사인지 확인
                if context_analysis.is_conversation_closing:
                    logger.info(f"대화 마무리 인사로 감지: 유형={context_analysis.closing_type}")

                    # 상태 업데이트
                    state["agent_results"]["question_analysis"] = context_analysis_result
                    state["summary"] = context_analysis.closing_response
                    state["answer"] = state["summary"]

                    # 메트릭 기록 및 처리 상태 업데이트
                    end_time = datetime.now()
                    duration = (end_time - start_time).total_seconds()

                    state["metrics"] = state.get("metrics", {})
                    state["metrics"]["question_analyzer"] = {
                        "start_time": start_time,
                        "end_time": end_time,
                        "duration": duration,
                        "status": "completed",
                        "error": None,
                        "model_name": self.agent_llm.get_model_name(),
                    }

                    state["processing_status"] = state.get("processing_status", {})
                    state["processing_status"]["question_analyzer"] = "completed"

                    logger.info(f"대화 마무리 감지, QuestionAnalyzerAgent 빠른 처리 완료: {duration:.2f}초 소요")
                    logger.info(f"마무리 유형: {context_analysis.closing_type}, 응답: {context_analysis.closing_response}")
                    return state

                if context_analysis.is_different_stock and context_analysis.stock_relation == "다른종목":
                    logger.info("완전히 다른종목 질문")
                    # 상태 업데이트
                    state["agent_results"]["question_analysis"] = context_analysis_result
                    state["summary"] = "현재 종목과 관련이 없는 질문입니다.\n다른 종목에 관한 질문은 새 채팅에서 해주세요"
                    state["answer"] = state["summary"]
                    # 메트릭 기록 및 처리 상태 업데이트
                    end_time = datetime.now()
                    duration = (end_time - start_time).total_seconds()

                    state["metrics"] = state.get("metrics", {})
                    state["metrics"]["question_analyzer"] = {
                        "start_time": start_time,
                        "end_time": end_time,
                        "duration": duration,
                        "status": "completed",
                        "error": None,
                        "model_name": self.agent_llm.get_model_name(),
                    }

                    state["processing_status"] = state.get("processing_status", {})
                    state["processing_status"]["question_analyzer"] = "completed"

                    logger.info(f"대화 마무리 감지, QuestionAnalyzerAgent 빠른 처리 완료: {duration:.2f}초 소요")
                    logger.info(f"마무리 유형: {context_analysis.closing_type}, 응답: {context_analysis.closing_response}")
                    return state

                # 후속 질문인 경우 빠르게 처리하고 리턴
                if context_analysis.requires_context:
                    logger.info("후속 질문으로 감지되어 상세 분석 생략하고 빠르게 리턴합니다.")

                    state["agent_results"]["question_analysis"] = context_analysis_result

                    # 메트릭 기록 및 처리 상태 업데이트
                    end_time = datetime.now()
                    duration = (end_time - start_time).total_seconds()

                    state["metrics"] = state.get("metrics", {})
                    state["metrics"]["question_analyzer"] = {
                        "start_time": start_time,
                        "end_time": end_time,
                        "duration": duration,
                        "status": "completed",
                        "error": None,
                        "model_name": self.agent_llm.get_model_name(),
                    }

                    state["processing_status"] = state.get("processing_status", {})
                    state["processing_status"]["question_analyzer"] = "completed"

                    logger.info(f"QuestionAnalyzerAgent 빠른 처리 완료: {duration:.2f}초 소요")
                    return state

                # 후속 처리에 필요한 정보 기록
                if context_analysis.requires_context:
                    logger.info(f"이전 대화 컨텍스트 참조 필요: {context_analysis.relation_to_previous}")
                    if context_analysis.referenced_context:
                        logger.info(f"참조 컨텍스트: {context_analysis.referenced_context}")
            else:
                logger.info("대화 기록 없음, 컨텍스트 분석 건너뜀")
                state["context_analysis"] = {
                    "requires_context": False,
                    "is_followup_question": False,
                    "relation_to_previous": "독립적",
                    "is_conversation_closing": False,
                    "closing_type": None,
                    "closing_response": None,
                    "is_different_stock": False,
                    "previous_stock_name": None,
                    "previous_stock_code": None,
                    "stock_relation": "알수없음",
                    "reasoning": "대화 기록이 없습니다.",
                }

            logger.info(f"QuestionAnalyzerAgent analyzing query: {query}")

            # 커스텀 프롬프트 템플릿 확인
            # 1. 상태에서 커스텀 프롬프트 템플릿 확인
            custom_prompt_from_state = state.get("custom_prompt_template")
            # 2. 속성에서 커스텀 프롬프트 템플릿 확인
            custom_prompt_from_attr = getattr(self, "prompt_template_test", None)

            # 커스텀 프롬프트 사용 우선순위: 상태 > 속성 > 기본값
            system_prompt = None
            if custom_prompt_from_state:
                system_prompt = custom_prompt_from_state
                logger.info(f"QuestionAnalyzerAgent using custom prompt from state : {custom_prompt_from_state}")
            elif custom_prompt_from_attr:
                system_prompt = custom_prompt_from_attr
                logger.info("QuestionAnalyzerAgent using custom prompt from attribute")

            import asyncio

            # 1. 사용자 질문 의도 분석 및 2. 최근 이슈 검색/목차 생성을 병렬로 실행
            logger.info("사용자 질문 분석과 최근 이슈 검색을 병렬로 실행")

            # 1. 사용자 질문 의도 분석 비동기 함수
            async def analyze_question_intent():
                # 프롬프트 준비
                prompt = format_question_analyzer_prompt(query=query, stock_name=stock_name, stock_code=stock_code, system_prompt=system_prompt)

                try:
                    # LLM 호출로 분석 수행
                    # agent_temp = get_agent_llm("gemini-2.0-flash")

                    # raw_response = await agent_temp.with_structured_output(QuestionAnalysis).ainvoke(prompt, user_id=user_id, project_type=ProjectType.STOCKEASY, db=self.db)
                    raw_response = await self.agent_llm_lite.with_structured_output(QuestionAnalysis).ainvoke(
                        prompt, user_id=user_id, project_type=ProjectType.STOCKEASY, db=self.db
                    )

                    response: QuestionAnalysis

                    if isinstance(raw_response, AIMessage):
                        logger.info("AIMessage 형태로 응답 받음, JSON 파싱 시도")
                        content = raw_response.content

                        # ```json ``` 제거
                        if isinstance(content, str):
                            # 정규 표현식을 사용하여 ```json ... ``` 또는 ``` ... ``` 패턴을 찾고 내부 JSON만 추출
                            match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", content, re.DOTALL)
                            if match:
                                json_str = match.group(1)
                            else:
                                # 단순 ``` 제거 시도 (패턴이 안맞을 경우 대비)
                                json_str = content.strip()
                                if json_str.startswith("```json"):
                                    json_str = json_str[7:]
                                if json_str.startswith("```"):
                                    json_str = json_str[3:]
                                if json_str.endswith("```"):
                                    json_str = json_str[:-3]
                                json_str = json_str.strip()

                            try:
                                parsed_data = json.loads(json_str)
                                response = QuestionAnalysis(**parsed_data)
                                logger.info(f"AIMessage JSON 파싱 성공: {response}")
                            except json.JSONDecodeError as json_err:
                                logger.error(f"AIMessage JSON 파싱 실패: {json_err}. Fallback 로직으로 진행합니다.")
                                raise Exception("AIMessage JSON parsing failed")  # Fallback 트리거
                        else:
                            logger.error("AIMessage content가 문자열이 아님. Fallback 로직으로 진행합니다.")
                            raise Exception("AIMessage content is not a string")  # Fallback 트리거
                    elif isinstance(raw_response, QuestionAnalysis):
                        response = raw_response
                    else:
                        logger.error(f"예상치 못한 응답 타입: {type(raw_response)}. Fallback 로직으로 진행합니다.")
                        raise Exception(f"Unexpected response type: {type(raw_response)}")

                    # response가 QuestionAnalysis 객체인 경우 처리
                    response.entities.stock_name = stock_name
                    response.entities.stock_code = stock_code

                    # 모든 데이터 전부 on
                    response.data_requirements.reports_needed = True
                    response.data_requirements.telegram_needed = True
                    response.data_requirements.financial_statements_needed = True
                    response.data_requirements.industry_data_needed = True
                    response.data_requirements.confidential_data_needed = True
                    response.data_requirements.revenue_data_needed = True

                    # 기술적 분석은 무조건 필요로 설정 (키워드 감지와 관계없이)
                    ta_needed = True  # self._detect_technical_analysis_need(query) 대신 무조건 True
                    response.data_requirements.technical_analysis_needed = ta_needed
                    logger.info(f"[데이터요구사항] technical_analysis_needed 설정: {ta_needed} (무조건 활성화)")

                    # 분석 결과 로깅
                    logger.info(f"Analysis result: {response}")

                    # 서브그룹 가져오기
                    stock_info_service = StockInfoService()
                    subgroup_list = await stock_info_service.get_sector_by_code(stock_code)
                    logger.info(f"subgroup_info: {subgroup_list}")

                    if subgroup_list and len(subgroup_list) > 0:
                        response.entities.subgroup = subgroup_list

                    # QuestionAnalysisResult 객체 생성 - 유틸리티 함수 사용
                    question_analysis: QuestionAnalysisResult = {
                        "entities": response.entities.dict(),
                        "classification": response.classification.dict(),
                        "data_requirements": response.data_requirements.dict(),
                        "keywords": response.keywords,
                        "detail_level": response.detail_level,
                    }

                except Exception as e:
                    # 구조화된 출력 파싱에 실패한 경우 fallback 처리
                    logger.error(f"구조화된 출력 파싱 중 오류 발생: {str(e)}")

                    # LLM 호출 다시 시도 (일반 응답으로)
                    logger.info("일반 응답 형식으로 다시 시도합니다.")
                    ai_response: AIMessage = await self.agent_llm.ainvoke_with_fallback(prompt, user_id=user_id, project_type=ProjectType.STOCKEASY, db=self.db)

                    logger.info(f"일반 응답 받음: {type(ai_response)}")

                    # AIMessage에서 JSON 파싱 시도
                    try:
                        # JSON 패턴 찾기 (중괄호로 감싸진 부분) - re 모듈은 이미 최상단에 import됨
                        json_str = extract_json_from_text(ai_response.content)

                        if json_str:
                            # JSON 문자열 파싱
                            parsed_data = json.loads(json_str)
                            logger.info(f"\n✅ JSON 파싱 성공: title={parsed_data.get('title')}, sections={len(parsed_data.get('sections', []))}개")

                            # 기본 데이터 구조 생성
                            question_analysis = {
                                "entities": {
                                    "stock_name": stock_name,
                                    "stock_code": stock_code,
                                    "sector": parsed_data.get("entities", {}).get("sector"),
                                    "subgroup": None,  # 아래에서 설정
                                    "time_range": parsed_data.get("entities", {}).get("time_range"),
                                    "financial_metric": parsed_data.get("entities", {}).get("financial_metric"),
                                    "competitor": parsed_data.get("entities", {}).get("competitor"),
                                    "product": parsed_data.get("entities", {}).get("product"),
                                },
                                "classification": {
                                    "primary_intent": parsed_data.get("classification", {}).get("primary_intent", "종목기본정보"),
                                    "complexity": parsed_data.get("classification", {}).get("complexity", "중간"),
                                    "expected_answer_type": parsed_data.get("classification", {}).get("expected_answer_type", "사실형"),
                                },
                                "data_requirements": {
                                    "telegram_needed": True,
                                    "reports_needed": True,
                                    "financial_statements_needed": True,
                                    "industry_data_needed": True,
                                    "confidential_data_needed": True,
                                    "revenue_data_needed": True,
                                    "web_search_needed": parsed_data.get("data_requirements", {}).get("web_search_needed", False),
                                    "technical_analysis_needed": True,  # 무조건 활성화
                                },
                                "keywords": parsed_data.get("keywords", []),
                                "detail_level": parsed_data.get("detail_level", "보통"),
                            }

                            # 서브그룹 가져오기
                            stock_info_service = StockInfoService()
                            subgroup_list = await stock_info_service.get_sector_by_code(stock_code)
                            logger.info(f"subgroup_info: {subgroup_list}")

                            if subgroup_list and len(subgroup_list) > 0:
                                question_analysis["entities"]["subgroup"] = subgroup_list
                        else:
                            logger.warning("JSON 패턴을 찾을 수 없음, 기본 응답 구조 사용")
                            # 기본 응답 구조 생성
                            question_analysis = await create_default_question_analysis(stock_name, stock_code)

                    except Exception as json_error:
                        logger.error(f"JSON 파싱 중 오류 발생: {str(json_error)}")
                        # 기본 응답 구조 생성
                        question_analysis = await create_default_question_analysis(stock_name, stock_code)

                return question_analysis

            # 기본 질문 분석 구조 생성 함수
            async def create_default_question_analysis(stock_name, stock_code):
                # 서브그룹 가져오기
                try:
                    stock_info_service = StockInfoService()
                    subgroup_list = await stock_info_service.get_sector_by_code(stock_code)
                except Exception:
                    subgroup_list = []

                # 기술적 분석은 무조건 필요로 설정 (기본 구조에서도)
                ta_needed_default = True  # self._detect_technical_analysis_need(query) 대신 무조건 True
                logger.info(f"[기본분석구조] 기술적분석 필요성 설정: {ta_needed_default} (무조건 활성화)")

                return {
                    "entities": {
                        "stock_name": stock_name,
                        "stock_code": stock_code,
                        "sector": None,
                        "subgroup": subgroup_list if subgroup_list and len(subgroup_list) > 0 else None,
                        "time_range": None,
                        "financial_metric": None,
                        "competitor": None,
                        "product": None,
                    },
                    "classification": {"primary_intent": "종목기본정보", "complexity": "중간", "expected_answer_type": "사실형"},
                    "data_requirements": {
                        "telegram_needed": True,
                        "reports_needed": True,
                        "financial_statements_needed": True,
                        "industry_data_needed": True,
                        "confidential_data_needed": True,
                        "revenue_data_needed": True,
                        "web_search_needed": False,
                        "technical_analysis_needed": ta_needed_default,
                    },
                    "keywords": [stock_name, "정보"],
                    "detail_level": "보통",
                }

            # 2. 최근 이슈 검색 및 목차 생성 비동기 함수
            async def search_issues_and_generate_toc():
                # logger.info(f"search_issues_and_generate_toc 실행: {user_email} - {settings.ADMIN_IDS}, {user_email in settings.ADMIN_IDS}")
                is_admin_and_prod = settings.ENV == "production" and user_email in settings.ADMIN_IDS
                redis_client = self.redis_client
                cache_key_prefix = "recent_issues_summary"
                cache_key = f"{cache_key_prefix}:{stock_name}:{stock_code}"

                recent_issues_summary = None

                # 1. 관리자가 아닌 경우에만 캐시에서 조회
                if not is_admin_and_prod:
                    cached_summary = await redis_client.get_key(cache_key)
                    if cached_summary:
                        logger.info(f"종목 [{stock_name}/{stock_code}]에 대한 캐시된 최근 이슈 요약 사용: {cache_key}")
                        recent_issues_summary = cached_summary

                # 2. 캐시에 데이터가 없거나 관리자인 경우, 새로 생성하고 캐시에 저장
                if recent_issues_summary is None:
                    if is_admin_and_prod:
                        logger.info(f"관리자({user_email}) 요청: 캐시를 건너뛰고 최근 이슈를 다시 검색 및 요약합니다.")
                    else:
                        logger.info(f"종목 [{stock_name}/{stock_code}]에 대한 캐시 없음, 최근 이슈 요약 생성: {cache_key}")

                    recent_issues_summary = await self.summarize_recent_issues(stock_name, stock_code, user_id)

                    # 생성된 요약을 캐시에 저장
                    expire_time = 259200  # 172800 2일 -> 3일
                    if settings.ENV == "development":
                        expire_time = 86400 * 7  # 개발버전은 7일단위.
                    await redis_client.set_key(cache_key, recent_issues_summary, expire=expire_time)

                    log_message_prefix = "관리자 요청으로 갱신된 " if is_admin_and_prod else ""
                    logger.info(f"{log_message_prefix}최근 이슈 요약을 캐시에 저장 (만료: {expire_time}초): {cache_key}")

                final_report_toc = await self.generate_dynamic_toc(query, recent_issues_summary, user_id)
                return {"recent_issues_summary": recent_issues_summary, "final_report_toc": final_report_toc.model_dump()}

            # 두 작업 병렬 실행
            question_analysis_task = analyze_question_intent()
            issues_and_toc_task = search_issues_and_generate_toc()

            # 병렬 작업 실행 및 결과 수집
            question_analysis_result, issues_and_toc_result = await asyncio.gather(question_analysis_task, issues_and_toc_task)

            # 병렬 처리 결과 저장
            state["question_analysis"] = question_analysis_result
            state["agent_results"]["question_analysis"] = question_analysis_result
            state["recent_issues_summary"] = issues_and_toc_result["recent_issues_summary"]
            state["final_report_toc"] = issues_and_toc_result["final_report_toc"]

            # 성능 지표 업데이트
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()

            # 메트릭 기록
            state["metrics"] = state.get("metrics", {})
            state["metrics"]["question_analyzer"] = {
                "start_time": start_time,
                "end_time": end_time,
                "duration": duration,
                "status": "completed",
                "error": None,
                "model_name": self.agent_llm.get_model_name(),
            }

            # 처리 상태 업데이트
            state["processing_status"] = state.get("processing_status", {})
            state["processing_status"]["question_analyzer"] = "completed"

            logger.info(f"QuestionAnalyzerAgent completed in {duration:.2f} seconds")
            return state

        except Exception as e:
            logger.exception(f"Error in QuestionAnalyzerAgent: {str(e)}")
            self._add_error(state, f"질문 분석기 에이전트 오류: {str(e)}")
            return state

    async def analyze_conversation_context(
        self, query: str, conversation_history: List[Any], stock_name: str, stock_code: str, user_id: Optional[str] = None
    ) -> ConversationContextAnalysis:
        """
        현재 질문이 이전 대화 컨텍스트에 의존하는지 분석합니다.

        Args:
            query: 현재 사용자 질문
            conversation_history: 이전 대화 기록 (LangChain 메시지 객체 목록)

        Returns:
            대화 컨텍스트 분석 결과
        """
        # logger.info(f"Analyzing conversation context dependency for query: {query}")

        if not conversation_history or len(conversation_history) < 2:
            # logger.info("대화 기록이 충분하지 않음, 컨텍스트 분석 건너뜀")
            return ConversationContextAnalysis(
                requires_context=False,
                is_followup_question=False,
                relation_to_previous="독립적",
                is_conversation_closing=False,
                closing_type=None,
                closing_response=None,
                is_different_stock=False,
                previous_stock_name=None,
                previous_stock_code=None,
                stock_relation="알수없음",
                reasoning="대화 기록이 충분하지 않습니다.",
            )

        # 대화 기록 포맷팅 (최근 3번의 대화만 사용)
        formatted_history = ""
        recent_history = conversation_history[-6:] if len(conversation_history) >= 6 else conversation_history

        for i, msg in enumerate(recent_history):
            role = "사용자" if msg.type == "human" else "AI"
            formatted_history += f"{role}: {msg.content}\n\n"

        # 대화 컨텍스트 분석 프롬프트
        system_prompt = """
당신은 대화 흐름 분석 전문가입니다. 현재 질문이 이전 대화 컨텍스트에 의존하는지, 독립적인 새 질문인지, 또는 대화 마무리를 뜻하는 인사말인지 판단해야 합니다.

다음 사항을 고려하세요:
1. 대명사(이것, 그것, 저것 등)나 생략된 주어가 있는지
2. 이전 대화에서 언급된 특정 정보를 참조하는지
3. 이전 응답에 대한 후속 질문인지
4. 이전 응답 내용을 확장하거나 수정하려는 의도가 있는지
5. "고마워", "감사합니다", "알겠습니다", "정보가 없네", "바보야" 등 대화 마무리를 뜻하는 표현인지
6. 현재 질문이 이전 질문들에서 언급된 종목과 다른 종목에 관한 것인지 판단하세요

예시)
 - 고마워. 감사합니다 : 대화 마무리
 - 고마워, 그럼 24년 영업이익은 어떻게 되는거지? : 후속 질문
 - 정보가 없네. 다른 경쟁사들은 어떻게 하는지 찾아봐 : 후속 질문
 - 바보야 : 대화 마무리

종목 관계 분석 가이드:
- 종목명이나 종목코드가 명시적으로 언급되지 않은 경우, 맥락을 통해 동일 종목에 관한 질문인지 추론하세요.
- 질문에서 새로운 종목이 언급되었지만 이전 종목과의 비교를 위한 것이라면, "종목비교"로 판단하세요.
- 이전 대화와 전혀 관련 없는 새로운 종목에 대한 질문이면 "다른종목"으로 판단하세요.
- 같은 종목에 대한 후속 질문이면 "동일종목"으로 판단하세요.

대화 마무리로 판단된 경우, 마무리 유형(긍정적/중립적/부정적)에 따라 적절한 응답 메시지를 생성해 주세요:
- 긍정적 마무리(예: "감사합니다", "고마워"): 친절하고 도움이 되었다는 메시지로 응답
- 중립적 마무리(예: "알겠습니다", "끝내자"): 간결하고 정중한 마무리 메시지로 응답
- 부정적 마무리(예: "정보가 없네", "바보야"): 공손하게 사과하고 더 나은 서비스를 약속하는 메시지로 응답

분석 결과를 다음 형식으로 제공하세요:
- requires_context: 이전 대화 컨텍스트가 필요한지 여부(true/false)
- is_followup_question: 이전 질문에 대한 후속 질문인지 여부(true/false)
- referenced_context: 참조하는 특정 대화 내용(있는 경우)
- relation_to_previous: 이전 대화와의 관계("독립적", "직접참조", "간접참조", "확장", "수정" 중 하나)
- is_conversation_closing: 대화 마무리를 뜻하는 인사말인지 여부(true/false)
- closing_type: 마무리 인사의 유형("긍정적", "중립적", "부정적" 중 하나, is_conversation_closing이 true인 경우에만 값 제공)
- closing_response: 마무리 인사에 대한 응답 메시지(is_conversation_closing이 true인 경우에만 값 제공)
- is_different_stock: 이전 질문과 다른 종목에 관한 질문인지 여부(true/false)
- previous_stock_name: 이전 질문에서 언급된 종목명(있는 경우)
- previous_stock_code: 이전 질문에서 언급된 종목코드(있는 경우)
- stock_relation: 이전 종목과의 관계("동일종목", "종목비교", "다른종목", "알수없음" 중 하나)
- reasoning: 판단 이유 설명(3-4문장으로 간결하게)
"""

        user_prompt = f"""
대화 기록:
{formatted_history}

현재 질문:
{query}

현재 종목 정보: [종목명: {stock_name}, 종목코드: {stock_code}]

위 대화에서 현재 질문이 이전 대화 컨텍스트에 의존하는지, 대화 마무리 표현인지, 종목 관계는 어떤지 분석해주세요.
"""

        try:
            [SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)]
            formatted_prompt = f"{system_prompt}\n\n{user_prompt}"
            # LLM 호출로 대화 컨텍스트 분석
            response = await self.agent_llm_lite.with_structured_output(ConversationContextAnalysis).ainvoke(
                formatted_prompt, project_type=ProjectType.STOCKEASY, user_id=user_id, db=self.db
            )

            logger.info(f"대화 컨텍스트 분석 결과: {response}")
            return response

        except Exception as e:
            logger.error(f"대화 컨텍스트 분석 중 오류 발생: {str(e)}")
            # 오류 발생 시 기본값 반환
            return ConversationContextAnalysis(
                requires_context=False,
                is_followup_question=False,
                relation_to_previous="독립적",
                is_conversation_closing=False,
                closing_type=None,
                closing_response=None,
                is_different_stock=False,
                previous_stock_name=None,
                previous_stock_code=None,
                stock_relation="알수없음",
                reasoning=f"분석 중 오류 발생: {str(e)}",
            )

    def _add_error(self, state: Dict[str, Any], error_message: str) -> None:
        """
        상태 객체에 오류 정보를 추가합니다.

        Args:
            state: 상태 객체
            error_message: 오류 메시지
        """
        state["errors"] = state.get("errors", [])
        state["errors"].append(
            {"agent": "question_analyzer", "error": error_message, "type": "processing_error", "timestamp": datetime.now(), "context": {"query": state.get("query", "")}}
        )

        # 처리 상태 업데이트
        state["processing_status"] = state.get("processing_status", {})
        state["processing_status"]["question_analyzer"] = "failed"

    # 동적 목차 생성 함수 추가
    async def generate_dynamic_toc(self, query: str, recent_issues_summary: str, user_id: str) -> DynamicTocOutput:
        """
        사용자의 질문과 최근 이슈 요약을 바탕으로 동적인 목차를 생성하는 함수

        Args:
            query (str): 사용자의 초기 질문
            recent_issues_summary (str): 최근 이슈 요약

        Returns:
            DynamicTocOutput: 생성된 목차 구조
        """
        logger.info("\n📋 동적 목차 생성 중...")

        prompt_template = ChatPromptTemplate.from_template(PROMPT_DYNAMIC_TOC).partial(
            query=query, recent_issues_summary=recent_issues_summary, today_date=datetime.now().strftime("%Y-%m-%d")
        )
        formatted_prompt = prompt_template.format_prompt()

        # 1. 먼저 구조화된 출력을 시도
        try:
            logger.info("구조화된 출력(DynamicTocOutput)을 사용하여 목차 생성 시도")
            structured_response = await self.agent_llm.with_structured_output(DynamicTocOutput).ainvoke(
                formatted_prompt, project_type=ProjectType.STOCKEASY, user_id=user_id, db=self.db
            )

            # 구조화된 출력이 성공적으로 파싱된 경우
            logger.info(f"\n✅ 구조화된 출력 성공: title={structured_response.title}, sections={len(structured_response.sections)}개")

            # 섹션이 비어있는 경우 확인
            if len(structured_response.sections) == 0:
                logger.warning("구조화된 출력에 섹션이 없습니다. 기본 응답 구조로 fallback합니다.")
                raise ValueError("구조화된 출력에 섹션이 없습니다.")

            return structured_response

        except Exception as e:
            # 구조화된 출력 파싱 실패 시 fallback으로 일반 텍스트 응답 시도
            logger.warning(f"\n⚠️ 구조화된 출력 실패: {str(e)}, 일반 텍스트 응답으로 fallback")

            # 2. 일반 텍스트 응답 시도
            response: AIMessage = await self.agent_llm.ainvoke_with_fallback(formatted_prompt, project_type=ProjectType.STOCKEASY, user_id=user_id, db=self.db)

            response_text = response.content
            logger.info("\n📄 LLM 원본 응답:")
            logger.info(f"\n{response_text[:200]}")  # 응답 일부 출력 (디버깅용)

            # 3. JSON 문자열 파싱 시도
            try:
                # JSON 부분 추출 (LLM이 JSON 외에 다른 텍스트를 포함할 수 있음)
                json_str = extract_json_from_text(response_text)
                if json_str:
                    # JSON 문자열 파싱
                    toc_data = json.loads(json_str)
                    logger.info(f"\n✅ JSON 파싱 성공: title={toc_data.get('title')}, sections={len(toc_data.get('sections', []))}개")

                    # 섹션이 비어있는 경우 확인
                    if len(toc_data.get("sections", [])) == 0:
                        logger.warning("JSON 파싱 성공했으나 섹션이 없습니다. 기본 목차 구조를 사용합니다.")
                        raise ValueError("JSON 파싱 성공했으나 섹션이 없습니다.")

                    # JSON 데이터를 DynamicTocOutput 모델 형식으로 변환
                    converted_sections = []
                    for section in toc_data.get("sections", []):
                        # 서브섹션 변환
                        converted_subsections = []
                        for subsection in section.get("subsections", []):
                            converted_subsections.append(
                                SubsectionModel(subsection_id=subsection.get("subsection_id", ""), title=subsection.get("title", ""), description=subsection.get("description"))
                            )

                        # 섹션 변환
                        converted_sections.append(
                            SectionModel(
                                section_id=section.get("section_id", ""), title=section.get("title", ""), description=section.get("description"), subsections=converted_subsections
                            )
                        )

                    # DynamicTocOutput 객체 생성
                    result = DynamicTocOutput(title=toc_data.get("title", f"투자 리서치 보고서: {query}"), sections=converted_sections)

                    return result

                else:
                    # JSON 패턴을 찾지 못한 경우
                    logger.warning("JSON 문자열을 추출할 수 없음, 기본 응답 구조 사용")
                    raise ValueError("JSON 문자열을 추출할 수 없습니다.")

            except Exception as json_error:
                # 4. JSON 파싱 실패 시 기본 목차 구조 사용
                logger.warning(f"\n⚠️ JSON 파싱 오류: {str(json_error)}, 기본 목차 구조 사용")
                logger.warning(f"LLM 원본 응답:\n{response_text}")

                # 기본 목차 구조 생성
                default_sections = [
                    SectionModel(section_id="section_1", title="핵심 요약 (Executive Summary)", description="주요 발견과 결론을 요약", subsections=[]),
                    SectionModel(section_id="section_2", title="기업 개요 및 사업 모델", description="기업의 기본 정보와 비즈니스 모델 분석", subsections=[]),
                    SectionModel(section_id="section_3", title="산업/시장 동향 분석", description="기업이 속한 산업의 현황과 전망", subsections=[]),
                ]

                # 기본 DynamicTocOutput 객체 생성
                result = DynamicTocOutput(title=f"투자 리서치 보고서: {query}", sections=default_sections)

                print(f"\n✅ 동적 목차 생성 완료. 총 {len(result.sections)}개 섹션 포함")
                print(f"📚 보고서 제목: {result.title}")

                # 섹션 정보 상세 출력
                print("📑 목차 구조:")
                for section in result.sections:
                    print(f"  {section.title}")
                    if section.description:
                        print(f"     - {section.description}")

                    # 하위 섹션이 있으면 출력
                    if section.subsections:
                        for subsection in section.subsections:
                            print(f"     {subsection.title}")

                return result

    async def summarize_recent_issues(self, stock_name: str, stock_code: str, user_id: str) -> str:
        """LLM을 사용하여 검색된 최근 이슈 결과를 요약합니다."""

        search_results = await self.search_recent_issues(stock_name, stock_code)  # 최근 이슈 검색

        print(f"\n📝 {stock_name}의 최근 이슈 요약 중...")
        prompt = f"""
    다음은 '{stock_name}'에 대한 최근 주요 뉴스 및 이슈 검색 결과입니다. 이 내용을 바탕으로 주요 뉴스 제목, 핵심 이슈, 반복적으로 언급되는 키워드를 간결하게 요약해주세요. 요약은 글머리 기호(불릿 포인트) 형식을 사용하고, 가장 중요한 순서대로 정렬해주세요..

    검색 결과:
    {search_results}

    최근 주요 뉴스 및 이슈 검색 결과 키워드 요약:
    """
        try:
            response = await self.agent_llm_lite.ainvoke_with_fallback(prompt, project_type=ProjectType.STOCKEASY, user_id=user_id, db=self.db)

            summary = response.content
            print(f"  📝 {stock_name} 최근 이슈 요약 완료.")
            # print(f"=== 요약 내용 ===\\n{summary}\\n===========") # 디버깅용
            return summary
        except Exception as e:
            print(f"  ⚠️ {stock_name} 최근 이슈 요약 중 오류: {str(e)}")
            return f"{stock_name} 최근 이슈 요약 중 오류 발생: {str(e)}"

    async def search_recent_issues(self, stock_name: str, stock_code: str) -> str:
        """Tavily API를 사용하여 특정 종목의 최근 6개월간 주요 뉴스 및 이슈를 검색합니다."""
        print(f"\n🔍 {stock_name}의 최근 주요 이슈 검색 중...")
        query = f"{stock_name}({stock_code}) 최근 주요 뉴스 및 핵심 이슈 동향"
        try:
            # search_with_tavily 함수를 재사용하거나 직접 Tavily 호출 로직 구현
            search_results = await self.search_with_tavily(query)
            print(f"  📊 {stock_name} 최근 이슈 검색 완료.\n[{search_results[:200]}]")

            # 검색 결과를 JSON 파일로 저장
            await self._save_recent_issues_to_json(stock_name, stock_code, query, search_results)

            return search_results
        except Exception as e:
            print(f"  ⚠️ {stock_name} 최근 이슈 검색 중 오류: {str(e)}")
            return f"{stock_name} 최근 이슈 검색 중 오류 발생: {str(e)}"

    async def _save_recent_issues_to_json(self, stock_name: str, stock_code: str, query: str, search_results: Any) -> None:
        """
        최근 이슈 검색 결과를 일자별 JSON 파일로 저장합니다. 비동기 방식으로 동작합니다.

        Args:
            stock_name: 종목 이름
            stock_code: 종목 코드
            query: 검색 쿼리
            search_results: Tavily API 검색 결과

        Returns:
            None
        """
        try:
            # 파일 I/O 작업을 별도 스레드에서 실행하기 위한 함수 정의
            def write_to_json() -> str:
                # JSON 파일 경로 설정
                json_dir = os.path.join("stockeasy", "local_cache", "web_search")
                os.makedirs(json_dir, exist_ok=True)

                date_str = datetime.now().strftime("%Y%m%d")
                json_path = os.path.join(json_dir, f"recent_issues_{date_str}.json")

                # 현재 날짜와 시간
                current_datetime = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                # 저장할 데이터 구성
                entry = {"timestamp": current_datetime, "stock_code": stock_code, "stock_name": stock_name, "query": query, "search_results": search_results}

                # 파일 존재 여부 확인
                data = []
                if os.path.exists(json_path) and os.path.getsize(json_path) > 0:
                    try:
                        with open(json_path, "r", encoding="utf-8-sig") as json_file:
                            data = json.load(json_file)
                    except json.JSONDecodeError:
                        # 파일이 손상된 경우 새로 시작
                        data = []

                # 데이터 추가
                data.append(entry)

                # 파일에 저장
                with open(json_path, "w", encoding="utf-8-sig") as json_file:
                    json.dump(data, json_file, ensure_ascii=False, indent=2)

                return json_path

            # 파일 I/O 작업을 별도 스레드에서 비동기적으로 실행
            json_path = await asyncio.to_thread(write_to_json)

            print(f"  💾 {stock_name} 최근 이슈 검색결과가 JSON 파일에 저장되었습니다: {json_path}")

        except Exception as e:
            print(f"  ⚠️ JSON 파일 저장 중 오류 발생: {str(e)}")

    async def search_with_tavily(self, query: str) -> str:
        """Tavily API를 사용하여 웹 검색을 수행합니다."""
        try:
            # search_results = await self.tavily_search.ainvoke({"query": query,
            #                                                    "search_depth":"basic",# "advanced",
            #                                                 "max_results": 10,
            #                                                 "topic": "general",
            #                                                 #"topic":"finance",
            #                                                 "time_range" : "6m",
            #                                                 "chunks_per_source": 3,
            #                                                 "include_raw_content": True,
            #                                                 "include_answer":True
            #                                                 })
            # search_results = await self.tavily_search.ainvoke({"query": query,
            #                                     "search_depth": "advanced", # "basic",
            #                                     #"search_depth": "basic", # "basic",
            #                                     "max_results": 14,
            #                                     "topic": "general",
            #                                     #"topic":"finance",
            #                                     "time_range" : "year",
            #                                     })
            search_results = await self.tavily_service.search_async(
                query=query,
                search_depth="advanced",  # "basic",
                # "search_depth": "basic", # "basic",
                max_results=14,
                topic="general",
                # "topic":"finance",
                time_range="year",
            )

            # print(f"검색결과 : {search_results}")
            # print(f"검색결과 시간 : {search_results.get('response_time', '0')}")
            # print(f"검색결과 응답 : {search_results.get('answer', 'None')}")
            formatted_results = "검색 결과:\n\n"
            for i, result_item in enumerate(search_results.get("results", []), 1):
                # result_item이 딕셔너리인지 확인 후 처리합니다.
                if isinstance(result_item, dict):
                    formatted_results += f"{i}. 제목: {result_item.get('title', '제목 없음')}\n"
                    formatted_results += f"   URL: {result_item.get('url', '링크 없음')}\n"
                    formatted_results += f"   내용: {result_item.get('content', '내용 없음')}\n\n"
                else:
                    # result_item이 딕셔너리가 아닌 경우 로그를 남기거나 다른 처리를 할 수 있습니다.
                    logger.warning(f"검색 결과 항목이 예상된 딕셔너리 타입이 아닙니다: {result_item}")
                    formatted_results += f"{i}. 처리할 수 없는 결과 항목입니다.\n\n"
            return formatted_results
        except Exception as e:
            print(f"검색 중 오류가 발생했습니다: {str(e)}")
            return f"검색 중 오류가 발생했습니다: {str(e)}"

    def _detect_technical_analysis_need(self, query: str) -> bool:
        """
        질문에서 기술적 분석 관련 키워드를 감지하여 기술적 분석 필요성을 판단합니다.

        Args:
            query: 사용자 질문

        Returns:
            기술적 분석이 필요한지 여부
        """
        try:
            logger.info(f"[기술적분석감지] 분석 시작 - 쿼리: '{query}'")

            # 질문을 소문자로 변환하여 대소문자 무관하게 검색
            query_lower = query.lower()
            logger.debug(f"[기술적분석감지] 소문자 변환: '{query_lower}'")

            # 각 카테고리별 키워드 매칭 점수 계산
            keyword_scores = {}
            total_matches = 0

            for category, keywords in self.technical_analysis_keywords.items():
                matches = 0
                matched_keywords = []

                for keyword in keywords:
                    keyword_lower = keyword.lower()
                    if keyword_lower in query_lower:
                        matches += 1
                        matched_keywords.append(keyword)
                        total_matches += 1
                        logger.debug(f"[기술적분석감지] 키워드 매칭: '{keyword}' in '{query_lower}' (카테고리: {category})")

                keyword_scores[category] = {"matches": matches, "matched_keywords": matched_keywords, "score": matches / len(keywords) if keywords else 0}

                if matches > 0:
                    logger.info(f"[기술적분석감지] {category} 카테고리 매칭: {matches}개 - {matched_keywords}")

            logger.info(f"[기술적분석감지] 전체 키워드 매칭 결과: 총 {total_matches}개 매칭")
            logger.info(f"[기술적분석감지] 카테고리별 점수: {keyword_scores}")

            # 기술적 분석 필요성 판단 로직
            needs_technical_analysis = False
            reasoning = []

            # 1. 직접적인 기술분석 키워드 확인
            logger.info(f"[기술적분석감지] 규칙1 확인 - market_analysis 매칭: {keyword_scores['market_analysis']['matches']}개")
            if keyword_scores["market_analysis"]["matches"] > 0:
                needs_technical_analysis = True
                reasoning.append(f"기술분석 직접 키워드 감지: {keyword_scores['market_analysis']['matched_keywords']}")
                logger.info("[기술적분석감지] ✅ 규칙1 통과 - 기술분석 직접 키워드 감지")

            # 2. 기술적 지표 키워드 확인 (2개 이상이면 높은 확률)
            logger.info(f"[기술적분석감지] 규칙2 확인 - technical_indicators 매칭: {keyword_scores['technical_indicators']['matches']}개")
            if keyword_scores["technical_indicators"]["matches"] >= 2:
                needs_technical_analysis = True
                reasoning.append(f"기술적 지표 키워드 다중 감지: {keyword_scores['technical_indicators']['matched_keywords']}")
                logger.info("[기술적분석감지] ✅ 규칙2a 통과 - 기술적 지표 키워드 다중 감지")
            elif keyword_scores["technical_indicators"]["matches"] >= 1:
                # 1개라도 있으면 일단 후보로 고려
                reasoning.append(f"기술적 지표 키워드 감지: {keyword_scores['technical_indicators']['matched_keywords']}")
                logger.info("[기술적분석감지] 📝 규칙2b - 기술적 지표 키워드 1개 감지 (후보)")

            # 3. 매매 신호 키워드 확인
            logger.info(f"[기술적분석감지] 규칙3 확인 - trading_signals 매칭: {keyword_scores['trading_signals']['matches']}개")
            if keyword_scores["trading_signals"]["matches"] >= 1:
                needs_technical_analysis = True
                reasoning.append(f"매매 신호 키워드 감지: {keyword_scores['trading_signals']['matched_keywords']}")
                logger.info("[기술적분석감지] ✅ 규칙3 통과 - 매매 신호 키워드 감지")

            # 4. 차트 패턴 기반 판단 (패턴 키워드 1개만 있어도 기술적 분석으로 분류)
            chart_pattern_matches = keyword_scores["chart_patterns"]["matches"]
            technical_indicator_matches = keyword_scores["technical_indicators"]["matches"]
            price_movement_matches = keyword_scores["price_movements"]["matches"]
            logger.info(
                f"[기술적분석감지] 규칙4 확인 - chart_patterns: {chart_pattern_matches}개, technical_indicators: {technical_indicator_matches}개, price_movements: {price_movement_matches}개"
            )

            if chart_pattern_matches >= 1:
                needs_technical_analysis = True
                reasoning.append(f"차트패턴 키워드 감지: {keyword_scores['chart_patterns']['matched_keywords']}")
                logger.info("[기술적분석감지] ✅ 규칙4a 통과 - 차트패턴 키워드 감지 (1개 이상)")
            elif price_movement_matches >= 2:
                # 가격 움직임만으로는 약하지만 2개 이상이면 고려
                reasoning.append(f"가격 움직임 키워드 다중 감지: {keyword_scores['price_movements']['matched_keywords']}")
                logger.info("[기술적분석감지] 📝 규칙4b - 가격 움직임 키워드 다중 감지 (후보)")

            # 5. 전체 매칭 키워드 수가 많으면 기술적 분석 가능성 높음
            logger.info(f"[기술적분석감지] 규칙5 확인 - 총 매칭 키워드: {total_matches}개, 현재 결과: {needs_technical_analysis}")
            if total_matches >= 2 and not needs_technical_analysis:
                needs_technical_analysis = True
                reasoning.append(f"기술적 분석 관련 키워드 다수 감지 (총 {total_matches}개)")
                logger.info("[기술적분석감지] ✅ 규칙5 통과 - 키워드 다수 감지 (2개 이상)")

            # 최종 판단 로깅
            if needs_technical_analysis:
                logger.info(f"[기술적분석감지] 🎯 최종 결과: TRUE - 이유: {', '.join(reasoning)}")
            else:
                logger.info(f"[기술적분석감지] ❌ 최종 결과: FALSE - 매칭된 키워드 총 {total_matches}개")

            return needs_technical_analysis

        except Exception as e:
            logger.error(f"[기술적분석감지] ❌ 오류 발생: {str(e)}")
            logger.info("[기술적분석감지] 🛡️ 안전하게 False 반환")
            # 오류 발생 시 안전하게 False 반환
            return False

    async def _handle_general_question(self, state: Dict[str, Any], query: str, start_time: datetime) -> Dict[str, Any]:
        """
        일반 질문 모드 처리

        Args:
            state: 현재 상태
            query: 사용자 질문
            start_time: 처리 시작 시간

        Returns:
            업데이트된 상태
        """
        try:
            logger.info("일반 질문 분석 시작")

            # user_id 추출
            user_context = state.get("user_context", {})
            user_id = user_context.get("user_id", None)

            # 1. 사용자 질문에서 종목 정보 추출 시도
            extracted_entities = await self._extract_entities_from_query(query, user_id)
            stock_name = extracted_entities.get("stock_name")
            stock_code = extracted_entities.get("stock_code")
            has_stock_reference = extracted_entities.get("has_stock_reference", False)

            # 2. 질문 분석
            analysis_result = await self._analyze_general_question(query, extracted_entities, state)

            # 3. 최근 이슈 요약 (종목이 언급된 경우)
            recent_issues_summary = ""
            if has_stock_reference and stock_name and stock_code:
                logger.info(f"일반 질문 내 종목({stock_name}) 언급 확인, 최근 이슈 검색 수행")
                recent_issues_summary = await self.summarize_recent_issues(stock_name, stock_code, user_id)

            # 4. 기술적 분석 섹션 제외한 동적 목차 생성
            # 참고: _generate_general_toc는 analysis_result가 필요하여 병렬처리 불가
            final_report_toc = await self._generate_general_toc(query, analysis_result, user_id)

            # 5. 결과 저장 (stock-specific 플로우와 동일한 구조로)
            state["question_analysis"] = analysis_result
            state["agent_results"] = state.get("agent_results", {})
            state["agent_results"]["question_analysis"] = analysis_result
            state["recent_issues_summary"] = recent_issues_summary
            state["final_report_toc"] = final_report_toc

            # 메트릭 기록
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()

            state["metrics"] = state.get("metrics", {})
            state["metrics"]["question_analyzer"] = {
                "start_time": start_time,
                "end_time": end_time,
                "duration": duration,
                "status": "completed",
                "error": None,
                "model_name": self.agent_llm.get_model_name(),
                "general_mode": True,
            }

            state["processing_status"] = state.get("processing_status", {})
            state["processing_status"]["question_analyzer"] = "completed"

            logger.info(f"일반 질문 분석 완료: {duration:.2f}초 소요")
            return state

        except Exception as e:
            logger.error(f"일반 질문 처리 중 오류: {str(e)}")
            self._add_error(state, f"일반 질문 분석 오류: {str(e)}")
            return state

    async def _extract_entities_from_query(self, query: str, user_id: Optional[str] = None) -> Dict[str, Any]:
        """사용자 질문에서 종목 정보 추출"""
        try:
            extraction_prompt = f"""
            다음 질문에서 종목명, 종목코드, 섹터 정보를 추출해주세요:

            질문: {query}

            - subgroup은 사용자 질문에 포함된 키워드 혹은 사용자 질문이 의도하는 키워드를 포함해야합니다.
            - subgroup은 최소 1개 이상의 키워드를 포함해야합니다.

            JSON 형식으로 답변해주세요:
            {{
                "stock_name": "종목명 또는 null",
                "stock_code": "종목코드 또는 null", 
                "sector": "섹터 또는 null",
                "subgroup": ["키워드1", "키워드2", "키워드3"],
                "has_stock_reference": True/False,
            }}
            """

            response = await self.agent_llm_lite.ainvoke_with_fallback(extraction_prompt, project_type=ProjectType.STOCKEASY, user_id=user_id, db=self.db)

            # JSON 응답 파싱
            content = response.content if hasattr(response, "content") else str(response)
            json_str = remove_json_block(content)

            if json_str:
                try:
                    result = json.loads(json_str)
                except json.JSONDecodeError:
                    result = {"has_stock_reference": False}
            else:
                result = {"has_stock_reference": False}

            return result if result else {"has_stock_reference": False}

        except Exception as e:
            logger.error(f"엔티티 추출 오류: {str(e)}")
            return {"has_stock_reference": False}

    async def _analyze_general_question(self, query: str, entities: Dict[str, Any], state: Dict[str, Any]) -> Dict[str, Any]:
        """일반 질문 분석"""
        try:
            # 기술적 분석 필요성 설정 (기본값과 동일)
            ta_needed_default = True
            logger.info(f"[일반질문분석] 기술적분석 필요성 설정: {ta_needed_default} (무조건 활성화)")

            stock_name = entities.get("stock_name")
            stock_code = entities.get("stock_code")
            subgroup = entities.get("subgroup")

            # create_default_question_analysis와 완전히 동일한 구조
            analysis_result = {
                "entities": {
                    "stock_name": stock_name,
                    "stock_code": stock_code,
                    "sector": None,
                    "subgroup": subgroup if subgroup else [],  # None 대신 빈 리스트
                    "time_range": None,
                    "financial_metric": None,
                    "competitor": None,
                    "product": None,
                },
                "classification": {"primary_intent": "종목기본정보", "complexity": "중간", "expected_answer_type": "사실형"},
                "data_requirements": {
                    "telegram_needed": True,
                    "reports_needed": True,
                    "financial_statements_needed": True,
                    "industry_data_needed": True,
                    "confidential_data_needed": True,
                    "revenue_data_needed": True,
                    "web_search_needed": False,
                    "technical_analysis_needed": ta_needed_default,
                },
                "keywords": [stock_name or "일반질문", "정보"],
                "detail_level": "보통",
            }

            return analysis_result

        except Exception as e:
            logger.error(f"일반 질문 분석 오류: {str(e)}")
            raise

    async def _generate_general_toc(self, query: str, analysis_result: Dict[str, Any], user_id: Optional[str] = None) -> Dict[str, Any]:
        """일반 질문용 동적 목차 생성 (기술적 분석 섹션 제외)"""
        try:
            logger.info("\n📋 일반 질문 동적 목차 생성 중...")

            prompt_template = ChatPromptTemplate.from_template(PROMPT_DYNAMIC_GENERAL_TOC).partial(
                query=query, analysis_result=analysis_result, today_date=datetime.now().strftime("%Y-%m-%d")
            )
            formatted_prompt = prompt_template.format_prompt()

            # 1. 먼저 구조화된 출력을 시도
            try:
                logger.info("구조화된 출력(DynamicTocOutput)을 사용하여 일반 목차 생성 시도")
                structured_response = await self.agent_llm.with_structured_output(DynamicTocOutput).ainvoke(
                    formatted_prompt, project_type=ProjectType.STOCKEASY, user_id=user_id, db=self.db
                )

                # 구조화된 출력이 성공적으로 파싱된 경우
                logger.info(f"\n✅ 구조화된 출력 성공: title={structured_response.title}, sections={len(structured_response.sections)}개")

                # 섹션이 비어있는 경우 확인
                if len(structured_response.sections) == 0:
                    logger.warning("구조화된 출력에 섹션이 없습니다. 기본 응답 구조로 fallback합니다.")
                    raise ValueError("구조화된 출력에 섹션이 없습니다.")

                # DynamicTocOutput을 Dict로 변환
                return {
                    "title": structured_response.title,
                    "sections": [
                        {
                            "section_id": section.section_id,
                            "title": section.title,
                            "description": section.description,
                            "subsections": [
                                {"subsection_id": subsection.subsection_id, "title": subsection.title, "description": subsection.description} for subsection in section.subsections
                            ],
                        }
                        for section in structured_response.sections
                    ],
                }

            except Exception as e:
                # 구조화된 출력 파싱 실패 시 fallback으로 일반 텍스트 응답 시도
                logger.warning(f"\n⚠️ 구조화된 출력 실패: {str(e)}, 일반 텍스트 응답으로 fallback")

                # 2. 일반 텍스트 응답 시도
                response = await self.agent_llm.ainvoke_with_fallback(formatted_prompt, project_type=ProjectType.STOCKEASY, user_id=user_id, db=self.db)

                # JSON 응답 파싱
                content = response.content if hasattr(response, "content") else str(response)
                json_str = extract_json_from_text(content)

                if json_str:
                    try:
                        result = json.loads(json_str)
                        logger.info(f"\n✅ JSON 파싱 성공: title={result.get('title')}, sections={len(result.get('sections', []))}개")

                        # 섹션이 비어있는 경우 확인
                        if len(result.get("sections", [])) == 0:
                            logger.warning("JSON 파싱 성공했으나 섹션이 없습니다. 기본 목차 구조를 사용합니다.")
                            raise ValueError("JSON 파싱 성공했으나 섹션이 없습니다.")

                        return result
                    except json.JSONDecodeError as parse_error:
                        logger.error(f"일반 목차 JSON 파싱 오류: {parse_error}")
                        raise ValueError("JSON 파싱 실패")
                else:
                    logger.warning("JSON 문자열을 추출할 수 없음, 기본 응답 구조 사용")
                    raise ValueError("JSON 문자열을 추출할 수 없습니다.")

        except Exception as e:
            logger.error(f"일반 질문 목차 생성 오류: {str(e)}")
            # 기본 목차 반환
            return {
                "title": "일반 질문 분석 결과",
                "sections": [
                    {"section_id": "section_1", "title": "1. 핵심 요약", "description": "질문에 대한 핵심 내용 요약", "subsections": []},
                    {"section_id": "section_2", "title": "2. 상세 분석", "description": "질문 주제에 대한 상세한 분석 내용", "subsections": []},
                    {"section_id": "section_3", "title": "3. 결론 및 시사점", "description": "분석 결과 및 향후 전망", "subsections": []},
                ],
            }

    def _extract_keywords_from_query(self, query: str) -> List[str]:
        """질문에서 키워드 추출"""
        try:
            # 간단한 키워드 추출 로직
            import re

            # 한국어, 영어, 숫자만 남기고 나머지 제거 후 단어 분리
            words = re.findall(r"\b\w+\b", query)

            # 길이가 2 이상인 단어만 키워드로 추출
            keywords = [word for word in words if len(word) >= 2]

            return keywords[:10]  # 최대 10개 키워드

        except Exception as e:
            logger.error(f"키워드 추출 오류: {str(e)}")
            return []
