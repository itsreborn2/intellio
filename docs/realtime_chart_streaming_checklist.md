# 실시간 차트 스트리밍 기능 구현 체크리스트

## 📋 프로젝트 개요
- **목표**: 사용자 대기시간 개선을 위한 실시간 차트 스트리밍 기능 구현
- **예상 완료 시간**: 5-7일
- **주요 성과**: 5-10초 내 기술적 분석 차트 제공

---

## 🎯 Phase 1: 백엔드 워크플로우 수정

### 1.1 StockAnalysisGraph 워크플로우 변경

- [x] `backend/stockeasy/graph/stock_analysis_graph.py` 파일 백업
- [x] `_build_graph()` 메서드에서 워크플로우 엣지 수정
  - [x] `workflow.add_edge("session_manager", "technical_analyzer")` 추가
  - [x] `workflow.add_edge("technical_analyzer", "question_analyzer")` 추가
  - [x] 기존 `session_manager → question_analyzer` 엣지 제거
- [x] `question_analyzer_router()` 함수 수정
  - [x] 후속질문이 아닌 경우 `orchestrator`로 라우팅 변경 (이미 구현됨)
  - [x] 조건부 엣지 매핑 업데이트 (이미 올바름)
- [ ] 워크플로우 변경사항 테스트
  - [ ] 단위 테스트 작성
  - [ ] 통합 테스트 실행

**예상 소요시간**: 1일  
**담당자**: 백엔드 개발자  
**검증 방법**: 로그를 통해 에이전트 실행 순서 확인

---

### 1.2 TechnicalAnalyzerAgent 수정

- [x] `backend/stockeasy/agents/technical_analyzer_agent.py` 파일 백업
- [x] `process()` 메서드 수정
  - [x] `streaming_callback` 추출 로직 추가
  - [x] 기술적 분석 수행 부분 유지
  - [x] 차트 컴포넌트 생성 로직 추가
  - [x] SSE 이벤트 생성 및 전송 로직 추가
  - [x] `agent_results`에 `preliminary_sent` 플래그 저장
- [x] `_create_preliminary_chart_components()` 메서드 추가
  - [x] 헤딩 컴포넌트 생성
  - [x] 설명 paragraph 컴포넌트 생성
  - [x] 기술적 지표 차트 컴포넌트 생성
  - [x] 주가 차트 컴포넌트 생성
  - [x] 매매신호 요약 컴포넌트 생성 (선택적)
- [x] 에러 핸들링 강화
  - [x] 스트리밍 실패 시 계속 진행
  - [x] 차트 생성 실패 시 처리 (try-catch 블록)
  - [x] 종목 코드 없음 케이스 처리
- [x] 로깅 개선
  - [x] 실행 시간 로깅 (기존에 구현됨)
  - [x] 스트리밍 성공/실패 로깅
  - [x] 차트 데이터 크기 로깅 (컴포넌트 개수 로깅)

**예상 소요시간**: 2일  
**담당자**: 백엔드 개발자  
**검증 방법**: 스트리밍 이벤트 정상 전송 확인

---

### 1.3 ParallelSearchAgent 수정

- [x] `backend/stockeasy/agents/parallel_search_agent.py` 파일 백업
- [x] `process()` 메서드 수정
  - [x] `technical_analyzer` 에이전트 제외 로직 추가
  - [x] 이미 실행된 technical_analyzer 상태 확인
  - [x] 로깅 메시지 업데이트
- [ ] 테스트 케이스 작성
  - [ ] technical_analyzer 제외 확인
  - [ ] 나머지 에이전트 정상 실행 확인
  - [ ] agent_results 병합 확인

**예상 소요시간**: 0.5일  
**담당자**: 백엔드 개발자  
**검증 방법**: 병렬 검색에서 technical_analyzer 제외 확인

---

## 🎨 Phase 2: 프론트엔드 UI 구현

### 2.1 상태 관리 및 타입 정의

- [x] `frontend/stockeasy/app/components/chat/AIChatArea/components/MessageComponentRenderer.tsx` 파일 백업
- [x] 새로운 인터페이스 정의
  - [x] `PreliminaryChartData` 인터페이스 추가
  - [x] 기존 타입과 호환성 확인
- [x] 상태 변수 추가
  - [x] `preliminaryChart` 상태 추가
  - [x] `showCompletionPopup` 상태 추가
  - [x] `finalResponse` 상태 추가
- [x] useState 훅 설정
  - [x] 초기값 설정
  - [x] 타입 안전성 확인

**예상 소요시간**: 0.5일  
**담당자**: 프론트엔드 개발자  
**검증 방법**: TypeScript 컴파일 오류 없음 확인

---

### 2.2 SSE 이벤트 처리 로직 ✅ **COMPLETED**

- [x] `streamChatMessage()` 함수에 `preliminary_chart` 이벤트 케이스 추가
- [x] `useMessageProcessing` 훅에서 `onPreliminaryChart` 콜백 처리
- [x] 상태 업데이트 로직 구현
  - [x] `setPreliminaryChart()` 상태 업데이트
  - [x] `setCurrentStatus()` 메시지 업데이트
- [x] 에러 핸들링 추가 (콘솔 로깅)
- [x] 이벤트 타입별 처리 분리
  - [x] 기존 이벤트 처리 유지
  - [x] 새로운 이벤트와 기존 이벤트 충돌 방지

**예상 소요시간**: 1일 → **실제 소요시간**: 0.5일  
**담당자**: 프론트엔드 개발자  
**검증 방법**: 브라우저 개발자 도구에서 이벤트 수신 확인

---

### 2.3 PreliminaryChartDisplay 컴포넌트

