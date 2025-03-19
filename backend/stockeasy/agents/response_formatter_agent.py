"""
응답 포맷터 에이전트 모듈

이 모듈은 통합된 지식 정보를 사용자에게 이해하기 쉬운 
형태로 포맷팅하는 응답 포맷터 에이전트 클래스를 구현합니다.
"""

import json
from loguru import logger
from typing import Dict, Any

from langchain_core.messages import HumanMessage, AIMessage
from common.services.agent_llm import get_llm_for_agent
from stockeasy.prompts.response_formatter_prompts import format_response_formatter_prompt
from langchain_core.output_parsers import StrOutputParser

class ResponseFormatterAgent:
    """
    통합된 정보를 사용자에게 이해하기 쉬운 형태로 포맷팅하는 응답 포맷터 에이전트 클래스
    """
    
    def __init__(self):
        """
        응답 포맷터 에이전트 초기화
        
        Args:
            model_name: 사용할 OpenAI 모델 이름
            temperature: 모델 출력의 다양성 조절 파라미터
        """
        #self.llm = ChatOpenAI(model_name=model_name, temperature=temperature, api_key=settings.OPENAI_API_KEY)
        self.llm, self.model_name, self.provider = get_llm_for_agent("response_formatter_agent")
        logger.info(f"ResponseFormatterAgent initialized with provider: {self.provider}, model: {self.model_name}")
        self.parser = StrOutputParser()

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
            
            # 프롬프트 준비
            prompt_context = format_response_formatter_prompt(
                query=query,
                stock_name=stock_name,
                stock_code=stock_code,
                integrated_response=summary,
                core_insights=core_insights,
                confidence_assessment=confidence_assessment,
                uncertain_areas=uncertain_areas
            )
            # prompt = ChatPromptTemplate.from_template(prompt_context)
            
            # # LLM 호출로 포맷팅 수행
            # chain = prompt | self.llm | self.parser
            # response = await chain.ainvoke({})  
            response:AIMessage = await self.llm.ainvoke([HumanMessage(content=prompt_context)])
            formatted_response = response.content
            
            logger.info("Response formatting completed successfully")
            
            # 포맷팅된 응답 저장
            state["formatted_response"] = formatted_response
            
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
            return state 