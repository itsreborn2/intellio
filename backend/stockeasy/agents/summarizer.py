"""
요약 에이전트

이 모듈은 다양한 소스에서 검색된 정보를 통합하여 사용자 질문에 대한 요약된 응답을 생성하는 에이전트를 정의합니다.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
from loguru import logger

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from stockeasy.agents.base import BaseAgent
from stockeasy.models.agent_io import RetrievedTelegramMessage
from stockeasy.prompts.telegram_prompts import format_telegram_messages
from common.core.config import settings
from common.services.agent_llm import get_llm_for_agent

class SummarizerAgent(BaseAgent):
    """검색된 정보를 요약하는 에이전트"""
    
    def __init__(self):
        """에이전트 초기화"""
        super().__init__("summarizer")
        #self.llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.1,api_key=settings.OPENAI_API_KEY )
        self.llm, self.model_name, self.provider = get_llm_for_agent("summarizer_agent")
        logger.info(f"SummarizerAgent initialized with provider: {self.provider}, model: {self.model_name}")
        self.parser = StrOutputParser()
    
    async def process(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        검색된 정보를 요약합니다.
        
        Args:
            state: 현재 상태 (query, classification, retrieved_data 등 포함)
            
        Returns:
            업데이트된 상태 (summary 추가)
        """
        try:
            query = state.get("query", "")
            stock_code = state.get("stock_code")
            stock_name = state.get("stock_name")
            classification = state.get("question_classification", {}).get("classification", {})
            agent_results = state.get("agent_results", {})

            telegram_messages = agent_results.get("telegram_retriever", {}).get("data", [])
            report_data = agent_results.get("report_analyzer", {}).get("data", [])
            financial_data = agent_results.get("financial_analyzer", {}).get("data", {})
            industry_data = agent_results.get("industry_analyzer", {}).get("data", [])
            
            # 통합된 지식이 있으면 사용
            integrated_knowledge = agent_results.get("knowledge_integrator", {}).get("data", {})
            #integrated_knowledge = state.get("integrated_knowledge")
            
            if not query:
                state["errors"] = state.get("errors", []) + [{
                    "agent": self.get_name(),
                    "error": "질문이 제공되지 않았습니다.",
                    "type": "InvalidInputError",
                    "timestamp": datetime.now()
                }]
                state["processing_status"] = state.get("processing_status", {})
                state["processing_status"]["summarizer"] = "error"
                return state
            
            if ( (not telegram_messages or len(telegram_messages) == 0) and 
                (not report_data or len(report_data)) == 0 and 
                not financial_data and not industry_data and 
                not integrated_knowledge):
                state["errors"] = state.get("errors", []) + [{
                    "agent": self.get_name(),
                    "error": "요약할 정보가 없습니다.",
                    "type": "InsufficientDataError",
                    "timestamp": datetime.now()
                }]
                state["processing_status"] = state.get("processing_status", {})
                state["processing_status"]["summarizer"] = "error"
                return state
        except Exception as e:
            logger.exception(f"정보 요약 중 오류 발생: {e}")
            state["errors"] = state.get("errors", []) + [{
                "agent": self.get_name(),
                "error": str(e),
                "type": type(e).__name__,
                "timestamp": datetime.now()
            }]

        try:
            # 요약 프롬프트 생성
            prompt = self._create_prompt(
                query=query, stock_code=stock_code, stock_name=stock_name, classification=classification,
                telegram_messages=telegram_messages, report_data=report_data, financial_data=financial_data, industry_data=industry_data,
                integrated_knowledge=integrated_knowledge
            )
            
            # LLM으로 요약 생성
            chain = prompt | self.llm | self.parser
            summary = await chain.ainvoke({})
            
            # 상태 업데이트
            state["summary"] = summary
            state["processing_status"] = state.get("processing_status", {})
            state["processing_status"]["summarizer"] = "completed"
            
            return state
        except Exception as e:
            logger.exception(f"요약 프롬프트 생성 중 오류 발생: {e}")
            state["errors"] = state.get("errors", []) + [{
                "agent": self.get_name(),
                "error": str(e),
                "type": type(e).__name__,
                "timestamp": datetime.now()
            }]
        
    
    def _create_prompt(self, query: str, stock_code: Optional[str], stock_name: Optional[str],
                      classification: Dict[str, Any], telegram_messages: List[RetrievedTelegramMessage],
                      report_data: List[Dict[str, Any]], financial_data: Dict[str, Any],
                      industry_data: List[Dict[str, Any]], integrated_knowledge: Optional[Any]) -> ChatPromptTemplate:
        """요약을 위한 프롬프트 생성"""
        
        template = """
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

답변 수준에 따른 구체성:
- 간단한답변: 100자 내외의 핵심만 요약
- 긴설명요구: 섹션별로 구분된 상세 설명
- 종합적판단: 다양한 관점과 시나리오 제시
- 전문가분석: 전문적인 용어와 심층 분석 제공

요약에는 불확실한 정보나 추가 확인이 필요한 부분을 명시하세요.
"""
        
        # classification
        # primary_intent: Literal["종목기본정보", "성과전망", "재무분석", "산업동향", "기타"] # 주요 질문 의도
        # complexity: Literal["단순", "중간", "복합", "전문가급"]                      # 질문 복잡도
        # expected_answer_type: Literal["사실형", "추론형", "비교형", "예측형", "설명형"]  # 기대하는 답변 유형

        # 질문 유형 및 답변 수준 매핑
        # question_types = ["종목기본정보", "전망", "재무분석", "산업동향", "기타"]
        # answer_levels = ["간단한답변", "긴설명요구", "종합적판단", "전문가분석"]
        
        # question_type_idx = classification.get("질문주제", 4)
        # answer_level_idx = classification.get("답변수준", 1)
        
        # question_type = question_types[question_type_idx] if 0 <= question_type_idx < len(question_types) else "기타"
        # answer_level = answer_levels[answer_level_idx] if 0 <= answer_level_idx < len(answer_levels) else "긴설명요구"
        primary_intent = classification.get("primary_intent", "기타")
        complexity = classification.get("complexity", "중간")
        expected_answer_type = classification.get("expected_answer_type", "사실형")
        
        # 소스 정보 형식화
        sources_info = ""
        
        # 텔레그램 메시지
        if telegram_messages:
            formatted_msgs = format_telegram_messages(telegram_messages)
            sources_info += f"텔레그램 메시지:\n{formatted_msgs}\n\n"
        
        # 기업 리포트
        if report_data:
            analysis = report_data.get("analysis", {})
            sources_info += "기업 리포트:\n"
            if analysis:
                # 전체 소스를 다 줄게 아니라, 기업리포트 에이전트가 출력한 결과만 전달.
                # 아.. 인용처리가 애매해지네.
                # 일단은 기업리포트 결과만 남겨보자.
                sources_info += f" - 투자의견:\n{analysis.get('investment_opinions', '')}\n\n"
                sources_info += f" - 최종결과:\n{analysis.get('opinion_summary', '')}\n\n"
                sources_info += f" - 최종결과:\n{analysis.get('llm_response', '')}\n\n"
            else:
                searched_reports = report_data.get("searched_reports", [])
                for report in searched_reports[:5]:
                    report_info = report.get("content", "")
                    report_source = report.get("source", "미상")
                    report_date = report.get("published_date", "날짜 미상")
                    report_page = f"report.get('page', '페이지 미상') page"
                    sources_info += f"[출처: {report_source}, {report_date}, {report_page}]\n{report_info}\n\n"

                
            


            
        
        # 재무 정보(일단 미구현. 재무분석 에이전트 추가 후에 풀것)
        # if financial_data:
        #     sources_info += "재무 정보:\n"
        #     for key, value in financial_data.items():
        #         sources_info += f"{key}: {value}\n"
        #     sources_info += "\n"
        
        # 산업 동향(일단 미구현. 산업리포트 에이전트 추가 후에 풀것)
        # if industry_data:
        #     sources_info += "산업 동향:\n"
        #     for item in industry_data:
        #         industry_info = item.get("content", "")
        #         industry_source = item.get("source", "미상")
        #         industry_date = item.get("date", "날짜 미상")
        #         sources_info += f"[출처: {industry_source}, {industry_date}]\n{industry_info}\n\n"
        
        # 통합된 지식
        if integrated_knowledge:
            sources_info += f"통합된 지식:\n{integrated_knowledge}\n\n"

        
        # 정보가 없는 경우
        if not sources_info:
            sources_info = "검색된 정보가 없습니다. 질문에 관련된 정보를 찾을 수 없습니다."
        
        # 프롬프트 생성
        return ChatPromptTemplate.from_template(template).partial(
            query=query,
            stock_code=stock_code or "정보 없음",
            stock_name=stock_name or "정보 없음",
            primary_intent=primary_intent,
            complexity=complexity,
            expected_answer_type=expected_answer_type,
            sources_info=sources_info
        )

