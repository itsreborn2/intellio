"""
지식 통합기 에이전트 모듈

이 모듈은 여러 검색 에이전트(텔레그램, 기업리포트, 재무제표, 산업 분석)에서 
수집된 정보를 통합하여 응답을 생성하는 통합기 에이전트 클래스를 구현합니다.
"""

import json
from loguru import logger
from typing import Dict, List, Any, Optional

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from pydantic.v1 import BaseModel, Field
from stockeasy.prompts.knowledge_integrator_prompts import format_knowledge_integrator_prompt
from common.core.config import settings

# Pydantic 모델 정의
class CoreInsights(BaseModel):
    주요_인사이트1: Optional[str] = Field(default=None, description="통합된 첫 번째 주요 인사이트")
    주요_인사이트2: Optional[str] = Field(default=None, description="통합된 두 번째 주요 인사이트")
    주요_인사이트3: Optional[str] = Field(default=None, description="통합된 세 번째 주요 인사이트")
    # 추가적인 인사이트가 필요한 경우 동적으로 처리

class ConfidenceAssessment(BaseModel):
    정보_영역1: Optional[str] = Field(default=None, description="첫 번째 정보 영역의 신뢰도 (높음/중간/낮음)")
    정보_영역2: Optional[str] = Field(default=None, description="두 번째 정보 영역의 신뢰도 (높음/중간/낮음)")
    정보_영역3: Optional[str] = Field(default=None, description="세 번째 정보 영역의 신뢰도 (높음/중간/낮음)")
    # 추가적인 영역이 필요한 경우 동적으로 처리

class KnowledgeIntegratorOutput(BaseModel):
    핵심_결론: CoreInsights = Field(description="통합된 핵심 결론과 인사이트")
    신뢰도_평가: ConfidenceAssessment = Field(description="정보 영역별 신뢰도 평가")
    불확실_영역: List[str] = Field(description="부족하거나 불확실한 정보 영역 목록")
    통합_응답: str = Field(description="사용자 질문에 대한 종합적인 답변")

class KnowledgeIntegratorAgent:
    """
    여러 검색 에이전트에서 수집된 정보를 통합하는 지식 통합기 에이전트 클래스
    """
    
    def __init__(self, model_name: str = "gpt-4o", temperature: float = 0):
        """
        지식 통합기 에이전트 초기화
        
        Args:
            model_name: 사용할 OpenAI 모델 이름
            temperature: 모델 출력의 다양성 조절 파라미터
        """
        self.llm = ChatOpenAI(model_name=model_name, temperature=temperature, api_key=settings.OPENAI_API_KEY)
        self.parser = JsonOutputParser(pydantic_object=KnowledgeIntegratorOutput)
        self.chain = self.llm.with_structured_output(KnowledgeIntegratorOutput)
        logger.info(f"KnowledgeIntegratorAgent initialized with model: {model_name}")
        
    async def process(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        여러 검색 에이전트에서 수집된 정보를 통합하고 응답을 생성합니다.
        
        Args:
            state: 현재 상태 정보를 포함하는 딕셔너리
            
        Returns:
            업데이트된 상태 딕셔너리
        """
        try:
            # 현재 사용자 쿼리 및 종목 정보 추출
            query = state.get("query", "")
            stock_code = state.get("stock_code")
            stock_name = state.get("stock_name")
            
            # 각 검색 에이전트 결과 추출
            telegram_results = state.get("telegram_results", "정보 없음")
            report_results = state.get("report_results", "정보 없음")
            financial_results = state.get("financial_results", "정보 없음")
            industry_results = state.get("industry_results", "정보 없음")
            
            # 데이터 중요도 추출 (기본값: 5/10)
            data_importance = state.get("data_importance", {})
            telegram_importance = data_importance.get("telegram_retriever", 5)
            report_importance = data_importance.get("report_analyzer", 5)
            financial_importance = data_importance.get("financial_analyzer", 5)
            industry_importance = data_importance.get("industry_analyzer", 5)
            
            logger.info(f"KnowledgeIntegratorAgent integrating results for query: {query}")
            
            # 프롬프트 준비
            prompt = format_knowledge_integrator_prompt(
                query=query,
                stock_name=stock_name,
                stock_code=stock_code,
                telegram_results=telegram_results,
                report_results=report_results,
                financial_results=financial_results,
                industry_results=industry_results,
                telegram_importance=telegram_importance,
                report_importance=report_importance,
                financial_importance=financial_importance,
                industry_importance=industry_importance
            )
            
            # LLM 호출로 통합 수행
            integration_result = await self.chain.ainvoke(prompt)
            logger.info("Knowledge integration completed successfully")
            
            # 통합된 지식 저장
            state["integrated_knowledge"] = integration_result.dict()
            
            # 주요 인사이트 및 응답 저장
            state["core_insights"] = integration_result.핵심_결론.dict()
            state["confidence_assessment"] = integration_result.신뢰도_평가.dict()
            state["uncertain_areas"] = integration_result.불확실_영역
            state["integrated_response"] = integration_result.통합_응답
            
            # 오류 제거 (성공적으로 처리됨)
            if "error" in state:
                del state["error"]
                
            return state
            
        except Exception as e:
            logger.exception(f"Error in KnowledgeIntegratorAgent: {str(e)}")
            state["error"] = f"지식 통합기 에이전트 오류: {str(e)}"
            state["integrated_response"] = "죄송합니다. 정보를 통합하는 중 오류가 발생했습니다."
            return state 