# Stockeasy 멀티에이전트 시스템 구현 보고서

## 1. 개요

Stockeasy 멀티에이전트 시스템은 한국 주식 시장 정보를 통합적으로 분석하고 제공하기 위한 LangGraph 기반 멀티에이전트 아키텍처입니다. 이 시스템은 텔레그램 메시지, 기업 리포트, 재무제표, 산업 동향 데이터를 병렬로 검색하고 통합하여 사용자 질문에 대한 종합적인 응답을 생성합니다.

## 2. 시스템 아키텍처

### 2.1 전체 구조

시스템은 다음과 같은 계층 구조로 설계되었습니다:

1. **데이터 계층**: 텔레그램 메시지 DB, 기업리포트 DB, 재무데이터 DB
2. **에이전트 계층**: 각 역할별 전문화된 에이전트 모듈
3. **통합 계층**: 에이전트 간 워크플로우를 관리하는 그래프 구조
4. **서비스 계층**: 사용자 요청을 처리하는 API 서비스

### 2.2 기술 스택

- **기반 프레임워크**: LangChain, LangGraph
- **언어 모델**: OpenAI GPT-4 (gpt-4o), Google Gemini (gemini-2.0-flash)
- **데이터베이스**: PostgreSQL (세션 관리)
- **벡터 데이터베이스**: Pinecone (텔레그램 메시지, 기업 리포트)
- **백엔드**: FastAPI, SQLAlchemy 2.0

### 2.3 아키텍처 다이어그램

```
사용자 → 세션 관리자 → 오케스트레이터 → 질문 분석기
                                          ↓
                            ┌─────────────┴─────────────────────────────┐
                            ↓             ↓              ↓              ↓
                    텔레그램 검색   기업리포트 분석     재무 분석        산업 분석
                            ↓             ↓              ↓              ↓
                            └────────────→←──────────────←──────────────┘
                                            ↓
                                    지식 통합기
                                            ↓
                                    요약 생성
                                            ↓
                                    응답 포맷팅
                                            ↓
                                        사용자
```

## 3. 구현된 에이전트

### 3.1 기본 에이전트 인터페이스

모든 에이전트는 `BaseAgent` 클래스를 상속받아 일관된 인터페이스를 제공합니다:

```python
class BaseAgent(ABC):
    @abstractmethod
    async def process(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """상태를 입력받아 처리하고 업데이트된 상태를 반환"""
        pass
```

### 3.2 핵심 에이전트

현재 구현 완료된 에이전트들:

#### 3.2.1 세션 관리자 에이전트 (SessionManagerAgent)

- **역할**: 사용자 세션 관리 및 컨텍스트 유지
- **기능**: 세션 생성, 이전 대화 컨텍스트 로드, 컨텍스트 기반 질문 보강
- **구현 상태**: 완료

#### 3.2.2 오케스트레이터 에이전트 (OrchestratorAgent)

- **역할**: 전체 워크플로우 조정 및 실행 경로 결정
- **기능**: 
  - 사용자 질문 분석
  - 필요한 에이전트 선택
  - 정보 소스별 중요도 결정
  - 실행 계획 수립
- **구현 상태**: 완료

#### 3.2.3 질문 분석기 에이전트 (QuestionAnalyzerAgent)

- **역할**: 사용자 질문 상세 분석
- **기능**: 
  - 종목명, 종목코드 추출
  - 질문 주제 분류 (종목기본정보, 전망, 재무분석, 산업동향 등)
  - 필요한 데이터 소스 결정
- **구현 상태**: 완료

#### 3.2.4 지식 통합기 에이전트 (KnowledgeIntegratorAgent)

- **역할**: 여러 에이전트로부터 수집된 정보 통합
- **기능**: 
  - 중복 정보 제거
  - 충돌 정보 해결
  - 정보의 신뢰도 평가
  - 통합된 정보 생성
- **구현 상태**: 완료

#### 3.2.5 요약 생성 에이전트 (SummarizerAgent)

- **역할**: 통합된 정보에서 핵심 내용 요약
- **기능**:
  - 통합된 정보 요약
  - 핵심 포인트 추출
  - 사용자 맞춤형 요약 생성
- **구현 상태**: 완료

#### 3.2.6 응답 포맷터 에이전트 (ResponseFormatterAgent)

- **역할**: 최종 응답을 사용자 친화적 형식으로 변환
- **기능**: 
  - 마크다운 형식 적용
  - 중요 정보 강조
  - 구조화된 응답 생성
- **구현 상태**: 완료

#### 3.2.7 폴백 관리자 에이전트 (FallbackManagerAgent)

- **역할**: 오류 발생 시 대체 응답 제공
- **기능**: 
  - 오류 유형 분석
  - 상황별 적절한 대체 응답 생성
  - 사용자 안내 메시지 제공
- **구현 상태**: 완료

### 3.3 검색 에이전트 (구현 완료)

#### 3.3.1 텔레그램 검색 에이전트 (TelegramRetrieverAgent)

