"""
산업 및 시장 동향 분석을 위한 에이전트

이 모듈은 산업 및 시장 동향 정보를 검색하고 분석하는 에이전트를 정의합니다.
"""

import re
from typing import Dict, List, Any, Optional, cast
from datetime import datetime
from uuid import UUID
from loguru import logger

from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import JsonOutputParser
from langchain.prompts import PromptTemplate

from common.services.embedding_models import EmbeddingModelType
from common.services.retrievers.models import RetrievalResult
from common.services.retrievers.semantic import SemanticRetriever, SemanticRetrieverConfig
from common.services.vector_store_manager import VectorStoreManager
from common.utils.util import async_retry
from stockeasy.prompts.industry_prompts import INDUSTRY_ANALYSIS_PROMPT
# from stockeasy.services.industry.industry_data_service import IndustryDataService
# from stockeasy.services.stock.stock_info_service import StockInfoService
from stockeasy.models.agent_io import IndustryReportData, RetrievedAllAgentData, IndustryData
from common.services.agent_llm import get_agent_llm, get_llm_for_agent
from common.core.config import settings
from langchain_core.messages import AIMessage, HumanMessage
from common.models.token_usage import ProjectType
from stockeasy.agents.base import BaseAgent
from sqlalchemy.ext.asyncio import AsyncSession

