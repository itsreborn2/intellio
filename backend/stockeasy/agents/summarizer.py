"""
요약 에이전트

이 모듈은 다양한 소스에서 검색된 정보를 통합하여 사용자 질문에 대한 요약된 응답을 생성하는 에이전트를 정의합니다.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
from loguru import logger

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from stockeasy.agents.base import BaseAgent
from stockeasy.models.agent_io import AgentState, RetrievedMessage
from stockeasy.prompts.telegram_prompts import format_telegram_messages
from common.core.config import settings


class SummarizerAgent(BaseAgent):
    """검색된 정보를 요약하는 에이전트"""
    
    def __init__(self):
        """에이전트 초기화"""
        super().__init__("summarizer")
        self.llm = ChatOpenAI(
            model=settings.OPENAI_MODEL_NAME,
            temperature=0.1,  # 창의성을 약간 허용
            api_key=settings.OPENAI_API_KEY
        )
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
            classification = state.get("classification", {})
            telegram_messages = state.get("telegram_messages", [])
            report_data = state.get("report_data", [])
            financial_data = state.get("financial_data", {})
            industry_data = state.get("industry_data", [])
            
            # 통합된 지식이 있으면 사용
            integrated_knowledge = state.get("integrated_knowledge")
            
            if not query:
                return {
                    **state,
                    "errors": state.get("errors", []) + [{
                        "agent": self.get_name(),
                        "error": "질문이 제공되지 않았습니다.",
                        "type": "InvalidInputError",
                        "timestamp": datetime.now()
                    }],
                    "processing_status": {
                        **state.get("processing_status", {}),
                        "summarizer": "error"
                    }
                }
            
            if (not telegram_messages and not report_data and 
                not financial_data and not industry_data and 
                not integrated_knowledge):
                return {
                    **state,
                    "errors": state.get("errors", []) + [{
                        "agent": self.get_name(),
                        "error": "요약할 정보가 없습니다.",
                        "type": "InsufficientDataError",
                        "timestamp": datetime.now()
                    }],
                    "processing_status": {
                        **state.get("processing_status", {}),
                        "summarizer": "error"
                    }
                }
            
            # 요약 프롬프트 생성
            prompt = self._create_prompt(
                query, stock_code, stock_name, classification,
                telegram_messages, report_data, financial_data, industry_data,
                integrated_knowledge
            )
            
            # LLM으로 요약 생성
            chain = prompt | self.llm | self.parser
            summary = await chain.ainvoke({})
            
            # 상태 업데이트
            return {
                **state,
                "summary": summary,
                "processing_status": {
                    **state.get("processing_status", {}),
                    "summarizer": "completed"
                }
            }
            
        except Exception as e:
            logger.error(f"정보 요약 중 오류 발생: {e}", exc_info=True)
            return {
                **state,
                "errors": state.get("errors", []) + [{
                    "agent": self.get_name(),
                    "error": str(e),
                    "type": type(e).__name__,
                    "timestamp": datetime.now()
                }],
                "processing_status": {
                    **state.get("processing_status", {}),
                    "summarizer": "error"
                }
            }
    
    def _create_prompt(self, query: str, stock_code: Optional[str], stock_name: Optional[str],
                      classification: Dict[str, Any], telegram_messages: List[RetrievedMessage],
                      report_data: List[Dict[str, Any]], financial_data: Dict[str, Any],
                      industry_data: List[Dict[str, Any]], integrated_knowledge: Optional[Any]) -> ChatPromptTemplate:
        """요약을 위한 프롬프트 생성"""
        
        template = """
당신은 금융 시장과 주식 관련 정보를 분석하고 요약하는 전문가입니다.
다음 정보를 분석하여 사용자의 질문에 답변하세요.

사용자 질문: {query}
종목코드: {stock_code}
종목명: {stock_name}
질문 유형: {question_type}
답변 수준: {answer_level}

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
        
        # 질문 유형 및 답변 수준 매핑
        question_types = ["종목기본정보", "전망", "재무분석", "산업동향", "기타"]
        answer_levels = ["간단한답변", "긴설명요구", "종합적판단", "전문가분석"]
        
        question_type_idx = classification.get("질문주제", 4)
        answer_level_idx = classification.get("답변수준", 1)
        
        question_type = question_types[question_type_idx] if 0 <= question_type_idx < len(question_types) else "기타"
        answer_level = answer_levels[answer_level_idx] if 0 <= answer_level_idx < len(answer_levels) else "긴설명요구"
        
        # 소스 정보 형식화
        sources_info = ""
        
        # 텔레그램 메시지
        if telegram_messages:
            formatted_msgs = format_telegram_messages(telegram_messages)
            sources_info += f"텔레그램 메시지:\n{formatted_msgs}\n\n"
        
        # 기업 리포트
        if report_data:
            sources_info += "기업 리포트:\n"
            for report in report_data:
                report_info = report.get("content", "")
                report_source = report.get("source", "미상")
                report_date = report.get("date", "날짜 미상")
                sources_info += f"[출처: {report_source}, {report_date}]\n{report_info}\n\n"
        
        # 재무 정보
        if financial_data:
            sources_info += "재무 정보:\n"
            for key, value in financial_data.items():
                sources_info += f"{key}: {value}\n"
            sources_info += "\n"
        
        # 산업 동향
        if industry_data:
            sources_info += "산업 동향:\n"
            for item in industry_data:
                industry_info = item.get("content", "")
                industry_source = item.get("source", "미상")
                industry_date = item.get("date", "날짜 미상")
                sources_info += f"[출처: {industry_source}, {industry_date}]\n{industry_info}\n\n"
        
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
            question_type=question_type,
            answer_level=answer_level,
            sources_info=sources_info
        )


class KnowledgeIntegratorAgent(BaseAgent):
    """여러 소스의 검색 결과를 통합하는 에이전트"""
    
    def __init__(self):
        """에이전트 초기화"""
        super().__init__("knowledge_integrator")
    
    async def process(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        검색 결과를 통합합니다.
        
        현재는 단순히 각 소스의 데이터를 통과시키는 역할만 수행합니다.
        향후 구현 시 소스 간의 정보 중복 제거, 충돌 해결 등의 로직을 추가할 수 있습니다.
        
        Args:
            state: 현재 상태
            
        Returns:
            업데이트된 상태
        """
        # 향후 구현: 여러 데이터 소스의 정보를 통합하는 로직
        # 현재는 단순히 상태를 그대로 통과
        
        return {
            **state,
            "processing_status": {
                **state.get("processing_status", {}),
                "knowledge_integrator": "completed"
            }
        } 