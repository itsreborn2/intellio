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
from common.models.token_usage import ProjectType
from stockeasy.agents.base import BaseAgent
from sqlalchemy.ext.asyncio import AsyncSession

class FallbackManagerAgent(BaseAgent):
    """
    오류 발생 시 폴백 응답을 생성하는 에이전트
    
    이 에이전트는 워크플로우 실행 중 오류가 발생했을 때
    사용자에게 적절한 안내 메시지를 제공합니다.
    """
    
    def __init__(self, name: Optional[str] = None, db: Optional[AsyncSession] = None):
        """
        폴백 매니저 에이전트 초기화
        
        Args:
            name: 에이전트 이름 (지정하지 않으면 클래스명 사용)
            db: 데이터베이스 세션 객체 (선택적)
        """
        super().__init__(name, db)
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
            errors = state.get("errors", [])
            if errors and not error:
                error = " | ".join([e.get("error", "") for e in errors if "error" in e])
            
            logger.info(f"FallbackManagerAgent handling error: {error}")
            
            # LangSmith 타임스탬프 오류 확인
            is_langsmith_timestamp_error = False
            if "invalid 'dotted_order'" in error and "earlier than parent timestamp" in error:
                logger.warning("LangSmith 타임스탬프 오류 감지됨: 상태를 재설정하고 다시 시작합니다.")
                is_langsmith_timestamp_error = True
                
                # 상태를 재설정하여 그래프를 다시 시작할 수 있게 함
                clean_state = {
                    "query": query,
                    "stock_code": stock_code,
                    "stock_name": stock_name,
                    "session_id": state.get("session_id", ""),
                    "restart_from_error": True,
                    "previous_error": error,
                    "errors": [],  # 오류 목록 초기화
                    "processing_status": {},  # 처리 상태 초기화
                    "retrieved_data": {},  # 검색 결과 초기화
                    "agent_results": {},  # 에이전트 결과 초기화
                }
                
                # 중요: 쿼리 타입을 유지
                if "query_type" in state:
                    clean_state["query_type"] = state["query_type"]
                
                # 사용자 정보 유지
                if "user_id" in state:
                    clean_state["user_id"] = state["user_id"]
                
                logger.info("상태가 재설정되었습니다. 그래프가 처음부터 다시 시작합니다.")
                return clean_state
            
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