class IndustryAnalyzerAgent(BaseAgent):
    """산업 및 시장 동향 분석 에이전트"""

    def __init__(self, name: Optional[str] = None, db: Optional[AsyncSession] = None):
        """
        산업 및 시장 동향 분석 에이전트 초기화
        
        Args:
            name: 에이전트 이름 (지정하지 않으면 클래스명 사용)
            db: 데이터베이스 세션 객체 (선택적)
        """
        super().__init__(name, db)
        self.retrieved_str = "industry_report"
        self.llm, self.model_name, self.provider = get_llm_for_agent("industry_analyzer_agent")
        self.agent_llm = get_agent_llm("industry_analyzer_agent")
        self.parser = JsonOutputParser()
        logger.info(f"IndustryAnalyzerAgent initialized with provider: {self.provider}, model: {self.model_name}")
        
        # 서비스 초기화
        #self.industry_service = IndustryDataService()
        #self.stock_service = StockInfoService()

    async def process(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        산업 및 시장 동향 분석을 수행합니다.
        
        Args:
            state: 현재 상태 정보를 포함하는 딕셔너리
            
        Returns:
            업데이트된 상태 딕셔너리
        """
        try:
            # 성능 측정 시작
            start_time = datetime.now()
            logger.info("IndustryAnalyzerAgent starting processing")
            
            # 현재 쿼리 및 세션 정보 추출
            query = state.get("query", "")
            
            # 질문 분석 결과 추출 (새로운 구조)
            question_analysis = state.get("question_analysis", {})
            entities = question_analysis.get("entities", {})
            classification = question_analysis.get("classification", {})
            data_requirements = question_analysis.get("data_requirements", {})
            keywords = question_analysis.get("keywords", [])
            detail_level = question_analysis.get("detail_level", "보통")
            user_id = state.get("user_context", {}).get("user_id", None)
            
            # 엔티티에서 종목 정보 추출
            stock_code = entities.get("stock_code", state.get("stock_code"))
            stock_name = entities.get("stock_name", state.get("stock_name"))
            sector = entities.get("sector", "")
            
            logger.info(f"IndustryAnalyzerAgent analyzing: {stock_code or stock_name}")
            logger.info(f"sector: {sector}, keywords: {keywords}")
            #logger.info(f"Classification data: {classification}")
            #logger.info(f"Data requirements: {data_requirements}")
            
            # 종목 코드 또는 종목명이 없는 경우 처리
            if not stock_code and not stock_name:
                logger.warning("No stock information provided to IndustryAnalyzerAgent")
                self._add_error(state, "산업 분석을 위한 종목 정보가 없습니다.")
                return state
            
            # 산업/섹터 정보가 없는 경우 조회
            if not sector and stock_name:
                logger.info(f"Retrieving sector info for {stock_name}, no sector provided")
                # try:
                #     stock_info = await self.stock_service.get_stock_by_name(stock_name)
                #     if stock_info and "sector" in stock_info:
                #         sector = stock_info["sector"]
                #         logger.info(f"Retrieved sector '{sector}' for {stock_name}")
                #     else:
                #         # 임시 더미 데이터 사용
                #         sector = self._get_dummy_sector(stock_name)
                #         logger.info(f"Using dummy sector '{sector}' for {stock_name}")
                # except Exception as e:
                #     logger.error(f"Error retrieving sector info: {str(e)}")
                #     sector = self._get_dummy_sector(stock_name)
            
            # 산업 데이터 조회
            try:
                # 실제 구현에서는 업종/산업 데이터 서비스 활용
                # industry_data = await self.industry_service.get_industry_data(sector)

                k = self._get_report_count(classification)
                threshold = self._calculate_dynamic_threshold(classification)

                # 제거하고 싶은 특정 문자열 목록
                exclude_keywords = ["실적", "주가", "전망", "투자", "기업", "회사", "산업", "설명"]
                
                # keywords에서 제외할 키워드 필터링
                filtered_keywords = [kw for kw in keywords if kw not in exclude_keywords]
                keywords_list = keywords
                sector_list = []  # 기본값으로 빈 리스트 초기화
                if sector:
                    sector_splits = sector.split("/")
                    sector_list = [x.strip() for x in sector_splits] # 제약/바이오 같은 패턴 분리.
                    keywords_list += sector_list
                

                searched_industry_data = await self._search_reports(query, k=k, threshold=threshold, metadata_filter={"subgroup_list": {"$in":sector_list}} if sector_list else {}, user_id=user_id)
                searched_industry_data2 = await self._search_reports(query, k=k, threshold=threshold, metadata_filter={"keywords": {"$in":keywords_list}}, user_id=user_id)
                
                # 두 검색 결과 병합 및 중복 제거
                merged_industry_data = self._merge_and_remove_duplicates(searched_industry_data, searched_industry_data2)
                
                if not merged_industry_data:
                    logger.warning(f"No industry data found for sector: {sector}")
                    
                    # 실행 시간 계산
                    end_time = datetime.now()
                    duration = (end_time - start_time).total_seconds()
                    
                    # 새로운 구조로 상태 업데이트 (결과 없음)
                    state["agent_results"] = state.get("agent_results", {})
                    state["agent_results"]["industry_analyzer"] = {
                        "agent_name": "industry_analyzer",
                        "status": "partial_success",
                        "data": [],
                        "error": "산업 데이터를 찾을 수 없습니다.",
                        "execution_time": duration,
                        "metadata": {
                            "sector": sector,
                            "stock_name": stock_name
                        }
                    }
                    
                    # 타입 주석을 사용한 데이터 할당
                    if "retrieved_data" not in state:
                        state["retrieved_data"] = {}
                    retrieved_data = cast(RetrievedAllAgentData, state["retrieved_data"])
                    industry_data_result: List[IndustryReportData] = []
                    retrieved_data[self.retrieved_str] = industry_data_result
                    
                    state["processing_status"] = state.get("processing_status", {})
                    state["processing_status"]["industry_analyzer"] = "completed_no_data"
                    
                    # 메트릭 기록
                    state["metrics"] = state.get("metrics", {})
                    state["metrics"]["industry_analyzer"] = {
                        "start_time": start_time,
                        "end_time": end_time,
                        "duration": duration,
                        "status": "completed_no_data",
                        "error": None,
                        "model_name": self.model_name
                    }
                    
                    logger.info(f"IndustryAnalyzerAgent completed in {duration:.2f} seconds, no data found")
                    return state
                
                # 검색 결과 가공
                processed_industry_data:List[IndustryReportData] = self._process_reports(merged_industry_data)
                
                analysis = await self._generate_report_analysis(
                        processed_industry_data, 
                        query, 
                        stock_code, 
                        stock_name,
                        state
                    )
                # # 산업 데이터 분석
                # analysis_results = await self._analyze_industry_data(
                #     searched_industry_data, 
                #     query,
                #     sector,
                #     stock_code,
                #     stock_name,
                #     classification,
                #     detail_level
                # )
                
                # 실행 시간 계산
                end_time = datetime.now()
                duration = (end_time - start_time).total_seconds()
                
                # 새로운 구조로 상태 업데이트
                state["agent_results"] = state.get("agent_results", {})
                state["agent_results"]["industry_analyzer"] = {
                    "agent_name": "industry_analyzer",
                    "status": "success",
                    "data": {
                        "analysis": analysis,
                        "searched_reports": merged_industry_data
                    },
                    "error": None,
                    "execution_time": duration,
                    "metadata": {
                        "sector": sector,
                        "stock_name": stock_name
                    }
                }
                
                # 타입 주석을 사용한 데이터 할당
                if "retrieved_data" not in state:
                    state["retrieved_data"] = {}
                retrieved_data = cast(RetrievedAllAgentData, state["retrieved_data"])
                industry_data_result: List[IndustryReportData] = {
                    "searched_reports": merged_industry_data,
                    "analysis": analysis
                }
                retrieved_data[self.retrieved_str] = industry_data_result
                
                state["processing_status"] = state.get("processing_status", {})
                state["processing_status"]["industry_analyzer"] = "completed"
                
                # 메트릭 기록
                state["metrics"] = state.get("metrics", {})
                state["metrics"]["industry_analyzer"] = {
                    "start_time": start_time,
                    "end_time": end_time,
                    "duration": duration,
                    "status": "completed",
                    "error": None,
                    "model_name": self.model_name
                }
                
                logger.info(f"IndustryAnalyzerAgent completed in {duration:.2f} seconds")
                return state
                
            except Exception as e:
                logger.exception(f"Error in industry data processing: {str(e)}")
                self._add_error(state, f"산업 데이터 처리 오류: {str(e)}")
                
                # 오류 상태 업데이트
                state["agent_results"] = state.get("agent_results", {})
                state["agent_results"]["industry_analyzer"] = {
                    "agent_name": "industry_analyzer",
                    "status": "failed",
                    "data": [],
                    "error": str(e),
                    "execution_time": 0,
                    "metadata": {}
                }
                
                # 타입 주석을 사용한 데이터 할당
                if "retrieved_data" not in state:
                    state["retrieved_data"] = {}
                retrieved_data = cast(RetrievedAllAgentData, state["retrieved_data"])
                industry_data_result: List[IndustryReportData] = []
                retrieved_data["industry"] = industry_data_result
                
                state["processing_status"] = state.get("processing_status", {})
                state["processing_status"]["industry_analyzer"] = "error"
                
                return state
                
        except Exception as e:
            logger.exception(f"Error in IndustryAnalyzerAgent: {str(e)}")
            self._add_error(state, f"산업 분석 에이전트 오류: {str(e)}")
            
            # 오류 상태 업데이트
            state["agent_results"] = state.get("agent_results", {})
            state["agent_results"]["industry_analyzer"] = {
                "agent_name": "industry_analyzer",
                "status": "failed",
                "data": [],
                "error": str(e),
                "execution_time": 0,
                "metadata": {}
            }
            
            # 타입 주석을 사용한 데이터 할당
            if "retrieved_data" not in state:
                state["retrieved_data"] = {}
            retrieved_data = cast(RetrievedAllAgentData, state["retrieved_data"])
            industry_data_result: List[IndustryReportData] = []
            retrieved_data[self.retrieved_str] = industry_data_result
            
            state["processing_status"] = state.get("processing_status", {})
            state["processing_status"]["industry_analyzer"] = "error"
            
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
            "agent": "industry_analyzer",
            "error": error_message,
            "type": "processing_error",
            "timestamp": datetime.now(),
            "context": {"query": state.get("query", "")}
        })
    
    async def _generate_report_analysis(self, reports: List[IndustryReportData], query: str, 
                                       stock_code: Optional[str] = None, 
                                       stock_name: Optional[str] = None,
                                       state: Dict[str, Any] = {}) -> List[IndustryReportData]:
        """
        파인콘 DB에서 검색된 산업 리포트를 분석합니다.
        
        Args:
            reports: 산업 리포트 데이터 리스트
            query: 사용자 질문
            stock_code: 종목 코드 (선택)
            stock_name: 종목명 (선택)
            state: 현재 상태 정보
            
        Returns:
            분석이 추가된 산업 리포트 데이터 리스트
        """
        if not reports:
            logger.warning("산업 리포트 데이터가 없습니다.")
            return []
        
        try:
            # 질문 분류 정보 가져오기
            classification = {}
            if state and "question_analysis" in state and "classification" in state["question_analysis"]:
                classification = state["question_analysis"]["classification"]
            
            # 섹터 정보 가져오기
            sector = ""
            if state and "question_analysis" in state and "entities" in state["question_analysis"]:
                sector = state["question_analysis"]["entities"].get("sector", "")
            # 없으면 첫 번째 리포트에서 가져오기
            if not sector and reports and "sector_name" in reports[0]:
                sector = reports[0]["sector_name"]
            
            # 산업 리포트 데이터 포맷팅
            from stockeasy.prompts.industry_prompts import format_industry_data
            formatted_industry_data = format_industry_data(reports)
            
            # 산업 분석 프롬프트 생성
            from stockeasy.prompts.industry_prompts import INDUSTRY_ANALYSIS_PROMPT
            prompt = PromptTemplate(
                template=INDUSTRY_ANALYSIS_PROMPT,
                input_variables=["query", "stock_code", "stock_name", "sector", "classification", "industry_data"]
            )
            
            # user_id 추출
            user_context = state.get("user_context", {})
            user_id = user_context.get("user_id", None)

            # 프롬프트 포맷팅
            formatted_prompt = prompt.format(
                query=query,
                stock_code=stock_code or "",
                stock_name=stock_name or "",
                sector=sector,
                classification=classification,
                industry_data=formatted_industry_data
            )
            
            # LLM 호출
            analysis_result = await self.agent_llm.ainvoke_with_fallback(
                input=formatted_prompt,
                user_id=user_id,
                project_type=ProjectType.STOCKEASY,
                db=self.db
            )
            
            logger.info(f"산업 리포트 분석 완료: {len(reports)} 개의 리포트")
            
            return {
                "llm_response": analysis_result.content,
            }
            
        except Exception as e:
            logger.exception(f"산업 리포트 분석 중 오류 발생: {str(e)}")
            # 오류 발생시 원본 데이터 반환
            for report in reports:
                report["analysis"] = {"error": f"분석 중 오류 발생: {str(e)}"}
            return reports

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
            return 5
        elif complexity == "중간":
            return 10
        elif complexity == "복합":
            return 20
        else:  # "전문가급"
            return 30
        
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
        
    @async_retry(retries=3, delay=1.0, exceptions=(Exception,))
    async def _search_reports(self, query: str, k: int = 5, threshold: float = 0.22,
                             metadata_filter: Optional[Dict[str, Any]] = None,
                             user_id: Optional[UUID] = None) -> List[IndustryReportData]:
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
                namespace=settings.PINECONE_NAMESPACE_STOCKEASY_INDUSTRY
            )

            # 시맨틱 검색 설정
            semantic_retriever = SemanticRetriever(
                config=SemanticRetrieverConfig(min_score=threshold, user_id=user_id, project_type=ProjectType.STOCKEASY),
                vs_manager=vs_manager
            )
            
            # 검색 수행
            retrieval_result: RetrievalResult = await semantic_retriever.retrieve(
                query=query, 
                top_k=k * 2,  # 중복 제거를 고려하여 2배로 검색
                filters=metadata_filter
            )
            
            # 검색 결과 처리
            results = []
            seen_contents = set()  # 중복 제거를 위한 집합
            
            for i, doc in enumerate(retrieval_result.documents):
                content = doc.page_content
                metadata = doc.metadata
                score = doc.score or 0.0
                if i < 2:
                    short_content = (content[:50] if len(content) > 50 else content).strip()
                    logger.info(f"문서 {i} 점수: {score:.3f}, 내용({len(content)}): {short_content}")
                    short_metadata = {k: v for k, v in metadata.items() if k in ["sector_code", "sector_name", "document_date", "provider_code", "file_name", "page", "keywords"]}
                    logger.info(f"문서 {i} 메타데이터: {short_metadata}")
                    logger.info(f"---------------------------------------------------------------")
                
                # 내용 기반 중복 제거 (문서 일부가 중복되는 경우가 많음)
                content_hash = hash(content[:100])  # 앞부분을 기준으로
                if content_hash in seen_contents:
                    continue
                seen_contents.add(content_hash)
                
                # 결과 정보 구성
                report_info:IndustryReportData = {
                    "content": content,
                    "score": score,
                    "source": metadata.get("provider_code", "미상"),
                    "publish_date": self._format_date(metadata.get("document_date", "")),
                    "file_name": metadata.get("file_name", ""),
                    "page": metadata.get("page", 0),
                    "stock_code": metadata.get("stock_code", ""),
                    "stock_name": metadata.get("stock_name", ""),
                    "keyword_list": metadata.get("keywords", ""),
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
            date_str: 날짜 문자열 (예: "20230101")
            
        Returns:
            형식화된 날짜 문자열 (예: "2023-01-01")
        """
        if not date_str or len(date_str) != 8:
            return date_str
        
        try:
            year = date_str[:4]
            month = date_str[4:6]
            day = date_str[6:8]
            return f"{year}-{month}-{day}"
        except:
            return date_str
        
    def _get_dummy_sector(self, stock_name: str) -> str:
        """종목명으로부터 더미 산업/섹터 정보를 반환합니다.

        Args:
            stock_name: 종목명

        Returns:
            str: 더미 산업/섹터 정보
        """
        # 실제로는 DB나 API를 통해 산업 정보를 조회해야 함
        sectors = {
            "삼성전자": "전자/반도체",
            "SK하이닉스": "반도체",
            "네이버": "인터넷/플랫폼",
            "카카오": "인터넷/플랫폼",
            "현대차": "자동차",
            "기아": "자동차",
            "LG화학": "화학/배터리",
            "삼성바이오로직스": "바이오/제약",
            "셀트리온": "바이오/제약",
            "POSCO홀딩스": "철강/금속"
        }
        
        return sectors.get(stock_name, "IT/소프트웨어")  # 기본값

    
    def _process_reports(self, reports: List[IndustryReportData]) -> List[IndustryReportData]:
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
    
    async def _analyze_industry_data(self, 
                                    industry_data: List[IndustryReportData],
                                    query: str,
                                    sector_name: str,
                                    stock_code: str,
                                    stock_name: str,
                                    classification: Dict[str, Any],
                                    detail_level: str) -> Dict[str, Any]:
        """
        산업 데이터에 대한 분석을 수행합니다.
        
        Args:
            industry_data: 산업 데이터
            query: 사용자 쿼리
            sector_name: 산업/섹터명
            stock_code: 종목코드
            stock_name: 종목명
            classification: 질문 분류 정보
            detail_level: 분석 세부 수준
            
        Returns:
            분석 결과
        """
        try:
           # 필요가 없는데.
            # 상세 분석일 경우 - LLM을 통한 분석 수행
            # 프롬프트 생성
            prompt = PromptTemplate(
                template=INDUSTRY_ANALYSIS_PROMPT,
                input_variables=["industry_data", "query", "stock_name", "stock_code", "sector", "classification"]
            )
            
            # 프롬프트 포맷팅
            formatted_prompt = prompt.format(
                industry_data=industry_data,
                query=query,
                stock_name=stock_name,
                stock_code=stock_code,
                sector=sector_name,
                classification=classification
            )
            
            # LLM 호출
            analysis_result = await self.agent_llm.ainvoke_with_fallback(
                input=[HumanMessage(content=formatted_prompt)],
                user_id=None,  # 상태 객체에서 유저 ID를 전달받아야 함
                project_type=ProjectType.STOCKEASY,
                db=self.db
            )
            
            # 응답을 JSON으로 파싱
            try:
                # JSON 응답 파싱 시도
                import json
                from json import JSONDecodeError
                
                # 문자열 응답 추출
                response_content = analysis_result.content
                
                # JSON 파싱
                analysis_json = json.loads(response_content)
                return analysis_json
            except JSONDecodeError:
                # JSON 파싱 실패 시 텍스트 응답 반환
                return {
                    "summary": analysis_result.content,
                    "format_error": "JSON 변환에 실패했습니다."
                }
            
        except Exception as e:
            logger.error(f"산업 데이터 분석 중 오류 발생: {str(e)}")
            return {
                "summary": "산업 데이터 분석 중 오류가 발생했습니다.",
                "error": str(e)
            }

    def _merge_and_remove_duplicates(self, data1: List[IndustryReportData], data2: List[IndustryReportData]) -> List[IndustryReportData]:
        """
        두 검색 결과를 병합하고 중복을 제거합니다.
        
        Args:
            data1: 첫 번째 검색 결과 리스트
            data2: 두 번째 검색 결과 리스트
            
        Returns:
            중복이 제거된 병합 리스트
        """
        # 내용 기준으로 중복 확인을 위한 해시 집합
        content_hashes = set()
        merged_results = []
        
        # 첫 번째 데이터 추가
        for item in data1:
            # 내용 기반 해시 생성 (앞부분 100자 기준)
            content = item.get("content", "")
            content_hash = hash(content[:100])
            
            if content_hash not in content_hashes:
                content_hashes.add(content_hash)
                merged_results.append(item)
        
        # 두 번째 데이터에서 중복되지 않는 항목만 추가
        for item in data2:
            content = item.get("content", "")
            content_hash = hash(content[:100])
            
            if content_hash not in content_hashes:
                content_hashes.add(content_hash)
                merged_results.append(item)
        
        # 스코어 기준 정렬
        merged_results.sort(key=lambda x: x.get("score", 0), reverse=True)
        
        return merged_results 