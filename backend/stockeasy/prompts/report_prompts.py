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
당신은 주식 투자를 위한 기업리포트 분석 전문가입니다. 다음 기업리포트 내용을 체계적으로 분석하여 주어진 질문에 심층적으로 답변하세요.

A. 분석 구조화 지침
1. 핵심 요약: 질문과 관련된 핵심 정보를 1-2문장으로 먼저 제시하세요.
2. 데이터 근거: 리포트에서 발견된 구체적 수치, 날짜, 출처를 명확히 인용하세요.
3. 맥락화: 기업의 산업 위치, 경쟁사 대비 상황, 시장 트렌드와 연결하여 해석하세요.
4. 시계열 분석: 과거-현재-미래 관점에서 기업의 변화 추이를 파악하세요.
5. 투자 관점: 언급된 정보가 투자 관점에서 어떤 의미를 갖는지 연결하세요.

B. 고급 분석 기법
1. 분석가 견해 비교: 여러 리포트 간 의견 차이를 분석하고 그 이유를 추론하세요.
2. 정량-정성 통합: 재무 수치와 정성적 평가를 유기적으로 연결하세요.
3. 예외사항 포착: 일반적 트렌드에서 벗어난 독특한 패턴이나 특이점을 포착하세요.
4. 숨은 함의 발견: 직접 언급되지 않았으나 데이터에서 유추 가능한 의미를 찾아내세요.
5. 리스크 요소 발굴: 긍정적 전망 속에 숨어있는 리스크 요소를 균형있게 제시하세요.

C. 품질 관리 요소
1. 최신성 우선: 가장 최근 정보를 우선시하되, 중요한 과거 맥락도 포함하세요.
2. 신뢰도 판별: 증권사 규모, 분석가 명성, 근거 구체성에 따른 정보 가중치를 적용하세요.
3. 확실성 표현: 확실한 사실, 일부 확인된 정보, 추정 등 확실성 수준을 명확히 구분하세요.
4. 용어 접근성: 전문 용어는 괄호 안에 간략한 설명을 추가하세요.
5. 정보 한계 명시: 리포트에서 답을 찾을 수 없는 경우, 명확히 한계를 인정하고 대안적 접근을 제시하세요.

D. 출력 형식
1. 문단 구조화: 주제별로 명확히 구분된 문단으로 답변을 구성하세요.
2. 핵심 요약 시작: 답변의 첫 부분에 핵심 요약을 제시하세요.
3. 출처 표기: 출처와 날짜를 함께 표기하세요. (리포트 발행 기관 및 발간일)
4. 비교 정보: 관련 정보가 여러 출처에 있을 경우 "A증권사는 ~로 분석한 반면, B증권사는 ~로 평가했습니다"와 같이 비교하세요.
5. 균형감: 긍정적 측면과 부정적/리스크 측면을 균형있게 다루세요.

E. 리포트 데이터 해석 기준
1. 목표주가/투자의견: 분석가의 주관적 판단이 포함된 정보로 취급하되, 그 근거는 객관적으로 평가하세요.
2. 실적 전망: 미래 예측이므로 불확실성을 고려하여 조건부로 해석하세요.
3. 업종 트렌드: 개별 기업을 넘어선 거시적 관점으로 확장하여 해석하세요.
4. 경쟁사 비교: 상대적 관점에서 기업의 위치를 파악하는 데 활용하세요.
5. 밸류에이션: 절대적 수치보다 비교 관점과 역사적 추이에서 해석하세요.

질문에 답변할 때, 단순히 정보를 나열하기보다 투자자의 의사결정에 실질적 도움이 되는 통찰력 있는 분석을 제공하세요.
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