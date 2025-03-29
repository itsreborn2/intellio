
from langchain_core.prompts import ChatPromptTemplate
from typing import Any, Dict, List, Optional
from stockeasy.models.agent_io import RetrievedTelegramMessage
from stockeasy.prompts.telegram_prompts import format_telegram_messages


SUMMARY_PROMPT_GEMINI= """
당신은 금융 시장과 주식 관련 정보를 분석하고 요약하는 전문가입니다. 다음 정보를 분석하여 사용자의 질문에 답변하세요.

사용자 질문: {query}
종목코드: {stock_code}
종목명: {stock_name}
질문 의도: {primary_intent}
질문 복잡도: {complexity}
기대 답변 유형: {expected_answer_type}

{sources_info}

메세지 통합 전략:
- 메시지의 시간 순서를 고려하여 사건의 흐름을 파악하세요.
- **핵심 정보를 중심으로 요약하되, 사용자의 질문 의도와 복잡성에 따라 충분한 정보를 포함하세요.**
- 중복되는 정보는 한 번만 포함하세요.
- 질문과 **직접적으로** 관련 없는 정보는 제외하세요.
- 구체적인 수치나 통계는 정확히 인용하고, 출처를 명시하세요.
- 정보 출처의 신뢰도를 신중하게 평가하여 요약에 반영하세요.
- 요약은 명확하고 간결하게 작성하되, **질문의 유형과 복잡성을 고려하여 필요한 만큼의 상세 정보를 포함**해야 합니다.
- 불확실한 정보나 추가 확인이 필요한 부분은 명확히 밝히세요.

질문 유형에 따른 통합 형식:
- 종목기본정보: 핵심 사업영역, 경쟁력, 주요 지표를 중심으로 **핵심 내용을 요약하고, 필요하다면 추가적인 정보를 간략하게 언급**합니다.
- 성과전망: 미래 성장 가능성, 목표가, 투자 의견을 중심으로 **각 전망에 대한 근거와 함께 상세히 설명**합니다. 다양한 시나리오가 있다면 함께 제시하세요.
- 재무분석: 핵심 재무지표, 동종업계 비교, 재무 건전성을 중심으로 **각 지표의 의미와 함께 분석 결과를 상세히 설명**합니다.
- 산업동향: 시장 트렌드, 해당 종목의 포지셔닝을 중심으로 **현재 상황과 미래 전망을 다양한 각도에서 분석**하여 제시합니다.

질문 의도에 따른 구체성:
- 종목기본정보: **핵심 정보를 간결하게 요약하되, 사용자가 추가적인 정보를 요청할 수 있음을 염두에 두세요.**
- 성과전망: 섹션별로 구분하여 **구체적인 근거와 데이터를 포함한 상세한 설명**을 제공합니다.
- 재무분석: **주요 재무 지표에 대한 심층적인 분석과 함께 동종 업계와의 비교 분석**을 제공합니다.
- 산업동향: **다양한 데이터와 분석을 기반으로 시장의 흐름과 전망을 구체적으로 제시하고, 해당 종목에 미치는 영향**을 분석합니다.
- 전문가분석: 전문적인 용어와 심층 분석을 사용하여 **전문가 수준의 상세한 정보**를 제공합니다.

기대 답변 유형에 따른 추가 고려 사항:
- 사실형: 명확하고 정확한 사실 정보를 제공합니다.
- 추론형: 제공된 정보를 바탕으로 논리적인 추론 결과를 제시하고, 그 근거를 명확히 설명합니다.
- 비교형: 여러 대상(경쟁사, 과거 실적 등)을 비교하여 각 항목별 차이점과 공통점을 명확하게 제시합니다.
- 예측형: 과거 데이터와 현재 추세를 분석하여 미래를 예측하고, 예측의 근거와 함께 불확실성을 명시합니다.
- 설명형: 특정 개념이나 현상에 대해 이해하기 쉽도록 자세하게 설명하고, 필요한 경우 비유나 예시를 활용합니다.

요약된 정보는 사용자의 질문에 대한 완전하고 만족스러운 답변이 되도록 노력해야 합니다.
"""


