"""재무제표 분석을 위한 프롬프트 템플릿

이 모듈은 재무제표와 사업보고서 분석을 위한 프롬프트를 정의합니다.
"""

from typing import List, Dict, Any

# 재무제표 분석 프롬프트
FINANCIAL_ANALYSIS_PROMPT = """당신은 기업 재무제표 및 사업보고서 분석 전문가입니다. 다음 정보를 바탕으로 재무 데이터를 분석하세요:

질문: {query}
종목코드: {stock_code}
종목명: {stock_name}
질문분류: {classification}

분석 전략:
1. 가장 최근 공시된 재무 정보를 기본으로 하되, 질문의 시간적 범위에 맞게 조정하세요.
2. 질문 주제에 따라 다음 재무 정보에 집중하세요:
   - 종목기본정보: PER, PBR, ROE, 배당수익률 등 핵심 지표
   - 재무분석: 수익성, 성장성, 안정성, 활동성 지표 종합 분석
   - 전망: 최근 3개년 추이와 향후 전망 중심

3. 다음 재무제표 요소를 중점적으로 분석하세요:
   - 손익계산서: 매출액, 영업이익, 순이익 및 관련 마진
   - 재무상태표: 자산, 부채, 자본 구조 및 변동성
   - 현금흐름표: 영업/투자/재무 활동 현금흐름 및 FCF

4. 동종업계 평균과 비교 분석을 제공하세요.
5. 주요 재무 지표의 추세와 변동 원인을 설명하세요.

모든 수치는 정확하게 인용하고, 단위(억원, %)를 명확히 표시하세요.
데이터 출처와 기준일을 명시하세요(예: 2023년 3분기 보고서, 2022년 사업보고서).

재무 데이터:
{financial_data}
"""

def format_financial_data(financial_data: List[Dict[str, Any]]) -> str:
    """재무 데이터를 문자열로 포맷팅합니다.

    Args:
        financial_data: 재무 데이터 리스트

    Returns:
        str: 포맷팅된 재무 데이터 문자열
    """
    if not financial_data:
        return "재무 데이터가 없습니다."
    
    formatted_data = []
    
    for item in financial_data:
        source = item.get("source", "알 수 없는 출처")
        date = item.get("date", "날짜 없음")
        content = item.get("content", "")
        indicators = item.get("financial_indicators", {})
        
        data_str = f"[출처: {source} ({date})]\n{content}\n"
        
        if indicators:
            data_str += "\n주요 재무 지표:\n"
            for key, value in indicators.items():
                data_str += f"- {key}: {value}\n"
        
        formatted_data.append(data_str)
    
    return "\n\n".join(formatted_data) 