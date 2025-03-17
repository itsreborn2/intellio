"""
주식 분석 워크플로우 그래프 정의

이 모듈은 LangGraph를 사용하여 주식 분석 에이전트들의 워크플로우를 정의합니다.
"""

import os
from typing import Dict, Any, List, Literal, Union, Optional, TypedDict, Tuple, Set, cast
from langchain_core.runnables import ConfigurableField
import langgraph.graph as lg
from langgraph.graph import END, StateGraph
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import BaseMessage, HumanMessage
from datetime import datetime
from loguru import logger
from langchain.callbacks.tracers import LangChainTracer

from stockeasy.models.agent_io import AgentState
from stockeasy.agents.base import BaseAgent
from stockeasy.agents.session_manager import SessionManagerAgent
from common.services.user import UserService
from common.schemas.user import SessionBase
from sqlalchemy.ext.asyncio import AsyncSession

# LangSmith 트레이서 초기화
os.environ["LANGCHAIN_TRACING"] = "true"
os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_PROJECT"] = "stockeasy_multiagent"
tracer = LangChainTracer(project_name="stockeasy_multiagent")

def should_use_telegram(state: AgentState) -> bool:
    """텔레그램 검색 에이전트를 사용해야 하는지 결정합니다."""
    # 기존 오케스트레이터 분류 우선 확인
    classification = state.get("classification", {})
    question_type = classification.get("질문주제", 4)  # 기본값: 기타
    
    # 새로운 question_analyzer의 분류 확인
    data_requirements = state.get("data_requirements", {})
    telegram_needed = data_requirements.get("telegram_needed", True)
    
    # question_analyzer 결과가 있으면 우선 적용, 없으면 오케스트레이터 결과 사용
    if "data_requirements" in state:
        return telegram_needed
    
    # 기존 로직 (fallback)
    return True

def should_use_report(state: AgentState) -> bool:
    """기업 리포트 검색 에이전트를 사용해야 하는지 결정합니다."""
    # 기존 오케스트레이터 분류 우선 확인
    classification = state.get("classification", {})
    question_type = classification.get("질문주제", 4)  # 기본값: 기타
    
    # 새로운 question_analyzer의 분류 확인
    data_requirements = state.get("data_requirements", {})
    reports_needed = data_requirements.get("reports_needed", True)
    
    # question_analyzer 결과가 있으면 우선 적용, 없으면 오케스트레이터 결과 사용
    if "data_requirements" in state:
        return reports_needed
    
    # 기존 로직 (fallback)
    return question_type in [0, 1, 4]

def should_use_financial(state: AgentState) -> bool:
    """재무제표 분석 에이전트를 사용해야 하는지 결정합니다."""
    # 기존 오케스트레이터 분류 우선 확인
    classification = state.get("classification", {})
    question_type = classification.get("질문주제", 4)  # 기본값: 기타
    
    # 새로운 question_analyzer의 분류 확인
    data_requirements = state.get("data_requirements", {})
    financial_statements_needed = data_requirements.get("financial_statements_needed", False)
    
    # question_analyzer 결과가 있으면 우선 적용, 없으면 오케스트레이터 결과 사용
    if "data_requirements" in state:
        return financial_statements_needed
    
    # 기존 로직 (fallback)
    return question_type in [2, 4]

def should_use_industry(state: AgentState) -> bool:
    """산업 분석 에이전트를 사용해야 하는지 결정합니다."""
    # 기존 오케스트레이터 분류 우선 확인
    classification = state.get("classification", {})
    question_type = classification.get("질문주제", 4)  # 기본값: 기타
    
    # 새로운 question_analyzer의 분류 확인
    data_requirements = state.get("data_requirements", {})
    industry_data_needed = data_requirements.get("industry_data_needed", False)
    
    # question_analyzer 결과가 있으면 우선 적용, 없으면 오케스트레이터 결과 사용
    if "data_requirements" in state:
        return industry_data_needed
    
    # 기존 로직 (fallback)
    return question_type in [1, 3, 4]

def should_fallback_early(state: AgentState) -> str:
    """
    조기에 폴백 관리자로 라우팅해야 하는지 확인합니다.
    
    Args:
        state: 현재 에이전트 상태
    
    Returns:
        다음 에이전트 이름
    """
    # 질문 분석 자체가 실패한 경우
    errors = state.get("errors", [])
    if errors and any(e.get("agent") == "question_analyzer" for e in errors):
        return "fallback_manager"
    
    # 그렇지 않으면 정상 진행
    return "telegram_retriever"  # 첫 번째 검색 에이전트로 진행

