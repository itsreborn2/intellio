"""
내부 테스트를 위한 API 엔드포인트

이 모듈은 에이전트 테스트를 위한 API를 제공합니다.
"""

from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger
import time

from common.core.database import get_db_async
from stockeasy.services.test_service import InternalTestService
from stockeasy.graph.agent_registry import get_agents
from stockeasy.schemas.internal_test import (
    AgentPromptConfig,
    VectorDBConfig,
    InternalTestRequest,
    InternalTestResponse,
    TestRequest,
    TestResponse,
    AvailableAgentsResponse,
    TestMode
)

# 개발자 테스트용 라우터 (비공개 API)
router = APIRouter(prefix="/_internal_test", tags=["internal_test"])

@router.post("", response_model=TestResponse)
async def run_internal_test(
    request: TestRequest,
    db: AsyncSession = Depends(get_db_async)
) -> TestResponse:
    """
    내부 테스트 실행 API
    
    선택적 파라미터:
    - question: 테스트할 질문
    - stock_code: 종목 코드
    - stock_name: 종목명
    - session_id: 세션 ID
    - agent_configs: 에이전트별 프롬프트 설정
    - vector_db_config: 벡터 DB 설정
    - test_mode: 테스트 모드 설정 (선택적 에이전트 테스트용)
    """
    try:
        # 내부 테스트 서비스 초기화
        test_service = InternalTestService(db)
        
        # 선택적 테스트 모드 처리
        agent_configs = request.agent_configs or []
        test_mode = "full"  # 기본값
        single_agent_name = None
        
        # 테스트 모드 처리
        if request.test_mode:
            test_mode = request.test_mode.mode
            
            # 단일 에이전트 테스트 모드인 경우 에이전트 이름 추출
            if test_mode == "single" and request.test_mode.selected_agents:
                # 선택된 에이전트 중 활성화된 하나만 찾기
                selected_agents = request.test_mode.selected_agents
                enabled_agents = [name for name, enabled in selected_agents.items() if enabled]
                
                if len(enabled_agents) == 1:
                    single_agent_name = enabled_agents[0]
                    logger.info(f"단일 에이전트 테스트: {single_agent_name}")
                elif len(enabled_agents) > 1:
                    # 여러 에이전트가 선택되었으면 첫 번째 것만 사용
                    single_agent_name = enabled_agents[0]
                    logger.warning(f"여러 에이전트가 선택되었지만 첫 번째 에이전트만 사용합니다: {single_agent_name}")
            
            # 선택적 테스트 모드인 경우 에이전트 설정 생성
            elif test_mode == "selective" and request.test_mode.selected_agents:
                selected_agents = request.test_mode.selected_agents
                
                # 모든 에이전트 목록 가져오기
                all_agents = get_agents(db)
                
                # 선택된 에이전트만 활성화하는 설정 생성
                for agent_name in all_agents.keys():
                    is_enabled = selected_agents.get(agent_name, False)
                    
                    # 이미 설정된 에이전트 설정이 있는지 확인
                    existing_config = next((config for config in agent_configs if config.agent_name == agent_name), None)
                    
                    if existing_config:
                        # 기존 설정이 있으면 활성화 상태만 업데이트
                        existing_config.enabled = is_enabled
                    else:
                        # 기존 설정이 없으면 새로 추가
                        agent_configs.append(AgentPromptConfig(
                            agent_name=agent_name,
                            prompt_template=None,
                            enabled=is_enabled
                        ))
        
        # 테스트 실행
        start_time = time.time()
        logger.info(f"[내부 테스트] 시작: {request.question}, 모드: {test_mode}, Agent configs: {agent_configs}")
        
        answer, agent_results, total_execution_time, error = await test_service.test_agents(
            question=request.question,
            stock_code=request.stock_code,
            stock_name=request.stock_name,
            session_id=request.session_id or "test_session",
            agent_configs=agent_configs,
            vector_db_config=request.vector_db_config,
            test_mode=test_mode,
            single_agent_name=single_agent_name
        )
        
        logger.info(f"[내부 테스트] 완료: {time.time() - start_time:.2f}초 소요")
        
        # 응답 생성
        response = TestResponse(
            question=request.question,
            answer=answer,
            agent_results=agent_results,
            total_execution_time=total_execution_time,
            error=error
        )
        
        return response
        
    except Exception as e:
        logger.error(f"내부 테스트 실행 중 오류 발생: {str(e)}", exc_info=True)
        # 오류 발생 시에도 형식에 맞는 응답 반환
        return TestResponse(
            question=request.question,
            answer="내부 테스트 중 오류가 발생했습니다.",
            agent_results=[],
            total_execution_time=time.time() - start_time,
            error=str(e)
        )

@router.get("/agents", response_model=AvailableAgentsResponse)
async def get_available_agents(
    db: AsyncSession = Depends(get_db_async),
) -> AvailableAgentsResponse:
    """
    사용 가능한 에이전트 목록 조회 API
    
    Returns:
        사용 가능한 에이전트 목록
    """
    try:
        # 에이전트 레지스트리에서 모든 에이전트 가져오기
        agents = get_agents(db)
        
        agent_list = []
        for name, agent in agents.items():
            # 에이전트 정보 수집
            description = getattr(agent, 'description', '설명 없음')
            
            agent_list.append({
                "name": name,
                "description": description
            })
        
        return AvailableAgentsResponse(agents=agent_list)
        
    except Exception as e:
        logger.error(f"에이전트 목록 조회 중 오류 발생: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"에이전트 목록 조회 중 오류 발생: {str(e)}")

@router.get("/agent_prompts/{agent_name}")
async def get_agent_prompt(
    agent_name: str,
    db: AsyncSession = Depends(get_db_async),
) -> dict:
    """
    에이전트 프롬프트 조회
    
    Args:
        agent_name: 에이전트 이름
        
    Returns:
        에이전트 프롬프트 정보
    """
    try:
        agents = get_agents(db)
        if agent_name not in agents:
            raise HTTPException(status_code=404, detail=f"에이전트 '{agent_name}'을(를) 찾을 수 없습니다.")
            
        agent = agents[agent_name]
        prompt_template = getattr(agent, 'prompt_template', None)
        
        if prompt_template is None:
            return {"message": f"에이전트 '{agent_name}'에 프롬프트 템플릿이 없습니다."}
        
        return {
            "agent_name": agent_name,
            "prompt_template": prompt_template
        }
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"에이전트 프롬프트 조회 중 오류 발생: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"에이전트 프롬프트 조회 중 오류 발생: {str(e)}") 