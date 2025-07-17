"""
요약 에이전트

이 모듈은 다양한 소스에서 검색된 정보를 통합하여 사용자 질문에 대한 요약된 응답을 생성하는 에이전트를 정의합니다.
"""

import asyncio
import hashlib
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from langchain_core.messages import HumanMessage
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from common.core.config import settings
from common.models.token_usage import ProjectType
from common.services.agent_llm import get_agent_llm
from common.utils.util import format_date_for_chart
from stockeasy.agents.base import BaseAgent
from stockeasy.models.agent_io import CompanyReportData, RetrievedTelegramMessage
from stockeasy.prompts.summarizer_section_prompt import (
    PROMPT_GENERATE_EXECUTIVE_SUMMARY,
    PROMPT_GENERATE_SECTION_CONTENT,
    PROMPT_GENERATE_TECHNICAL_ANALYSIS_SECTION,
    format_other_agent_data,
)


class SummarizerAgent(BaseAgent):
    """검색된 정보를 요약하는 에이전트"""

    def __init__(self, name: Optional[str] = None, db: Optional[AsyncSession] = None):
        """에이전트 초기화"""
        super().__init__(name, db)
        self.agent_llm = get_agent_llm("summarizer_agent")
        self.agent_llm_high = get_agent_llm("summarizer_agent_high")
        logger.info(
            f"SummarizerAgent initialized with provider: {self.agent_llm.get_provider()}, model: {self.agent_llm.get_model_name()}, model2: {self.agent_llm_high.get_model_name()}"
        )
        # self.parser = StrOutputParser() # 직접 사용 안 함
        # self.prompt_template = DEEP_RESEARCH_SYSTEM_PROMPT # 직접 사용 안 함

    def _remove_internal_db_references(self, text: str) -> str:
        """
        텍스트에서 내부DB 출처 인용을 제거합니다.
        Args:
            text: 처리할 텍스트

        Returns:
            내부DB 출처 인용이 제거된 텍스트
        """
        if not text:
            return text

        # 제거 대상 키워드들 정의
        remove_keywords = ["내부DB", "비공개자료", "웹검색결과", "web검색결과"]

        # 단순 패턴들 먼저 제거 (괄호 없는 경우)
        for keyword in remove_keywords:
            text = text.replace(f"<{keyword}>", "")
            text = text.replace(f"({keyword})", "")
            text = text.replace(f"{keyword};", "")
            text = text.replace(f", {keyword})", "")
            text = text.replace(f"; {keyword})", "")
            text = text.replace(f", {keyword}", "")
            text = text.replace(f"; {keyword}", "")

        # 괄호 안의 복합 패턴 처리
        def process_parentheses_content(match):
            content = match.group(1)  # 괄호 안의 내용

            # 세미콜론으로 분리된 항목들 분석
            items = [item.strip() for item in content.split(";")]
            remaining_items = []

            for item in items:
                # 각 항목이 제거 대상인지 확인
                should_remove = False
                for keyword in remove_keywords:
                    # "키워드" 또는 "키워드, 날짜" 형태인지 확인
                    if item == keyword or item.startswith(f"{keyword},") or re.match(rf"^{re.escape(keyword)}\s*,\s*\d{{4}}-\d{{2}}-\d{{2}}$", item):
                        should_remove = True
                        break

                if not should_remove:
                    remaining_items.append(item)

            # 남은 항목이 있으면 괄호 유지, 없으면 전체 제거
            if remaining_items:
                return f"({'; '.join(remaining_items)})"
            else:
                return ""

        # 괄호로 둘러싸인 모든 패턴 처리
        text = re.sub(r"\(([^)]+)\)", process_parentheses_content, text)

        # # 연속된 공백 정리 (줄바꿈은 보존하고 연속된 스페이스와 탭만 제거)
        # text = re.sub(r"[ \t]+", " ", text)  # 스페이스와 탭만 하나로 정리
        # text = re.sub(r"\n[ \t]+", "\n", text)  # 줄바꿈 뒤의 불필요한 공백 제거
        # text = re.sub(r"[ \t]+\n", "\n", text)  # 줄바꿈 앞의 불필요한 공백 제거
        # text = text.strip()

        return text

    async def process(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        검색된 정보를 요약합니다.

        Args:
            state: 현재 상태 (query, classification, retrieved_data 등 포함)

        Returns:
            업데이트된 상태 (summary 추가)
        """
        try:
            start_time_process = datetime.now()
            query = state.get("query", "")
            stock_code = state.get("stock_code")
            stock_name = state.get("stock_name")

            agent_results = state.get("agent_results", {})
            report_analyzer_data = agent_results.get("report_analyzer", {}).get("data", {})

            main_query_reports: List[CompanyReportData] = report_analyzer_data.get("main_query_reports", [])
            toc_data_report_agent: Dict[str, List[CompanyReportData]] = report_analyzer_data.get("toc_reports", {})

            # 텔레그램은 toc_results, main_query_results. 기업리포트와는 키 이름이 다르다(toc_reports)
            telegram_data = agent_results.get("telegram_retriever", {}).get("data", {})
            toc_data_telegram_agent: Dict[str, List[RetrievedTelegramMessage]] = telegram_data.get("toc_results", {})  # 텔레그램은 toc_results, main_query_results

            # 다른 에이전트 결과 데이터 포맷팅 (stock_code, stock_name 전달)
            other_agents_context_str = format_other_agent_data(agent_results, stock_code=stock_code, stock_name=stock_name)

            final_report_toc = state.get("final_report_toc")

            if not query:
                state["errors"] = state.get("errors", []) + [
                    {"agent": self.get_name(), "error": "질문이 제공되지 않았습니다.", "type": "InvalidInputError", "timestamp": datetime.now()}
                ]
                state["processing_status"] = state.get("processing_status", {})
                state["processing_status"]["summarizer"] = "error"
                return state

            if not final_report_toc:
                state["errors"] = state.get("errors", []) + [
                    {"agent": self.get_name(), "error": "동적 목차 정보(final_report_toc)가 없습니다.", "type": "MissingDataError", "timestamp": datetime.now()}
                ]
                state["processing_status"] = state.get("processing_status", {})
                state["processing_status"]["summarizer"] = "error"
                return state

            if not main_query_reports and not toc_data_report_agent:
                logger.warning("[SummarizerAgent] 요약할 기업 리포트 정보가 없습니다 (메인 쿼리 및 TOC 결과 모두 부족). 다른 컨텍스트만으로 진행될 수 있습니다.")

        except Exception as e:  # 데이터 준비 과정에서의 예외
            logger.exception(f"SummarizerAgent 정보 준비 중 오류 발생: {e}")
            state["errors"] = state.get("errors", []) + [{"agent": self.get_name(), "error": f"정보 준비 오류: {str(e)}", "type": type(e).__name__, "timestamp": datetime.now()}]
            state["processing_status"] = state.get("processing_status", {})
            state["processing_status"]["summarizer"] = "error"
            return state

        try:
            user_context = state.get("user_context", {})
            user_id = user_context.get("user_id", None)
            # state["agent_results"]["financial_analyzer"]["competitor_info"] = competitor_info
            competitors_infos = state.get("agent_results", {}).get("financial_analyzer", {}).get("competitor_infos", [])

            # 기술적 분석 데이터 추출
            technical_analysis_data = state.get("agent_results", {}).get("technical_analyzer", {}).get("data", {})

            # 테스트 모드 설정 (기술적 분석 섹션만 생성)

            technical_analysis_only_test = settings.TEST_TECH_AGENT

            summary, summary_by_section = await self.generate_sectioned_summary_v2(
                query=query,
                user_id=user_id,
                final_report_toc=final_report_toc,
                toc_data_company_report=toc_data_report_agent,
                toc_data_telegram_agent=toc_data_telegram_agent,
                other_agents_context_str=other_agents_context_str,
                competitors_infos=competitors_infos,
                technical_analysis_data=technical_analysis_data,
                stock_name=stock_name,
                stock_code=stock_code,
                technical_analysis_only=technical_analysis_only_test,
            )

            state["summary"] = summary
            state["summary_by_section"] = summary_by_section
            state["processing_status"] = state.get("processing_status", {})
            state["processing_status"]["summarizer"] = "completed"
            logger.info(f"[SummarizerAgent] 요약 생성 완료: 소요시간 {datetime.now() - start_time_process}")
            return state
        except Exception as e:
            logger.exception(f"SummarizerAgent 요약 생성 중 오류 발생: {e}")
            state["errors"] = state.get("errors", []) + [{"agent": self.get_name(), "error": f"요약 생성 오류: {str(e)}", "type": type(e).__name__, "timestamp": datetime.now()}]
            state["processing_status"] = state.get("processing_status", {})
            state["processing_status"]["summarizer"] = "error"
            return state

    async def generate_sectioned_summary_v2(
        self,
        query: str,
        user_id: str,
        final_report_toc: Dict[str, Any],
        toc_data_company_report: Dict[str, List[CompanyReportData]],
        toc_data_telegram_agent: Dict[str, List[RetrievedTelegramMessage]],
        other_agents_context_str: str,
        competitors_infos: List[Dict[str, Any]],
        technical_analysis_data: Optional[Dict[str, Any]] = None,
        stock_name: Optional[str] = None,
        stock_code: Optional[str] = None,
        technical_analysis_only: bool = False,
    ):
        """
        동적 목차에 따라 섹션별로 요약을 생성하고 통합하는 함수 (v2: 핵심요약 후생성).
        1. "핵심 요약"을 제외한 나머지 섹션들을 병렬로 생성.
        2. 생성된 다른 섹션들의 내용을 바탕으로 "핵심 요약" 섹션을 생성.
        3. 모든 섹션 내용을 통합하여 최종 보고서와 섹션별 내용 맵을 반환.

        Args:
            technical_analysis_only (bool): True인 경우 기술적 분석 섹션만 생성합니다. (테스트 모드)
        """
        logger.info("[SummarizerAgent] 동적 목차 기반 섹션별 요약 생성 시작 (v2: 핵심요약 후생성)")
        competitor_keywords = ["경쟁사", "경쟁업체", "경쟁기업", "라이벌", "경쟁자", "업계 경쟁", "경쟁 업체"]
        technical_analysis_keywords = ["기술적", "기술적분석", "차트", "차트분석", "기술분석", "매매신호", "기술지표", "트레이딩"]

        if technical_analysis_only:
            logger.info("[SummarizerAgent] 기술적 분석 섹션만 생성하는 테스트 모드로 실행됩니다.")

        toc_reports_summary_for_log = {k: len(v) for k, v in toc_data_company_report.items()}
        logger.info(f"[SummarizerAgent] 전달받은 toc_data_company_report (키: 리포트 수): {toc_reports_summary_for_log}")
        if not toc_data_company_report:
            logger.warning("[SummarizerAgent] toc_data_company_report가 비어있습니다. 일부 섹션 내용이 부실할 수 있습니다.")

        toc_telegram_summary_for_log = {k: len(v) for k, v in toc_data_telegram_agent.items()}
        logger.info(f"[SummarizerAgent] 전달받은 toc_data_telegram_agent (키: 텔레그램 메시지 수): {toc_telegram_summary_for_log}")
        if not toc_data_telegram_agent:
            logger.warning("[SummarizerAgent] toc_data_telegram_agent가 비어있습니다. 일부 섹션 내용이 부실할 수 있습니다.")

        toc_title = final_report_toc.get("title", "알 수 없는 제목의 보고서")
        toc_sections_from_generator = final_report_toc.get("sections", [])

        if not toc_sections_from_generator:
            logger.warning("[SummarizerAgent] 목차에 섹션 정보가 없습니다. 빈 보고서를 반환합니다.")
            return f"# {toc_title}\n\n목차에 정의된 섹션이 없어 보고서 내용을 생성할 수 없습니다.", {}

        # 1. "핵심 요약" 섹션 정보 분리 (첫 번째 섹션으로 가정)
        first_section_data_for_summary = toc_sections_from_generator[0]

        # 2. "핵심 요약"을 제외한 나머지 섹션들 생성 준비
        other_section_tasks = []
        other_section_details_for_llm_call = []

        start_time_other_sections = datetime.now()

        for i, section_data in enumerate(toc_sections_from_generator):
            if i == 0:  # "핵심 요약" 섹션은 나중에 처리
                continue

            current_section_title = section_data.get("title", f"섹션 {i + 1}")
            current_section_description = section_data.get("description", "")
            current_section_id = section_data.get("section_id")

            if not current_section_id:
                logger.warning(f"[SummarizerAgent] '{current_section_title}' (인덱스 {i})에 section_id가 없습니다. 이 섹션을 건너뜁니다.")
                continue

            current_section_company_report: List[CompanyReportData] = []
            reports_for_current_section_id = toc_data_company_report.get(current_section_id, [])
            current_section_company_report.extend(reports_for_current_section_id)

            current_section_telegram_msgs: List[RetrievedTelegramMessage] = []
            telegram_msgs_for_current_section_id = toc_data_telegram_agent.get(current_section_id, [])
            current_section_telegram_msgs.extend(telegram_msgs_for_current_section_id)

            subsections = section_data.get("subsections", [])
            subsections_text_current = ""
            if isinstance(subsections, list) and subsections:
                subsections_text_current = "\n".join([f" - {s.get('title', '')}\n   섹션설명:({s.get('description', '')})" for s in subsections])
                for sub_section_item in subsections:
                    if isinstance(sub_section_item, dict):
                        subsection_id = sub_section_item.get("subsection_id")
                        if subsection_id:
                            current_section_company_report.extend(toc_data_company_report.get(subsection_id, []))
                            current_section_telegram_msgs.extend(toc_data_telegram_agent.get(subsection_id, []))

            seen_contents = set()
            deduplicated_list_reports = []
            for report in current_section_company_report:
                content_key = hashlib.sha256(report.get("content", "")[:100].encode("utf-8")).hexdigest()
                if content_key not in seen_contents:
                    seen_contents.add(content_key)
                    deduplicated_list_reports.append(report)
            current_section_company_report = deduplicated_list_reports

            seen_telegram_msgs = set()
            deduplicated_list_tele_msgs = []
            for msg in current_section_telegram_msgs:
                # content가 리스트인 경우 (예: [{'type': 'text', 'content': '...'}]) 텍스트 내용 추출
                content = msg.get("content", "")
                if isinstance(content, list):
                    # 리스트에서 텍스트 내용 추출
                    text_content = ""
                    for item in content:
                        if isinstance(item, dict) and item.get("type") == "text":
                            text_content += item.get("content", "")
                    content = text_content
                elif not isinstance(content, str):
                    content = str(content)

                msg_key = hashlib.sha256(content[:100].encode("utf-8")).hexdigest()
                if msg_key not in seen_telegram_msgs:
                    seen_telegram_msgs.add(msg_key)
                    deduplicated_list_tele_msgs.append(msg)
            current_section_telegram_msgs = deduplicated_list_tele_msgs

            logger.info(
                f"[SummarizerAgent] 섹션 '{current_section_title}' (ID: {current_section_id}, 목차인덱스 {i}) 최종 집계 - 고유 리포트: {len(current_section_company_report)}개, 고유 텔레그램: {len(current_section_telegram_msgs)}개"
            )

            formatted_report_docs = self._format_documents_for_section(current_section_company_report)
            formatted_telegram_msgs = self._format_telegram_messages_for_section(current_section_telegram_msgs)

            # 기술적 분석 섹션인지 확인
            is_technical_analysis_section = any(keyword in current_section_title.lower() for keyword in technical_analysis_keywords)

            if is_technical_analysis_section:
                # 기술적 분석 섹션은 기술적 분석 데이터만 사용 (토큰 절약)
                logger.info(f"[SummarizerAgent] 기술적 분석 섹션 '{current_section_title}' - 기술적 분석 데이터만 사용 및 차트 플레이스홀더 활성화")

                formatted_technical_data = self._format_technical_analysis_data(technical_analysis_data)
                price_chart_data_str = self._format_price_chart(technical_analysis_data)

                logger.info(f"[SummarizerAgent] 일반 기술적 분석 섹션 '{current_section_title}' - 기존 차트 플레이스홀더 사용")

                combined_context_for_current_section = f"{formatted_technical_data}"
            else:
                if technical_analysis_only:
                    # 테스트 모드에서는 기술적 분석 섹션이 아닌 경우 건너뜁니다.
                    logger.info(f"[SummarizerAgent] 테스트 모드: 기술적 분석 섹션이 아닌 '{current_section_title}' 건너뜁니다.")
                    continue
                combined_context_for_current_section = f"{formatted_report_docs}\n\n{formatted_telegram_msgs}\n\n{other_agents_context_str}"

            # 경쟁사 목차이면, 경쟁사의 최근 분기별 재무데이터 추가.
            if any(keyword in current_section_title.lower() for keyword in competitor_keywords):
                logger.info("[SummarizerAgent] 경쟁사 목차 - 경쟁사의 최근 분기별 재무데이터 추가")
                formatted_data = self._format_competitor_financial_data(competitors_infos)
                combined_context_for_current_section += f"\n<경쟁사 분기별 재무데이터>\n{formatted_data}\n</경쟁사 분기별 재무데이터>"

            # 프롬프트 선택: 기술적 분석 섹션이면 전용 프롬프트 사용
            if is_technical_analysis_section:
                prompt_str_current = PROMPT_GENERATE_TECHNICAL_ANALYSIS_SECTION.format(
                    query=query,
                    section_title=current_section_title,
                    section_description=current_section_description,
                    subsections_info=subsections_text_current,
                    all_analyses=combined_context_for_current_section,
                    price_chart=price_chart_data_str,
                )
            else:
                prompt_str_current = PROMPT_GENERATE_SECTION_CONTENT.format(
                    query=query,
                    section_title=current_section_title,
                    section_description=current_section_description,
                    subsections_info=subsections_text_current,
                    all_analyses=combined_context_for_current_section,
                )
            messages_current = [HumanMessage(content=prompt_str_current)]

            # 기술적 분석 섹션은 agent_llm25 사용, 나머지는 기존 agent_llm 사용
            llm_to_use = self.agent_llm_high if is_technical_analysis_section else self.agent_llm
            task_current = asyncio.create_task(llm_to_use.ainvoke_with_fallback(messages_current, user_id=user_id, project_type=ProjectType.STOCKEASY, db=self.db))
            other_section_tasks.append(task_current)
            other_section_details_for_llm_call.append(
                {
                    "title": current_section_title,
                    "original_toc_index": i,
                }
            )

        # 3. 나머지 섹션들 내용 병렬 생성
        other_sections_results_raw = await asyncio.gather(*other_section_tasks, return_exceptions=True)
        logger.info(f"[SummarizerAgent] 나머지 섹션들 내용 병렬 생성 완료: 소요시간 {datetime.now() - start_time_other_sections}")

        # 4. 생성된 나머지 섹션 내용 정리 및 "핵심 요약" 생성용 컨텍스트 준비
        generated_texts_for_summary_input = []
        processed_other_sections_data = []

        for idx, raw_result in enumerate(other_sections_results_raw):
            section_detail = other_section_details_for_llm_call[idx]
            original_section_title = section_detail["title"]

            if isinstance(raw_result, Exception):
                logger.error(f"[SummarizerAgent] '{original_section_title}' (목차인덱스 {section_detail['original_toc_index']}) 생성 실패: {str(raw_result)}")
                processed_other_sections_data.append(
                    {"details": section_detail, "text": f"*오류: '{original_section_title}' 섹션 내용을 생성하는 중 문제가 발생했습니다: {str(raw_result)}*"}
                )
                continue

            section_text_content = raw_result.content if hasattr(raw_result, "content") else str(raw_result)
            logger.info(f"[SummarizerAgent] '{original_section_title}' (목차인덱스 {section_detail['original_toc_index']}) 생성 완료 (길이: {len(section_text_content)})")

            # 차트 플레이스홀더 확인 및 로깅
            import re

            chart_placeholders = re.findall(r"\[CHART_PLACEHOLDER:[A-Z_]+\]", section_text_content)
            if chart_placeholders:
                logger.info(f"[SummarizerAgent] '{original_section_title}'에서 차트 플레이스홀더 발견: {chart_placeholders}")

            # generated_texts_for_summary_input.append(f"## {original_section_title}\n{section_text_content}")
            generated_texts_for_summary_input.append(section_text_content)
            processed_other_sections_data.append({"details": section_detail, "text": section_text_content})

        # 5. "핵심 요약" 섹션 내용 생성
        summary_section_content_str = "*핵심 요약 생성 중 오류가 발생했거나, 요약할 다른 섹션 내용이 없습니다.*"
        summary_section_title = first_section_data_for_summary.get("title", "핵심 요약")

        start_time_summary_section = datetime.now()
        if generated_texts_for_summary_input:
            context_for_summary_llm = "\n\n".join(generated_texts_for_summary_input)

            # if other_agents_context_str and other_agents_context_str.strip():
            #      context_for_summary_llm += f"\n\n<기타_참고_자료>\n{other_agents_context_str}\n</기타_참고_자료>"

            first_section_data_for_summary.get("description", "보고서 전체의 주요 내용을 요약합니다.")
            summary_section_subsections = first_section_data_for_summary.get("subsections", [])
            if isinstance(summary_section_subsections, list) and summary_section_subsections:
                "\n이 핵심 요약 섹션이 다룰 수 있는 하위 주제 목록:\n" + "\n".join([f" - {s.get('title', '')} ({s.get('description', '')})" for s in summary_section_subsections])

            # 핵심 요약 프롬프트 사용
            prompt_str_summary = PROMPT_GENERATE_EXECUTIVE_SUMMARY.format(
                original_query=query,  # 원본 사용자 질문
                report_title=toc_title,  # 보고서 전체 제목
                section_title=summary_section_title,  # 현재 섹션 제목 ("핵심 요약")
                # section_description은 EXECUTIVE_SUMMARY 프롬프트에 없음
                # subsections_info도 EXECUTIVE_SUMMARY 프롬프트에 없음
                sections_summary=context_for_summary_llm,  # 다른 섹션들의 생성된 내용 + 기타 참고자료
            )
            messages_summary = [HumanMessage(content=prompt_str_summary)]

            logger.info(
                f"[SummarizerAgent] '{summary_section_title}' 생성 작업 시작 (PROMPT_GENERATE_EXECUTIVE_SUMMARY 사용). 컨텍스트 길이(근사치): {len(context_for_summary_llm)}"
            )
            try:
                result_summary_section_raw = await self.agent_llm.ainvoke_with_fallback(messages_summary, user_id=user_id, project_type=ProjectType.STOCKEASY, db=self.db)
                if isinstance(result_summary_section_raw, Exception):
                    logger.error(f"[SummarizerAgent] '{summary_section_title}' 생성 실패 (LLM 호출 결과가 예외 객체): {str(result_summary_section_raw)}")
                    summary_section_content_str = "*핵심 요약 생성 중 오류가 발생했습니다.*"
                elif hasattr(result_summary_section_raw, "content"):
                    summary_section_content_str = result_summary_section_raw.content
                    logger.info(f"[SummarizerAgent] '{summary_section_title}' 생성 완료 (길이: {len(summary_section_content_str)})")
                else:
                    summary_section_content_str = str(result_summary_section_raw)
                    logger.warning(f"[SummarizerAgent] '{summary_section_title}' 생성 결과가 예상과 다릅니다: {summary_section_content_str[:200]}...")
            except Exception as e_summary:
                logger.exception(f"[SummarizerAgent] '{summary_section_title}' 생성 중 LLM 호출 예외 발생: {e_summary}")
                summary_section_content_str = "*핵심 요약 생성 중 오류가 발생했습니다.*"
        else:
            logger.warning(f"[SummarizerAgent] '{summary_section_title}' 생성 스킵: 요약할 다른 섹션 내용이 없습니다.")
        logger.info(f"[SummarizerAgent] 핵심요약 생성 완료: 소요시간 {datetime.now() - start_time_summary_section}")

        # 6. 최종 보고서 통합
        section_contents_map = {}
        final_report_parts = []

        # "핵심 요약" 섹션 추가 (목차상 1번)
        f"{first_section_data_for_summary.get('original_toc_index', 0) + 1}. {summary_section_title}"

        # 핵심 요약에서도 내부DB 관련 텍스트 제거
        summary_section_content_str = self._remove_internal_db_references(summary_section_content_str)

        section_contents_map[summary_section_title] = summary_section_content_str
        # final_report_parts.append(f"## {numbered_summary_title_for_report}\n{summary_section_content_str}")
        final_report_parts.append(summary_section_content_str)

        # 나머지 섹션들 추가 (목차 순서대로)
        for item in processed_other_sections_data:
            details = item["details"]
            text_content = item["text"]
            section_title_from_details = details["title"]

            # 내부DB 관련 텍스트 제거 (기존 패턴 + 날짜 포함 패턴)
            text_content = self._remove_internal_db_references(text_content)

            section_contents_map[section_title_from_details] = text_content
            # final_report_parts.append(f"## {numbered_section_title_for_report}\n{text_content}")
            final_report_parts.append(text_content)
        section_contents_map["면책조항"] = (
            "본 보고서는 투자 참고 자료로만 활용하시기 바라며, 특정 종목의 매수 또는 매도를 권유하지 않습니다. 보고서의 내용이 사실과 다른 내용이 일부 존재할 수 있으니 참고해 주시기 바랍니다. 투자 결정은 투자자 본인의 책임하에 이루어져야 하며, 본 보고서에 기반한 투자로 인한 손실에 대해 작성자와 당사는 어떠한 법적 책임도 지지 않습니다. 모든 투자에는 위험이 수반되므로 투자 전 투자자 본인의 판단과 책임하에 충분한 검토가 필요합니다."
        )
        final_report_parts.append(section_contents_map["면책조항"])

        final_summary_md = f"# {toc_title}\n\n"
        final_summary_md += "\n\n".join(final_report_parts)
        # final_summary_md += "\n\n**면책조항**\n\n본 보고서는 투자 참고 자료로만 활용하시기 바라며, 특정 종목의 매수 또는 매도를 권유하지 않습니다. 보고서의 내용이 사실과 다른 내용이 일부 존재할 수 있으니 참고해 주시기 바랍니다. 투자 결정은 투자자 본인의 책임하에 이루어져야 하며, 본 보고서에 기반한 투자로 인한 손실에 대해 작성자와 당사는 어떠한 법적 책임도 지지 않습니다. 모든 투자에는 위험이 수반되므로 투자 전 투자자 본인의 판단과 책임하에 충분한 검토가 필요합니다."

        logger.info(f"[SummarizerAgent] 동적 목차 기반 섹션별 요약 통합 완료 (v2), 소요시간 {datetime.now() - start_time_other_sections}")
        return final_summary_md, section_contents_map

    def _format_documents_for_section(self, reports: List[CompanyReportData]) -> str:
        """
        CompanyReportData 리스트를 LLM 프롬프트에 적합한 문자열로 변환합니다.
        (기존 common.agents.report_analyzer_agent.format_report_contents 와 유사하지만,
         SummarizerAgent에 맞게 커스터마이징 가능)
        """
        if not reports:
            return "해당 섹션에 대한 기업리포트 참고 자료가 없습니다."

        text = "--- 데이터소스: 기업리포트 ---\n\n"
        for i, report in enumerate(reports):
            if i > 0:  # 첫 번째 항목이 아닌 경우만 구분선 추가
                text += "____\n\n"

            text += f"- **출처**: {report.get('source', '미상')}\n"
            text += f"- **날짜**: {report.get('publish_date', '날짜 정보 없음')}\n"

            # content가 리스트인 경우 (예: [{'type': 'text', 'content': '...'}]) 텍스트 내용 추출
            sContent = report.get("content", "내용 없음")
            if isinstance(sContent, list):
                # 리스트에서 텍스트 내용 추출
                text_content = ""
                for item in sContent:
                    if isinstance(item, dict) and item.get("type") == "text":
                        text_content += item.get("content", "")
                sContent = text_content if text_content else "내용 없음"
            elif not isinstance(sContent, str):
                sContent = str(sContent)

            sContent = sContent.replace("\n\n", "\n")
            text += f"- **내용**:\n{sContent}\n\n"

        return text

    def _format_telegram_messages_for_section(self, messages: List[RetrievedTelegramMessage]) -> str:
        """
        RetrievedTelegramMessage 리스트를 LLM 프롬프트에 적합한 문자열로 변환합니다.
        """
        if not messages:
            return "해당 섹션에 대한 내부DB 참고 자료가 없습니다."

        text = "--- 데이터소스: 내부DB ---\n\n"
        for i, message in enumerate(messages):
            # ISO 형식의 날짜를 년-월-일 형식으로 변환
            created_at = message.get("message_created_at", "")
            formatted_date = "날짜 정보 없음"

            if created_at:
                try:
                    # datetime 객체인지 문자열인지 확인
                    if isinstance(created_at, datetime):
                        # datetime 객체인 경우 직접 포맷팅
                        formatted_date = created_at.strftime("%Y-%m-%d")
                    elif isinstance(created_at, str):
                        # 문자열인 경우 ISO 형식 처리
                        # timezone 정보가 포함된 ISO 문자열 처리를 위해 replace 사용
                        # 예: 2025-07-14 23:07:47.601942+09:00 -> 2025-07-14T23:07:47.601942+09:00
                        if " " in created_at and "T" not in created_at:
                            created_at = created_at.replace(" ", "T", 1)

                        dt_obj = datetime.fromisoformat(created_at)
                        formatted_date = dt_obj.strftime("%Y-%m-%d")
                    else:
                        # 다른 타입인 경우 문자열로 변환 후 처리
                        created_at_str = str(created_at)
                        import re

                        date_match = re.search(r"(\d{4}-\d{2}-\d{2})", created_at_str)
                        if date_match:
                            formatted_date = date_match.group(1)
                        else:
                            formatted_date = created_at_str
                except (ValueError, TypeError) as e:
                    # 날짜 변환 실패 시 정규식으로 YYYY-MM-DD 추출 시도
                    import re

                    created_at_str = str(created_at)
                    date_match = re.search(r"(\d{4}-\d{2}-\d{2})", created_at_str)
                    if date_match:
                        formatted_date = date_match.group(1)
                    else:
                        # 그래도 실패하면 원본 값 사용
                        formatted_date = created_at_str
                    logger.warning(f"[SummarizerAgent] 날짜 변환 실패: {created_at} (타입: {type(created_at)}) -> {e}")

            if i > 0:  # 첫 번째 항목이 아닌 경우만 구분선 추가
                text += "____\n\n"

            # content가 리스트인 경우 (예: [{'type': 'text', 'content': '...'}]) 텍스트 내용 추출
            content = message.get("content", "내용 없음")
            if isinstance(content, list):
                # 리스트에서 텍스트 내용 추출
                text_content = ""
                for item in content:
                    if isinstance(item, dict) and item.get("type") == "text":
                        text_content += item.get("content", "")
                content = text_content if text_content else "내용 없음"
            elif not isinstance(content, str):
                content = str(content)

            text += f"- **날짜**: {formatted_date}\n"
            text += f"- **내용**: {content}\n\n"

        return text

    def _format_competitor_financial_data(self, competitors_infos: List[Dict[str, Any]]) -> str:
        """
        경쟁사의 재무 데이터를 포맷팅하여 문자열로 반환합니다.

        Args:
            competitors_infos: 경쟁사 정보 리스트

        Returns:
            포맷팅된 경쟁사 재무 데이터 문자열
        """
        formatted_data = ""
        if isinstance(competitors_infos, list) and competitors_infos:
            for competitor_info in competitors_infos:
                stock_name = competitor_info.get("stock_name", "경쟁사")
                stock_code = competitor_info.get("stock_code", "")
                logger.info(f" 경쟁사 재무 데이터 포맷팅 시작: {stock_name} ({stock_code})")
                formatted_data += f"--- 데이터소스: {stock_name} ({stock_code}) 분기별 재무 데이터 ---\n\n"

                if "db_search_data" in competitor_info:
                    db_data = competitor_info["db_search_data"]
                    if "quarters" in db_data:
                        quarters = db_data["quarters"]
                        # 분기 데이터를 시간순으로 정렬
                        sorted_quarters = sorted(quarters.items(), reverse=True)

                        # 각 분기별 데이터 추가 (텍스트 형식)
                        for quarter_key, quarter_data in sorted_quarters[:4]:  # 최근 4분기만 표시
                            year = quarter_data.get("year", 0)
                            if year == 0:
                                qk = int(quarter_key) // 100
                                year = qk
                            quarter_num = quarter_data.get("quarter", 0)
                            if quarter_num == 0:
                                qk = int(quarter_key) % 100
                                quarter_num = qk / 3
                            quarter_display = f"{year}년 {quarter_num}분기"

                            revenue = quarter_data.get("revenue", {}).get("period_value", "-")
                            revenue_unit = quarter_data.get("revenue", {}).get("display_unit", "")

                            op_income = quarter_data.get("operating_income", {}).get("period_value", "-")
                            op_income_unit = quarter_data.get("operating_income", {}).get("display_unit", "")

                            net_income = quarter_data.get("net_income", {}).get("period_value", "-")
                            net_income_unit = quarter_data.get("net_income", {}).get("display_unit", "")

                            formatted_data += f"{quarter_display}: 매출액 {revenue}{revenue_unit}, 영업이익 {op_income}{op_income_unit}, 당기순이익 {net_income}{net_income_unit}\n"

                        formatted_data += "\n"
                    else:
                        formatted_data += "분기별 재무 데이터를 찾을 수 없습니다.\n\n"
                else:
                    formatted_data += "경쟁사 재무 데이터를 찾을 수 없습니다.\n\n"
        else:
            formatted_data = "경쟁사 재무 데이터를 찾을 수 없습니다."

        return formatted_data

    def _format_technical_analysis_data(self, technical_analysis_data: Optional[Dict[str, Any]]) -> str:
        """
        기술적 분석 데이터를 LLM 프롬프트에 적합한 문자열로 변환합니다.

        Args:
            technical_analysis_data: 기술적 분석 결과 데이터

        Returns:
            포맷팅된 기술적 분석 데이터 문자열
        """
        if not technical_analysis_data:
            return "기술적 분석 데이터가 없습니다."

        formatted_text = "--- 데이터소스: 기술적분석 ---\n\n"

        # 기본 정보
        stock_name = technical_analysis_data.get("stock_name", "")
        stock_code = technical_analysis_data.get("stock_code", "")
        current_price = technical_analysis_data.get("current_price", 0)
        analysis_date = technical_analysis_data.get("analysis_date", "")

        formatted_text += f"종목: {stock_name} ({stock_code})\n"
        formatted_text += f"현재가: {current_price:,}원\n"
        formatted_text += f"분석일시: {analysis_date}\n\n"

        # 추세추종 지표들을 위한 차트 플레이스홀더 추가
        formatted_text += "차트 분석:\n"
        formatted_text += "[CHART_PLACEHOLDER:TECHNICAL_INDICATOR_CHART]\n\n"

        # 기술적 지표
        indicators = technical_analysis_data.get("technical_indicators", {})
        if indicators:
            formatted_text += "기술적 지표 분석:\n"

            # 기술적 지표 요약 테이블
            formatted_text += "\n기술적 지표 요약:\n"

            # 테이블용 데이터 수집
            table_data = []

            # 모멘텀 지표들 (RSI, MACD, 스토캐스틱)
            # RSI (기본 지표)
            rsi = indicators.get("rsi")
            if rsi is not None:
                if rsi < 30:
                    rsi_status = "과매도 상태 (매수 신호)"
                    rsi_signal = "매수"
                elif rsi > 70:
                    rsi_status = "과매수 상태 (매도 신호)"
                    rsi_signal = "매도"
                else:
                    rsi_status = "중립 상태"
                    rsi_signal = "중립"

                table_data.append(f"|RSI (14일)|{rsi:.2f}|{rsi_signal}|{rsi_status}|")
                formatted_text += f"  RSI (14일): {rsi:.2f} - {rsi_status}\n"
                formatted_text += "    - RSI가 30 이하면 과매도, 70 이상이면 과매수로 판단됩니다.\n"

            # MACD (모멘텀 지표)
            macd = indicators.get("macd")
            macd_signal = indicators.get("macd_signal")
            macd_histogram = indicators.get("macd_histogram")
            if macd is not None and macd_signal is not None:
                # MACD 신호 판단
                if macd > macd_signal:
                    if macd_histogram and macd_histogram > 0:
                        macd_status = "상승 모멘텀 (매수 신호)"
                        macd_signal_type = "매수"
                    else:
                        macd_status = "상승 전환 시도"
                        macd_signal_type = "관심"
                elif macd < macd_signal:
                    if macd_histogram and macd_histogram < 0:
                        macd_status = "하락 모멘텀 (매도 신호)"
                        macd_signal_type = "매도"
                    else:
                        macd_status = "하락 전환 시도"
                        macd_signal_type = "주의"
                else:
                    macd_status = "중립 상태"
                    macd_signal_type = "중립"

                table_data.append(f"|MACD|{macd:.3f}|{macd_signal_type}|{macd_status}|")
                formatted_text += f"  MACD: {macd:.3f} - {macd_status}\n"
                formatted_text += f"    - MACD 라인: {macd:.3f}, 시그널 라인: {macd_signal:.3f}\n"
                if macd_histogram is not None:
                    formatted_text += f"    - MACD 히스토그램: {macd_histogram:.3f}\n"
                formatted_text += "    - MACD가 시그널 라인을 상향 돌파하면 매수신호, 하향 돌파하면 매도신호로 판단됩니다.\n"

            # 스토캐스틱 (모멘텀 지표)
            stochastic_k = indicators.get("stochastic_k")
            stochastic_d = indicators.get("stochastic_d")
            if stochastic_k is not None and stochastic_d is not None:
                # 스토캐스틱 신호 판단
                if stochastic_k < 20 and stochastic_d < 20:
                    stoch_status = "과매도 상태 (매수 신호)"
                    stoch_signal = "매수"
                elif stochastic_k > 80 and stochastic_d > 80:
                    stoch_status = "과매수 상태 (매도 신호)"
                    stoch_signal = "매도"
                elif stochastic_k > stochastic_d:
                    stoch_status = "상승 모멘텀"
                    stoch_signal = "긍정"
                elif stochastic_k < stochastic_d:
                    stoch_status = "하락 모멘텀"
                    stoch_signal = "부정"
                else:
                    stoch_status = "중립 상태"
                    stoch_signal = "중립"

                table_data.append(f"|스토캐스틱|%K: {stochastic_k:.1f}, %D: {stochastic_d:.1f}|{stoch_signal}|{stoch_status}|")
                formatted_text += f"  스토캐스틱: %K {stochastic_k:.1f}, %D {stochastic_d:.1f} - {stoch_status}\n"
                formatted_text += "    - %K가 20 이하면 과매도, 80 이상이면 과매수로 판단됩니다.\n"
                formatted_text += "    - %K가 %D를 상향 돌파하면 매수신호, 하향 돌파하면 매도신호로 판단됩니다.\n"

            # ADX (추세 강도 지표)
            adx = indicators.get("adx")
            adx_plus_di = indicators.get("adx_plus_di")
            adx_minus_di = indicators.get("adx_minus_di")
            if adx is not None:
                if adx >= 85:
                    trend_strength = "극도의 강한 추세 (신규 진입 절대 금지, 현 구간부터의 신규 진입은 대부분 손실)"
                elif adx >= 70:
                    trend_strength = "매우 강한 추세 (반전 위험, 주의 필요)"
                elif adx >= 25:
                    trend_strength = "강한 추세 (추세 매매 적합)"
                elif adx <= 20:
                    trend_strength = "약한 추세 (횡보 구간)"
                else:
                    trend_strength = "보통 추세"

                # ADX 신호 결정
                if adx >= 70:
                    adx_signal = "극도추세 (주의)"
                elif adx >= 25:
                    if adx_plus_di and adx_minus_di:
                        if adx_plus_di > adx_minus_di:
                            adx_signal = "강한 상승추세"
                        else:
                            adx_signal = "강한 하락추세"
                    else:
                        adx_signal = "강한 추세"
                elif adx <= 20:
                    adx_signal = "횡보"
                else:
                    adx_signal = "보통 추세"

                table_data.append(f"|ADX|{adx:.2f}|{adx_signal}|{trend_strength}|")
                formatted_text += f"  ADX (Average Directional Index): {adx:.2f} - {trend_strength}\n"

                if adx_plus_di and adx_minus_di:
                    if adx_plus_di > adx_minus_di:
                        direction_signal = "상승 추세 우세"
                    elif adx_minus_di > adx_plus_di:
                        direction_signal = "하락 추세 우세"
                    else:
                        direction_signal = "방향성 불분명"

                    formatted_text += f"    - +DI: {adx_plus_di:.2f}, -DI: {adx_minus_di:.2f} ({direction_signal})\n"

                if adx >= 85:
                    formatted_text += "    - ADX 85 이상시 극도의 강한 추세로 신규 진입 절대 금지, 현구간부터의 신규 진입은 대부분 손실일 가능성이 매우 높습니다.\n"
                elif adx >= 70:
                    formatted_text += "    - ADX 70 이상시 매우의 강한 추세로 반전 위험이 높아 주의가 필요합니다. 기존 보유자의 영역입니다.\n"
                else:
                    formatted_text += "    - ADX 25 이상시 강한 추세, 20 이하시 횡보 구간으로 판단됩니다.\n"

            # 슈퍼트렌드 (SuperTrend)
            supertrend = indicators.get("supertrend")
            supertrend_direction = indicators.get("supertrend_direction")
            if supertrend is not None:
                if supertrend_direction == 1:
                    trend_signal = "상승추세 (매수 신호)"
                    signal_description = "주가가 슈퍼트렌드 라인 위에 위치하여 상승 추세를 나타냅니다."
                elif supertrend_direction == -1:
                    trend_signal = "하락추세 (매도 신호)"
                    signal_description = "주가가 슈퍼트렌드 라인 아래에 위치하여 하락 추세를 나타냅니다."
                else:
                    trend_signal = "중립 (추세 전환 구간)"
                    signal_description = "추세 전환 구간으로 매매 신호가 불분명합니다."

                # SuperTrend 신호 결정
                if supertrend_direction == 1:
                    supertrend_signal = "매수"
                elif supertrend_direction == -1:
                    supertrend_signal = "매도"
                else:
                    supertrend_signal = "중립"

                price_vs_supertrend = current_price - supertrend
                price_difference_pct = (price_vs_supertrend / supertrend) * 100

                table_data.append(f"|SuperTrend|{supertrend:,.0f}원|{supertrend_signal}|{trend_signal}|")
                formatted_text += f"  슈퍼트렌드: {supertrend:,.0f}원 - {trend_signal}\n"
                formatted_text += f"    - 현재가와 차이: {price_vs_supertrend:+,.0f}원 ({price_difference_pct:+.1f}%)\n"
                formatted_text += f"    - {signal_description}\n"

            # RS (상대강도) 분석 - technical_analysis_data에서 rs_data 추출
            rs_data = technical_analysis_data.get("rs_data")
            if rs_data:
                rs_value = rs_data.get("rs")
                rs_1m = rs_data.get("rs_1m")
                rs_3m = rs_data.get("rs_3m")
                rs_6m = rs_data.get("rs_6m")
                sector = rs_data.get("sector")

                if rs_value is not None:
                    # market_rs를 기준으로 상대적 강도 판단
                    market_comparison = rs_data.get("market_comparison")
                    market_rs = None
                    if market_comparison:
                        market_rs = market_comparison.get("market_rs")

                    if market_rs is not None:
                        rs_diff = rs_value - market_rs
                        if rs_diff >= 18:
                            rs_status = "매우 강한 상대강도"
                            rs_signal = "강세"
                        elif rs_diff >= 10:
                            rs_status = "강한 상대강도"
                            rs_signal = "긍정"
                        elif rs_diff >= -5:
                            rs_status = "보통 상대강도"
                            rs_signal = "중립"
                        elif rs_diff >= -15:
                            rs_status = "약한 상대강도"
                            rs_signal = "부정"
                        else:
                            rs_status = "매우 약한 상대강도"
                            rs_signal = "약세"
                    else:
                        # market_rs가 없을 경우 기본값 62.5를 사용
                        default_market_rs = 62.5
                        rs_diff = rs_value - default_market_rs
                        if rs_diff >= 15:
                            rs_status = "매우 강한 상대강도"
                            rs_signal = "강세"
                        elif rs_diff >= 5:
                            rs_status = "강한 상대강도"
                            rs_signal = "긍정"
                        elif rs_diff >= -5:
                            rs_status = "보통 상대강도"
                            rs_signal = "중립"
                        elif rs_diff >= -15:
                            rs_status = "약한 상대강도"
                            rs_signal = "부정"
                        else:
                            rs_status = "매우 약한 상대강도"
                            rs_signal = "약세"

                    table_data.append(f"|RS (상대강도)|{rs_value:.1f}|{rs_signal}|{rs_status}|")
                    formatted_text += f"  RS (상대강도): {rs_value:.1f} - {rs_status}\n"

                    # 시간별 RS 추이
                    if rs_1m is not None or rs_3m is not None or rs_6m is not None:
                        formatted_text += f"    - 1개월 단위 RS : {rs_1m:.1f}, 3개월 단위 RS : {rs_3m:.1f}, 6개월 단위 RS : {rs_6m:.1f}\n"
                        formatted_text += "\n"

                    # 시장 비교 분석
                    market_comparison = rs_data.get("market_comparison")
                    if market_comparison:
                        market_code = market_comparison.get("market_code")
                        market_rs = market_comparison.get("market_rs")
                        if market_code and market_rs is not None:
                            rs_diff = rs_value - market_rs
                            if rs_diff > 10:
                                market_status = f"{market_code} 대비 강세"
                            elif rs_diff > 0:
                                market_status = f"{market_code} 대비 우위"
                            elif rs_diff > -10:
                                market_status = f"{market_code}와 비슷한 수준"
                            else:
                                market_status = f"{market_code} 대비 약세"

                            formatted_text += f"    - {market_code} 비교: RS {market_rs:.1f} vs 종목 RS {rs_value:.1f} ({market_status})\n"

                    # 상대적 강도 분석
                    relative_analysis = rs_data.get("relative_strength_analysis")
                    if relative_analysis:
                        vs_market = relative_analysis.get("vs_market")
                        if vs_market:
                            outperforming = vs_market.get("outperforming", False)
                            strength_level = vs_market.get("strength_level", "")
                            if outperforming:
                                formatted_text += f"    - 시장 아웃퍼폼: {strength_level}\n"
                            else:
                                formatted_text += f"    - 시장 언더퍼폼: {strength_level}\n"

                        # 시장별 특화 분석
                        market_specific = relative_analysis.get("market_specific_analysis")
                        if market_specific:
                            market_position = market_specific.get("market_position")
                            if market_position:
                                formatted_text += f"    - 시장 내 위치: {market_position}\n"

                    if sector:
                        formatted_text += f"    - 업종: {sector}\n"

                    if market_rs is not None:
                        formatted_text += f"    - 시장RS({market_rs:.1f}) 대비 +5 이상시 강세, -5 이하시 약세로 판단됩니다.\n"
                    else:
                        formatted_text += "    - 시장RS(평균 62.5) 대비 +5 이상시 강세, -5 이하시 약세로 판단됩니다.\n"
                    formatted_text += "    - 상대강도가 시장보다 높은 종목은 추세추종 전략에 유리합니다.\n"

            # 테이블 출력
            if table_data:
                for row in table_data:
                    formatted_text += row + "\n"
                formatted_text += "\n"

            # 종합적 지표 분석
            formatted_text += "종합적 지표 분석:\n"

            # 각 지표의 신호를 수집하고 종합 판단
            signals = []

            # RSI 신호
            if rsi is not None:
                if rsi < 30:
                    signals.append("매수")
                elif rsi > 70:
                    signals.append("매도")
                else:
                    signals.append("중립")

            # MACD 신호
            if macd is not None and macd_signal is not None:
                if macd > macd_signal:
                    if macd_histogram and macd_histogram > 0:
                        signals.append("매수")
                    else:
                        signals.append("중립")
                elif macd < macd_signal:
                    if macd_histogram and macd_histogram < 0:
                        signals.append("매도")
                    else:
                        signals.append("중립")
                else:
                    signals.append("중립")

            # 스토캐스틱 신호
            if stochastic_k is not None and stochastic_d is not None:
                if stochastic_k < 20 and stochastic_d < 20:
                    signals.append("매수")
                elif stochastic_k > 80 and stochastic_d > 80:
                    signals.append("매도")
                else:
                    signals.append("중립")

            # ADX 신호
            if adx is not None and adx_plus_di and adx_minus_di:
                if adx >= 70:
                    # ADX가 70 이상이면 과도한 추세 상태로 반전 위험이 있어 중립
                    signals.append("중립")
                elif adx >= 25:
                    if adx_plus_di > adx_minus_di:
                        signals.append("매수")
                    else:
                        signals.append("매도")
                else:
                    signals.append("중립")

            # # ADR 신호
            # if adr is not None:
            #     if adr > 1.2:
            #         signals.append("매수")
            #     elif adr < 0.8:
            #         signals.append("매도")
            #     else:
            #         signals.append("중립")

            # SuperTrend 신호
            if supertrend_direction is not None:
                if supertrend_direction == 1:
                    signals.append("매수")
                elif supertrend_direction == -1:
                    signals.append("매도")
                else:
                    signals.append("중립")

            # RS 신호
            rs_data = technical_analysis_data.get("rs_data")
            if rs_data:
                rs_value = rs_data.get("rs")
                if rs_value is not None:
                    # market_rs를 기준으로 신호 판단
                    market_comparison = rs_data.get("market_comparison")
                    market_rs = None
                    if market_comparison:
                        market_rs = market_comparison.get("market_rs")

                    if market_rs is not None:
                        rs_diff = rs_value - market_rs
                        if rs_diff >= 5:
                            signals.append("매수")
                        elif rs_diff >= -5:
                            signals.append("중립")
                        else:
                            signals.append("매도")
                    else:
                        # market_rs가 없을 경우 기본값 62.5를 사용
                        default_market_rs = 62.5
                        rs_diff = rs_value - default_market_rs
                        if rs_diff >= 5:
                            signals.append("매수")
                        elif rs_diff >= -5:
                            signals.append("중립")
                        else:
                            signals.append("매도")

            # 신호 종합
            if signals:
                buy_count = signals.count("매수")
                sell_count = signals.count("매도")
                neutral_count = signals.count("중립")
                total_signals = len(signals)

                formatted_text += f"  - 총 {total_signals}개 지표 중 매수 신호: {buy_count}개, 매도 신호: {sell_count}개, 중립: {neutral_count}개\n"

                if buy_count > sell_count and buy_count > neutral_count:
                    overall_signal = "매수 우세"
                    signal_strength = buy_count / total_signals * 100
                elif sell_count > buy_count and sell_count > neutral_count:
                    overall_signal = "매도 우세"
                    signal_strength = sell_count / total_signals * 100
                else:
                    overall_signal = "혼조 또는 중립"
                    signal_strength = max(buy_count, sell_count, neutral_count) / total_signals * 100

                formatted_text += f"  - 종합 신호: {overall_signal} (신호 강도: {signal_strength:.1f}%)\n"

            formatted_text += "\n"

        # 차트 패턴
        chart_patterns = technical_analysis_data.get("chart_patterns", {})
        if chart_patterns:
            formatted_text += "차트 패턴:\n"

            trend_direction = chart_patterns.get("trend_direction")
            trend_strength = chart_patterns.get("trend_strength")
            if trend_direction and trend_strength:
                formatted_text += f"  추세: {trend_direction} ({trend_strength})\n"

            support_levels = chart_patterns.get("support_levels", [])
            if support_levels:
                formatted_text += f"  지지선: {', '.join([f'{level:.0f}' for level in support_levels])}\n"

            resistance_levels = chart_patterns.get("resistance_levels", [])
            if resistance_levels:
                formatted_text += f"  저항선: {', '.join([f'{level:.0f}' for level in resistance_levels])}\n"

            patterns = chart_patterns.get("patterns", [])
            if patterns:
                formatted_text += f"  식별된 패턴: {', '.join(patterns)}\n"

            formatted_text += "\n"

            # 매매신호는 사용자에게 매수하라는 오해를 제공할수 있으니, 일단 제거
            # 매매 신호
            # trading_signals = technical_analysis_data.get("trading_signals", {})
            # if trading_signals:
            #     formatted_text += "매매 신호:\n"

            #     overall_signal = trading_signals.get("overall_signal")
            #     confidence = trading_signals.get("confidence", 0)
            #     if overall_signal:
            #         formatted_text += f"  종합 신호: {overall_signal} (신뢰도: {confidence:.2f})\n"

            #     # stop_loss = trading_signals.get("stop_loss")
            #     # target_price = trading_signals.get("target_price")
            #     # if stop_loss:
            #     #     formatted_text += f"  손절가: {stop_loss:.0f}원\n"
            #     # if target_price:
            #     #     formatted_text += f"  목표가: {target_price:.0f}원\n"

            #     signals = trading_signals.get("signals", [])
            #     if signals:
            #         formatted_text += "  개별 신호:\n"
            #         for signal in signals:
            #             indicator = signal.get("indicator", "")
            #             signal_type = signal.get("signal", "")
            #             reason = signal.get("reason", "")
            #             strength = signal.get("strength", 0)
            #             formatted_text += f"    {indicator}: {signal_type} ({reason}, 강도: {strength:.2f})\n"

            formatted_text += "\n"

        # 시장 정서
        market_sentiment = technical_analysis_data.get("market_sentiment", {})
        if market_sentiment:
            formatted_text += "시장 정서:\n"

            volume_trend = market_sentiment.get("volume_trend")
            if volume_trend:
                formatted_text += f"  거래량 추이: {volume_trend}\n"

            price_volume_relation = market_sentiment.get("price_volume_relation")
            if price_volume_relation:
                formatted_text += f"  가격-거래량 관계: {price_volume_relation}\n"

            formatted_text += "\n"

        # 차트 데이터 (최근 가격 동향)
        chart_data = technical_analysis_data.get("chart_data", [])
        if chart_data:
            formatted_text += "최근 주가 동향:\n"

            # 최근 10개 데이터만 표시
            recent_data = chart_data[-10:] if len(chart_data) > 10 else chart_data
            formatted_text += f"  데이터 기간: 최근 {len(recent_data)}일\n"

            if recent_data:
                # 첫 번째와 마지막 데이터로 변화율 계산
                first_close = recent_data[0].get("close") or 0
                last_close = recent_data[-1].get("close") or 0

                if first_close > 0:
                    change_rate = ((last_close - first_close) / first_close) * 100
                    formatted_text += f"  기간 변화율: {change_rate:+.2f}%\n"

                # 최고가, 최저가
                closes = [data.get("close") or 0 for data in recent_data if data.get("close")]
                if closes:
                    max_price = max(closes)
                    min_price = min(closes)
                    formatted_text += f"  기간 내 최고가: {max_price:,.0f}원\n"
                    formatted_text += f"  기간 내 최저가: {min_price:,.0f}원\n"

                # 최근 한달 데이터 상세
                recent_1month = recent_data[-22:] if len(recent_data) >= 3 else recent_data
                formatted_text += "  최근 한달 상세:\n"
                for data in recent_1month:
                    date = data.get("date", "")
                    normalized_date = format_date_for_chart(date)
                    close = data.get("close") or 0
                    volume = data.get("volume") or 0
                    formatted_text += f"    {normalized_date}: 종가 {close:,.0f}원, 거래량 {volume:,}주\n"

            formatted_text += "\n"

        # 수급 데이터 (투자주체별 거래현황)
        supply_demand_data = technical_analysis_data.get("supply_demand_data", [])
        if supply_demand_data:
            formatted_text += "투자주체별 거래현황:\n"

            # 최근 5개 데이터만 표시
            recent_supply_data = supply_demand_data[-10:] if len(supply_demand_data) > 10 else supply_demand_data
            formatted_text += f"  데이터 기간: 최근 {len(recent_supply_data)}일\n"
            # formatted_text += f"  데이터 단위: {unit}\n"
            if recent_supply_data:
                # 기간별 누적 매매대금 계산
                total_individual = 0
                total_foreign = 0
                total_institution = 0

                formatted_text += "  일별 수급 현황:\n"
                for data in recent_supply_data:
                    date = data.get("date", "")
                    normalized_date = format_date_for_chart(date)
                    individual = data.get("individual_investor", 0) or 0
                    foreign = data.get("foreign_investor", 0) or 0
                    institution = data.get("institution_total", 0) or 0

                    total_individual += individual
                    total_foreign += foreign
                    total_institution += institution

                    # 수급 데이터를 억원 단위로 표시 (원본 데이터는 백만원 단위)
                    formatted_text += f"    {normalized_date}: 개인 {individual / 100:+,.1f}억원, 외국인 {foreign / 100:+,.1f}억원, 기관 {institution / 100:+,.1f}억원\n"

                # 기간별 누적 요약
                formatted_text += "  기간별 누적 매매대금:\n"
                formatted_text += f"    개인투자자: {total_individual / 100:+,.1f}억원\n"
                formatted_text += f"    외국인투자자: {total_foreign / 100:+,.1f}억원\n"
                formatted_text += f"    기관투자자: {total_institution / 100:+,.1f}억원\n"

                # 주도 세력 분석
                abs_individual = abs(total_individual)
                abs_foreign = abs(total_foreign)
                abs_institution = abs(total_institution)

                max_amount = max(abs_individual, abs_foreign, abs_institution)
                if max_amount == abs_individual:
                    pass
                elif max_amount == abs_foreign:
                    pass
                else:
                    pass

                # formatted_text += f"  주도세력: {main_player} ({trend})\n"

            formatted_text += "\n"

        # 요약 및 권고사항
        summary = technical_analysis_data.get("summary", "")
        if summary:
            formatted_text += f"분석 요약:\n{summary}\n\n"

        # recommendations = technical_analysis_data.get("recommendations", [])
        # if recommendations:
        #     formatted_text += "투자 권고사항:\n"
        #     for i, rec in enumerate(recommendations, 1):
        #         formatted_text += f"  {i}. {rec}\n"
        #     formatted_text += "\n"

        return formatted_text

    def _format_price_chart(self, technical_analysis_data: Optional[Dict[str, Any]]) -> str:
        """
        차트 데이터를 간단한 배열 형태의 문자열로 변환합니다.

        Args:
            technical_analysis_data: 기술적 분석 결과 데이터

        Returns:
            포맷팅된 차트 데이터 문자열
        """
        if not technical_analysis_data:
            return "차트 데이터가 없습니다."

        chart_data = technical_analysis_data.get("chart_data", [])
        if not chart_data:
            return "차트 데이터가 없습니다."

        formatted_text = "--- 데이터소스: 차트데이터 ---\n\n"
        formatted_text += "**데이터 형식**: 날짜, 시가, 고가, 저가, 종가, 거래량, 등락률\n\n"
        formatted_text += "**가격 데이터**:\n"

        # 최근 5개월 차트
        recent_data = chart_data[-66:] if len(chart_data) > 66 else chart_data

        try:
            for data in recent_data:
                if isinstance(data, list) and len(data) >= 7:
                    # [날짜, Open, High, Low, Close, Volume, 등락률] 형태로 표시
                    formatted_text += f"{data}\n"
                elif isinstance(data, dict):
                    # dict 형태인 경우 배열로 변환
                    date = data.get("date", "")
                    normalized_date = format_date_for_chart(date)
                    open_price = data.get("open") or 0
                    high_price = data.get("high") or 0
                    low_price = data.get("low") or 0
                    close_price = data.get("close") or 0
                    volume = data.get("volume") or 0
                    price_change_percent = data.get("price_change_percent") or 0
                    formatted_text += f"{normalized_date},{open_price:.0f},{high_price:.0f},{low_price:.0f},{close_price:.0f},{volume:.0f},{price_change_percent:.1f}%\n"

        except Exception as e:
            logger.error(f"차트오류:{date} : {e}", exc_info=True)

        return formatted_text
