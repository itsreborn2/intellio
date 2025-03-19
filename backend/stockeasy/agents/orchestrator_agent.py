"""
오케스트레이터 에이전트 모듈

이 모듈은 질문 분석 결과를 바탕으로 전체 워크플로우를 설계하고,
데이터 검색 및 통합 과정을 조율하는 OrchestratorAgent 클래스를 구현합니다.
"""

import json
import uuid
from loguru import logger
from typing import Dict, List, Any, Optional, Literal
from datetime import datetime

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage
from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel, Field
from common.services.agent_llm import get_llm_for_agent
from stockeasy.models.agent_io import QuestionAnalysisResult
from stockeasy.prompts.orchestrator_prompts import format_orchestrator_prompt
from common.core.config import settings


class AgentConfigModel(BaseModel):
    """에이전트 실행 설정"""
    agent_name: str = Field(..., description="에이전트 이름")
    enabled: bool = Field(..., description="활성화 여부")
    priority: int = Field(..., description="우선순위 (1-10)")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="에이전트별 매개변수")


class ExecutionPlanModel(BaseModel):
    """실행 계획"""
    agents: List[AgentConfigModel] = Field(..., description="실행할 에이전트 목록")
    execution_order: List[str] = Field(..., description="실행 순서")
    integration_strategy: str = Field(..., description="정보 통합 전략")
    expected_output: str = Field(..., description="예상 출력물")
    fallback_strategy: str = Field(..., description="실패 시 대응 전략")


