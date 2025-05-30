"""
에이전트 입출력 데이터 모델 정의

이 모듈은 에이전트 간 데이터 교환을 위한 모델을 정의합니다.
TypedDict를 사용하여 에이전트 상태의 구조를 명확히 합니다.
"""

from typing import TypedDict, List, Dict, Any, Optional, Union, Literal, TypeVar, cast, Type
from datetime import datetime
from pydantic import BaseModel


# Pydantic 모델을 TypedDict로 변환하는 유틸리티 함수
T = TypeVar('T', bound=TypedDict) # type: ignore

def pydantic_to_typeddict(pydantic_obj: BaseModel, typeddict_class: Type[T]) -> T:
    """
    Pydantic 모델 객체를 TypedDict로 변환합니다.
    
    Args:
        pydantic_obj: 변환할 Pydantic 모델 객체
        typeddict_class: 변환할 TypedDict 클래스 타입
        
    Returns:
        변환된 TypedDict 객체
    
    Examples:
        ```python
        # QuestionAnalysis Pydantic 모델을 QuestionAnalysisResult TypedDict로 변환
        question_analysis = pydantic_to_typeddict(response.entities, ExtractedEntity)
        ```
    """
    return cast(typeddict_class, pydantic_obj.dict())


# 질문분류기 관련 데이터 모델들
class ExtractedEntity(TypedDict, total=False):
    """추출된 엔티티 정보"""
    stock_name: Optional[str]       # 주식/종목명
    stock_code: Optional[str]       # 종목 코드
    sector: Optional[str]           # 산업/섹터
    time_range: Optional[str]       # 시간 범위 (예: 최근 3개월, 지난 분기 등)
    financial_metric: Optional[str] # 재무 지표 (예: 매출, 영업이익, PER 등)
    competitor: Optional[str]       # 경쟁사
    product: Optional[str]          # 제품/서비스


class QuestionClassification(TypedDict, total=False):
    """질문 분류 결과"""
    primary_intent: Literal["종목기본정보", "성과전망", "재무분석", "산업동향", "기타"] # 주요 질문 의도
    complexity: Literal["단순", "중간", "복합", "전문가급"]                      # 질문 복잡도
    expected_answer_type: Literal["사실형", "추론형", "비교형", "예측형", "설명형", "종합형"]  # 기대하는 답변 유형


class DataRequirement(TypedDict, total=False):
    """데이터 요구사항"""
    telegram_needed: bool           # 텔레그램 데이터 필요 여부
    reports_needed: bool            # 기업 리포트 필요 여부
    financial_statements_needed: bool # 재무제표 필요 여부
    industry_data_needed: bool      # 산업 데이터 필요 여부


class QuestionAnalysisResult(TypedDict, total=False):
    """질문 분석 결과 (질문분류기 출력)"""
    entities: ExtractedEntity                # 추출된 엔티티 정보
    classification: QuestionClassification    # 질문 분류 정보
    data_requirements: DataRequirement        # 데이터 요구사항
    keywords: List[str]                      # 주요 키워드
    detail_level: Literal["간략", "보통", "상세"] # 요구되는 상세도


# 오케스트레이터 관련 데이터 모델들
class AgentConfig(TypedDict, total=False):
    """각 에이전트 실행 설정"""
    agent_name: str                 # 에이전트 이름
    enabled: bool                   # 활성화 여부
    priority: int                   # 우선순위 (1-10)
    parameters: Dict[str, Any]      # 에이전트별 매개변수


class ExecutionPlan(TypedDict, total=False):
    """실행 계획 (오케스트레이터 출력)"""
    plan_id: str                    # 계획 ID
    created_at: datetime            # 생성 시간
    agents: List[AgentConfig]       # 실행할 에이전트 목록
    execution_order: List[str]      # 실행 순서
    integration_strategy: str       # 정보 통합 전략 설명
    expected_output: str            # 예상 출력물 설명
    fallback_strategy: str          # 실패 시 대응 전략


# 에이전트 실행 결과 모델들
class AgentExecutionResult(TypedDict, total=False):
    """개별 에이전트 실행 결과"""
    agent_name: str                 # 에이전트 이름
    status: Literal["success", "partial_success", "failed", "skipped"] # 실행 상태
    data: Any                       # 에이전트 출력 데이터
    error: Optional[str]            # 오류 정보 (있을 경우)
    execution_time: float           # 실행 시간 (초)
    metadata: Dict[str, Any]        # 기타 메타데이터


class RetrievedTelegramMessage(TypedDict):
    """검색된 텔레그램 메시지"""
    content: str                    # 메시지 내용
    channel_name: str              # 채널명
    message_created_at: datetime    # 생성 시간
    final_score: float              # 최종 점수
    metadata: Dict[str, Any]        # 메타데이터


class CompanyReportData(TypedDict, total=False):
    """분석된 기업 리포트 데이터
     리포트의 개별 청크를 분석 결과
    """
    title: str                      # 제목
    publish_date: datetime          # 발행일
    author: str                     # 작성자/증권사
    content: str                    # 내용
    stock_name: str                 # 종목명
    stock_code: str                 # 종목코드
    score: float                    # 유사도 점수
    analysis: Dict[str, Any]        # 추가 분석 정보
    page: int                       # 페이지 번호
    source: str                     # 출처
    sector_name: str                # 산업명
    keyword_list: List[str]         # 키워드 목록


