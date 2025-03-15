"""
기업리포트 분석 에이전트

이 모듈은 파인콘 DB에서 기업리포트를 검색하고 분석하는 에이전트를 정의합니다.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import re
from loguru import logger
import asyncio

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from stockeasy.agents.base import BaseAgent
from stockeasy.models.agent_io import AgentState, RetrievedMessage
from stockeasy.prompts.report_prompts import (
    REPORT_SEARCH_PROMPT, 
    REPORT_ANALYSIS_PROMPT, 
    INVESTMENT_OPINION_PROMPT,
    format_report_contents,
    format_investment_opinions
)
from common.core.config import settings
from common.services.vector_store_manager import VectorStoreManager
from common.services.retrievers.semantic import SemanticRetriever, SemanticRetrieverConfig
from common.services.retrievers.models import RetrievalResult
from common.utils.util import async_retry


class ReportAnalyzerAgent(BaseAgent):
    """기업리포트 검색 및 분석 에이전트"""
    
    def __init__(self):
        """에이전트 초기화"""
        super().__init__("report_analyzer")
        self.llm = ChatOpenAI(
            model=settings.OPENAI_MODEL_NAME,
            temperature=0.0,
            api_key=settings.OPENAI_API_KEY
        )
        self.parser = StrOutputParser()
        self.embedding_model_type = "openai:text-embedding-3-small"
        self.namespace = settings.PINECONE_NAMESPACE_STOCKEASY_REPORT
    
    async def process(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        기업리포트 검색 및 분석
        
        Args:
            state: 현재 상태 (query, stock_code, stock_name, classification 등 포함)
            
        Returns:
            업데이트된 상태 (report_data 추가)
        """
        try:
            query = state.get("query", "")
            stock_code = state.get("stock_code")
            stock_name = state.get("stock_name")
            classification = state.get("classification", {})
            
            if not query:
                return {
                    **state,
                    "errors": state.get("errors", []) + [{
                        "agent": self.get_name(),
                        "error": "검색 쿼리가 제공되지 않았습니다.",
                        "type": "InvalidInputError",
                        "timestamp": datetime.now()
                    }],
                    "processing_status": {
                        **state.get("processing_status", {}),
                        "report_analyzer": "error"
                    }
                }
            
            # 검색 요청 생성
            search_query = self._make_search_query(query, stock_code, stock_name, classification)
            
            # 검색 매개변수 설정
            k = self._get_report_count(classification)
            threshold = self._calculate_dynamic_threshold(classification)
            metadata_filter = self._create_metadata_filter(stock_code, stock_name, classification)
            
            # 기업리포트 검색
            reports = await self._search_reports(
                search_query, 
                k=k,
                threshold=threshold,
                metadata_filter=metadata_filter
            )
            
            # 검색된 리포트가 없을 경우
            if not reports:
                logger.info(f"기업리포트 검색 결과가 없습니다. 쿼리: {query}")
                return {
                    **state,
                    "report_data": [],
                    "processing_status": {
                        **state.get("processing_status", {}),
                        "report_analyzer": "completed_no_data"
                    }
                }
            
            # 검색 결과 가공
            processed_reports = self._process_reports(reports)
            
            # 질문 주제가 전망(1)이거나 답변 수준이 높은 경우 추가 분석 수행
            question_type = classification.get("질문주제", 4)
            answer_level = classification.get("답변수준", 1)
            
            if question_type == 1 or answer_level >= 2:
                # 리포트 내용에서 핵심 정보 추출 및 분석
                try:
                    analysis = await self._generate_report_analysis(
                        processed_reports, 
                        query, 
                        stock_code, 
                        stock_name
                    )
                    # 분석 결과 추가
                    for i, report in enumerate(processed_reports):
                        if i < len(analysis) and analysis[i]:
                            report.update(analysis[i])
                except Exception as analysis_error:
                    logger.error(f"기업리포트 추가 분석 중 오류: {analysis_error}", exc_info=True)
                    # 추가 분석 오류는 전체 처리를 중단하지 않음
            
            # 상태 업데이트
            return {
                **state,
                "report_data": processed_reports,
                "processing_status": {
                    **state.get("processing_status", {}),
                    "report_analyzer": "completed"
                }
            }
            
        except Exception as e:
            logger.error(f"기업리포트 분석 중 오류 발생: {e}", exc_info=True)
            return {
                **state,
                "errors": state.get("errors", []) + [{
                    "agent": self.get_name(),
                    "error": str(e),
                    "type": type(e).__name__,
                    "timestamp": datetime.now()
                }],
                "processing_status": {
                    **state.get("processing_status", {}),
                    "report_analyzer": "error"
                },
                "report_data": []
            }
    
    def _make_search_query(self, query: str, stock_code: Optional[str], 
                          stock_name: Optional[str], classification: Dict[str, Any]) -> str:
        """
        검색 쿼리 생성
        
        Args:
            query: 사용자 쿼리
            stock_code: 종목 코드
            stock_name: 종목명
            classification: 분류 결과
            
        Returns:
            검색 쿼리
        """
        search_query = query
        
        # 종목 정보 추가
        if stock_name:
            if stock_name not in query:
                search_query = f"{stock_name} {search_query}"
        
        # 분류 정보 기반 검색 키워드 추가
        question_type = classification.get("질문주제", 4)
        if question_type == 0:  # 종목 기본 정보
            search_query += " 기본 정보 사업 구조 핵심 지표"
        elif question_type == 1:  # 전망
            search_query += " 전망 목표가 예상 성장"
        elif question_type == 2:  # 재무 분석
            search_query += " 재무제표 실적 매출 영업이익"
        elif question_type == 3:  # 산업 동향
            search_query += " 산업 동향 시장 구조 경쟁사"
        
        return search_query
    
    def _get_report_count(self, classification: Dict[str, Any]) -> int:
        """
        검색할 리포트 수를 결정
        
        Args:
            classification: 분류 결과
            
        Returns:
            검색할 리포트 수
        """
        answer_level = classification.get("답변수준", 1)
        
        if answer_level == 0:  # 간단한 답변
            return 3
        elif answer_level == 1:  # 긴 설명 요구
            return 5
        elif answer_level == 2:  # 종합적 판단
            return 8
        else:  # 전문가 분석
            return 10
    
    def _calculate_dynamic_threshold(self, classification: Dict[str, Any]) -> float:
        """
        분류에 따른 동적 임계값 계산
        
        Args:
            classification: 분류 결과
            
        Returns:
            유사도 임계값
        """
        question_type = classification.get("질문주제", 4)
        
        if question_type == 0:  # 종목 기본 정보
            return 0.7  # 정확한 정보 필요
        elif question_type == 1:  # 전망
            return 0.6  # 전망 관련 정보는 약간 더 포괄적으로
        elif question_type == 2:  # 재무 분석
            return 0.7  # 정확한 재무 정보 필요
        elif question_type == 3:  # 산업 동향
            return 0.5  # 산업 동향은 더 넓게 검색
        else:  # 기타
            return 0.6  # 중간 수준의 임계값
    
    def _create_metadata_filter(self, stock_code: Optional[str], stock_name: Optional[str],
                              classification: Dict[str, Any]) -> Dict[str, Any]:
        """
        메타데이터 필터 생성
        
        Args:
            stock_code: 종목 코드
            stock_name: 종목명
            classification: 분류 결과
            
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
        sector_name = classification.get("산업분류")
        if sector_name and not stock_code and not stock_name:
            metadata_filter["sector_name"] = {"$eq": sector_name}
        
        # 시간 범위가 있으면 해당 기간으로 제한
        time_range = classification.get("시간범위", "")
        if time_range:
            date_filter = self._parse_time_range(time_range)
            if date_filter:
                metadata_filter["document_date"] = date_filter
        
        return metadata_filter
    
    def _parse_time_range(self, time_range: str) -> Optional[Dict[str, str]]:
        """
        시간 범위 문자열을 파싱하여 날짜 필터 생성
        
        Args:
            time_range: 시간 범위 문자열 (예: "2022년", "최근", "1분기")
            
        Returns:
            날짜 필터 딕셔너리 또는 None
        """
        today = datetime.now()
        
        # 최근 키워드 처리
        if "최근" in time_range or "지난" in time_range:
            # 최근 3개월
            three_months_ago = (today - timedelta(days=90)).strftime("%Y%m%d")
            return {"$gte": three_months_ago}
        
        # 올해 키워드 처리
        if "올해" in time_range or "이번" in time_range:
            year_start = today.replace(month=1, day=1).strftime("%Y%m%d")
            return {"$gte": year_start}
        
        # 작년 키워드 처리
        if "작년" in time_range or "전년" in time_range:
            last_year = today.year - 1
            year_start = today.replace(year=last_year, month=1, day=1).strftime("%Y%m%d")
            year_end = today.replace(year=last_year, month=12, day=31).strftime("%Y%m%d")
            return {"$gte": year_start, "$lte": year_end}
        
        # 특정 연도 처리
        year_match = re.search(r'(20\d{2})년', time_range)
        if year_match:
            year = year_match.group(1)
            year_start = f"{year}0101"
            year_end = f"{year}1231"
            return {"$gte": year_start, "$lte": year_end}
        
        # 분기 처리 (현재 연도 기준)
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
    
    @async_retry(retries=3, delay=1.0, exceptions=(Exception,))
    async def _search_reports(self, query: str, k: int = 5, threshold: float = 0.7,
                             metadata_filter: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
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
            vs_manager = VectorStoreManager(
                embedding_model_type=self.embedding_model_type,
                project_name="stockeasy",
                namespace=self.namespace
            )
            
            # 검색 설정
            config = SemanticRetrieverConfig(
                min_score=threshold,
                metadata_filter=metadata_filter
            )
            
            semantic_retriever = SemanticRetriever(config=config, vs_manager=vs_manager)
            
            # 검색 실행
            retrieval_result: RetrievalResult = await semantic_retriever.retrieve(
                query=query,
                top_k=k * 2,  # 중복 제거를 위해 여유있게 검색
            )
            
            # 결과가 없으면 빈 리스트 반환
            if not retrieval_result.documents:
                return []
            
            # 결과 처리
            results = []
            seen_contents = set()  # 중복 제거를 위한 집합
            
            for doc in retrieval_result.documents:
                content = doc.page_content
                metadata = doc.metadata
                score = doc.score or 0.0
                
                # 내용 기반 중복 제거 (문서 일부가 중복되는 경우가 많음)
                content_hash = hash(content[:100])  # 앞부분을 기준으로 중복 체크
                if content_hash in seen_contents:
                    continue
                seen_contents.add(content_hash)
                
                # 결과 정보 구성
                report_info = {
                    "content": content,
                    "score": score,
                    "source": metadata.get("report_provider", "미상"),
                    "date": self._format_date(metadata.get("document_date", "")),
                    "file_name": metadata.get("file_name", ""),
                    "page": metadata.get("page", 0),
                    "stock_code": metadata.get("stock_code", ""),
                    "stock_name": metadata.get("stock_name", ""),
                    "sector_name": metadata.get("sector_name", ""),
                    "heading": metadata.get("category", "")
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
    
    def _process_reports(self, reports: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        검색된 리포트 처리
        
        Args:
            reports: 검색된 리포트 목록
            
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
            content: 원본 내용
            
        Returns:
            정제된 내용
        """
        # 연속된 공백 제거
        cleaned = re.sub(r'\s+', ' ', content)
        
        # 페이지 번호 및 푸터 정보 제거
        cleaned = re.sub(r'\b\d+\s*/\s*\d+\b', '', cleaned)
        
        # 특수 문자 정리
        cleaned = re.sub(r'[\u200b\u200c\u200d]', '', cleaned)
        
        return cleaned.strip()
    
    def _extract_title_from_content(self, content: str) -> str:
        """
        내용에서 제목 추출 시도
        
        Args:
            content: 리포트 내용
            
        Returns:
            추출된 제목 또는 기본값
        """
        # 첫 줄이 짧고 특수문자가 없으면 제목으로 간주
        lines = content.split('\n')
        if lines and len(lines[0]) < 100 and not re.search(r'[^\w\s.,:()\[\]\-]', lines[0]):
            return lines[0].strip()
        
        # 기본값 반환
        return "기업리포트 섹션"
    
    async def _generate_report_analysis(self, reports: List[Dict[str, Any]], query: str, 
                                       stock_code: Optional[str] = None, 
                                       stock_name: Optional[str] = None) -> List[Dict[str, Any]]:
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
        analysis_prompt = ChatPromptTemplate.from_template(REPORT_ANALYSIS_PROMPT).partial(
            query=query,
            stock_code=stock_code or "정보 없음",
            stock_name=stock_name or "정보 없음",
            report_contents=formatted_reports
        )
        
        # 2) 투자 의견 및 목표가 추출 프롬프트
        opinion_prompt = ChatPromptTemplate.from_template(INVESTMENT_OPINION_PROMPT).partial(
            stock_code=stock_code or "정보 없음",
            stock_name=stock_name or "정보 없음",
            report_contents=formatted_reports
        )
        
        # 병렬로 분석 실행
        analysis_chain = analysis_prompt | self.llm | self.parser
        opinion_chain = opinion_prompt | self.llm | self.parser
        
        # 병렬 실행
        results = await asyncio.gather(
            analysis_chain.ainvoke({}),
            opinion_chain.ainvoke({}),
            return_exceptions=True
        )
        
        # 결과 처리
        analysis_result = results[0] if not isinstance(results[0], Exception) else ""
        opinion_result = results[1] if not isinstance(results[1], Exception) else ""
        
        # 투자 의견 및 목표가 추출
        investment_opinions = []
        target_prices = []
        
        if opinion_result:
            try:
                # 투자 의견 정보 파싱 시도
                opinion_data = {}
                
                # "투자의견:" 또는 "투자 의견:" 패턴 찾기
                opinion_pattern = r'(투자\s*의견|투자의견)\s*:\s*([^\n,]+)'
                opinion_matches = re.findall(opinion_pattern, opinion_result)
                
                # "목표가:" 또는 "목표 가격:" 패턴 찾기
                price_pattern = r'(목표\s*가격|목표가|목표\s*주가)\s*:\s*([\d,]+)'
                price_matches = re.findall(price_pattern, opinion_result)
                
                for report in reports:
                    source = report["source"]
                    date = report["date"]
                    
                    # 해당 리포트에 대한 투자 의견 찾기
                    report_opinion = None
                    for _, opinion in opinion_matches:
                        if source in opinion_result and date in opinion_result:
                            report_opinion = opinion.strip()
                            break
                    
                    # 해당 리포트에 대한 목표가 찾기
                    report_price = None
                    for _, price in price_matches:
                        if source in opinion_result and date in opinion_result:
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
        report_analyses = []
        for report in reports:
            report_analyses.append({
                "analysis": analysis_result,
                "investment_opinions": investment_opinions,
                "opinion_summary": opinion_result
            })
        
        return report_analyses
    
    async def _generate_report_summary(self, reports: List[Dict[str, Any]], query: str) -> str:
        """
        검색된 리포트의 요약 생성
        
        Args:
            reports: 검색된 리포트 목록
            query: 사용자 쿼리
            
        Returns:
            요약 텍스트
        """
        if not reports:
            return "관련된 기업리포트를 찾을 수 없습니다."
        
        # 요약 프롬프트 생성
        formatted_reports = format_report_contents(reports)
        prompt = ChatPromptTemplate.from_template(REPORT_ANALYSIS_PROMPT).partial(
            query=query,
            stock_code="",
            stock_name="",
            report_contents=formatted_reports
        )
        
        # LLM으로 요약 생성
        chain = prompt | self.llm | self.parser
        summary = await chain.ainvoke({})
        
        return summary 