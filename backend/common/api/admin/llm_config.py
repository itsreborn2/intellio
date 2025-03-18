"""
LLM 설정 관리 API 모듈

이 모듈은 LLM 설정을 관리하기 위한 API 엔드포인트를 제공합니다.
"""

from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from common.core.deps import get_admin_user
from common.models.user import User
from common.services.llm_config import llm_config_manager
from common.services.agent_llm import get_agent_llm, agent_llm_cache

# 라우터 생성
router = APIRouter(
    prefix="/admin/llm-config",
    tags=["admin", "llm-config"],
    dependencies=[Depends(get_admin_user)]
)

# 모델 정의
class LLMConfigSchema(BaseModel):
    """LLM 설정 스키마"""
    provider: str = Field(..., description="LLM 제공자 (openai, gemini, anthropic 등)")
    model_name: str = Field(..., description="모델 이름")
    temperature: float = Field(0.0, description="생성 다양성 조절 (0.0 ~ 1.0)")
    max_tokens: Optional[int] = Field(None, description="최대 생성 토큰 수")
    top_p: Optional[float] = Field(None, description="토큰 확률 임계값 (0.0 ~ 1.0)")
    api_key_env: Optional[str] = Field(None, description="API 키 환경 변수 이름")

class AgentLLMConfigSchema(BaseModel):
    """에이전트별 LLM 설정 스키마"""
    agent_name: str = Field(..., description="에이전트 이름")
    config: LLMConfigSchema = Field(..., description="LLM 설정")

class FallbackProviderSchema(BaseModel):
    """폴백 제공자 설정 스키마"""
    provider: str = Field(..., description="LLM 제공자")
    model_name: str = Field(..., description="모델 이름")
    temperature: float = Field(0.0, description="생성 다양성 조절")

class FallbackSettingsSchema(BaseModel):
    """폴백 설정 스키마"""
    enabled: bool = Field(True, description="폴백 활성화 여부")
    max_retries: int = Field(3, description="최대 재시도 횟수")
    providers: List[FallbackProviderSchema] = Field([], description="폴백 제공자 목록")

class FullLLMConfigSchema(BaseModel):
    """전체 LLM 설정 스키마"""
    default: LLMConfigSchema = Field(..., description="기본 LLM 설정")
    agents: Dict[str, LLMConfigSchema] = Field({}, description="에이전트별 LLM 설정")
    fallback_settings: FallbackSettingsSchema = Field(..., description="폴백 설정")

@router.get("/")
async def get_all_configs(current_user: User = Depends(get_admin_user)) -> FullLLMConfigSchema:
    """
    모든 LLM 설정 가져오기
    """
    try:
        # 전체 설정 가져오기
        all_configs = llm_config_manager.get_all_configs()
        return all_configs
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"설정 가져오기 실패: {str(e)}"
        )

@router.get("/agents")
async def get_agent_list(current_user: User = Depends(get_admin_user)) -> List[str]:
    """
    에이전트 목록 가져오기
    """
    try:
        # 전체 설정 가져오기
        all_configs = llm_config_manager.get_all_configs()
        
        # 에이전트 목록 가져오기
        agent_names = list(all_configs.get("agents", {}).keys())
        
        return agent_names
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"에이전트 목록 가져오기 실패: {str(e)}"
        )

@router.get("/agent/{agent_name}")
async def get_agent_config(
    agent_name: str,
    current_user: User = Depends(get_admin_user)
) -> LLMConfigSchema:
    """
    에이전트별 LLM 설정 가져오기
    """
    try:
        # 에이전트 설정 가져오기
        agent_config = llm_config_manager.get_agent_config(agent_name)
        
        return agent_config
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"에이전트 설정 가져오기 실패: {str(e)}"
        )

@router.put("/agent/{agent_name}")
async def update_agent_config(
    agent_name: str,
    config: LLMConfigSchema,
    current_user: User = Depends(get_admin_user)
) -> Dict[str, Any]:
    """
    에이전트별 LLM 설정 업데이트
    """
    try:
        # 에이전트 설정 업데이트
        llm_config_manager.update_agent_config(agent_name, config.dict())
        
        # 캐시에 있는 에이전트 LLM 클리어
        if agent_name in agent_llm_cache:
            agent_llm = agent_llm_cache[agent_name]
            agent_llm.llm = None
            agent_llm.llm_streaming = None
        
        return {"message": f"에이전트 {agent_name} 설정 업데이트 완료"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"에이전트 설정 업데이트 실패: {str(e)}"
        )

@router.put("/default")
async def update_default_config(
    config: LLMConfigSchema,
    current_user: User = Depends(get_admin_user)
) -> Dict[str, Any]:
    """
    기본 LLM 설정 업데이트
    """
    try:
        # 전체 설정 가져오기
        all_configs = llm_config_manager.get_all_configs()
        
        # 기본 설정 업데이트
        all_configs["default"] = config.dict()
        
        # 파일 저장
        with open(llm_config_manager.get_config_path(), "w", encoding="utf-8") as f:
            import json
            json.dump(all_configs, f, indent=2, ensure_ascii=False)
        
        # 설정 새로고침
        llm_config_manager.refresh()
        
        # 캐시된 모든 에이전트 LLM 클리어
        for agent_name, agent_llm in agent_llm_cache.items():
            agent_llm.llm = None
            agent_llm.llm_streaming = None
        
        return {"message": "기본 설정 업데이트 완료"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"기본 설정 업데이트 실패: {str(e)}"
        )

@router.put("/fallback")
async def update_fallback_settings(
    settings: FallbackSettingsSchema,
    current_user: User = Depends(get_admin_user)
) -> Dict[str, Any]:
    """
    폴백 설정 업데이트
    """
    try:
        # 전체 설정 가져오기
        all_configs = llm_config_manager.get_all_configs()
        
        # 폴백 설정 업데이트
        all_configs["fallback_settings"] = settings.dict()
        
        # 파일 저장
        with open(llm_config_manager.get_config_path(), "w", encoding="utf-8") as f:
            import json
            json.dump(all_configs, f, indent=2, ensure_ascii=False)
        
        # 설정 새로고침
        llm_config_manager.refresh()
        
        return {"message": "폴백 설정 업데이트 완료"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"폴백 설정 업데이트 실패: {str(e)}"
        )

@router.get("/path")
async def get_config_path(current_user: User = Depends(get_admin_user)) -> Dict[str, str]:
    """
    설정 파일 경로 가져오기
    """
    try:
        return {"path": llm_config_manager.get_config_path()}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"설정 파일 경로 가져오기 실패: {str(e)}"
        )

@router.post("/refresh")
async def refresh_configs(current_user: User = Depends(get_admin_user)) -> Dict[str, Any]:
    """
    LLM 설정 새로고침
    """
    try:
        # 설정 파일 새로고침
        llm_config_manager.refresh()
        
        # 캐시된 모든 에이전트 LLM 클리어
        for agent_name, agent_llm in agent_llm_cache.items():
            agent_llm.llm = None
            agent_llm.llm_streaming = None
        
        return {"message": "LLM 설정 새로고침 완료"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"LLM 설정 새로고침 실패: {str(e)}"
        )