class ConfidentialData(TypedDict, total=False):
    """비공개 자료 데이터
    내부 비공개 문서 및 자료의 분석 결과
    """
    title: str                      # 제목
    publish_date: datetime          # 발행일
    author: str                     # 작성자/증권사
    content: str                    # 내용
    stock_name: str                 # 종목명
    stock_code: str                 # 종목코드
    score: float                    # 유사도 점수
    analysis: Dict[str, Any]        # 추가 분석 정보
    page: int                       # 페이지 번호
    source: str                     # 출처
    sector_name: str                # 산업명
    keyword_list: List[str]         # 키워드 목록
    access_level: str               # 접근 권한 레벨
    confidentiality: str            # 기밀성 등급
    document_type: str              # 문서 유형

class IndustryReportData(TypedDict, total=False):
    """분석된 산업 리포트 데이터
     리포트의 개별 청크를 분석 결과
    """
    title: str                      # 제목
    publish_date: datetime          # 발행일
    author: str                     # 작성자/증권사
    content: str                    # 내용
    stock_name: str                 # 종목명
    stock_code: str                 # 종목코드
    score: float                    # 유사도 점수
    analysis: Dict[str, Any]        # 추가 분석 정보
    page: int                       # 페이지 번호
    source: str                     # 출처
    sector_name: str                # 산업명
    subgroup_list: List[str]        # 세부 산업 목록
    keyword_list: List[str]         # 키워드 목록


class FinancialData(TypedDict, total=False):
    """재무 데이터"""
    stock_code: str                 # 종목코드
    stock_name: str                 # 종목명
    period: str                     # 기간 (연도, 분기)
    metrics: Dict[str, Any]         # 재무 지표
    analysis: Dict[str, Any]        # 분석 정보


class IndustryData(TypedDict, total=False):
    """산업 데이터"""
    sector: str                     # 산업/섹터명
    period: str                     # 기간
    trends: Dict[str, Any]          # 트렌드 정보
    competitors: List[Dict[str, Any]] # 경쟁사 정보
    market_share: Dict[str, float]  # 시장 점유율




class RetrievedAllAgentData(TypedDict, total=False):
    """검색 및 분석된 모든 데이터"""
    telegram_messages: List[RetrievedTelegramMessage] # 텔레그램 메시지
    company_report: List[CompanyReportData]       # 기업 리포트
    financials: List[FinancialData] # 재무 데이터
    industry_report: List[IndustryData]    # 산업 정보
    confidential: List[ConfidentialData]   # 비공개 자료


class IntegratedKnowledge(TypedDict, total=False):
    """통합된 지식 베이스"""
    core_insights: List[str]        # 핵심 인사이트
    facts: List[Dict[str, Any]]     # 확인된 사실
    opinions: List[Dict[str, Any]]  # 다양한 의견
    analysis: Dict[str, Any]        # 종합 분석
    sources: Dict[str, List[str]]   # 출처 정보


class AgentMetric(TypedDict):
    """에이전트 성능 측정 지표"""
    start_time: datetime
    end_time: Optional[datetime]
    duration: Optional[float]
    status: str                     # 'started', 'completed', 'failed'
    error: Optional[str]
    memory_usage: Optional[float]
    api_calls: Optional[int]
    token_usage: Optional[Dict[str, int]] # 토큰 사용량


class AgentError(TypedDict):
    """에이전트 오류 정보"""
    agent: str                      # 오류 발생 에이전트
    error: str                      # 오류 메시지
    type: str                       # 오류 유형
    timestamp: datetime             # 발생 시간
    context: Dict[str, Any]         # 오류 발생 맥락


class AgentState(TypedDict, total=False):
    """에이전트 상태 모델
    
    이 타입은 에이전트 간 데이터 교환을 위한 상태 모델을 정의합니다.
    각 필드는 선택적이며, 필요에 따라 추가/수정될 수 있습니다.
    """
    # 기본 정보
    query: str                      # 사용자 질문
    stock_code: str                 # 종목코드
    stock_name: str                 # 종목명
    session_id: str                 # 세션 ID
    
    # 사용자 컨텍스트
    user_context: Dict[str, Any]    # 사용자 컨텍스트 정보
    conversation_history: List[Dict[str, Any]]  # 대화 이력
    
    # 질문 분석 결과 (질문분류기에서 설정)
    question_analysis: QuestionAnalysisResult  # 질문 분석 결과
    
    # 실행 계획 (오케스트레이터에서 설정)
    execution_plan: ExecutionPlan   # 실행 계획
    
    # 에이전트 실행 결과
    agent_results: Dict[str, AgentExecutionResult]  # 각 에이전트의 실행 결과
    
    # 검색된 데이터
    retrieved_data: RetrievedAllAgentData   # 검색 및 분석된 데이터
    
    # 통합 및 요약
    integrated_knowledge: Optional[IntegratedKnowledge]  # 통합된 지식 베이스
    summary: Optional[str]          # 생성된 요약
    formatted_response: Optional[str]  # 최종 응답
    answer: Optional[str]           # 최종 답변
    answer_expert: Optional[str]    # 전문가형 답변
    
    # 에러 및 메트릭
    errors: List[AgentError]        # 발생한 오류 목록
    metrics: Dict[str, AgentMetric] # 에이전트별 성능 측정 지표
    
    # 처리 상태
    processing_status: Dict[str, str]  # 각 단계별 처리 상태
    
    # Fallback 정보
    used_fallback: bool             # Fallback 사용 여부
    fallback_reason: Optional[str]  # Fallback 이유 