class OrchestratorAgent:
    """
    워크플로우 설계 및 조율을 담당하는 오케스트레이터 에이전트
    
    이 에이전트는 질문분류기의 결과를 바탕으로 다음을 수행합니다:
    1. 필요한 에이전트 목록 결정
    2. 에이전트 실행 순서 및 우선순위 설정
    3. 데이터 통합 전략 수립
    4. 예외 상황 대응 계획 마련
    """
    
    def __init__(self):
        """
        오케스트레이터 에이전트 초기화
        
        Args:
            model_name: 사용할 OpenAI 모델 이름
            temperature: 모델 출력의 다양성 조절 파라미터
        """
        # self.llm = ChatOpenAI(
        #     model_name=model_name, 
        #     temperature=temperature, 
        #     api_key=settings.OPENAI_API_KEY
        # )
        self.llm, self.model_name, self.provider = get_llm_for_agent("orchestrator_agent")
        #self.model_name = model_name
        logger.info(f"OrchestratorAgent initialized with provider: {self.provider}, model: {self.model_name}")
        
        # 사용 가능한 에이전트 목록
        self.available_agents = {
            "telegram_retriever": "텔레그램 메시지 검색 에이전트",
            "report_analyzer": "기업 리포트 검색 및 분석 에이전트",
            "financial_analyzer": "재무제표 분석 에이전트",
            "industry_analyzer": "산업 동향 분석 에이전트",
            "knowledge_integrator": "정보 통합 에이전트",
            "summarizer": "요약 에이전트",
            "response_formatter": "응답 형식화 에이전트",
            "fallback_manager": "오류 처리 에이전트"
        }
    
    async def process(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        질문 분석 결과를 바탕으로 워크플로우를 설계합니다.
        
        Args:
            state: 현재 상태 정보를 포함하는 딕셔너리
            
        Returns:
            업데이트된 상태 딕셔너리
        """
        try:
            # 성능 측정 시작
            start_time = datetime.now()
            logger.info(f"OrchestratorAgent starting processing")
            
            # 질문 분석 결과 추출
            query = state.get("query", "")
            question_analysis:QuestionAnalysisResult = state.get("question_analysis", {})
            
            if not question_analysis:
                logger.warning("Question analysis not found in state")
                self._add_error(state, "질문 분석 결과가 없습니다.")
                return self._create_default_plan(state)
            
            # 필요한 정보 추출
            entities = question_analysis.get("entities", {})
            classification = question_analysis.get("classification", {})
            data_requirements =question_analysis.get("data_requirements", {})
            keywords = question_analysis.get("keywords", [])
            detail_level = question_analysis.get("detail_level", "보통")
            
            # 로깅
            logger.info(f"OrchestratorAgent processing query: {query}")
            logger.info(f"Classification: {classification}")
            logger.info(f"Data requirements: {data_requirements}")
            
            # 프롬프트 준비 (새로운 프롬프트 포맷 필요)
            prompt = format_orchestrator_prompt(
                query=query,
                question_analysis=question_analysis,
                available_agents=self.available_agents
            )
            
            # LLM 호출로 계획 수립
            #execution_plan = await self.llm.with_structured_output(ExecutionPlanModel,method="function_calling").ainvoke(
            execution_plan = await self.llm.with_structured_output(ExecutionPlanModel).ainvoke(
                [HumanMessage(content=prompt)]
            )
            
            # 실행 계획 로깅
            logger.info(f"Execution plan created: {execution_plan.dict()}")
            
            # 최종 실행 계획 구성
            plan_id = str(uuid.uuid4())
            final_plan = {
                "plan_id": plan_id,
                "created_at": datetime.now(),
                "agents": [agent.dict() for agent in execution_plan.agents],
                "execution_order": execution_plan.execution_order,
                "integration_strategy": execution_plan.integration_strategy,
                "expected_output": execution_plan.expected_output,
                "fallback_strategy": execution_plan.fallback_strategy
            }
            
            # 상태 업데이트
            state["execution_plan"] = final_plan
            
            # 성능 지표 업데이트
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            # 메트릭 기록
            state["metrics"] = state.get("metrics", {})
            state["metrics"]["orchestrator"] = {
                "start_time": start_time,
                "end_time": end_time,
                "duration": duration,
                "status": "completed",
                "error": None,
                "model_name": self.model_name
            }
            
            # 처리 상태 업데이트
            state["processing_status"] = state.get("processing_status", {})
            state["processing_status"]["orchestrator"] = "completed"
            
            logger.info(f"OrchestratorAgent completed in {duration:.2f} seconds")
            return state
            
        except Exception as e:
            logger.exception(f"Error in OrchestratorAgent: {str(e)}")
            self._add_error(state, f"오케스트레이터 에이전트 오류: {str(e)}")
            return self._create_default_plan(state)
    
    def _create_default_plan(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        기본 실행 계획을 생성합니다 (오류 발생 시 fallback).
        
        Args:
            state: 현재 상태
            
        Returns:
            기본 계획이 추가된 상태
        """
        logger.info("Creating default execution plan")
        
        # 기본 계획 생성
        default_plan = {
            "plan_id": str(uuid.uuid4()),
            "created_at": datetime.now(),
            "agents": [
                {
                    "agent_name": "telegram_retriever",
                    "enabled": True,
                    "priority": 10,
                    "parameters": {}
                },
                {
                    "agent_name": "knowledge_integrator",
                    "enabled": True,
                    "priority": 5,
                    "parameters": {}
                },
                {
                    "agent_name": "response_formatter",
                    "enabled": True,
                    "priority": 1,
                    "parameters": {}
                }
            ],
            "execution_order": ["telegram_retriever", "knowledge_integrator", "response_formatter"],
            "integration_strategy": "텔레그램 메시지를 기반으로 간단한 요약 생성",
            "expected_output": "기본적인 질문 답변",
            "fallback_strategy": "질문에 답변할 수 없는 경우 솔직하게 답변 불가 안내"
        }
        
        # 상태 업데이트
        state["execution_plan"] = default_plan
        
        # 처리 상태 업데이트
        state["processing_status"] = state.get("processing_status", {})
        state["processing_status"]["orchestrator"] = "completed_with_default_plan"
        
        return state
    
    def _add_error(self, state: Dict[str, Any], error_message: str) -> None:
        """
        상태 객체에 오류 정보를 추가합니다.
        
        Args:
            state: 상태 객체
            error_message: 오류 메시지
        """
        state["errors"] = state.get("errors", [])
        state["errors"].append({
            "agent": "orchestrator",
            "error": error_message,
            "type": "processing_error",
            "timestamp": datetime.now(),
            "context": {
                "query": state.get("query", ""),
                "question_analysis": state.get("question_analysis", {})
            }
        }) 