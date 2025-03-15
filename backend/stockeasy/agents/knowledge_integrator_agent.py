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
from backend.stockeasy.prompts.knowledge_integrator_prompts import format_knowledge_integrator_prompt

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
        self.llm = ChatOpenAI(model_name=model_name, temperature=temperature)
        self.output_parser = JsonOutputParser()
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
            query = state.get("current_query", "")
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
            response = await self.llm.ainvoke([HumanMessage(content=prompt)])
            content = response.content
            
            # JSON 응답 파싱
            try:
                if "```json" in content:
                    # JSON 코드 블록 추출
                    json_content = content.split("```json")[1].split("```")[0].strip()
                    integration_result = json.loads(json_content)
                else:
                    # 일반 JSON 파싱 시도
                    integration_result = json.loads(content)
                    
                logger.info("Knowledge integration completed successfully")
                
                # 통합된 지식 저장
                state["integrated_knowledge"] = integration_result
                
                # 주요 인사이트 및 응답 저장
                state["core_insights"] = integration_result.get("핵심_결론", {})
                state["confidence_assessment"] = integration_result.get("신뢰도_평가", {})
                state["uncertain_areas"] = integration_result.get("불확실_영역", [])
                state["integrated_response"] = integration_result.get("통합_응답", "응답을 생성할 수 없습니다.")
                
                # 오류 제거 (성공적으로 처리됨)
                if "error" in state:
                    del state["error"]
                    
            except json.JSONDecodeError:
                logger.error(f"Failed to parse integration result JSON: {content}")
                state["error"] = "통합 결과 파싱 실패"
                state["integrated_response"] = "죄송합니다. 응답을 생성하는 중 오류가 발생했습니다."
                
            return state
            
        except Exception as e:
            logger.exception(f"Error in KnowledgeIntegratorAgent: {str(e)}")
            state["error"] = f"지식 통합기 에이전트 오류: {str(e)}"
            state["integrated_response"] = "죄송합니다. 정보를 통합하는 중 오류가 발생했습니다."
            return state 