- [x] 컴포넌트 기본 구조 생성
  - [x] 함수형 컴포넌트 정의
  - [x] Props 인터페이스 정의
  - [x] 기본 스타일링 적용
- [x] 실시간 배지 구현
  - [x] 위치 및 스타일 설정
  - [x] 애니메이션 효과 추가
  - [x] 색상 및 아이콘 설정
- [x] 차트 컴포넌트 렌더링
  - [x] `MessageComponentRenderer` 연동
  - [x] 차트 데이터 전달
  - [x] 에러 케이스 처리
- [x] 메시지 표시 영역
  - [x] 동적 메시지 렌더링
  - [x] 스타일링 적용
  - [x] 반응형 디자인 고려
- [x] 로딩 인디케이터
  - [x] 스피너 애니메이션
  - [x] 진행 상태 텍스트
  - [x] CSS 애니메이션 적용

**예상 소요시간**: 1.5일  
**담당자**: 프론트엔드 개발자  
**검증 방법**: 다양한 화면 크기에서 UI 확인

---

### 2.4 CompletionPopup 컴포넌트

- [x] 팝업 컴포넌트 기본 구조
  - [x] 고정 위치 설정 (중앙 모달)
  - [x] z-index 설정
  - [x] 기본 스타일 적용
- [x] 애니메이션 구현
  - [x] 스케일 및 페이드 애니메이션
  - [x] 페이드 인/아웃 효과
  - [x] 트랜지션 설정
- [x] 버튼 상호작용
  - [x] "상세 보고서 보기" 버튼
  - [x] 호버 효과
  - [x] 클릭 이벤트 처리
- [x] 접근성 고려
  - [x] 키보드 네비게이션 (ESC 키)
  - [x] 스크린 리더 지원
  - [x] ARIA 라벨 설정

**예상 소요시간**: 1일  
**담당자**: 프론트엔드 개발자  
**검증 방법**: 접근성 도구로 검증

---

### 2.5 메인 렌더링 로직 통합 ✅ **COMPLETED**

- [x] 조건부 렌더링 로직
  - [x] `preliminaryChart && !finalResponse && isLoading` 표시 조건
  - [x] `showCompletionPopup` 표시 조건
  - [x] `finalResponse` 표시 조건
- [x] 상태 전환 로직
  - [x] 임시 차트 → 완료 팝업 (`onProcessingComplete`)
  - [x] 완료 팝업 → 최종 문서 (`onViewFinalReport`)
  - [x] 상태 정리 로직 (`setPreliminaryChart(null)`)
- [x] 스크롤 처리
  - [x] 최종 문서로 자동 스크롤 (`messageListRef.current?.scrollToBottom()`)
- [x] 컴포넌트 임포트 및 통합
  - [x] PreliminaryChartDisplay 컴포넌트 연동
  - [x] CompletionPopup 컴포넌트 연동
  - [x] props 전달 및 이벤트 핸들링

**예상 소요시간**: 1일 → **실제 소요시간**: 0.5일  
**담당자**: 프론트엔드 개발자  
**검증 방법**: 전체 플로우 시나리오 테스트

---

## 🎨 Phase 3: CSS 및 애니메이션

### 3.1 글로벌 CSS 스타일 ✅ **COMPLETED**

- [x] 애니메이션 키프레임 정의
  - [x] `@keyframes slideInUp` 추가
  - [x] `@keyframes slideInRight` 추가  
  - [x] `@keyframes pulse` 추가
  - [x] `@keyframes fadeIn` 추가
  - [x] `@keyframes scaleIn` 추가
  - [x] `@keyframes bounceIn` 추가
  - [x] `@keyframes shimmer` 추가
  - [x] `@keyframes loadingBounce` 추가
- [x] 공통 클래스 정의
  - [x] `.chart-container` 호버 효과
  - [x] `.loading-dots` 스타일
  - [x] `.preliminary-chart-container` 스타일
  - [x] `.realtime-badge` 스타일
  - [x] `.completion-popup` 애니메이션
  - [x] `.status-message` 스타일
- [x] 반응형 디자인
  - [x] 모바일 브레이크포인트 (max-width: 640px)
  - [x] 태블릿 브레이크포인트 (641px - 1024px)
  - [x] 데스크톱 최적화 (min-width: 1025px)
- [x] 다크모드 지원
  - [x] CSS 변수를 활용한 색상 정의
  - [x] 테마별 스타일 구현
  - [x] `prefers-color-scheme` 자동 감지
- [x] 컴포넌트에 CSS 클래스 적용
  - [x] PreliminaryChartDisplay 컴포넌트
  - [x] CompletionPopup 컴포넌트

**예상 소요시간**: 1일 → **실제 소요시간**: 0.5일  
**담당자**: 프론트엔드 개발자  
**검증 방법**: 다양한 디바이스에서 시각적 확인

---

## 🧪 Phase 4: 테스트 및 검증

### 4.1 단위 테스트

- [ ] 백엔드 단위 테스트
  - [ ] TechnicalAnalyzerAgent 테스트
  - [ ] ParallelSearchAgent 테스트
  - [ ] 워크플로우 라우팅 테스트
- [ ] 프론트엔드 단위 테스트
  - [ ] 컴포넌트 렌더링 테스트
  - [ ] 이벤트 처리 로직 테스트
  - [ ] 상태 관리 테스트
- [ ] 목 데이터 준비
  - [ ] 차트 데이터 샘플
  - [ ] SSE 이벤트 샘플
  - [ ] 에러 시나리오 샘플

**예상 소요시간**: 1일  
**담당자**: 개발팀 전체  
**검증 방법**: 테스트 커버리지 80% 이상

---

