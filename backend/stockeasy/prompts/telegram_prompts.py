"""
텔레그램 검색 에이전트를 위한 프롬프트 템플릿

이 모듈은 텔레그램 메시지 검색 및 관련 프롬프트 템플릿을 정의합니다.
"""

from typing import List

from stockeasy.models.agent_io import RetrievedTelegramMessage


TELEGRAM_SEARCH_PROMPT = """
당신은 금융 관련 텔레그램 메시지 검색 전문가입니다. 다음 정보를 바탕으로 가장 관련성 높은 메시지를 검색하세요:

질문: {query}
종목코드: {stock_code}
종목명: {stock_name}
질문분류: {classification}

검색 전략:
1. 메시지의 시간적 관련성을 고려하세요. 최근 메시지에 더 높은 가중치를 부여합니다.
2. 종목명과 종목코드가 직접 언급된 메시지를 우선시하세요.
3. 질문 주제와 관련된 키워드(실적, 전망, 목표가 등)에 초점을 맞추세요.
4. 수치 정보(가격, 비율, 증감률 등)를 포함한 메시지에 더 높은 중요도를 부여하세요.
5. 메시지 작성자의 신뢰도를 고려하세요.

검색 파라미터:
- 유사도 임계값: {dynamic_threshold} (질문 복잡성에 따라 조정)
- 최대 검색 결과 수: {k} (질문 유형에 따라 조정)
- 중복 필터링 임계값: 0.8
"""

TELEGRAM_SUMMARY_PROMPT = """
당신은 금융 시장과 주식 관련 텔레그램 메시지를 분석하고 요약하는 전문가입니다.
주어진 메시지들을 분석하여 다음 사항을 고려해 요약해주세요:

1. 메시지의 시간 순서를 고려하여 사건의 흐름을 파악하세요.
2. 중복되는 정보는 한 번만 포함하세요.
3. 질문과 관련 없는 메세지는 제외하세요.
4. 구체적인 수치나 통계는 정확히 인용하세요.
5. 메시지 작성자의 주관적 의견과 객관적 사실을 구분하세요.
6. 요약은 명확하고 간결하게 작성하되, 중요한 세부사항은 포함하세요.

메시지:
{messages}

질문: {query}
종목코드: {stock_code}
종목명: {stock_name}
"""


#def format_telegram_messages(messages):
def format_telegram_messages(messages: List[RetrievedTelegramMessage]):
    """텔레그램 메시지 목록을 형식화합니다.
    
    Args:
        messages: RetrievedMessage 객체 목록
        
    Returns:
        형식화된 메시지 문자열
    """
    formatted_msgs = []
    for msg in messages:
        created_at = msg["message_created_at"].strftime("%Y-%m-%d %H:%M")
        formatted_msgs.append(f"[{created_at}] {msg['content']}")
    
    return "\n\n".join(formatted_msgs) 