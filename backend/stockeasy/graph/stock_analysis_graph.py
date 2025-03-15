"""
주식 분석 워크플로우 그래프 정의

이 모듈은 LangGraph를 사용하여 주식 분석 에이전트들의 워크플로우를 정의합니다.
"""

from typing import Dict, Any, List, Literal, Union, Optional, TypedDict, Tuple, Set, cast
from langchain_core.runnables import ConfigurableField
import langgraph.graph as lg
from langgraph.graph import END, StateGraph
from langchain_core.messages import BaseMessage, HumanMessage
from datetime import datetime
from loguru import logger

from stockeasy.models.agent_io import AgentState
from stockeasy.agents.base import BaseAgent
from stockeasy.agents.session_manager import SessionManagerAgent
from common.services.user import UserService
from common.schemas.user import SessionBase
from sqlalchemy.ext.asyncio import AsyncSession

def router_function(state: AgentState) -> Union[str, List[str]]:
    """
    질문 유형에 따라 적절한 검색 에이전트를 선택합니다.
    
    Args:
        state: 현재 에이전트 상태
        
    Returns:
        검색할 에이전트 이름 또는 이름 목록
    """
    classification = state.get("classification", {})
    question_type = classification.get("질문주제", 4)  # 기본값: 기타
    
    # 종목기본정보: 텔레그램, 기업리포트
    if question_type == 0:
        return ["telegram_retriever", "report_analyzer"]
    
    # 전망: 텔레그램, 기업리포트, 산업분석
    elif question_type == 1:
        return ["telegram_retriever", "report_analyzer", "industry_analyzer"]
    
    # 재무분석: 텔레그램, 재무제표
    elif question_type == 2:
        return ["telegram_retriever", "financial_analyzer"]
    
    # 산업동향: 텔레그램, 산업분석
    elif question_type == 3:
        return ["telegram_retriever", "industry_analyzer"]
    
    # 기타: 모든 소스 검색
    else:
        return ["telegram_retriever", "report_analyzer", "financial_analyzer", "industry_analyzer"]


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
    return "question_analyzer_next"


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
        self.graph = self._build_graph()
    
    def _build_graph(self):
        """
        주식 분석 워크플로우 그래프를 구축합니다.
        """
        # 그래프 초기화
        workflow = StateGraph(AgentState)
        
        # 노드 추가
        # 각 에이전트를 그래프의 노드로 추가
        workflow.add_node("session_manager", {})
        workflow.add_node("orchestrator", {})
        workflow.add_node("question_analyzer", {})
        workflow.add_node("question_analyzer_next", {})
        workflow.add_node("knowledge_integrator", {})
        workflow.add_node("summarizer", {})
        workflow.add_node("response_formatter", {})
        workflow.add_node("fallback_manager", {})
        
        # 기본 흐름 정의
        workflow.add_edge("session_manager", "orchestrator")
        workflow.add_edge("orchestrator", "question_analyzer")
        
        # 분류 후 조건부 경로
        workflow.add_conditional_edges(
            "question_analyzer",
            should_fallback_early,
            {
                "fallback_manager": "fallback_manager",
                "question_analyzer_next": "question_analyzer_next",
            }
        )
        
        # 검색 에이전트들을 병렬 처리하기 위한 브랜치 정의
        # 브랜치 내의 모든 노드들은 동시에 실행됨
        with workflow.branch("retrieval_branch") as branch:
            # 검색 에이전트 노드 추가
            branch.add_node("telegram_retriever", {})
            branch.add_node("report_analyzer", {})
            branch.add_node("financial_analyzer", {})
            branch.add_node("industry_analyzer", {})
        
        # 질문 분석 결과에 따라 필요한, 검색 에이전트만 실행하도록 라우팅
        workflow.add_conditional_edges(
            "question_analyzer_next",
            router_function,
            {
                "telegram_retriever": ["retrieval_branch.telegram_retriever"],
                "report_analyzer": ["retrieval_branch.report_analyzer"],
                "financial_analyzer": ["retrieval_branch.financial_analyzer"],
                "industry_analyzer": ["retrieval_branch.industry_analyzer"],
                ["telegram_retriever", "report_analyzer"]: ["retrieval_branch.telegram_retriever", "retrieval_branch.report_analyzer"],
                ["telegram_retriever", "report_analyzer", "industry_analyzer"]: ["retrieval_branch.telegram_retriever", "retrieval_branch.report_analyzer", "retrieval_branch.industry_analyzer"],
                ["telegram_retriever", "financial_analyzer"]: ["retrieval_branch.telegram_retriever", "retrieval_branch.financial_analyzer"],
                ["telegram_retriever", "industry_analyzer"]: ["retrieval_branch.telegram_retriever", "retrieval_branch.industry_analyzer"],
                ["telegram_retriever", "report_analyzer", "financial_analyzer", "industry_analyzer"]: ["retrieval_branch.telegram_retriever", "retrieval_branch.report_analyzer", "retrieval_branch.financial_analyzer", "retrieval_branch.industry_analyzer"],
            }
        )
        
        # 검색 결과 통합 - 모든 브랜치가 완료되면 knowledge_integrator로 이동
        workflow.add_edge("retrieval_branch", "knowledge_integrator")
        
        # 검색 결과 기반 조건부 경로
        workflow.add_conditional_edges(
            "knowledge_integrator",
            has_insufficient_data,
            {
                "fallback_manager": "fallback_manager",
                "summarizer": "summarizer"
            }
        )
        
        # 최종 경로
        workflow.add_edge("summarizer", "response_formatter")
        workflow.add_edge("fallback_manager", "response_formatter")
        
        # 시작점과 종료점 설정
        workflow.set_entry_point("session_manager")
        workflow.set_finish_point("response_formatter")
        
        return workflow.compile()
    
    def register_agents(self, agents: Dict[str, BaseAgent], db: AsyncSession):
        """
        그래프에 에이전트를 등록합니다.
        
        Args:
            agents: 에이전트 이름과 인스턴스의 딕셔너리
            db: 데이터베이스 세션
        """
        self.agents = agents
        
        # 세션 관리자 에이전트는 DB 연결이 필요하므로 따로 생성
        if "session_manager" not in self.agents:
            self.agents["session_manager"] = SessionManagerAgent(db)
        
        # 그래프의 노드와 에이전트 연결
        for node_name, agent in self.agents.items():
            # 브랜치 내부 노드 처리
            if "." in node_name:
                branch_name, node_name = node_name.split(".", 1)
                if branch_name == "retrieval_branch":
                    # retrieval_branch 내부 노드에 에이전트 연결
                    self.graph.runners[f"retrieval_branch.{node_name}"] = agent.process
            else:
                # 일반 노드에 에이전트 연결
                self.graph.runners[node_name] = agent.process
    
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
            # 초기 상태 설정
            initial_state: AgentState = {
                "query": query,
                "session_id": session_id or datetime.now().strftime("%Y%m%d%H%M%S"),
                "stock_code": stock_code,
                "stock_name": stock_name,
                "errors": [],
                "processing_status": {},
                **kwargs
            }
            
            # 그래프 실행
            result = await self.graph.ainvoke(initial_state)
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