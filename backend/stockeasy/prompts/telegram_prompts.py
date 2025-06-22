"""
텔레그램 검색 에이전트를 위한 프롬프트 템플릿

이 모듈은 텔레그램 메시지 검색 및 관련 프롬프트 템플릿을 정의합니다.
"""

from typing import List

from stockeasy.models.agent_io import RetrievedTelegramMessage


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

TELEGRAM_SUMMARY_PROMPT_2 = """
내부DB에서 보고서 목차에 맞는 정보를 추출하고 매핑하는 전문가입니다.

## 목표
- 목차 항목별로 <메세지모음></메세지모음> 내 관련 정보 추출
- 원본 메시지 왜곡 없이 핵심만 발췌  
- 메시지 출처(시간) 식별

## 추출 대상
1. **텍스트**: 목차 관련 핵심 내용, 의견, 전망
2. **수치**: 실적, 가격, 통계 (단위 포함)
3. **키워드**: 목차 관련 중요 용어

## 작업 규칙
- **목차 우선**: 목차 기준으로만 정보 추출
- **정확성**: 원본 내용 왜곡 금지
- **출처 필수**: 각 정보의 메시지 시간 표시
- **중복 최소화**: 동일 정보 반복 제거

**중요**: 
- <메세지모음></메세지모음> 내 데이터만 사용
- 목차 내용을 content에 포함 금지
- 추측/생성 금지, 정보 없으면 "관련 메시지 없음"

출력형식 JSON:
```json
{{
  "섹션제목_1": [
    {{"type": "text", "content": "...", "date": "메세지일자"}},
    {{"type": "table", "content": "...", "date": "메세지일자"}}
  ],
  "섹션제목_2": [
    {{"type": "text", "content": "...", "date": "메세지일자"}}
  ]
}}
```
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
