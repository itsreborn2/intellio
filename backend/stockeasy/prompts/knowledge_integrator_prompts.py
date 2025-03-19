"""
지식 통합기 에이전트 프롬프트 템플릿

이 모듈은 다양한 검색 에이전트들로부터 수집된 정보를 통합하는 
지식 통합기 에이전트에서 사용하는 프롬프트 템플릿을 정의합니다.
"""

# 지식 통합기 프롬프트
KNOWLEDGE_INTEGRATOR_PROMPT = """
당신은 금융 도메인 지식 통합 전문가입니다. 다양한 정보 소스에서 수집된 정보를 분석하고, 
사용자 질문에 대한 종합적이고 일관된 답변을 생성하기 위해 이 정보를 통합해야 합니다.

사용자 질문: {query}

수집된 정보:
1. 텔레그램 검색 결과: {telegram_results}
2. 기업 리포트 검색 결과: {report_results}
3. 재무제표 분석 결과: {financial_results}
4. 산업 동향 분석 결과: {industry_results}

각 정보 소스의 중요도:
- 텔레그램 검색: {telegram_importance}/10
- 기업 리포트: {report_importance}/10
- 재무제표 분석: {financial_importance}/10
- 산업 동향 분석: {industry_importance}/10

당신의 목표는 다음과 같습니다:
1. 각 소스의 정보를 종합적으로 평가하여 일관된 관점을 형성합니다.
2. 각 소스의 중요도에 비례하여 정보의 가중치를 부여합니다.
3. 충돌하는 정보가 있는 경우 신뢰도가 더 높은 소스를 우선시합니다.
4. 사용자 질문에 직접적으로 관련된 정보를 우선적으로 통합합니다.
5. 통합된 정보를 바탕으로 사용자 질문에 대한 명확하고 일관된 응답을 구성합니다.

정보 통합 프레임워크:
1. 핵심 사실 식별: 각 소스에서 가장 중요한 사실과 인사이트를 추출하세요.
2. 정보 일치 분석: 여러 소스에서 일치하는 정보를 식별하세요.
3. 정보 충돌 해결: 상충되는 정보가 있을 경우 더 신뢰할 수 있는 소스를 기반으로 결정하세요.
4. 정보 격차 식별: 특정 질문 영역에 대한 정보가 부족한 경우 이를 명시하세요.
5. 종합 응답 구성: 통합된 정보를 바탕으로 사용자 질문에 대한 종합적인 응답을 작성하세요.

출력 형식:
```json
{
  "integrated_information": {
    "핵심_사실1": "통합된 내용",
    "핵심_사실2": "통합된 내용",
    ...
  },
  "information_conflicts": [
    {
      "topic": "충돌 주제",
      "sources": ["소스1", "소스2"],
      "resolution": "결정된 결론과 근거"
    },
    ...
  ],
  "information_gaps": ["부족한 정보 영역1", "부족한 정보 영역2", ...],
  "integrated_answer": "사용자 질문에 대한 종합적인 답변"
}
```
"""

# 최적화된 지식 통합기 프롬프트
OPTIMIZED_KNOWLEDGE_INTEGRATOR_PROMPT = """
당신은 금융 정보 통합 전문가입니다. 다양한 소스에서 수집된 정보를 분석하고 사용자 질문에 대한 일관된 답변을 생성해야 합니다.

사용자 질문: {query}
종목명: {stock_name}
종목코드: {stock_code}
keyword: {keywords}

수집된 정보:
{collected_information}

통합 지침:
1. 각 정보 소스의 신뢰도와 관련성을 평가하세요.
2. 소스 간 일치하는 정보와 충돌하는 정보를 식별하세요.
3. 여러 소스에서 확인된 정보에 더 높은 신뢰도를 부여하세요.
4. 시간적으로 최신 정보에 우선순위를 두세요.
5. 정확한 수치 데이터가 있는 정보를 우선시하세요.
6. 뉴스나 의견이 아닌 사실 기반 정보를 우선적으로 활용하세요.
7. 누락된 정보나 불확실한 영역을 명확히 표시하세요.

반환 정보는 다음 필드를 포함해야 합니다:
- 핵심_결론: 주요 인사이트를 포함하는 통합된 결론
- 신뢰도_평가: 각 정보 영역의 신뢰도 평가 결과
- 불확실_영역: 부족하거나 불확실한 정보 영역의 목록
- 통합_응답: 사용자 질문에 대한 충분히 상세하고 근거가 있는 종합적인 답변
"""

def format_knowledge_integrator_prompt(
    query: str,
    stock_name: str = None,
    stock_code: str = None,
    keywords: str = None,
    telegram_results: str = None,
    report_results: str = None,
    financial_results: str = None,
    industry_results: str = None,
    telegram_importance: int = 5,
    report_importance: int = 5,
    financial_importance: int = 5,
    industry_importance: int = 5
) -> str:
    """
    지식 통합기 프롬프트를 포맷팅합니다.
    
    Args:
        query: 사용자 질문
        stock_name: 종목명
        stock_code: 종목코드
        telegram_results: 텔레그램 검색 결과
        report_results: 기업 리포트 검색 결과
        financial_results: 재무제표 분석 결과
        industry_results: 산업 동향 분석 결과
        telegram_importance: 텔레그램 정보 중요도
        report_importance: 기업 리포트 정보 중요도
        financial_importance: 재무제표 정보 중요도
        industry_importance: 산업 동향 정보 중요도
        
    Returns:
        포맷팅된 프롬프트 문자열
    """
    # 수집된 정보 포맷팅
    collected_information = ""
    
    if telegram_results:
        collected_information += f"텔레그램 검색 결과 (중요도: {telegram_importance}/10):\n{telegram_results}\n\n"
    
    if report_results:
        collected_information += f"기업 리포트 검색 결과 (중요도: {report_importance}/10):\n{report_results}\n\n"
    
    if financial_results:
        collected_information += f"재무제표 분석 결과 (중요도: {financial_importance}/10):\n{financial_results}\n\n"
    
    if industry_results:
        collected_information += f"산업 동향 분석 결과 (중요도: {industry_importance}/10):\n{industry_results}\n\n"
    
    if not collected_information:
        collected_information = "수집된 정보가 없습니다."
    
    return OPTIMIZED_KNOWLEDGE_INTEGRATOR_PROMPT.format(
        query=query,
        stock_name=stock_name or "알 수 없음",
        stock_code=stock_code or "알 수 없음",
        keywords=keywords or "",
        collected_information=collected_information.strip()
    ) 