def has_insufficient_data(state: AgentState) -> str:
    """
    충분한 데이터가 검색되었는지 확인합니다.
    
    Args:
        state: 현재 에이전트 상태
    
    Returns:
        다음 에이전트 이름
    """
    # 검색된 데이터가 없는 경우 Fallback
    retrieved_data = state.get("retrieved_data", {})
    telegram_messages = retrieved_data.get("telegram_messages", [])
    report_data = retrieved_data.get("report_data", [])
    financial_data = retrieved_data.get("financial_data", [])
    industry_data = retrieved_data.get("industry_data", [])
    
    # 모든 소스에서 데이터를 찾지 못한 경우
    if not telegram_messages and not report_data and not financial_data and not industry_data:
        return "fallback_manager"
    else:
        return "summarizer"

class StockAnalysisGraph:
    """주식 분석 워크플로우 그래프 클래스"""
    
    def __init__(self, agents: Dict[str, BaseAgent] = None):
        """
        그래프 초기화
        
        Args:
            agents: 에이전트 이름과 인스턴스의 딕셔너리
        """
        self.agents = agents or {}
        # 그래프 초기화는 register_agents에서 수행
        self.graph = None
        # 메모리 저장소 초기화
        self.memory_saver = MemorySaver()
    
    def _build_graph(self, db: AsyncSession = None):
        """
        주식 분석 워크플로우 그래프를 구축합니다.
        
        Args:
            db: 데이터베이스 세션 (세션 관리자 에이전트 초기화용)
            
        Returns:
            컴파일된 그래프
        """
        # 세션 관리자 에이전트 준비
        if "session_manager" not in self.agents and db:
            self.agents["session_manager"] = SessionManagerAgent(db)
        
        # 그래프 초기화
        workflow = StateGraph(AgentState)
        
        # 노드 추가 - 에이전트 함수 직접 설정
        for node_name, agent in self.agents.items():
            # 존재하는 에이전트만 추가
            if agent:
                workflow.add_node(node_name, agent.process)
            else:
                workflow.add_node(node_name, {})  # 빈 노드
        
        # 새로운 흐름 정의: 질문분류기 -> 오케스트레이터 -> 동적 워크플로우
        workflow.add_edge("session_manager", "question_analyzer")
        workflow.add_edge("question_analyzer", "orchestrator")
        
        # 오케스트레이터 이후의 흐름은 동적으로 결정
        workflow.add_conditional_edges(
            "orchestrator",
            self._determine_next_agent,
            {
                "telegram_retriever": "telegram_retriever",
                "report_analyzer": "report_analyzer",
                "financial_analyzer": "financial_analyzer",
                "industry_analyzer": "industry_analyzer",
                "knowledge_integrator": "knowledge_integrator",
                "summarizer": "summarizer",
                "response_formatter": "response_formatter",
                "fallback_manager": "fallback_manager",
                END: END
            }
        )
        
        # 각 검색 에이전트 이후의 다음 에이전트 결정
        for agent_name in ["telegram_retriever", "report_analyzer", "financial_analyzer", "industry_analyzer"]:
            workflow.add_conditional_edges(
                agent_name,
                self._determine_next_agent,
                {
                    "telegram_retriever": "telegram_retriever",
                    "report_analyzer": "report_analyzer",
                    "financial_analyzer": "financial_analyzer",
                    "industry_analyzer": "industry_analyzer",
                    "knowledge_integrator": "knowledge_integrator",
                    "summarizer": "summarizer",
                    "response_formatter": "response_formatter",
                    "fallback_manager": "fallback_manager",
                    END: END
                }
            )
        
        # 통합 및 요약 에이전트 이후의 흐름
        workflow.add_conditional_edges(
            "knowledge_integrator",
            self._determine_next_agent,
            {
                "summarizer": "summarizer",
                "response_formatter": "response_formatter",
                END: END
            }
        )
        
        workflow.add_conditional_edges(
            "summarizer",
            self._determine_next_agent,
            {
                "response_formatter": "response_formatter",
                END: END
            }
        )
        
        # fallback_manager와 response_formatter는 항상 종료
        workflow.add_edge("fallback_manager", "response_formatter")
        workflow.add_edge("response_formatter", END)
        
        # 시작점 설정
        workflow.set_entry_point("session_manager")
        
        # 그래프 컴파일 (체크포인트 저장소 설정)
        return workflow.compile(checkpointer=self.memory_saver)

    def _determine_next_agent(self, state: AgentState) -> str:
        """
        현재 상태를 기반으로 다음에 실행할 에이전트를 결정합니다.
        
        Args:
            state: 현재 에이전트 상태
        
        Returns:
            다음 에이전트 이름 또는 END
        """
        # 오류가 있으면 fallback_manager로 라우팅
        errors = state.get("errors", [])
        if errors and len(errors) > 2:  # 2개 이상의 오류가 있으면 fallback
            return "fallback_manager"
        
        # 실행 계획 확인
        execution_plan = state.get("execution_plan", {})
        if not execution_plan:
            return "fallback_manager"
        
        # 실행 순서 확인
        execution_order = execution_plan.get("execution_order", [])
        if not execution_order:
            return "fallback_manager"
        
        # 현재 상태에서 마지막으로 실행된 에이전트 확인
        processing_status = state.get("processing_status", {})
        executed_agents = [
            agent for agent, status in processing_status.items() 
            if status in ["completed", "completed_with_default_plan", "completed_no_data"]
        ]
        
        # 아직 실행되지 않은 에이전트 찾기
        next_agents = [
            agent for agent in execution_order 
            if agent not in executed_agents and agent in self.agents
        ]
        
        # 다음 실행할 에이전트가 있으면 반환
        if next_agents:
            return next_agents[0]
        
        # 모든 에이전트가 실행되었으면 종료
        return END

    def register_agents(self, agents: Dict[str, BaseAgent], db: AsyncSession):
        """
        에이전트를 등록하고 그래프를 구축합니다.
        
        Args:
            agents: 에이전트 이름과 인스턴스의 딕셔너리
            db: 데이터베이스 세션
        """
        self.agents = agents
        # 등록된 에이전트들로 그래프 구축
        self.graph = self._build_graph(db)
        
        # LangSmith 트레이싱 설정은 그래프 컴파일 시 이미 추가됨
        logger.info("그래프 구축 완료")
    
    async def process_query(self, query: str, session_id: Optional[str] = None, 
                           stock_code: Optional[str] = None, stock_name: Optional[str] = None,
                           **kwargs) -> Dict[str, Any]:
        """
        사용자 쿼리를 처리하여 결과를 반환합니다.
        
        Args:
            query: 사용자 질문
            session_id: 세션 ID (선택적)
            stock_code: 종목 코드 (선택적)
            stock_name: 종목명 (선택적)
            **kwargs: 추가 매개변수
            
        Returns:
            처리 결과
        """
        try:
            if not self.graph:
                raise ValueError("그래프가 초기화되지 않았습니다. register_agents 메서드를 먼저 호출하세요.")
            
            # 세션 ID 설정 (추적 ID로 사용)
            trace_id = session_id or datetime.now().strftime("%Y%m%d%H%M%S")
            
            # 초기 상태 설정
            initial_state: AgentState = {
                "query": query,
                "session_id": trace_id,
                "stock_code": stock_code,
                "stock_name": stock_name,
                "errors": [],
                "processing_status": {},
                "retrieved_data": {},  # 검색 결과를 담을 딕셔너리
                **kwargs
            }
            
            # 그래프 실행 (thread_id 제거, config 매개변수만 사용)
            result = await self.graph.ainvoke(
                initial_state,
                config={"configurable": {"thread_id": trace_id}}
            )
            
            # 트레이스 정보 기록
            logger.info(f"트레이스 ID: {trace_id} - 처리 완료")
            
            return result
            
        except Exception as e:
            logger.error(f"쿼리 처리 중 오류 발생: {str(e)}", exc_info=True)
            return {
                "query": query,
                "errors": [{
                    "agent": "stock_analysis_graph",
                    "error": str(e),
                    "type": type(e).__name__,
                    "timestamp": datetime.now()
                }],
                "summary": "처리 중 오류가 발생했습니다."
            }
    
    def get_thread_ids(self) -> List[str]:
        """
        모든 스레드 ID를 반환합니다.
        
        Returns:
            스레드 ID 목록
        """
        return list(self.memory_saver.list_threads()) 

# StockAnalysisGraph 인스턴스를 생성하고 그래프를 빌드하여 반환하는 함수
def create_graph():
    """
    StockAnalysisGraph 인스턴스를 생성하고 그래프를 반환합니다.
    이 함수는 LangGraph API에서 사용됩니다.
    """
    # 그래프 빌드 및 반환
    #return analysis_graph._build_graph()
    return get_graph(None)


# 팩토리 함수를 graph 변수로 내보냅니다
graph = create_graph 