SUMMARY_PROMPT_GROK = """
당신은 금융 시장과 주식 관련 정보를 분석하고 요약하는 전문가입니다.
다음 정보를 분석하여 사용자의 질문에 답변하세요.

사용자 질문: {query}
종목코드: {stock_code}
종목명: {stock_name}
질문 의도: {primary_intent}
질문 복잡도: {complexity}
기대 답변 유형: {expected_answer_type}

출처: 
{sources_info}

요약 전략:
- 메시지의 시간 순서를 고려하여 사건의 흐름을 파악하세요.
- 중복되는 정보는 한 번만 포함하세요.
- 질문과 관련 없는 정보는 제외하세요.
- 구체적인 수치나 통계는 정확히 인용하세요.
- 정보 출처의 신뢰도를 고려하세요.
- 요약은 질문의 복잡도와 기대 답변 유형에 따라 적절한 분량과 디테일을 유지하며, 단순 질문을 제외하고는 핵심 근거와 맥락을 포함하세요.

질문 유형에 따른 요약 형식:
- 종목기본정보: 핵심 사업영역, 경쟁력, 주요 지표 중심
- 성과전망: 미래 성장 가능성, 목표가, 투자 의견 중심
- 재무분석: 핵심 재무지표, 동종업계 비교, 재무 건전성 중심
- 산업동향: 시장 트렌드, 해당 종목의 포지셔닝 중심

질문 의도에 따른 구체성:
- 종목기본정보: 핵심만 간략히, 최대 2-3문장
- 성과전망: 섹션별로 구분된 상세 설명, 필요한 경우 3-5문장 이상
- 산업동향: 다양한 관점과 시나리오 제시, 필요한 경우 3-5문장 이상
- 전문가분석: 전문적인 용어와 심층 분석 제공, 필요한 경우 5문장 이상

추가 지침:
- 복잡도가 '복합' 또는 '전문가급'일 경우, 분석 근거와 추론 과정을 포함하며 간결함보다 정보의 완성도를 우선시하세요.
- 기대 답변 유형이 '추론형' 또는 '예측형'일 경우, 단순 나열보다 논리적 전개와 가능성을 설명하세요.
- 여러 출처의 정보를 통합할 때는 각 출처의 관점과 근거를 명확히 구분하고, 상충되는 정보가 있다면 이를 비교 분석하여 제시하세요.
- 요약에는 불확실한 정보나 추가 확인이 필요한 부분을 명시하세요.
"""

SUMMARY_PROMPT_DEFAULT = """
당신은 금융 시장과 주식 관련 정보를 분석하고 요약하는 전문가입니다.
다음 정보를 분석하여 사용자의 질문에 답변하세요.

사용자 질문: {query}
종목코드: {stock_code}
종목명: {stock_name}
질문 의도: {primary_intent}
질문 복잡도: {complexity}
기대 답변 유형: {expected_answer_type}

{sources_info}

요약 전략:
1. 메시지의 시간 순서를 고려하여 사건의 흐름을 파악하세요.
2. 중복되는 정보는 한 번만 포함하세요.
3. 질문과 관련 없는 정보는 제외하세요.
4. 구체적인 수치나 통계는 정확히 인용하세요.
5. 정보 출처의 신뢰도를 고려하세요.
6. 요약은 명확하고 간결하게 작성하되, 중요한 세부사항은 포함하세요.

질문 유형에 따른 요약 형식:
- 종목기본정보: 핵심 사업영역, 경쟁력, 주요 지표 중심
- 전망: 미래 성장 가능성, 목표가, 투자 의견 중심
- 재무분석: 핵심 재무지표, 동종업계 비교, 재무 건전성 중심
- 산업동향: 시장 트렌드, 해당 종목의 포지셔닝 중심

질문 의도에 따른 구체성:
- 종목기본정보: 100자 내외의 핵심만 요약
- 성과전망: 섹션별로 구분된 상세 설명
- 산업동향: 다양한 관점과 시나리오 제시
- 전문가분석: 전문적인 용어와 심층 분석 제공

요약에는 불확실한 정보나 추가 확인이 필요한 부분을 명시하세요.
"""

