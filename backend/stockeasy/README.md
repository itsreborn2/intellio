# Stockeasy 멀티에이전트 시스템

Stockeasy 멀티에이전트 시스템은 주식 관련 질문에 대한 종합적인 분석과 답변을 제공하는 LLM 기반 시스템입니다. LangChain과 Langgraph를 활용한 모듈식 에이전트 아키텍처로 구현되어 있습니다.

## 주요 기능

- 사용자 질문 분석 및 분류
- 텔레그램 메시지 검색 및 분석
- 여러 데이터 소스(텔레그램, 기업리포트, 재무제표, 산업분석)의 통합
- 종합적인 정보 요약 및 응답 생성
- 오류 처리 및 대체 응답 제공

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

## 사용 방법

### 기본 사용법

```python
from stockeasy.services.telegram.rag_service import StockRAGService

# RAG 서비스 초기화
rag_service = StockRAGService()

# 주식 분석 요청
async def analyze():
    result = await rag_service.analyze_stock(
        query="삼성전자 최근 실적은 어떤가요?",
        stock_code="005930",
        stock_name="삼성전자"
    )
    
    # 응답 출력
    print(result["summary"])
    
    # 검색된 텔레그램 메시지
    messages = result["retrieved_messages"]
    
    # 분류 결과
    classification = result["classification"]
```

### 테스트 실행

```bash
# 테스트 스크립트 실행
python -m backend.stockeasy.tests.test_multiagent
```

## 확장 방향

현재 구현된 시스템은 기본적인 텔레그램 메시지 검색 및 요약 기능을 제공합니다. 향후 다음과 같은 확장이 계획되어 있습니다:

1. **추가 데이터 소스**: 기업리포트, 재무제표, 산업 동향 데이터 통합
2. **성능 모니터링**: 에이전트별 성능 측정 및 분석
3. **병렬 처리**: 복수 데이터 소스의 병렬 처리로 응답 시간 단축
4. **사용자 컨텍스트**: 대화 이력 및 사용자 선호도 기반 개인화

## 개발 환경 설정

### 필수 라이브러리

- Python 3.9+
- LangChain
- Langgraph
- OpenAI API
- FastAPI
- Pinecone (벡터 데이터베이스)

### 환경 변수

필요한 환경 변수는 `.env` 파일에 설정할 수 있습니다:

```
OPENAI_API_KEY=your_openai_api_key
PINECONE_API_KEY=your_pinecone_api_key
PINECONE_ENVIRONMENT=your_pinecone_environment
PINECONE_INDEX=your_pinecone_index
PINECONE_NAMESPACE_STOCKEASY_TELEGRAM=telegram_namespace
```

## 라이선스

이 프로젝트는 MIT 라이선스 하에 배포됩니다. 