- **역할**: 관련 텔레그램 메시지 검색
- **기능**:
  - 벡터 검색을 통한 관련 메시지 검색
  - 메시지 중요도 및 신선도 평가
  - 관련성 높은 메시지 필터링
- **구현 상태**: 완료

#### 3.3.2 기업리포트 분석 에이전트 (ReportAnalyzerAgent)

- **역할**: 기업 리포트 검색 및 분석
- **기능**:
  - 벡터 검색을 통한 관련 리포트 검색
  - 리포트 내용 요약 및 분석
  - 관련 정보 추출
- **모델**: Google Gemini (gemini-2.0-flash)
- **구현 상태**: 완료

#### 3.3.3 재무제표 분석 에이전트 (FinancialAnalyzerAgent)

- **역할**: 재무제표 검색 및 분석
- **기능**:
  - 재무제표 데이터 검색
  - 지표 계산 및 트렌드 분석
  - 핵심 재무 정보 추출
- **구현 상태**: 완료

#### 3.3.4 산업 분석 에이전트 (IndustryAnalyzerAgent)

- **역할**: 산업 동향 데이터 검색 및 분석
- **기능**:
  - 산업 관련 데이터 검색
  - 산업 트렌드 분석
  - 동종 업계 비교 정보 제공
- **구현 상태**: 완료

## 4. 워크플로우 그래프

### 4.1 그래프 구조

LangGraph의 `StateGraph`를 사용하여 에이전트 간 워크플로우를 정의했습니다:

```python
workflow = StateGraph(AgentState)

# 기본 노드 추가
workflow.add_node("session_manager", session_manager_agent)
workflow.add_node("orchestrator", orchestrator_agent)
workflow.add_node("question_analyzer", question_analyzer_agent)
# ... 생략 ...

# 기본 흐름 정의
workflow.add_edge("session_manager", "orchestrator")
workflow.add_edge("orchestrator", "question_analyzer")
# ... 생략 ...
```

### 4.2 병렬 처리 구현

검색 에이전트들은 조건부로 실행되며, 병렬적으로 처리될 수 있습니다:

```python
# 조건부 라우팅
def should_use_telegram(state: AgentState) -> bool:
    data_requirements = state.get("data_requirements", {})
    telegram_needed = data_requirements.get("telegram_needed", True)
    return telegram_needed

def should_use_report(state: AgentState) -> bool:
    data_requirements = state.get("data_requirements", {})
    reports_needed = data_requirements.get("reports_needed", True)
    return reports_needed

# 조건부 에지 추가
workflow.add_conditional_edges(
    "question_analyzer",
    should_use_telegram,
    {
        True: "telegram_retriever",
        False: "knowledge_integrator"  # 텔레그램 검색이 필요 없는 경우 스킵
    }
)
```

### 4.3 동적 경로 구성

오케스트레이터가 생성한 실행 계획에 따라 워크플로우가 동적으로 구성됩니다:

```python
def has_insufficient_data(state: AgentState) -> str:
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
```

### 4.4 오류 처리

각 단계에서 오류가 발생할 경우 폴백 메커니즘이 작동합니다:

```python
# 오류 발생 시 폴백 매니저로 라우팅
workflow.add_conditional_edges(
    "knowledge_integrator",
    has_insufficient_data,
    {
        "fallback_manager": "fallback_manager",
        "summarizer": "summarizer"
    }
)
```

## 5. 에이전트 간 통신

### 5.1 상태 모델

에이전트 간 데이터는 공통 상태 객체를 통해 전달됩니다:

```python
class AgentState(TypedDict):
    query: str                        # 사용자 질문
    session_id: str                   # 세션 ID
    stock_code: Optional[str]         # 종목 코드
    stock_name: Optional[str]         # 종목명
    user_context: Dict[str, Any]      # 사용자 컨텍스트
    conversation_history: List[Dict]  # 대화 이력
    question_analysis: Dict[str, Any] # 질문 분석 결과
    execution_plan: Dict[str, Any]    # 실행 계획
    retrieved_data: Dict[str, Any]    # 검색된 데이터
    agent_results: Dict[str, Any]     # 에이전트 결과
    errors: List[Dict[str, Any]]      # 오류 정보
    metrics: Dict[str, Any]           # 성능 측정
    processing_status: Dict[str, str] # 처리 상태
```

### 5.2 주요 데이터 흐름

1. 사용자 질문 → 세션 관리자 → 오케스트레이터
2. 오케스트레이터 → 질문 분석기 → 데이터 요구사항 결정
3. 데이터 요구사항에 따라 필요한 검색 에이전트들 실행
4. 검색 에이전트들 → 지식 통합기 → 요약기 → 응답 포맷터
5. 응답 포맷터 → 사용자 응답

## 6. 최근 업데이트 (2025년 3월)

### 6.1 기능 개선

1. **멀티 모델 지원**
   - OpenAI GPT-4(gpt-4o) 및 Google Gemini(gemini-2.0-flash) 모델 지원
   - 에이전트별 최적 모델 선택 기능

