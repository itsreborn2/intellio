"""
여러 검색 에이전트를 병렬로 실행하는 에이전트

이 모듈은 여러 검색 관련 에이전트(텔레그램, 리포트, 재무, 산업)를
비동기 방식으로 병렬 실행하여 성능을 향상시킵니다.
"""

import asyncio
import copy
import csv
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

import psutil
from loguru import logger

from stockeasy.agents.base import BaseAgent
from stockeasy.models.agent_io import AgentState

# 메모리 추적 On/Off 설정 변수
ENABLE_MEMORY_TRACKING = os.getenv("ENABLE_MEMORY_TRACKING", "true").lower() == "true"


class ParallelSearchAgent(BaseAgent):
    """
    여러 검색 에이전트를 병렬로 실행하는 에이전트
    """

    def __init__(self, agents: Dict[str, BaseAgent], graph=None):
        """
        초기화

        Args:
            agents: 검색 에이전트 이름과 인스턴스의 딕셔너리
            graph: 그래프 인스턴스 (콜백 실행용)
        """
        self.agents = agents
        self.graph = graph  # 그래프 인스턴스 저장
        self.search_agent_names = [
            "telegram_retriever",
            "revenue_breakdown",
            "report_analyzer",
            "financial_analyzer",
            "industry_analyzer",
            "confidential_analyzer",
            "technical_analyzer",
            "web_search",
        ]

    def get_memory_usage(self):
        """메모리 사용량을 반환합니다. (가벼운 버전)"""
        try:
            process = psutil.Process(os.getpid())
            memory_info = process.memory_info()
            return {
                "rss": memory_info.rss / (1024 * 1024),  # RSS in MB
                "vms": memory_info.vms / (1024 * 1024),  # VMS in MB
                "gc_objects": 0,  # 무거운 작업 제거
                "state_size": 0,  # parallel agent에서는 state_size를 별도로 계산하지 않음
            }
        except Exception as e:
            logger.error(f"메모리 사용량 체크 중 오류: {str(e)}")
            return {"rss": 0, "vms": 0, "gc_objects": 0, "state_size": 0}

    async def log_memory_to_csv(self, phase: str, memory_data: Dict[str, Any], agent_name: str = "parallel_search", session_id: str = "unknown"):
        """메모리 사용량을 CSV 파일에 비동기로 기록합니다."""
        if not ENABLE_MEMORY_TRACKING:
            return

        try:
            csv_dir = Path("stockeasy/local_cache/memory_tracking")
            csv_dir.mkdir(parents=True, exist_ok=True)
            csv_path = csv_dir / "memory_usage.csv"

            # CSV 파일 존재 여부 확인
            file_exists = csv_path.exists()

            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")

            # 비동기 파일 작업을 위한 함수
            async def write_memory_csv():
                # CSV 파일에 데이터 추가 (이벤트 루프 차단 방지)
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, lambda: self._write_memory_to_csv(csv_path, file_exists, timestamp, session_id, agent_name, phase, memory_data))

            # 비동기 CSV 작성 실행
            await write_memory_csv()

        except Exception as e:
            logger.error(f"메모리 CSV 로깅 중 오류: {str(e)}")

    def _write_memory_to_csv(self, path, exists, timestamp, session_id, agent_name, phase, memory_data):
        """실제 CSV 파일 작성 함수 (이벤트 루프 외부에서 실행)"""
        try:
            with open(path, "a", newline="") as csvfile:
                fieldnames = ["timestamp", "pid", "worker_id", "thread_info", "session_id", "agent", "phase", "rss_mb", "vms_mb", "gc_objects", "state_size"]
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

                writer.writerow(
                    {
                        "timestamp": timestamp,
                        "pid": os.getpid(),
                        "worker_id": worker_id,
                        "thread_info": thread_info,
                        "session_id": session_id,
                        "agent": agent_name,
                        "phase": phase,
                        "rss_mb": round(memory_data["rss"], 2),
                        "vms_mb": round(memory_data["vms"], 2),
                        "gc_objects": memory_data["gc_objects"],
                        "state_size": memory_data["state_size"],
                    }
                )
        except Exception as e:
            logger.error(f"CSV 파일 작성 중 오류: {str(e)}")

    async def process(self, state: AgentState) -> AgentState:
        """
        여러 검색 에이전트를 병렬로 실행합니다.

        Args:
            state: 현재 에이전트 상태

        Returns:
            업데이트된 상태
        """
        start_time = time.time()
        logger.info("ParallelSearchAgent 병렬 처리 시작")

        # 그래프에 병렬 검색 에이전트 자체의 처리 상태 업데이트
        session_id = state.get("session_id")
        if self.graph and session_id and hasattr(self.graph, "current_state") and self.graph.current_state is not None:
            try:
                async with self.graph.state_lock:
                    # current_state가 clear된 상태인지 확인
                    if self.graph.current_state is None:
                        logger.warning("그래프의 current_state가 이미 정리되었습니다.")
                        return state
                        
                    if session_id not in self.graph.current_state:
                        self.graph.current_state[session_id] = {}

                    if "processing_status" not in self.graph.current_state[session_id]:
                        self.graph.current_state[session_id]["processing_status"] = {}

                    # 병렬 검색 에이전트 자체의 상태 업데이트
                    self.graph.current_state[session_id]["processing_status"]["parallel_search"] = "processing"
                    # logger.debug(f"ParallelSearchAgent: 처리 시작 상태를 그래프에 업데이트")
            except (AttributeError, KeyError) as e:
                logger.warning(f"그래프 상태가 이미 정리되었거나 없습니다: {str(e)}")
            except Exception as e:
                logger.error(f"그래프 상태 업데이트 중 오류 발생 (병렬 검색 에이전트): {str(e)}")

        # 실행 계획에서 어떤 에이전트를 실행할지 확인
        execution_plan = state.get("execution_plan", {})
        execution_order = execution_plan.get("execution_order", [])

        # 데이터 요구사항 확인
        data_requirements = state.get("data_requirements", {})

        # retrieved_data가 없으면 초기화
        if "retrieved_data" not in state:
            state["retrieved_data"] = {}

        # processing_status가 없으면 초기화
        if "processing_status" not in state:
            state["processing_status"] = {}

        # 커스텀 프롬프트 템플릿 정보 확인 및 복사
        custom_prompt_templates = {}
        if "custom_prompt_template" in state:
            # 현재 에이전트에 적용된 템플릿이 있으면 모든 하위 에이전트에 전달
            for agent_name in self.search_agent_names:
                custom_prompt_templates[agent_name] = state["custom_prompt_template"]
            logger.info("현재 커스텀 프롬프트 템플릿을 모든 검색 에이전트에 적용합니다.")

        # 이미 custom_prompt_templates가 있으면 병합
        if "custom_prompt_templates" in state:
            custom_prompt_templates.update(state["custom_prompt_templates"])
            logger.info(f"기존 커스텀 프롬프트 템플릿 병합 완료. 적용 에이전트: {list(custom_prompt_templates.keys())}")

        # 실행할 검색 에이전트 목록 생성
        search_agents = []
        for agent_name in self.search_agent_names:
            # technical_analyzer는 이미 실행되었으므로 건너뜀
            if agent_name == "technical_analyzer":
                logger.info(f"기술적 분석은 이미 완료되어 건너뜁니다: {agent_name}")
                continue

            # 이미 실행 완료된 에이전트는 건너뜀
            if state.get("processing_status", {}).get(agent_name) in ["completed", "completed_with_default_plan", "completed_no_data"]:
                logger.info(f"에이전트 {agent_name}은 이미 실행 완료되었습니다. 건너뜁니다.")
                continue

            # 실행 계획이나 데이터 요구사항에 따라 실행 여부 결정
            should_execute = False

            # 실행 계획 기반 확인
            if agent_name in execution_order:
                should_execute = True

            # 데이터 요구사항 기반 확인
            if data_requirements:
                if agent_name == "telegram_retriever" and data_requirements.get("telegram_needed", False):
                    should_execute = True
                elif agent_name == "report_analyzer" and data_requirements.get("reports_needed", False):
                    should_execute = True
                elif agent_name == "financial_analyzer" and data_requirements.get("financial_statements_needed", False):
                    should_execute = True
                elif agent_name == "industry_analyzer" and data_requirements.get("industry_data_needed", False):
                    should_execute = True
                elif agent_name == "confidential_analyzer" and data_requirements.get("confidential_data_needed", False):
                    # logger.info(f"비공개 자료 필요: {agent_name}, {data_requirements}")
                    should_execute = True
                elif agent_name == "revenue_breakdown" and data_requirements.get("revenue_data_needed", False):
                    # logger.info(f"매출 및 수주 현황 데이터 필요: {agent_name}, {data_requirements}")
                    should_execute = True
                elif agent_name == "web_search" and data_requirements.get("web_search_needed", False):
                    # logger.info(f"웹 검색 데이터 필요: {agent_name}, {data_requirements}")
                    should_execute = True
                elif agent_name == "technical_analyzer" and data_requirements.get("technical_analysis_needed", False):
                    logger.info(f"기술적 분석 데이터 필요: {agent_name}, {data_requirements}")
                    should_execute = True
            # logger.info(f"데이터 요구사항: {should_execute} {agent_name}, {data_requirements}")
            # 에이전트가 존재하고 실행이 필요한 경우 목록에 추가
            if should_execute and agent_name in self.agents and self.agents[agent_name]:
                search_agents.append((agent_name, self.agents[agent_name]))

        logger.info(f"병렬로 실행할 에이전트: {[name for name, _ in search_agents]}")

        # 실행할 에이전트가 없는 경우를 명시적으로 처리
        if not search_agents:
            logger.warning("병렬로 실행할 에이전트가 없습니다.")
            # 처리 상태 표시를 위한 플래그 추가 (이 플래그는 반드시 설정되어야 함)
            state["parallel_search_executed"] = True
            # 빈 검색 결과 표시
            state["retrieved_data"]["no_search_agents_executed"] = True
            return state

        # 상태 업데이트를 위한 콜백 함수 정의 - 원본 state를 직접 업데이트
        def update_processing_status(agent_name: str, status: str) -> None:
            """원본 state의 processing_status를 업데이트하는 콜백 함수"""
            state["processing_status"][agent_name] = status

        def update_agent_results(agent_name: str, result: Dict[str, Any]) -> None:
            """원본 state의 agent_results를 업데이트하는 콜백 함수"""
            if "agent_results" not in state:
                state["agent_results"] = {}
            state["agent_results"][agent_name] = result

        def update_retrieved_data(agent_name: str, data: Any) -> None:
            """원본 state의 retrieved_data를 업데이트하는 콜백 함수"""
            if "retrieved_data" not in state:
                state["retrieved_data"] = {}
            state["retrieved_data"][agent_name] = data

        def update_metrics(agent_name: str, metrics: Dict[str, Any]) -> None:
            """원본 state의 metrics를 업데이트하는 콜백 함수"""
            if "metrics" not in state:
                state["metrics"] = {}
            state["metrics"][agent_name] = metrics

        # 각 에이전트를 실행할 비동기 작업 생성
        tasks = []
        for name, agent in search_agents:
            # 처리 상태 초기화 - 우선 processing 상태로 설정
            state["processing_status"][name] = "processing"

            # shallow copy 사용 - 읽기 전용 데이터만 공유
            agent_state = copy.copy(state)

            # 에이전트가 수정하는 데이터는 빈 상태로 초기화 (콜백을 통해서만 업데이트)
            agent_state["retrieved_data"] = {}
            agent_state["agent_results"] = {}
            agent_state["metrics"] = {}
            agent_state["errors"] = []

            # 콜백 함수들 추가 - 원본 state를 참조
            agent_state["update_processing_status"] = update_processing_status
            agent_state["update_agent_results"] = update_agent_results
            agent_state["update_retrieved_data"] = update_retrieved_data
            agent_state["update_metrics"] = update_metrics
            # 에이전트 이름 전달
            agent_state["agent_name"] = name

            # 커스텀 프롬프트 템플릿 정보 추가
            if custom_prompt_templates:
                agent_state["custom_prompt_templates"] = custom_prompt_templates
            # 비동기 작업 생성
            tasks.append(self._run_agent(name, agent, agent_state))

        # 병렬로 모든 에이전트 실행
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 결과 처리를 위한 변수
        success_count = 0
        failure_count = 0

        # 결과 처리
        # result는 agent_state
        for (name, _), result in zip(search_agents, results):
            if isinstance(result, Exception):
                # 오류 처리
                failure_count += 1
                logger.error(f"에이전트 {name} 실행 중 오류 발생: {str(result)}")
                if "errors" not in state:
                    state["errors"] = []
                state["errors"].append({"agent": name, "error": str(result), "type": type(result).__name__, "timestamp": datetime.now()})
                state["processing_status"][name] = "failed"
            else:
                # 성공적인 결과 병합
                success_count += 1
                # logger.info(f"에이전트 {name} 실행 완료")

                # 처리 상태 업데이트
                if "processing_status" in result:
                    for agent_name, status in result["processing_status"].items():
                        state["processing_status"][agent_name] = status
                else:
                    state["processing_status"][name] = "completed"

                # 검색 결과 병합
                if "retrieved_data" in result:
                    for key, value in result["retrieved_data"].items():
                        if key not in state["retrieved_data"]:
                            state["retrieved_data"][key] = value
                        elif isinstance(state["retrieved_data"][key], list) and isinstance(value, list):
                            state["retrieved_data"][key].extend(value)

                # agent_results 병합 (중요: 이 키가 knowledge_integrator와 summarizer에서 사용됨)
                if "agent_results" in result:
                    if "agent_results" not in state:
                        state["agent_results"] = {}

                    # agent_results 딕셔너리 병합
                    for agent_name, agent_result in result["agent_results"].items():
                        state["agent_results"][agent_name] = agent_result
                        # logger.info(f"에이전트 {agent_name}의 agent_results 병합 완료")

        # agent_results가 없으면 빈 딕셔너리 초기화
        if "agent_results" not in state:
            state["agent_results"] = {}
            logger.warning("agent_results가 없어 빈 딕셔너리로 초기화합니다.")
        # else:
        #     logger.info(f"병합된 agent_results 키: {list(state['agent_results'].keys())}")

        # 모든 에이전트가 실패했는지 확인
        if search_agents and failure_count == len(search_agents):
            logger.warning("모든 검색 에이전트 실행이 실패했습니다.")
            state["all_search_agents_failed"] = True

        # 검색 결과가 비어있는지 확인
        has_data = False
        for key, value in state["retrieved_data"].items():
            if key in ["telegram_messages", "report_data", "financial_data", "industry_data", "confidential_data", "web_search_results", "technical_analysis_data"] and value:
                has_data = True
                # logger.info(f"검색 결과 있음: {key}에 {len(value)}개 항목")
                break

        if not has_data:
            logger.warning("검색 결과가 없습니다.")
            # 빈 검색 결과 표시
            state["retrieved_data"]["no_data_found"] = True

        # 각 에이전트의 상태 로깅
        logger.info(f"에이전트 처리 상태: {state['processing_status']}")

        # 검색 데이터 키 로깅
        logger.info(f"검색 데이터 키: {list(state['retrieved_data'].keys())}")

        # 처리 완료 플래그 설정 (중요: 이 플래그가 라우팅 결정에 사용됨)
        state["parallel_search_executed"] = True

        # 실행 시간 계산
        end_time = time.time()
        execution_time = end_time - start_time

        # 병렬 검색 에이전트 자체의 결과도 agent_results에 추가
        if "agent_results" not in state:
            state["agent_results"] = {}

        # 병렬 검색 에이전트의 결과 정보 저장
        state["agent_results"]["parallel_search"] = {
            "data": {
                "executed_agents": [name for name, _ in search_agents],
                "success_count": success_count,
                "failure_count": failure_count,
                "execution_time": execution_time,
                "has_data": has_data,
            },
            "metadata": {"timestamp": datetime.now().isoformat(), "version": "1.0"},
        }

        # 병렬 검색 에이전트 상태를 '완료'로 설정
        state["processing_status"]["parallel_search"] = "completed"

        # 그래프 상태 업데이트 - 병렬 검색 완료
        session_id = state.get("session_id")
        if self.graph and session_id and hasattr(self.graph, "current_state"):
            try:
                async with self.graph.state_lock:
                    if session_id not in self.graph.current_state:
                        self.graph.current_state[session_id] = {}

                    if "processing_status" not in self.graph.current_state[session_id]:
                        self.graph.current_state[session_id]["processing_status"] = {}

                    # 병렬 검색 에이전트 자체의 상태 업데이트
                    self.graph.current_state[session_id]["processing_status"]["parallel_search"] = "completed"
                    # logger.debug(f"ParallelSearchAgent: 처리 완료 상태를 그래프에 업데이트")
            except Exception as e:
                logger.error(f"그래프 상태 업데이트 중 오류 발생 (병렬 검색 에이전트): {str(e)}")

        logger.info(f"ParallelSearchAgent 병렬 처리 완료. 실행 시간: {execution_time:.2f}초, 성공: {success_count}, 실패: {failure_count}")

        return state

    def write_to_csv_full_graph_time(self, event_type: str, agent_name: str, note: Optional[str] = None, session_id: Optional[str] = None) -> None:
        # CSV 파일 경로 설정
        log_dir = os.path.join("stockeasy", "local_cache")
        os.makedirs(log_dir, exist_ok=True)

        date_str = datetime.now().strftime("%Y%m%d")
        csv_path = os.path.join(log_dir, f"log_agent_time_{date_str}.csv")

        # 파일 존재 여부 확인 (헤더 추가 여부 결정)
        file_exists = os.path.isfile(csv_path)

        # 현재 날짜와 시간
        current_datetime = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # PID 정보 가져오기
        current_pid = os.getpid()

        # CSV 파일에 데이터 추가
        with open(csv_path, "a", newline="", encoding="utf-8-sig") as csvfile:
            fieldnames = ["일자", "pid", "session_id", "event_type", "agent_name", "note"]
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

            # 파일이 새로 생성된 경우 헤더 작성
            if not file_exists:
                writer.writeheader()
            writer.writerow({"일자": current_datetime, "pid": current_pid, "session_id": session_id or "unknown", "event_type": event_type, "agent_name": agent_name, "note": note})

    async def _run_agent(self, name: str, agent: BaseAgent, state: AgentState) -> AgentState:
        """
        단일 에이전트를 비동기적으로 실행합니다.

        Args:
            name: 에이전트 이름
            agent: 에이전트 인스턴스
            state: 현재 에이전트 상태

        Returns:
            에이전트 실행 후 상태
        """
        session_id = state.get("session_id", "unknown")
        agent_start_time = time.time()  # 에이전트 시작 시간 기록

        # 메모리 추적이 활성화된 경우에만 메모리 체크 수행
        pre_memory = None
        if ENABLE_MEMORY_TRACKING:
            # 에이전트 시작 전 메모리 사용량 체크 (동기로 빠르게)
            pre_memory = self.get_memory_usage()  # 동기 호출로 변경 (빠름)
            logger.info(f"[메모리체크-시작] {name} - RSS: {pre_memory['rss']:.2f}MB, VMS: {pre_memory['vms']:.2f}MB")
            # 백그라운드로 CSV 로깅
            asyncio.create_task(self.log_memory_to_csv("before", pre_memory, name, session_id))

        try:
            if self.graph:
                # 그래프에 처리 상태 업데이트 (에이전트 시작)
                if session_id and hasattr(self.graph, "current_state"):
                    try:
                        async with self.graph.state_lock:
                            if session_id not in self.graph.current_state:
                                self.graph.current_state[session_id] = {}

                            if "processing_status" not in self.graph.current_state[session_id]:
                                self.graph.current_state[session_id]["processing_status"] = {}

                            self.graph.current_state[session_id]["processing_status"][name] = "processing"
                            logger.debug(f"ParallelSearchAgent: {name} 처리 시작 상태를 그래프에 업데이트")
                    except Exception as e:
                        logger.error(f"그래프 상태 업데이트 중 오류 발생 (병렬 검색 에이전트): {str(e)}")

            # 에이전트 상태 업데이트 (콜백 함수 사용)
            if "update_processing_status" in state and "agent_name" in state:
                state["update_processing_status"](state["agent_name"], "started")

            # logger.info(f"에이전트 {name} 실행 시작")
            await asyncio.to_thread(self.write_to_csv_full_graph_time, "agent_start", name, None, session_id)
            result = await agent.process(state)
            # logger.info(f"에이전트 {name} 실행 완료")
            await asyncio.to_thread(self.write_to_csv_full_graph_time, "agent_end", name, None, session_id)

            # 에이전트 실행 시간 계산
            agent_end_time = time.time()
            execution_time = agent_end_time - agent_start_time

            # 결과에 에이전트 이름 추가
            result["last_agent"] = name

            # 처리 상태가 없는 경우 명시적으로 추가
            if "processing_status" not in result:
                result["processing_status"] = {}

            # 완료 상태로 설정 (혹시 set되지 않은 경우)
            if name not in result["processing_status"]:
                result["processing_status"][name] = "completed"

            # 에이전트 상태 업데이트 (콜백 함수 사용)
            if "update_processing_status" in state and "agent_name" in state:
                state["update_processing_status"](state["agent_name"], "completed")

            if self.graph:
                # 그래프에 처리 상태 업데이트 (에이전트 완료)
                if session_id and hasattr(self.graph, "current_state"):
                    try:
                        async with self.graph.state_lock:
                            if session_id not in self.graph.current_state:
                                self.graph.current_state[session_id] = {}

                            if "processing_status" not in self.graph.current_state[session_id]:
                                self.graph.current_state[session_id]["processing_status"] = {}

                            self.graph.current_state[session_id]["processing_status"][name] = result["processing_status"][name]
                            logger.debug(f"ParallelSearchAgent: {name} {result['processing_status'][name]} 상태를 그래프에 업데이트")
                    except Exception as e:
                        logger.error(f"그래프 상태 업데이트 중 오류 발생 (병렬 검색 에이전트): {str(e)}")

            # 메모리 추적이 활성화된 경우에만 메모리 체크 수행
            # 단, 에이전트 실행 시간이 충분히 긴 경우에만 (0.5초 이상)
            if ENABLE_MEMORY_TRACKING and pre_memory and execution_time >= 0.5:
                # 백그라운드로 메모리 체크 및 로깅 수행
                async def background_memory_work():
                    try:
                        # 에이전트 완료 후 메모리 사용량 체크 (동기로 빠르게)
                        post_memory = self.get_memory_usage()
                        memory_diff = {
                            "rss": post_memory["rss"] - pre_memory["rss"],
                            "vms": post_memory["vms"] - pre_memory["vms"],
                            "gc_objects": 0,  # 무거운 작업 제거
                            "state_size": 0,
                        }

                        logger.info(f"[메모리체크-종료-백그라운드] {name} - 실행시간: {execution_time:.2f}s, RSS: {post_memory['rss']:.2f}MB, VMS: {post_memory['vms']:.2f}MB")
                        logger.info(f"[메모리변화-백그라운드] {name} - RSS: {memory_diff['rss']:.2f}MB, VMS: {memory_diff['vms']:.2f}MB")

                        # 비동기로 CSV 파일에 로깅
                        await self.log_memory_to_csv("after", post_memory, name, session_id)
                    except Exception as e:
                        logger.warning(f"[메모리체크-백그라운드] {name} - 메모리 체크 중 오류: {e}")

                # 백그라운드 작업 시작 (결과 기다리지 않음)
                asyncio.create_task(background_memory_work())
            elif ENABLE_MEMORY_TRACKING and execution_time < 0.5:
                logger.debug(f"[메모리체크-건너뛰기] {name} - 실행시간이 짧아서 메모리 체크 건너뜀 ({execution_time:.2f}s)")

            return result

        except Exception as e:
            # 에이전트 실행 시간 계산 (오류 시)
            agent_end_time = time.time()
            execution_time = agent_end_time - agent_start_time

            logger.error(f"에이전트 {name} 실행 중 오류 발생 (실행시간: {execution_time:.2f}s): {str(e)}", exc_info=True)

            # 메모리 추적이 활성화된 경우 오류 시 메모리 체크 (실행시간이 충분한 경우만)
            if ENABLE_MEMORY_TRACKING and execution_time >= 0.5:
                # 오류 발생 시 메모리 상태 체크 (background)
                async def background_error_memory():
                    try:
                        error_memory = self.get_memory_usage()
                        logger.error(f"[메모리체크-오류-백그라운드] {name} - 실행시간: {execution_time:.2f}s, RSS: {error_memory['rss']:.2f}MB, VMS: {error_memory['vms']:.2f}MB")
                        await self.log_memory_to_csv("error", error_memory, name, session_id)
                    except Exception as mem_e:
                        logger.warning(f"[메모리체크-오류-백그라운드] {name} - 오류 메모리 체크 중 오류: {mem_e}")

                # Background 작업 시작
                asyncio.create_task(background_error_memory())

            # 에러 상태 표시를 위한 처리 상태 업데이트
            state["processing_status"][name] = "failed"

            # 에이전트 상태 업데이트 (콜백 함수 사용)
            if "update_processing_status" in state and "agent_name" in state:
                state["update_processing_status"](state["agent_name"], "failed")

            if self.graph:
                # 그래프에 처리 상태 업데이트 (에이전트 실패)
                if session_id and hasattr(self.graph, "current_state"):
                    try:
                        async with self.graph.state_lock:
                            if session_id not in self.graph.current_state:
                                self.graph.current_state[session_id] = {}

                            if "processing_status" not in self.graph.current_state[session_id]:
                                self.graph.current_state[session_id]["processing_status"] = {}

                            self.graph.current_state[session_id]["processing_status"][name] = "failed"
                            logger.debug(f"ParallelSearchAgent: {name} 실패 상태를 그래프에 업데이트")
                    except Exception as e:
                        logger.error(f"그래프 상태 업데이트 중 오류 발생 (병렬 검색 에이전트): {str(e)}")

            # 예외를 다시 발생시켜 caller가 처리할 수 있도록 함
            raise
