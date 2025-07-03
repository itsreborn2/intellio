"""
기업리포트 검색 및 분석 에이전트 모듈

이 모듈은 사용자 질문에 관련된 기업리포트를 검색하고
분석하는 에이전트 클래스를 구현합니다.
"""

import asyncio
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union
from uuid import UUID

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from common.core.config import settings
from common.models.token_usage import ProjectType
from common.services.agent_llm import get_llm_for_agent
from common.services.embedding_models import EmbeddingModelType
from common.services.retrievers.semantic import SemanticRetriever, SemanticRetrieverConfig
from common.utils.util import async_retry
from stockeasy.agents.base import BaseAgent
from stockeasy.models.agent_io import CompanyReportData
from stockeasy.prompts.report_prompts import format_report_contents


def format_report_contents(reports: List[CompanyReportData]) -> str:
    """
    리포트 내용을 문자열로 형식화합니다.

    Args:
        reports: 형식화할 리포트 목록

    Returns:
        형식화된 리포트 내용 문자열
    """
    # title: str                      # 제목
    # publish_date: datetime          # 발행일
    # author: str                     # 작성자/증권사
    # content: str                    # 내용
    # stock_name: str                 # 종목명
    # stock_code: str                 # 종목코드
    # score: float                    # 유사도 점수
    # analysis: Dict[str, Any]        # 추가 분석 정보
    # page: int                       # 페이지 번호
    # source: str                     # 출처
    # sector_name: str                # 산업명
    formatted = ""
    for i, report in enumerate(reports):
        formatted += f"\n--- 리포트 {i + 1} ---\n"
        # formatted += f"제목: {report.get('title', '제목 없음')}\n"
        formatted += f"출처: {report.get('source', '미상')}\n"
        formatted += f"날짜: {report.get('publish_date', '날짜 정보 없음')}\n"
        formatted += f"내용:\n{report.get('content', '내용 없음')}\n"  # 내용 일부만 포함

    return formatted


