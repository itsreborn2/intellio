"""
내부 테스트를 위한 서비스

이 모듈은 에이전트 테스트를 위한 서비스를 제공합니다.
"""

import time
import asyncio
from typing import Dict, List, Any, Optional, Tuple
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from stockeasy.services.rag_service import StockRAGService
from stockeasy.graph.agent_registry import get_graph, get_agents
from stockeasy.schemas.internal_test import (
    AgentPromptConfig, 
    VectorDBConfig,
    AgentProcessResult
)

class InternalTestService:
    """
    내부 테스트 서비스
    
    에이전트 프롬프트와 벡터DB 설정을 동적으로 변경하여 테스트할 수 있는 기능을 제공합니다.
    """
    
    def __init__(self, db: AsyncSession = None):
        """
        서비스 초기화
        
        Args:
            db: 데이터베이스 세션 객체 (선택적)
        """
        self.stock_rag_service = StockRAGService(db)
        self.db = db
        
    async def test_agents(
        self,
        question: str,
        stock_code: Optional[str] = None,
        stock_name: Optional[str] = None,
        session_id: Optional[str] = "test_session",
        agent_configs: Optional[List[AgentPromptConfig]] = None,
        vector_db_config: Optional[VectorDBConfig] = None,
        test_mode: Optional[str] = "full",
        single_agent_name: Optional[str] = None
    ) -> Tuple[str, List[AgentProcessResult], float, Optional[str]]:
        """
        에이전트 테스트 실행
        
        Args:
            question: 질문
            stock_code: 종목 코드 (선택적)
            stock_name: 종목명 (선택적)
            session_id: 세션 ID (선택적, 기본값은 test_session)
            agent_configs: 에이전트별 프롬프트 설정 (선택적)
            vector_db_config: 벡터 DB 설정 (선택적)
            test_mode: 테스트 모드 (full, selective, single)
            single_agent_name: 단일 테스트일 경우 에이전트 이름
            
        Returns:
            (최종 답변, 에이전트별 처리 결과 리스트, 전체 실행 시간, 에러 메시지)
        """
        start_time = time.time()
        agent_results = []
        error = None
        
        try:
            # 그래프 및 에이전트 가져오기
            graph = get_graph(self.db)
            agents = get_agents(self.db)
            
            # 단일 에이전트 테스트 모드인 경우
            if test_mode == "single" and single_agent_name and single_agent_name in agents:
                logger.info(f"단일 에이전트 테스트 모드: {single_agent_name}")
                
                # 선택된 에이전트만 가져오기
                agent = agents[single_agent_name]
                
                # 에이전트 실행 시간 측정
                start_agent_time = time.time()
                
                try:
                    # 에이전트 초기 상태 설정
                    agent_input = {
                        "query": question,
                        "stock_code": stock_code,
                        "stock_name": stock_name,
                        "session_id": session_id,
                    }
                    
                    # 에이전트 직접 호출
                    # 에이전트마다 인터페이스가 다를 수 있으므로 공통 방식으로 호출
                    if hasattr(agent, "invoke"):
                        agent_output = await agent.invoke(agent_input)
                    elif hasattr(agent, "run"):
                        agent_output = await agent.run(agent_input)
                    elif hasattr(agent, "process"):
                        agent_output = await agent.process(agent_input)
                    else:
                        raise ValueError(f"에이전트 {single_agent_name}에 호출 가능한 메서드가 없습니다.")
                    
                    # 실행 시간 계산
                    execution_time = time.time() - start_agent_time
                    
                    # 결과 저장
                    agent_result = AgentProcessResult(
                        agent_name=single_agent_name,
                        input=agent_input,
                        output=agent_output,
                        error=None,
                        execution_time=execution_time
                    )
                    agent_results.append(agent_result)
                    
                    # 응답 생성
                    if isinstance(agent_output, dict):
                        answer = agent_output.get('output', '') or agent_output.get('answer', '') or agent_output.get('result', '')
                        if not answer and 'content' in agent_output:
                            answer = agent_output['content']
                    else:
                        answer = str(agent_output)
                    
                    if not answer:
                        answer = f"에이전트 {single_agent_name}의 응답을 해석할 수 없습니다."
                    
                except Exception as e:
                    logger.error(f"단일 에이전트 {single_agent_name} 실행 중 오류 발생: {str(e)}", exc_info=True)
                    agent_result = AgentProcessResult(
                        agent_name=single_agent_name,
                        input=agent_input,
                        output={},
                        error=str(e),
                        execution_time=time.time() - start_agent_time
                    )
                    agent_results.append(agent_result)
                    answer = f"에이전트 {single_agent_name} 테스트 중 오류가 발생했습니다: {str(e)}"
                    error = str(e)
                
                # 총 실행 시간 계산
                total_execution_time = time.time() - start_time
                return answer, agent_results, total_execution_time, error
            
            # 전체 또는 선택적 테스트 모드
            # 에이전트 프롬프트 설정 적용 (임시)
            original_prompt_templates = {}
            # 비활성화된 에이전트 목록 저장
            disabled_agents = {}
            
            if agent_configs:
                for config in agent_configs:
                    agent_name = config.agent_name
                    if agent_name in agents:
                        agent = agents[agent_name]
                        # 프롬프트 템플릿 임시 저장
                        if hasattr(agent, 'prompt_template') and config.prompt_template:
                            original_prompt_templates[agent_name] = agent.prompt_template
                            agent.prompt_template_test = config.prompt_template
                            logger.info(f"에이전트 {agent_name} 프롬프트 템플릿 임시 저장: {config.prompt_template}")
                        # 에이전트 활성화/비활성화
                        if not config.enabled and agent_name in graph.agents:
                            # 그래프에서 에이전트 제거하여 비활성화
                            disabled_agents[agent_name] = graph.agents.pop(agent_name)
                            logger.info(f"에이전트 {agent_name} 비활성화 (테스트 중)")
                        elif config.enabled and agent_name not in graph.agents and agent_name in disabled_agents:
                            # 활성화 상태로 바뀐 경우 다시 추가
                            graph.agents[agent_name] = disabled_agents.pop(agent_name)
                            logger.info(f"에이전트 {agent_name} 활성화 (테스트 중)")
            
            # 벡터 DB 설정 적용 (임시)
            original_vector_db_settings = {}
            if vector_db_config:
                for agent_name, agent in agents.items():
                    if hasattr(agent, 'retriever') and agent.retriever:
                        # 네임스페이스 설정
                        if vector_db_config.namespace and hasattr(agent.retriever, 'namespace'):
                            original_vector_db_settings.setdefault(agent_name, {})
                            original_vector_db_settings[agent_name]['namespace'] = agent.retriever.namespace
                            agent.retriever.namespace = vector_db_config.namespace
                            
                        # 메타데이터 필터 설정
                        if vector_db_config.metadata_filter and hasattr(agent.retriever, 'metadata_filter'):
                            original_vector_db_settings.setdefault(agent_name, {})
                            original_vector_db_settings[agent_name]['metadata_filter'] = agent.retriever.metadata_filter
                            agent.retriever.metadata_filter = vector_db_config.metadata_filter
                            
                        # top_k 설정
                        if vector_db_config.top_k and hasattr(agent.retriever, 'top_k'):
                            original_vector_db_settings.setdefault(agent_name, {})
                            original_vector_db_settings[agent_name]['top_k'] = agent.retriever.top_k
                            agent.retriever.top_k = vector_db_config.top_k
            
            # 상태 추적을 위한 콜백 등록
            agent_inputs = {}
            agent_outputs = {}
            agent_times = {}
            
            # 커스텀 프롬프트 템플릿 저장
            custom_prompt_templates = {}
            if agent_configs:
                for config in agent_configs:
                    if config.prompt_template:
                        custom_prompt_templates[config.agent_name] = config.prompt_template
            
            # 에이전트 호출 시작 콜백
            def on_agent_start(agent_name, input_state):
                # 기존 상태 복사
                agent_inputs[agent_name] = input_state.copy()
                agent_times[agent_name] = {'start': time.time()}
                
                # 커스텀 프롬프트 템플릿 적용 (모든 에이전트)
                if custom_prompt_templates:
                    # ParallelSearchAgent가 실행하는 하위 에이전트들을 위한 템플릿 정보도 추가
                    input_state['custom_prompt_templates'] = custom_prompt_templates
                    logger.info(f"상태에 custom_prompt_templates 추가됨: {list(custom_prompt_templates.keys())}")
                    
                    # 현재 에이전트에 대한 커스텀 프롬프트가 있으면 직접 적용
                    if agent_name in custom_prompt_templates:
                        # 상태에 커스텀 프롬프트 템플릿 추가
                        agent_inputs[agent_name]['custom_prompt_template'] = custom_prompt_templates[agent_name]
                        
                        # 실제 실행되는 input_state에도 추가
                        input_state['custom_prompt_template'] = custom_prompt_templates[agent_name]
                        logger.info(f"에이전트 {agent_name}의 상태에 커스텀 프롬프트 템플릿 직접 추가됨")
            
            # 에이전트 호출 완료 콜백
            def on_agent_end(agent_name, output_state):
                agent_outputs[agent_name] = output_state.copy()
                agent_times[agent_name]['end'] = time.time()
            
            # 콜백 등록 (안전하게 처리)
            try:
                if hasattr(graph, 'register_callback'):
                    graph.register_callback('agent_start', on_agent_start)
                    graph.register_callback('agent_end', on_agent_end)
                    logger.info("에이전트 실행 콜백이 성공적으로 등록되었습니다.")
                else:
                    logger.warning("그래프에 register_callback 메서드가 없습니다. 에이전트 실행 상세 정보를 수집할 수 없습니다.")
            except Exception as e:
                logger.warning(f"콜백 등록 중 오류 발생: {str(e)}. 에이전트 실행 상세 정보를 수집할 수 없습니다.")
            
            # 실제 쿼리 처리
            logger.info(f"[내부 테스트] 쿼리 처리 시작: {question}")
            result = await self.stock_rag_service.analyze_stock(
                query=question,
                stock_code=stock_code,
                stock_name=stock_name,
                session_id=session_id,
                user_id="test_user"
            )
            
            # 결과 추출
            answer = result.get('answer', '') or result.get('summary', '') or "응답을 생성할 수 없습니다."
            
            # 에이전트별 처리 결과 수집
            for agent_name in agent_outputs.keys():
                if agent_name in agent_inputs and agent_name in agent_times:
                    execution_time = agent_times[agent_name].get('end', time.time()) - agent_times[agent_name].get('start', time.time())
                    agent_result = AgentProcessResult(
                        agent_name=agent_name,
                        input=agent_inputs[agent_name],
                        output=agent_outputs[agent_name],
                        error=None,
                        execution_time=execution_time
                    )
                    agent_results.append(agent_result)
            
        except Exception as e:
            logger.error(f"에이전트 테스트 중 오류 발생: {str(e)}", exc_info=True)
            error = str(e)
            answer = "내부 테스트 중 오류가 발생했습니다."
        
        finally:
            # 원래 설정으로 복원
            try:
                agents = get_agents(self.db)
                
                # 프롬프트 템플릿 복원
                for agent_name, template in original_prompt_templates.items():
                    if agent_name in agents and hasattr(agents[agent_name], 'prompt_template'):
                        agents[agent_name].prompt_template = template
                
                # 비활성화된 에이전트 복원
                for agent_name, agent in disabled_agents.items():
                    if agent_name not in graph.agents:
                        graph.agents[agent_name] = agent
                        logger.info(f"에이전트 {agent_name} 복원됨 (테스트 종료)")
                
                # 벡터 DB 설정 복원
                for agent_name, settings in original_vector_db_settings.items():
                    if agent_name in agents and hasattr(agents[agent_name], 'retriever'):
                        for key, value in settings.items():
                            setattr(agents[agent_name].retriever, key, value)
            except Exception as e:
                logger.error(f"설정 복원 중 오류 발생: {str(e)}")
        
        # 전체 실행 시간 계산
        total_execution_time = time.time() - start_time
        
        return answer, agent_results, total_execution_time, error 