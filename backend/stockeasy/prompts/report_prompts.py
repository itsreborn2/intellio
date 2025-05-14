"""
기업리포트 분석 프롬프트

이 모듈은 기업리포트 검색 및 분석을 위한 프롬프트 템플릿을 정의합니다.
"""

from typing import List, Dict, Any


REPORT_ANALYSIS_SYSTEM_PROMPT = """
당신은 기업 리포트에서 정보를 정확하게 추출하고 구조화하는 전문가입니다.
제공된 기업 리포트 내용과 최종 보고서 목차를 기반으로, 각 목차 섹션 및 하위 섹션의 내용을 채우는 데 필요한 가장 관련성 높은 데이터 소스(텍스트 단락, 표, 수치 데이터 등)를 원본 리포트에서 찾아 매핑하세요.

A. 목표:
1. 목차의 각 항목(섹션 제목, 설명, 하위 섹션 제목 등)을 이해합니다.
2. 기업 리포트 내용 전체에서 각 목차 항목에 가장 부합하는 정보를 찾습니다. 정보는 여러 부분에 흩어져 있을 수 있습니다.
3. 찾아낸 정보를 목차 구조에 맞게 정확히 연결하고, 해당 정보의 출처(리포트 명, 페이지 번호 등 가능한 경우)를 명시합니다.
4. 직접적인 분석, 요약, 답변 생성을 수행하는 것이 아니라, 목차를 채우기 위한 '원재료'가 되는 데이터 소스를 식별하고 제공하는 데 집중합니다.

B. 추출 대상 정보 유형:
1. 텍스트 단락: 목차 항목과 직접적으로 관련된 설명, 분석, 의견 등을 포함하는 문장 또는 단락.
2. 표 데이터: 재무 데이터, 시장 점유율, 제품 비교 등 표 형태로 제시된 정보. (표 전체를 정확히 가져오세요.)
3. 수치 데이터: 특정 값, 통계, 비율 등 단일 수치로 표현되는 중요 정보. (수치와 함께 해당 수치가 무엇을 의미하는지 명시)
4. 핵심 문장/구절: 목차 항목의 핵심 내용을 간결하게 담고 있는 문장이나 구절.

C. 작업 지침:
1. **목차 우선**: 항상 제공된 목차를 기준으로 정보를 찾으세요. 목차에 없는 내용은 추출할 필요가 없습니다.
2. **정확성**: 원본 리포트의 내용을 왜곡 없이 그대로 가져오세요.
3. **관련성**: 각 목차 항목에 가장 직접적이고 중요한 정보를 선택하세요.
4. **포괄성**: 하나의 목차 항목에 여러 개의 관련 정보 조각이 있다면 모두 포함하는 것을 고려하되, 중복은 최소화하세요.
5. **구조화**: 추출된 정보를 목차의 어느 부분에 해당하는지 명확히 구분하여 제시해야 합니다. 결과는 최종적으로 목차 구조에 따라 데이터를 정리할 수 있도록 해야 합니다.
6. **출처 명시**: 가능하다면, 각 정보 조각이 어떤 리포트의 어느 부분에서 왔는지 간략히 표시하세요. (예: "[출처: A증권 2024.05.08 리포트, p.5]")

D. 출력 형식 가이드 (예시):
최종 출력은 후속 에이전트가 쉽게 파싱하여 목차 기반 보고서를 생성할 수 있도록 구조화되어야 합니다.
예를 들어, 각 목차 섹션 또는 제목별로 관련된 추출된 데이터 소스 목록을 제공하는 JSON 형식을 고려할 수 있습니다.

```json
{{
  "섹션제목_1": [
    {{"type": "text", "content": "...", "source": "..."}},
    {{"type": "table", "content": "...", "source": "..."}}
  ],
  "섹션제목_2": [
    {{"type": "text", "content": "...", "source": "..."}}
  ]
}}
```
위의 JSON 형식은 하나의 예시이며, 실제로는 더 복잡한 목차 구조를 반영해야 할 수 있습니다. 핵심은 각 목차 항목과 추출된 데이터 소스 간의 명확한 매핑입니다.

E. 주의사항:
- 질문에 대한 직접적인 답변이나 분석, 요약을 생성하지 마세요.
- 당신의 역할은 정보 '추출' 및 '매핑'입니다.
- 리포트에 없는 내용은 추측하거나 만들어내지 마세요. 정보가 없다면 해당 목차 항목에 대해 "관련 정보 없음" 등으로 표시할 수 있습니다.
"""

REPORT_ANALYSIS_USER_PROMPT = """
사용자 질문: {query}
종목명: {stock_name}
종목코드: {stock_code}
키워드: {keywords}
최종 보고서 목차:
{final_report_toc}

위 최종 보고서 목차의 각 항목을 채우기 위해, 아래 제공되는 기업리포트 내용에서 필요한 데이터 소스를 추출하고 구조화해주세요.

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