"""
질문 분석기 에이전트 모듈

이 모듈은 사용자 질문을 분석하여 의도, 엔티티, 키워드 등의 
중요한 정보를 추출하는 QuestionAnalyzerAgent 클래스를 구현합니다.
"""

import json
from loguru import logger
from typing import Dict, List, Any, Optional, Literal, cast, Union
from datetime import datetime
import os
import asyncio

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel, Field
from typing import List, Optional as PydanticOptional
from stockeasy.services.financial.stock_info_service import StockInfoService
from common.models.token_usage import ProjectType
from common.services.agent_llm import get_llm_for_agent, get_agent_llm
from stockeasy.prompts.question_analyzer_prompts import PROMPT_DYNAMIC_TOC, SYSTEM_PROMPT, format_question_analyzer_prompt
from common.core.config import settings
from common.core.redis import AsyncRedisClient
from stockeasy.models.agent_io import (
    QuestionAnalysisResult, ExtractedEntity, QuestionClassification, 
    DataRequirement, pydantic_to_typeddict
)
from langchain_core.prompts import ChatPromptTemplate
from stockeasy.agents.base import BaseAgent
from sqlalchemy.ext.asyncio import AsyncSession
#from langchain_tavily import TavilySearch
from common.services.tavily import TavilyService

class Entities(BaseModel):
    """추출된 엔티티 정보"""
    stock_name: PydanticOptional[str] = Field(None, description="종목명 또는 null")
    stock_code: PydanticOptional[str] = Field(None, description="종목코드 또는 null")
    sector: PydanticOptional[str] = Field(None, description="종목이 속한 산업/섹터 또는 null")
    subgroup: PydanticOptional[list] = Field(None, description="종목이 속한 subgroup 또는 null")
    time_range: PydanticOptional[str] = Field(None, description="시간범위 또는 null")
    financial_metric: PydanticOptional[str] = Field(None, description="재무지표 또는 null")
    competitor: PydanticOptional[str] = Field(None, description="경쟁사 또는 null")
    product: PydanticOptional[str] = Field(None, description="제품/서비스 또는 null")



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
        )
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
        )
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
        )
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
class DynamicTocOutput(BaseModel):
    """
    동적 목차 생성 결과를 위한 구조화된 출력 포맷
    """
    title: str = Field(
        description="보고서 제목 (질문과 기업명을 반영)"
    )
    sections: List[Dict[str, Any]] = Field(
        description="보고서 섹션 정보"
    )

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
        self.llm, self.model_name, self.provider = get_llm_for_agent("question_analyzer_agent")
        self.agent_llm = get_agent_llm("question_analyzer_agent")
        self.agent_llm_lite = get_agent_llm("gemini-2.0-flash-lite")
        logger.info(f"QuestionAnalyzerAgent initialized with provider: {self.agent_llm.get_provider()}, model: {self.agent_llm.get_model_name()}")
        self.prompt_template = SYSTEM_PROMPT

        #self.tavily_search = TavilySearch(api_key=settings.TAVILY_API_KEY)
        self.tavily_service = TavilyService()
        self.redis_client = AsyncRedisClient()
    
        
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
            logger.info(f"QuestionAnalyzerAgent starting processing")
            
            # 현재 사용자 쿼리 추출
            query = state.get("query", "")
            stock_code = state.get("stock_code", "")
            stock_name = state.get("stock_name", "")
            logger.info(f"query[{stock_name},{stock_code}] : {query}")
            if not query:
                logger.warning("Empty query provided to QuestionAnalyzerAgent")
                self._add_error(state, "질문이 비어 있습니다.")
                return state

            #state["agent_results"] = state.get("agent_results", {})
            # user_id 추출
            user_context = state.get("user_context", {})
            user_id = user_context.get("user_id", None)

            # 대화 기록 확인
            conversation_history = state.get("conversation_history", [])
            logger.info(f"대화 기록 타입: {type(conversation_history)}, 길이: {len(conversation_history) if isinstance(conversation_history, list) else '알 수 없음'}")
            # 대화 컨텍스트 의존성 분석
            # 수정된 조건: 대화 기록이 2개 이상 있는지 확인
            # 상용 서비스에 맞게 type 속성이 있는 경우도 처리
            has_valid_history = (
                conversation_history and 
                isinstance(conversation_history, list) and 
                len(conversation_history) >= 1
            )
            
            if has_valid_history:
                logger.info(f"대화 기록 있음: {len(conversation_history)}개 메시지")
                context_analysis = await self.analyze_conversation_context(query, conversation_history, stock_name, stock_code, user_id)
                context_analysis_result = context_analysis.model_dump() # dict
                
                # 분석 결과 상태에 저장
                state["context_analysis"] = context_analysis_result
                
                # 대화 마무리 인사인지 확인
                if context_analysis.is_conversation_closing:
                    logger.info(f"대화 마무리 인사로 감지: 유형={context_analysis.closing_type}")
                    
                    # 상태 업데이트
                    state["agent_results"]["question_analysis"] = context_analysis_result
                    state["summary"] = context_analysis.closing_response
                    state["formatted_response"] = state["summary"]
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
                        "model_name": self.model_name
                    }
                    
                    state["processing_status"] = state.get("processing_status", {})
                    state["processing_status"]["question_analyzer"] = "completed"
                    
                    logger.info(f"대화 마무리 감지, QuestionAnalyzerAgent 빠른 처리 완료: {duration:.2f}초 소요")
                    logger.info(f"마무리 유형: {context_analysis.closing_type}, 응답: {context_analysis.closing_response}")
                    return state
                
                if context_analysis.is_different_stock and context_analysis.stock_relation == "다른종목":
                    logger.info(f"완전히 다른종목 질문")
                    # 상태 업데이트
                    state["agent_results"]["question_analysis"] = context_analysis_result
                    state["summary"] = "현재 종목과 관련이 없는 질문입니다.\n다른 종목에 관한 질문은 새 채팅에서 해주세요"
                    state["formatted_response"] = state["summary"]
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
                        "model_name": self.model_name
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
                        "model_name": self.model_name
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
                    "reasoning": "대화 기록이 없습니다."
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
                logger.info(f"QuestionAnalyzerAgent using custom prompt from attribute")
            
            import asyncio
            
            # 1. 사용자 질문 의도 분석 및 2. 최근 이슈 검색/목차 생성을 병렬로 실행
            logger.info("사용자 질문 분석과 최근 이슈 검색을 병렬로 실행")
            
            # 1. 사용자 질문 의도 분석 비동기 함수
            async def analyze_question_intent():
                # 프롬프트 준비
                prompt = format_question_analyzer_prompt(query=query, stock_name=stock_name, stock_code=stock_code, system_prompt=system_prompt)
                
                # LLM 호출로 분석 수행 - structured output 사용
                response:QuestionAnalysis = await self.agent_llm.with_structured_output(QuestionAnalysis).ainvoke(
                    prompt, # input=prompt 하면 안됨. 그냥 prompt 전달
                    user_id=user_id,
                    project_type=ProjectType.STOCKEASY,
                    db=self.db
                )
                response.entities.stock_name = stock_name
                response.entities.stock_code = stock_code

                # 모든 데이터 전부 on
                response.data_requirements.reports_needed = True
                response.data_requirements.telegram_needed = True
                response.data_requirements.financial_statements_needed = True
                response.data_requirements.industry_data_needed = True
                response.data_requirements.confidential_data_needed = True
                response.data_requirements.revenue_data_needed = True
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
                    "detail_level": response.detail_level
                }
                
                return question_analysis
            
            # 2. 최근 이슈 검색 및 목차 생성 비동기 함수
            async def search_issues_and_generate_toc():
                redis_client = self.redis_client
                cache_key_prefix = "recent_issues_summary"
                # user_id를 캐시 키에서 제외하여 종목별로 공통 캐시 사용
                cache_key = f"{cache_key_prefix}:{stock_name}:{stock_code}"

                # 1. 캐시에서 데이터 조회
                cached_summary = await redis_client.get_key(cache_key)

                if cached_summary:
                    logger.info(f"종목 [{stock_name}/{stock_code}]에 대한 캐시된 최근 이슈 요약 사용: {cache_key}")
                    recent_issues_summary = cached_summary 
                else:
                    logger.info(f"종목 [{stock_name}/{stock_code}]에 대한 캐시 없음, 최근 이슈 요약 생성: {cache_key}")
                    recent_issues_summary = await self.summarize_recent_issues(stock_name, stock_code, user_id)
                    # 2. 생성된 요약을 캐시에 저장 (만료 시간: 1일 = 86400초) -> 2일로 변경(크레딧 문제때문에..)
                    await redis_client.set_key(cache_key, recent_issues_summary, expire=172800)
                    logger.info(f"종목 [{stock_name}/{stock_code}]에 최근 이슈 요약 캐시 저장 (만료: 1일): {cache_key}")

                final_report_toc = await self.generate_dynamic_toc(query, recent_issues_summary, user_id)
                return {
                    "recent_issues_summary": recent_issues_summary,
                    "final_report_toc": final_report_toc.model_dump()
                }
            
            # 두 작업 병렬 실행
            question_analysis_task = analyze_question_intent()
            issues_and_toc_task = search_issues_and_generate_toc()
            
            # 병렬 작업 실행 및 결과 수집
            question_analysis_result, issues_and_toc_result = await asyncio.gather(
                question_analysis_task,
                issues_and_toc_task
            )
            
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
                "model_name": self.model_name
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

    async def analyze_conversation_context(self, query: str, conversation_history: List[Any], stock_name: str, stock_code: str, user_id: Optional[str] = None) -> ConversationContextAnalysis:
        """
        현재 질문이 이전 대화 컨텍스트에 의존하는지 분석합니다.
        
        Args:
            query: 현재 사용자 질문
            conversation_history: 이전 대화 기록 (LangChain 메시지 객체 목록)
            
        Returns:
            대화 컨텍스트 분석 결과
        """
        logger.info(f"Analyzing conversation context dependency for query: {query}")
        
        if not conversation_history or len(conversation_history) < 2:
            logger.info("대화 기록이 충분하지 않음, 컨텍스트 분석 건너뜀")
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
                reasoning="대화 기록이 충분하지 않습니다."
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
            prompt = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ]
            formatted_prompt = f"{system_prompt}\n\n{user_prompt}"
            # LLM 호출로 대화 컨텍스트 분석
            response = await self.agent_llm_lite.with_structured_output(ConversationContextAnalysis).ainvoke(
                formatted_prompt,
                project_type=ProjectType.STOCKEASY,
                user_id=user_id,
                db=self.db
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
                reasoning=f"분석 중 오류 발생: {str(e)}"
            )
    
    def _add_error(self, state: Dict[str, Any], error_message: str) -> None:
        """
        상태 객체에 오류 정보를 추가합니다.
        
        Args:
            state: 상태 객체
            error_message: 오류 메시지
        """
        state["errors"] = state.get("errors", [])
        state["errors"].append({
            "agent": "question_analyzer",
            "error": error_message,
            "type": "processing_error",
            "timestamp": datetime.now(),
            "context": {"query": state.get("query", "")}
        })
        
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
        print("\n📋 동적 목차 생성 중...")
        
        #llm_lite = get_llm_for_agent("gemini-lite")

        prompt_template = ChatPromptTemplate.from_template(PROMPT_DYNAMIC_TOC).partial(
            query=query,
            recent_issues_summary=recent_issues_summary,
            today_date=datetime.now().strftime("%Y-%m-%d")
        )
        formatted_prompt = prompt_template.format_prompt()
        
        response:AIMessage = await self.agent_llm.ainvoke_with_fallback(
                formatted_prompt,
                project_type=ProjectType.STOCKEASY,
                user_id=user_id,
                db=self.db
            )
        
        # # 구조화된 출력 대신 일반 텍스트 응답으로 받음
        # chain = prompt_template | llm_lite | StrOutputParser()
        
        # # LLM에 요청 보내기
        # response_text = await chain.ainvoke({
        #     "query": query, 
        #     "recent_issues_summary": recent_issues_summary
        # })
        

        response_text = response.content
        print("\n📄 LLM 원본 응답:")
        print(response_text[:200]) # 응답 일부 출력 (디버깅용)
        
        # JSON 문자열을 파싱
        try:
            # JSON 부분 추출 (LLM이 JSON 외에 다른 텍스트를 포함할 수 있음)
            import re
            import json
            
            # JSON 패턴 찾기 (중괄호로 감싸진 부분)
            json_pattern = r'\{(?:[^{}]|(?:\{(?:[^{}]|(?:\{(?:[^{}]|(?:\{[^{}]*\}))*\}))*\}))*\}'
            json_match = re.search(json_pattern, response_text, re.DOTALL)
            
            if json_match:
                json_str = json_match.group(0)
                # JSON 문자열 파싱
                toc_data = json.loads(json_str)
                print("\n✅ JSON 파싱 성공")
            else:
                # JSON 패턴을 찾지 못한 경우
                print("\n⚠️ JSON 패턴을 찾을 수 없음, 기본 목차 구조 사용")
                toc_data = {
                    "title": f"투자 리서치 보고서: {query}",
                    "sections": [
                        {
                            "section_id": "section_1",
                            "title": "핵심 요약 (Executive Summary)",
                            "description": "주요 발견과 결론을 요약",
                            "subsections": []
                        },
                        {
                            "section_id": "section_2", 
                            "title": "기업 개요 및 사업 모델",
                            "description": "기업의 기본 정보와 비즈니스 모델 분석",
                            "subsections": []
                        },
                        {
                            "section_id": "section_3",
                            "title": "산업/시장 동향 분석",
                            "description": "기업이 속한 산업의 현황과 전망",
                            "subsections": []
                        }
                    ],
                    "rationale": "기본 목차 구조 사용"
                }
        except Exception as e:
            print(f"\n⚠️ JSON 파싱 오류: {str(e)}, 기본 목차 구조 사용")
            # 오류 시 기본 목차 구조 사용
            toc_data = {
                "title": f"투자 리서치 보고서: {query}",
                "sections": [
                    {
                        "section_id": "section_1",
                        "title": "핵심 요약 (Executive Summary)",
                        "description": "주요 발견과 결론을 요약",
                        "subsections": []
                    },
                    {
                        "section_id": "section_2", 
                        "title": "기업 개요 및 사업 모델",
                        "description": "기업의 기본 정보와 비즈니스 모델 분석",
                        "subsections": []
                    },
                    {
                        "section_id": "section_3",
                        "title": "산업/시장 동향 분석",
                        "description": "기업이 속한 산업의 현황과 전망",
                        "subsections": []
                    }
                ],
            }
        
        # 파싱된 데이터로 DynamicTocOutput 객체 생성
        result = DynamicTocOutput(
            title=toc_data.get("title", f"투자 리서치 보고서: {query}"),
            sections=toc_data.get("sections", []),
            rationale=toc_data.get("rationale", "")
        )
        
        print(f"\n✅ 동적 목차 생성 완료. 총 {len(result.sections)}개 섹션 포함")
        print(f"📚 보고서 제목: {result.title}")
        
        # 섹션 정보 상세 출력
        print(f"📑 목차 구조:")
        for i, section in enumerate(result.sections, 1):
            # 섹션 제목과 설명 출력
            section_title = section.get('title', '제목 없음')
            section_desc = section.get('description', '')
            print(f"  {section_title}")
            if section_desc:
                print(f"     - {section_desc}")
                
            # 하위 섹션이 있으면 출력
            if 'subsections' in section and section['subsections']:
                for j, subsection in enumerate(section['subsections'], 1):
                    subsection_title = subsection.get('title', '제목 없음')
                    print(f"     {subsection_title}")
        
        return result
    
    async def summarize_recent_issues(self, stock_name: str, stock_code: str, user_id: str) -> str:
        """LLM을 사용하여 검색된 최근 이슈 결과를 요약합니다."""

        search_results = await self.search_recent_issues(stock_name, stock_code) # 최근 이슈 검색

        print(f"\n📝 {stock_name}의 최근 이슈 요약 중...")
        prompt = f"""
    다음은 '{stock_name}'에 대한 최근 주요 뉴스 및 이슈 검색 결과입니다. 이 내용을 바탕으로 주요 뉴스 제목, 핵심 이슈, 반복적으로 언급되는 키워드를 간결하게 요약해주세요. 요약은箇条書き(불릿 포인트) 형식을 사용하고, 가장 중요한 순서대로 정렬해주세요.

    검색 결과:
    {search_results}

    최근 주요 뉴스 및 이슈 검색 결과 키워드 요약:
    """
        try:
            response = await self.agent_llm_lite.ainvoke_with_fallback(
                prompt,
                project_type=ProjectType.STOCKEASY,
                user_id=user_id,
                db=self.db
            )

            summary = response.content
            print(f"  📝 {stock_name} 최근 이슈 요약 완료.")
            #print(f"=== 요약 내용 ===\\n{summary}\\n===========") # 디버깅용
            return summary
        except Exception as e:
            print(f"  ⚠️ {stock_name} 최근 이슈 요약 중 오류: {str(e)}")
            return f"{stock_name} 최근 이슈 요약 중 오류 발생: {str(e)}"
    # --- END: 최근 이슈 검색 및 요약 함수 ---

    async def search_recent_issues(self, stock_name: str, stock_code: str) -> str:
        """Tavily API를 사용하여 특정 종목의 최근 6개월간 주요 뉴스 및 이슈를 검색합니다."""
        print(f"\n🔍 {stock_name}의 최근 주요 이슈 검색 중...")
        query = f"{stock_name} 최근 주요 뉴스 및 핵심 이슈"
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
            
    async def _save_recent_issues_to_json(self, stock_name: str, stock_code: str, 
                                         query: str, search_results: Any) -> None:
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
                json_dir = os.path.join('stockeasy', 'local_cache', 'web_search')
                os.makedirs(json_dir, exist_ok=True)
                
                date_str = datetime.now().strftime('%Y%m%d')
                json_path = os.path.join(json_dir, f'recent_issues_{date_str}.json')
                
                # 현재 날짜와 시간
                current_datetime = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                
                # 저장할 데이터 구성
                entry = {
                    "timestamp": current_datetime,
                    "stock_code": stock_code,
                    "stock_name": stock_name,
                    "query": query,
                    "search_results": search_results
                }
                
                # 파일 존재 여부 확인
                data = []
                if os.path.exists(json_path) and os.path.getsize(json_path) > 0:
                    try:
                        with open(json_path, 'r', encoding='utf-8-sig') as json_file:
                            data = json.load(json_file)
                    except json.JSONDecodeError:
                        # 파일이 손상된 경우 새로 시작
                        data = []
                
                # 데이터 추가
                data.append(entry)
                
                # 파일에 저장
                with open(json_path, 'w', encoding='utf-8-sig') as json_file:
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
            search_results = await self.tavily_service.search_async(query=query, 
                                                search_depth="advanced", # "basic",
                                                #"search_depth": "basic", # "basic",
                                                max_results=14, 
                                                topic="general",
                                                #"topic":"finance",
                                                time_range="year",
                                                )
            
            print(f"검색결과 : {search_results}")
            print(f"검색결과 시간 : {search_results.get('response_time', '0')}")
            print(f"검색결과 응답 : {search_results.get('answer', 'None')}")
            formatted_results = "검색 결과:\n\n"
            for i, result_item in enumerate(search_results.get('results', []), 1):
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
            print(search_results)
            return f"검색 중 오류가 발생했습니다: {str(e)}"
        
