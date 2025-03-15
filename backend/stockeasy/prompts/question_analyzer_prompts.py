"""
질문 분석기 에이전트 프롬프트 템플릿

이 모듈은 사용자 질문을 분석하여 중요 엔티티와 정보 요구사항을 추출하는 
질문 분석기 에이전트에서 사용하는 프롬프트 템플릿을 정의합니다.
"""

# 질문 분석기 프롬프트
QUESTION_ANALYZER_PROMPT = """
당신은 금융 정보 시스템의 질문 분석 전문가입니다. 사용자 질문을 분석하여 다음 정보를 추출해 주세요:

사용자 질문: {query}

1. 질문 유형 분석:
   - 주요 질문 의도: [기본정보/성과예측/재무분석/산업비교/기타]
   - 질문 복잡성: [단순/중간/복합/전문가급]
   - 필요한 데이터 유형: [뉴스/기업리포트/재무제표/산업데이터/기타]

2. 핵심 엔티티 추출:
   - 종목명: 
   - 종목코드(있는 경우): 
   - 산업/섹터(언급된 경우): 
   - 시간범위(언급된 경우): 

3. 중요 키워드:
   - 키워드 1: 
   - 키워드 2: 
   - 키워드 3: 

4. 세부 정보 요구사항:
   - 필요한 상세 정보 수준: [간략/보통/상세]
   - 중점적으로 다루어야 할 측면: 

출력 형식은 다음과 같은 JSON으로 제공해주세요:
```json
{
  "question_type": {
    "intent": "기본정보/성과예측/재무분석/산업비교/기타 중 하나",
    "complexity": "단순/중간/복합/전문가급 중 하나",
    "data_types": ["뉴스", "기업리포트", "재무제표", "산업데이터", "기타"] 중 필요한 것
  },
  "entities": {
    "stock_name": "종목명 또는 null",
    "stock_code": "종목코드 또는 null",
    "sector": "산업/섹터 또는 null",
    "time_range": "시간범위 또는 null"
  },
  "keywords": ["키워드1", "키워드2", "키워드3"],
  "detail_requirements": {
    "detail_level": "간략/보통/상세 중 하나",
    "focus_aspects": ["중점 측면1", "중점 측면2"]
  }
}
```
"""

# 최적화된 질문 분석기 프롬프트
OPTIMIZED_QUESTION_ANALYZER_PROMPT = """
당신은 금융 도메인 특화 질문 분석 전문가입니다. 다음 사용자 질문을 분석하여 JSON 형식으로 정보를 추출해 주세요:

사용자 질문: {query}

분석 지침:
1. 한국 주식 종목명과 종목코드 추출 (예: 삼성전자, 005930)
2. 산업/섹터 정보 식별 (예: 반도체, IT, 금융 등)
3. 질문의 시간적 범위 파악 (예: 최근 1년, 2023년 3분기 등)
4. 질문의 주제 분류 (기본정보, 성과전망, 재무분석, 산업동향 등)
5. 필요한 데이터 소스 식별 (텔레그램, 리포트, 재무제표, 산업보고서 등)
6. 질문의 중요 키워드와 구체적인 요구사항 추출

주의:
- 종목명/코드가 명시되지 않았으면 null로 표시
- 언급되지 않은 항목은 null로 표시
- 한국 주식 시장 맥락에서 분석할 것
- 확실하지 않은 정보는 추측하지 말 것

출력 형식:
```json
{
  "entities": {
    "stock_name": "종목명 또는 null",
    "stock_code": "종목코드 또는 null",
    "sector": "산업/섹터 또는 null",
    "time_range": "시간범위 또는 null"
  },
  "classification": {
    "primary_intent": "종목기본정보/성과전망/재무분석/산업동향/기타 중 하나",
    "complexity": "단순/중간/복합/전문가급 중 하나"
  },
  "data_requirements": {
    "telegram_needed": true/false,
    "reports_needed": true/false,
    "financial_statements_needed": true/false,
    "industry_data_needed": true/false
  },
  "keywords": ["키워드1", "키워드2", "키워드3"],
  "detail_level": "간략/보통/상세 중 하나"
}
```
"""

def format_question_analyzer_prompt(query: str) -> str:
    """
    사용자 쿼리를 기반으로 질문 분석기 프롬프트를 포맷팅합니다.
    
    Args:
        query: 사용자 질문
        
    Returns:
        포맷팅된 프롬프트 문자열
    """
    return OPTIMIZED_QUESTION_ANALYZER_PROMPT.format(query=query) 