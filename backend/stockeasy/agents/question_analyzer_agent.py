"""
질문 분석기 에이전트 모듈

이 모듈은 사용자 질문을 분석하여 종목명, 종목코드, 산업 및 기타 
중요 엔티티와 정보 요구사항을 추출하는 에이전트 클래스를 구현합니다.
"""

import json
from loguru import logger
from typing import Dict, List, Any, Optional

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage
from langchain_core.output_parsers import JsonOutputParser
from backend.stockeasy.prompts.question_analyzer_prompts import format_question_analyzer_prompt

class QuestionAnalyzerAgent:
    """
    사용자 질문에서 중요 정보를 추출하는 질문 분석기 에이전트 클래스
    """
    
    def __init__(self, model_name: str = "gpt-4o", temperature: float = 0):
        """
        질문 분석기 에이전트 초기화
        
        Args:
            model_name: 사용할 OpenAI 모델 이름
            temperature: 모델 출력의 다양성 조절 파라미터
        """
        self.llm = ChatOpenAI(model_name=model_name, temperature=temperature)
        self.output_parser = JsonOutputParser()
        logger.info(f"QuestionAnalyzerAgent initialized with model: {model_name}")
        
    async def process(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        사용자 질문을 분석하여 중요 정보를 추출하고 상태를 업데이트합니다.
        
        Args:
            state: 현재 상태 정보를 포함하는 딕셔너리
            
        Returns:
            업데이트된 상태 딕셔너리
        """
        try:
            # 현재 사용자 쿼리 추출
            query = state.get("current_query", "")
            
            if not query:
                logger.warning("Empty query provided to QuestionAnalyzerAgent")
                state["error"] = "질문이 비어 있습니다."
                return state
            
            logger.info(f"QuestionAnalyzerAgent analyzing query: {query}")
            
            # 프롬프트 준비
            prompt = format_question_analyzer_prompt(query=query)
            
            # LLM 호출로 분석 수행
            response = await self.llm.ainvoke([HumanMessage(content=prompt)])
            content = response.content
            
            # JSON 응답 파싱
            try:
                if "```json" in content:
                    # JSON 코드 블록 추출
                    json_content = content.split("```json")[1].split("```")[0].strip()
                    analysis_result = json.loads(json_content)
                else:
                    # 일반 JSON 파싱 시도
                    analysis_result = json.loads(content)
                    
                logger.info(f"Analysis result: {analysis_result}")
                
                # 엔티티 정보 추출
                entities = analysis_result.get("entities", {})
                classification = analysis_result.get("classification", {})
                data_requirements = analysis_result.get("data_requirements", {})
                
                # 상태 업데이트
                state["extracted_entities"] = entities
                state["question_classification"] = classification
                state["data_requirements"] = data_requirements
                state["keywords"] = analysis_result.get("keywords", [])
                state["detail_level"] = analysis_result.get("detail_level", "보통")
                
                # 중요 엔티티 정보 상태 업데이트
                if not state.get("stock_code") and entities.get("stock_code"):
                    state["stock_code"] = entities.get("stock_code")
                    
                if not state.get("stock_name") and entities.get("stock_name"):
                    state["stock_name"] = entities.get("stock_name")
                    
                state["sector"] = entities.get("sector", state.get("sector"))
                state["time_range"] = entities.get("time_range", state.get("time_range"))
                
                # 필요한 에이전트 결정
                needed_agents = []
                
                if data_requirements.get("telegram_needed", True):
                    needed_agents.append("telegram_retriever")
                    
                if data_requirements.get("reports_needed", False):
                    needed_agents.append("report_analyzer")
                    
                if data_requirements.get("financial_statements_needed", False):
                    needed_agents.append("financial_analyzer")
                    
                if data_requirements.get("industry_data_needed", False):
                    needed_agents.append("industry_analyzer")
                
                # 적어도 하나의 에이전트가 필요함
                if not needed_agents:
                    needed_agents = ["telegram_retriever"]  # 기본값
                
                state["needed_agents"] = needed_agents
                
                logger.info(f"QuestionAnalyzerAgent determined needed agents: {needed_agents}")
                
            except json.JSONDecodeError:
                logger.error(f"Failed to parse analysis result JSON: {content}")
                state["needed_agents"] = ["telegram_retriever"]  # 기본값
                state["error"] = "분석 결과 파싱 실패"
                
            return state
            
        except Exception as e:
            logger.exception(f"Error in QuestionAnalyzerAgent: {str(e)}")
            state["error"] = f"질문 분석기 에이전트 오류: {str(e)}"
            return state 