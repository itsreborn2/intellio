"""
기업리포트 검색 및 분석 에이전트 모듈

이 모듈은 사용자 질문에 관련된 기업리포트를 검색하고 
분석하는 에이전트 클래스를 구현합니다.
"""

import json
import re
import asyncio
from datetime import datetime, timedelta
from uuid import UUID
from loguru import logger
from typing import Dict, List, Any, Optional, Union, cast, Tuple

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.language_models import BaseChatModel

from common.services.reranker import PineconeRerankerConfig, Reranker, RerankerConfig, RerankerType
from common.models.token_usage import ProjectType
from common.services.embedding_models import EmbeddingModelType
from stockeasy.prompts.report_prompts import (
    
    REPORT_ANALYSIS_SYSTEM_PROMPT,
    REPORT_ANALYSIS_USER_PROMPT,
    INVESTMENT_OPINION_PROMPT,
    format_report_contents
)
from common.core.config import settings
from common.services.vector_store_manager import VectorStoreManager
from common.services.retrievers.semantic import SemanticRetriever, SemanticRetrieverConfig
from common.services.retrievers.models import RetrievalResult
from common.utils.util import async_retry, measure_time_async
from stockeasy.models.agent_io import RetrievedAllAgentData, CompanyReportData
from langchain_core.messages import AIMessage
from common.services.agent_llm import get_llm_for_agent, get_agent_llm
from common.models.token_usage import ProjectType
from stockeasy.agents.base import BaseAgent
from sqlalchemy.ext.asyncio import AsyncSession

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
        formatted += f"\n--- 리포트 {i+1} ---\n"
        #formatted += f"제목: {report.get('title', '제목 없음')}\n"
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
        self.vs_manager = VectorStoreManager(
            embedding_model_type=EmbeddingModelType.OPENAI_3_LARGE,
            project_name="stockeasy",
            namespace=settings.PINECONE_NAMESPACE_STOCKEASY
        )
    
    async def process(self, state: Dict[str, Any]) -> Dict[str, Any]:
        process_start_time = datetime.now() # process 전체 시작 시간
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
                    "agent_name": "report_analyzer", "status": "failed", "data": {"reports_with_toc": {}}, 
                    "error": "검색 쿼리가 제공되지 않았습니다.", "execution_time": 0,
                    "metadata": {"model_name": self.model_name, "provider": self.provider}
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
            structured_search_results: Dict[str, Union[List[CompanyReportData], Dict[str, List[CompanyReportData]]]] = \
                await self._search_reports(
                    search_query, 
                    k, 
                    threshold, 
                    metadata_filter,
                    user_id=user_id,
                    final_report_toc=final_report_toc
                )
            search_duration = (datetime.now() - search_start_time).total_seconds()
            logger.info(f"기업리포트 검색 시간 (_search_reports): {search_duration:.2f} 초")

            main_query_reports = structured_search_results.get("main_query_results", [])
            toc_reports = structured_search_results.get("toc_results", {})
            processed_reports: List[CompanyReportData] = main_query_reports if isinstance(main_query_reports, list) else []

            analysis = None

            if not processed_reports and not structured_search_results.get("toc_results"):
                logger.warning("기업 리포트 검색 결과가 없습니다 (메인 쿼리 및 TOC 모두).")
                total_duration = (datetime.now() - process_start_time).total_seconds()
                state["agent_results"] = state.get("agent_results", {})
                state["agent_results"]["report_analyzer"] = {
                    "agent_name": "report_analyzer", "status": "partial_success_no_data",
                    "data": {"analysis": None, "searched_reports": [], "reports_with_toc": structured_search_results},
                    "error": "검색된 기업 리포트가 없습니다.", "execution_time": total_duration,
                    "metadata": {
                        "report_count": 0, "threshold": threshold, 
                        "model_name": self.model_name, "provider": self.provider
                    }
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
                    "provider": self.provider
                }
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
                "agent_name": "report_analyzer", "status": "failed",
                "data": {"analysis": None, "searched_reports": [], "reports_with_toc": {}},
                "error": str(e), "execution_time": total_duration if total_duration > 0 else 0,
                "metadata": {"model_name": self.model_name, "provider": self.provider}
            }
            if "retrieved_data" not in state: state["retrieved_data"] = {}
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
        state["errors"].append({
            "agent": "report_analyzer",
            "error": error_message,
            "type": "processing_error",
            "timestamp": datetime.now(),
            "context": {"query": state.get("query", "")}
        })
    
    def _make_search_query(self, query: str, stock_code: Optional[str], 
                          stock_name: Optional[str], classification: Dict[str, Any], 
                          state: Dict[str, Any]) -> str:
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
            #search_query += f", 오늘 {datetime.now().strftime('%Y-%m-%d')} 기준"
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
        return 20 # 무조건 20개 고정
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
    
    def _create_metadata_filter(self, stock_code: Optional[str], stock_name: Optional[str],
                              classification: Dict[str, Any], state: Dict[str, Any] = None) -> Dict[str, Any]:
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
        time_range = ""
        
        # classification에서 primary_intent 확인
        primary_intent = classification.get("primary_intent", "")
        
        # state에서 keywords 활용
        time_keywords = []
        if state and "keywords" in state:
            time_keywords = [kw for kw in state["keywords"] if any(t in kw for t in ["년", "분기", "월", "일", "최근"])]
        
        # 시간 범위가 있으면 해당 기간으로 제한
        if time_keywords and len(time_keywords) > 0:
            time_range = time_keywords[0]  # 첫 번째 시간 관련 키워드 사용
        
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
            recent_days_match = re.search(r'최근\s*(\d+)\s*일', time_range)
            if recent_days_match:
                days = int(recent_days_match.group(1))
                start_date = today - timedelta(days=days)
                return {
                    "$gte": start_date.strftime("%Y%m%d"),
                    "$lte": today.strftime("%Y%m%d")
                }
            
            # "최근 X개월" 패턴
            recent_months_match = re.search(r'최근\s*(\d+)\s*개월', time_range)
            if recent_months_match:
                months = int(recent_months_match.group(1))
                start_date = today.replace(month=today.month - months if today.month > months else today.month + 12 - months,
                                         year=today.year if today.month > months else today.year - 1)
                return {
                    "$gte": start_date.strftime("%Y%m%d"),
                    "$lte": today.strftime("%Y%m%d")
                }
            
            # "YYYY년" 패턴
            year_match = re.search(r'(20\d{2})년', time_range)
            if year_match:
                year = year_match.group(1)
                return {
                    "$gte": f"{year}0101",
                    "$lte": f"{year}1231"
                }
            
            # "X분기" 패턴
            quarter_match = re.search(r'(\d)분기', time_range)
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
    async def _search_reports(self, 
                             query: str, 
                             k: int,
                             threshold: float,
                             metadata_filter: Optional[Dict[str, Any]],
                             user_id: Optional[Union[str, UUID]],
                             final_report_toc: Optional[dict]
                             ) -> Dict[str, Union[List[CompanyReportData], Dict[str, List[CompanyReportData]]]]:
        """
        파인콘 DB에서 사용자 쿼리 및 목차별로 기업리포트를 검색하고,
        리랭킹 없이 구조화된 딕셔너리 형태로 반환합니다.
        목차 간 중복 문서는 허용되며, 각 검색 결과 리스트 내에서의 중복만 간단히 처리합니다.
        """
        
        report_data_for_summary_agent: Dict[str, Union[List[CompanyReportData], Dict[str, List[CompanyReportData]]]] = {
            "main_query_results": [],
            "toc_results": {} 
        }

        # 기본 필터 설정 (6개월 이내 문서)
        six_months_ago = datetime.now() - timedelta(days=150)
        six_months_ago_str = six_months_ago.strftime('%Y%m%d')
        six_months_ago_int = int(six_months_ago_str)
        
        current_metadata_filter = metadata_filter.copy() if metadata_filter else {}
        current_metadata_filter["document_date"] = {"$gte": six_months_ago_int}
            
        logger.info(f"[_search_reports] 사용자쿼리k: {k}, threshold: {threshold}, 필터: {current_metadata_filter}")
        
        parsed_user_id = None
        if user_id != "test_user":
            parsed_user_id = UUID(user_id) if isinstance(user_id, str) else user_id

        semantic_retriever = SemanticRetriever(
            config=SemanticRetrieverConfig(min_score=threshold, user_id=parsed_user_id, project_type=ProjectType.STOCKEASY),
            vs_manager=self.vs_manager
        )
        
        try:
            # 1. 기본 사용자 쿼리로 검색
            logger.info(f"  기본쿼리 검색 시작: '{query}' (k={k})")
            main_retrieval_result: RetrievalResult = await semantic_retriever.retrieve(
                query=query, 
                top_k=k, 
                filters=current_metadata_filter
            )
            main_query_reports_raw = [self._convert_doc_to_company_report_data(doc) for doc in main_retrieval_result.documents]
            report_data_for_summary_agent["main_query_results"] = self._deduplicate_company_reports_in_list(main_query_reports_raw)
            logger.info(f"  기본쿼리 검색 완료: 원본 {len(main_retrieval_result.documents)}개 -> 중복제거 후 {len(report_data_for_summary_agent['main_query_results'])}개")

            # 2. final_report_toc가 있는 경우 목차 항목별 검색 추가
            toc_search_queries: Dict[str, str] = {} 
            if final_report_toc and isinstance(final_report_toc, dict) and final_report_toc.get("sections"):
                toc_search_queries = self._extract_toc_queries_for_search(final_report_toc) 

            if toc_search_queries:
                k_toc = 10 # 각 TOC 항목별 검색할 문서 수 (조정 가능)
                logger.info(f"  TOC 기반 검색 시작. 총 TOC 쿼리 수: {len(toc_search_queries)}, 각 항목당 k_toc: {k_toc}")
                
                processed_toc_results: Dict[str, List[CompanyReportData]] = {}
                for toc_key, toc_item_query_text in toc_search_queries.items():
                    if not toc_item_query_text: 
                        logger.debug(f"    TOC 검색 건너<0xEB><0x9A><0x8D> (쿼리 비어있음): [{toc_key}]")
                        continue
                    try:
                        logger.debug(f"    TOC 검색 중 - [{toc_key}]: '{toc_item_query_text}'")
                        toc_retrieval_result: RetrievalResult = await semantic_retriever.retrieve(
                            query=toc_item_query_text, top_k=k_toc, filters=current_metadata_filter 
                        )
                        toc_item_reports_raw = [self._convert_doc_to_company_report_data(doc) for doc in toc_retrieval_result.documents]
                        processed_toc_results[toc_key] = self._deduplicate_company_reports_in_list(toc_item_reports_raw)
                        logger.debug(f"      TOC 검색 결과 [{toc_key}]: 원본 {len(toc_retrieval_result.documents)}개 -> 중복제거 후 {len(processed_toc_results[toc_key])}개")
                    except Exception as e:
                        logger.warning(f"    TOC 검색 오류 [{toc_key}]: {str(e)}")
                        processed_toc_results[toc_key] = [] 
                report_data_for_summary_agent["toc_results"] = processed_toc_results
                logger.info(f"  TOC 기반 검색 완료.")
            else:
                logger.info("  TOC 정보가 없거나 검색할 유효한 TOC 항목이 없어 TOC 기반 검색을 수행하지 않았습니다.")

        except Exception as e:
            logger.error(f"[_search_reports] 심각한 오류 발생: {str(e)}", exc_info=True)
        finally:
            if 'semantic_retriever' in locals() and semantic_retriever:
                await semantic_retriever.aclose()
                
        return report_data_for_summary_agent

    def _convert_doc_to_company_report_data(self, doc: Any) -> CompanyReportData:
        content = doc.page_content
        metadata = doc.metadata
        score = getattr(doc, 'score', metadata.get('_score', 0.0))
        if score is None: score = 0.0
        title = metadata.get("title")
        if not title and content:
            title = content.split('\n')[0][:100] 
        elif not title:
            title = "제목 없음"
        return {
            "content": content, "score": score,
            "source": metadata.get("provider_code", metadata.get("source", "미상")),
            "publish_date": self._format_date(metadata.get("document_date", "")),
            "file_name": metadata.get("file_name", ""), "page": metadata.get("page", 0),
            "stock_code": metadata.get("stock_code", ""), "stock_name": metadata.get("stock_name", ""),
            "sector_name": metadata.get("sector_name", ""), "title": title 
        }

    def _extract_toc_queries_for_search(self, toc_data: dict) -> Dict[str, str]:
        queries: Dict[str, str] = {}
        if not (isinstance(toc_data, dict) and "sections" in toc_data and isinstance(toc_data["sections"], list)):
            logger.warning("TOC 데이터 구조가 유효하지 않아 검색 쿼리를 추출할 수 없습니다.")
            return queries
        for section_index, section in enumerate(toc_data["sections"]):
            if section_index == 0: continue
            if not isinstance(section, dict): continue
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
                unique_key = section_id # 제목 부분 제외
                queries[unique_key] = section_title
        logger.info(f"TOC에서 추출된 검색 쿼리 수: {len(queries)}")
        if len(queries) > 0 : logger.debug(f"  추출된 TOC 쿼리 (일부): {list(queries.items())[:3]}")
        return queries

    def _deduplicate_company_reports_in_list(self, reports: List[CompanyReportData]) -> List[CompanyReportData]:
        if not reports: return []
        deduped_reports: List[CompanyReportData] = []
        seen_identifiers = set()
        for report in reports:
            content_prefix = report.get('content', '')[:200] if report.get('content') else ''
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
            date_str = str(date_str).split('.')[0]  # 소수점 이하 제거
            
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
        cleaned = re.sub(r'\s+', ' ', content).strip()
        
        # 표, 서식 등의 특수문자 정리
        cleaned = re.sub(r'[\u2028\u2029\ufeff\xa0]', ' ', cleaned)
        
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