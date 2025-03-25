"""
요약 에이전트

이 모듈은 다양한 소스에서 검색된 정보를 통합하여 사용자 질문에 대한 요약된 응답을 생성하는 에이전트를 정의합니다.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
from loguru import logger


from langchain_core.output_parsers import StrOutputParser

from stockeasy.prompts.summarizer_prompt import create_prompt
from stockeasy.agents.base import BaseAgent

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

            telegram_data = agent_results.get("telegram_retriever", {}).get("data", [])
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
            
            if ( (not telegram_data or len(telegram_data) == 0) and 
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
            prompt = create_prompt(
                query=query, stock_code=stock_code, stock_name=stock_name, classification=classification,
                telegram_data=telegram_data, report_data=report_data, financial_data=financial_data, industry_data=industry_data,
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
        
    
