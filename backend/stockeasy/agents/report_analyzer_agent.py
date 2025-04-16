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
    REPORT_ANALYSIS_PROMPT,
    REPORT_ANALYSIS_SYSTEM_PROMPT,
    REPORT_ANALYSIS_USER_PROMPT,
    INVESTMENT_OPINION_PROMPT,
    format_report_contents
)
from common.core.config import settings
from common.services.vector_store_manager import VectorStoreManager
from common.services.retrievers.semantic import SemanticRetriever, SemanticRetrieverConfig
from common.services.retrievers.models import RetrievalResult
from common.utils.util import async_retry
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
        formatted += f"제목: {report.get('title', '제목 없음')}\n"
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
        # 설정 파일에서 LLM 생성 및 모델 정보 가져오기
        self.retrieved_str = "report_data"
        self.llm, self.model_name, self.provider = get_llm_for_agent("report_analyzer_agent")
        self.agent_llm = get_agent_llm("report_analyzer_agent")
        self.parser = JsonOutputParser()
        self.prompt_template = REPORT_ANALYSIS_SYSTEM_PROMPT
        logger.info(f"ReportAnalyzerAgent initialized with provider: {self.provider}, model: {self.model_name}")
    
    async def process(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        기업 리포트 검색 및 분석을 수행합니다.
        
        Args:
            state: 현재 상태 정보를 포함하는 딕셔너리
            
        Returns:
            업데이트된 상태 딕셔너리
        """
        try:
            # 성능 측정 시작
            start_time = datetime.now()
            logger.info(f"ReportAnalyzerAgent starting processing with {self.provider} {self.model_name}")
            
            # 현재 사용자 쿼리 및 세션 정보 추출
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
            
            if not query:
                logger.warning("Empty query provided to ReportAnalyzerAgent")
                self._add_error(state, "검색 쿼리가 제공되지 않았습니다.")
                return state
            
            logger.info(f"ReportAnalyzerAgent processing query: {query}")
            #logger.info(f"Classification data: {classification}")
            #logger.info(f"State keys: {state.keys()}")
            logger.info(f"Entities: {entities}")
            #logger.info(f"Data requirements: {data_requirements}")
            #logger.info(f"stock_code: {state.get('stock_code')}")
            #logger.info(f"type(state): {type(state)}")
            
            
            user_context = state.get("user_context", {})
            user_id = user_context.get("user_id", None)

            # 벡터DB 검색 쿼리 생성 - question_classification 활용
            search_query = self._make_search_query(query, stock_code, stock_name, classification, state)
            
            # 검색 매개변수 설정 - 세부 의도와 복잡성에 따라 조정
            k = self._get_report_count(classification)
            threshold = self._calculate_dynamic_threshold(classification)
            metadata_filter = self._create_metadata_filter(stock_code, stock_name, classification, state)
            
            # 기업리포트 검색
            reports:List[CompanyReportData] = await self._search_reports(
                search_query, 
                k, 
                threshold, 
                metadata_filter,
                user_id=user_id
            )
            
            # 검색 결과가 없는 경우
            if not reports:
                logger.warning("기업 리포트 검색 결과가 없습니다.")
                
                # 실행 시간 계산
                end_time = datetime.now()
                duration = (end_time - start_time).total_seconds()
                
                # 새로운 구조로 상태 업데이트 (결과 없음)
                state["agent_results"] = state.get("agent_results", {})
                state["agent_results"]["report_analyzer"] = {
                    "agent_name": "report_analyzer",
                    "status": "partial_success",
                    "data": [],
                    "error": None,
                    "execution_time": duration,
                    "metadata": {
                        "report_count": 0,
                        "threshold": threshold,
                        "model_name": self.model_name,
                        "provider": self.provider
                    }
                }
                
                # 타입 주석을 사용한 데이터 할당
                if "retrieved_data" not in state:
                    state["retrieved_data"] = {}
                retrieved_data = cast(RetrievedAllAgentData, state["retrieved_data"])
                reports: List[CompanyReportData] = []
                retrieved_data[self.retrieved_str] = reports
                
                state["processing_status"] = state.get("processing_status", {})
                state["processing_status"]["report_analyzer"] = "completed_no_data"
                
                # 메트릭 기록
                state["metrics"] = state.get("metrics", {})
                state["metrics"]["report_analyzer"] = {
                    "start_time": start_time,
                    "end_time": end_time,
                    "duration": duration,
                    "status": "completed_no_data",
                    "error": None,
                    "model_name": self.model_name,
                    "provider": self.provider
                }
                
                logger.info(f"ReportAnalyzerAgent completed in {duration:.2f} seconds, found 0 reports")
                return state
            
            # 검색 결과 가공
            processed_reports:List[CompanyReportData] = self._process_reports(reports)
            
            # 상세한 분석이 필요한 경우 (primary_intent와 complexity 기반 판단)
            primary_intent = classification.get("primary_intent", "")
            complexity = classification.get("complexity", "")
            
            # primary_intent: Literal["종목기본정보", "성과전망", "재무분석", "산업동향", "기타"] # 주요 질문 의도
            # complexity: Literal["단순", "중간", "복합", "전문가급"]                      # 질문 복잡도
            # expected_answer_type: Literal["사실형", "추론형", "비교형", "예측형", "설명형"]  # 기대하는 답변 유형

            # 성과전망, 복합, 전문가급 질문이 아니면. 그냥 벡터 DB 검색결과를 리턴함.
            # need_detailed_analysis = (
            #     primary_intent in ["성과전망", "재무분석", "산업동향"] or 
            #     complexity in ["복합", "전문가급"]
            # )
            # logger.info(f"need_detailed_analysis: {need_detailed_analysis}")
            need_detailed_analysis = True

            # 리포트 내용에서 핵심 정보 추출 및 분석
            try:
                # 커스텀 프롬프트 템플릿 확인
                # 1. 상태에서 커스텀 프롬프트 템플릿 확인
                custom_prompt_from_state = state.get("custom_prompt_template")
                # 2. 속성에서 커스텀 프롬프트 템플릿 확인 
                custom_prompt_from_attr = getattr(self, "prompt_template_test", None)
                # 커스텀 프롬프트 사용 우선순위: 상태 > 속성 > 기본값
                system_prompt = None
                if custom_prompt_from_state:
                    system_prompt = custom_prompt_from_state
                    logger.info(f"ReportAnalyzerAgent using custom prompt from state : {custom_prompt_from_state}")
                elif custom_prompt_from_attr:
                    system_prompt = custom_prompt_from_attr
                    logger.info(f"ReportAnalyzerAgent using custom prompt from attribute")
                    
                analysis = await self._generate_report_analysis(
                    processed_reports, 
                    query, 
                    stock_code, 
                    stock_name,
                    state,
                    system_prompt=system_prompt
                )
                
            except Exception as e:
                logger.error(f"기업 리포트 분석 중 오류 발생: {str(e)}")
            
            # 실행 시간 계산
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            

            state["agent_results"] = state.get("agent_results", {})
            state["agent_results"]["report_analyzer"] = {
                "agent_name": "report_analyzer",
                "status": "success",
                "data": {
                        "analysis": analysis if need_detailed_analysis else None,
                        "searched_reports": processed_reports,
                    },
                "error": None,
                "execution_time": duration,
                "metadata": {
                    "report_count": len(processed_reports),
                    "threshold": threshold,
                    "detailed_analysis": need_detailed_analysis,
                    "model_name": self.model_name,
                    "provider": self.provider
                }
            }
            
            # 타입 주석을 사용한 데이터 할당
            # state["retrieved_data"]["reports"] = processed_reports
            if "retrieved_data" not in state:
                state["retrieved_data"] = {}
            retrieved_data = cast(RetrievedAllAgentData, state["retrieved_data"])
            reports: List[CompanyReportData] = processed_reports
            retrieved_data[self.retrieved_str] = reports

            
            state["processing_status"] = state.get("processing_status", {})
            state["processing_status"]["report_analyzer"] = "completed"
            logger.info(f"ReportAnalyzerAgent processing_status: {state['processing_status']}")
            
            # 메트릭 기록
            state["metrics"] = state.get("metrics", {})
            state["metrics"]["report_analyzer"] = {
                "start_time": start_time,
                "end_time": end_time,
                "duration": duration,
                "status": "completed",
                "error": None,
                "model_name": self.model_name,
                "provider": self.provider
            }
            
            logger.info(f"ReportAnalyzerAgent completed in {duration:.2f} seconds, found {len(processed_reports)} reports")
            return state
            
        except Exception as e:
            logger.exception(f"Error in ReportAnalyzerAgent: {str(e)}")
            self._add_error(state, f"기업 리포트 검색 에이전트 오류: {str(e)}")
            
            # 오류 상태 업데이트
            state["agent_results"] = state.get("agent_results", {})
            state["agent_results"]["report_analyzer"] = {
                "agent_name": "report_analyzer",
                "status": "failed",
                "data": [],
                "error": str(e),
                "execution_time": 0,
                "metadata": {
                    "model_name": self.model_name,
                    "provider": self.provider
                }
            }
            
            # 타입 주석을 사용한 데이터 할당
            if "retrieved_data" not in state:
                state["retrieved_data"] = {}
            retrieved_data = cast(RetrievedAllAgentData, state["retrieved_data"])
            reports: List[CompanyReportData] = []
            retrieved_data[self.retrieved_str] = reports
            
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
            return 0.5
        elif complexity == "중간":
            return 0.35
        elif complexity == "복합":
            return 0.25
        else:  # "전문가급"
            return 0.21
    
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
        
        if time_range:
            date_filter = self._parse_time_range(time_range)
            if date_filter:
                metadata_filter["document_date"] = date_filter
        
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
    
    @async_retry(retries=3, delay=1.0, exceptions=(Exception,))
    async def _search_reports(self, query: str, k: int = 5, threshold: float = 0.3,
                             metadata_filter: Optional[Dict[str, Any]] = None,
                             user_id: Optional[Union[str, UUID]] = None) -> List[CompanyReportData]:
        """
        파인콘 DB에서 기업리포트 검색
        
        Args:
            query: 검색 쿼리
            k: 검색할 최대 결과 수
            threshold: 유사도 임계값
            metadata_filter: 메타데이터 필터
            
        Returns:
            검색된 리포트 목록
        """
        try:
            # 벡터 스토어 연결
            vs_manager = VectorStoreManager(
                embedding_model_type=EmbeddingModelType.OPENAI_3_LARGE,
                project_name="stockeasy",
                namespace=settings.PINECONE_NAMESPACE_STOCKEASY
            )

            # UUID 변환 로직: 문자열이면 UUID로 변환, UUID 객체면 그대로 사용, None이면 None
            if user_id != "test_user":
                parsed_user_id = UUID(user_id) if isinstance(user_id, str) else user_id
            else:
                parsed_user_id = None

            # 시맨틱 검색 설정
            semantic_retriever = SemanticRetriever(
                config=SemanticRetrieverConfig(min_score=threshold,
                                               user_id=parsed_user_id,
                                               project_type=ProjectType.STOCKEASY),
                vs_manager=vs_manager
            )
            
            # 검색 수행
            retrieval_result: RetrievalResult = await semantic_retriever.retrieve(
                query=query, 
                top_k=k * 4,  # 중복 제거, 리랭킹을 고려하여 4배로 검색
                filters=metadata_filter
            )

            # 2. 리랭킹 수행
            reranker = Reranker(
                RerankerConfig(
                    reranker_type=RerankerType.PINECONE,
                    pinecone_config=PineconeRerankerConfig(
                        api_key=settings.PINECONE_API_KEY_STOCKEASY,
                        min_score=0.1  # 낮은 임계값으로 더 많은 결과 포함
                    )
                )
            )
            
            reranked_results = await reranker.rerank(
                query=query,
                documents=retrieval_result.documents,
                top_k=int(k * 1.5)
            )
            logger.info(f"리랭킹 완료 - 결과: {len(retrieval_result.documents)} -> {len(reranked_results.documents)} 문서")
            # 검색 결과 처리
            results = []
            seen_contents = set()  # 중복 제거를 위한 집합
            
            #for i, doc in enumerate(retrieval_result.documents):
            for i, doc in enumerate(reranked_results.documents):
                content = doc.page_content
                metadata = doc.metadata
                score = doc.score or 0.0
                if i < 2:
                    short_content = (content[:50] if len(content) > 50 else content).strip().replace("\n\n", "\n")
                    logger.debug(f"문서 {i} 점수: {score:.3f}, 내용({len(content)}): {short_content}")
                    short_metadata = {k: v for k, v in metadata.items() if k in ["stock_code", "stock_name", "sector_code", "sector_name", "document_date", "report_provider", "file_name", "page", "category"]}
                    logger.debug(f"문서 {i} 메타데이터: {short_metadata}")
                    logger.debug(f"---------------------------------------------------------------")
                
                # 내용 기반 중복 제거 (문서 일부가 중복되는 경우가 많음)
                content_hash = hash(content[:100])  # 앞부분을 기준으로
                if content_hash in seen_contents:
                    continue
                seen_contents.add(content_hash)
                
                # 결과 정보 구성
                report_info:CompanyReportData = {
                    "content": content,
                    "score": score,
                    "source": metadata.get("provider_code", "미상"),
                    "publish_date": self._format_date(metadata.get("document_date", "")),
                    "file_name": metadata.get("file_name", ""),
                    "page": metadata.get("page", 0),
                    "stock_code": metadata.get("stock_code", ""),
                    "stock_name": metadata.get("stock_name", ""),
                    "sector_name": metadata.get("sector_name", ""),

                }             
                
                results.append(report_info)
            
            # 스코어 기준 정렬
            results.sort(key=lambda x: x["score"], reverse=True)
            
            # 최대 k개만 반환
            return results[:k]
            
        except Exception as e:
            logger.error(f"기업리포트 검색 중 오류 발생: {str(e)}", exc_info=True)
            raise
    
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
    
    async def _generate_report_analysis(self, reports: List[CompanyReportData], query: str, 
                                       stock_code: Optional[str] = None, 
                                       stock_name: Optional[str] = None,
                                       state: Dict[str, Any] = {},
                                       system_prompt: Optional[str] = None) -> List[CompanyReportData]:
        """
        검색된 리포트의 투자 의견 및 목표가 정보 추출
        
        Args:
            reports: 검색된 리포트 목록
            query: 사용자 쿼리
            stock_code: 종목 코드
            stock_name: 종목명
            
        Returns:
            각 리포트에 대한 분석 결과
        """
        if not reports:
            return []
        
        # 리포트 내용 형식화
        formatted_reports = format_report_contents(reports)
        
        # 1) 기본 분석 프롬프트 생성
        query_with_date = f"오늘 {datetime.now().strftime('%Y-%m-%d')} 기준, {query}"
        qa = state.get("question_analysis", {})
        keywords = qa.get("keywords", [])
        if keywords:
            important_keywords = ", ".join(keywords[:3])  # 상위 3개 키워드 사용
        
        # 시스템 메시지와 사용자 메시지 분리 구성
        if system_prompt:
            system_message = SystemMessagePromptTemplate.from_template(system_prompt)
        else:
            system_message = SystemMessagePromptTemplate.from_template(REPORT_ANALYSIS_SYSTEM_PROMPT)
        user_message = HumanMessagePromptTemplate.from_template(REPORT_ANALYSIS_USER_PROMPT)
        
        # ChatPromptTemplate 구성
        analysis_prompt = ChatPromptTemplate.from_messages([
            system_message,
            user_message
        ]).partial(
            query=query_with_date,
            stock_code=stock_code or "정보 없음",
            stock_name=stock_name or "정보 없음",
            report_contents=formatted_reports,
            keywords=important_keywords if important_keywords else ""
        )
        
        # 2) 투자 의견 및 목표가 추출 프롬프트
        opinion_prompt = ChatPromptTemplate.from_template(INVESTMENT_OPINION_PROMPT).partial(
            stock_code=stock_code or "정보 없음",
            stock_name=stock_name or "정보 없음",
            report_contents=formatted_reports
        )
        
        # 폴백을 지원하는 AgentLLM 객체 사용
        
        # 병렬로 분석 실행 (폴백 메커니즘 사용)
        try:
            user_context = state.get("user_context", {})
            user_id = user_context.get("user_id", None)
            
            # 프롬프트 형식화
            formatted_analysis_prompt = analysis_prompt.format_prompt()
            formatted_opinion_prompt = opinion_prompt.format_prompt()
            
            # 병렬 실행
            results = await asyncio.gather(
                self.agent_llm.ainvoke_with_fallback(formatted_analysis_prompt, user_id=user_id, project_type=ProjectType.STOCKEASY, db=self.db),
                self.agent_llm.ainvoke_with_fallback(formatted_opinion_prompt, user_id=user_id, project_type=ProjectType.STOCKEASY, db=self.db),
                return_exceptions=True
            )
            
            # 결과 처리
            analysis_result:AIMessage = results[0] if not isinstance(results[0], Exception) else ""
            opinion_result:AIMessage = results[1] if not isinstance(results[1], Exception) else ""
            
            # 예외 로깅
            if isinstance(results[0], Exception):
                logger.error(f"리포트 분석 중 오류 발생: {str(results[0])}")
            if isinstance(results[1], Exception):
                logger.error(f"투자 의견 추출 중 오류 발생: {str(results[1])}")
            
            # 투자 의견 및 목표가 추출
            investment_opinions = []
            target_prices = []
            
            if opinion_result:
                try:
                    # 투자 의견 정보 파싱 시도
                    opinion_data = {}
                    opinion_content = opinion_result.content
                    # "투자의견:" 또는 "투자 의견:" 패턴 찾기
                    opinion_pattern = r'(투자\s*의견|투자의견)\s*:\s*([^\n,]+)'
                    opinion_matches = re.findall(opinion_pattern, opinion_content)
                    
                    # "목표가:" 또는 "목표 가격:" 패턴 찾기
                    price_pattern = r'(목표\s*가격|목표가|목표\s*주가)\s*:\s*([\d,]+)'
                    price_matches = re.findall(price_pattern, opinion_content)
                    
                    for report in reports:
                        source = report["source"] # provider_code, 증권사
                        date = report["publish_date"]
                        
                        # 해당 리포트에 대한 투자 의견 찾기
                        report_opinion = None
                        for _, opinion in opinion_matches:
                            if source in opinion_content and date in opinion_content:
                                report_opinion = opinion.strip()
                                break
                        
                        # 해당 리포트에 대한 목표가 찾기
                        report_price = None
                        for _, price in price_matches:
                            if source in opinion_content and date in opinion_content:
                                try:
                                    # 쉼표 제거 후 숫자로 변환
                                    report_price = int(price.replace(",", ""))
                                except ValueError:
                                    pass
                                break
                        
                        investment_opinions.append({
                            "source": source,
                            "date": date,
                            "opinion": report_opinion,
                            "target_price": report_price
                        })
                except Exception as e:
                    logger.error(f"투자 의견 추출 중 오류: {e}", exc_info=True)
            
            # 분석 결과 구조화
            #report_analyses = []
            #for report in reports:
            analysis_content = analysis_result.content if not isinstance(analysis_result, Exception) else "분석 중 오류가 발생했습니다."
            opinion_content = opinion_result.content if not isinstance(opinion_result, Exception) else "의견 추출 중 오류가 발생했습니다."
                
            #report_analyses.append()
            
            return {
                #"analysis": {
                    "llm_response": analysis_content,
                    "investment_opinions": investment_opinions,
                    "opinion_summary": opinion_content
                #}
                #"searched_documents": reports
            }
            
        except Exception as e:
            logger.exception(f"리포트 분석 프로세스 전체 오류: {str(e)}")
            return [] 