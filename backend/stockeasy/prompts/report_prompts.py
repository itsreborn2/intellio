"""
기업리포트 분석 프롬프트

이 모듈은 기업리포트 검색 및 분석을 위한 프롬프트 템플릿을 정의합니다.
"""

from typing import List, Dict, Any

# 기업리포트 검색 프롬프트
REPORT_SEARCH_PROMPT = """
당신은 금융 및 주식 관련 기업리포트를 효과적으로 검색하는 전문가입니다.
다음 정보를 바탕으로 가장 관련성 높은 기업리포트 섹션을 검색해주세요.

사용자 질문: {query}
종목명: {stock_name}
종목코드: {stock_code}
질문 분류: {classification}

검색 전략:
1. 주제와 직접 관련된 내용에 우선순위를 두세요.
2. 최신 리포트를 우선적으로 고려하세요.
3. 구체적인 수치 정보가 포함된 내용을 선호하세요.
4. 대형사나 신뢰성이 있는 증권사나 애널리스트의 리포트에 가중치를 부여하세요.
5. 제목(heading)이 질문과 관련성이 높은 섹션을 우선시하세요.

유사도 임계값: {threshold}
최대 검색결과 수: {max_results}
"""

# 기업리포트 분석 프롬프트
REPORT_ANALYSIS_PROMPT = """
당신은 기업리포트 분석 전문가입니다. 다음 기업리포트 내용을 분석하여 주어진 질문에 답변하세요.  

사용자 질문: {query}
종목명: {stock_name}
종목코드: {stock_code}
키워드: {keywords}

기업리포트 내용:
{report_contents}

분석 지침:
1. 리포트에서 질문과 직접 관련된 핵심 정보를 추출하세요.
2. 최신 정보를 우선적으로 고려하세요.
3. 여러 리포트 간 정보가 충돌할 경우, 최신 날짜의 정보와 대형사나 신뢰성이 있는 출처의 정보를 우선시하세요.
4. 숫자와 통계는 정확하게 인용하고, 출처를 명시하세요.
5. 분석가의 주관적 견해와 객관적 사실을 구분하여 표현하세요.
6. 특정 용어나 영어는 필요시 간단히 설명하세요.
7. 질문에 답변이 불확실성이 있는 경우, 그 한계를 명확히 표현하세요.
"""

REPORT_ANALYSIS_SYSTEM_PROMPT = """
당신은 기업리포트 분석 전문가입니다. 다음 기업리포트 내용을 분석하여 주어진 질문에 답변하세요. 

분석 지침:
1. 리포트에서 질문과 직접 관련된 핵심 정보를 추출하세요.
2. 최신 정보를 우선적으로 고려하세요.
3. 여러 리포트 간 정보가 충돌할 경우, 최신 날짜의 정보와 대형사나 신뢰성이 있는 출처의 정보를 우선시하세요.
4. 숫자와 통계는 정확하게 인용하고, 출처를 명시하세요.
5. 분석가의 주관적 견해와 객관적 사실을 구분하여 표현하세요.
6. 특정 용어나 영어는 필요시 간단히 설명하세요.
7. 질문에 답변이 불확실성이 있는 경우, 그 한계를 명확히 표현하세요. 

"""
REPORT_ANALYSIS_USER_PROMPT = """
사용자 질문: {query}
종목명: {stock_name}
종목코드: {stock_code}
키워드: {keywords}

기업리포트 내용:
{report_contents}
"""

# 투자 의견 및 목표가 추출 프롬프트
INVESTMENT_OPINION_PROMPT = """
당신은 기업리포트에서 투자 의견과 목표가를 추출하는 전문가입니다.
다음 기업리포트 내용에서 투자 의견(매수, 중립, 매도 등)과 목표가를 추출하세요.

종목명: {stock_name}
종목코드: {stock_code}

기업리포트 내용:
{report_contents}

추출 지침:
1. 현재 투자의견(매수, 중립, 매도 등)을 정확히 추출하세요.
2. 목표가(target price)를 추출하세요.
3. 투자의견과 목표가의 근거가 되는 핵심 이유를 추출하세요.
4. 각 정보의 출처(증권사명)와 날짜를 함께 표시하세요.
5. 여러 증권사의 의견이 있을 경우, 모두 추출하고 최신 날짜순으로 정렬하세요.
6. 객관적으로 정보를 추출하고, 자의적인 내용은 추가하지 마세요.
"""

def format_report_contents(reports: List[Dict[str, Any]]) -> str:
    """
    검색된 기업리포트 내용을 형식화합니다.

    Args:
        reports: 검색된 리포트 목록

    Returns:
        형식화된 리포트 내용
    """
    if not reports:
        return "검색된 리포트가 없습니다."

    formatted_content = ""

    for i, report in enumerate(reports, 1):
        content = report.get("content", "")
        source = report.get("source", "미상")
        date = report.get("date", "")
        title = report.get("title", "")
        
        formatted_content += f"[리포트 {i}] {source}, {date}, {title}\n{content}\n\n"

    return formatted_content

def format_investment_opinions(reports: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """
    투자 의견 및 목표가 정보를 형식화합니다.

    Args:
        reports: 리포트 데이터 목록

    Returns:
        형식화된 투자 의견 데이터
    """
    results = {
        "by_source": {},
        "latest": [],
        "summary": {
            "avg_target_price": None,
            "opinions": {}
        }
    }
    
    if not reports:
        return results
    
    # 투자 의견 및 목표가 수집
    all_opinions = []
    target_prices = []
    opinion_counts = {}
    
    for report in reports:
        opinions = report.get("investment_opinions", [])
        for opinion in opinions:
            source = opinion.get("source", "미상")
            date = opinion.get("date", "")
            opinion_text = opinion.get("opinion", "")
            target_price = opinion.get("target_price")
            
            # 출처별 그룹화
            if source not in results["by_source"]:
                results["by_source"][source] = []
            
            opinion_data = {
                "date": date,
                "opinion": opinion_text,
                "target_price": target_price
            }
            
            results["by_source"][source].append(opinion_data)
            all_opinions.append({
                "source": source,
                "date": date,
                "opinion": opinion_text,
                "target_price": target_price
            })
            
            # 투자 의견 카운트
            if opinion_text:
                opinion_counts[opinion_text] = opinion_counts.get(opinion_text, 0) + 1
            
            # 목표가 수집
            if target_price:
                target_prices.append(target_price)
    
    # 날짜순 정렬
    for source in results["by_source"]:
        results["by_source"][source].sort(key=lambda x: x.get("date", ""), reverse=True)
    
    # 최신 의견만 선택 (각 증권사별 최신 의견)
    latest_by_source = {}
    for opinion in all_opinions:
        source = opinion.get("source")
        date = opinion.get("date", "")
        
        if source not in latest_by_source or date > latest_by_source[source]["date"]:
            latest_by_source[source] = opinion
    
    results["latest"] = list(latest_by_source.values())
    results["latest"].sort(key=lambda x: x.get("date", ""), reverse=True)
    
    # 요약 정보
    if target_prices:
        results["summary"]["avg_target_price"] = sum(target_prices) / len(target_prices)
    
    results["summary"]["opinions"] = opinion_counts
    
    return results 