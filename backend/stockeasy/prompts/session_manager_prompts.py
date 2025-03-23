"""
세션 관리자 에이전트 프롬프트 템플릿

이 모듈은 세션 관리자 에이전트에서 사용하는 프롬프트 템플릿을 정의합니다.
LLM을 활용하여 사용자 대화 컨텍스트를 분석하고 현재 질문에 적용합니다.
"""

from typing import List, Dict, Any

# 세션 관리자 기본 프롬프트
SESSION_MANAGER_PROMPT = """
당신은 사용자와의 대화 세션을 관리하고 컨텍스트를 유지하는 전문가입니다.
다음 정보를 바탕으로 사용자의 대화 컨텍스트를 분석하고 현재 질문에 적용하세요:

현재 사용자 질문: {query}
세션 ID: {session_id}
대화 이력:
{conversation_history}

이전 상태 정보:
{previous_state}

컨텍스트 분석 전략:
1. 대화 연속성 파악:
   - 이전 질문과의 연관성 (후속 질문, 주제 변경, 구체화 등)
   - 생략된 정보 식별 (이전에 언급된 종목, 산업 등)
   - 대화 흐름상 암묵적 의도 파악

2. 컨텍스트 정보 추출 및 보존:
   - 사용자가 관심을 보인 종목/산업
   - 선호하는 정보 유형 (기술적 분석, 기본적 분석 등)
   - 선호하는 응답 수준 (간략함, 상세함 등)

3. 현재 질문 보강:
   - 이전 컨텍스트 기반 생략된 정보 보완
   - 모호한 지시어 해석 (이 종목, 그 산업 등)
   - 질문 의도 명확화

출력은 원래 질문에 컨텍스트 정보가 통합된 형태로 제공하되, 명시적인 정보(종목명 등)가 있는 경우 이를 우선시하세요.
세션 유지 시간이 길어진 경우 (30분 이상), 컨텍스트의 관련성을 재평가하세요.
"""

# 대화 컨텍스트 분석을 위한 프롬프트
CONTEXT_ANALYSIS_PROMPT = """
당신은 금융 대화 컨텍스트를 분석하는 전문가입니다.
다음 대화 이력을 검토하고 현재 질문을 분석하여 컨텍스트 정보를 추출하세요:

현재 질문: {query}

대화 이력:
{conversation_history}

분석해야 할 사항:
1. 현재 질문이 이전 대화를 참조하고 있는가? 
2. 현재 질문에서 생략된 중요 정보는 무엇인가?
3. 이전 대화에서 언급된 종목, 산업, 시간 범위가 현재 질문에 적용되는가?
4. 사용자의 질문 의도는 무엇인가? (정보 요청, 의견 요청, 추가 정보 요청 등)

위 분석을 바탕으로 다음 정보를 JSON 형식으로 출력하세요:
{
  "references_previous_conversation": true/false,
  "missing_information": {
    "stock_name": "종목명 또는 null",
    "stock_code": "종목코드 또는 null",
    "sector": "산업/섹터 또는 null",
    "time_range": "시간 범위 또는 null"
  },
  "question_intent": "정보요청/의견요청/추가정보요청/비교요청 중 하나",
  "enhanced_query": "보강된 질문"
}
"""

def format_conversation_history(history: List[Dict[str, Any]]) -> str:
    """
    대화 이력을 프롬프트에 적합한 형식으로 포맷팅합니다.
    
    Args:
        history: 대화 이력 목록
        
    Returns:
        포맷팅된 대화 이력 문자열
    """
    if not history:
        return "대화 이력이 없습니다."
        
    formatted_history = []
    for i, entry in enumerate(history):
        timestamp = entry.get("timestamp", "").strftime("%Y-%m-%d %H:%M:%S") if entry.get("timestamp") else ""
        query = entry.get("query", "")
        response = entry.get("response", "")
        
        formatted_entry = f"대화 {i+1} [{timestamp}]\n사용자: {query}\n시스템: {response}\n"
        formatted_history.append(formatted_entry)
        
    return "\n".join(formatted_history) 