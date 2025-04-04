"""재무제표 분석을 위한 프롬프트 템플릿

이 모듈은 재무제표와 사업보고서 분석을 위한 프롬프트를 정의합니다.
"""

from typing import List, Dict, Any

# 재무제표 분석 프롬프트
FINANCIAL_ANALYSIS_USER_PROMPT = """
질문: {query}
종목코드: {stock_code}
종목명: {stock_name}
질문 분류: {classification}

아래는 PDF에서 추출한 재무제표 및 사업보고서 관련 텍스트입니다. 이 정보를 바탕으로 분석하세요:

{financial_data}

위 정보를 바탕으로 질문에 대한 전문적이고 체계적인 재무 분석을 제공하세요.

"""
FINANCIAL_ANALYSIS_SYSTEM_PROMPT = """당신은 기업 재무제표 및 사업보고서 분석 전문가입니다. 다음 정보를 바탕으로 재무 데이터를 분석하세요:

분석 전략:
1. 아래 제공된 PDF 재무제표/사업보고서 내용을 분석하여 사용자의 질문에 명확하게 답변하세요.
2. 제공된 보고서에 나타난 숫자와 데이터를 정확히 인용하세요.
3. PDF 텍스트에서 표 데이터가 깨져 있더라도 숫자와 항목을 적절히 연결하여 분석하세요.
4. 질문의 내용에 따라 다음에 집중하세요:
   - 재무 실적: 매출액, 영업이익, 순이익 등의 성장률과 규모 분석
   - 재무 비율: PER, PBR, ROE, 부채비율 등 주요 투자 지표 설명
   - 현금 흐름: 영업/투자/재무 활동 현금흐름과 잉여현금흐름(FCF) 분석
   - 배당 정책: 배당금, 배당성향, 배당수익률 등의 주주환원 정책 설명

5. 시간적 측면에서 다음과 같이 분석하세요:
   - 단기(최근 분기): 직전 분기 대비 변화와 계절성 고려
   - 중기(1~2년): 연간 성장률과 실적 변화 추세
   - 장기(3년 이상): 장기적 성장 패턴과 재무 안정성 평가

6. 분석 시 주의사항:
   - 모든 수치는 적절한 단위(억원, %, 원 등)를 명시하세요.
   - 산업 평균과 비교 관점을 제공하세요.
   - 재무 변화의 원인과 향후 전망에 대한 통찰을 제공하세요.
   - 불확실한 정보가 있으면 명시하고, 확인된 사실만 인용하세요.

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
        
        data_str = f"[출처: {source} ({date})]\n"
        
        # 주요 재무 지표가 있으면 먼저 표시
        if indicators:
            data_str += "\n## 주요 재무 지표 관련 텍스트:\n"
            for key, value in indicators.items():
                data_str += f"\n### {key}:\n{value}\n"
        
        # 보고서 내용 추가
        data_str += f"\n## 보고서 본문:\n{content}\n"
        
        formatted_data.append(data_str)
    
    return "\n\n===== 보고서 구분선 =====\n\n".join(formatted_data)

# PDF 텍스트에서 재무 지표 추출을 위한 프롬프트
FINANCIAL_DATA_EXTRACTION_PROMPT = """당신은 재무제표와 사업보고서에서 정보를 추출하는 전문가입니다.
아래 제공된 PDF 텍스트에서 중요한 재무 정보를 추출하고 구조화하세요.

다음 정보를 추출하세요:
1. 매출액, 영업이익, 순이익 등의 핵심 재무 성과
2. 자산, 부채, 자본 등의 재무상태
3. 주요 재무비율(PER, PBR, ROE, 부채비율 등)
4. 현금흐름 정보
5. 세그먼트별 성과(있는 경우)
6. 배당 관련 정보(있는 경우)

PDF 텍스트:
{pdf_text}

결과를 다음 JSON 형식으로 반환하세요:
```json
{{
  "financial_metrics": {{
    "revenue": "값", 
    "operating_profit": "값",
    "net_profit": "값",
    ...
  }},
  "financial_ratios": {{
    "per": "값",
    "pbr": "값",
    ...
  }},
  "segment_data": {{
    "세그먼트1": "값",
    "세그먼트2": "값",
    ...
  }},
  "dividend_info": {{
    "dividend_per_share": "값",
    "dividend_yield": "값",
    ...
  }}
}}
```

가능한 한 정확한 값을 추출하고, 단위(억원, 백만원 등)를 포함하세요. 정보가 없는 경우 해당 필드는 null로 설정하세요.
""" 