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
- **언어 모델**: OpenAI GPT-4 (모델명: gpt-4o)
- **데이터베이스**: PostgreSQL (세션 관리)
- **벡터 데이터베이스**: Pinecone (텔레그램 메시지, 기업 리포트)
- **백엔드**: FastAPI, SQLAlchemy 2.0

### 2.3 아키텍처 다이어그램

```
사용자 → 세션 관리자 → 오케스트레이터 → 질문 분석기
                                    ↓
                      ┌────────────┴───────────────┐
                      ↓             ↓              ↓
               텔레그램 검색   기업리포트 분석   재무/산업 분석
                      ↓             ↓              ↓
                      └────────────→←──────────────┘
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
- **구현 상태**: 기본 기능 구현 완료

#### 3.2.2 오케스트레이터 에이전트 (OrchestratorAgent)

- **역할**: 전체 워크플로우 조정 및 실행 경로 결정
- **기능**: 
  - 사용자 질문 분석
  - 필요한 에이전트 선택
  - 정보 소스별 중요도 결정
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

#### 3.2.5 응답 포맷터 에이전트 (ResponseFormatterAgent)

- **역할**: 최종 응답을 사용자 친화적 형식으로 변환
- **기능**: 
  - 마크다운 형식 적용
  - 중요 정보 강조
  - 구조화된 응답 생성
- **구현 상태**: 완료

#### 3.2.6 폴백 관리자 에이전트 (FallbackManagerAgent)

- **역할**: 오류 발생 시 대체 응답 제공
- **기능**: 
  - 오류 유형 분석
  - 상황별 적절한 대체 응답 생성
  - 사용자 안내 메시지 제공
- **구현 상태**: 완료

### 3.3 검색 에이전트 (구현 중)

- **텔레그램 검색 에이전트 (TelegramRetrieverAgent)**
- **기업리포트 분석 에이전트 (ReportAnalyzerAgent)**
- **재무제표 분석 에이전트 (FinancialAnalyzerAgent)**
- **산업 분석 에이전트 (IndustryAnalyzerAgent)**

## 4. 워크플로우 그래프

### 4.1 그래프 구조

LangGraph의 `StateGraph`를 사용하여 에이전트 간 워크플로우를 정의했습니다:

```python
workflow = StateGraph(AgentState)

# 기본 노드 추가
workflow.add_node("session_manager", {})
workflow.add_node("orchestrator", {})
workflow.add_node("question_analyzer", {})
# ... 생략 ...

# 기본 흐름 정의
workflow.add_edge("session_manager", "orchestrator")
workflow.add_edge("orchestrator", "question_analyzer")
# ... 생략 ...
```

### 4.2 병렬 처리 구현

검색 에이전트들은 병렬로 실행되도록 브랜치로 구현했습니다:

```python
# 브랜치 정의
with workflow.branch("retrieval_branch") as branch:
    branch.add_node("telegram_retriever", {})
    branch.add_node("report_analyzer", {})
    branch.add_node("financial_analyzer", {})
    branch.add_node("industry_analyzer", {})

# 조건부 라우팅
workflow.add_conditional_edges(
    "question_analyzer_next",
    router_function,
    {
        "telegram_retriever": ["retrieval_branch.telegram_retriever"],
        # ... 생략 ...
    }
)
```

### 4.3 조건부 경로

사용자 질문 유형에 따라 실행할 에이전트를 동적으로 결정합니다:

```python
def router_function(state: AgentState) -> Union[str, List[str]]:
    classification = state.get("question_classification", {})
    question_type = classification.get("질문주제", 4)  # 기본값: 기타
    
    # 종목기본정보: 텔레그램, 기업리포트
    if question_type == 0:
        return ["telegram_retriever", "report_analyzer"]
    # ... 생략 ...
```

### 4.4 오류 처리

각 단계에서 오류가 발생할 경우 폴백 메커니즘이 작동합니다:

```python
# 검색 결과 기반 조건부 경로
workflow.add_conditional_edges(
    "knowledge_integrator",
    has_insufficient_data,
    {
        "fallback_manager": "fallback_manager",
        "summarizer": "summarizer"
    }
)
```

## 5. 프롬프트 템플릿

각 에이전트는 특화된 프롬프트 템플릿을 사용합니다:

### 5.1 구현된 프롬프트

- **오케스트레이터 프롬프트**: 질문 분석 및 에이전트 선택 지시
- **질문 분석기 프롬프트**: 질문 분류 및 엔티티 추출 지시
- **지식 통합기 프롬프트**: 다양한 소스 정보 통합 지시
- **응답 포맷터 프롬프트**: 사용자 친화적 응답 생성 지시
- **폴백 매니저 프롬프트**: 오류 상황 대응 지시

### 5.2 프롬프트 예시 (질문 분석기)

```
당신은 금융 도메인 특화 질문 분석 전문가입니다. 다음 사용자 질문을 분석하여 JSON 형식으로 정보를 추출해 주세요:

