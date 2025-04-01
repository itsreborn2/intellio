"""
오케스트레이터 에이전트 프롬프트

이 모듈은 오케스트레이터 에이전트가 워크플로우를 설계하는 데 사용하는 프롬프트를 정의합니다.
"""

from typing import Dict, List, Any, Optional


def format_orchestrator_prompt(
    query: str,
    question_analysis: Dict[str, Any],
    available_agents: Dict[str, str]
) -> str:
    """
    오케스트레이터 에이전트 프롬프트 포맷
    
    Args:
        query: 사용자 질문
        question_analysis: 질문 분석기의 결과
        available_agents: 사용 가능한 에이전트 목록
        
    Returns:
        포맷된 프롬프트
    """
    # 엔티티 정보 추출
    entities = question_analysis.get("entities", {})
    classification = question_analysis.get("classification", {})
    data_requirements = question_analysis.get("data_requirements", {})
    keywords = question_analysis.get("keywords", [])
    detail_level = question_analysis.get("detail_level", "보통")
    
    # 엔티티 정보 문자열 생성
    entity_str = ", ".join([f"{k}: {v}" for k, v in entities.items() if v])
    entity_str = entity_str if entity_str else "없음"
    
    # 키워드 목록 문자열 생성
    keyword_str = ", ".join(keywords) if keywords else "없음"
    
    # 데이터 요구사항 문자열 생성
    data_req_list = []
    if data_requirements.get("telegram_needed"):
        data_req_list.append("텔레그램 메시지")
    if data_requirements.get("reports_needed"):
        data_req_list.append("기업 리포트")
    if data_requirements.get("financial_statements_needed"):
        data_req_list.append("재무제표")
    if data_requirements.get("industry_data_needed"):
        data_req_list.append("산업 동향 데이터")
    
    data_req_str = ", ".join(data_req_list) if data_req_list else "없음"
    
    # 에이전트 목록 문자열 생성
    agent_list_str = "\n".join([f"- {name}: {desc}" for name, desc in available_agents.items()])
    
    # 프롬프트 템플릿
    prompt = f"""당신은 주식 분석 시스템의 오케스트레이터입니다. 사용자 질문과 질문 분석 결과를 바탕으로 
최적의 워크플로우를 설계해야 합니다. 워크플로우는 다양한 에이전트들의 실행 순서와 설정으로 구성됩니다.

## 사용자 질문
{query}

## 질문 분석 결과
- 주요 의도: {classification.get("primary_intent", "알 수 없음")}
- 복잡도: {classification.get("complexity", "알 수 없음")}
- 기대 답변 유형: {classification.get("expected_answer_type", "알 수 없음")}
- 요구 상세도: {detail_level}
- 추출된 엔티티: {entity_str}
- 주요 키워드: {keyword_str}
- 필요한 데이터: {data_req_str}

## 사용 가능한 에이전트
{agent_list_str}

## 당신의 임무
1. 질문에 가장 적합한 에이전트들을 선택하고 우선순위를 부여하세요.
2. 에이전트들의 최적 실행 순서를 결정하세요.
3. 데이터 통합 전략을 설계하세요.
4. 오류 발생 시 대응 전략(fallback)을 수립하세요.
5. 예상되는 출력물에 대해 기술하세요.

각 에이전트의 실행 여부(enabled)와 우선순위(priority)를 결정할 때:
- 질문의 의도와 복잡도를 고려하세요.
- 필요한 데이터 요구사항을 반영하세요.
- 우선순위는 1(낮음)부터 10(높음)까지의 숫자로 표현하세요.
- 기업리포트와 텔레그램 검색 에이전트는 높은 우선순위를 가집니다.
- 비공개 자료 검색 에이전트는 높은 우선순위를 가집니다.
- 간략한 답변이 요구되는 경우에는 기업리포트만 실행합니다.
- 텔레그램 검색 에이전트 적극 사용합니다.

주의: 
1. "knowledge_integrator"와 "response_formatter"는 항상 워크플로우에 포함되어야 합니다.
2. 실행 순서는 일반적으로 검색 에이전트들(telegram_retriever, report_analyzer 등) → knowledge_integrator → summarizer → response_formatter 순으로 구성됩니다.
3. 검색 에이전트들은 병렬로 실행될 수 있으므로, 실행 순서상 어떤 순서로 나열해도 괜찮습니다.
4. fallback_manager는 오류 발생 시에만 사용되므로 일반적인 실행 순서에 포함하지 마세요.


"""
    
# 응답은 다음 JSON 형식으로 제공하세요:
# {{
#   "agents": [
#     {{
#       "agent_name": "에이전트 이름",
#       "enabled": true/false,
#       "priority": 1-10 사이의 정수,
#       "parameters": {{}} // 필요한 경우 에이전트별 특수 매개변수
#     }},
#     // 다른 에이전트들...
#   ],
#   "execution_order": List[str] = Field(..., description="실행 순서"),
#   "integration_strategy": str = Field(..., description="정보 통합 전략"),
#   "expected_output": str = Field(..., description="예상 출력물"),
#   "fallback_strategy": str = Field(..., description="실패 시 대응 전략")
# }}

    return prompt 