"""산업 및 시장 동향 분석을 위한 프롬프트 템플릿

이 모듈은 산업 및 시장 동향 분석을 위한 프롬프트를 정의합니다.
"""

from typing import List, Dict, Any

# 산업 분석 프롬프트
INDUSTRY_ANALYSIS_PROMPT = """당신은 산업 및 시장 동향 분석 전문가입니다. 다음 정보를 바탕으로 산업 관련 정보를 검색하고 분석하세요:

질문: {query}
종목코드: {stock_code}
종목명: {stock_name}
산업/섹터: {sector}
질문분류: {classification}

분석 전략:
1. 최신 산업 동향 정보를 우선적으로 검색하세요.
2. 다음 소스의 정보를 균형있게 참조하세요:
   - 산업 전문 블로그 및 뉴스
   - 정부/협회 발표 자료
   - 시장 조사 기관 보고서
   - 전문가 칼럼 및 인터뷰

3. 질문 주제에 따라 다음 정보에 집중하세요:
   - 산업 규모 및 성장률
   - 주요 트렌드 및 기술 변화
   - 규제 환경 및 정책 변화
   - 경쟁 구도 및 주요 기업 동향
   - 해당 종목의 산업 내 위치 및 경쟁력

4. 산업의 과거, 현재, 미래 흐름을 연결하여 설명하세요.
5. 글로벌 트렌드와 국내 시장의 차이점을 비교하세요.

정보의 출처와 발표 시기를 명확히 표시하고, 의견과 사실을 구분하여 제시하세요.

산업 데이터:
{industry_data}
"""

def format_industry_data(industry_data: List[Dict[str, Any]]) -> str:
    """산업 데이터를 문자열로 포맷팅합니다.

    Args:
        industry_data: 산업 데이터 리스트

    Returns:
        str: 포맷팅된 산업 데이터 문자열
    """
    if not industry_data:
        return "산업 데이터가 없습니다."
    
    formatted_data = []
    
    for item in industry_data:
        source = item.get("source", "알 수 없는 출처")
        date = item.get("date", "날짜 없음")
        title = item.get("title", "제목 없음")
        content = item.get("content", "")
        
        data_str = f"[출처: {source} ({date})]\n제목: {title}\n\n{content}\n"
        
        # 주요 트렌드 정보가 있는 경우
        key_trends = item.get("key_trends", [])
        if key_trends:
            data_str += "\n주요 트렌드:\n"
            for trend in key_trends:
                data_str += f"- {trend}\n"
        
        # 시장 데이터가 있는 경우
        market_data = item.get("market_data", {})
        if market_data:
            data_str += "\n시장 데이터:\n"
            for key, value in market_data.items():
                data_str += f"- {key}: {value}\n"
        
        # 정책 변화 정보가 있는 경우
        policy_changes = item.get("policy_changes", [])
        if policy_changes:
            data_str += "\n정책 변화:\n"
            for policy in policy_changes:
                data_str += f"- {policy}\n"
        
        formatted_data.append(data_str)
    
    return "\n\n".join(formatted_data) 