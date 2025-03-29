"""
질문 분석기 에이전트 프롬프트 템플릿

이 모듈은 사용자 질문을 분석하여 중요 엔티티와 정보 요구사항을 추출하는 
질문 분석기 에이전트에서 사용하는 프롬프트 템플릿을 정의합니다.
"""


# 최적화된 질문 분석기 프롬프트
OPTIMIZED_QUESTION_ANALYZER_PROMPT = """
당신은 금융 도메인 특화 질문 분석 전문가입니다. 다음 사용자 질문을 분석하여 구조화된 형식으로 정보를 추출해 주세요:

사용자 질문: {query}
종목명: {stock_name}
종목코드: {stock_code}

분석 지침:
1. 한국 주식 종목명과 종목코드 추출 (예: 삼성전자, 005930)
2. 종목이 속한 산업/섹터 정보 식별 (예: 반도체, IT, 금융 등)
3. 질문의 시간적 범위 파악 (예: 최근 1년, 2023년 3분기 등)
4. 질문의 주제 분류 (기본정보, 성과전망, 재무분석, 산업동향 등)
5. 필요한 데이터 소스 식별 (텔레그램, 리포트, 재무제표, 산업보고서 등)
6. 질문의 중요 키워드와 구체적인 요구사항 추출
7. 기업리포트나 텔레그램 데이터 소스는 둘 중 하나가 반드시 포함되어야 함.

주의:
- 종목명/코드가 명시되지 않았으면 null로 표시
- 언급되지 않은 항목은 null로 표시
- 한국 주식 시장 맥락에서 분석할 것
- 확실하지 않은 정보는 추측하지 말 것

"""

def format_question_analyzer_prompt(query: str, stock_name: str, stock_code: str) -> str:
    """
    사용자 쿼리를 기반으로 질문 분석기 프롬프트를 포맷팅합니다.
    
    Args:
        query: 사용자 질문
        
    Returns:
        포맷팅된 프롬프트 문자열
    """
    return OPTIMIZED_QUESTION_ANALYZER_PROMPT.format(query=query, stock_name=stock_name, stock_code=stock_code) 