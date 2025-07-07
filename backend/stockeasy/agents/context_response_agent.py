"""
대화 컨텍스트 응답 에이전트 모듈

이 모듈은 이전 대화 컨텍스트를 활용하여 후속 질문에 답변하는 에이전트를 정의합니다.
"""

from datetime import datetime
from typing import Any, Dict

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from common.models.token_usage import ProjectType
from common.services.agent_llm import get_agent_llm
from stockeasy.agents.base import BaseAgent


class ContextResponseAgent(BaseAgent):
    """
    이전 대화 컨텍스트를 활용하여 후속 질문에 답변하는 에이전트

    이 에이전트는 다음을 수행합니다:
    1. 이전 대화 컨텍스트와 현재 질문을 분석
    2. 컨텍스트를 고려한 구체적인 응답 생성
    3. 이전 응답에서 언급된 정보를 활용해 연속적인 대화 유지
    """

    def __init__(self, name: str | None = None, db: AsyncSession | None = None):
        """
        컨텍스트 응답 에이전트 초기화

        Args:
            name: 에이전트 이름 (지정하지 않으면 클래스명 사용)
            db: 데이터베이스 세션 객체 (선택적)
        """
        super().__init__(name, db)
        #self.llm, self.agent_llm.get_model_name(), self.agent_llm.get_provider() = get_llm_for_agent("context_response_agent")
        self.agent_llm = get_agent_llm("context_response_agent")
        logger.info(f"ContextResponseAgent initialized with provider: {self.agent_llm.get_provider()}, model: {self.agent_llm.get_model_name()}")

    async def process(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        대화 컨텍스트를 바탕으로 질문을 분석하고 응답을 생성합니다.

        Args:
            state: 현재 상태 정보를 포함하는 딕셔너리

        Returns:
            업데이트된 상태 딕셔너리
        """
        try:
            # 성능 측정 시작
            start_time = datetime.now()
            logger.info("ContextResponseAgent 처리 시작")

            # 현재 사용자 쿼리 및 분석 결과 추출
            query = state.get("query", "")


            stock_code = state.get("stock_code", "")
            stock_name = state.get("stock_name", "")
            context_analysis = state.get("context_analysis", {})
            conversation_history = state.get("conversation_history", [])
            is_follow_up = state.get("is_follow_up", False)


            if not query:
                logger.warning("빈 쿼리가 ContextResponseAgent에 제공됨")
                self._add_error(state, "질문이 비어 있습니다.")
                return state

            if not context_analysis:
                logger.warning("컨텍스트 분석 결과가 없음")
                self._add_error(state, "컨텍스트 분석 결과가 없습니다.")
                return state

            if not is_follow_up: # state['is_follow_up] 은 프론트에서 후속질문인지 판단해서 전송한값. question_analyzer_agent에서 설정한 값이 아님.
                logger.warning("후속질문이 아님")
                self._add_error(state, "후속질문이 아닙니다.")
                return state

            if not conversation_history or len(conversation_history) < 2:
                logger.warning("대화 기록이 충분하지 않음")
                self._add_error(state, "대화 기록이 충분하지 않습니다.")
                return state

            formatted_agent_results = self._format_agent_results(state)
            logger.info(f"formatted_agent_results: {formatted_agent_results[:500]}")

            # 대화 기록 포맷팅 (최근 5번의 대화만 사용)
            formatted_history = ""
            recent_history = conversation_history[-10:] if len(conversation_history) >= 10 else conversation_history

            for i, msg in enumerate(recent_history):
                role = "사용자" if msg.type == "human" else "AI"
                formatted_history += f"{role}: {msg.content}\n\n"

            # 컨텍스트 응답 프롬프트 구성
#             system_prompt = """
# 당신은 깊이 있는 주식 분석 전문가로서 다양한 데이터 소스를 종합하여 사용자의 후속 질문에 심층적으로 답변하는 역할을 합니다.

# 이전 대화 내용을 기반으로 사용자의 현재 질문에 맥락을 유지하며 통찰력 있는 답변을 제공하세요.
# 주어진 분석 결과물(기업리포트, 텔레그램, 재무/사업보고서, 산업 분석, 비공개 자료, 매출별 특징)을 종합적으로 활용하여
# 사용자가 질문하는 관점에 맞게 깊이 있는 분석과 해석을 제공해야 합니다.

# A. 심층 분석 가이드라인
#  1. 다중 데이터 통합 분석: 여러 분석 결과물을 교차 검증하고 종합하여 일관된 관점을 제시하세요.
#  2. 맥락 유지 및 확장: 이전 대화 내용을 명확히 참조하면서 새로운 통찰력을 추가하세요.
#  3. 연결고리 형성: 대화 맥락 속 숨겨진 질문의 의도를 파악하고, 관련된 정보를 자연스럽게 연결하세요.
#  4. 계층적 정보 제공: 핵심 요약부터 시작해 세부 내용으로 확장하는 구조로 답변하세요.
#  5. 종목 특수성 반영: 해당 종목의 특성, 업종 특성, 시장 환경을 고려한 맞춤형 분석을 제공하세요.
#  6. 비교 분석 접근: 동종 업계, 경쟁사, 과거 실적 등과 비교하여 상대적 위치를 설명하세요.
#  7. 정량-정성 통합: 숫자 데이터와 정성적 평가를 균형 있게 결합하여 종합적 견해를 제시하세요.
#  8. 투자 관점 유지: 모든 분석은 최종적으로 투자 의사결정에 어떤 의미가 있는지 연결하세요.
#  9. 깊이있는 설명: 단순 사실 나열을 넘어 "왜" 그런지, "어떤 의미"가 있는지 분석적 해석을 추가하세요.
#  10. 전문용어 활용과 설명: 전문 용어를 적절히 사용하되, 필요시 쉽게 설명하여 전문성과 접근성을 모두 확보하세요.
#  11. 불확실성 표현: 분석의 한계나 변동 가능성을 명시하고, 확률적 관점에서 설명하세요.
#  12. 질문 재해석: 사용자의 질문을 더 넓은 맥락에서 재해석하여 더 가치 있는 답변을 제공하세요.

# B. 후속질문 대응 전략
#  1. "더 자세히 설명해줘" 유형: 이전 답변에서 언급된 핵심 내용을 더 깊이 분석하고, 관련 데이터나 사례를 추가하세요.
#  2. "이것은 무슨 의미인가요?" 유형: 전문 용어나 개념에 대해 쉽게 풀어서 설명하고, 실제 사례와 연결하세요.
#  3. "그럼 어떻게 해야 하나요?" 유형: 분석 결과가 시사하는 실용적 관점을 제시하되, 단정적인 투자 조언은 피하세요.
#  4. "다른 관점은?" 유형: 긍정적/부정적 요소를 균형 있게 제시하고, 다양한 시나리오를 검토하세요.
#  5. "이전에 언급한..." 유형: 이전 대화에서 언급된 정보를 정확히 참조하고 새로운 맥락에 맞게 재해석하세요.
#  6. "...와 비교하면?" 유형: 요청된 비교 대상과의 공통점/차이점을 체계적으로 분석하세요.
#  7. "미래 전망은?" 유형: 현재 데이터와 트렌드를 기반으로 조건부 전망을 제시하되, 불확실성을 명시하세요.
#  8. "왜 그런가요?" 유형: 현상 뒤의 원인과 메커니즘을 다층적으로 분석하여 설명하세요.

# C. 답변 품질 향상 기법
#  1. 정보 계층화: 핵심 요약 → 주요 포인트 → 세부 분석 → 추가 고려사항 순으로 구성하세요.
#  2. 데이터 인용: 분석의 근거가 되는 구체적 수치나 출처를 명시하세요.
#  3. 맥락화된 해석: 단순 사실을 넘어 해당 정보가 주식/기업에 어떤 의미를 갖는지 해석하세요.
#  4. 균형적 관점: 긍정적 요소와 위험 요소를 균형 있게 제시하세요.
#  5. 정보 간 연결: 별개로 보이는 정보들 사이의 연결고리와 패턴을 발견하여 제시하세요.
#  6. 이해하기 쉬운 비유: 복잡한 개념을 일상적인 비유로 설명하여 이해를 돕되, 전문성을 유지하세요.
#  7. 섹션 구분: 긴 답변의 경우 주제별로 구분하여 가독성을 높이세요.

# 만약 제공된 분석 결과물로 답변할 수 없는 경우:
#  1. 가장 근접한 관련 정보를 활용하여 일반적인 분석을 제공하세요.
#  2. 더 정확한 답변을 위해 어떤 추가 정보가 필요한지 언급하세요.
#  3. 답변에 한계가 있음을 명시하되, 사용자에게 최대한 도움이 되는 정보를 제공하세요.
# """
            system_prompt = """
당신은 주식 분석 전문가로, 다양한 데이터를 빠르게 통합하여 사용자의 후속 질문에 핵심적인 답변을 제공합니다.

사용자 질문의 맥락을 파악하고 제공된 분석 결과물(기업리포트, 텔레그램, 재무보고서, 산업 분석 등)에서 가장 관련성 높은 정보만 선택적으로 활용하세요.

핵심 분석 지침 (우선순위 순):
1. 즉시 답변: 질문의 핵심에 바로 답하고, 가장 중요한 1-2개 인사이트를 먼저 제시하세요.
2. 선택과 집중: 모든 데이터를 분석하려 하지 말고, 질문과 직접 관련된 정보만 활용하세요.
3. 간결한 구조: 답변은 핵심 요약(1-2문장) → 주요 근거(2-3개) → 투자 의미 순으로 구성하세요.
4. 불필요한 배경설명 생략: 사용자가 이미 알고 있는 기본 정보는 반복하지 마세요.
5. 하나의 관점: 여러 시각을 모두 다루려 하지 말고, 가장 설득력 있는 관점을 선택하세요.

후속질문 빠른 대응:
- "더 자세히": 앞서 언급한 핵심 포인트 중 하나만 선택하여 깊이 파고드세요.
- "의미는?": 간결한 한 문장 설명과 실제 예시 하나로 충분합니다.
- "비교": 핵심 차이점 1-2개만 집중적으로.
- "전망": 가장 가능성 높은 시나리오 하나에 집중하세요.

답변 형식:
- 짧은 문단 사용 (2-3문장)
- 긴 나열보다 핵심 포인트 2-3개
- 전문용어 설명은 가장 중요한 것만
- 출처 인용은 간결하게 (날짜, 기관명만)

정보가 부족하면 즉시 "해당 질문에 대한 충분한 정보가 없습니다"라고 명시하고,
대신 관련된 다른 정보를 짧게 제공하세요.
"""
            user_prompt = f"""
오늘 일자: {datetime.now().strftime("%Y-%m-%d")}
종목명: {stock_name}
종목코드: {stock_code}
현재 질문:
{query}

최초 분석내용:
{formatted_agent_results}


위 대화 맥락을 고려하여 현재 질문에 답변해주세요.
"""

            # user_id 추출
            user_context = state.get("user_context", {})
            user_id = user_context.get("user_id", None)


            # LLM 호출로 컨텍스트 기반 응답 생성
            analysis_prompt = ChatPromptTemplate.from_messages([
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ])
            logger.info(f"컨텍스트 기반 응답 생성 시작: {query}")
            response = await self.agent_llm.ainvoke_with_fallback(
                analysis_prompt.format_prompt(),
                user_id=user_id,
                project_type=ProjectType.STOCKEASY,
                db=self.db
            )

            # 응답 추출
            answer = response.content
            logger.info(f"컨텍스트 응답 생성 완료: {len(answer)} 자")

            # 응답을 상태에 저장
            # summary에 저장하면, response에서 이걸 읽는다.

            state["agent_results"]["context_response_agent"] = {
                "answer": answer,
                "based_on_context": True,
                "reference_length": len(conversation_history)
            }

            # answer 필드 업데이트 (최종 응답 제공용)
            #state["answer"] = answer
            state["summary"] = answer

            # 키 설정 확인 로그 추가
            logger.info(f"[ContextResponseAgent] summary 키 설정 완료: {bool(state.get('summary'))}, 길이: {len(state.get('summary', ''))}")
            logger.info(f"[ContextResponseAgent] answer 키 존재: {bool(state.get('answer'))}")

            # 성능 지표 업데이트
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()

            # 메트릭 기록
            state["metrics"] = state.get("metrics", {})
            state["metrics"]["context_response"] = {
                "start_time": start_time,
                "end_time": end_time,
                "duration": duration,
                "status": "completed",
                "error": None,
                "model_name": self.agent_llm.get_model_name()
            }

            # 처리 상태 업데이트
            state["processing_status"] = state.get("processing_status", {})
            state["processing_status"]["context_response"] = "completed"
            state["next"] = "response_formatter"  # 다음 단계로 응답 포맷터 지정

            logger.info(f"ContextResponseAgent 완료: {duration:.2f}초 소요")
            return state

        except Exception as e:
            logger.exception(f"ContextResponseAgent 오류: {str(e)}")
            self._add_error(state, f"컨텍스트 응답 에이전트 오류: {str(e)}")
            # 오류가 발생하더라도 플로우 계속 진행
            state["next"] = "response_formatter"
            return state
    def _format_agent_results(self, state: Dict[str, Any]) -> str:
        """
        에이전트 결과물을 포맷팅하여 문자열로 반환합니다.
        """
        ar = state.get("agent_results", {})
        ## report_analyzer
        report_analyzer = ar.get("report_analyzer", {})
        report_analyzer_data = report_analyzer.get("data", {})
        report_analyzer_analysis = report_analyzer_data.get("analysis", {})
        report_analyzer_llm_response = report_analyzer_analysis.get("llm_response", "")
        report_analyzer_analysis.get("investment_opinions", "")
        report_analyzer_data.get("searched_reports", {})

        ## telegram_retriever
        telegram_analyzer = ar.get("telegram_retriever", {})
        telegram_analyzer_data = telegram_analyzer.get("data", {})
        telegram_analyzer_summary = telegram_analyzer_data.get("summary", {})


        ## financial_analyzer
        # financial_analyzer
        financial_analyzer = ar.get("financial_analyzer", {})
        financial_analyzer_data = financial_analyzer.get("data", {})
        financial_analyzer_llm_response = financial_analyzer_data.get("llm_response", "")
        financial_analyzer_data.get("raw_financial_data", "")

        ## industry_analyzer
        industry_analyzer = ar.get("industry_analyzer", {})
        industry_analyzer_data = industry_analyzer.get("data", {})
        industry_analyzer_analysis = industry_analyzer_data.get("analysis", {})
        industry_analyzer_llm_response = industry_analyzer_analysis.get("llm_response", "")
        industry_analyzer_data.get("searched_reports", {})

        ## confidential_analyzer
        confidential_analyzer = ar.get("confidential_analyzer", {})
        confidential_analyzer_data = confidential_analyzer.get("data", {})
        confidential_analyzer_analysis = confidential_analyzer_data.get("analysis", {})
        confidential_analyzer_llm_response = confidential_analyzer_analysis.get("llm_response", "")
        confidential_analyzer_data.get("searched_reports", {})

        # revenue_breakdown
        revenue_breakdown = ar.get("revenue_breakdown", {})
        revenue_breakdown_result = revenue_breakdown.get("data", {})

        # 결과 문자열 생성
        result_str = f"""
-----------------------------
----- 기업리포트 분석 결과 -----
{report_analyzer_llm_response}


-----------------------------
----- 내부DB 분석 결과 -----
{telegram_analyzer_summary}


-----------------------------
----- 재무,사업보고서 분석 결과 -----
{financial_analyzer_llm_response}


-----------------------------
----- 산업 분석 결과 -----
{industry_analyzer_llm_response}


-----------------------------
----- 비공개 자료 분석 결과 -----
{confidential_analyzer_llm_response}


-----------------------------
----- 매출별 특징 분석 결과 -----
{revenue_breakdown_result}
-----------------------------
        """

        return result_str
        # return result_str.format(
        #     report_analyzer_llm_response=report_analyzer_llm_response,
        #     telegram_analyzer_llm_response=telegram_analyzer_llm_response,
        #     financial_analyzer_llm_response=financial_analyzer_llm_response,
        #     industry_analyzer_llm_response=industry_analyzer_llm_response,
        #     confidential_analyzer_llm_response=confidential_analyzer_llm_response,
        # )

    def _add_error(self, state: Dict[str, Any], error_message: str) -> None:
        """
        상태 객체에 오류 정보를 추가합니다.

        Args:
            state: 상태 객체
            error_message: 오류 메시지
        """
        state["errors"] = state.get("errors", [])
        state["errors"].append({
            "agent": "context_response",
            "error": error_message,
            "type": "processing_error",
            "timestamp": datetime.now(),
            "context": {"query": state.get("query", "")}
        })

        # 처리 상태 업데이트
        state["processing_status"] = state.get("processing_status", {})
        state["processing_status"]["context_response"] = "failed"
