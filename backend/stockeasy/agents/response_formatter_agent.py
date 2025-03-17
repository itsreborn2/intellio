"""
응답 포맷터 에이전트 모듈

이 모듈은 통합된 지식 정보를 사용자에게 이해하기 쉬운 
형태로 포맷팅하는 응답 포맷터 에이전트 클래스를 구현합니다.
"""

import json
from loguru import logger
from typing import Dict, List, Any, Optional

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage
from langchain_core.prompts import ChatPromptTemplate
from stockeasy.prompts.response_formatter_prompts import format_response_formatter_prompt
from common.core.config import settings

class ResponseFormatterAgent:
    """
    통합된 정보를 사용자에게 이해하기 쉬운 형태로 포맷팅하는 응답 포맷터 에이전트 클래스
    """
    
    def __init__(self, model_name: str = "gpt-4o", temperature: float = 0.2):
        """
        응답 포맷터 에이전트 초기화
        
        Args:
            model_name: 사용할 OpenAI 모델 이름
            temperature: 모델 출력의 다양성 조절 파라미터
        """
        self.llm = ChatOpenAI(model_name=model_name, temperature=temperature, api_key=settings.OPENAI_API_KEY)
        logger.info(f"ResponseFormatterAgent initialized with model: {model_name}")
        
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
            integrated_response = state.get("integrated_response", "")
            core_insights = state.get("core_insights", {})
            confidence_assessment = state.get("confidence_assessment", {})
            uncertain_areas = state.get("uncertain_areas", [])
            
            logger.info(f"ResponseFormatterAgent formatting response for query: {query}")
            
            # 통합된 응답이 없는 경우 처리
            if not integrated_response or integrated_response == "응답을 생성할 수 없습니다.":
                logger.warning("No integrated response available")
                state["formatted_response"] = "죄송합니다. 현재 요청에 대한 정보를 찾을 수 없습니다. 다른 질문을 해 주시거나 나중에 다시 시도해 주세요."
                return state
            
            # 프롬프트 준비
            prompt = format_response_formatter_prompt(
                query=query,
                stock_name=stock_name,
                stock_code=stock_code,
                integrated_response=integrated_response,
                core_insights=core_insights,
                confidence_assessment=confidence_assessment,
                uncertain_areas=uncertain_areas
            )
            
            # LLM 호출로 포맷팅 수행
            response = await self.llm.ainvoke([HumanMessage(content=prompt)])
            formatted_response = response.content
            
            logger.info("Response formatting completed successfully")
            
            # 포맷팅된 응답 저장
            state["formatted_response"] = formatted_response
            
            # 오류 제거 (성공적으로 처리됨)
            if "error" in state:
                del state["error"]
                
            return state
            
        except Exception as e:
            logger.exception(f"Error in ResponseFormatterAgent: {str(e)}")
            state["error"] = f"응답 포맷터 에이전트 오류: {str(e)}"
            state["formatted_response"] = "죄송합니다. 응답을 포맷팅하는 중 오류가 발생했습니다."
            return state 