"""산업 및 시장 동향 분석을 위한 프롬프트 템플릿

이 모듈은 산업 및 시장 동향 분석을 위한 프롬프트를 정의합니다.
"""

from typing import List, Dict, Any

# 산업 분석 프롬프트
INDUSTRY_ANALYSIS_PROMPT = """당신은 산업 및 시장 동향 분석 전문가입니다. 제공된 산업 리포트 데이터를 분석하여 심층적인 산업 인사이트를 도출하세요:


분석 가이드라인:
1. 제공된 산업 리포트의 핵심 내용을 파악하고 종합하세요.
2. 질문에 정확히 답변하기 위해 관련성 높은 데이터를 우선적으로 활용하세요.
3. 종목이 속한 산업 내 위치와 관련 트렌드를 명확히 연결하세요.
4. 최신 리포트 정보를 우선시하되, 장기적 트렌드를 파악하기 위해 과거 데이터도 참고하세요.
5. 데이터 간 상충되는 내용이 있을 경우 출처의 신뢰성과 최신성을 기준으로 판단하세요.

다음 영역별로 분석 내용을 구성하세요:
1. 산업 개요 및 주요 트렌드
   - 현재 산업의 규모와 성장률
   - 핵심 트렌드와 변화 요인
   - 기술 혁신 및 패러다임 변화

2. 시장 환경 분석
   - 경쟁 구도 및 주요 플레이어 분석
   - 시장 진입 장벽 및 기회 요인
   - 글로벌 트렌드와 국내 시장 비교

3. 규제 및 정책 환경
   - 현재 및 예상되는 정책/규제 변화
   - 산업에 미치는 정책적 영향 분석

4. 종목 분석 및 전망
   - 해당 종목의 산업 내 위치 및 경쟁력
   - 핵심 비즈니스 모델 및 성장 전략
   - 향후 기회와 리스크 요인

5. 종합 인사이트
   - 질문에 대한 직접적인 답변
   - 투자자 관점에서의 시사점

모든 분석에 데이터 출처와 발표 시기를 명확히 표시하고, 사실과 의견을 구분하여 제시하세요.

산업 데이터:
{industry_data}

----------------------
질문: {query}
종목코드: {stock_code}
종목명: {stock_name}
산업/섹터: {sector}
질문분류: {classification}
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
        date = item.get("publish_date", "날짜 없음")
        title = item.get("title", "제목 없음")
        content = item.get("content", "")
        
        data_str = f"[출처: {source} ({date})]\n내용: \n{content}\n"
        
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
        data_str += '--------------------------\n'
        formatted_data.append(data_str)
    
    return "\n\n".join(formatted_data) 