2. **데이터 요구사항 분석 강화**
   - 질문 분석기가 필요한 데이터 소스를 보다 정확하게 판단
   - 불필요한 에이전트 실행 최소화

3. **실행 계획 생성**
   - 오케스트레이터가 질문에 따른 최적의 실행 계획 생성
   - 에이전트별 우선순위 및 실행 순서 최적화

4. **에러 복구 및 폴백 전략**
   - 에이전트 실패 시 대체 전략 구현
   - 데이터 부족 시 대체 정보 소스 활용

### 6.2 성능 개선

1. **병렬 처리 최적화**
   - 독립적인 검색 에이전트의 병렬 실행
   - 전체 응답 시간 단축

2. **캐싱 및 최적화**
   - 유사 질문에 대한 중간 결과 캐싱
   - 모델 호출 최소화

3. **동적 임계값 조정**
   - 질문 복잡도에 따른 검색 임계값 자동 조정
   - 질문 유형별 최적화된 파라미터 적용

## 7. 실제 실행 예시

아래는 실제 시스템 로그에서 발췌한 "올해 실적은?" 쿼리 처리 과정입니다:

```
1. 오케스트레이터 분석 결과:
   - 데이터 요구사항: {'telegram_needed': False, 'reports_needed': True, 'financial_statements_needed': True, 'industry_data_needed': False}
   
2. 실행 계획 생성:
   - 순서: ['telegram_retriever', 'report_analyzer', 'financial_analyzer', 'knowledge_integrator', 'summarizer', 'response_formatter']
   - 통합 전략: Knowledge Integrator를 사용하여 기업 리포트, 재무제표, 텔레그램 메시지에서 추출된 정보를 통합
   
3. 텔레그램 검색 결과:
   - 2개의 관련 메시지 발견
   
4. 리포트 분석 결과:
   - 3개의 관련 리포트 발견 및 분석
   
5. 재무 분석 결과:
   - 데이터 없음 (분석 스킵)
   
6. 지식 통합 및 요약:
   - 모든 소스의 정보 통합 및 요약
   
7. 최종 응답 생성:
   - 사용자 친화적 형식으로 응답 포맷팅
```

## 8. 구현 현황 및 향후 개선 사항

### 8.1 구현 완료된 작업

1. **전체 아키텍처 구현**
   - 모든 핵심 에이전트 구현 완료
   - 워크플로우 그래프 구현 완료
   - 병렬 처리 및 조건부 실행 구현

2. **데이터 검색 에이전트 구현**
   - TelegramRetrieverAgent
   - ReportAnalyzerAgent
   - FinancialAnalyzerAgent
   - IndustryAnalyzerAgent

3. **통합 및 응답 생성 에이전트 구현**
   - KnowledgeIntegratorAgent
   - SummarizerAgent
   - ResponseFormatterAgent

4. **API 서비스 구현**
   - FastAPI 엔드포인트 연결
   - 세션 관리 구현

### 8.2 개선 계획

1. **모델 최적화**
   - 에이전트별 최적 모델 선택 로직 개선
   - 모델 성능/비용 최적화

2. **캐싱 전략 강화**
   - 유사 질문 캐싱 구현
   - 중간 결과 재사용

3. **응답 품질 개선**
   - 보다 자연스러운 응답 생성
   - 더 정확한 정보 추출

4. **모니터링 강화**
   - 각 에이전트 성능 모니터링 시스템 구축
   - 오류 추적 및 분석 개선

## 부록: 폴더 구조

```
backend/
└── stockeasy/
    ├── agents/               # 에이전트 구현
    │   ├── base.py           # 기본 에이전트 인터페이스
    │   ├── session_manager.py
    │   ├── orchestrator_agent.py
    │   ├── question_analyzer_agent.py
    │   ├── telegram_retriever_agent.py
    │   ├── report_analyzer_agent.py
    │   ├── financial_analyzer_agent.py
    │   ├── industry_analyzer_agent.py
    │   ├── knowledge_integrator_agent.py
    │   ├── summarizer.py
    │   ├── response_formatter_agent.py
    │   └── fallback_manager_agent.py
    ├── graph/                # 워크플로우 그래프
    │   ├── agent_registry.py  # 에이전트 등록 관리
    │   └── stock_analysis_graph.py # 그래프 정의
    ├── prompts/              # 프롬프트 템플릿
    │   ├── orchestrator_prompts.py
    │   ├── question_analyzer_prompts.py
    │   ├── knowledge_integrator_prompts.py
    │   ├── response_formatter_prompts.py
    │   └── fallback_manager_prompts.py
    ├── services/             # 서비스 구현
    │   ├── telegram/
    │   │   ├── rag_service.py
    │   │   └── embedding.py
    │   └── rag_service.py     # 통합 RAG 서비스
    └── models/               # 데이터 모델
        └── agent_io.py       # 에이전트 I/O 모델
``` 