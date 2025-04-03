# FinancialAnalyzerAgent 구현 가이드

## 개요
FinancialAnalyzerAgent는 GCS에 저장된 정기보고서 PDF 파일을 읽어 재무 데이터를 분석하고 사용자 질문에 답변하는 에이전트입니다.

## 주요 구성요소

### 1. FinancialAnalyzerAgent (backend/stockeasy/agents/financial_analyzer_agent.py)
- 사용자 질문을 분석하고 필요한 재무 데이터를 요청
- 재무 데이터를 LLM에 전달하여 분석 결과 생성
- 결과를 상태 객체에 저장

### 2. FinancialDataService (backend/stockeasy/services/financial/data_service.py)
- GCS에서 PDF 파일 목록 조회
- 로컬 캐싱 메커니즘 구현
- PDF 파일에서 재무제표 페이지 추출

### 3. StockInfoService (backend/stockeasy/services/financial/stock_info_service.py)
- 종목 코드 및 이름 관리
- 종목 검색 기능 제공

### 4. 프롬프트 템플릿 (backend/stockeasy/prompts/financial_prompts.py)
- 재무 데이터 분석을 위한 프롬프트 정의
- PDF 텍스트 분석을 위한 지시사항 포함

## 주요 기능

### 1. PDF 파일 관리
- GCS 경로: `정기보고서/{종목코드}/{날짜}_{회사명}_{종목코드}_{업종}_{보고서유형}_DART.pdf`
- 로컬 캐싱: `stockeasy/local_cache/financial_reports/{stock_code}/{file_name}`
- 파일 목록 캐싱: `stockeasy/local_cache/financial_reports_list.json`

### 2. PDF 처리 흐름
1. 종목코드로 GCS 파일 목록 조회
2. 파일명 정규식 파싱으로 메타데이터 추출 (날짜, 회사명, 보고서 유형 등)
3. 로컬 캐시 확인 후 없으면 GCS에서 다운로드
4. PyMuPDF로 PDF 텍스트 추출
5. 재무제표 관련 페이지 식별 및 추출

### 3. 데이터 분석 흐름
1. 사용자 질문과 요구사항 분석
2. 필요한 연도 범위 및 재무 지표 식별
3. 재무 데이터 추출 및 포맷팅
4. LLM에 컨텍스트 제공하여 분석 결과 생성

## 캐싱 전략
1. 파일 목록 캐싱: 24시간 유효
2. PDF 파일 캐싱: 한 번 다운로드 후 로컬 저장
3. 종목 정보 캐싱: 24시간 유효

## 사용 예시
```python
# 에이전트 초기화
agent = FinancialAnalyzerAgent(db=db_session)

# 상태 객체 생성
state = {
    "query": "삼성전자의 최근 2년간 영업이익 추이를 알려줘",
    "question_analysis": {
        "entities": {
            "stock_name": "삼성전자"
        },
        "classification": {
            "primary_intent": "재무정보",
            "complexity": "단순"
        },
        "data_requirements": {
            "time_range": {
                "start_date": "2022-01-01",
                "end_date": "2024-01-01"
            }
        }
    }
}

# 에이전트 실행
result_state = await agent.process(state)

# 결과 추출
analysis_result = result_state["agent_results"]["financial_analyzer"]["data"]["llm_response"]
print(analysis_result)
```

## 구현 시 고려사항

### 성능 최적화
- GCS API 호출 최소화를 위한 캐싱 활용
- 필요한 페이지만 추출하여 LLM 토큰 사용량 절감
- 비동기 처리로 I/O 병목 현상 방지

### 오류 처리
- 파일 형식 오류 시 로깅 및 대체 데이터 활용
- LLM 응답 생성 실패 시 폴백 메커니즘 사용
- 모든 예외 상황에서 명확한 오류 메시지 제공

### 확장성
- 새로운 재무 지표 추가 가능한 유연한 구조
- 미래에 다른 데이터 소스 추가 용이
- 보고서 유형별 처리 로직 분리 