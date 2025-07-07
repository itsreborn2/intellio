"""
재무 데이터 분석을 수행하는 에이전트

재무 데이터를 검색하고 분석하여 관련 종목의 재무 정보를 제공합니다.
"""

import json
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, cast

from langchain_core.messages import AIMessage
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from common.models.token_usage import ProjectType
from common.services.agent_llm import get_agent_llm
from stockeasy.agents.base import BaseAgent
from stockeasy.models.agent_io import FinancialData, RetrievedAllAgentData
from stockeasy.prompts.financial_prompts import FINANCIAL_ANALYSIS_SYSTEM_PROMPT, FINANCIAL_ANALYSIS_USER_PROMPT, format_financial_data
from stockeasy.services.financial.data_service_db import FinancialDataServiceDB
from stockeasy.services.financial.data_service_pdf import FinancialDataServicePDF
from stockeasy.services.financial.stock_info_service import StockInfoService


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
        self.agent_llm_lite = get_agent_llm("gemini-lite")
        logger.info(f"FinancialAnalyzerAgent initialized with provider: {self.agent_llm.get_provider()}, model: {self.agent_llm.get_model_name()}")
        self.financial_service_pdf = FinancialDataServicePDF()
        self.financial_service_db = FinancialDataServiceDB(db_session=db)

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

            # 상태 업데이트 - 콜백 함수 사용
            if "update_processing_status" in state and "agent_name" in state:
                state["update_processing_status"](state["agent_name"], "processing")
            else:
                # 기존 방식으로 상태 업데이트 (콜백 함수가 없는 경우)
                state["processing_status"] = state.get("processing_status", {})
                state["processing_status"]["financial_analyzer"] = "processing"

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
            date_range = self._determine_date_range(query, data_requirements)
            logger.info(f"date_range: {date_range}")

            # 재무 데이터 조회 (순차 처리)
            logger.info("[성능개선] PDF 데이터 조회 시작")
            pdf_start_time = datetime.now()

            # PDF 데이터 조회 (시간이 오래 걸림)
            try:
                financial_data = await self.financial_service_pdf.get_financial_data(stock_code, date_range)
            except Exception as e:
                logger.error(f"PDF 데이터 조회 실패: {e}")
                financial_data = {}

            pdf_duration = (datetime.now() - pdf_start_time).total_seconds()
            logger.info(f"[성능개선] PDF 데이터 조회 완료 - 소요시간: {pdf_duration:.2f}초")

            # DB 데이터 조회 (빠름)
            #logger.info("[성능개선] DB 데이터 조회 시작")
            db_start_time = datetime.now()

            try:
                db_search_data = await self.financial_service_db.get_financial_data_with_qoq(stock_code, date_range)
            except Exception as e:
                logger.error(f"DB 데이터 조회 실패: {e}")
                db_search_data = {}

            db_duration = (datetime.now() - db_start_time).total_seconds()
            #logger.info(f"[성능개선] DB 데이터 조회 완료 - 소요시간: {db_duration:.2f}초")

            # content를 제외한 메타데이터만 로깅
            log_data = {
                "stock_code": financial_data.get("stock_code"),
                "date_range": financial_data.get("date_range", {}),
                "reports": {
                    key: {
                        "metadata": value.get("metadata", {})
                    }
                    for key, value in financial_data.get("reports", {}).items()
                }
            }
            #logger.info(f"financial_data metadata: {log_data}")


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
                        "stock_name": stock_name,
                        "date_range": date_range
                    }
                }

                # 타입 주석을 사용한 데이터 할당
                if "retrieved_data" not in state:
                    state["retrieved_data"] = {}
                retrieved_data = cast(RetrievedAllAgentData, state["retrieved_data"])
                financial_data_list: List[FinancialData] = []
                retrieved_data["financials"] = financial_data_list

                # 상태 업데이트 - 콜백 함수 사용
                if "update_processing_status" in state and "agent_name" in state:
                    state["update_processing_status"](state["agent_name"], "completed_no_data")
                else:
                    # 기존 방식으로 상태 업데이트 (콜백 함수가 없는 경우)
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
                    "model_name": self.agent_llm.get_model_name(),
                    "performance_metrics": {
                        "pdf_data_fetch_duration": pdf_duration if 'pdf_duration' in locals() else 0.0,
                        "db_data_fetch_duration": db_duration if 'db_duration' in locals() else 0.0,
                        "total_data_fetch_time": (pdf_duration if 'pdf_duration' in locals() else 0.0) + (db_duration if 'db_duration' in locals() else 0.0)
                    }
                }

                logger.info(f"FinancialAnalyzerAgent completed in {duration:.2f} seconds, no data found")
                return state

            # 필요한 재무 지표 식별
            required_metrics = self._identify_required_metrics(classification, query)
            logger.info(f"[FinancialAnalyzerAgent] required_metrics: {required_metrics}")

            # 추출된 재무 데이터를 LLM에 전달할 형식으로 변환
            formatted_data = await self._prepare_financial_data_for_llm(
                financial_data,
                db_search_data,
                query,
                required_metrics,
                data_requirements
            )
            #logger.info(f"[FinancialAnalyzerAgent] formatted_data: {formatted_data}")

            # 재무 데이터 분석 수행
            analysis_results = await self._analyze_financial_data(
                formatted_data,
                db_search_data,
                query,
                stock_code,
                stock_name or "",
                classification
            )

            # 실행 시간 계산
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()

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
                    "date_range": date_range
                }
            }

            # 타입 주석을 사용한 데이터 할당
            if "retrieved_data" not in state:
                state["retrieved_data"] = {}
            retrieved_data = cast(RetrievedAllAgentData, state["retrieved_data"])
            financial_data_result: List[FinancialData] = [analysis_results]
            retrieved_data["financials"] = financial_data_result

            # 목차 항목에 경쟁사가 있다면, 경쟁사의 이름을 llm에게 조회를 한다.
            final_report_toc = state.get("final_report_toc")
            competitor_infos = await self._get_competitor_info(final_report_toc=final_report_toc,
                                                              stock_name=stock_name,
                                                              stock_code=stock_code, date_range=date_range)
            if competitor_infos:
                state["agent_results"]["financial_analyzer"]["competitor_infos"] = competitor_infos

                # 검색된 데이터가 있으면 retrieved_data에 추가
                if "retrieved_data" in state and "financials" in retrieved_data:
                    for financial in retrieved_data["financials"]:
                        if isinstance(financial, dict):
                            financial["competitor_infos"] = competitor_infos

            # 상태 업데이트 - 콜백 함수 사용
            if "update_processing_status" in state and "agent_name" in state:
                state["update_processing_status"](state["agent_name"], "completed")
            else:
                # 기존 방식으로 상태 업데이트 (콜백 함수가 없는 경우)
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
                "model_name": self.agent_llm.get_model_name(),
                "performance_metrics": {
                    "pdf_data_fetch_duration": pdf_duration,
                    "db_data_fetch_duration": db_duration,
                    "total_data_fetch_time": pdf_duration + db_duration
                }
            }

            logger.info(f"[성능개선] FinancialAnalyzerAgent 완료 - 총 실행시간: {duration:.2f}초")
            logger.info(f"[성능개선] 데이터 조회 시간 요약 - PDF: {pdf_duration:.2f}초, DB: {db_duration:.2f}초")
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
                "metadata": {
                    "stock_code": stock_code,
                    "stock_name": stock_name or "",
                    "date_range": {
                        "start_date": datetime.now().strftime("%Y-%m-%d"),
                        "end_date": datetime.now().strftime("%Y-%m-%d")
                    }
                }
            }

            # 타입 주석을 사용한 데이터 할당
            if "retrieved_data" not in state:
                state["retrieved_data"] = {}
            retrieved_data = cast(RetrievedAllAgentData, state["retrieved_data"])
            financial_data_list: List[FinancialData] = []
            retrieved_data["financials"] = financial_data_list

            # 상태 업데이트 - 콜백 함수 사용
            if "update_processing_status" in state and "agent_name" in state:
                state["update_processing_status"](state["agent_name"], "error")
            else:
                # 기존 방식으로 상태 업데이트 (콜백 함수가 없는 경우)
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

    def _determine_date_range(self, query: str, data_requirements: Dict[str, Any]) -> Dict[str, datetime]:
        """
        질문과 데이터 요구사항을 기반으로 분석할 날짜 범위를 결정합니다.

        Args:
            query: 사용자 쿼리
            data_requirements: 데이터 요구사항

        Returns:
            날짜 범위 (시작일, 종료일)
        """
        # 현재 날짜 기준
        end_date = datetime.now()
        start_date = end_date
        default_years = 2

        # 데이터 요구사항에서 시간 범위 확인
        time_range = data_requirements.get("time_range", "")
        if isinstance(time_range, str) and time_range:
            # "최근 X년" 패턴
            recent_years_match = re.search(r'최근\s*(\d+)\s*년', time_range)
            if recent_years_match:
                years = int(recent_years_match.group(1))
                years = min(max(years, 1), 5)  # 1~5년 사이로 제한
                start_date = end_date - timedelta(days=years*365)
                return {"start_date": start_date, "end_date": end_date}

            # "최근 X개월" 패턴
            recent_months_match = re.search(r'최근\s*(\d+)\s*개월', time_range)
            if recent_months_match:
                months = int(recent_months_match.group(1))
                start_date = end_date - timedelta(days=months*30)
                return {"start_date": start_date, "end_date": end_date}

            # "YYYY년" 패턴 - 현재 연도와의 차이를 계산
            year_match = re.search(r'(20\d{2})년', time_range)
            if year_match:
                target_year = int(year_match.group(1))
                start_date = datetime(target_year, 1, 1)
                end_date = datetime(target_year, 12, 31)
                return {"start_date": start_date, "end_date": end_date}

            # "YY년" 패턴 (2자리 연도) - 20을 앞에 붙여서 4자리 연도로 변환
            short_year_match = re.search(r'(\d{2})년', time_range)
            if short_year_match:
                year_suffix = int(short_year_match.group(1))
                # 2000년대로 가정
                target_year = 2000 + year_suffix
                # 미래 연도인 경우 현재 연도 이하로 조정
                current_year = datetime.now().year
                if target_year > current_year:
                    target_year = current_year

                start_date = datetime(target_year, 1, 1)
                end_date = datetime(target_year, 12, 31)
                return {"start_date": start_date, "end_date": end_date}

            # "X분기" 패턴 - 분기 데이터만 처리
            quarter_match = re.search(r'(\d)분기', time_range)
            if quarter_match:
                quarter = int(quarter_match.group(1))
                current_year = end_date.year

                # 분기 시작/종료일 계산
                if quarter == 1:
                    start_date = datetime(current_year, 4, 1)
                    end_date = datetime(current_year, 5, 16)
                elif quarter == 2:
                    start_date = datetime(current_year, 7, 1)
                    end_date = datetime(current_year, 8, 16)
                elif quarter == 3: # 3분기
                    start_date = datetime(current_year, 10, 1)
                    end_date = datetime(current_year, 11, 16)
                elif quarter == 4: # 4분기는 1~3월에 마감. 연간 사업보고서에는 4분기 실적이 따로 없으므로, 연간보고서 - 3분기실적 으로 처리.
                    start_date = datetime(current_year, 10, 1)
                    end_date = datetime(current_year+1, 3, 31)

                return {"start_date": start_date, "end_date": end_date}

        # 쿼리에서 연도 범위 파악

        # 1. 특정 연도 매칭 패턴 (예: 2023년, 23년)
        year_specific_patterns = [
            r"(20\d{2})년",  # 4자리 연도 (YYYY년)
            r"(\d{2})년"     # 2자리 연도 (YY년)
        ]

        for pattern in year_specific_patterns:
            match = re.search(pattern, query)
            if match:
                try:
                    group = match.group(1)
                    # 연도 처리
                    if len(group) == 4 and group.startswith('20'):
                        target_year = int(group)
                    else:  # 2자리 연도
                        year_suffix = int(group)
                        target_year = 2000 + year_suffix

                    # 미래 연도인 경우 현재 연도 이하로 조정
                    current_year = datetime.now().year
                    if target_year > current_year:
                        target_year = current_year

                    start_date = datetime(target_year, 1, 1)
                    end_date = datetime(target_year, 12, 31)
                    return {"start_date": start_date, "end_date": end_date}
                except ValueError:
                    pass

        # 2. 기간 매칭 패턴 (예: 3년간, 5년 동안)
        period_patterns = [
            r"(\d+)년간",
            r"(\d+)년\s*동안",
            r"지난\s*(\d+)년",
            r"최근\s*(\d+)년",
            r"(\d+)년치",
            r"(\d+)년\s*데이터",
            r"(\d+)\s*년",
            r"(\d+)\s*years"
        ]

        for pattern in period_patterns:
            match = re.search(pattern, query)
            if match:
                try:
                    year_range = int(match.group(1))
                    year_range = min(max(year_range, 1), 5)  # 1~5년 사이로 제한
                    start_date = end_date - timedelta(days=year_range*365)
                    return {"start_date": start_date, "end_date": end_date}
                except ValueError:
                    pass

        # 특정 키워드에 기반한 범위 결정
        if any(keyword in query or keyword in str(time_range)
               for keyword in ["장기", "전체", "역대", "모든", "전부"]):
            start_date = end_date - timedelta(days=5*365)  # 5년
        elif any(keyword in query or keyword in str(time_range)
                for keyword in ["중장기", "3년", "삼년"]):
            start_date = end_date - timedelta(days=3*365)  # 3년
        elif any(keyword in query or keyword in str(time_range)
                for keyword in ["단기", "1년", "일년", "올해"]):
            start_date = end_date - timedelta(days=1*365)  # 1년
        else:
            # 기본값: 2년
            start_date = end_date - timedelta(days=default_years*365)

        return {"start_date": start_date, "end_date": end_date}

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
                                     db_search_data: Dict[str, Any],
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
# """
# db_search_data 형식
# {  'stock_code': '000660',
# 	'period': {'end_date': '2025-04-25', 'start_date': '2023-12-01'},
#    'quarters': {  202312: {  'net_income': {  'cumulative_value': -9137547.0,
#                                               'display_unit': '백만원',
#                                               'period_value': -1379450.0},
#                              'operating_income': {  'cumulative_value': -7730313.0,
#                                                     'display_unit': '백만원',
#                                                     'period_value': 346034.0},
#                              'revenue': {  'cumulative_value': 32765719.0,
#                                            'display_unit': '백만원',
#                                            'period_value': 11305505.0}},
#                   202403: {  'net_income': {  'cumulative_value': 1917039.0,
#                                               'display_unit': '백만원',
#                                               'period_value': 1917039.0},
#                              'operating_income': {  'cumulative_value': 2886029.0,
#                                                     'display_unit': '백만원',
#                                                     'period_value': 2886029.0},
#                              'revenue': {  'cumulative_value': 12429598.0,
#                                            'display_unit': '백만원',
#                                            'period_value': 12429598.0}},

