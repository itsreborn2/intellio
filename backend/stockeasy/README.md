# Stockeasy 멀티에이전트 시스템

Stockeasy 멀티에이전트 시스템은 주식 관련 질문에 대한 종합적인 분석과 답변을 제공하는 LLM 기반 시스템입니다. LangChain과 Langgraph를 활용한 모듈식 에이전트 아키텍처로 구현되어 있습니다.

## 주요 기능

- 사용자 질문 분석 및 분류
- 텔레그램 메시지 검색 및 분석
- 여러 데이터 소스(텔레그램, 기업리포트, 재무제표, 산업분석)의 통합
- 종합적인 정보 요약 및 응답 생성
- 오류 처리 및 대체 응답 제공

## 환경 설정

### 메모리 추적 기능

메모리 사용량과 누수를 모니터링하기 위한 메모리 추적 기능을 제공합니다.

**메모리 추적 활성화 (기본값)**
```bash
export ENABLE_MEMORY_TRACKING=true
```

**메모리 추적 비활성화**
```bash
export ENABLE_MEMORY_TRACKING=false
```

메모리 추적이 활성화되면:
- 각 에이전트 실행 전후의 메모리 사용량이 기록됩니다
- `backend/stockeasy/local_cache/memory_tracking/memory_usage.csv`에 메모리 데이터가 저장됩니다
- 객체 분석 정보가 수집됩니다 (주요 에이전트만)

**참고**: 메모리 추적 기능은 비동기로 실행되어 시스템 성능에 최소한의 영향을 줍니다.

## 아키텍처

![멀티에이전트 시스템 아키텍처](../../docs/images/multiagent_architecture.png)

### 핵심 컴포넌트

- **질문 분석 에이전트**: 사용자 질문 분석 및 분류
- **텔레그램 검색 에이전트**: 관련 텔레그램 메시지 검색
- **지식 통합 에이전트**: 다양한 소스의 정보 통합
- **요약 에이전트**: 검색된 정보 요약
- **응답 포맷터**: 사용자 친화적 응답 생성
- **Fallback 관리자**: 오류 처리 및 대체 응답 생성

## 파일 구조

```
backend/stockeasy/
├── agents/               # 에이전트 정의
│   ├── base.py           # 기본 에이전트 인터페이스
│   ├── orchestrator.py   # 워크플로우 조정 에이전트
│   ├── question_analyzer.py # 질문 분석 에이전트
│   ├── telegram_retriever.py # 텔레그램 검색 에이전트
│   ├── summarizer.py     # 요약 및 통합 에이전트
│   └── fallback_response.py # 에러 처리 및 응답 포맷팅
├── graph/                # 에이전트 워크플로우 그래프
│   ├── stock_analysis_graph.py # 주식 분석 워크플로우
│   └── agent_registry.py # 에이전트 등록 관리
├── models/               # 데이터 모델
│   └── agent_io.py       # 에이전트 상태 및 I/O 모델
├── prompts/              # 프롬프트 템플릿
│   └── telegram_prompts.py # 텔레그램 관련 프롬프트
└── services/             # 서비스 구현
    └── telegram/         # 텔레그램 관련 서비스
        ├── embedding.py  # 임베딩 서비스
        └── rag_service.py # RAG 서비스
```
