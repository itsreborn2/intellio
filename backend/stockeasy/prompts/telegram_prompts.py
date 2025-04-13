"""
텔레그램 검색 에이전트를 위한 프롬프트 템플릿

이 모듈은 텔레그램 메시지 검색 및 관련 프롬프트 템플릿을 정의합니다.
"""

from typing import List

from stockeasy.models.agent_io import RetrievedTelegramMessage


TELEGRAM_SEARCH_PROMPT = """
당신은 금융 관련 내부DB 메시지 검색 전문가입니다. 다음 정보를 바탕으로 가장 관련성 높은 메시지를 검색하세요:

질문: {query}
종목코드: {stock_code}
종목명: {stock_name}
질문분류: {classification}

검색 전략:
1. 메시지의 시간적 관련성을 고려하세요. 최근 메시지에 더 높은 가중치를 부여합니다.
2. 종목명과 종목코드가 직접 언급된 메시지를 우선시하세요.
3. 질문 주제와 관련된 키워드(실적, 전망, 목표가 등)에 초점을 맞추세요.
4. 수치 정보(가격, 비율, 증감률 등)를 포함한 메시지에 더 높은 중요도를 부여하세요.

검색 파라미터:
- 유사도 임계값: {dynamic_threshold} (질문 복잡성에 따라 조정)
- 최대 검색 결과 수: {k} (질문 유형에 따라 조정)
- 중복 필터링 임계값: 0.8
"""

TELEGRAM_SUMMARY_PROMPT = """
당신은 금융 시장과 주식 관련 내부DB 메시지를 분석하고 요약하는 전문가입니다.
주어진 메시지들을 분석하여 다음 사항을 고려해 요약해주세요:

1. 메시지의 시간 순서를 고려하여 사건의 흐름을 파악하세요.
2. 중복되는 정보는 한 번만 포함하세요.
3. 질문과 관련 없는 메세지는 제외하세요.
4. 질문과 관련 없는 종목에 대한 메시지는 반드시 제외하세요.
5. 재무데이터(매출, 영업이익, 순이익)가 포함된 메시지의 경우, 종목명 또는 종목코드가 정확히 일치하지 않으면 제외하세요.
6. 구체적인 수치나 통계는 정확히 인용하세요.
7. 메시지 작성자의 주관적 의견과 객관적 사실을 구분하세요.
8. 요약은 명확하고 간결하게 작성하되, 중요한 세부사항은 포함하세요.

메시지 필터링 규칙:
- 재무데이터(매출, 영업이익, 순이익) 메시지는 위의 종목코드나 종목명이 정확히 언급된 경우에만 포함
- 다른 종목에 대한 내용이 혼합된 메시지에서는 관련 종목 정보만 추출하여 요약에 포함
"""


#def format_telegram_messages(messages):
def format_telegram_messages(telegram_data: dict, stock_code: str = None, stock_name: str = None):
    """텔레그램 메시지 목록을 형식화합니다.
    
    Args:
        telegram_data: 텔레그램 데이터 (messages와 summary를 포함)
        stock_code: 종목 코드
        stock_name: 종목명
        
    Returns:
        형식화된 메시지 문자열
    """

    # 요약만 넘길것인가
    # 요약 + 메시지 모두 넘길것인가
    summary = telegram_data.get("summary", "")
    messages = telegram_data.get("messages", [])
    
    if summary:
        content = f"\n종합결과: \n{summary}"
    else:
        formatted_msgs = []
        for msg in messages:
            created_at = msg["message_created_at"].strftime("%Y-%m-%d %H:%M")
            formatted_msgs.append(f"[{created_at}] {msg['content']}")
        content = "\n\n".join(formatted_msgs)
    return content if content else "내부DB 검색 결과 없음"
