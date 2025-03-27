"""
재무 데이터 분석을 수행하는 에이전트

재무 데이터를 검색하고 분석하여 관련 종목의 재무 정보를 제공합니다.
"""

import re
import json
import asyncio
from typing import Dict, List, Any, Optional, cast
from datetime import datetime, timedelta
from loguru import logger

from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import JsonOutputParser
from langchain.prompts import PromptTemplate
from langchain_core.messages import AIMessage

from common.core.config import settings
# from stockeasy.services.financial.data_service import FinancialDataService
# from stockeasy.services.stock.stock_info_service import StockInfoService
from stockeasy.prompts.financial_prompts import (
    FINANCIAL_ANALYSIS_PROMPT,
    #FINANCIAL_DATA_EXTRACTION_PROMPT
)
from stockeasy.models.agent_io import RetrievedAllAgentData, FinancialData
from common.services.agent_llm import get_llm_for_agent, get_agent_llm
from common.models.token_usage import ProjectType
from stockeasy.agents.base import BaseAgent
from sqlalchemy.ext.asyncio import AsyncSession

class FinancialAnalyzerAgent(BaseAgent):
    """금융 데이터를 분석하는 에이전트"""

    def __init__(self, name: Optional[str] = None, db: Optional[AsyncSession] = None):
        """
        금융 데이터 분석 에이전트 초기화
        
        Args:
            name: 에이전트 이름 (지정하지 않으면 클래스명 사용)
            db: 데이터베이스 세션 객체 (선택적)
        """
        super().__init__(name, db)
        self.llm, self.model_name, self.provider = get_llm_for_agent("financial_analyzer_agent")
        self.agent_llm = get_agent_llm("financial_analyzer_agent")
        logger.info(f"FinancialAnalyzerAgent initialized with provider: {self.provider}, model: {self.model_name}")
        #self.financial_service = FinancialDataService()
        #self.stock_service = StockInfoService()
        
    async def process(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        재무 데이터 분석을 수행합니다.
        
        Args:
            state: 현재 상태 정보를 포함하는 딕셔너리
            
        Returns:
            업데이트된 상태 딕셔너리
        """
        try:
            # 성능 측정 시작
            start_time = datetime.now()
            logger.info("FinancialAnalyzerAgent starting processing")
            
            # 현재 쿼리 및 세션 정보 추출
            query = state.get("query", "")
            
            # 질문 분석 결과 추출 (새로운 구조)
            question_analysis = state.get("question_analysis", {})
            entities = question_analysis.get("entities", {})
            classification = question_analysis.get("classification", {})
            data_requirements = question_analysis.get("data_requirements", {})
            keywords = question_analysis.get("keywords", [])
            detail_level = question_analysis.get("detail_level", "보통")
            
            # 엔티티에서 종목 정보 추출
            stock_code = entities.get("stock_code", state.get("stock_code"))
            stock_name = entities.get("stock_name", state.get("stock_name"))
            
            if not stock_code and not stock_name:
                logger.warning("No stock information provided to FinancialAnalyzerAgent")
                self._add_error(state, "재무 분석을 위한 종목 정보가 없습니다.")
                return state
                
            logger.info(f"FinancialAnalyzerAgent analyzing stock: {stock_code or stock_name}")
            #logger.info(f"Classification data: {classification}")
            #logger.info(f"Data requirements: {data_requirements}")
            
            # 종목 코드가 없으면 종목명으로 조회
            if not stock_code and stock_name:
                # stock_info = await self.stock_service.get_stock_by_name(stock_name)
                # if stock_info:
                #     stock_code = stock_info.get("code")
                #     logger.info(f"Found stock code {stock_code} for {stock_name}")
                logger.warning("No stock_code information provided to FinancialAnalyzerAgent")
                self._add_error(state, "재무 분석을 위한 종목 코드가 없습니다.")
                return state
                    
            if not stock_code:
                logger.warning(f"Could not find stock code for {stock_name}")
                self._add_error(state, f"종목 코드를 찾을 수 없습니다: {stock_name}")
                return state
                
            # 재무 데이터 조회
            #financial_data = await self.financial_service.get_financial_data(stock_code)
            financial_data = None
            if not financial_data:
                logger.warning(f"No financial data found for stock {stock_code}")
                
                # 실행 시간 계산
                end_time = datetime.now()
                duration = (end_time - start_time).total_seconds()
                
                # 새로운 구조로 상태 업데이트 (결과 없음)
                state["agent_results"] = state.get("agent_results", {})
                state["agent_results"]["financial_analyzer"] = {
                    "agent_name": "financial_analyzer",
                    "status": "partial_success",
                    "data": {},
                    "error": "재무 데이터를 찾을 수 없습니다.",
                    "execution_time": duration,
                    "metadata": {
                        "stock_code": stock_code,
                        "stock_name": stock_name
                    }
                }
                
                # 타입 주석을 사용한 데이터 할당
                if "retrieved_data" not in state:
                    state["retrieved_data"] = {}
                retrieved_data = cast(RetrievedAllAgentData, state["retrieved_data"])
                financial_data_list: List[FinancialData] = []
                retrieved_data["financials"] = financial_data_list
                
                state["processing_status"] = state.get("processing_status", {})
                state["processing_status"]["financial_analyzer"] = "completed_no_data"
                
                # 메트릭 기록
                state["metrics"] = state.get("metrics", {})
                state["metrics"]["financial_analyzer"] = {
                    "start_time": start_time,
                    "end_time": end_time,
                    "duration": duration,
                    "status": "completed_no_data",
                    "error": None,
                    "model_name": self.model_name
                }
                
                logger.info(f"FinancialAnalyzerAgent completed in {duration:.2f} seconds, no data found")
                return state
                
            # 분석이 필요한 재무 데이터 정보 식별 (query와 classification 활용)
            required_metrics = self._identify_required_metrics(classification, query)
            
            # 재무 데이터 분석 수행
            analysis_results = await self._analyze_financial_data(
                financial_data,
                required_metrics,
                query,
                classification,
                detail_level
            )
            
            # 실행 시간 계산
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            # 새로운 구조로 상태 업데이트
            #state["agent_results"] = state.get("agent_results", {})
            state["agent_results"]["financial_analyzer"] = {
                "agent_name": "financial_analyzer",
                "status": "success",
                "data": analysis_results,
                "error": None,
                "execution_time": duration,
                "metadata": {
                    "stock_code": stock_code,
                    "stock_name": stock_name,
                    "required_metrics": required_metrics
                }
            }
            
            # 타입 주석을 사용한 데이터 할당
            if "retrieved_data" not in state:
                state["retrieved_data"] = {}
            retrieved_data = cast(RetrievedAllAgentData, state["retrieved_data"])
            financial_data_result: List[FinancialData] = [analysis_results]
            retrieved_data["financials"] = financial_data_result
            
            state["processing_status"] = state.get("processing_status", {})
            state["processing_status"]["financial_analyzer"] = "completed"
            
            # 메트릭 기록
            state["metrics"] = state.get("metrics", {})
            state["metrics"]["financial_analyzer"] = {
                "start_time": start_time,
                "end_time": end_time,
                "duration": duration,
                "status": "completed",
                "error": None,
                "model_name": self.model_name
            }
            
            logger.info(f"FinancialAnalyzerAgent completed in {duration:.2f} seconds")
            return state
            
        except Exception as e:
            logger.exception(f"Error in FinancialAnalyzerAgent: {str(e)}")
            self._add_error(state, f"재무 데이터 분석 에이전트 오류: {str(e)}")
            
            # 오류 상태 업데이트
            state["agent_results"] = state.get("agent_results", {})
            state["agent_results"]["financial_analyzer"] = {
                "agent_name": "financial_analyzer",
                "status": "failed",
                "data": {},
                "error": str(e),
                "execution_time": 0,
                "metadata": {}
            }
            
            # 타입 주석을 사용한 데이터 할당
            if "retrieved_data" not in state:
                state["retrieved_data"] = {}
            retrieved_data = cast(RetrievedAllAgentData, state["retrieved_data"])
            financial_data_list: List[FinancialData] = []
            retrieved_data["financials"] = financial_data_list
            
            state["processing_status"] = state.get("processing_status", {})
            state["processing_status"]["financial_analyzer"] = "error"
            
            return state
            
    def _add_error(self, state: Dict[str, Any], error_message: str) -> None:
        """
        상태 객체에 오류 정보를 추가합니다.
        
        Args:
            state: 상태 객체
            error_message: 오류 메시지
        """
        state["errors"] = state.get("errors", [])
        state["errors"].append({
            "agent": "financial_analyzer",
            "error": error_message,
            "type": "processing_error",
            "timestamp": datetime.now(),
            "context": {"query": state.get("query", "")}
        })
    
    def _identify_required_metrics(self, classification: Dict[str, Any], query: str) -> List[str]:
        """
        질문 분류 및 쿼리 내용을 기반으로 필요한 재무 지표를 식별합니다.
        
        Args:
            classification: 질문 분류 정보
            query: 사용자 쿼리
            
        Returns:
            필요한 재무 지표 목록
        """
        # 기본 재무 지표 정의
        default_metrics = ["revenue", "operating_profit", "net_profit", "eps", "bps", "per", "pbr"]
        
        # 확장된 지표 정의
        expanded_metrics = default_metrics + ["debt_ratio", "roe", "dividend_yield", "current_ratio"]
        
        # 전체 지표 정의
        all_metrics = expanded_metrics + ["quick_ratio", "capex", "fcf", "ebitda", "debt_to_equity"]
        
        # 분류에 따른 지표 선택
        primary_intent = classification.get("primary_intent", "")
        complexity = classification.get("complexity", "")
        
        if primary_intent == "재무정보":
            if complexity == "단순":
                return default_metrics
            elif complexity == "복합":
                return expanded_metrics
            elif complexity == "전문가급":
                return all_metrics
        
        # 재무 관련 키워드 확인
        financial_keywords = [
            "매출", "revenue", "영업이익", "operating profit", "순이익", "net profit",
            "per", "pbr", "eps", "bps", "부채비율", "자기자본비율", "roe", "배당", "dividend",
            "현금흐름", "cash flow", "fcf", "ebitda", "capex", "자본지출"
        ]
        
        # 쿼리에 재무 관련 키워드가 많을수록 더 많은 지표 포함
        keyword_count = sum(1 for keyword in financial_keywords if keyword.lower() in query.lower())
        
        if keyword_count >= 5:
            return all_metrics
        elif keyword_count >= 2:
            return expanded_metrics
        else:
            return default_metrics
    
    async def _analyze_financial_data(self, 
                                     financial_data: Dict[str, Any],
                                     required_metrics: List[str],
                                     query: str,
                                     classification: Dict[str, Any],
                                     detail_level: str) -> Dict[str, Any]:
        """
        재무 데이터를 분석합니다.
        
        Args:
            financial_data: 분석할 재무 데이터
            required_metrics: 필요한 재무 지표 목록
            query: 사용자 쿼리
            classification: 질문 분류 정보
            detail_level: 분석 세부 수준
            
        Returns:
            분석 결과
        """
        try:
            # 필요한 지표만 추출
            filtered_data = {}
            for metric in required_metrics:
                if metric in financial_data:
                    filtered_data[metric] = financial_data[metric]
            
            # 분석 레벨에 따른 처리
            if detail_level == "간단" or classification.get("complexity", "") == "단순":
                # 간단한 처리: 최신 데이터와 YoY 변화율만 계산
                simplified_data = self._simplify_financial_data(filtered_data)
                return {
                    "extracted_data": simplified_data,
                    "analysis": {
                        "summary": "최근 재무 데이터",
                        "trends": self._calculate_simple_trends(simplified_data)
                    }
                }
            else:
                # 상세 분석: LLM을 사용하여 더 깊은 분석 수행
                analysis = await self._generate_financial_analysis(filtered_data, query, classification)
                return {
                    "extracted_data": filtered_data,
                    "analysis": analysis
                }
        
        except Exception as e:
            logger.error(f"재무 데이터 분석 중 오류 발생: {str(e)}")
            return {
                "extracted_data": financial_data,
                "analysis": {
                    "summary": "재무 데이터 분석 중 오류가 발생했습니다.",
                    "error": str(e)
                }
            }
    
    def _simplify_financial_data(self, financial_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        재무 데이터를 단순화합니다.
        
        Args:
            financial_data: 원본 재무 데이터
            
        Returns:
            단순화된 재무 데이터
        """
        simplified = {}
        
        for metric, data in financial_data.items():
            if isinstance(data, dict) and "quarterly" in data and "yearly" in data:
                # 최근 분기 데이터
                quarterly = data.get("quarterly", [])
                latest_quarterly = quarterly[0] if quarterly else None
                
                # 최근 연간 데이터
                yearly = data.get("yearly", [])
                latest_yearly = yearly[0] if yearly else None
                
                # 단순화된 데이터 저장
                simplified[metric] = {
                    "latest_quarterly": latest_quarterly,
                    "latest_yearly": latest_yearly
                }
            else:
                simplified[metric] = data
                
        return simplified
    
    def _calculate_simple_trends(self, simplified_data: Dict[str, Any]) -> Dict[str, str]:
        """
        단순화된 재무 데이터의 트렌드를 계산합니다.
        
        Args:
            simplified_data: 단순화된 재무 데이터
            
        Returns:
            각 지표별 트렌드 설명
        """
        trends = {}
        
        for metric, data in simplified_data.items():
            if isinstance(data, dict) and "latest_quarterly" in data and "latest_yearly" in data:
                latest_quarterly = data.get("latest_quarterly", {})
                latest_yearly = data.get("latest_yearly", {})
                
                if latest_quarterly and latest_yearly:
                    # 분기 데이터 값과 연간 데이터 값
                    q_value = latest_quarterly.get("value")
                    y_value = latest_yearly.get("value")
                    
                    if q_value is not None and y_value is not None:
                        # 기본 메트릭 설명
                        if metric == "revenue":
                            metric_name = "매출액"
                        elif metric == "operating_profit":
                            metric_name = "영업이익"
                        elif metric == "net_profit":
                            metric_name = "순이익"
                        else:
                            metric_name = metric
                            
                        # 증감율 계산
                        if y_value != 0:
                            change_pct = (q_value - y_value) / y_value * 100
                            direction = "증가" if change_pct > 0 else "감소"
                            trends[metric] = f"{metric_name}은(는) 전년 대비 {abs(change_pct):.1f}% {direction}"
                        else:
                            trends[metric] = f"{metric_name} 데이터 있음"
                    else:
                        trends[metric] = f"{metric} 데이터 불완전"
                else:
                    trends[metric] = f"{metric} 데이터 없음"
            else:
                trends[metric] = f"{metric} 데이터 형식 다름"
                
        return trends
    
    async def _generate_financial_analysis(self, 
                                      financial_data: Dict[str, Any],
                                      query: str,
                                      classification: Dict[str, Any]) -> Dict[str, Any]:
        """
        금융 데이터에 대한 LLM 분석을 수행합니다.
        
        Args:
            financial_data: 분석할 금융 데이터
            query: 사용자 검색어
            classification: 질문 분류 결과
            
        Returns:
            LLM 분석 결과
        """
        try:
            # 재무 데이터 문자열 변환
            financial_data_str = json.dumps(financial_data, ensure_ascii=False, indent=2)
            
            # 프롬프트 구성
            prompt = FINANCIAL_ANALYSIS_PROMPT.format(
                query=query,
                financial_data=financial_data_str,
                primary_intent=classification.get("primary_intent", ""),
                complexity=classification.get("complexity", "중간")
            )
            
            # LLM 호출
            user_context = {}
            user_id = user_context.get("user_id", None)
            
            # 폴백 메커니즘을 사용하여 LLM 호출
            response:AIMessage = await self.agent_llm.ainvoke_with_fallback(
                input=prompt,
                user_id=user_id,
                project_type=ProjectType.STOCKEASY,
                db=self.db
            )
            
            # 분석 결과 추출
            analysis_content = response.content if response else "분석 결과를 생성할 수 없습니다."
            
            return {
                "llm_response": analysis_content,
                "trends": financial_data.get("trends", {}),
                "metrics": financial_data.get("processed_metrics", {})
            }
            
        except Exception as e:
            logger.exception(f"재무 데이터 분석 중 오류: {str(e)}")
            return {
                "llm_response": f"재무 분석 중 오류가 발생했습니다: {str(e)}",
                "trends": {},
                "metrics": {}
            } 