class ReportAnalyzerAgent(BaseAgent):
    """기업리포트 검색 및 분석 에이전트"""

    def __init__(self, name: Optional[str] = None, db: Optional[AsyncSession] = None):
        """
        기업리포트 검색 및 분석 에이전트 초기화

        Args:
            name: 에이전트 이름 (지정하지 않으면 클래스명 사용)
            db: 데이터베이스 세션 객체 (선택적)
        """
        super().__init__(name, db)
        self.retrieved_str = "report_data"
        self.llm, self.model_name, self.provider = get_llm_for_agent("report_analyzer_agent")
        logger.info(f"ReportAnalyzerAgent initialized with provider: {self.provider}, model: {self.model_name}")
        # VectorStoreManager 캐시된 인스턴스 사용 (지연 초기화)
        self.vs_manager = None  # 실제 사용 시점에 AgentRegistry에서 가져옴

        # 동시 검색 수 제한 (API Rate Limiting 방지)
        self._search_semaphore = asyncio.Semaphore(8)  # 최대 8개 동시 검색 (메인 + TOC 섹션들)

    async def process(self, state: Dict[str, Any]) -> Dict[str, Any]:
        process_start_time = datetime.now()  # process 전체 시작 시간
        try:
            logger.info(f"ReportAnalyzerAgent starting processing with {self.provider} {self.model_name}")

            # 상태 업데이트 - 콜백 함수 사용
            if "update_processing_status" in state and "agent_name" in state:
                state["update_processing_status"](state["agent_name"], "processing")
            else:
                # 기존 방식으로 상태 업데이트 (콜백 함수가 없는 경우)
                state["processing_status"] = state.get("processing_status", {})
                state["processing_status"]["report_analyzer"] = "processing"

            query = state.get("query", "")
            question_analysis = state.get("question_analysis", {})
            entities = question_analysis.get("entities", {})
            classification = question_analysis.get("classification", {})
            final_report_toc: Optional[dict] = state.get("final_report_toc")

            stock_code = entities.get("stock_code", state.get("stock_code"))
            stock_name = entities.get("stock_name", state.get("stock_name"))

            if not query:
                logger.warning("Empty query provided to ReportAnalyzerAgent")
                self._add_error(state, "검색 쿼리가 제공되지 않았습니다.")
                state["agent_results"] = state.get("agent_results", {})
                state["agent_results"]["report_analyzer"] = {
                    "agent_name": "report_analyzer",
                    "status": "failed",
                    "data": {"reports_with_toc": {}},
                    "error": "검색 쿼리가 제공되지 않았습니다.",
                    "execution_time": 0,
                    "metadata": {"model_name": self.model_name, "provider": self.provider},
                }

                # 상태 업데이트 - 콜백 함수 사용
                if "update_processing_status" in state and "agent_name" in state:
                    state["update_processing_status"](state["agent_name"], "error")
                else:
                    # 기존 방식으로 상태 업데이트 (콜백 함수가 없는 경우)
                    state["processing_status"] = state.get("processing_status", {})
                    state["processing_status"]["report_analyzer"] = "error"

                return state

            logger.info(f"ReportAnalyzerAgent processing query: {query}")
            logger.info(f"Entities: {entities}")

            user_context = state.get("user_context", {})
            user_id = user_context.get("user_id", None)

            search_query = self._make_search_query(query, stock_code, stock_name, classification, state)

            k = self._get_report_count(classification)
            threshold = self._calculate_dynamic_threshold(classification)
            metadata_filter = self._create_metadata_filter(stock_code, stock_name, classification, state)

            search_start_time = datetime.now()
            structured_search_results: Dict[str, Union[List[CompanyReportData], Dict[str, List[CompanyReportData]]]] = await self._search_reports(
                search_query, k, threshold, metadata_filter, user_id=user_id, final_report_toc=final_report_toc
            )
            search_duration = (datetime.now() - search_start_time).total_seconds()
            logger.info(f"기업리포트 검색 시간 (_search_reports): {search_duration:.2f} 초")

            main_query_reports = structured_search_results.get("main_query_results", [])
            toc_reports = structured_search_results.get("toc_results", {})
            processed_reports: List[CompanyReportData] = main_query_reports if isinstance(main_query_reports, list) else []

            if not processed_reports and not structured_search_results.get("toc_results"):
                logger.warning("기업 리포트 검색 결과가 없습니다 (메인 쿼리 및 TOC 모두).")
                total_duration = (datetime.now() - process_start_time).total_seconds()
                state["agent_results"] = state.get("agent_results", {})
                state["agent_results"]["report_analyzer"] = {
                    "agent_name": "report_analyzer",
                    "status": "partial_success_no_data",
                    "data": {"analysis": None, "searched_reports": [], "reports_with_toc": structured_search_results},
                    "error": "검색된 기업 리포트가 없습니다.",
                    "execution_time": total_duration,
                    "metadata": {"report_count": 0, "threshold": threshold, "model_name": self.model_name, "provider": self.provider},
                }
                state["retrieved_data"] = {}
                state["retrieved_data"]["structured_report_data"] = structured_search_results

                # 상태 업데이트 - 콜백 함수 사용
                if "update_processing_status" in state and "agent_name" in state:
                    state["update_processing_status"](state["agent_name"], "completed_no_data")
                else:
                    # 기존 방식으로 상태 업데이트 (콜백 함수가 없는 경우)
                    state["processing_status"] = state.get("processing_status", {})
                    state["processing_status"]["report_analyzer"] = "completed_no_data"

                logger.info(f"ReportAnalyzerAgent completed in {total_duration:.2f} seconds, found 0 reports overall.")
                return state

            total_duration = (datetime.now() - process_start_time).total_seconds()

            state["agent_results"] = state.get("agent_results", {})
            state["agent_results"]["report_analyzer"] = {
                "agent_name": "report_analyzer",
                "status": "success",
                "data": {
                    "analysis": None,
                    "searched_reports": processed_reports,
                    "main_query_reports": main_query_reports,
                    "toc_reports": toc_reports,
                },
                "error": None,
                "execution_time": total_duration,
                "metadata": {
                    "report_count_main": len(processed_reports),
                    "threshold": threshold,
                    "detailed_analysis_skipped": True,
                    "model_name": self.model_name,
                    "provider": self.provider,
                },
            }

            state["retrieved_data"] = {}
            state["retrieved_data"]["structured_report_data"] = structured_search_results

            # 상태 업데이트 - 콜백 함수 사용
            if "update_processing_status" in state and "agent_name" in state:
                state["update_processing_status"](state["agent_name"], "completed_search_only")
            else:
                # 기존 방식으로 상태 업데이트 (콜백 함수가 없는 경우)
                state["processing_status"] = state.get("processing_status", {})
                state["processing_status"]["report_analyzer"] = "completed_search_only"

            logger.info(f"ReportAnalyzerAgent (search_only) completed in {total_duration:.2f} seconds. Main reports: {len(processed_reports)}.")
            return state

        except Exception as e:
            logger.exception(f"Error in ReportAnalyzerAgent: {str(e)}")
            self._add_error(state, f"기업 리포트 검색 에이전트 오류: {str(e)}")

            total_duration = (datetime.now() - process_start_time).total_seconds()
            state["agent_results"] = state.get("agent_results", {})
            state["agent_results"]["report_analyzer"] = {
                "agent_name": "report_analyzer",
                "status": "failed",
                "data": {"analysis": None, "searched_reports": [], "reports_with_toc": {}},
                "error": str(e),
                "execution_time": total_duration if total_duration > 0 else 0,
                "metadata": {"model_name": self.model_name, "provider": self.provider},
            }
            if "retrieved_data" not in state:
                state["retrieved_data"] = {}
            state["retrieved_data"]["structured_report_data"] = {}

            # 상태 업데이트 - 콜백 함수 사용
            if "update_processing_status" in state and "agent_name" in state:
                state["update_processing_status"](state["agent_name"], "error")
            else:
                # 기존 방식으로 상태 업데이트 (콜백 함수가 없는 경우)
                state["processing_status"] = state.get("processing_status", {})
                state["processing_status"]["report_analyzer"] = "error"

            return state

    def _add_error(self, state: Dict[str, Any], error_message: str) -> None:
        """
        상태 객체에 오류 정보를 추가합니다.

        Args:
            state: 상태 객체
            error_message: 오류 메시지
        """
        state["errors"] = state.get("errors", [])
        state["errors"].append(
            {"agent": "report_analyzer", "error": error_message, "type": "processing_error", "timestamp": datetime.now(), "context": {"query": state.get("query", "")}}
        )

    def _make_search_query(self, query: str, stock_code: Optional[str], stock_name: Optional[str], classification: Dict[str, Any], state: Dict[str, Any]) -> str:
        """
        검색 쿼리 생성 - Question Analyzer의 상세 분류 활용

        Args:
            query: 사용자 쿼리
            stock_code: 종목 코드
            stock_name: 종목명
            classification: 분류 결과
            state: 전체 상태 정보

        Returns:
            검색 쿼리
        """
        search_query = query

        # 종목 정보 추가
        if stock_name and stock_name not in query:
            search_query = f"{stock_name} {search_query}"

        # question_analyzer_agent의 분류 정보 기반 검색 키워드 추가
        primary_intent = classification.get("primary_intent", "")

        if primary_intent == "종목기본정보":
            search_query += ", 기본 정보 사업 구조 핵심 지표"
        elif primary_intent == "성과전망":
            # search_query += f", 오늘 {datetime.now().strftime('%Y-%m-%d')} 기준"
            search_query += ", 전망 목표가 예상 성장"
        elif primary_intent == "재무분석":
            search_query += ", 재무제표 실적 매출 영업이익"
        elif primary_intent == "산업동향":
            search_query += ", 산업 동향 시장 구조 경쟁사"

        # 키워드 추가
        qa = state.get("question_analysis", {})
        keywords = qa.get("keywords", [])
        if keywords:
            important_keywords = " ".join(keywords[:3])  # 상위 3개 키워드 사용
            search_query += f" {important_keywords}"

        return search_query

    def _get_report_count(self, classification: Dict[str, Any]) -> int:
        """
        검색할 리포트 수를 결정 - 복잡도 기반

        Args:
            classification: 분류 결과

        Returns:
            검색할 리포트 수
        """
        return 20  # 무조건 20개 고정
        complexity = classification.get("complexity", "중간")

        if complexity == "단순":
            return 6
        elif complexity == "중간":
            return 12
        elif complexity == "복합":
            return 18
        else:  # "전문가급"
            return 25

    def _calculate_dynamic_threshold(self, classification: Dict[str, Any]) -> float:
        """
        동적 유사도 임계값 계산

        Args:
            classification: 분류 결과

        Returns:
            유사도 임계값
        """
        complexity = classification.get("complexity", "중간")

        # 단순한 질문일수록 높은 임계값 (정확한 결과)
        # 복잡한 질문일수록 낮은 임계값 (더 많은 결과)
        if complexity == "단순":
            return 0.3
        elif complexity == "중간":
            return 0.25
        elif complexity == "복합":
            return 0.21
        else:  # "전문가급"
            return 0.20

    def _create_metadata_filter(self, stock_code: Optional[str], stock_name: Optional[str], classification: Dict[str, Any], state: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        메타데이터 필터 생성

        Args:
            stock_code: 종목 코드
            stock_name: 종목명
            classification: 분류 결과
            state: 전체 상태 정보

        Returns:
            메타데이터 필터
        """
        metadata_filter = {}

        # 리포트 타입 필터 (항상 기업리포트로 제한)
        metadata_filter["report_type"] = {"$eq": "기업리포트"}

        # 종목 코드가 있으면 해당 종목으로 제한
        if stock_code:
            metadata_filter["stock_code"] = {"$eq": stock_code}
        # 종목명이 있고 코드가 없으면 종목명으로 제한
        elif stock_name:
            metadata_filter["stock_name"] = {"$eq": stock_name}

        # 산업 분류가 있으면 해당 산업으로 제한 (옵션)
        # state에서 extracted_entities의 sector 정보 사용
        sector_name = None
        if state and "extracted_entities" in state:
            sector_name = state["extracted_entities"].get("sector")

        if sector_name and not stock_code and not stock_name:
            metadata_filter["sector_name"] = {"$eq": sector_name}

        # 시간 범위 처리
        # primary_intent와 시간 관련 키워드에서 정보 유추

        # classification에서 primary_intent 확인
        classification.get("primary_intent", "")

        # state에서 keywords 활용
        time_keywords = []
        if state and "keywords" in state:
            time_keywords = [kw for kw in state["keywords"] if any(t in kw for t in ["년", "분기", "월", "일", "최근"])]

        # 시간 범위가 있으면 해당 기간으로 제한
        if time_keywords and len(time_keywords) > 0:
            time_keywords[0]  # 첫 번째 시간 관련 키워드 사용

        # if time_range:
        #     date_filter = self._parse_time_range(time_range)
        #     if date_filter:
        #         metadata_filter["document_date"] = date_filter

        return metadata_filter

    def _parse_time_range(self, time_range: str) -> Optional[Dict[str, str]]:
        """
        시간 범위 문자열을 파싱하여 날짜 필터 생성

        Args:
            time_range: 시간 범위 문자열

        Returns:
            날짜 필터 딕셔너리 또는 None
        """
        try:
            # 오늘 날짜
            today = datetime.now()

            # "최근 X일" 패턴
            recent_days_match = re.search(r"최근\s*(\d+)\s*일", time_range)
            if recent_days_match:
                days = int(recent_days_match.group(1))
                start_date = today - timedelta(days=days)
                return {"$gte": start_date.strftime("%Y%m%d"), "$lte": today.strftime("%Y%m%d")}

            # "최근 X개월" 패턴
            recent_months_match = re.search(r"최근\s*(\d+)\s*개월", time_range)
            if recent_months_match:
                months = int(recent_months_match.group(1))
                start_date = today.replace(
                    month=today.month - months if today.month > months else today.month + 12 - months, year=today.year if today.month > months else today.year - 1
                )
                return {"$gte": start_date.strftime("%Y%m%d"), "$lte": today.strftime("%Y%m%d")}

            # "YYYY년" 패턴
            year_match = re.search(r"(20\d{2})년", time_range)
            if year_match:
                year = year_match.group(1)
                return {"$gte": f"{year}0101", "$lte": f"{year}1231"}

            # "X분기" 패턴
            quarter_match = re.search(r"(\d)분기", time_range)
            if quarter_match:
                quarter = int(quarter_match.group(1))
                if 1 <= quarter <= 4:
                    year = today.year
                    if quarter == 1:
                        return {"$gte": f"{year}0101", "$lte": f"{year}0331"}
                    elif quarter == 2:
                        return {"$gte": f"{year}0401", "$lte": f"{year}0630"}
                    elif quarter == 3:
                        return {"$gte": f"{year}0701", "$lte": f"{year}0930"}
                    else:  # quarter == 4
                        return {"$gte": f"{year}1001", "$lte": f"{year}1231"}

            return None

        except Exception as e:
            logger.error(f"시간 범위 파싱 중 오류: {e}")
            return None

    @async_retry(retries=1, delay=1.0, exceptions=(Exception,))
    async def _search_reports(
        self, query: str, k: int, threshold: float, metadata_filter: Optional[Dict[str, Any]], user_id: Optional[Union[str, UUID]], final_report_toc: Optional[dict]
    ) -> Dict[str, Union[List[CompanyReportData], Dict[str, List[CompanyReportData]]]]:
        """
        파인콘 DB에서 사용자 쿼리 및 목차별로 기업리포트를 검색하고,
        리랭킹 없이 구조화된 딕셔너리 형태로 반환합니다.
        목차 간 중복 문서는 허용되며, 각 검색 결과 리스트 내에서의 중복만 간단히 처리합니다.
        """

        # VectorStoreManager 캐시된 인스턴스 사용 (지연 초기화)
        if self.vs_manager is None:
            logger.debug("글로벌 캐시에서 VectorStoreManager 가져오기 시작 (ReportAnalyzer)")

            # 글로벌 캐시 함수를 직접 사용
            from stockeasy.graph.agent_registry import get_cached_vector_store_manager

            self.vs_manager = get_cached_vector_store_manager(
                embedding_model_type=EmbeddingModelType.OPENAI_3_LARGE, namespace=settings.PINECONE_NAMESPACE_STOCKEASY, project_name="stockeasy"
            )
            logger.debug("글로벌 캐시에서 VectorStoreManager 가져오기 완료 (ReportAnalyzer)")

        report_data_for_summary_agent: Dict[str, Union[List[CompanyReportData], Dict[str, List[CompanyReportData]]]] = {"main_query_results": [], "toc_results": {}}

        # 기본 필터 설정 (6개월 이내 문서)
        six_months_ago = datetime.now() - timedelta(days=150)
        six_months_ago_str = six_months_ago.strftime("%Y%m%d")
        six_months_ago_int = int(six_months_ago_str)

        current_metadata_filter = metadata_filter.copy() if metadata_filter else {}
        current_metadata_filter["document_date"] = {"$gte": six_months_ago_int}

        logger.info(f"[_search_reports] 사용자쿼리k: {k}, threshold: {threshold}, 필터: {current_metadata_filter}")

        parsed_user_id = None
        if user_id != "test_user":
            parsed_user_id = UUID(user_id) if isinstance(user_id, str) else user_id

        semantic_retriever = SemanticRetriever(
            config=SemanticRetrieverConfig(min_score=threshold, user_id=parsed_user_id, project_type=ProjectType.STOCKEASY), vs_manager=self.vs_manager
        )

        try:
            # TOC 쿼리 사전 준비
            toc_search_queries: Dict[str, str] = {}
            if final_report_toc and isinstance(final_report_toc, dict) and final_report_toc.get("sections"):
                toc_search_queries = self._extract_toc_queries_for_search(final_report_toc)

            # 병렬 검색 태스크 준비
            search_tasks = []
            task_names = []

            # 1. 기본 사용자 쿼리 검색 태스크
            logger.info(f"  기본쿼리 검색 시작: '{query}' (k={k})")
            main_task = semantic_retriever.retrieve(query=query, top_k=k, filters=current_metadata_filter)
            search_tasks.append(main_task)
            task_names.append("main_query")

            # 2. TOC 기반 검색 태스크들 추가 (핵심요약 제외한 모든 목차)
            if toc_search_queries:
                k_toc = 50  # 각 TOC 항목별 검색할 문서 수
                logger.info(f"  TOC 기반 검색 시작. 총 TOC 쿼리 수: {len(toc_search_queries)}, 각 항목당 k_toc: {k_toc}")

                for toc_key, toc_item_query_text in toc_search_queries.items():
                    if not toc_item_query_text:
                        logger.debug(f"    TOC 검색 건너뜀 (쿼리 비어있음): [{toc_key}]")
                        continue

                    logger.debug(f"    TOC 검색 태스크 준비 - [{toc_key}]: '{toc_item_query_text}'")
                    toc_task = semantic_retriever.retrieve(query=toc_item_query_text, top_k=k_toc, filters=current_metadata_filter)
                    search_tasks.append(toc_task)
                    task_names.append(toc_key)

            # 병렬 검색 실행 (Semaphore로 동시 실행 수 제한)
            logger.info(f"  병렬 검색 실행 시작 - 총 {len(search_tasks)}개 태스크 (메인쿼리 + 모든 TOC 섹션, 최대 동시 {self._search_semaphore._value}개)")
            search_start_time = datetime.now()

            # Semaphore를 사용한 제한된 병렬 실행
            async def _limited_search(task, task_name):
                async with self._search_semaphore:
                    # logger.debug(f"    검색 시작: [{task_name}]")
                    try:
                        result = await task
                        # logger.debug(f"    검색 완료: [{task_name}]")
                        return result
                    except Exception as e:
                        logger.warning(f"    검색 실패: [{task_name}] - {str(e)}")
                        return e

            # 제한된 병렬 실행
            limited_tasks = [_limited_search(task, name) for task, name in zip(search_tasks, task_names)]
            search_results = await asyncio.gather(*limited_tasks, return_exceptions=True)

            search_duration = (datetime.now() - search_start_time).total_seconds()
            logger.info(f"  제한된 병렬 검색 실행 완료 - 총 소요시간: {search_duration:.2f}초")

            # 검색 결과 처리
            for i, (result, task_name) in enumerate(zip(search_results, task_names)):
                if isinstance(result, Exception):
                    logger.warning(f"    검색 오류 [{task_name}]: {str(result)}")
                    if task_name == "main_query":
                        report_data_for_summary_agent["main_query_results"] = []
                    else:
                        if "toc_results" not in report_data_for_summary_agent:
                            report_data_for_summary_agent["toc_results"] = {}
                        report_data_for_summary_agent["toc_results"][task_name] = []
                    continue

                # 성공한 결과 처리
                if task_name == "main_query":
                    main_query_reports_raw = [self._convert_doc_to_company_report_data(doc) for doc in result.documents]
                    report_data_for_summary_agent["main_query_results"] = self._deduplicate_company_reports_in_list(main_query_reports_raw)
                    logger.info(f"    기본쿼리 검색 완료: 원본 {len(result.documents)}개 -> 중복제거 후 {len(report_data_for_summary_agent['main_query_results'])}개")
                else:
                    # TOC 검색 결과: 50개 추출 → 점수 정렬 → 상위 10개 선별 → 중복제거
                    if "toc_results" not in report_data_for_summary_agent:
                        report_data_for_summary_agent["toc_results"] = {}
                    toc_item_reports_raw = [self._convert_doc_to_company_report_data(doc) for doc in result.documents]
                    # 점수 기준으로 상위 10개 선별
                    top_10_reports = self._select_top_reports_by_score(toc_item_reports_raw, top_k=10)
                    # 선별된 10개에서 중복 제거
                    report_data_for_summary_agent["toc_results"][task_name] = self._deduplicate_company_reports_in_list(top_10_reports)
                    # logger.debug(
                    #     f"      TOC 검색 결과 [{task_name}]: 원본 {len(result.documents)}개 -> 상위 10개 선별 -> 중복제거 후 {len(report_data_for_summary_agent['toc_results'][task_name])}개"
                    # )

        except Exception as e:
            logger.error(f"[_search_reports] 심각한 오류 발생: {str(e)}", exc_info=True)
        finally:
            # 캐시된 VectorStoreManager를 사용하므로 개별 에이전트에서 close하지 않음
            # if 'semantic_retriever' in locals() and semantic_retriever:
            #     await semantic_retriever.aclose()
            pass

        return report_data_for_summary_agent

    def _calculate_date_weight(self, document_date: Union[str, int, float]) -> float:
        """
        문서 날짜에 따른 가중치 계산

        Args:
            document_date: 문서 날짜 (YYYYMMDD 형식의 문자열, 정수, 또는 실수)

        Returns:
            날짜 기반 가중치 (7일 이내: 0.15, 14일 이내: 0.1, 22일 이내: 0.07, 44일 이내: 0.03)
        """
        try:
            # 현재 날짜
            current_date = datetime.now()

            # document_date 파싱
            if isinstance(document_date, (float, int)):
                document_date = str(document_date).split(".")[0]  # 소수점 이하 제거

            if not document_date or len(str(document_date)) != 8:
                return 0.0  # 날짜 정보가 없거나 형식이 맞지 않으면 가중치 없음

            date_str = str(document_date)
            year = int(date_str[:4])
            month = int(date_str[4:6])
            day = int(date_str[6:8])

            doc_date = datetime(year, month, day)
            days_diff = (current_date - doc_date).days

            # 날짜 차이에 따른 가중치 적용
            if days_diff <= 7:
                weight = 0.15
                # logger.debug(f"날짜 가중치 적용: {document_date} ({days_diff}일 전) -> +{weight}")
                return weight
            elif days_diff <= 14:
                weight = 0.1
                # logger.debug(f"날짜 가중치 적용: {document_date} ({days_diff}일 전) -> +{weight}")
                return weight
            elif days_diff <= 22:
                weight = 0.07
                # logger.debug(f"날짜 가중치 적용: {document_date} ({days_diff}일 전) -> +{weight}")
                return weight
            elif days_diff <= 44:
                weight = 0.03
                # logger.debug(f"날짜 가중치 적용: {document_date} ({days_diff}일 전) -> +{weight}")
                return weight
            else:
                # logger.debug(f"날짜 가중치 미적용: {document_date} ({days_diff}일 전) -> +0.0")
                return 0.0  # 44일 초과는 가중치 없음

        except Exception as e:
            logger.debug(f"날짜 가중치 계산 중 오류: {e}, document_date: {document_date}")
            return 0.0

    def _convert_doc_to_company_report_data(self, doc: Any) -> CompanyReportData:
        content = doc.page_content
        metadata = doc.metadata
        original_score = getattr(doc, "score", metadata.get("_score", 0.0))
        if original_score is None:
            original_score = 0.0

        # 날짜 기반 가중치 적용
        document_date = metadata.get("document_date", "")
        date_weight = self._calculate_date_weight(document_date)
        score = original_score + date_weight

        title = metadata.get("title")
        if not title and content:
            title = content.split("\n")[0][:100]
        elif not title:
            title = "제목 없음"
        return {
            "content": content,
            "score": score,
            "source": metadata.get("provider_code", metadata.get("source", "미상")),
            "publish_date": self._format_date(document_date),
            "file_name": metadata.get("file_name", ""),
            "page": metadata.get("page", 0),
            "stock_code": metadata.get("stock_code", ""),
            "stock_name": metadata.get("stock_name", ""),
            "sector_name": metadata.get("sector_name", ""),
            "title": title,
        }

    def _extract_toc_queries_for_search(self, toc_data: dict) -> Dict[str, str]:
        queries: Dict[str, str] = {}
        if not (isinstance(toc_data, dict) and "sections" in toc_data and isinstance(toc_data["sections"], list)):
            logger.warning("TOC 데이터 구조가 유효하지 않아 검색 쿼리를 추출할 수 없습니다.")
            return queries
        for section_index, section in enumerate(toc_data["sections"]):
            if section_index == 0:
                continue
            if not isinstance(section, dict):
                continue
            section_id = section.get("section_id", f"s{section_index + 1}")
            section_title = section.get("title", "").strip()
            subsections = section.get("subsections")
            if isinstance(subsections, list) and subsections:
                for sub_idx, subsection_item in enumerate(subsections):
                    if isinstance(subsection_item, dict):
                        subsection_id = subsection_item.get("subsection_id", f"{section_id}_{sub_idx + 1}")
                        subsection_title = subsection_item.get("title", "").strip()
                        if subsection_title:
                            unique_key = subsection_id
                            queries[unique_key] = subsection_title
            elif section_title:
                unique_key = section_id  # 제목 부분 제외
                queries[unique_key] = section_title
        logger.info(f"TOC에서 추출된 검색 쿼리 수: {len(queries)}")
        if len(queries) > 0:
            logger.debug(f"  추출된 TOC 쿼리 (일부): {list(queries.items())[:3]}")
        return queries

    def _select_top_reports_by_score(self, reports: List[CompanyReportData], top_k: int = 10) -> List[CompanyReportData]:
        """
        가중치가 적용된 점수 기준으로 상위 k개 리포트 선별

        Args:
            reports: 리포트 목록
            top_k: 선별할 상위 리포트 수

        Returns:
            점수 기준 상위 k개 리포트 목록
        """
        if not reports:
            return []

        # 점수 기준으로 내림차순 정렬
        sorted_reports = sorted(reports, key=lambda x: x.get("score", 0.0), reverse=True)

        # 상위 k개만 반환
        selected_reports = sorted_reports[:top_k]
        logger.debug(f"점수 기준 상위 {top_k}개 선별: 원본 {len(reports)}개 -> 선별 {len(selected_reports)}개")

        return selected_reports

    def _deduplicate_company_reports_in_list(self, reports: List[CompanyReportData]) -> List[CompanyReportData]:
        if not reports:
            return []
        deduped_reports: List[CompanyReportData] = []
        seen_identifiers = set()
        for report in reports:
            content_prefix = report.get("content", "")[:200] if report.get("content") else ""
            identifier = f"{report.get('file_name', '')}_{content_prefix}"
            if identifier not in seen_identifiers:
                seen_identifiers.add(identifier)
                deduped_reports.append(report)
        return deduped_reports

    def _format_date(self, date_str: str) -> str:
        """
        날짜 문자열 형식화

        Args:
            date_str: 날짜 문자열 (예: "20230101") 또는 숫자 (예: 20230101.0)

        Returns:
            형식화된 날짜 문자열 (예: "2023-01-01")
        """
        # float나 int 타입인 경우 문자열로 변환
        if isinstance(date_str, (float, int)):
            date_str = str(date_str).split(".")[0]  # 소수점 이하 제거

        if not date_str or len(date_str) != 8:
            return date_str

        try:
            year = date_str[:4]
            month = date_str[4:6]
            day = date_str[6:8]
            return f"{year}-{month}-{day}"
        except:
            return date_str

    def _process_reports(self, reports: List[CompanyReportData]) -> List[CompanyReportData]:
        """
        검색된 리포트 처리

        Args:
            reports: 검색된 리포트 목록, 벡터 DB 검색 내용.

        Returns:
            처리된 리포트 목록
        """
        processed_reports = []

        for report in reports:
            # 원본 정보 유지
            processed_report = report.copy()

            # 내용 정제 (예: 불필요한 공백 제거, 줄바꿈 정리 등)
            content = report["content"]
            cleaned_content = self._clean_report_content(content)
            processed_report["content"] = cleaned_content

            # 제목 추출
            heading = report.get("heading", "")
            if heading:
                processed_report["title"] = heading
            else:
                processed_report["title"] = self._extract_title_from_content(cleaned_content)

            processed_reports.append(processed_report)

        return processed_reports

    def _clean_report_content(self, content: str) -> str:
        """
        리포트 내용 정제

        Args:
            content: 원본 리포트 내용

        Returns:
            정제된 내용
        """
        # 불필요한 공백 제거
        cleaned = re.sub(r"\s+", " ", content).strip()

        # 표, 서식 등의 특수문자 정리
        cleaned = re.sub(r"[\u2028\u2029\ufeff\xa0]", " ", cleaned)

        return cleaned

    def _extract_title_from_content(self, content: str) -> str:
        """
        내용에서 제목 추출 시도

        Args:
            content: 리포트 내용

        Returns:
            추출된 제목 또는 기본값
        """
        # 첫 줄이나 문장을 제목으로 사용
        lines = content.split("\n")
        if lines and len(lines[0]) < 100:  # 첫 줄이 짧으면 제목으로 간주
            return lines[0]

        # 첫 60자를 제목으로 사용
        return content[:60] + "..." if len(content) > 60 else content

    async def _batch_create_embeddings_for_queries(self, queries: List[str]) -> Dict[str, List[float]]:
        """
        여러 검색 쿼리에 대한 임베딩을 배치로 생성하여 API 호출 최적화

        Args:
            queries: 검색 쿼리 리스트

        Returns:
            쿼리별 임베딩 딕셔너리
        """
        if not queries:
            return {}

        try:
            # 배치로 임베딩 생성
            embeddings = await self.vs_manager.embedding_model_provider.create_embeddings_async(queries)

            # 쿼리-임베딩 매핑 생성
            query_embeddings = {}
            for i, query in enumerate(queries):
                if i < len(embeddings):
                    query_embeddings[query] = embeddings[i]

            logger.info(f"배치 임베딩 생성 완료: {len(queries)}개 쿼리 -> {len(query_embeddings)}개 임베딩")
            return query_embeddings

        except Exception as e:
            logger.error(f"배치 임베딩 생성 실패: {str(e)}")
            # 폴백: 개별 임베딩 생성
            query_embeddings = {}
            for query in queries:
                try:
                    embedding = await self.vs_manager.create_embeddings_single_query_async(query)
                    query_embeddings[query] = embedding
                except Exception as individual_error:
                    logger.error(f"개별 임베딩 생성 실패 [{query}]: {str(individual_error)}")

            return query_embeddings

    async def _search_reports_with_batch_embeddings(
        self, query: str, k: int, threshold: float, metadata_filter: Optional[Dict[str, Any]], user_id: Optional[Union[str, UUID]], final_report_toc: Optional[dict]
    ) -> Dict[str, Union[List[CompanyReportData], Dict[str, List[CompanyReportData]]]]:
        """
        배치 임베딩 기반 최적화된 검색 메서드 (향후 사용 고려)
        """
        # VectorStoreManager 캐시된 인스턴스 사용
        if self.vs_manager is None:
            from stockeasy.graph.agent_registry import get_cached_vector_store_manager

            self.vs_manager = get_cached_vector_store_manager(
                embedding_model_type=EmbeddingModelType.OPENAI_3_LARGE, namespace=settings.PINECONE_NAMESPACE_STOCKEASY, project_name="stockeasy"
            )

        # 모든 검색 쿼리 수집
        all_queries = [query]
        toc_search_queries = {}

        if final_report_toc and isinstance(final_report_toc, dict) and final_report_toc.get("sections"):
            toc_search_queries = self._extract_toc_queries_for_search(final_report_toc)
            all_queries.extend([q for q in toc_search_queries.values() if q])

        # 배치로 임베딩 생성
        logger.info(f"배치 임베딩 생성 시작: {len(all_queries)}개 쿼리")
        await self._batch_create_embeddings_for_queries(all_queries)

        # TODO: 생성된 임베딩으로 직접 Pinecone 검색하는 로직 구현
        # 현재는 기존 메서드 사용
        return await self._search_reports(query, k, threshold, metadata_filter, user_id, final_report_toc)
