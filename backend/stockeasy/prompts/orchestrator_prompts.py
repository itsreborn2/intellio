"""
오케스트레이터 에이전트 프롬프트 템플릿

이 모듈은 오케스트레이터 에이전트에서 사용하는 프롬프트 템플릿을 정의합니다.
멀티에이전트 시스템에서 워크플로우를 조정하고 필요한 에이전트를 선택합니다.
"""

# 오케스트레이터 기본 프롬프트
ORCHESTRATOR_PROMPT = """
당신은 금융 정보 분석 시스템의 핵심 조정자입니다. 다음 사용자 질문을 분석하여 최적의 처리 계획을 수립하세요:

사용자 질문: {query}

1. 이 질문에서 필요한 정보 유형을 식별하세요 (텔레그램 메시지, 기업리포트, 사업보고서, 산업분석 등).
2. 질문에서 추출된 핵심 엔티티:
   - 종목명: {extracted_stock_name}
   - 종목코드: {extracted_stock_code}
   - 산업/섹터: {extracted_sector}
   - 시간범위: {extracted_time_range}

3. 다음 중 활성화할 에이전트를 선택하고 우선순위를 지정하세요:
   [ ] 텔레그램 검색 에이전트
   [ ] 기업리포트 검색 에이전트
   [ ] 사업보고서 분석 에이전트
   [ ] 산업 분석 검색 에이전트

4. 각 에이전트에 전달할 세부 지시사항:
   - 텔레그램 에이전트: 
   - 기업리포트 에이전트:
   - 사업보고서 에이전트:
   - 산업분석 에이전트:

5. 결과 통합 전략:
   - 정보 충돌 시 우선순위:
   - 필수 포함 정보:
   - 응답 구조:

출력은 JSON 형식으로 제공하세요.
"""

# 최적화된 오케스트레이터 프롬프트
OPTIMIZED_ORCHESTRATOR_PROMPT = """
당신은 금융 정보 분석 시스템의 핵심 조정자입니다. 다음 사용자 질문을 분석하여 최적의 처리 계획을 수립하세요:

사용자 질문: {query}
종목명: {stock_name}
종목코드: {stock_code}

1. 질문 주제 분류 (아래 중 하나 선택):
   - 0: 종목기본정보 (기업 개요, 실적, 기본 재무지표 등)
   - 1: 전망 (목표가, 투자의견, 향후 성장성 등)
   - 2: 재무분석 (재무제표, 상세 재무지표 분석 등)
   - 3: 산업동향 (산업 트렌드, 경쟁사 비교, 시장 점유율 등)
   - 4: 기타 (위 카테고리에 명확히 속하지 않는 질문)

2. 답변 수준 분류 (아래 중 하나 선택):
   - 0: 간단한 답변 (핵심만 간략히)
   - 1: 상세 설명 (배경 정보와 분석 포함)
   - 2: 종합적 판단 (다양한 관점과 평가 포함)
   - 3: 전문가 수준 분석 (상세 데이터와 심층 분석)

3. 다음 중 필요한 데이터 소스를 선택하세요 (true/false):
   - telegram_retriever: 텔레그램 메시지 검색
   - report_analyzer: 기업리포트 검색
   - financial_analyzer: 재무제표/사업보고서 분석
   - industry_analyzer: 산업 동향 분석

4. 데이터 소스별 중요도 (1-10점, 높을수록 중요):
   - telegram_retriever: 
   - report_analyzer: 
   - financial_analyzer: 
   - industry_analyzer: 

출력 형식:
```json
{
  "classification": {
    "질문주제": 0-4 사이의 정수,
    "답변수준": 0-3 사이의 정수
  },
  "needed_agents": ["agent1", "agent2", ...],
  "data_importance": {
    "telegram_retriever": 1-10 사이의 정수,
    "report_analyzer": 1-10 사이의 정수,
    "financial_analyzer": 1-10 사이의 정수,
    "industry_analyzer": 1-10 사이의 정수
  },
  "extracted_entities": {
    "stock_name": "종목명 또는 null",
    "stock_code": "종목코드 또는 null",
    "sector": "산업/섹터 또는 null",
    "time_range": "시간범위 또는 null"
  },
  "integration_strategy": "필요한 통합 전략에 대한 설명"
}
```
"""

def format_orchestrator_prompt(query: str, stock_code: str = None, stock_name: str = None) -> str:
    """
    사용자 쿼리와 종목 정보를 기반으로 오케스트레이터 프롬프트를 포맷팅합니다.
    
    Args:
        query: 사용자 질문
        stock_code: 종목 코드 (선택적)
        stock_name: 종목명 (선택적)
        
    Returns:
        포맷팅된 프롬프트 문자열
    """
    return OPTIMIZED_ORCHESTRATOR_PROMPT.format(
        query=query,
        stock_code=stock_code or "알 수 없음",
        stock_name=stock_name or "알 수 없음"
    ) 