사용자 질문: {query}

분석 지침:
1. 한국 주식 종목명과 종목코드 추출 (예: 삼성전자, 005930)
2. 산업/섹터 정보 식별 (예: 반도체, IT, 금융 등)
...
```

## 6. 데이터 흐름

### 6.1 상태 모델

에이전트 간 데이터는 공통 상태 객체를 통해 전달됩니다:

```python
class AgentState(TypedDict):
    query: str                        # 사용자 질문
    session_id: str                   # 세션 ID
    stock_code: Optional[str]         # 종목 코드
    stock_name: Optional[str]         # 종목명
    # ... 생략 ...
```

### 6.2 주요 데이터 흐름

1. 사용자 질문 → 세션 관리자 → 오케스트레이터
2. 오케스트레이터 → 질문 분석기 → 필요한 검색 에이전트들
3. 검색 에이전트들 → 지식 통합기 → 요약기 → 응답 포맷터
4. 응답 포맷터 → 사용자 응답

## 7. 데이터베이스 연동

### 7.1 세션 관리

PostgreSQL을 사용하여 사용자 세션 및 대화 이력을 관리합니다:

```python
async def get_db_session() -> AsyncSession:
    session = AsyncSessionLocal()
    try:
        logger.debug("새 DB 세션 생성")
        return session
    except Exception as e:
        logger.error(f"DB 세션 생성 중 오류 발생: {e}")
        await session.close()
        raise
```

## 8. 구현 현황 및 남은 작업

### 8.1 구현 완료된 작업

1. **기본 아키텍처 설계**
   - 전체 멀티에이전트 시스템 설계
   - 에이전트 간 인터페이스 정의

2. **핵심 에이전트 구현**
   - SessionManagerAgent (세션 관리)
   - OrchestratorAgent (워크플로우 조정)
   - QuestionAnalyzerAgent (질문 분석)
   - KnowledgeIntegratorAgent (정보 통합)
   - ResponseFormatterAgent (응답 포맷팅)
   - FallbackManagerAgent (오류 처리)

3. **워크플로우 그래프 구현**
   - LangGraph 기반 그래프 구조 설정
   - 조건부 라우팅 로직 구현
   - 병렬 처리 브랜치 구현

4. **데이터베이스 연동**
   - PostgreSQL 세션 관리 구현
   - 데이터베이스 연결 관리 코드 통합

### 8.2 우선순위 작업

1. **검색 에이전트 구현/통합**
   - TelegramRetrieverAgent 연결
   - ReportAnalyzerAgent, FinancialAnalyzerAgent, IndustryAnalyzerAgent 구현

2. **테스트 코드 작성**
   - 통합 테스트 코드 개발
   - 성능 측정 및 최적화

3. **API 서비스 구현**
   - FastAPI 엔드포인트 연결
   - 요청/응답 처리 최적화

### 8.3 향후 개선 사항

1. **모니터링 시스템 구현**
   - 에이전트 성능 측정
   - 로깅 및 분석 기능

2. **캐싱 전략 구현**
   - 반복 질문에 대한 응답 캐싱
   - 유사 질문 처리 최적화

3. **UI/UX 개선**
   - 대화형 인터페이스 개발
   - 결과 시각화 기능 추가

## 9. 결론

Stockeasy 멀티에이전트 시스템은 다양한 금융 데이터 소스를 통합하여 사용자 질문에 대한 종합적인 응답을 제공합니다. 현재까지 핵심 에이전트들의 구현을 완료했으며, 검색 에이전트 구현 및 통합을 진행 중입니다. LangGraph를 활용한 병렬 처리 구조를 통해 효율적인 데이터 검색 및 통합이 가능하며, 향후 지속적인 개선을 통해 더욱 강력한 금융 정보 제공 시스템으로 발전할 예정입니다.

## 부록: 폴더 구조

```
backend/
└── stockeasy/
    ├── agents/               # 에이전트 구현
    │   ├── base.py           # 기본 에이전트 인터페이스
    │   ├── session_manager.py
    │   ├── orchestrator_agent.py
    │   ├── question_analyzer_agent.py
    │   ├── knowledge_integrator_agent.py
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
    │   └── ...
    └── models/               # 데이터 모델
        └── agent_io.py       # 에이전트 I/O 모델
``` 