"""
응답 포맷터 에이전트 모듈

이 모듈은 통합된 지식 정보를 사용자에게 이해하기 쉬운 
형태로 포맷팅하는 응답 포맷터 에이전트 클래스를 구현합니다.
"""

import json
from loguru import logger
from typing import Dict, Any, Optional

from langchain_core.messages import HumanMessage, AIMessage
from common.services.agent_llm import get_agent_llm, get_llm_for_agent
from stockeasy.prompts.response_formatter_prompts import FRIENDLY_RESPONSE_FORMATTER_SYSTEM_PROMPT, OPTIMIZED_RESPONSE_FORMATTER_SYSTEM_PROMPT, format_response_formatter_prompt
from langchain_core.output_parsers import StrOutputParser
from common.models.token_usage import ProjectType
from stockeasy.agents.base import BaseAgent
from sqlalchemy.ext.asyncio import AsyncSession

class ResponseFormatterAgent(BaseAgent):
    """
    최종 응답을 형식화하는 에이전트
    
    이 에이전트는 knowledge_integrator 또는 summarizer의 결과를 받아
    사용자 친화적인 형태로 가공합니다.
    """
    
    def __init__(self, name: Optional[str] = None, db: Optional[AsyncSession] = None):
        """
        응답 형식화 에이전트 초기화
        
        Args:
            name: 에이전트 이름 (지정하지 않으면 클래스명 사용)
            db: 데이터베이스 세션 객체 (선택적)
        """
        super().__init__(name, db)
        #self.llm, self.model_name, self.provider = get_llm_for_agent("response_formatter_agent")
        self.agent_llm = get_agent_llm("response_formatter_agent")
        logger.info(f"ResponseFormatterAgent initialized with provider: {self.agent_llm.get_provider()}, model: {self.agent_llm.get_model_name()}")
        self.parser = StrOutputParser()
        self.prompt_template = FRIENDLY_RESPONSE_FORMATTER_SYSTEM_PROMPT

    async def process(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        통합된 정보를 기반으로 사용자에게 이해하기 쉬운 응답을 생성합니다.
        
        Args:
            state: 현재 상태 정보를 포함하는 딕셔너리
            
        Returns:
            업데이트된 상태 딕셔너리
        """
        try:
            # 현재 사용자 쿼리 및 종목 정보 추출
            query = state.get("query", "")
            stock_code = state.get("stock_code")
            stock_name = state.get("stock_name")
            
            # 통합된 응답 및 인사이트 추출
            integrated_knowledge = state.get("integrated_knowledge", {})
            
            integrated_response = integrated_knowledge.get("integrated_response", state.get("integrated_response", ""))
            core_insights = integrated_knowledge.get("core_insights", [])
            
            analysis = integrated_knowledge.get("analysis", {})
            confidence_assessment = analysis.get("confidence_assessment", {})
            uncertain_areas = analysis.get("uncertain_areas", [])
            
            logger.info(f"ResponseFormatterAgent formatting response for query: {query}")
            
            summary = state.get("summary", "")
            processing_status = state.get("processing_status", {})
            summarizer_status = processing_status.get("summarizer", "not_started")
            # 통합된 응답이 없는 경우 처리
            if not summary or summarizer_status != "completed":
                logger.warning(f"No summary response available.")
                logger.warning(f"processing_status: {processing_status}")
                logger.warning(f"Summarizer status: {summarizer_status}")
                state["formatted_response"] = "죄송합니다. 현재 요청에 대한 정보를 찾을 수 없습니다. 다른 질문을 해 주시거나 나중에 다시 시도해 주세요."
                return state
            
            # 1. 상태에서 커스텀 프롬프트 템플릿 확인
            custom_prompt_from_state = state.get("custom_prompt_template")
            # 2. 속성에서 커스텀 프롬프트 템플릿 확인 
            custom_prompt_from_attr = getattr(self, "prompt_template_test", None)
            # 커스텀 프롬프트 사용 우선순위: 상태 > 속성 > 기본값
            system_prompt = None
            if custom_prompt_from_state:
                system_prompt = custom_prompt_from_state
                logger.info(f"ResponseFormatterAgent using custom prompt from state : {custom_prompt_from_state}")
            elif custom_prompt_from_attr:
                system_prompt = custom_prompt_from_attr
                logger.info(f"ResponseFormatterAgent using custom prompt from attribute")

            # 프롬프트 준비
            prompt = format_response_formatter_prompt(
                query=query,
                stock_name=stock_name,
                stock_code=stock_code,
                integrated_response=summary,
                core_insights=core_insights,
                confidence_assessment=confidence_assessment,
                uncertain_areas=uncertain_areas,
                system_prompt=system_prompt
            )
            
            # # LLM 호출로 포맷팅 수행
            user_context = state.get("user_context", {})
            user_id = user_context.get("user_id", None)
            response:AIMessage = await self.agent_llm.ainvoke_with_fallback(
                input=prompt.format_prompt(),
                user_id=user_id,
                project_type=ProjectType.STOCKEASY,
                db=self.db
            )
            formatted_response = response.content
            
            logger.info("Response formatting completed successfully")
            
            # 포맷팅된 응답 저장
            state["formatted_response"] = formatted_response
            state["answer"] = formatted_response
            
            # 오류 제거 (성공적으로 처리됨)
            if "error" in state:
                del state["error"]
                
            # 처리 상태 업데이트
            state["processing_status"] = state.get("processing_status", {})
            state["processing_status"]["response_formatter"] = "completed"
                
            return state
            
        except Exception as e:
            logger.exception(f"Error in ResponseFormatterAgent: {str(e)}")
            state["error"] = f"응답 포맷터 에이전트 오류: {str(e)}"
            state["formatted_response"] = "죄송합니다. 응답을 포맷팅하는 중 오류가 발생했습니다."
            state["answer"] = state["formatted_response"]
            return state 