"""
웹 검색 에이전트 모듈

이 모듈은 사용자 질문과 관련된 최신 정보를 웹에서 검색하는 에이전트 클래스를 구현합니다.
최근 이슈 요약과 사용자 질문을 기반으로 여러 검색 쿼리를 생성하고 결과를 취합합니다.
"""

import asyncio
import csv
import json
import os
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, cast
from urllib.parse import urlparse

from langchain_core.output_parsers import JsonOutputParser
from loguru import logger
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from common.models.token_usage import ProjectType
from common.services.agent_llm import get_agent_llm

# from langchain_tavily import TavilySearch
from common.services.tavily import TavilyService
from common.utils.util import async_retry, remove_json_block
from stockeasy.agents.base import BaseAgent
from stockeasy.models.agent_io import RetrievedAllAgentData, RetrievedWebSearchResult
from stockeasy.services.web_search_cache_service import WebSearchCacheService


class MultiQueryOutput(BaseModel):
    """
    멀티쿼리 생성 결과를 위한 구조화된 출력 포맷
    """

    queries: List[str] = Field(description="사용자 질문을 기반으로 생성된 검색 쿼리 목록 (10-15개)")
    rationale: Optional[str] = Field(default=None, description="쿼리 선택 및 생성에 대한 설명 (선택사항)")


