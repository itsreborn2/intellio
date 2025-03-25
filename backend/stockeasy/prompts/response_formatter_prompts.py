"""
응답 포맷터 에이전트 프롬프트 템플릿

이 모듈은 통합된 지식 정보를 사용자에게 이해하기 쉬운 
형태로 포맷팅하는 응답 포맷터 에이전트에서 사용하는 프롬프트 템플릿을 정의합니다.
"""

from datetime import datetime
from typing import Dict, List, Union, Any

# 응답 포맷터 프롬프트
RESPONSE_FORMATTER_PROMPT = """
당신은 금융 정보 시스템의 응답 포맷팅 전문가입니다. 통합된 정보를 사용자에게 이해하기 쉽고
읽기 좋은 형식으로 변환하는 역할을 합니다.

사용자 질문: {query}

통합된 정보:
{integrated_response}

통합된 정보에서 추출된 주요 인사이트:
{core_insights}

신뢰도 평가:
{confidence_assessment}

불확실한 영역:
{uncertain_areas}

다음 지침에 따라 최종 응답을 작성하세요:
1. 명확하고 간결한 언어로 작성합니다.
2. 핵심 정보를 먼저 제시하고, 세부 사항은 그 후에 제공합니다.
3. 논리적인 흐름으로 정보를 구성합니다.
4. 필요한 경우 글머리 기호, 번호 매기기, 문단 나누기를 사용하여 가독성을 높입니다.
5. 가능한 경우 숫자나 데이터를 표로 정리하여 제시합니다.
6. 불확실한 영역이나 낮은 신뢰도의 정보는 명시적으로 표시합니다.
7. 사용자의 질문에 직접적으로 답변하는 방식으로 작성합니다.
8. 응답의 끝에 "추가 질문이 있으시면 언제든지 물어보세요." 문구를 추가합니다.

응답은 다음 형식으로 제공하세요:
1. 간결한 요약 (2-3문장)
2. 주요 포인트 (글머리 기호 목록)
3. 세부 설명 (필요한 경우)
4. 한계 및 주의사항 (낮은 신뢰도의 정보가 있는 경우)
5. 결론
"""

# 최적화된 응답 포맷터 프롬프트
OPTIMIZED_RESPONSE_FORMATTER_PROMPT = """
당신은 금융 정보를 사용자 친화적인 형식으로 변환하는 전문가입니다. 통합된 정보를 명확하고 구조화된 응답으로 변환하세요.

사용자 질문: {query}
종목명: {stock_name}
종목코드: {stock_code}
오늘 날짜: {today}

통합된 응답: 
{integrated_response}

신뢰도 평가:
{confidence_assessment}

불확실한 영역:
{uncertain_areas}

포맷팅 지침:
1. 명확한 구조로 정보를 체계화하세요:
   - 핵심 요약 (1-2문장)
   - 주요 요점 (글머리 기호)
   - 세부 설명 (필요시)
   - 한계점 (있는 경우)

2. 다음 포맷팅 요소를 활용하세요:
   - 중요 정보는 **굵게** 표시
   - 목록과 구분점으로 정보 분류
   - 주요 숫자 데이터는 표 형식으로 제시
   - 섹션은 제목(###)으로 구분

3. 다음 내용을 포함하세요:
   - 날짜/시간 정보 (데이터 최신성)
   - 불확실한 영역에 대한 명시적 언급
   - 신뢰도 수준이 낮은 정보 표시
   - 맨 마지막에 "추가 질문이 있으시면 언제든지 물어보세요."

4. 응답 스타일:
   - 전문적이면서 접근하기 쉬운 톤
   - 불필요한 금융 전문용어 최소화
   - 중요한 인사이트 강조
   - 직관적이고 읽기 쉬운 구조
"""

def format_response_formatter_prompt(
    query: str,
    stock_name: str = None,
    stock_code: str = None,
    integrated_response: str = None,
    core_insights: Union[Dict[str, Any], List[str]] = None,
    confidence_assessment: Union[Dict[str, Any], List[str]] = None,
    uncertain_areas: list = None
) -> str:
    """
    응답 포맷터 프롬프트를 포맷팅합니다.
    
    Args:
        query: 사용자 질문
        stock_name: 종목명
        stock_code: 종목코드
        integrated_response: 통합된 응답
        core_insights: 핵심 인사이트 (딕셔너리 또는 리스트)
        confidence_assessment: 신뢰도 평가 (딕셔너리 또는 리스트)
        uncertain_areas: 불확실한 영역
        
    Returns:
        포맷팅된 프롬프트 문자열
    """
    # 핵심 인사이트 포맷팅
    core_insights_str = ""
    if core_insights:
        if isinstance(core_insights, list):
            for i, insight in enumerate(core_insights, 1):
                core_insights_str += f"- 인사이트 {i}: {insight}\n"
        elif isinstance(core_insights, dict):
            for key, value in core_insights.items():
                core_insights_str += f"- {key}: {value}\n"
        else:
            core_insights_str = str(core_insights)
    
    # 신뢰도 평가 포맷팅
    confidence_assessment_str = ""
    if confidence_assessment:
        if isinstance(confidence_assessment, list):
            for i, assessment in enumerate(confidence_assessment, 1):
                confidence_assessment_str += f"- 평가 {i}: {assessment}\n"
        elif isinstance(confidence_assessment, dict):
            for key, value in confidence_assessment.items():
                confidence_assessment_str += f"- {key}: {value}\n"
        else:
            confidence_assessment_str = str(confidence_assessment)
    
    # 불확실 영역 포맷팅
    uncertain_areas_str = ""
    if uncertain_areas:
        for area in uncertain_areas:
            uncertain_areas_str += f"- {area}\n"
    
    today = datetime.now().strftime("%Y-%m-%d")
    return OPTIMIZED_RESPONSE_FORMATTER_PROMPT.format(
        query=query,
        stock_name=stock_name or "알 수 없음",
        stock_code=stock_code or "알 수 없음",
        today=today,
        integrated_response=integrated_response or "최종 요약 응답이 없습니다.",
        core_insights=core_insights_str or "핵심 인사이트가 없습니다.",
        confidence_assessment=confidence_assessment_str or "신뢰도 평가가 없습니다.",
        uncertain_areas=uncertain_areas_str or "불확실한 영역이 없습니다."
    ) 