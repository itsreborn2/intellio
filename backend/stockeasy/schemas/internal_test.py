"""
내부 테스트를 위한 스키마 정의

이 모듈은 에이전트 테스트를 위한 요청과 응답 모델을 정의합니다.
"""

from typing import Dict, List, Any, Optional, Literal
from pydantic import BaseModel, Field

class AgentPromptConfig(BaseModel):
    """에이전트 프롬프트 설정"""
    agent_name: str = Field(..., description="에이전트 이름")
    prompt_template: Optional[str] = Field(None, description="프롬프트 템플릿 (설정 시 기본값 대신 사용)")
    enabled: bool = Field(True, description="에이전트 사용 여부")
    
class VectorDBConfig(BaseModel):
    """벡터 DB 설정"""
    namespace: Optional[str] = Field(None, description="벡터 DB 네임스페이스 (설정 시 기본값 대신 사용)")
    metadata_filter: Optional[Dict[str, Any]] = Field(None, description="메타데이터 필터 (설정 시 기본값 대신 사용)")
    top_k: Optional[int] = Field(None, description="검색 결과 수 (설정 시 기본값 대신 사용)")

class InternalTestRequest(BaseModel):
    """내부 테스트 요청 모델"""
    question: str = Field(..., description="질문 입력값")
    stock_code: Optional[str] = Field(None, description="종목 코드")
    stock_name: Optional[str] = Field(None, description="종목명")
    session_id: Optional[str] = Field(None, description="세션 ID")
    agent_configs: Optional[List[AgentPromptConfig]] = Field(None, description="에이전트별 프롬프트 설정")
    vector_db_config: Optional[VectorDBConfig] = Field(None, description="벡터 DB 설정")
    
class AgentProcessResult(BaseModel):
    """에이전트 처리 결과"""
    agent_name: str = Field(..., description="에이전트 이름")
    input: Dict[str, Any] = Field(..., description="에이전트 입력")
    output: Dict[str, Any] = Field(..., description="에이전트 출력")
    error: Optional[str] = Field(None, description="에러 메시지 (있을 경우)")
    execution_time: float = Field(..., description="실행 시간 (초)")
    
class InternalTestResponse(BaseModel):
    """내부 테스트 응답 모델"""
    question: str = Field(..., description="질문 입력값")
    answer: str = Field(..., description="최종 답변")
    agent_results: List[AgentProcessResult] = Field(..., description="각 에이전트별 처리 결과")
    total_execution_time: float = Field(..., description="전체 실행 시간 (초)")
    error: Optional[str] = Field(None, description="에러 메시지 (있을 경우)")

class Agent(BaseModel):
    """에이전트 정보"""
    name: str
    description: str = Field(default="설명 없음")

class AvailableAgentsResponse(BaseModel):
    """사용 가능한 에이전트 목록 응답"""
    agents: List[Agent] = []

# 선택적 에이전트 테스트를 위한 스키마
class TestMode(BaseModel):
    """테스트 모드 설정"""
    mode: Literal["full", "selective", "single"] = Field(default="full", description="테스트 모드 (full: 전체 에이전트, selective: 선택적 에이전트, single: 단일 에이전트)")
    selected_agents: Optional[Dict[str, bool]] = Field(None, description="선택된 에이전트 목록 (에이전트 이름: 활성화 여부)")
    single_agent_name: Optional[str] = Field(None, description="단일 테스트 모드에서 선택된 에이전트 이름")

class TestRequest(BaseModel):
    """새로운 테스트 요청 모델 (선택적 에이전트 지원)"""
    question: str = Field(..., description="질문 입력값")
    stock_code: Optional[str] = Field(None, description="종목 코드")
    stock_name: Optional[str] = Field(None, description="종목명")
    session_id: Optional[str] = Field("test_session", description="세션 ID")
    agent_configs: Optional[List[AgentPromptConfig]] = Field(None, description="에이전트별 프롬프트 설정")
    vector_db_config: Optional[VectorDBConfig] = Field(None, description="벡터 DB 설정")
    test_mode: Optional[TestMode] = Field(None, description="테스트 모드 설정 (선택적 에이전트 테스트용)")

class TestResponse(BaseModel):
    """새로운 테스트 응답 모델"""
    question: str = Field(..., description="질문 입력값")
    answer: str = Field(..., description="최종 답변")
    agent_results: List[AgentProcessResult] = Field(default=[], description="각 에이전트별 처리 결과")
    total_execution_time: float = Field(..., description="전체 실행 시간 (초)")
    error: Optional[str] = Field(None, description="에러 메시지 (있을 경우)") 