# """
        reports = financial_data.get("reports", {})
        stock_code = financial_data.get("stock_code", "")
        formatted_data = []
        # 보고서 기간 파악
        # # data_requirements 는 각종 에이전트를 사용하냐 마냐하는 필드임.
        specific_period = None
        if data_requirements and "period" in data_requirements:
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
            #print(f"[FIN_FORMAT] 보고서 데이터 구조화: {metadata}")
            year = int(metadata.get("year", ""))
            report_type = metadata.get('type')
            # if( report_type.lower() == "annual" ):
            #     year = year - 1

            formatted_report = {
                "source": f"{year}년 {report_type} 보고서",
                "date": metadata.get("date", ""),
                "content": content[:5000] if len(content) > 5000 else content,  # 컨텐츠 제한
                "financial_indicators": metrics,
                "metadata": metadata
            }

            formatted_data.append(formatted_report)

        # 데이터 타입 검사 및 로깅
        if not formatted_data:
            logger.warning(f"formatted_data가 비어 있습니다. stock_code: {stock_code}")
            print(f"[재무 분석] 포맷된 데이터가 비어 있습니다: {stock_code}")
            return []

        # 데이터 타입 검사
        for idx, item in enumerate(formatted_data):
            if not isinstance(item, dict):
                logger.error(f"포맷된 데이터 오류: 항목 {idx}이(가) 딕셔너리가 아닙니다. 타입: {type(item)}")
                print(f"[재무 분석] 데이터 형식 오류 - 항목 {idx}의 타입: {type(item)}")
                # 오류 항목 제거
                formatted_data = [item for item in formatted_data if isinstance(item, dict)]
                break

        print(f"[재무 분석] 처리된 보고서 수: {len(formatted_data)}")
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
                                     db_search_data: Dict[str, Any],
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
            # 타입 검사
            if not isinstance(formatted_data, list):
                logger.error(f"타입 오류: formatted_data가 리스트가 아닙니다. 타입: {type(formatted_data)}")
                print(f"[재무 분석] 치명적 오류: formatted_data 타입이 리스트가 아닙니다: {type(formatted_data)}")
                formatted_data = []
            else:
                # 리스트 내부 항목 검사
                invalid_items = [i for i, item in enumerate(formatted_data) if not isinstance(item, dict)]
                if invalid_items:
                    logger.error(f"타입 오류: formatted_data의 일부 항목이 딕셔너리가 아닙니다. 인덱스: {invalid_items}")
                    print(f"[재무 분석] 잘못된 데이터 항목 발견: {invalid_items}")
                    # 잘못된 항목 필터링
                    formatted_data = [item for item in formatted_data if isinstance(item, dict)]

            # 재무 데이터 문자열 변환
            financial_data_str = format_financial_data(formatted_data)

            # 메시지 구성
            from langchain_core.messages import HumanMessage, SystemMessage

            messages = [
                SystemMessage(content=self.prompt_template),
                HumanMessage(content=FINANCIAL_ANALYSIS_USER_PROMPT.format(
                    today=datetime.now().strftime("%Y-%m-%d"),
                    query=query,
                    financial_data=financial_data_str,
                    db_search_data=json.dumps(db_search_data, ensure_ascii=False, indent=2),
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
                    "date_range": self._extract_date_range(formatted_data)
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

    def _extract_date_range(self, formatted_data: List[Dict[str, Any]]) -> Dict[str, str]:
        """
        포맷된 데이터에서 실제 포함된 날짜 범위를 추출합니다.

        Args:
            formatted_data: 포맷된 재무 데이터

        Returns:
            포함된 날짜 범위 (시작일, 종료일)
        """
        dates = []
        years = set()

        for report in formatted_data:
            metadata = report.get("metadata", {})

            # 날짜 정보 확인
            date_str = metadata.get("date", "")
            if date_str:
                try:
                    date = datetime.fromisoformat(date_str)
                    dates.append(date)
                except ValueError:
                    pass

            # 연도 정보 확인 (날짜 정보가 없는 경우 대비)
            if "year" in metadata:
                years.add(metadata["year"])

        # 날짜 정보가 있는 경우 해당 날짜 범위 사용
        if dates:
            min_date = min(dates)
            max_date = max(dates)
            return {
                "start_date": min_date.strftime("%Y-%m-%d"),
                "end_date": max_date.strftime("%Y-%m-%d"),
                "included_years": sorted(list(years), reverse=True)
            }

        # 날짜 정보가 없는 경우 연도 정보만 사용
        if years:
            min_year = min(years)
            max_year = max(years)
            return {
                "start_date": f"{min_year}-01-01",
                "end_date": f"{max_year}-12-31",
                "included_years": sorted(list(years), reverse=True)
            }

        # 아무 정보도 없는 경우 기본값 반환
        return {
            "start_date": "",
            "end_date": "",
            "included_years": []
        }

    async def _get_competitor_info(self, final_report_toc: Dict[str, Any], stock_name:str, stock_code: str, date_range: Dict[str, datetime]) -> List[Dict[str, Any]]:
        """
        경쟁사 정보를 조회하고 반환합니다.

        Args:
            final_report_toc: 목차
            stock_name: 종목명
            stock_code: 종목 코드
            date_range: 분석할 날짜 범위

        Returns:
            경쟁사 정보 리스트 (없으면 빈 리스트)
        """
        try:
            # final_report_toc가 없거나 sections가 없으면 빈 리스트 반환
            if not final_report_toc or "sections" not in final_report_toc:
                logger.info("목차 정보가 없습니다.")
                return []

            # 경쟁사 관련 키워드 정의
            competitor_keywords = ["경쟁사", "경쟁업체", "경쟁기업", "라이벌", "경쟁자", "업계 경쟁", "경쟁 업체"]
            competitor_sections = []

            # 모든 섹션과 하위 섹션에서 경쟁사 관련 키워드 검색
            sections = final_report_toc.get("sections", [])
            for section in sections:
                section_title = section.get("title", "")
                section_desc = section.get("description", "")

                # 섹션 제목이나 설명에 경쟁사 키워드가 있는지 확인
                if any(keyword in section_title or keyword in section_desc for keyword in competitor_keywords):
                    competitor_sections.append({
                        "title": section_title,
                        "description": section_desc
                    })

                # 하위 섹션 검사
                subsections = section.get("subsections", [])
                for subsection in subsections:
                    subsection_title = subsection.get("title", "")
                    subsection_desc = subsection.get("description", "")

                    # 하위 섹션 제목이나 설명에 경쟁사 키워드가 있는지 확인
                    if any(keyword in subsection_title or keyword in subsection_desc for keyword in competitor_keywords):
                        competitor_sections.append({
                            "title": subsection_title,
                            "description": subsection_desc
                        })

            # 경쟁사 관련 섹션이 없으면 빈 리스트 반환
            if not competitor_sections:
                logger.info("경쟁사 관련 섹션이 목차에 없습니다.")
                return []

            # 경쟁사 섹션 정보를 텍스트로 변환하여 LLM에 전달
            competitor_text = "\n\n".join([
                f"섹션: {section['title']}\n설명: {section['description']}"
                for section in competitor_sections
            ])

            # LLM을 사용하여 경쟁사 이름 추출
            competitors = await self._extract_competitors_from_toc(stock_name, stock_code, competitor_text)
            logger.info(f"목차에 경쟁사 키워드. LLM 경쟁사 정보 수신 : {competitors}")

            if not competitors:
                logger.info("목차에서 경쟁사를 추출할 수 없습니다.")
                return []

            # 모든 경쟁사 정보를 담을 리스트
            competitors_info_list = []

            # 각 경쟁사에 대한 정보 조회
            for competitor in competitors:
                competitor_name = competitor
                # 경쟁사 종목 코드 찾기
                competitor_info = await self.stock_service.get_stock_by_name(competitor_name)

                if not competitor_info or not competitor_info.get("code"):
                    logger.warning(f"경쟁사 종목 코드를 찾을 수 없습니다: {competitor_name}")
                    continue

                competitor_code = competitor_info.get("code")
                logger.info(f"경쟁사 종목 코드: {competitor_code}")

                # 경쟁사의 재무 데이터 조회
                competitor_db_search_data = await self.financial_service_db.get_financial_data_with_qoq(competitor_code, date_range)

                if not competitor_db_search_data:
                    logger.warning(f"경쟁사 재무 데이터를 찾을 수 없습니다: {competitor_name} ({competitor_code})")
                    continue

                # 결과 추가
                competitors_info_list.append({
                    "stock_code": competitor_code,
                    "stock_name": competitor_name,
                    "db_search_data": competitor_db_search_data
                })

                # 최대 3개까지만 조회
                if len(competitors_info_list) >= 3:
                    break

            logger.info(f"조회된 경쟁사 수: {len(competitors_info_list)}")
            return competitors_info_list

        except Exception as e:
            logger.exception(f"경쟁사 정보 조회 중 오류 발생: {str(e)}")
            return []

    async def _extract_competitors_from_toc(self, stock_name: str, stock_code: str, competitor_text: str) -> List[str]:
        """
        목차 정보에서 경쟁사 이름을 추출합니다.

        Args:
            stock_name: 종목명
            stock_code: 종목 코드
            competitor_text: 경쟁사 관련 섹션 텍스트

        Returns:
            경쟁사 이름 리스트
        """
        try:
            # 프롬프트 구성
            prompt_template = """
            한국 주식 시장에서 {stock_name}({stock_code})의 주요 경쟁사를 알려주세요.

            반드시 JSON 형식으로 리스트 형태로 결과를 반환해주세요. 정확한 회사명만 추출하세요.
            만약 경쟁사 회사명이 명확하게 파악되지 않는다면, 해당 산업의 주요 경쟁사를 3개만 추론하여 반환해주세요.

            예시 형식:
            ["삼성전자", "SK하이닉스"]
            """

            # 메시지 구성
            from langchain_core.messages import HumanMessage, SystemMessage

            messages = [
                SystemMessage(content="당신은 한국 주식 시장의 기업 정보와 산업 구조에 대해 잘 알고 있는 AI 도우미입니다. JSON 형식으로 정확하게 응답해주세요."),
                HumanMessage(content=prompt_template.format(
                    stock_name=stock_name,
                    stock_code=stock_code
                ))
            ]

            # LLM 호출
            response = await self.agent_llm_lite.ainvoke_with_fallback(
                messages,
                project_type=ProjectType.STOCKEASY,
                db=self.db
            )

            # 결과 추출
            response_text = response.content if response else ""

            # JSON 형식 찾기
            json_pattern = r'\[.*?\]'
            json_match = re.search(json_pattern, response_text, re.DOTALL)

            if json_match:
                json_str = json_match.group(0)
                try:
                    competitors = json.loads(json_str)
                    if isinstance(competitors, list) and competitors:
                        return competitors
                except json.JSONDecodeError:
                    logger.error(f"경쟁사 목록 JSON 파싱 실패: {json_str}")

            # JSON 파싱 실패 시 텍스트 기반 추출 시도
            lines = response_text.split('\n')
            for line in lines:
                if '["' in line and '"]' in line:
                    try:
                        competitors = json.loads(line.strip())
                        if isinstance(competitors, list) and competitors:
                            return competitors
                    except json.JSONDecodeError:
                        continue

            # 텍스트에서 회사명 패턴 추출 시도
            company_pattern = r'([가-힣a-zA-Z0-9]+(?:[가-힣a-zA-Z0-9\s]+)?(?:주식회사|전자|반도체|그룹|회사|컴퍼니|주식|Corp|Inc|Co\.|Ltd\.)?)'
            companies = []

            # 응답에서 회사명 추출
            matches = re.findall(company_pattern, response_text)
            for match in matches:
                if len(match) > 1 and match not in ["경쟁사", "경쟁업체", "경쟁기업", "라이벌"]:
                    companies.append(match.strip())

            # 중복 제거 및 반환
            return list(set(companies))

        except Exception as e:
            logger.exception(f"경쟁사 추출 중 오류 발생: {str(e)}")
            return []
