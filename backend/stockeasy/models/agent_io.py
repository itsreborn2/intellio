"""
에이전트 입출력 데이터 모델 정의

이 모듈은 에이전트 간 데이터 교환을 위한 모델을 정의합니다.
TypedDict를 사용하여 에이전트 상태의 구조를 명확히 합니다.
"""

from typing import TypedDict, List, Dict, Any, Optional
from datetime import datetime


class QuestionClassification(TypedDict, total=False):
    """질문 분류 결과"""
    질문주제: int  # 0: 종목기본정보, 1: 전망, 2: 재무분석, 3: 산업동향, 4: 기타
    답변수준: int  # 0: 간단한답변, 1: 긴설명요구, 2: 종합적판단, 3: 전문가분석
    종목명: Optional[str]
    종목코드: Optional[str]
    산업분류: Optional[str]
    시간범위: Optional[str]


class RetrievedMessage(TypedDict):
    """검색된 메시지"""
    content: str
    created_at: datetime
    score: float
    source: str
    metadata: Dict[str, Any]


class AgentMetric(TypedDict):
    """에이전트 성능 측정 지표"""
    start_time: datetime
    end_time: Optional[datetime]
    duration: Optional[float]
    status: str  # 'started', 'completed', 'failed'
    error: Optional[str]
    memory_usage: Optional[float]
    api_calls: Optional[int]


class AgentError(TypedDict):
    """에이전트 오류 정보"""
    agent: str
    error: str
    type: str
    timestamp: datetime


class AgentState(TypedDict, total=False):
    """에이전트 상태 모델
    
    이 타입은 에이전트 간 데이터 교환을 위한 상태 모델을 정의합니다.
    각 필드는 선택적이며, 필요에 따라 추가/수정될 수 있습니다.
    """
    # 기본 정보
    query: str                          # 사용자 질문
    session_id: str                     # 세션 ID
    
    # 종목 정보
    stock_code: Optional[str]           # 종목 코드
    stock_name: Optional[str]           # 종목명
    
    # 분석 결과
    classification: Optional[QuestionClassification]  # 질문 분류 결과
    
    # 사용자 컨텍스트
    user_context: Dict[str, Any]        # 사용자 컨텍스트 정보
    conversation_history: List[Dict[str, Any]]  # 대화 이력
    
    # 검색 결과
    retrieved_data: Dict[str, List[Any]]  # 소스별 검색된 데이터
    telegram_messages: List[RetrievedMessage]  # 텔레그램 메시지
    report_data: List[Dict[str, Any]]    # 기업리포트 데이터
    financial_data: Dict[str, Any]       # 재무 정보
    industry_data: List[Dict[str, Any]]  # 산업 동향 데이터
    
    # 통합 및 요약
    integrated_knowledge: Optional[Any]  # 통합된 지식 베이스
    summary: Optional[str]              # 생성된 요약
    formatted_response: Optional[str]   # 최종 응답
    
    # 에러 및 메트릭
    errors: List[AgentError]            # 발생한 오류 목록
    metrics: Dict[str, AgentMetric]     # 에이전트별 성능 측정 지표
    
    # 처리 상태
    processing_status: Dict[str, str]   # 각 단계별 처리 상태
    
    # Fallback 정보
    used_fallback: bool                 # Fallback 사용 여부
    fallback_reason: Optional[str]      # Fallback 이유 