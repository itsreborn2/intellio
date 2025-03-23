"""
폴백 매니저 에이전트 모듈

이 모듈은 오류 상황이나 응답 생성 실패 시 사용자에게 
적절한 대체 응답을 제공하는 폴백 매니저 에이전트 클래스를 구현합니다.
"""

import json
from loguru import logger
from typing import Dict, List, Any, Optional

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage
from langchain_core.prompts import ChatPromptTemplate
from stockeasy.prompts.fallback_manager_prompts import format_fallback_manager_prompt
from common.core.config import settings
from common.services.agent_llm import get_llm_for_agent

class FallbackManagerAgent:
    """
    오류 상황이나 응답 생성 실패 시 대체 응답을 제공하는 폴백 매니저 에이전트 클래스
    """
    
    def __init__(self):
        """
        폴백 매니저 에이전트 초기화
        
        Args:
            model_name: 사용할 OpenAI 모델 이름
            temperature: 모델 출력의 다양성 조절 파라미터
        """
        #self.llm = ChatOpenAI(model_name=model_name, temperature=temperature, api_key=settings.OPENAI_API_KEY)
        self.llm, self.model_name, self.provider = get_llm_for_agent("fallback_manager_agent")
        logger.info(f"FallbackManagerAgent initialized with provider: {self.provider}, model: {self.model_name}")
        
    async def process(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        오류 상황이나 응답 생성 실패 시 대체 응답을 생성합니다.
        
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
            
            # 오류 정보 추출
            error = state.get("error", "")
            
            logger.info(f"FallbackManagerAgent handling error: {error}")
            
            # 상황 및 오류 설명 결정
            situation = "요청한 정보를 처리하는 중 문제가 발생했습니다."
            error_description = error if error else "알 수 없는 오류가 발생했습니다."
            
            # 일반적인 오류 유형 분석 및 상황 설명 개선
            if "파싱 실패" in error or "JSONDecodeError" in error:
                situation = "응답 형식을 처리하는 과정에서 문제가 발생했습니다."
                error_description = "데이터 형식을 해석하는 데 어려움이 있습니다."
            elif "시간 초과" in error or "timeout" in error.lower():
                situation = "요청 처리 시간이 너무 오래 걸려 시간 초과가 발생했습니다."
                error_description = "서버 응답 시간이 지연되고 있습니다."
            elif "검색 결과 없음" in error or "no results" in error.lower():
                situation = "요청하신 정보에 대한 검색 결과를 찾을 수 없습니다."
                error_description = "데이터베이스에서 관련 정보를 찾지 못했습니다."
            elif "API" in error or "외부 서비스" in error:
                situation = "외부 데이터 소스와 통신하는 과정에서 문제가 발생했습니다."
                error_description = "외부 서비스 연결에 일시적인 문제가 있습니다."
            
            # 종목 관련 오류인 경우 추가 정보 제공
            if stock_name or stock_code:
                if "찾을 수 없음" in error or "not found" in error.lower():
                    if stock_name:
                        situation = f"'{stock_name}' 종목에 대한 정보를 찾는 과정에서 문제가 발생했습니다."
                        error_description = f"'{stock_name}' 종목에 대한 데이터를 찾을 수 없거나 불충분합니다."
                    elif stock_code:
                        situation = f"'{stock_code}' 코드의 종목에 대한 정보를 찾는 과정에서 문제가 발생했습니다."
                        error_description = f"'{stock_code}' 코드의 종목에 대한 데이터를 찾을 수 없거나 불충분합니다."
            
            # 프롬프트 준비
            prompt = format_fallback_manager_prompt(
                query=query,
                stock_name=stock_name,
                stock_code=stock_code,
                situation=situation,
                error_description=error_description
            )
            
            # LLM 호출로 폴백 응답 생성
            response = await self.llm.ainvoke([HumanMessage(content=prompt)])
            fallback_response = response.content
            
            logger.info("Fallback response generated successfully")
            
            # 폴백 응답 저장
            state["fallback_response"] = fallback_response
            state["final_response"] = fallback_response  # 최종 응답으로 설정
            
            return state
            
        except Exception as e:
            logger.exception(f"Error in FallbackManagerAgent: {str(e)}")
            # 심각한 오류 발생 시 하드코딩된 기본 응답 제공
            state["fallback_response"] = "죄송합니다. 요청을 처리하는 중에 기술적인 문제가 발생했습니다. 잠시 후 다시 시도해 주시기 바랍니다."
            state["final_response"] = state["fallback_response"]
            return state 