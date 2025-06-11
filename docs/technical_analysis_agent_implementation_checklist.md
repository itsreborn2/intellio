# 기술적 분석 에이전트 구현 체크리스트

## 📋 개요
기술적 분석 에이전트를 멀티 에이전트 시스템에 통합하기 위한 구현 체크리스트입니다. 이 체크리스트를 순서대로 진행하여 단계적으로 구현을 완료합니다.

---

## 🏗️ Phase 1: 데이터 모델 및 인터페이스 정의

### 1.1 데이터 모델 확장
- [X] **`stockeasy/models/agent_io.py` 수정**
  - [X] `DataRequirement` 클래스에 `technical_analysis_needed: bool` 필드 추가
  - [X] 기술적 분석 결과를 위한 새로운 모델 클래스 정의
    - [X] `TechnicalAnalysisResult` 모델 생성
    - [X] `ChartPatternAnalysis` 모델 생성
    - [X] `TechnicalIndicators` 모델 생성
    - [X] `TradingSignals` 모델 생성

### 1.2 API 인터페이스 확인
- [X] **`backend/stockeasy/collector/api/routers.py` 확인**
  - [X] 주가 데이터 엔드포인트 확인 (`/api/v1/stock/chart/{symbol}`)
  - [X] 수급 데이터 엔드포인트 확인 (`/api/v1/stock/supply-demand/{symbol}`)
  - [X] 시장지수 데이터 엔드포인트 확인 (`/api/v1/market/indices`)
  - [X] 필요시 엔드포인트 추가 요청 사항 정리 (기존 엔드포인트로 충분)

---

## 🤖 Phase 2: Technical Analysis Agent 구현

### 2.1 에이전트 클래스 생성
- [X] **`backend/stockeasy/agents/technical_analyzer_agent.py` 생성**
  - [X] `BaseAgent` 상속하는 `TechnicalAnalyzerAgent` 클래스 생성
  - [X] `__init__` 메서드 구현
  - [X] `process` 메서드 기본 구조 구현

### 2.2 데이터 수집 로직 구현
- [X] **stock-data-collector API 클라이언트 구현**
  - [X] HTTP 클라이언트 초기화 (aiohttp)
  - [X] 주가 데이터 요청 메서드 구현
  - [X] 수급 데이터 요청 메서드 구현
  - [X] 시장지수 데이터 요청 메서드 구현
  - [X] 에러 처리 및 재시도 로직 구현
  - [X] 타임아웃 설정

### 2.3 기술적 분석 알고리즘 구현
- [X] **기술적 지표 계산 함수들 구현**
  - [X] 이동평균선 계산 (SMA, EMA)
  - [X] RSI 계산
  - [X] MACD 계산
  - [X] 볼린저 밴드 계산
  - [X] 스토캐스틱 계산

- [X] **차트 패턴 분석 함수들 구현**
  - [X] 지지선/저항선 식별
  - [X] 추세선 분석
  - [X] 기본 차트 패턴 인식

- [X] **매매 신호 생성 로직 구현**
  - [X] 골든크로스/데드크로스 감지
  - [X] 과매수/과매도 신호 생성
  - [X] 종합 매매 신호 계산

### 2.4 결과 포맷팅 및 반환
- [X] **분석 결과 구조화**
  - [X] 기술적 지표 결과 포맷팅
  - [X] 차트 패턴 분석 결과 포맷팅
  - [X] 매매 신호 결과 포맷팅
  - [X] `agent_results`에 저장할 형식으로 변환

---

## 🔍 Phase 3: Question Analyzer 확장

### 3.1 DataRequirements 모델 업데이트
- [X] **`backend/stockeasy/agents/question_analyzer_agent.py` 수정**
  - [X] `DataRequirements` 클래스에 `technical_analysis_needed` 필드 추가
  - [X] 기본값을 `False`로 설정

### 3.2 질문 패턴 분석 로직 추가
- [X] **키워드 기반 기술적 분석 필요성 판단 로직 구현**
  - [X] 기술적 분석 관련 키워드 목록 정의
    - [X] 차트 패턴 키워드: "차트", "패턴", "지지선", "저항선" 등
    - [X] 기술적 지표 키워드: "RSI", "MACD", "볼린저밴드", "이동평균선" 등
    - [X] 매매 신호 키워드: "매수신호", "매도신호", "골든크로스" 등
  - [X] 질문에서 키워드 감지 로직 구현
  - [X] `technical_analysis_needed` 플래그 설정 로직 구현

### 3.3 목차 생성 로직 확장
- [X] **동적 목차에 기술적 분석 섹션 추가**
  - [X] `generate_dynamic_toc` 메서드 수정 (프롬프트 기반으로 자동 생성)
  - [X] 기술적 분석이 필요한 경우 관련 섹션 추가
  - [X] 섹션 구조 정의:
    - [X] "기술적 분석" 메인 섹션
    - [X] "차트 패턴 분석" 하위 섹션
    - [X] "기술적 지표 분석" 하위 섹션
    - [X] "매매 신호 분석" 하위 섹션

---

## 🎯 Phase 4: Orchestrator 확장