class WebSearchAgent(BaseAgent):
    """웹 검색 에이전트"""

    def __init__(self, name: Optional[str] = None, db: Optional[AsyncSession] = None):
        """
        웹 검색 에이전트 초기화

        Args:
            name: 에이전트 이름 (지정하지 않으면 클래스명 사용)
            db: 데이터베이스 세션 객체 (선택적)
        """
        super().__init__(name, db)
        self.retrieved_str = "web_search_results"
        self.agent_llm = get_agent_llm("web_search_agent")
        self.agent_llm_lite = get_agent_llm("gemini-lite")
        self.parser = JsonOutputParser()

        # self.tavily_search = TavilySearch(api_key=settings.TAVILY_API_KEY)
        self.tavily_service = TavilyService()

        # 최대 쿼리 개수 및 최대 결과 개수 설정
        self.max_queries = 7
        self.max_results_per_query = 15

        # 캐싱 관련 설정 추가
        self.use_cache = True  # 캐싱 기능 활성화 여부
        self.web_search_cache_service = WebSearchCacheService(db) if db else None
        self.similarity_threshold = 0.89  # 유사도 임계값
        self.cache_expiry_days = 15  # 캐시 유효기한 (일)

        # 캐싱 지표
        self.cache_hits = 0
        self.cache_misses = 0

        logger.info(f"WebSearchAgent initialized with provider: {self.agent_llm.get_provider()}, model: {self.agent_llm.get_model_name()}")

    def _clean_search_content(self, content: str) -> str:
        """
        웹 검색 결과 내용에서 마크다운 기호 및 불필요한 포맷팅 문자를 정제합니다.

        Args:
            content: 정제할 원본 텍스트

        Returns:
            정제된 텍스트
        """
        if not content:
            return content

        try:
            original_length = len(content)
            original_markdown_count = content.count("#") + content.count("*") + content.count("|")
            # 1. 마크다운 헤더 제거 (### 제목, #### 소제목 등)
            content = re.sub(r"^#{1,6}\s+", "", content, flags=re.MULTILINE)

            # 2. 마크다운 링크 정리 ([텍스트](URL) -> 텍스트)
            content = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", content)

            # 3. 마크다운 볼드/이탤릭 제거 (**텍스트**, *텍스트*, __텍스트__)
            content = re.sub(r"\*\*([^\*]+)\*\*", r"\1", content)
            content = re.sub(r"\*([^\*]+)\*", r"\1", content)
            content = re.sub(r"__([^_]+)__", r"\1", content)
            content = re.sub(r"_([^_]+)_", r"\1", content)

            # 4. 테이블 구분자 제거 (|  |, | --- |)
            content = re.sub(r"\|\s*\|", "", content)
            content = re.sub(r"\|\s*-+\s*\|", "", content)
            content = re.sub(r"\|\s*([^|]*)\s*\|", r"\1", content)

            # 5. 생략 표시 정리 ([...], […], ...)
            content = re.sub(r"\[\.\.\.\]", "(생략)", content)
            content = re.sub(r"\[…\]", "(생략)", content)
            content = re.sub(r"\.{3,}", "(생략)", content)

            # 6. HTML 태그 제거
            content = re.sub(r"<[^>]+>", "", content)

            # 7. FAQ 형식 정리 (숫자. 질문? -> 질문:)
            content = re.sub(r"(\d+)\.\s*([^?]+)\?\s*", r"\2: ", content)

            # 8. 리스트 형식 정리 (1), (2) -> 1., 2.)
            content = re.sub(r"\((\d+)\)\s*", r"\1. ", content)

            # 9. 특수 문자 조합 정리 (R ​​& D -> R&D)
            content = re.sub(r"R\s*​*\s*&\s*D", "R&D", content)

            # 10. 연속된 공백 정리
            content = re.sub(r"\s+", " ", content)

            # 11. 연속된 줄바꿈 정리
            content = re.sub(r"\n\s*\n", "\n", content)

            # 12. 앞뒤 공백 제거
            content = content.strip()

            return content

        except Exception as e:
            logger.warning(f"텍스트 정제 중 오류 발생: {str(e)}, 원본 텍스트 반환")
            return content

    def _clean_search_title(self, title: str) -> str:
        """
        웹 검색 결과 제목에서 불필요한 문자를 정제합니다.

        Args:
            title: 정제할 원본 제목

        Returns:
            정제된 제목
        """
        if not title:
            return title

        try:
            # 1. HTML 태그 제거
            title = re.sub(r"<[^>]+>", "", title)

            # 2. 특수 문자 정리 (..., [브랜드명] 등)
            title = re.sub(r"\[\.\.\.\]", "", title)
            title = re.sub(r"\[…\]", "", title)
            title = re.sub(r"\.{3,}", "", title)

            # 3. 연속된 공백 정리
            title = re.sub(r"\s+", " ", title)

            # 4. 앞뒤 공백 제거
            title = title.strip()

            return title

        except Exception as e:
            logger.warning(f"제목 정제 중 오류 발생: {str(e)}, 원본 제목 반환")
            return title

    async def process(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        사용자 쿼리와 최근 이슈를 기반으로 웹 검색을 수행합니다.

        Args:
            state: 현재 상태 정보를 포함하는 딕셔너리

        Returns:
            업데이트된 상태 딕셔너리
        """
        try:
            # 성능 측정 시작
            start_time = datetime.now()
            logger.info("WebSearchAgent starting processing")

            # 상태 업데이트 - 콜백 함수 사용
            if "update_processing_status" in state and "agent_name" in state:
                state["update_processing_status"](state["agent_name"], "processing")
            else:
                # 기존 방식으로 상태 업데이트 (콜백 함수가 없는 경우)
                state["processing_status"] = state.get("processing_status", {})
                state["processing_status"]["web_search"] = "processing"

            # 현재 쿼리 및 세션 정보 추출
            query = state.get("query", "")

            # 질문 분석 결과 추출 (새로운 구조)
            question_analysis = state.get("question_analysis", {})
            entities = question_analysis.get("entities", {})
            classification = question_analysis.get("classification", {})
            question_analysis.get("data_requirements", {})
            question_analysis.get("keywords", [])
            question_analysis.get("detail_level", "보통")

            # 엔티티에서 종목 정보 추출
            stock_code = entities.get("stock_code", state.get("stock_code"))
            stock_name = entities.get("stock_name", state.get("stock_name"))
            entities.get("sector", "")

            # 최근 이슈 요약 추출 (없을 경우 빈 문자열)
            state.get("recent_issues_summary", "")
            final_report_toc = state.get("final_report_toc", {})
            if not query:
                logger.warning("Empty query provided to WebSearchAgent")
                self._add_error(state, "검색 쿼리가 제공되지 않았습니다.")

                # 상태 업데이트 - 콜백 함수 사용
                if "update_processing_status" in state and "agent_name" in state:
                    state["update_processing_status"](state["agent_name"], "error")
                else:
                    # 기존 방식으로 상태 업데이트 (콜백 함수가 없는 경우)
                    state["processing_status"] = state.get("processing_status", {})
                    state["processing_status"]["web_search"] = "error"

                return state

            logger.info(f"WebSearchAgent processing query: {query}")

            # 멀티 쿼리 생성
            search_queries = await self._generate_search_queries(
                query=query, stock_code=stock_code, stock_name=stock_name, max_queries=self.max_queries, final_report_toc=final_report_toc
            )

            if not search_queries:
                logger.warning("No search queries generated")
                self._add_error(state, "검색 쿼리를 생성할 수 없습니다.")
                return self._handle_error_response(state, start_time, "검색 쿼리 생성 실패")

            logger.info(f"총 {len(search_queries)}개의 쿼리 생성됨: {search_queries}")

            # 멀티 쿼리 CSV 저장
            await self._save_queries_to_csv(query=query, stock_code=stock_code, stock_name=stock_name, search_queries=search_queries)

            # 웹 검색 수행 (캐싱 기능 사용)
            search_results = await self._perform_web_searches(search_queries=search_queries, stock_code=stock_code, stock_name=stock_name)
            logger.info(f"웹 검색결과: {len(search_results)}개")

            if not search_results:
                logger.warning("No web search results found")
                return self._handle_no_results_response(state, start_time)

            # 웹 검색 결과 JSON 저장 (정제 전 원본 저장)
            await self._save_search_results_to_json(query=query, stock_code=stock_code, stock_name=stock_name, search_queries=search_queries, search_results=search_results)

            # 검색 결과 요약(요약하지 않고, 검색 결과 병합)
            summary = await self._summarize_search_results(query, stock_code, stock_name, search_results, classification)

            # 수행 시간 계산
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()

            # processed_result = {
            #             "title": result_item.get("title", "제목 없음"),
            #             "content": result_item.get("content", "내용 없음"),
            #             "url": result_item.get("url", "링크 없음"),
            #             "search_query": query,
            #         }
            # 결과 형태 설정 (정제된 내용 사용)
            processed_results = []
            cleaned_count = 0
            for result in search_results:
                # 제목과 내용 정제
                original_title = result.get("title", "")
                original_content = result.get("content", "")
                clean_title = self._clean_search_title(original_title)
                clean_content = self._clean_search_content(original_content)

                # 정제 효과 확인
                if (original_title != clean_title) or (original_content != clean_content):
                    cleaned_count += 1

                processed_result: RetrievedWebSearchResult = {
                    "title": clean_title,
                    "content": clean_content,
                    "url": result.get("url", ""),
                    "search_query": result.get("search_query", ""),
                    "search_date": datetime.now(),
                }
                processed_results.append(processed_result)

            if cleaned_count > 0:
                logger.info(f"웹 검색 결과 정제 완료: 전체 {len(search_results)}개 중 {cleaned_count}개 정제됨")

            # 새로운 구조로 상태 업데이트
            agent_result = {
                "agent_name": "web_search",
                "status": "success",
                "data": {"summary": summary, "results": processed_results},
                "error": None,
                "execution_time": duration,
                "metadata": {"result_count": len(processed_results), "queries": search_queries},
            }

            # 콜백 함수를 통한 상태 업데이트
            if "update_agent_results" in state:
                state["update_agent_results"]("web_search", agent_result)
            else:
                # 기존 방식으로 상태 업데이트 (콜백 함수가 없는 경우)
                state["agent_results"] = state.get("agent_results", {})
                state["agent_results"]["web_search"] = agent_result

            # 검색 데이터 업데이트
            retrieved_data_result = {"summary": summary, "results": processed_results}

            if "update_retrieved_data" in state:
                state["update_retrieved_data"](self.retrieved_str, retrieved_data_result)
            else:
                # 기존 방식으로 상태 업데이트 (콜백 함수가 없는 경우)
                if "retrieved_data" not in state:
                    state["retrieved_data"] = {}
                retrieved_data = cast(RetrievedAllAgentData, state["retrieved_data"])
                retrieved_data[self.retrieved_str] = retrieved_data_result

            # 상태 업데이트 - 콜백 함수 사용
            if "update_processing_status" in state and "agent_name" in state:
                state["update_processing_status"](state["agent_name"], "completed")
            else:
                # 기존 방식으로 상태 업데이트 (콜백 함수가 없는 경우)
                state["processing_status"] = state.get("processing_status", {})
                state["processing_status"]["web_search"] = "completed"

            # 메트릭 업데이트
            metrics_result = {
                "start_time": start_time,
                "end_time": end_time,
                "duration": duration,
                "status": "completed",
                "error": None,
                "model_name": self.agent_llm.get_model_name(),
                "cache_hits": self.cache_hits,
                "cache_misses": self.cache_misses,
                "cache_hit_ratio": round(self.cache_hits / (self.cache_hits + self.cache_misses), 2) if (self.cache_hits + self.cache_misses) > 0 else 0,
            }

            if "update_metrics" in state:
                state["update_metrics"]("web_search", metrics_result)
            else:
                # 기존 방식으로 상태 업데이트 (콜백 함수가 없는 경우)
                state["metrics"] = state.get("metrics", {})
                state["metrics"]["web_search"] = metrics_result

            logger.info(f"WebSearchAgent completed in {duration:.2f} seconds, found {len(processed_results)} results")
            return state

        except Exception as e:
            logger.exception(f"Error in WebSearchAgent: {str(e)}")
            return self._handle_error_response(state, start_time, str(e))

    def _filter_technical_analysis_from_toc(self, toc: Dict[str, Any]) -> Dict[str, Any]:
        """
        목차에서 기술적 분석 관련 섹션을 제거합니다.

        Args:
            toc: 원본 목차 딕셔너리

        Returns:
            기술적 분석 섹션이 제거된 목차 딕셔너리
        """
        if not toc:
            return toc

        # 기술적 분석 관련 키워드들
        # technical_keywords = ["기술적", "기술", "technical", "chart", "차트", "지표", "indicator", "분석", "analysis", "시세", "봉차트", "캔들", "이동평균", "rsi", "macd"]
        technical_keywords = ["기술적 분석", "기술적분석"]

        def should_exclude_key(key: str) -> bool:
            """키가 기술적 분석 관련인지 확인"""
            key_lower = key.lower()
            return any(keyword in key_lower for keyword in technical_keywords)

        def filter_dict_recursive(data: Dict[str, Any]) -> Dict[str, Any]:
            """재귀적으로 딕셔너리에서 기술적 분석 관련 항목 제거"""
            filtered = {}

            for key, value in data.items():
                # 키 자체가 기술적 분석 관련이면 제외
                if should_exclude_key(key):
                    continue

                # 값이 딕셔너리면 재귀적으로 필터링
                if isinstance(value, dict):
                    filtered_value = filter_dict_recursive(value)
                    # 필터링 후 빈 딕셔너리가 아니면 추가
                    if filtered_value:
                        filtered[key] = filtered_value
                # 값이 리스트면 각 항목 확인
                elif isinstance(value, list):
                    filtered_list = []
                    for item in value:
                        if isinstance(item, dict):
                            filtered_item = filter_dict_recursive(item)
                            if filtered_item:
                                filtered_list.append(filtered_item)
                        elif isinstance(item, str):
                            if not should_exclude_key(item):
                                filtered_list.append(item)
                        else:
                            filtered_list.append(item)

                    if filtered_list:
                        filtered[key] = filtered_list
                # 문자열이면 기술적 분석 관련 확인
                elif isinstance(value, str):
                    if not should_exclude_key(value):
                        filtered[key] = value
                else:
                    # 다른 타입은 그대로 유지
                    filtered[key] = value

            return filtered

        try:
            return filter_dict_recursive(toc)
        except Exception as e:
            logger.warning(f"목차 필터링 중 오류 발생: {str(e)}, 원본 목차 사용")
            return toc

    async def _generate_search_queries(self, query: str, stock_code: Optional[str], stock_name: Optional[str], max_queries: int, final_report_toc: Dict[str, Any]) -> List[str]:
        """
        사용자 쿼리와 문서 최종 목차를 기반으로 여러 검색 쿼리를 생성합니다.

        Args:
            query: 원본 사용자 쿼리
            stock_code: 종목 코드
            stock_name: 종목 이름
            final_report_toc: 문서 최종 목차

        Returns:
            생성된 검색 쿼리 목록
        """
        # 종목 정보 유무 확인 (일반 질문 vs 주식 관련 질문)
        is_stock_related = bool(stock_code and stock_code.strip()) or bool(stock_name and stock_name.strip())

        try:
            if is_stock_related:
                # 주식 관련 질문용 프롬프트
                logger.info(f"종목 관련 질문으로 판단: stock_code={stock_code}, stock_name={stock_name}")
                prompt = await self._create_stock_related_prompt(query, stock_code, stock_name, final_report_toc)
            else:
                # 일반 질문용 프롬프트
                logger.info(f"일반 질문으로 판단: stock_code={stock_code}, stock_name={stock_name}")
                prompt = await self._create_general_prompt(query, final_report_toc)

            # LLM 호출
            response = await self.agent_llm_lite.ainvoke_with_fallback(input=prompt, project_type=ProjectType.STOCKEASY, db=self.db)

            # 응답 파싱
            content = response.content.strip()
            content = remove_json_block(content)

            # JSON 부분만 추출 (프롬프트 무시 방지)
            json_match = re.search(r"({.*})", content, re.DOTALL)
            if json_match:
                content = json_match.group(1)

            # JSON 파싱
            try:
                result = json.loads(content)
                search_queries = result.get("search_queries", [])

                # 최대 쿼리 개수 제한
                return search_queries[: self.max_queries]
            except json.JSONDecodeError:
                # JSON 파싱 실패 시 텍스트에서 쿼리 추출 시도
                queries = []
                for line in content.split("\n"):
                    if line.strip() and not line.startswith("{") and not line.endswith("}"):
                        queries.append(line.strip().strip('"').strip("'"))
                        if len(queries) >= self.max_queries:
                            break

                if queries:
                    return queries

                # 모든 방법 실패 시 기본 쿼리 생성
                default_query = f"{stock_name if stock_name else ''} {query}".strip()
                return [default_query]

        except Exception as e:
            logger.error(f"Error generating search queries: {str(e)}", exc_info=True)
            # 오류 발생 시 기본 쿼리 생성
            if is_stock_related:
                default_query = f"{stock_name if stock_name else ''} {query}".strip()
            else:
                default_query = query.strip()
            return [default_query]

    async def _create_stock_related_prompt(self, query: str, stock_code: Optional[str], stock_name: Optional[str], final_report_toc: Dict[str, Any]) -> str:
        """
        주식 관련 질문을 위한 프롬프트를 생성합니다.

        Args:
            query: 원본 사용자 쿼리
            stock_code: 종목 코드
            stock_name: 종목 이름
            final_report_toc: 문서 최종 목차

        Returns:
            주식 관련 검색 쿼리 생성용 프롬프트
        """
        # 기술적 분석 섹션을 제거한 새로운 목차 생성
        filtered_toc = self._filter_technical_analysis_from_toc(final_report_toc)

        return f"""
당신은 주식 및 금융 정보 검색 전문가입니다. 사용자의 질문과 주식 정보를 분석하여 효과적인 웹 검색 쿼리를 생성해주세요.

사용자 질문: {query}

관련 주식 정보:
- 종목 코드: {stock_code if stock_code else "없음"}
- 종목명: {stock_name if stock_name else "없음"}

문서 최종 목차:
{json.dumps(filtered_toc, ensure_ascii=False, indent=2) if filtered_toc else "목차 정보가 없습니다."}

검색 쿼리를 생성할 때 다음 사항을 고려하세요:
1. **문서 최종 목차 활용**: 목차에 있는 각 섹션과 주제를 참고하여 관련 검색 쿼리를 생성하세요.
   - 각 목차 항목은 중요한 정보 영역을 나타내므로, 이에 맞춰 검색 쿼리를 설계하세요.
   - 특히 "주요 이슈", "산업 동향", "경쟁사 현황"과 같은 섹션을 중점적으로 참고하세요.

2. **종합적인 검색 전략**:
   - 주식 기본 정보, 최근 재무 실적, 시장 트렌드, 경쟁사 분석 등 다양한 측면을 다루는 쿼리를 생성하세요.
   - 각 쿼리는 목차의 서로 다른 섹션에 대응되도록 하여 포괄적인 정보 수집이 가능하게 하세요.

3. **쿼리 구성 요소**:
   - 쿼리는 구체적이고, 명확하며, 검색 가능한 형태로 작성되어야 합니다.
   - 관련 키워드, 개체명, 숫자, 최근 이벤트 등 검색에 유용한 요소를 포함하세요.
   - 종목명과 코드를 적절히 활용하되, 너무 많은 키워드를 한 쿼리에 포함하지 마세요.

4. **최대 {self.max_queries}개의 검색 쿼리**를 생성해주세요.

# 아래와 관련된 검색 쿼리는 반드시 제외하세요.
- ESG 경영 평가
- 재무데이터
- 주가전망

# 출력 형식: JSON
검색 쿼리 목록만 반환하세요. 다음 형식으로 JSON을 반환하세요:
{{
  "search_queries": ["쿼리1", "쿼리2", "쿼리3"]
}}
"""

    async def _create_general_prompt(self, query: str, final_report_toc: Dict[str, Any]) -> str:
        """
        일반 질문을 위한 프롬프트를 생성합니다.

        Args:
            query: 원본 사용자 쿼리
            final_report_toc: 문서 최종 목차

        Returns:
            일반 검색 쿼리 생성용 프롬프트
        """
        return f"""
당신은 정보 검색 전문가입니다. 사용자의 질문을 분석하여 효과적인 웹 검색 쿼리를 생성해주세요.

사용자 질문: {query}

문서 목차 (참고용):
{json.dumps(final_report_toc, ensure_ascii=False, indent=2) if final_report_toc else "목차 정보가 없습니다."}

검색 쿼리를 생성할 때 다음 사항을 고려하세요:
1. **질문 의도 파악**: 사용자가 원하는 정보가 무엇인지 명확히 파악하여 관련 검색 쿼리를 생성하세요.
   - 핵심 키워드를 추출하고, 동의어나 관련 용어도 포함하세요.
   - 질문의 맥락과 배경을 고려한 검색 쿼리를 설계하세요.

2. **다각도 검색 전략**:
   - 기본 정보, 정의, 특징, 동향, 최신 뉴스 등 다양한 관점에서 접근하는 쿼리를 생성하세요.
   - 주제와 관련된 여러 측면을 다루는 포괄적인 검색이 가능하도록 하세요.

3. **쿼리 구성 요소**:
   - 쿼리는 구체적이고, 명확하며, 검색 가능한 형태로 작성되어야 합니다.
   - 관련 키워드, 전문용어, 최신 이벤트 등 검색에 유용한 요소를 포함하세요.
   - 너무 복잡하지 않으면서도 정확한 결과를 얻을 수 있는 쿼리를 만드세요.

4. **최대 {self.max_queries}개의 검색 쿼리**를 생성해주세요.

# 출력 형식: JSON
검색 쿼리 목록만 반환하세요. 다음 형식으로 JSON을 반환하세요:
{{
  "search_queries": ["쿼리1", "쿼리2", "쿼리3"]
}}
"""

    @async_retry(retries=0, delay=1.0, exceptions=(Exception,))
    async def _perform_web_searches(self, search_queries: List[str], stock_code: Optional[str] = None, stock_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        생성된 쿼리를 사용하여 웹 검색을 수행합니다. 캐시를 먼저 확인하고 없는 경우 API를 호출합니다.

        Args:
            search_queries: 검색할 쿼리 목록
            stock_code: 종목 코드
            stock_name: 종목 이름

        Returns:
            검색 결과 목록
        """
        try:
            all_results = []

            if self.use_cache and self.web_search_cache_service and self.db:
                # 캐시 검색
                logger.info(f"캐시에서 {len(search_queries)}개 쿼리 검색 시도")
                cache_results, cache_miss_queries = await self.web_search_cache_service.check_cache(queries=search_queries, stock_code=stock_code, stock_name=stock_name)

                # 캐시 히트 결과 추가
                if cache_results:
                    all_results.extend(cache_results)
                    self.cache_hits += len(search_queries) - len(cache_miss_queries)
                    logger.info(f"캐시 히트: {len(search_queries) - len(cache_miss_queries)}개 쿼리")

                # 캐시 미스 쿼리만 API 호출
                if cache_miss_queries:
                    self.cache_misses += len(cache_miss_queries)
                    logger.info(f"캐시 미스: {len(cache_miss_queries)}개 쿼리, API 호출")
                    api_results = await self.tavily_service.batch_search_async(
                        queries=cache_miss_queries, search_depth="advanced", max_results=self.max_results_per_query, topic="general", time_range="year"
                    )

                    # 결과 추가
                    all_results.extend(api_results)

                    # 결과 캐싱
                    for query in cache_miss_queries:
                        query_results = [r for r in api_results if r.get("search_query") == query]
                        if query_results:
                            # 캐시에 저장
                            await self.web_search_cache_service.save_to_cache(query=query, results=query_results, stock_code=stock_code, stock_name=stock_name)
            else:
                # 캐시 사용하지 않고 모든 쿼리 API 호출
                logger.info(f"캐싱 비활성화 또는 DB 연결 없음: 직접 API 호출 ({len(search_queries)}개 쿼리)")
                all_results = await self.tavily_service.batch_search_async(
                    queries=search_queries, search_depth="advanced", max_results=self.max_results_per_query, topic="general", time_range="year"
                )

            return all_results

        except Exception as e:
            logger.error(f"웹 검색 수행 중 오류 발생: {str(e)}", exc_info=True)
            return []

    def _remove_duplicates(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        검색 결과에서 중복을 제거합니다.

        Args:
            results: 검색 결과 목록

        Returns:
            중복이 제거된 검색 결과 목록
        """
        # URL 기반으로 중복 제거
        seen_urls = set()
        unique_results = []

        for result in results:
            url = result.get("url", "")
            if url and url not in seen_urls:
                seen_urls.add(url)
                unique_results.append(result)

        return unique_results

    def _score_results(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        검색 결과의 관련성 점수를 계산하고 정렬합니다.

        Args:
            results: 검색 결과 목록

        Returns:
            관련성 점수가 부여되고 정렬된 검색 결과 목록
        """
        # 간단한 휴리스틱 점수 계산
        for result in results:
            # 기본 점수
            score = 1.0

            # 제목 및 내용의 길이에 따른 점수 조정
            title_length = len(result.get("title", ""))
            content_length = len(result.get("content", ""))

            if title_length > 0:
                score += min(0.2, title_length / 100)

            if content_length > 100:
                score += 0.3
            elif content_length > 50:
                score += 0.1

            # 메타데이터 기반 점수 조정
            metadata = result.get("metadata", {})
            position = metadata.get("position", 999)

            # 검색 결과 위치에 따른 점수 조정
            if position <= 3:
                score += 0.5
            elif position <= 5:
                score += 0.3
            elif position <= 10:
                score += 0.1

            # 최종 점수 저장
            result["relevance_score"] = round(score, 2)

        # 점수에 따라 정렬
        scored_results = sorted(results, key=lambda x: x.get("relevance_score", 0), reverse=True)

        return scored_results

    @async_retry(retries=1, delay=1.0, exceptions=(Exception,))
    async def _summarize_search_results(
        self, query: str, stock_code: Optional[str], stock_name: Optional[str], search_results: List[Dict[str, Any]], classification: Dict[str, Any]
    ) -> str:
        """
        검색 결과를 요약합니다.

        Args:
            query: 원본 사용자 쿼리
            stock_code: 종목 코드
            stock_name: 종목 이름
            search_results: 검색 결과 목록
            classification: 질문 분류 정보

        Returns:
            요약된 내용
        """
        try:
            if not search_results:
                return "관련된 검색 결과를 찾을 수 없습니다."

            # 상위 결과만 사용
            top_results = search_results

            # 포맷팅
            formatted_results = []
            seen_urls = set()  # 중복 URL 추적을 위한 set 추가
            for i, result in enumerate(top_results, 1):
                title = result.get("title", "제목 없음")
                content = result.get("content", "내용 없음")
                url = result.get("url", "URL 없음")

                # 제목과 내용 정제
                clean_title = self._clean_search_title(title)
                clean_content = self._clean_search_content(content)

                if url and url not in seen_urls:  # URL이 있고, 아직 처리되지 않은 경우
                    formatted_results.append(f"제목: {clean_title}")
                    domain_name = self._extract_domain_name(url)
                    formatted_results.append(f"출처: {domain_name}")
                    formatted_results.append(f"URL: {url}")
                    formatted_results.append(f"내용: {clean_content}")
                    formatted_results.append("---[검색결과 구분선]---")  # LLM이 명확히 인식할 수 있는 구분자
                    seen_urls.add(url)  # 처리된 URL로 추가

            # 검색 결과 텍스트
            results_text = "\n".join(formatted_results)
            return results_text

        except Exception as e:
            error_msg = f"검색 결과 요약 중 오류 발생: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return "검색 결과 요약 중 오류가 발생했습니다. 관련 정보를 찾지 못했습니다."

    def _add_error(self, state: Dict[str, Any], error_message: str) -> None:
        """
        상태 객체에 오류 정보를 추가합니다.

        Args:
            state: 상태 객체
            error_message: 오류 메시지
        """
        state["errors"] = state.get("errors", [])
        state["errors"].append(
            {"agent": "web_search", "error": error_message, "type": "processing_error", "timestamp": datetime.now(), "context": {"query": state.get("query", "")}}
        )

    def _handle_error_response(self, state: Dict[str, Any], start_time: datetime, error_message: str) -> Dict[str, Any]:
        """
        오류 응답을 처리합니다.

        Args:
            state: 상태 딕셔너리
            start_time: 시작 시간
            error_message: 오류 메시지

        Returns:
            업데이트된 상태 딕셔너리
        """
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        # 상태 업데이트 - 콜백 함수 사용
        if "update_processing_status" in state and "agent_name" in state:
            state["update_processing_status"](state["agent_name"], "error")
        else:
            # 기존 방식으로 상태 업데이트 (콜백 함수가 없는 경우)
            state["processing_status"] = state.get("processing_status", {})
            state["processing_status"]["web_search"] = "error"

        # 오류 추가
        self._add_error(state, f"웹 검색 에이전트 오류: {error_message}")

        # 오류 상태 업데이트
        agent_result = {"agent_name": "web_search", "status": "failed", "data": [], "error": error_message, "execution_time": duration, "metadata": {}}

        if "update_agent_results" in state:
            state["update_agent_results"]("web_search", agent_result)
        else:
            # 기존 방식으로 상태 업데이트 (콜백 함수가 없는 경우)
            state["agent_results"] = state.get("agent_results", {})
            state["agent_results"]["web_search"] = agent_result

        # 검색 데이터 업데이트
        retrieved_data_result = {"summary": "", "results": []}

        if "update_retrieved_data" in state:
            state["update_retrieved_data"](self.retrieved_str, retrieved_data_result)
        else:
            # 기존 방식으로 상태 업데이트 (콜백 함수가 없는 경우)
            if "retrieved_data" not in state:
                state["retrieved_data"] = {}
            retrieved_data = cast(RetrievedAllAgentData, state["retrieved_data"])
            retrieved_data[self.retrieved_str] = retrieved_data_result

        # 메트릭 업데이트
        metrics_result = {
            "start_time": start_time,
            "end_time": end_time,
            "duration": duration,
            "status": "error",
            "error": error_message,
            "model_name": self.agent_llm.get_model_name(),
        }

        if "update_metrics" in state:
            state["update_metrics"]("web_search", metrics_result)
        else:
            # 기존 방식으로 상태 업데이트 (콜백 함수가 없는 경우)
            state["metrics"] = state.get("metrics", {})
            state["metrics"]["web_search"] = metrics_result

        return state

    def _handle_no_results_response(self, state: Dict[str, Any], start_time: datetime) -> Dict[str, Any]:
        """
        검색 결과가 없는 경우를 처리합니다.

        Args:
            state: 상태 딕셔너리
            start_time: 시작 시간

        Returns:
            업데이트된 상태 딕셔너리
        """
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        # 상태 업데이트 - 콜백 함수 사용
        if "update_processing_status" in state and "agent_name" in state:
            state["update_processing_status"](state["agent_name"], "completed_no_data")
        else:
            # 기존 방식으로 상태 업데이트 (콜백 함수가 없는 경우)
            state["processing_status"] = state.get("processing_status", {})
            state["processing_status"]["web_search"] = "completed_no_data"

        # 새로운 구조로 상태 업데이트 (결과 없음)
        agent_result = {"agent_name": "web_search", "status": "partial_success", "data": [], "error": None, "execution_time": duration, "metadata": {"result_count": 0}}

        if "update_agent_results" in state:
            state["update_agent_results"]("web_search", agent_result)
        else:
            # 기존 방식으로 상태 업데이트 (콜백 함수가 없는 경우)
            state["agent_results"] = state.get("agent_results", {})
            state["agent_results"]["web_search"] = agent_result

        # 검색 데이터 업데이트
        retrieved_data_result = {"summary": "관련된 검색 결과를 찾을 수 없습니다.", "results": []}

        if "update_retrieved_data" in state:
            state["update_retrieved_data"](self.retrieved_str, retrieved_data_result)
        else:
            # 기존 방식으로 상태 업데이트 (콜백 함수가 없는 경우)
            if "retrieved_data" not in state:
                state["retrieved_data"] = {}
            retrieved_data = cast(RetrievedAllAgentData, state["retrieved_data"])
            retrieved_data[self.retrieved_str] = retrieved_data_result

        # 메트릭 업데이트
        metrics_result = {
            "start_time": start_time,
            "end_time": end_time,
            "duration": duration,
            "status": "completed_no_data",
            "error": None,
            "model_name": self.agent_llm.get_model_name(),
        }

        if "update_metrics" in state:
            state["update_metrics"]("web_search", metrics_result)
        else:
            # 기존 방식으로 상태 업데이트 (콜백 함수가 없는 경우)
            state["metrics"] = state.get("metrics", {})
            state["metrics"]["web_search"] = metrics_result

        logger.info(f"WebSearchAgent completed in {duration:.2f} seconds, found 0 results")
        return state

    async def _save_queries_to_csv(self, query: str, stock_code: Optional[str], stock_name: Optional[str], search_queries: List[str]) -> None:
        """
        생성된 검색 쿼리를 CSV 파일로 저장합니다. 비동기 방식으로 동작합니다.

        Args:
            query: 원본 사용자 쿼리
            stock_code: 종목 코드
            stock_name: 종목 이름
            search_queries: 생성된 검색 쿼리 목록

        Returns:
            None
        """
        try:
            # 파일 I/O 작업을 별도 스레드에서 실행하기 위한 함수 정의
            def write_to_csv() -> None:
                # CSV 파일 경로 설정
                log_dir = os.path.join("stockeasy", "local_cache", "web_search")
                os.makedirs(log_dir, exist_ok=True)

                date_str = datetime.now().strftime("%Y%m%d")
                csv_path = os.path.join(log_dir, f"search_queries_{date_str}.csv")

                # 파일 존재 여부 확인 (헤더 추가 여부 결정)
                file_exists = os.path.isfile(csv_path)

                # 현재 날짜와 시간
                current_datetime = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                # CSV 파일에 데이터 추가
                with open(csv_path, "a", newline="", encoding="utf-8-sig") as csvfile:
                    fieldnames = ["일자", "종목코드", "종목명", "사용자질문", "생성된쿼리"]
                    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

                    # 파일이 새로 생성된 경우 헤더 작성
                    if not file_exists:
                        writer.writeheader()

                    # 각 쿼리에 대한 행 추가
                    for q in search_queries:
                        writer.writerow(
                            {
                                "일자": current_datetime,
                                "종목코드": stock_code if stock_code else "",
                                "종목명": stock_name if stock_name else "",
                                "사용자질문": query,
                                "생성된쿼리": q,
                            }
                        )

                return csv_path

            # 파일 I/O 작업을 별도 스레드에서 비동기적으로 실행
            csv_path = await asyncio.to_thread(write_to_csv)

            logger.info(f"검색 쿼리가 CSV 파일에 저장되었습니다: {csv_path}")

        except Exception as e:
            logger.error(f"CSV 파일 저장 중 오류 발생: {str(e)}", exc_info=True)

    async def _save_search_results_to_json(
        self, query: str, stock_code: Optional[str], stock_name: Optional[str], search_queries: List[str], search_results: List[Dict[str, Any]]
    ) -> None:
        """
        웹 검색 결과를 일자별 JSON 파일로 저장합니다. 비동기 방식으로 동작합니다.

        Args:
            query: 원본 사용자 쿼리
            stock_code: 종목 코드
            stock_name: 종목 이름
            search_queries: 생성된 검색 쿼리 목록
            search_results: 웹 검색 결과 목록

        Returns:
            None
        """
        try:
            # 파일 I/O 작업을 별도 스레드에서 실행하기 위한 함수 정의
            def write_to_json() -> str:
                # JSON 파일 경로 설정
                json_dir = os.path.join("stockeasy", "local_cache", "web_search")
                os.makedirs(json_dir, exist_ok=True)

                date_str = datetime.now().strftime("%Y%m%d")
                json_path = os.path.join(json_dir, f"web_search_results_{date_str}.json")

                # 현재 날짜와 시간
                current_datetime = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                # 저장할 데이터 구성
                entry = {
                    "timestamp": current_datetime,
                    "stock_code": stock_code if stock_code else "",
                    "stock_name": stock_name if stock_name else "",
                    "query": query,
                    "search_queries": search_queries,
                    "search_results": search_results,
                }

                # 파일 존재 여부 확인
                data = []
                if os.path.exists(json_path) and os.path.getsize(json_path) > 0:
                    try:
                        with open(json_path, "r", encoding="utf-8-sig") as json_file:
                            data = json.load(json_file)
                    except json.JSONDecodeError:
                        # 파일이 손상된 경우 새로 시작
                        data = []

                # 데이터 추가
                data.append(entry)

                # 파일에 저장
                with open(json_path, "w", encoding="utf-8-sig") as json_file:
                    json.dump(data, json_file, ensure_ascii=False, indent=2)

                return json_path

            # 파일 I/O 작업을 별도 스레드에서 비동기적으로 실행
            json_path = await asyncio.to_thread(write_to_json)

            logger.info(f"웹 검색 결과가 JSON 파일에 저장되었습니다: {json_path}")

        except Exception as e:
            logger.error(f"JSON 파일 저장 중 오류 발생: {str(e)}", exc_info=True)

    def _extract_domain_name(self, url: str) -> str:
        """
        URL에서 메인 도메인명을 추출합니다.

        Args:
            url: 추출할 URL

        Returns:
            메인 도메인명 (예: naver, daum, google 등)
        """
        try:
            # URL 파싱
            parsed = urlparse(url)
            domain = parsed.netloc

            # 포트 번호 제거
            domain = domain.split(":")[0]

            # www. 제거
            if domain.startswith("www."):
                domain = domain[4:]

            # 도메인 분리 (예: zzz.aaa.com -> ['zzz', 'aaa', 'com'])
            parts = domain.split(".")

            if len(parts) >= 2:
                # 최상위 도메인이 .co.kr, .ne.kr 같은 경우 처리
                if len(parts) >= 3 and parts[-2] in ["co", "ne", "or", "go", "ac", "re"]:
                    # zzz.aaa.co.kr -> aaa 추출
                    return parts[-3] if len(parts) >= 3 else parts[-2]
                else:
                    # zzz.aaa.com -> aaa 추출
                    return parts[-2]

            return domain if domain else "알 수 없음"

        except Exception as e:
            logger.warning(f"도메인 추출 실패 ({url}): {str(e)}")
            return "알 수 없음"
