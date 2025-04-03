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
from stockeasy.services.financial.data_service import FinancialDataService
from stockeasy.services.financial.stock_info_service import StockInfoService
from stockeasy.prompts.financial_prompts import (
    FINANCIAL_ANALYSIS_SYSTEM_PROMPT,
    FINANCIAL_ANALYSIS_USER_PROMPT,
    format_financial_data
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
        self.agent_llm = get_agent_llm("financial_analyzer_agent")
        logger.info(f"FinancialAnalyzerAgent initialized with provider: {self.agent_llm.get_provider()}, model: {self.agent_llm.get_model_name()}")
        self.financial_service = FinancialDataService()
        self.stock_service = StockInfoService()
        self.prompt_template = FINANCIAL_ANALYSIS_SYSTEM_PROMPT
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
            
            # 질문 분석 결과 추출
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
            
            # 종목 코드가 없으면 종목명으로 조회
            if not stock_code and stock_name:
                stock_info = await self.stock_service.get_stock_by_name(stock_name)
                if stock_info:
                    stock_code = stock_info.get("code")
                    logger.info(f"Found stock code {stock_code} for {stock_name}")
                    
            if not stock_code:
                logger.warning(f"Could not find stock code for {stock_name}")
                self._add_error(state, f"종목 코드를 찾을 수 없습니다: {stock_name}")
                return state
                
            # 분석 기간 파악
            year_range = self._determine_year_range(query, data_requirements)
            logger.info(f"year_range: {year_range}")
            # 재무 데이터 조회 (GCS에서 PDF 파일을 가져와서 처리)
            financial_data = await self.financial_service.get_financial_data(stock_code, year_range)
            # content를 제외한 메타데이터만 로깅
            log_data = {
                "stock_code": financial_data.get("stock_code"),
                "reports": {
                    key: {
                        "metadata": value.get("metadata", {})
                    }
                    for key, value in financial_data.get("reports", {}).items()
                }
            }
            logger.info(f"financial_data metadata: {log_data}")

            
            if not financial_data or not financial_data.get("reports"):
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
            
            # 필요한 재무 지표 식별
            required_metrics = self._identify_required_metrics(classification, query)
            logger.info(f"required_metrics: {required_metrics}")


            # 추출된 재무 데이터를 LLM에 전달할 형식으로 변환
            formatted_data = await self._prepare_financial_data_for_llm(
                financial_data, 
                query, 
                required_metrics,
                data_requirements
            )
            logger.info(f"formatted_data: {formatted_data}")
            
            # 재무 데이터 분석 수행
            analysis_results = await self._analyze_financial_data(
                formatted_data,
                query,
                stock_code,
                stock_name or "",
                classification
            )
            
            # 실행 시간 계산
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            # 새로운 구조로 상태 업데이트
            # analysis_results
            # {
            #     "llm_response": analysis_content,
            #     "extracted_data": {
            #         "stock_code": stock_code,
            #         "stock_name": stock_name,
            #         "report_count": len(formatted_data),
            #         "years_covered": self._extract_years_covered(formatted_data)
            #     },
            #     "raw_financial_data": formatted_data[:3] if formatted_data else []  # 최대 2개 보고서만 포함
            # }
            state["agent_results"] = state.get("agent_results", {})
            state["agent_results"]["financial_analyzer"] = {
                "agent_name": "financial_analyzer",
                "status": "success",
                "data": analysis_results,
                "error": None,
                "execution_time": duration,
                "metadata": {
                    "stock_code": stock_code,
                    "stock_name": stock_name,
                    "required_metrics": required_metrics,
                    "year_range": year_range
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
                "model_name": self.agent_llm.get_model_name()
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
    
    def _determine_year_range(self, query: str, data_requirements: Dict[str, Any]) -> int:
        """
        질문과 데이터 요구사항을 기반으로 분석할 연도 범위를 결정합니다.
        
        Args:
            query: 사용자 쿼리
            data_requirements: 데이터 요구사항
            
        Returns:
            연도 범위 (몇 년치 데이터를 분석할지)
        """
        # 기본값 설정
        default_range = 2
        
        # 데이터 요구사항에서 시간 범위 확인
        time_range = data_requirements.get("time_range", "")
        if isinstance(time_range, str) and time_range:
            # "최근 X년" 패턴
            recent_years_match = re.search(r'최근\s*(\d+)\s*년', time_range)
            if recent_years_match:
                years = int(recent_years_match.group(1))
                return min(max(years, 1), 5)  # 1~5년 사이로 제한
                
            # "최근 X개월" 패턴 - 1년 이하는 1년으로, 그 이상은 올림하여 연단위로 변환
            recent_months_match = re.search(r'최근\s*(\d+)\s*개월', time_range)
            if recent_months_match:
                months = int(recent_months_match.group(1))
                years = (months + 11) // 12  # 올림 나눗셈
                return min(max(years, 1), 5)
                
            # "YYYY년" 패턴 - 현재 연도와의 차이를 계산
            year_match = re.search(r'(20\d{2})년', time_range)
            if year_match:
                target_year = int(year_match.group(1))
                current_year = datetime.now().year
                return min(max(current_year - target_year + 1, 1), 5)
                
            # "X분기" 패턴 - 분기 데이터는 1년치로 처리
            quarter_match = re.search(r'(\d)분기', time_range)
            if quarter_match:
                return 1
        
        # 쿼리에서 연도 범위 파악
        year_patterns = [
            r"(\d+)년간",
            r"(\d+)년\s*동안",
            r"지난\s*(\d+)년",
            r"최근\s*(\d+)년",
            r"(\d+)년치",
            r"(\d+)년\s*데이터",
            r"(\d+)\s*년",
            r"(\d+)\s*years"
        ]
        
        for pattern in year_patterns:
            match = re.search(pattern, query)
            if match:
                try:
                    year_range = int(match.group(1))
                    return min(max(year_range, 1), 5)  # 1~5년 사이로 제한
                except ValueError:
                    pass
        
        # 특정 키워드에 기반한 범위 결정
        if any(keyword in query or keyword in str(time_range) 
               for keyword in ["장기", "전체", "역대", "모든", "전부"]):
            return 5
        elif any(keyword in query or keyword in str(time_range)
                for keyword in ["중장기", "3년", "삼년"]):
            return 3
        elif any(keyword in query or keyword in str(time_range)
                for keyword in ["단기", "1년", "일년", "올해"]):
            return 1
            
        return default_range
    
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
        default_metrics = ["매출액", "영업이익", "순이익", "EPS", "BPS", "PER", "PBR"]
        
        # 확장된 지표 정의
        expanded_metrics = default_metrics + ["부채비율", "자기자본이익률", "배당수익률", "유동비율"]
        
        # 전체 지표 정의
        all_metrics = expanded_metrics + ["당좌비율", "자본지출", "잉여현금흐름", "EBITDA", "부채자본비율"]
        
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
            
    async def _prepare_financial_data_for_llm(self, 
                                     financial_data: Dict[str, Any],
                                     query: str,
                                     required_metrics: List[str],
                                     data_requirements: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        PDF에서 추출한 재무 데이터를 LLM에 전달할 형식으로 변환합니다.
        
        Args:
            financial_data: PDF에서 추출한 재무 데이터
            query: 사용자 쿼리
            required_metrics: 필요한 재무 지표 목록
            data_requirements: 데이터 요구사항
            
        Returns:
            LLM에 전달할 형식의 재무 데이터 리스트
        """
        reports = financial_data.get("reports", {})
        stock_code = financial_data.get("stock_code", "")
        formatted_data = []
        
        # 보고서 기간 파악
        specific_period = None
        if "period" in data_requirements:
            period_info = data_requirements.get("period", {})
            specific_period = period_info.get("value")
            
        for key, report in reports.items():
            metadata = report.get("metadata", {})
            content = report.get("content", "")
            
            # 특정 기간이 요청된 경우 해당 기간 데이터만 포함
            if specific_period and specific_period not in metadata.get("type", ""):
                continue
                
            # 보고서에서 필요한 지표 식별 (이 부분은 단순화된 구현)
            metrics = {}
            for metric in required_metrics:
                # 컨텐츠에서 지표 키워드 주변 텍스트 추출
                keyword_context = self._extract_keyword_context(content, metric, 300)
                if keyword_context:
                    metrics[metric] = keyword_context
            
            # 보고서 데이터 구조화
            formatted_report = {
                "source": f"{metadata.get('year')}년 {metadata.get('type')} 보고서",
                "date": metadata.get("date", ""),
                "content": content[:3000] if len(content) > 3000 else content,  # 컨텐츠 제한
                "financial_indicators": metrics,
                "metadata": metadata
            }
            
            formatted_data.append(formatted_report)
            
        return formatted_data
        
    def _extract_keyword_context(self, text: str, keyword: str, context_size: int = 200) -> str:
        """
        지정된 키워드 주변의 문맥을 추출합니다.
        
        Args:
            text: 전체 텍스트
            keyword: 찾을 키워드
            context_size: 키워드 주변에서 추출할 문자 수
            
        Returns:
            키워드 주변 문맥
        """
        if not text or not keyword:
            return ""
            
        # 대소문자 구분 없이 검색
        index = text.lower().find(keyword.lower())
        if index == -1:
            return ""
            
        # 문맥 범위 계산
        start = max(0, index - context_size // 2)
        end = min(len(text), index + len(keyword) + context_size // 2)
        
        # 문맥 추출
        context = text[start:end]
        
        # 단어 경계에서 시작하도록 조정
        if start > 0:
            first_space = context.find(" ")
            if first_space > 0:
                context = context[first_space + 1:]
                
        # 단어 경계에서 끝나도록 조정
        if end < len(text):
            last_space = context.rfind(" ")
            if last_space > 0:
                context = context[:last_space]
                
        return context
    
    async def _analyze_financial_data(self, 
                                     formatted_data: List[Dict[str, Any]],
                                     query: str,
                                     stock_code: str,
                                     stock_name: str,
                                     classification: Dict[str, Any]) -> Dict[str, Any]:
        """
        재무 데이터를 분석합니다.
        
        Args:
            formatted_data: 분석할 재무 데이터
            query: 사용자 쿼리
            stock_code: 종목 코드
            stock_name: 종목명
            classification: 질문 분류 정보
            
        Returns:
            분석 결과
        """
        try:
            # 재무 데이터 문자열 변환
            financial_data_str = format_financial_data(formatted_data)
            
            # 메시지 구성
            from langchain_core.messages import SystemMessage, HumanMessage
            
            messages = [
                SystemMessage(content=self.prompt_template),
                HumanMessage(content=FINANCIAL_ANALYSIS_USER_PROMPT.format(
                    query=query,
                    financial_data=financial_data_str,
                    stock_code=stock_code,
                    stock_name=stock_name,
                    classification=classification.get("primary_intent", "")
                ))
            ]
            
            # LLM 호출
            user_context = {}
            user_id = user_context.get("user_id", None)
            
            # 폴백 메커니즘을 사용하여 LLM 호출
            response: AIMessage = await self.agent_llm.ainvoke_with_fallback(
                messages,
                user_id=user_id,
                project_type=ProjectType.STOCKEASY,
                db=self.db
            )
            
            # 분석 결과 추출
            analysis_content = response.content if response else "분석 결과를 생성할 수 없습니다."
            
            return {
                "llm_response": analysis_content,
                "extracted_data": {
                    "stock_code": stock_code,
                    "stock_name": stock_name,
                    "report_count": len(formatted_data),
                    "years_covered": self._extract_years_covered(formatted_data)
                },
                "raw_financial_data": formatted_data[:3] if formatted_data else []  # 최대 2개 보고서만 포함
            }
            
        except Exception as e:
            logger.exception(f"재무 데이터 분석 중 오류: {str(e)}")
            return {
                "llm_response": f"재무 분석 중 오류가 발생했습니다: {str(e)}",
                "extracted_data": {},
                "raw_financial_data": []
            }
            
    def _extract_years_covered(self, formatted_data: List[Dict[str, Any]]) -> List[int]:
        """
        포맷된 데이터에서 포함된 연도 목록을 추출합니다.
        
        Args:
            formatted_data: 포맷된 재무 데이터
            
        Returns:
            포함된 연도 목록
        """
        years = set()
        for report in formatted_data:
            metadata = report.get("metadata", {})
            if "year" in metadata:
                years.add(metadata["year"])
                
        return sorted(list(years), reverse=True)  # 최신 연도부터 내림차순 정렬 