### 4.1 에이전트 목록 추가
- [X] **`backend/stockeasy/agents/orchestrator_agent.py` 수정**
  - [X] `available_agents` 딕셔너리에 `"technical_analyzer"` 추가
  - [X] 에이전트 설명 추가: "기술적 분석 에이전트"

### 4.2 실행 계획 로직 수정
- [X] **기술적 분석 에이전트 포함 실행 계획 수립**
  - [X] `_create_default_plan` 메서드 수정
  - [X] 기술적 분석 에이전트를 실행 순서에 포함
  - [X] 우선순위 설정 (다른 분석 에이전트와 동일한 레벨)
  - [X] web_search_mode와 일반 모드 양쪽에 기술적 분석 에이전트 추가

### 4.3 실행 순서 정의
- [X] **execution_order에 technical_analyzer 추가**
  - [X] 일반 모드 실행 순서에 추가
  - [X] 웹 검색 모드 실행 순서에 추가
  - [X] 적절한 위치 선정 (다른 분석 에이전트들과 함께)

---

## 🔄 Phase 5: Parallel Search Agent 확장

### 5.1 에이전트 목록 추가
- [X] **`backend/stockeasy/agents/parallel_search_agent.py` 수정**
  - [X] `search_agent_names` 리스트에 `"technical_analyzer"` 추가
  - [X] 에이전트 초기화 시 기술적 분석 에이전트 포함

### 5.2 실행 조건 로직 추가
- [X] **`process` 메서드 수정**
  - [X] `data_requirements.technical_analysis_needed` 확인 로직 추가
  - [X] 조건이 True일 때 기술적 분석 에이전트 실행하도록 설정

---

## 📦 Phase 6: Agent Registry 통합

### 6.1 에이전트 클래스 등록
- [X] **`backend/stockeasy/graph/agent_registry.py` 수정**
  - [X] `TechnicalAnalyzerAgent` 임포트 추가
  - [X] `agent_classes` 딕셔너리에 `"technical_analyzer": TechnicalAnalyzerAgent` 추가

### 6.2 초기화 순서 고려
- [X] **에이전트 초기화 순서 설정**
  - [X] 기술적 분석 에이전트를 적절한 초기화 그룹에 추가
  - [X] 검색/분석 에이전트 그룹에 포함

---

## 🕸️ Phase 7: Stock Analysis Graph 연결

### 7.1 그래프 노드 추가
- [X] **`backend/stockeasy/graph/stock_analysis_graph.py` 수정**
  - [X] 기술적 분석 에이전트를 병렬 검색 에이전트 목록에 추가
  - [X] `ParallelSearchAgent` 초기화 시 기술적 분석 에이전트 포함

### 7.2 데이터 플로우 확인
- [X] **데이터 흐름 검증**
  - [X] 기술적 분석 결과가 `retrieved_data`에 올바르게 저장되는지 확인 (에이전트 구현에서 보장)
  - [X] `agent_results`에 기술적 분석 결과가 포함되는지 확인 (에이전트 구현에서 보장)

---

## 📚 Phase 8: 프롬프트 및 문서화

### 8.1 프롬프트 개발
- [X] **기술적 분석 전용 프롬프트 생성**
  - [X] `backend/stockeasy/prompts/technical_analyzer_prompts.py` 생성
  - [X] 기술적 분석 결과 해석을 위한 프롬프트 정의
  - [X] 매매 신호 설명을 위한 프롬프트 정의

### 8.2 문서 업데이트
- [X] **API 문서 업데이트**
  - [X] 기술적 분석 결과 형식 문서화
  - [X] 에이전트 사용법 가이드 추가

---

## 🎯 최종 구현 체크리스트

### 기능 검증
- [X] 기술적 분석 관련 질문 입력 시 기술적 분석 에이전트가 정상 실행됨
- [X] stock-data-collector에서 데이터를 정상적으로 수집함
- [X] 기술적 지표가 올바르게 계산됨
- [X] 매매 신호가 논리적으로 생성됨
- [X] 분석 결과가 다른 에이전트 결과와 올바르게 통합됨

---

## 📝 구현 참고사항

### 파일 생성/수정 목록
```
신규 생성:
- backend/stockeasy/agents/technical_analyzer_agent.py
- backend/stockeasy/prompts/technical_analyzer_prompts.py

수정 필요:
- backend/stockeasy/models/agent_io.py
- backend/stockeasy/agents/question_analyzer_agent.py
- backend/stockeasy/agents/orchestrator_agent.py
- backend/stockeasy/agents/parallel_search_agent.py
- backend/stockeasy/graph/agent_registry.py
- backend/stockeasy/graph/stock_analysis_graph.py
```

### 핵심 구현 포인트
1. **모듈화**: 기술적 지표 계산을 별도 함수로 분리
2. **에러 처리**: API 호출 실패 시 graceful degradation
3. **성능**: 비동기 처리 및 적절한 타임아웃 설정
4. **확장성**: 새로운 지표 추가가 용이한 구조
5. **일관성**: 기존 에이전트들과 동일한 패턴 및 구조 유지

### 구현 순서
총 8개 Phase를 순서대로 진행:
1. 데이터 모델 정의 → 2. 에이전트 구현 → 3-7. 시스템 통합 → 8. 프롬프트 개발

---

*이 체크리스트를 순서대로 진행하여 기술적 분석 에이전트를 성공적으로 구현하세요.* 