def create_prompt(query: str, stock_code: Optional[str], stock_name: Optional[str],
                classification: Dict[str, Any], telegram_data: Dict[str, Any],
                report_data: List[Dict[str, Any]], financial_data: Dict[str, Any],
                industry_data: List[Dict[str, Any]], integrated_knowledge: Optional[Any]) -> ChatPromptTemplate:
        """요약을 위한 프롬프트 생성"""
        
        

        primary_intent = classification.get("primary_intent", "기타")
        complexity = classification.get("complexity", "중간")
        expected_answer_type = classification.get("expected_answer_type", "사실형")
        
        # 소스 정보 형식화
        sources_info = ""
        
        # 텔레그램 메시지
        if telegram_data:
            formatted_msgs = format_telegram_messages(telegram_data)
            sources_info += f"\n출처 - 내부DB :\n{formatted_msgs}\n\n"
        
        # 기업 리포트
        if report_data:
            analysis = report_data.get("analysis", {})
            sources_info += "\n출처 - 기업 리포트:\n"
            if analysis:
                # 전체 소스를 다 줄게 아니라, 기업리포트 에이전트가 출력한 결과만 전달.
                # 아.. 인용처리가 애매해지네.
                # 일단은 기업리포트 결과만 남겨보자.
                sources_info += f" - 투자의견:\n{analysis.get('investment_opinions', '')}\n\n"
                sources_info += f" - 종합의견:\n{analysis.get('opinion_summary', '')}\n\n"
                sources_info += f" - 최종결과:\n{analysis.get('llm_response', '')}\n\n"
            else:
                searched_reports = report_data.get("searched_reports", [])
                for report in searched_reports[:5]:
                    report_info = report.get("content", "")
                    report_source = report.get("source", "미상")
                    report_date = report.get("published_date", "날짜 미상")
                    report_page = f"{report.get('page', '페이지 미상')} p"
                    sources_info += f"[출처: {report_source}, {report_date}, {report_page}]\n{report_info}\n\n"

        # 산업 동향(일단 미구현. 산업리포트 에이전트 추가 후에 풀것)
        if industry_data:
            analysis = industry_data.get("analysis", {})
            sources_info += "\n출처 - 산업 동향:\n"
            if analysis:
                sources_info += f" - 최종결과:\n{analysis.get('llm_response', '')}\n\n"
            else:
                searched_reports = industry_data.get("searched_reports", [])
                for report in searched_reports[:5]:
                    report_info = report.get("content", "")
                    report_source = report.get("source", "미상")
                    report_date = report.get("published_date", "날짜 미상")
                    report_page = f"{report.get('page', '페이지 미상')} p"
                    sources_info += f"[출처: {report_source}, {report_date}, {report_page}]\n{report_info}\n\n"
                # industry_info = item.get("content", "")
                # industry_source = item.get("source", "미상")
                # industry_date = item.get("published_date", "날짜 미상")
                # sources_info += f"[출처: {industry_source}, {industry_date}]\n{industry_info}\n\n"            
        
        # 재무 정보(일단 미구현. 재무분석 에이전트 추가 후에 풀것)
        # if financial_data:
        #     sources_info += "재무 정보:\n"
        #     for key, value in financial_data.items():
        #         sources_info += f"{key}: {value}\n"
        #     sources_info += "\n"
        

        
        # 통합된 지식
        if integrated_knowledge:
            sources_info += f"통합된 지식:\n{integrated_knowledge}\n\n"

        
        # 정보가 없는 경우
        if not sources_info:
            sources_info = "검색된 정보가 없습니다. 질문에 관련된 정보를 찾을 수 없습니다."
        
        # 프롬프트 생성
        return ChatPromptTemplate.from_template(SUMMARY_PROMPT_GEMINI).partial(
            query=query,
            stock_code=stock_code or "정보 없음",
            stock_name=stock_name or "정보 없음",
            primary_intent=primary_intent,
            complexity=complexity,
            expected_answer_type=expected_answer_type,
            sources_info=sources_info
        )
