"""
여러 검색 에이전트를 병렬로 실행하는 에이전트

이 모듈은 여러 검색 관련 에이전트(텔레그램, 리포트, 재무, 산업)를
비동기 방식으로 병렬 실행하여 성능을 향상시킵니다.
"""

import asyncio
import copy
from typing import Dict, Any, List, Optional
from datetime import datetime
import time
from loguru import logger

from stockeasy.models.agent_io import AgentState
from stockeasy.agents.base import BaseAgent


class ParallelSearchAgent(BaseAgent):
    """
    여러 검색 에이전트를 병렬로 실행하는 에이전트
    """
    
    def __init__(self, agents: Dict[str, BaseAgent]):
        """
        초기화
        
        Args:
            agents: 검색 에이전트 이름과 인스턴스의 딕셔너리
        """
        self.agents = agents
        self.search_agent_names = [
            "telegram_retriever", 
            "report_analyzer", 
            "financial_analyzer", 
            "industry_analyzer"
        ]
    
    async def process(self, state: AgentState) -> AgentState:
        """
        여러 검색 에이전트를 병렬로 실행합니다.
        
        Args:
            state: 현재 에이전트 상태
            
        Returns:
            업데이트된 상태
        """
        start_time = time.time()
        logger.info(f"ParallelSearchAgent 병렬 처리 시작")
        
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
        
        # 실행할 검색 에이전트 목록 생성
        search_agents = []
        for agent_name in self.search_agent_names:
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
        
        # 각 에이전트를 실행할 비동기 작업 생성
        tasks = []
        for name, agent in search_agents:
            # 처리 상태 초기화 - 우선 processing 상태로 설정
            state["processing_status"][name] = "processing"
            # 비동기 작업 생성
            tasks.append(self._run_agent(name, agent, copy.deepcopy(state)))
        
        # 병렬로 모든 에이전트 실행
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 결과 처리를 위한 변수
        success_count = 0
        failure_count = 0
        
        # 결과 처리
        for (name, _), result in zip(search_agents, results):
            if isinstance(result, Exception):
                # 오류 처리
                failure_count += 1
                logger.error(f"에이전트 {name} 실행 중 오류 발생: {str(result)}")
                if "errors" not in state:
                    state["errors"] = []
                state["errors"].append({
                    "agent": name,
                    "error": str(result),
                    "type": type(result).__name__,
                    "timestamp": datetime.now()
                })
                state["processing_status"][name] = "failed"
            else:
                # 성공적인 결과 병합
                success_count += 1
                logger.info(f"에이전트 {name} 실행 완료")
                
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
                        #logger.info(f"에이전트 {agent_name}의 agent_results 병합 완료")
        
        # agent_results가 없으면 빈 딕셔너리 초기화
        if "agent_results" not in state:
            state["agent_results"] = {}
            logger.warning("agent_results가 없어 빈 딕셔너리로 초기화합니다.")
        else:
            logger.info(f"병합된 agent_results 키: {list(state['agent_results'].keys())}")
        
        # 모든 에이전트가 실패했는지 확인
        if search_agents and failure_count == len(search_agents):
            logger.warning("모든 검색 에이전트 실행이 실패했습니다.")
            state["all_search_agents_failed"] = True
        
        # 검색 결과가 비어있는지 확인
        has_data = False
        for key, value in state["retrieved_data"].items():
            if key in ["telegram_messages", "report_data", "financial_data", "industry_data"] and value:
                has_data = True
                logger.info(f"검색 결과 있음: {key}에 {len(value)}개 항목")
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
                "has_data": has_data
            },
            "metadata": {
                "timestamp": datetime.now().isoformat(),
                "version": "1.0"
            }
        }
        
        logger.info(f"ParallelSearchAgent 병렬 처리 완료. 실행 시간: {execution_time:.2f}초, 성공: {success_count}, 실패: {failure_count}")
        
        return state
    
    async def _run_agent(self, name: str, agent: BaseAgent, state: AgentState) -> AgentState:
        """
        개별 에이전트를 실행하는 도우미 함수
        
        Args:
            name: 에이전트 이름
            agent: 에이전트 인스턴스
            state: 상태의 복사본(깊은 복사)
            
        Returns:
            에이전트 실행 결과
        """
        try:
            logger.info(f"에이전트 {name} 실행 시작")
            start_time = time.time()
            result = await agent.process(state)
            end_time = time.time()
            logger.info(f"에이전트 {name} 실행 완료. 시간: {end_time - start_time:.2f}초")
            return result
        except Exception as e:
            logger.error(f"에이전트 {name} 실행 중 오류: {str(e)}")
            raise 