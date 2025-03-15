"""
오케스트레이터 에이전트 모듈

이 모듈은 사용자 질문을 분석하고 질문의 특성에 따라 
필요한 에이전트를 결정하는 오케스트레이터 에이전트 클래스를 구현합니다.
"""

import json
from loguru import logger
from typing import Dict, List, Any, Optional

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from backend.stockeasy.prompts.orchestrator_prompts import format_orchestrator_prompt

class OrchestratorAgent:
    """
    사용자 질문을 분석하고 필요한 에이전트를 결정하는 오케스트레이터 에이전트 클래스
    """
    
    def __init__(self, model_name: str = "gpt-4o", temperature: float = 0):
        """
        오케스트레이터 에이전트 초기화
        
        Args:
            model_name: 사용할 OpenAI 모델 이름
            temperature: 모델 출력의 다양성 조절 파라미터
        """
        self.llm = ChatOpenAI(model_name=model_name, temperature=temperature)
        self.output_parser = JsonOutputParser()
        logger.info(f"OrchestratorAgent initialized with model: {model_name}")
        
    async def process(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        상태 정보를 처리하고 필요한 에이전트를 결정합니다.
        
        Args:
            state: 현재 상태 정보를 포함하는 딕셔너리
            
        Returns:
            업데이트된 상태 딕셔너리
        """
        try:
            # 현재 사용자 쿼리 및 세션 정보 추출
            query = state.get("current_query", "")
            stock_code = state.get("stock_code")
            stock_name = state.get("stock_name")
            
            # 성능 측정 시작
            logger.info(f"OrchestratorAgent processing query: {query}")
            
            # 프롬프트 준비
            prompt = format_orchestrator_prompt(
                query=query,
                stock_code=stock_code,
                stock_name=stock_name
            )
            
            # LLM 호출로 분석 수행
            response = await self.llm.ainvoke([HumanMessage(content=prompt)])
            content = response.content
            
            # JSON 응답 파싱
            try:
                if "```json" in content:
                    # JSON 코드 블록 추출
                    json_content = content.split("```json")[1].split("```")[0].strip()
                    orchestration_result = json.loads(json_content)
                else:
                    # 일반 JSON 파싱 시도
                    orchestration_result = json.loads(content)
                    
                logger.info(f"Orchestration result: {orchestration_result}")
                
                # 필요한 에이전트 목록 업데이트
                needed_agents = orchestration_result.get("needed_agents", [])
                
                # 에이전트가 지정되지 않은 경우 기본값 설정
                if not needed_agents:
                    logger.warning("No agents specified, using default agents")
                    needed_agents = ["telegram_retriever"]
                
                # 분류 및 추출된 엔티티 가져오기
                classification = orchestration_result.get("classification", {})
                extracted_entities = orchestration_result.get("extracted_entities", {})
                data_importance = orchestration_result.get("data_importance", {})
                
                # 상태 업데이트
                state["needed_agents"] = needed_agents
                state["question_classification"] = classification
                state["extracted_entities"] = extracted_entities
                state["data_importance"] = data_importance
                state["integration_strategy"] = orchestration_result.get("integration_strategy", "")
                
                # 추출된 엔티티 상태 업데이트
                if not state.get("stock_code") and extracted_entities.get("stock_code"):
                    state["stock_code"] = extracted_entities.get("stock_code")
                    
                if not state.get("stock_name") and extracted_entities.get("stock_name"):
                    state["stock_name"] = extracted_entities.get("stock_name")
                    
                state["sector"] = extracted_entities.get("sector", state.get("sector"))
                state["time_range"] = extracted_entities.get("time_range", state.get("time_range"))
                
                logger.info(f"OrchestratorAgent determined needed agents: {needed_agents}")
                
            except json.JSONDecodeError:
                logger.error(f"Failed to parse orchestration result JSON: {content}")
                state["needed_agents"] = ["telegram_retriever"]  # 기본값
                state["error"] = "오케스트레이션 결과 파싱 실패"
                
            return state
            
        except Exception as e:
            logger.exception(f"Error in OrchestratorAgent: {str(e)}")
            state["error"] = f"오케스트레이터 에이전트 오류: {str(e)}"
            state["needed_agents"] = ["telegram_retriever"]  # 기본값
            return state 