"""
주식 분석 워크플로우 그래프 정의

이 모듈은 LangGraph를 사용하여 주식 분석 에이전트들의 워크플로우를 정의합니다.
"""

import os
from typing import Dict, Any, List, Literal, Union, Optional, TypedDict, Tuple, Set, cast, Callable

from langgraph.graph import END, StateGraph
from langgraph.checkpoint.memory import MemorySaver
from datetime import datetime
from loguru import logger


from stockeasy.models.agent_io import AgentState
from stockeasy.agents.base import BaseAgent
from stockeasy.agents.session_manager_agent import SessionManagerAgent
from stockeasy.agents.parallel_search_agent import ParallelSearchAgent
from sqlalchemy.ext.asyncio import AsyncSession


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
        # 콜백 함수 저장을 위한 딕셔너리 추가
        self.callbacks = {
            'agent_start': [],
            'agent_end': []
        }
    
    # 콜백 등록 메서드 추가
    def register_callback(self, event_type: str, callback_fn: Callable):
        """
        에이전트 이벤트에 대한 콜백 함수를 등록합니다.
        
        Args:
            event_type: 이벤트 유형 ('agent_start' 또는 'agent_end')
            callback_fn: 콜백 함수. 에이전트 이름과 상태를 인자로 받습니다.
        """
        if event_type not in self.callbacks:
            logger.warning(f"알 수 없는 이벤트 유형: {event_type}. 지원되는 이벤트: {list(self.callbacks.keys())}")
            return
            
        self.callbacks[event_type].append(callback_fn)
        logger.info(f"{event_type} 이벤트에 콜백 함수 등록됨")
    
    # 콜백 실행 메서드 추가
    def _execute_callbacks(self, event_type: str, agent_name: str, state: Dict[str, Any]):
        """
        등록된 콜백 함수들을 실행합니다.
        
        Args:
            event_type: 이벤트 유형
            agent_name: 에이전트 이름
            state: 현재 상태
        """
        if event_type not in self.callbacks:
            return
            
        for callback_fn in self.callbacks[event_type]:
            try:
                callback_fn(agent_name, state)
            except Exception as e:
                logger.error(f"{event_type} 콜백 실행 중 오류 발생: {str(e)}")
    
    def _build_graph(self, db: AsyncSession = None):
        """
        주식 분석 워크플로우 그래프를 구축합니다.
        
        Args:
            db: 데이터베이스 세션 (세션 관리자 에이전트 초기화용)
            
        Returns:
            컴파일된 그래프
        """
        # DB 세션을 모든 에이전트에 전달
        if db:
            for agent_name, agent in self.agents.items():
                if hasattr(agent, 'db'):
                    agent.db = db
                    #logger.info(f"에이전트 '{agent_name}'에 DB 세션 할당됨")
        
        # 세션 관리자 에이전트 준비
        if "session_manager" not in self.agents and db:
            self.agents["session_manager"] = SessionManagerAgent(db=db)
        
        # 병렬 검색 에이전트 생성
        parallel_search_agent = ParallelSearchAgent({
            "telegram_retriever": self.agents.get("telegram_retriever"),
            "report_analyzer": self.agents.get("report_analyzer"),
            "financial_analyzer": self.agents.get("financial_analyzer"),
            "industry_analyzer": self.agents.get("industry_analyzer"),
            "confidential_analyzer": self.agents.get("confidential_analyzer")
        })
        
        # 그래프 초기화
        workflow = StateGraph(AgentState)
        
        # 노드 추가 - 에이전트 함수 직접 설정
        for node_name, agent in self.agents.items():
            # 존재하는 에이전트만 추가
            if agent:
                # 콜백 래핑 함수 생성
                wrapped_process = self._create_wrapped_process(node_name, agent.process)
                workflow.add_node(node_name, wrapped_process)
            else:
                workflow.add_node(node_name, {})  # 빈 노드
        
        # 병렬 검색 노드 추가 - 콜백 래핑
        wrapped_parallel_search = self._create_wrapped_process("parallel_search", parallel_search_agent.process)
        workflow.add_node("parallel_search", wrapped_parallel_search)
        
        # 새로운 흐름 정의: 질문분류기 -> 오케스트레이터 -> 병렬 검색 -> 지식 통합
        workflow.add_edge("session_manager", "question_analyzer")
        workflow.add_edge("question_analyzer", "orchestrator")
        
        # 오케스트레이터 -> 병렬 검색 또는 fallback_manager (명확한 조건부 엣지)
        def orchestrator_router(state: AgentState) -> str:
            """오케스트레이터 이후 라우팅 결정"""
            # 오류가 많으면 fallback으로
            errors = state.get("errors", [])
            if errors and len(errors) > 2:
                logger.info("오류가 많아 fallback_manager로 라우팅합니다.")
                return "fallback_manager"
                
            # 실행 계획이 없으면 fallback으로
            execution_plan = state.get("execution_plan", {})
            if not execution_plan or not execution_plan.get("execution_order"):
                logger.info("실행 계획이 없어 fallback_manager로 라우팅합니다.")
                return "fallback_manager"
                
            # 정상 흐름은 병렬 검색으로
            logger.info("parallel_search로 라우팅합니다.")
            return "parallel_search"
        
        workflow.add_conditional_edges(
            "orchestrator",
            orchestrator_router,
            {
                "parallel_search": "parallel_search",
                "fallback_manager": "fallback_manager"
            }
        )
        
        # 병렬 검색 -> knowledge_integrator 또는 fallback_manager (명확한 조건부 엣지)
        def parallel_search_router(state: AgentState) -> str:
            """병렬 검색 이후 라우팅 결정"""
            # 로그에 전체 상태 출력 (디버깅용)
            logger.info(f"병렬 검색 이후 상태 확인 - processing_status: {state.get('processing_status', {})}")
            logger.info(f"병렬 검색 이후 상태 확인 - retrieved_data 키: {list(state.get('retrieved_data', {}).keys())}")
            
            # agent_results 키 확인 (중요: knowledge_integrator와 summarizer에서 사용)
            agent_results = state.get("agent_results", {})
            if agent_results:
                logger.info(f"병렬 검색 이후 agent_results 키: {list(agent_results.keys())}")
            else:
                logger.warning("병렬 검색 이후 agent_results 키가 없습니다!")
            
            # 병렬 검색 실행 완료 확인 방법 1: parallel_search_executed 플래그
            parallel_search_executed = state.get("parallel_search_executed", False)
            
            # 병렬 검색 실행 완료 확인 방법 2: 하위 에이전트 처리 상태
            processing_status = state.get("processing_status", {})
            telegram_status = processing_status.get("telegram_retriever")
            report_status = processing_status.get("report_analyzer")
            financial_status = processing_status.get("financial_analyzer")
            industry_status = processing_status.get("industry_analyzer")
            confidential_status = processing_status.get("confidential_analyzer")
            
            # 완료 상태 목록
            completed_statuses = ["completed", "completed_with_default_plan", "completed_no_data"]
            
            # 어느 하나라도 실행 완료 상태인지 확인
            search_completed = any([
                telegram_status in completed_statuses,
                report_status in completed_statuses, 
                financial_status in completed_statuses,
                industry_status in completed_statuses,
                confidential_status in completed_statuses
            ])
            
            # 검색 에이전트가 실행되지 않았는지 확인
            if not parallel_search_executed and not search_completed:
                logger.warning("병렬 검색이 실행되지 않았습니다.")
                logger.warning(f"실행 상태: telegram={telegram_status}, report={report_status}, financial={financial_status}, industry={industry_status}, confidential={confidential_status}")
                return "fallback_manager"
            
            # 모든 에이전트가 실패한 경우
            if state.get("all_search_agents_failed", False):
                logger.warning("모든 검색 에이전트가 실패했습니다.")
                return "fallback_manager"
            
            # 검색 결과가 있는지 확인
            retrieved_data = state.get("retrieved_data", {})
            
            # 실제 데이터 포함 항목만 확인
            has_data = False
            for key in ["telegram_messages", "report_data", "financial_data", "industry_data"]:
                if key in retrieved_data and retrieved_data[key]:
                    has_data = True
                    logger.info(f"데이터가 검색됨: {key}에 {len(retrieved_data[key])}개 항목이 있습니다.")
                    break
            
            if not has_data:
                logger.warning("검색 결과가 없어 fallback_manager로 라우팅합니다.")
                return "fallback_manager"
            
            logger.info("데이터가 검색되어 knowledge_integrator로 라우팅합니다.")
            return "knowledge_integrator"
        
        workflow.add_conditional_edges(
            "parallel_search",
            parallel_search_router,
            {
                "knowledge_integrator": "knowledge_integrator",
                "fallback_manager": "fallback_manager"
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

    def _create_wrapped_process(self, agent_name: str, original_process):
        """
        에이전트 프로세스 함수를 래핑하여 콜백을 추가합니다.
        
        Args:
            agent_name: 에이전트 이름
            original_process: 원래 프로세스 함수
            
        Returns:
            래핑된 프로세스 함수
        """
        async def wrapped_process(state: Dict[str, Any]) -> Dict[str, Any]:
            # 에이전트 시작 콜백 실행
            self._execute_callbacks('agent_start', agent_name, state)
            
            # 원래 프로세스 실행
            result = await original_process(state)
            
            # 에이전트 종료 콜백 실행
            self._execute_callbacks('agent_end', agent_name, result)
            
            return result
            
        return wrapped_process

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
            logger.info("오류가 많아 fallback_manager로 라우팅합니다.")
            return "fallback_manager"
        
        # 실행 계획 확인
        execution_plan = state.get("execution_plan", {})
        if not execution_plan:
            logger.info("실행 계획이 없어 fallback_manager로 라우팅합니다.")
            return "fallback_manager"
        
        # 실행 순서 확인
        execution_order = execution_plan.get("execution_order", [])
        if not execution_order:
            logger.info("실행 순서가 없어 fallback_manager로 라우팅합니다.")
            return "fallback_manager"
        
        # 현재 상태에서 마지막으로 실행된 에이전트 확인
        processing_status = state.get("processing_status", {})
        executed_agents = [
            agent for agent, status in processing_status.items() 
            if status in ["completed", "completed_with_default_plan", "completed_no_data"]
        ]
        
        # 다음 단계 결정
        if "knowledge_integrator" in executed_agents:
            if "summarizer" in execution_order and "summarizer" not in executed_agents:
                logger.info("knowledge_integrator 이후 summarizer로 라우팅합니다.")
                return "summarizer"
            else:
                logger.info("knowledge_integrator 이후 response_formatter로 라우팅합니다.")
                return "response_formatter"
        elif "summarizer" in executed_agents:
            logger.info("summarizer 이후 response_formatter로 라우팅합니다.")
            return "response_formatter"
        
        # 여기까지 오면 END 반환
        logger.info("더 이상 실행할 에이전트가 없어 END로 라우팅합니다.")
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
                "agent_results": {},   # 명시적으로 agent_results 초기화
                "parallel_search_executed": False,  # 병렬 검색 실행 여부 초기화
                **kwargs
            }
            logger.info(f"[process_query] initial_state: {initial_state}")
            logger.info("병렬 처리 설정으로 그래프 실행 시작")
            
            # 그래프 실행 (thread_id 제거, config 매개변수만 사용)
            result = await self.graph.ainvoke(
                initial_state,
                config={
                    "configurable": {"thread_id": trace_id}, 
                    "max_concurrency": 4,  # 병렬 처리 동시성 설정
                    "recursion_limit": 25  # 재귀 제한 설정
                }
            )
            
            # 결과 확인
            if "retrieved_data" in result:
                data_keys = list(result["retrieved_data"].keys())
                logger.info(f"검색 데이터 키: {data_keys}")
            
            if "processing_status" in result:
                logger.info(f"처리 상태: {result['processing_status']}")
            
            # 트레이스 정보 기록
            logger.info(f"트레이스 ID: {trace_id} - 처리 완료")
            
            return result
            
        except Exception as e:
            logger.error(f"쿼리 처리 중 오류 발생: {str(e)}", exc_info=True)
            
            # 노드 전환 오류인 경우 특별 처리
            if "telegram_retriever" in str(e) or "report_analyzer" in str(e):
                logger.error(f"노드 전환 오류 감지됨: {str(e)}")
                # 여기서 필요한 처리 추가
                
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
# def create_graph():
#     """
#     StockAnalysisGraph 인스턴스를 생성하고 그래프를 반환합니다.
#     이 함수는 LangGraph API에서 사용됩니다.
#     """
#     # 그래프 빌드 및 반환
#     #return analysis_graph._build_graph()
#     return get_graph(None)


# # 팩토리 함수를 graph 변수로 내보냅니다
# graph = create_graph 