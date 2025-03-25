"""
여러 검색 에이전트를 병렬로 실행하는 에이전트

이 모듈은 여러 검색 관련 에이전트(텔레그램, 리포트, 재무, 산업)를
비동기 방식으로 병렬 실행하여 성능을 향상시킵니다.
"""

import asyncio
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
            if should_execute and agent_name in self.agents:
                search_agents.append((agent_name, self.agents[agent_name]))
        
        logger.info(f"병렬로 실행할 에이전트: {[name for name, _ in search_agents]}")
        
        # 각 에이전트를 실행할 비동기 작업 생성
        tasks = []
        for name, agent in search_agents:
            # 처리 상태 초기화
            state["processing_status"][name] = "processing"
            # 비동기 작업 생성
            tasks.append(self._run_agent(name, agent, state))
        
        # 병렬로 모든 에이전트 실행
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 결과 처리
            for (name, _), result in zip(search_agents, results):
                if isinstance(result, Exception):
                    # 오류 처리
                    logger.error(f"에이전트 {name} 실행 중 오류 발생: {str(result)}")
                    state["errors"].append({
                        "agent": name,
                        "error": str(result),
                        "type": type(result).__name__,
                        "timestamp": datetime.now()
                    })
                    state["processing_status"][name] = "failed"
                else:
                    # 성공적인 결과 병합
                    logger.info(f"에이전트 {name} 실행 완료")
                    state["processing_status"][name] = result.get("processing_status", {}).get(name, "completed")
                    
                    # 검색 결과 병합
                    if "retrieved_data" in result:
                        for key, value in result["retrieved_data"].items():
                            if key not in state["retrieved_data"]:
                                state["retrieved_data"][key] = value
                            elif isinstance(state["retrieved_data"][key], list) and isinstance(value, list):
                                state["retrieved_data"][key].extend(value)
        else:
            logger.info("병렬로 실행할 에이전트가 없습니다.")
        
        end_time = time.time()
        execution_time = end_time - start_time
        logger.info(f"ParallelSearchAgent 병렬 처리 완료. 실행 시간: {execution_time:.2f}초")
        
        return state
    
    async def _run_agent(self, name: str, agent: BaseAgent, state: AgentState) -> AgentState:
        """
        개별 에이전트를 실행하는 도우미 함수
        
        Args:
            name: 에이전트 이름
            agent: 에이전트 인스턴스
            state: 현재 상태의 복사본
            
        Returns:
            에이전트 실행 결과
        """
        # 각 에이전트용 상태 복사 (깊은 복사를 사용하지 않고 필요한 부분만 복사)
        agent_state = state.copy()
        
        try:
            logger.info(f"에이전트 {name} 실행 시작")
            start_time = time.time()
            result = await agent.process(agent_state)
            end_time = time.time()
            logger.info(f"에이전트 {name} 실행 완료. 시간: {end_time - start_time:.2f}초")
            return result
        except Exception as e:
            logger.error(f"에이전트 {name} 실행 중 오류: {str(e)}")
            raise 