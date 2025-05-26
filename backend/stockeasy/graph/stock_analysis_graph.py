"""
주식 분석 워크플로우 그래프 정의

이 모듈은 LangGraph를 사용하여 주식 분석 에이전트들의 워크플로우를 정의합니다.
"""

import os
from typing import Dict, Any, List, Literal, Union, Optional, TypedDict, Tuple, Set, cast, Callable
import asyncio
import time
import csv
import psutil
import gc
import objgraph
from pathlib import Path

from langgraph.graph import END, StateGraph
from langgraph.checkpoint.memory import MemorySaver
from datetime import datetime
from loguru import logger


from stockeasy.models.agent_io import AgentState
from stockeasy.agents.base import BaseAgent
from stockeasy.agents.session_manager_agent import SessionManagerAgent
from stockeasy.agents.parallel_search_agent import ParallelSearchAgent
from sqlalchemy.ext.asyncio import AsyncSession

# 메모리 추적 On/Off 설정 변수
ENABLE_MEMORY_TRACKING = os.getenv("ENABLE_MEMORY_TRACKING", "true").lower() == "true"

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

def should_use_web_search(state: AgentState) -> bool:
    """웹 검색 에이전트를 사용해야 하는지 결정합니다."""
    # 새로운 question_analyzer의 분류 확인
    data_requirements = state.get("data_requirements", {})
    web_search_needed = data_requirements.get("web_search_needed", False)
    
    # question_analyzer 결과가 있으면 우선 적용
    if "data_requirements" in state:
        return web_search_needed
    
    # 기본값 반환 (검색 사용 우선)
    return True

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
            'agent_end': [],
            'graph_start': [],
            'graph_end': []
        }
        
        # 상태 추적을 위한 변수 추가
        self.current_state = {}
        self.state_lock = asyncio.Lock()  # 동시성 제어를 위한 락
    
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
    
    # 콜백 제거 메서드 추가
    def unregister_callback(self, event_type: str, callback_fn: Callable) -> bool:
        """
        등록된 콜백 함수를 제거합니다.
        
        Args:
            event_type: 이벤트 유형 ('agent_start' 또는 'agent_end')
            callback_fn: 제거할 콜백 함수
            
        Returns:
            제거 성공 여부
        """
        if event_type not in self.callbacks:
            logger.warning(f"알 수 없는 이벤트 유형: {event_type}. 지원되는 이벤트: {list(self.callbacks.keys())}")
            return False
            
        if callback_fn in self.callbacks[event_type]:
            self.callbacks[event_type].remove(callback_fn)
            logger.info(f"{event_type} 이벤트에서 콜백 함수 제거됨")
            return True
        else:
            logger.warning(f"{event_type} 이벤트에 해당 콜백 함수가 등록되어 있지 않습니다.")
            return False
    
    # 모든 콜백 제거 메서드 추가
    def clear_callbacks(self, event_type: Optional[str] = None):
        """
        등록된 모든 콜백 함수를 제거합니다.
        
        Args:
            event_type: 제거할 이벤트 유형 (None이면 모든 이벤트의 콜백 제거)
        """
        if event_type:
            if event_type in self.callbacks:
                self.callbacks[event_type] = []
                logger.info(f"{event_type} 이벤트의 모든 콜백 함수가 제거됨")
            else:
                logger.warning(f"알 수 없는 이벤트 유형: {event_type}. 지원되는 이벤트: {list(self.callbacks.keys())}")
        else:
            for event_type in self.callbacks:
                self.callbacks[event_type] = []
            logger.info(f"모든 이벤트의 콜백 함수가 제거됨")
    
    def write_to_csv_full_graph_time(self, event_type: str, agent_name: str, note: Optional[str] = None, session_id: Optional[str] = None) -> None:
        # CSV 파일 경로 설정
        log_dir = os.path.join('stockeasy', 'local_cache')
        os.makedirs(log_dir, exist_ok=True)
        
        date_str = datetime.now().strftime('%Y%m%d')
        csv_path = os.path.join(log_dir, f'log_agent_time_{date_str}.csv')
        
        # 파일 존재 여부 확인 (헤더 추가 여부 결정)
        file_exists = os.path.isfile(csv_path)
        
        # 현재 날짜와 시간
        current_datetime = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # PID 정보 가져오기
        current_pid = os.getpid()
        
        # CSV 파일에 데이터 추가
        with open(csv_path, 'a', newline='', encoding='utf-8-sig') as csvfile:
            fieldnames = ['일자', 'pid', 'session_id', 'event_type', 'agent_name', 'note']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            
            # 파일이 새로 생성된 경우 헤더 작성
            if not file_exists:
                writer.writeheader()
            writer.writerow({
                '일자': current_datetime,
                'pid': current_pid,
                'session_id': session_id or 'unknown',
                'event_type': event_type,
                'agent_name': agent_name,
                'note': note
            })
                
    
    # 콜백 실행 메서드 추가
    async def _execute_callbacks(self, event_type: str, agent_name: str, state: Dict[str, Any]):
        """
        등록된 콜백 함수들을 실행합니다.
        
        Args:
            event_type: 이벤트 타입 ('agent_start', 'agent_complete', 'graph_end')
            agent_name: 에이전트 이름
            state: 현재 상태
        """
        if event_type not in self.callbacks:
            return
        if event_type == "graph_start" or event_type == "agent_start" or event_type == "agent_end" or event_type == "graph_end":
            session_id = state.get("session_id", "unknown")
            await asyncio.to_thread(self.write_to_csv_full_graph_time, event_type, agent_name, None, session_id)

        # 세션 ID가 'test_session'인 경우에만 콜백 실행
        session_id = state.get("session_id")
        if session_id != "test_session":
            return
            
        for callback_fn in self.callbacks[event_type]:
            try:
                if asyncio.iscoroutinefunction(callback_fn):
                    await callback_fn(agent_name, state)
                else:
                    callback_fn(agent_name, state)
            except Exception as e:
                logger.error(f"{event_type} 콜백 실행 중 오류 발생: {str(e)}")
            
        # 상태 추적을 위한 코드 추가
        if 'session_id' in state:
            session_id = state['session_id']
            async with self.state_lock:
                if session_id not in self.current_state:
                    self.current_state[session_id] = {}
                
                # streaming_callback 함수 제거 (직렬화 불가능)
                serializable_state = {k: v for k, v in state.items() if k != 'streaming_callback'}
                
                # 처리 상태 복사
                if 'processing_status' in serializable_state:
                    self.current_state[session_id]['processing_status'] = serializable_state['processing_status'].copy()
                
                # 기타 필요한 정보 추가
                self.current_state[session_id]['last_updated'] = time.time()
                self.current_state[session_id]['current_agent'] = agent_name
                
                # 에이전트 결과 저장 (있는 경우)
                if 'agent_results' in serializable_state and agent_name in serializable_state['agent_results']:
                    if 'agent_results' not in self.current_state[session_id]:
                        self.current_state[session_id]['agent_results'] = {}
                    
                    self.current_state[session_id]['agent_results'][agent_name] = serializable_state['agent_results'][agent_name]
        
    
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
            "revenue_breakdown": self.agents.get("revenue_breakdown"),
            "report_analyzer": self.agents.get("report_analyzer"),
            "financial_analyzer": self.agents.get("financial_analyzer"),
            "industry_analyzer": self.agents.get("industry_analyzer"),
            "confidential_analyzer": self.agents.get("confidential_analyzer"),
            "web_search": self.agents.get("web_search"),
        }, graph=self)  # 현재 그래프 인스턴스 전달
        
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
        
        # 질문 분석기 이후 라우팅 결정: 후속 질문 여부에 따라 라우팅
        def question_analyzer_router(state: AgentState) -> str:
            """질문 분석기 이후 라우팅 결정"""
            # 컨텍스트 분석 결과 확인
            is_follow_up = state.get("is_follow_up", False)
            context_analysis = state.get("context_analysis", False)
            is_conversation_closing = context_analysis.get("is_conversation_closing", False)

            logger.info(f"[question_analyzer_router] 후속질문 여부: {is_follow_up}, 대화마무리 : {is_conversation_closing}")
            
            is_followup_question = context_analysis.get("is_followup_question", False)
            requires_context = context_analysis.get("requires_context", False)
            

            if is_conversation_closing:
                logger.info(f"대화 마무리로 에이전트를 종료합니다. END")
                if "processing_status" not in state:
                    state["processing_status"] = {}
                state["processing_status"]["question_analyzer"] = "completed"
                return END
            
            is_different_stock = context_analysis.get("is_different_stock", False)
            # stock_relation: Optional[Literal["동일종목", "종목비교", "다른종목", "알수없음"]]  # 이전 종목과의 관계
            stock_relation = context_analysis.get("stock_relation", "알수없음")
            logger.info(f"[question_analyzer_router] 다른종목 여부: {is_different_stock}, 종목관계 : {stock_relation}")
            if is_different_stock and stock_relation == "다른종목":
                logger.info(f"다른종목에 관란 질문이므로,  에이전트를 종료합니다. END")
                
                state["processing_status"]["question_analyzer"] = "completed"
                return END
            # 대화 컨텍스트가 필요한 경우 context_response로 라우팅

            #if requires_context:
            if is_follow_up:
                logger.info(f"후속질문으로 context_response 에이전트로 라우팅합니다.")
                # 처리 상태 업데이트
                if "processing_status" not in state:
                    state["processing_status"] = {}
                state["processing_status"]["question_analyzer"] = "completed"
                return "context_response"
            
            # 그 외의 경우는 일반 흐름대로 오케스트레이터로
            logger.info(f"일반 질문으로 orchestrator 에이전트로 라우팅합니다.")
            return "orchestrator"
        
        # 질문 분석기 -> 컨텍스트 응답 또는 오케스트레이터 조건부 엣지 추가
        workflow.add_conditional_edges(
            "question_analyzer",
            question_analyzer_router,
            {
                "context_response": "context_response",
                #"response_formatter": "response_formatter",
                "orchestrator": "orchestrator",
                END: END
            }
        )
        
        # 컨텍스트 응답 -> 응답 포맷터 엣지 추가
        workflow.add_edge("context_response", "response_formatter")
        
        # 오케스트레이터 -> 병렬 검색 또는 fallback_manager (명확한 조건부 엣지)
        def orchestrator_router(state: AgentState) -> str:
            """오케스트레이터 이후 라우팅 결정"""
            # 재시작 플래그 확인
            if state.get("restart_from_error", False):
                previous_error = state.get("previous_error", "")
                logger.info(f"오류 후 재시작 상태 감지됨. 이전 오류: {previous_error}")
                
                # LangSmith 타임스탬프 오류인 경우, 병렬 검색으로 직접 라우팅
                if "invalid 'dotted_order'" in previous_error and "earlier than parent timestamp" in previous_error:
                    logger.info("LangSmith 타임스탬프 오류 복구를 위해 병렬 검색으로 즉시 라우팅합니다.")
                    
                    # 추가 상태 설정 (필요 시)
                    state["processing_status"]["question_analyzer"] = "completed"
                    state["processing_status"]["orchestrator"] = "completed"
                    
                    # 재시작 플래그 제거 (중복 처리 방지)
                    state.pop("restart_from_error", None)
                    state.pop("previous_error", None)
                    
                    return "parallel_search"
            
            # 오류가 많으면 fallback으로
            errors = state.get("errors", [])
            if errors and len(errors) > 2:
                logger.info("오류가 많아 fallback_manager로 라우팅합니다.")
                return "fallback_manager"
                
            # 실행 계획이 없으면 fallback으로
            execution_plan = state.get("execution_plan", {})
            if not execution_plan:
                logger.info("실행 계획이 없어 fallback_manager로 라우팅합니다.")
                return "fallback_manager"
                
            # 실행 순서가 없거나 빈 배열이면 fallback으로
            execution_order = execution_plan.get("execution_order", [])
            if not execution_order:
                logger.info("실행 순서가 비어있어 fallback_manager로 라우팅합니다.")
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
            
            # 타임스탬프 오류 재시작 플래그 확인 - 재시작 직후라면 knowledge_integrator로 바로 라우팅
            if state.get("restart_after_timestamp_error", False):
                logger.info("LangSmith 타임스탬프 오류 후 재시작: knowledge_integrator로 즉시 라우팅합니다.")
                # 플래그 제거
                state.pop("restart_after_timestamp_error", None)
                return "knowledge_integrator"
            
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
            revenue_breakdown_status = processing_status.get("revenue_breakdown")
            
            # 완료 상태 목록
            completed_statuses = ["completed", "completed_with_default_plan", "completed_no_data"]
            
            # 어느 하나라도 실행 완료 상태인지 확인
            search_completed = any([
                telegram_status in completed_statuses,
                report_status in completed_statuses, 
                financial_status in completed_statuses,
                industry_status in completed_statuses,
                confidential_status in completed_statuses,
                revenue_breakdown_status in completed_statuses
            ])
            
            # 검색 에이전트가 실행되지 않았는지 확인
            if not parallel_search_executed and not search_completed:
                logger.warning("병렬 검색이 실행되지 않았습니다.")
                logger.warning(f"실행 상태: telegram={telegram_status}, report={report_status}, financial={financial_status}, industry={industry_status}, confidential={confidential_status}, revenue_breakdown={revenue_breakdown_status}")
                return "fallback_manager"
            
            # 모든 에이전트가 실패한 경우
            if state.get("all_search_agents_failed", False):
                logger.warning("모든 검색 에이전트가 실패했습니다.")
                return "fallback_manager"
            
            # 검색 결과가 있는지 확인
            retrieved_data = state.get("retrieved_data", {})
            
            # 검색 데이터 키 로깅
            logger.info(f"검색 데이터 키: {list(retrieved_data.keys())}")
            
            # 실제 데이터 포함 항목만 확인
            has_data = False
            for key in ["telegram_messages", "report_data", "financial_data", "industry_data", "confidential_data", "revenue_breakdown"]:
                if key in retrieved_data and retrieved_data[key]:
                    has_data = True
                    logger.info(f"데이터가 검색됨: {key}에 {len(retrieved_data[key])}개 항목이 있습니다.")
                    break
            
            # 병렬 검색이 실행되었다면, 검색 결과가 없어도 계속 진행
            # 이미 하위 에이전트가, 진행 중일 수 있기 때문에, 바로 fallback_manager로 가지 않음
            if not has_data:
                # 모든 하위 에이전트가 실패했거나 완료되었는지 확인
                all_agents_completed_or_failed = True
                for agent_name in ["telegram_retriever", "report_analyzer", "financial_analyzer", "industry_analyzer", "confidential_analyzer", "revenue_breakdown"]:
                    status = processing_status.get(agent_name)
                    if status and status not in completed_statuses and status != "failed" and status != "error":
                        all_agents_completed_or_failed = False
                        break
                
                if all_agents_completed_or_failed:
                    logger.warning("모든 검색 에이전트가 완료되었거나 실패했으며, 검색 결과가 없어 fallback_manager로 라우팅합니다.")
                    return "fallback_manager"
                else:
                    logger.info("검색 결과가 아직 없지만 일부 에이전트가. 진행 중이므로 knowledge_integrator로 라우팅합니다.")
                    return "knowledge_integrator"
            
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
        에이전트 프로세스를 래핑하여 상태 관리 및 콜백 처리를 추가합니다.
        
        Args:
            agent_name: 에이전트 이름
            original_process: 원본 프로세스 함수
            
        Returns:
            래핑된 프로세스 함수
        """
        
        async def wrapped_process(state: Dict[str, Any]) -> Dict[str, Any]:
            # 에이전트 시작 시간 기록
            agent_start_time = time.time()
            
            # 객체 유형 분석 함수
            async def analyze_objects(phase):
                if not ENABLE_MEMORY_TRACKING:
                    return
                    
                try:
                    # 객체 카운트 스냅샷 디렉토리 생성
                    csv_dir = Path("stockeasy/local_cache/memory_tracking")
                    csv_dir.mkdir(parents=True, exist_ok=True)
                    
                    session_id = state.get("session_id", "unknown")
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    
                    # 가장 많은 객체 유형 15개 출력
                    most_common = objgraph.most_common_types(limit=10)
                    # logger.info(f"[객체분석-{phase}] {agent_name} - 상위 15개 객체 유형:")
                    # for type_name, count in most_common:
                    #     logger.info(f"  {type_name}: {count}개")
                    
                    # CSV에 기록 (비동기 파일 작업)
                    csv_path = csv_dir / f"object_types_{session_id}.csv"
                    file_exists = csv_path.exists()
                    
                    # 비동기 파일 작업을 위한 함수
                    async def write_object_types_csv():
                        # CSV 파일에 데이터 추가 (이벤트 루프 차단 방지)
                        loop = asyncio.get_event_loop()
                        await loop.run_in_executor(None, lambda: _write_object_types_to_csv(
                            csv_path, file_exists, timestamp, session_id, agent_name, phase, most_common
                        ))
                    
                    # 실제 CSV 파일 작성 함수 (이벤트 루프 외부에서 실행)
                    def _write_object_types_to_csv(path, exists, timestamp, session_id, agent_name, phase, data):
                        with open(path, 'a', newline='') as csvfile:
                            fieldnames = ['timestamp', 'session_id', 'agent', 'phase', 'object_type', 'count']
                            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                            
                            if not exists:
                                writer.writeheader()
                            
                            for type_name, count in data:
                                writer.writerow({
                                    'timestamp': timestamp,
                                    'session_id': session_id,
                                    'agent': agent_name,
                                    'phase': phase,
                                    'object_type': type_name,
                                    'count': count
                                })
                    
                    # 비동기 CSV 작성 실행
                    # await write_object_types_csv()  # object_types 파일 생성 비활성화
                    
                    # parallel_search 에이전트 특별 처리 (가장 메모리를 많이 사용하는 에이전트)
                    if agent_name == "parallel_search":
                        # 상태 객체 내용 분석
                        if "retrieved_data" in state:
                            retrieved_data = state.get("retrieved_data", {})
                            logger.info(f"[객체분석-상세] {agent_name} - retrieved_data 컨텐츠:")
                            
                            # retrieved_data 내용을 CSV에 저장 (비동기)
                            retrieved_data_path = csv_dir / f"retrieved_data_{session_id}_{timestamp}.csv"
                            
                            # 비동기 파일 작업을 위한 함수
                            async def write_retrieved_data_csv():
                                # CSV 파일에 데이터 추가 (이벤트 루프 차단 방지)
                                loop = asyncio.get_event_loop()
                                await loop.run_in_executor(None, lambda: _write_retrieved_data_to_csv(
                                    retrieved_data_path, retrieved_data
                                ))
                                
                            # 실제 CSV 파일 작성 함수 (이벤트 루프 외부에서 실행)
                            def _write_retrieved_data_to_csv(path, data):
                                with open(path, 'w', newline='') as csvfile:
                                    fieldnames = ['key', 'type', 'items_count', 'size_kb']
                                    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                                    writer.writeheader()
                                    
                                    for key, value in data.items():
                                        size_kb = len(str(value)) // 1024
                                        items_count = len(value) if isinstance(value, (list, dict)) else 1
                                        writer.writerow({
                                            'key': key,
                                            'type': type(value).__name__,
                                            'items_count': items_count,
                                            'size_kb': size_kb
                                        })
                            
                            # 비동기 CSV 작성 실행
                            # await write_retrieved_data_csv()  # retrieved_data 파일 생성 비활성화
                            
                            # 로그 출력 (즉시 수행)
                            for key, value in retrieved_data.items():
                                size_kb = len(str(value)) // 1024
                                if isinstance(value, list):
                                    logger.info(f"  {key}: {len(value)}개 항목, 크기 약 {size_kb}KB")
                                else:
                                    logger.info(f"  {key}: 크기 약 {size_kb}KB")
                        
                        # 큰 객체 분석 (예: dict)
                        if any(t[0] == "dict" and t[1] > 10000 for t in most_common):
                            logger.info(f"[객체분석-상세] {agent_name} - dict 객체가 많음, 가장 큰 5개 dict 찾기:")
                            # 모든 객체에서 dict 객체 찾기
                            big_dicts = []
                            for obj in gc.get_objects():
                                if isinstance(obj, dict) and len(obj) > 100:  # 큰 딕셔너리만 체크
                                    big_dicts.append((len(obj), obj))
                            
                            # 크기순으로 정렬하고 상위 5개 출력
                            # 수정: key 함수를 사용하여 튜플의 첫 번째 요소(dict 길이)만으로 정렬
                            big_dicts.sort(key=lambda x: x[0], reverse=True)
                            big_dicts = big_dicts[:5]  # 상위 5개만 추출
                            
                            # 큰 딕셔너리 정보를 CSV에 저장 (비동기)
                            big_dicts_path = csv_dir / f"big_dicts_{agent_name}_{session_id}_{timestamp}.csv"
                            
                            # 로그 출력 (즉시 수행)
                            for i, (size, d) in enumerate(big_dicts):
                                # 딕셔너리의 일부 키만 출력
                                keys = list(d.keys())[:5] if len(d) > 5 else list(d.keys())
                                logger.info(f"  큰 dict #{i+1}: {size}개 항목, 키 샘플: {keys}")
                                
                                # 딕셔너리의 내용 일부 출력
                                if keys:
                                    first_key = keys[0]
                                    first_value = d[first_key]
                                    first_value_type = type(first_value).__name__
                                    logger.info(f"    첫 항목 타입: {first_value_type}")
                                    
                                    # 문자열 값이면 길이 출력
                                    if isinstance(first_value, str):
                                        first_value_length = len(first_value)
                                        logger.info(f"    첫 항목 길이: {first_value_length} 문자")
                            
                            # 비동기 파일 작업을 위한 함수
                            async def write_big_dicts_csv():
                                # CSV 파일에 데이터 추가 (이벤트 루프 차단 방지)
                                loop = asyncio.get_event_loop()
                                await loop.run_in_executor(None, lambda: _write_big_dicts_to_csv(
                                    big_dicts_path, big_dicts
                                ))
                                
                            # 실제 CSV 파일 작성 함수 (이벤트 루프 외부에서 실행)
                            def _write_big_dicts_to_csv(path, big_dicts_data):
                                with open(path, 'w', newline='') as csvfile:
                                    fieldnames = ['index', 'size', 'sample_keys', 'first_value_type', 'first_value_length']
                                    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                                    writer.writeheader()
                                    
                                    for i, (size, d) in enumerate(big_dicts_data):
                                        keys = list(d.keys())[:5] if len(d) > 5 else list(d.keys())
                                        
                                        first_value_type = ""
                                        first_value_length = 0
                                        if keys:
                                            first_key = keys[0]
                                            first_value = d[first_key]
                                            first_value_type = type(first_value).__name__
                                            
                                            if isinstance(first_value, str):
                                                first_value_length = len(first_value)
                                        
                                        writer.writerow({
                                            'index': i+1,
                                            'size': size,
                                            'sample_keys': str(keys),
                                            'first_value_type': first_value_type,
                                            'first_value_length': first_value_length
                                        })
                            
                            # 비동기 CSV 작성 실행
                            await write_big_dicts_csv()
                    
                    # 객체 참조 그래프 생성 (메모리 많이 사용하는 에이전트만)
                    if agent_name in ["parallel_search", "knowledge_integrator", "summarizer" , "response_formatter"]:
                        # 가장 큰 객체 유형에 대한 참조 그래프 생성
                        biggest_type = most_common[0][0]
                        try:
                            # objgraph 사용 가능성 확인
                            try:
                                import objgraph
                                has_objgraph = True
                            except ImportError:
                                logger.warning(f"[객체분석-경고] objgraph 라이브러리가 설치되지 않아 그래프 생성을 건너뜁니다. 설치 명령: pip install objgraph")
                                has_objgraph = False
                            
                            if has_objgraph:
                                # 그래프 파일 저장 (비동기)
                                graph_path = csv_dir / f"{agent_name}_{phase}_{biggest_type}_{timestamp}.png"
                                
                                # 비동기 그래프 생성 함수
                                async def create_graph():
                                    try:
                                        # 그래프 생성 (이벤트 루프 차단 방지)
                                        loop = asyncio.get_event_loop()
                                        await loop.run_in_executor(None, lambda: _create_object_graph(
                                            biggest_type, str(graph_path)
                                        ))
                                        logger.info(f"[객체분석-그래프] {agent_name} - {biggest_type} 타입 참조 그래프 저장 성공: {graph_path}")
                                    except Exception as graph_e:
                                        logger.error(f"[객체분석-그래프] {agent_name} - 그래프 생성 실행 중 오류: {str(graph_e)}")
                                
                                # 실제 그래프 생성 함수 (이벤트 루프 외부에서 실행)
                                def _create_object_graph(obj_type, path):
                                    try:
                                        sample_objs = objgraph.by_type(obj_type)[:3]  # 타입의 처음 3개 객체
                                        if sample_objs:
                                            logger.info(f"[객체분석-그래프] {agent_name} - {obj_type} 타입 객체 {len(sample_objs)}개로 그래프 생성 시작")
                                            
                                            # Graphviz 설치 여부 확인 후 적절한 방법 선택
                                            try:
                                                objgraph.show_backrefs(
                                                    sample_objs, 
                                                    filename=path,
                                                    max_depth=5,
                                                    too_many=10,
                                                    filter=lambda x: not isinstance(x, type)
                                                )
                                                logger.info(f"[객체분석-그래프] {agent_name} - 그래프 파일 생성 완료: {path}")
                                            except Exception as graphviz_e:
                                                if "graphviz" in str(graphviz_e).lower() or "dot" in str(graphviz_e).lower() or "executable not found" in str(graphviz_e).lower():
                                                    logger.warning(f"[객체분석-그래프] Graphviz가 설치되지 않아 PNG 그래프 대신 텍스트 참조 정보를 저장합니다.")
                                                    
                                                    # 텍스트 파일로 참조 정보 저장
                                                    text_path = str(path).replace('.png', '.txt')
                                                    with open(text_path, 'w', encoding='utf-8') as f:
                                                        f.write(f"객체 타입: {obj_type}\n")
                                                        f.write(f"분석 시점: {timestamp}\n")
                                                        f.write(f"에이전트: {agent_name}\n")
                                                        f.write(f"단계: {phase}\n\n")
                                                        
                                                        for i, obj in enumerate(sample_objs):
                                                            f.write(f"=== 객체 #{i+1} ===\n")
                                                            f.write(f"객체 ID: {id(obj)}\n")
                                                            f.write(f"객체 타입: {type(obj).__name__}\n")
                                                            f.write(f"객체 크기: {len(str(obj))} 문자\n")
                                                            
                                                            # 간단한 참조자 정보 수집
                                                            referrers = objgraph.find_backref_chain(obj, objgraph.is_proper_module)
                                                            if referrers:
                                                                f.write(f"참조 체인 길이: {len(referrers)}\n")
                                                                for j, ref in enumerate(referrers[:3]):  # 상위 3개만
                                                                    f.write(f"  참조자 #{j+1}: {type(ref).__name__}\n")
                                                            f.write("\n")
                                                    
                                                    logger.info(f"[객체분석-그래프] {agent_name} - 텍스트 참조 정보 저장 완료: {text_path}")
                                                else:
                                                    raise graphviz_e
                                        else:
                                            logger.warning(f"[객체분석-그래프] {agent_name} - {obj_type} 타입의 객체를 찾을 수 없어 그래프 생성을 건너뜁니다.")
                                    except Exception as create_e:
                                        logger.error(f"[객체분석-그래프] {agent_name} - 그래프 파일 생성 중 오류: {str(create_e)}")
                                        # graphviz가 설치되지 않은 경우의 오류 메시지 확인
                                        if "graphviz" in str(create_e).lower() or "dot" in str(create_e).lower():
                                            logger.warning(f"[객체분석-그래프] Graphviz가 설치되지 않은 것 같습니다. 설치 가이드: https://graphviz.org/download/")
                                        # 간단한 텍스트 요약이라도 저장
                                        try:
                                            text_path = str(path).replace('.png', '_error.txt')
                                            with open(text_path, 'w', encoding='utf-8') as f:
                                                f.write(f"그래프 생성 실패\n")
                                                f.write(f"오류: {str(create_e)}\n")
                                                f.write(f"객체 타입: {obj_type}\n")
                                                f.write(f"시점: {timestamp}\n")
                                            logger.info(f"[객체분석-그래프] 오류 정보 저장: {text_path}")
                                        except Exception as text_e:
                                            logger.error(f"[객체분석-그래프] 텍스트 파일 저장도 실패: {str(text_e)}")
                                
                                # 비동기 그래프 생성 실행
                                await create_graph()
                            
                        except Exception as e:
                            logger.error(f"[객체분석-오류] 그래프 생성 중 오류: {str(e)}", exc_info=True)
                
                except Exception as e:
                    logger.error(f"[객체분석-오류] 객체 분석 중 오류 발생: {str(e)}", exc_info=True)
            
            # 메모리 사용량 체크 함수
            def get_memory_usage():
                if not ENABLE_MEMORY_TRACKING:
                    return {"rss": 0, "vms": 0, "gc_objects": 0, "state_size": 0}
                    
                try:
                    process = psutil.Process(os.getpid())
                    memory_info = process.memory_info()
                    return {
                        "rss": memory_info.rss / (1024 * 1024),  # RSS in MB
                        "vms": memory_info.vms / (1024 * 1024),  # VMS in MB
                        "gc_objects": 0,  # 무거운 작업 제거 (빠른 처리 위해)
                        "state_size": len(str(state)) // 1024,  # 상태 크기 (KB 단위로 축소)
                    }
                except Exception as e:
                    logger.error(f"메모리 사용량 체크 중 오류: {str(e)}")
                    return {"rss": 0, "vms": 0, "gc_objects": 0, "state_size": 0}
            
            # 메모리 사용량을 CSV 파일에 기록하는 함수
            async def log_memory_to_csv(phase, memory_data):
                if not ENABLE_MEMORY_TRACKING:
                    return
                    
                try:
                    csv_dir = Path("stockeasy/local_cache/memory_tracking")
                    csv_dir.mkdir(parents=True, exist_ok=True)
                    csv_path = csv_dir / "memory_usage.csv"
                    
                    # CSV 파일 존재 여부 확인
                    file_exists = csv_path.exists()
                    
                    session_id = state.get("session_id", "unknown")
                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
                    
                    # 비동기 파일 작업을 위한 함수
                    async def write_memory_csv():
                        # CSV 파일에 데이터 추가 (이벤트 루프 차단 방지)
                        loop = asyncio.get_event_loop()
                        await loop.run_in_executor(None, lambda: _write_memory_to_csv(
                            csv_path, file_exists, timestamp, session_id, agent_name, phase, memory_data
                        ))
                    
                    # 실제 CSV 파일 작성 함수 (이벤트 루프 외부에서 실행)
                    def _write_memory_to_csv(path, exists, timestamp, session_id, agent_name, phase, memory_data):
                        try:
                            with open(path, 'a', newline='') as csvfile:
                                fieldnames = ['timestamp', 'pid', 'worker_id', 'thread_info', 'session_id', 'agent', 'phase', 'rss_mb', 'vms_mb', 'gc_objects', 'state_size']
                                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                                
                                # 파일이 없으면 헤더 추가
                                if not exists:
                                    writer.writeheader()
                                
                                # 워커 식별자 정보 추가
                                import multiprocessing
                                import threading
                                
                                process = multiprocessing.current_process()
                                worker_id = f"{process.name}-{process.pid}"
                                thread_info = f"{threading.current_thread().name}-{threading.get_ident()}"
                                
                                writer.writerow({
                                    'timestamp': timestamp,
                                    'pid': os.getpid(),
                                    'worker_id': worker_id,
                                    'thread_info': thread_info,
                                    'session_id': session_id,
                                    'agent': agent_name,
                                    'phase': phase,
                                    'rss_mb': round(memory_data["rss"], 2),
                                    'vms_mb': round(memory_data["vms"], 2),
                                    'gc_objects': memory_data["gc_objects"],
                                    'state_size': memory_data["state_size"]
                                })
                        except Exception as e:
                            logger.error(f"CSV 파일 작성 중 오류: {str(e)}")
                    
                    # 비동기 CSV 작성 실행
                    await write_memory_csv()
                    
                except Exception as e:
                    logger.error(f"메모리 CSV 로깅 중 오류: {str(e)}")
            
            # 프로세스 시작 전 메모리 사용량 체크 (동기로 빠르게)
            pre_memory = get_memory_usage()
            if ENABLE_MEMORY_TRACKING:
                logger.info(f"[메모리체크-시작] {agent_name} - RSS: {pre_memory['rss']:.2f}MB, VMS: {pre_memory['vms']:.2f}MB, 상태크기: {pre_memory['state_size']}KB")
                await log_memory_to_csv("before", pre_memory)
            
            # 에이전트 시작 콜백 실행
            await self._execute_callbacks("agent_start", agent_name, state)
            
            # 처리 상태 업데이트
            state["processing_status"] = state.get("processing_status", {})
            state["processing_status"][agent_name] = "processing"
            
            # 세션 ID로 현재 상태 저장 (진행 상황 추적용)
            session_id = state.get("session_id")
            if session_id:
                async with self.state_lock:
                    # 직렬화 가능한 상태만 저장
                    serializable_state = {k: v for k, v in state.items() if k != 'streaming_callback'}
                    self.current_state[session_id] = serializable_state.copy()
            
            # 전역 스트리밍 콜백이 있는지 확인하고 상태에 추가
            if hasattr(self, '_streaming_callback') and self._streaming_callback and 'streaming_callback' not in state:
                state['streaming_callback'] = self._streaming_callback  # 클래스 멤버로 저장
                logger.info(f"[wrapped_process] {agent_name} 에이전트에 스트리밍 콜백 함수 추가: {self._streaming_callback.__name__ if hasattr(self._streaming_callback, '__name__') else '이름 없는 함수'}")
            elif 'streaming_callback' in state and state['streaming_callback'] is None and hasattr(self, '_streaming_callback') and self._streaming_callback:
                # 상태에 streaming_callback이 None으로 있는 경우 전역 콜백으로 대체
                state['streaming_callback'] = self._streaming_callback
                logger.info(f"[wrapped_process] {agent_name} 에이전트의 None 콜백을 전역 콜백으로 대체: {self._streaming_callback.__name__ if hasattr(self._streaming_callback, '__name__') else '이름 없는 함수'}")
            elif 'streaming_callback' in state:
                logger.info(f"[wrapped_process] {agent_name} 에이전트에 이미 콜백 함수가 있음: {state['streaming_callback'].__name__ if hasattr(state['streaming_callback'], '__name__') else '이름 없는 함수' if state['streaming_callback'] else 'None'}")
            
            # 특정 에이전트에만 analyze_objects 시작 시 실행 (메모리 많이 사용하는 에이전트)
            # if ENABLE_MEMORY_TRACKING and agent_name in ["parallel_search", "knowledge_integrator", "summarizer", "response_formatter"]:
            #     asyncio.create_task(analyze_objects("before"))
            
            try:
                # 원본 프로세스 즉시 실행 (블로킹 없음)
                result = await original_process(state)
                
                # 에이전트 실행 시간 계산
                agent_end_time = time.time()
                execution_time = agent_end_time - agent_start_time
                
                # result가 None인 경우 빈 딕셔너리로 처리
                if result is None:
                    logger.warning(f"에이전트 {agent_name}에서 None 결과가 반환되었습니다. 빈 딕셔너리로 대체합니다.")
                    result = {}
                
                # streaming_callback 함수 제거 (직렬화 불가능)
                if result and 'streaming_callback' in result:
                    del result['streaming_callback']
                
                # Background GC 작업 (메인 플로우와 병렬)
                async def background_gc_work():
                    try:
                        collected = await asyncio.to_thread(gc.collect)
                        logger.info(f"[GC정보-백그라운드] {agent_name} - 실행시간: {execution_time:.2f}s, 수집된 객체: {collected}")
                    except Exception as e:
                        logger.warning(f"[GC정보-백그라운드] {agent_name} - GC 작업 중 오류: {e}")
                
                # Background 메모리 체크 작업
                async def background_memory_work():
                    if not ENABLE_MEMORY_TRACKING:
                        return
                        
                    try:
                        # 프로세스 종료 후 메모리 사용량 체크
                        post_memory = get_memory_usage()
                        memory_diff = {
                            "rss": post_memory["rss"] - pre_memory["rss"],
                            "vms": post_memory["vms"] - pre_memory["vms"],
                            "gc_objects": 0,  # 무거운 작업 제거
                            "state_size": post_memory["state_size"] - pre_memory["state_size"]
                        }
                        
                        logger.info(f"[메모리체크-종료-백그라운드] {agent_name} - 실행시간: {execution_time:.2f}s, RSS: {post_memory['rss']:.2f}MB, VMS: {post_memory['vms']:.2f}MB, 상태크기: {post_memory['state_size']}KB")
                        logger.info(f"[메모리변화-백그라운드] {agent_name} - RSS: {memory_diff['rss']:.2f}MB, VMS: {memory_diff['vms']:.2f}MB, 상태크기: {memory_diff['state_size']}KB")
                        
                        # 비동기로 CSV 파일에 로깅
                        await log_memory_to_csv("after", post_memory)
                    except Exception as e:
                        logger.warning(f"[메모리체크-백그라운드] {agent_name} - 메모리 체크 중 오류: {e}")
                
                # Background 작업들 시작 (결과 기다리지 않음)
                asyncio.create_task(background_gc_work())
                
                # 메모리 체크는 실행 시간이 0.5초 이상인 경우에만 수행
                if execution_time >= 0.5:
                    asyncio.create_task(background_memory_work())
                    if ENABLE_MEMORY_TRACKING:
                        # asyncio.create_task(analyze_objects("after"))  # big_dicts 파일 생성 비활성화
                        pass
                elif ENABLE_MEMORY_TRACKING:
                    logger.debug(f"[메모리체크-건너뛰기] {agent_name} - 실행시간이 짧아서 메모리 체크 건너뜀 ({execution_time:.2f}s)")
                
                # 에이전트 완료 콜백 실행
                await self._execute_callbacks("agent_end", agent_name, result)
                
                return result
                
            except Exception as e:
                # 에이전트 실행 시간 계산 (오류 시)
                agent_end_time = time.time()
                execution_time = agent_end_time - agent_start_time
                
                # 오류 발생 시 메모리 상태 체크 (background)
                async def background_error_memory():
                    if not ENABLE_MEMORY_TRACKING:
                        return
                        
                    try:
                        error_memory = get_memory_usage()
                        logger.error(f"[메모리체크-오류-백그라운드] {agent_name} - 실행시간: {execution_time:.2f}s, RSS: {error_memory['rss']:.2f}MB, VMS: {error_memory['vms']:.2f}MB, 상태크기: {error_memory['state_size']}KB")
                        await log_memory_to_csv("error", error_memory)
                    except Exception as mem_e:
                        logger.warning(f"[메모리체크-오류-백그라운드] {agent_name} - 오류 메모리 체크 중 오류: {mem_e}")
                
                # Background 작업들 (실행 시간이 충분한 경우에만)
                if execution_time >= 0.5:
                    asyncio.create_task(background_error_memory())
                    if ENABLE_MEMORY_TRACKING:
                        # asyncio.create_task(analyze_objects("error"))  # big_dicts 파일 생성 비활성화
                        pass
                
                logger.error(f"에이전트 {agent_name} 처리 중 오류 발생 (실행시간: {execution_time:.2f}s): {str(e)}", exc_info=True)
                state["processing_status"][agent_name] = "failed"
                state["errors"] = state.get("errors", [])
                state["errors"].append({
                    "agent": agent_name,
                    "error": str(e),
                    "type": type(e).__name__,
                    "timestamp": datetime.now()
                })
                
                # streaming_callback 함수 제거 (직렬화 불가능)
                if 'streaming_callback' in state:
                    del state['streaming_callback']
                
                # 에이전트 오류 콜백 실행
                await self._execute_callbacks("agent_error", agent_name, state)
                
                raise
        
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
            logger.info("실행 순서가 비어있어 fallback_manager로 라우팅합니다.")
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
        
    
    async def process_query(self, query: str, session_id: Optional[str] = None, 
                           stock_code: Optional[str] = None, stock_name: Optional[str] = None,
                           **kwargs) -> Dict[str, Any]:
        """
        사용자 쿼리를 처리하는 메인 메서드

        Args:
            query: 사용자 쿼리
            session_id: 세션 ID (선택적)
            stock_code: 종목 코드 (선택적)
            stock_name: 종목명 (선택적)
            **kwargs: 추가 인자
                is_follow_up: 후속질문 여부
                streaming_callback: 스트리밍 콜백 함수
                chat_session_id: 채팅 세션 ID
                conversation_history: 대화 이력

        Returns:
            처리 결과를 담은 딕셔너리
        """
        try:
            if not self.graph:
                raise ValueError("그래프가 초기화되지 않았습니다. register_agents 메서드를 먼저 호출하세요.")
            
                
            # 세션 ID 설정 (추적 ID로 사용)
            trace_id = session_id or datetime.now().strftime("%Y%m%d%H%M%S")
            chat_session_id = kwargs.get("chat_session_id", None)
            logger.info(f"[process_query] chat_session_id: {chat_session_id}")

            # 후속질문 여부 추출
            # is_follow_up = kwargs.get("is_follow_up", False)
            # logger.info(f"[process_query] 후속질문 여부: {is_follow_up}")

            # 이전 에이전트 결과물 추출
            agent_results = {}
            # if is_follow_up:
            #     agent_results = kwargs.get("agent_results", {})

            # 스트리밍 콜백 함수 추출 및 클래스 멤버로 저장
            streaming_callback = kwargs.get("streaming_callback")
            if streaming_callback and callable(streaming_callback):
                logger.info(f"[process_query] 스트리밍 콜백 함수가 전달되었습니다: {streaming_callback.__name__ if hasattr(streaming_callback, '__name__') else '이름 없는 함수'}")
                self._streaming_callback = streaming_callback  # 클래스 멤버로 저장
            
            # 초기 상태 설정 (streaming_callback을 제외한 다른 모든 키워드 인자 사용)
            kwargs_copy = {k: v for k, v in kwargs.items() if k != "streaming_callback"}
            
            initial_state: AgentState = {
                "query": query,
                "session_id": trace_id,
                "chat_session_id": chat_session_id,
                "stock_code": stock_code,
                "stock_name": stock_name,
                #"is_follow_up": is_follow_up,  # 후속질문 여부를 상태에 명시적으로 추가
                "errors": [],
                "processing_status": {},
                "retrieved_data": {},  # 검색 결과를 담을 딕셔너리
                "agent_results": agent_results,   # 이전 에이전트 결과를 넣어둠.
                "parallel_search_executed": False,  # 병렬 검색 실행 여부 초기화
                **kwargs_copy  # streaming_callback을 제외한 나머지 인자
            }
            chat_history = kwargs.get("conversation_history", [])
            if chat_history:
                logger.info(f"[process_query] 과거 대화 이력: {chat_history[:300]}")
            #logger.info(f"[process_query] initial_state: {initial_state['stock_code']}, {initial_state['agent_results']}")
            # 재시작 플래그 확인
            restart_from_error = kwargs.get("restart_from_error", False)
            if restart_from_error:
                logger.info(f"[process_query] 오류 후 재시작 감지됨. 이전 오류: {kwargs.get('previous_error', '알 수 없음')}")
                initial_state["restart_from_error"] = True
                initial_state["previous_error"] = kwargs.get("previous_error", "")
                
                # LangSmith 타임스탬프 오류인 경우 특별 처리
                if kwargs.get("previous_error") and "invalid 'dotted_order'" in kwargs.get("previous_error") and "earlier than parent timestamp" in kwargs.get("previous_error"):
                    logger.warning("LangSmith 타임스탬프 오류 감지됨. 폴백 메커니즘을 트리거합니다.")
                    # 오류 정보를 담은 상태로 폴백 매니저 에이전트를 직접 호출
                    try:
                        if "fallback_manager" in self.agents:
                            fallback_state = {
                                "query": query,
                                "stock_code": stock_code,
                                "stock_name": stock_name,
                                "session_id": session_id or "error_session",
                                "error": str(e),
                                "errors": [{
                                    "agent": "stock_analysis_graph",
                                    "error": str(e),
                                    "type": "LangSmithTimestampError",
                                    "timestamp": datetime.now()
                                }]
                            }
                            result = await self.agents["fallback_manager"].process(fallback_state)
                            return result
                    except Exception as fallback_error:
                        logger.error(f"폴백 매니저 호출 중 추가 오류 발생: {str(fallback_error)}")
                
          
            # 세션별 상태 초기화
            async with self.state_lock:
                self.current_state[session_id] = initial_state.copy()
                
            # 그래프 시작 콜백 실행
            await self._execute_callbacks("graph_start", "graph", initial_state)
                
            # LangGraph 호출
            trace_id = f"{session_id}_{int(time.time())}"  # 고유 추적 ID 생성
            logger.info(f"[process_query] 그래프 호출 시작 - trace_id: {trace_id}")
            
            # AgentState 타입에 conversation_history가 포함되도록 상태 관리
            # StateGraph 타입 제약 때문에 발생하는 문제 해결
            try:
                # 주의: streaming_callback은 직렬화가 불가능하므로 
                # _create_wrapped_process에서 각 에이전트 호출 시 추가됩니다.
                # 여기서는 initial_state에 추가하지 않습니다.
                
                result = await self.graph.ainvoke(
                    initial_state,
                    config={
                        "configurable": {"thread_id": trace_id}, 
                        "max_concurrency": 4,  # 병렬 처리 동시성 설정
                        "recursion_limit": 25  # 재귀 제한 설정
                    }
                )
            except Exception as e:
                logger.error(f"[process_query] 그래프 호출 중 오류 발생: {str(e)}", exc_info=True)
                # 오류가 타입 관련 문제인 경우 conversation_history를 상태에서 제거하고 다시 시도
                raise
                
            logger.info(f"[process_query] 그래프 호출 완료 - trace_id: {trace_id}")
            
                
            # 그래프 종료 콜백 실행
            await self._execute_callbacks("graph_end", "graph", result)
            
            # 상태 업데이트
            async with self.state_lock:
                if trace_id in self.current_state:
                    self.current_state[trace_id].update(result)
                    self.current_state[trace_id]['completed'] = True
                    self.current_state[trace_id]['completion_time'] = time.time()
            
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
                
            # LangSmith 타임스탬프 오류인 경우, 폴백 메커니즘 트리거
            if "invalid 'dotted_order'" in str(e) and "earlier than parent timestamp" in str(e):
                logger.warning("LangSmith 타임스탬프 오류 감지됨. 폴백 메커니즘을 트리거합니다.")
                # 오류 정보를 담은 상태로 폴백 매니저 에이전트를 직접 호출
                try:
                    if "fallback_manager" in self.agents:
                        fallback_state = {
                            "query": query,
                            "stock_code": stock_code,
                            "stock_name": stock_name,
                            "session_id": session_id or "error_session",
                            "error": str(e),
                            "errors": [{
                                "agent": "stock_analysis_graph",
                                "error": str(e),
                                "type": "LangSmithTimestampError",
                                "timestamp": datetime.now()
                            }]
                        }
                        result = await self.agents["fallback_manager"].process(fallback_state)
                        return result
                except Exception as fallback_error:
                    logger.error(f"폴백 매니저 호출 중 추가 오류 발생: {str(fallback_error)}")
                
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

    def get_session_state(self, session_id: str) -> Dict[str, Any]:
        """
        특정 세션의 현재 상태를 반환합니다.
        
        Args:
            session_id: 세션 ID
            
        Returns:
            세션 상태 정보 (없으면 빈 딕셔너리)
        """
        return self.current_state.get(session_id, {})

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