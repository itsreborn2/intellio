"""
요약 에이전트

이 모듈은 다양한 소스에서 검색된 정보를 통합하여 사용자 질문에 대한 요약된 응답을 생성하는 에이전트를 정의합니다.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
from loguru import logger
import asyncio
import json
import hashlib

from langchain_core.output_parsers import StrOutputParser

from stockeasy.models.agent_io import CompanyReportData
from stockeasy.services.financial.stock_info_service import StockInfoService
from stockeasy.prompts.summarizer_section_prompt import create_all_section_content, format_other_agent_data, PROMPT_GENERATE_SECTION_CONTENT
from common.models.token_usage import ProjectType
from stockeasy.prompts.summarizer_prompt import DEEP_RESEARCH_SYSTEM_PROMPT, create_prompt
from stockeasy.agents.base import BaseAgent
from sqlalchemy.ext.asyncio import AsyncSession
from common.core.config import settings
from common.services.agent_llm import get_agent_llm
from langchain_core.messages import  HumanMessage, SystemMessage
from stockeasy.prompts.telegram_prompts import format_telegram_messages


class SummarizerAgent(BaseAgent):
    """검색된 정보를 요약하는 에이전트"""
    
    def __init__(self, name: Optional[str] = None, db: Optional[AsyncSession] = None):
        """에이전트 초기화"""
        super().__init__(name, db)
        self.agent_llm = get_agent_llm("summarizer_agent")
        logger.info(f"SummarizerAgent initialized with provider: {self.agent_llm.get_provider()}, model: {self.agent_llm.get_model_name()}")
        # self.parser = StrOutputParser() # 직접 사용 안 함
        # self.prompt_template = DEEP_RESEARCH_SYSTEM_PROMPT # 직접 사용 안 함

    def _format_documents_for_section(self, reports: List[CompanyReportData]) -> str:
        """
        CompanyReportData 리스트를 LLM 프롬프트에 적합한 문자열로 변환합니다.
        (기존 common.agents.report_analyzer_agent.format_report_contents 와 유사하지만,
         SummarizerAgent에 맞게 커스터마이징 가능)
        """
        if not reports:
            return "해당 섹션에 대한 참고 자료가 없습니다."

        formatted_texts = []
        for i, report in enumerate(reports):
            text = f"\n--- 참고 자료 {i+1} ---\n"
            text += f"출처: {report.get('source', '미상')}\n"
            text += f"날짜: {report.get('publish_date', '날짜 정보 없음')}\n"
            if report.get('title') and report.get('title') != '제목 없음': # title이 유효하면 추가
                text += f"제목: {report.get('title')}\n"
            text += f"내용:\n{report.get('content', '내용 없음')}\n"
            formatted_texts.append(text)
        return "\n".join(formatted_texts)

    async def process(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        검색된 정보를 요약합니다.
        
        Args:
            state: 현재 상태 (query, classification, retrieved_data 등 포함)
            
        Returns:
            업데이트된 상태 (summary 추가)
        """
        try:
            query = state.get("query", "")
            stock_code = state.get("stock_code") 
            stock_name = state.get("stock_name") 
            
            agent_results = state.get("agent_results", {})
            report_analyzer_data = agent_results.get("report_analyzer", {}).get("data", {})
            
            main_query_reports: List[CompanyReportData] = report_analyzer_data.get("main_query_reports", [])
            toc_reports_data: Dict[str, List[CompanyReportData]] = report_analyzer_data.get("toc_reports", {})

            # 다른 에이전트 결과 데이터 포맷팅 (stock_code, stock_name 전달)
            other_agents_context_str = format_other_agent_data(
                agent_results, 
                stock_code=stock_code, 
                stock_name=stock_name
            )
            
            final_report_toc = state.get("final_report_toc") 

            if not query:
                state["errors"] = state.get("errors", []) + [{
                    "agent": self.get_name(),
                    "error": "질문이 제공되지 않았습니다.",
                    "type": "InvalidInputError",
                    "timestamp": datetime.now()
                }]
                state["processing_status"] = state.get("processing_status", {})
                state["processing_status"]["summarizer"] = "error"
                return state
            
            if not final_report_toc:
                state["errors"] = state.get("errors", []) + [{
                    "agent": self.get_name(),
                    "error": "동적 목차 정보(final_report_toc)가 없습니다.",
                    "type": "MissingDataError",
                    "timestamp": datetime.now()
                }]
                state["processing_status"] = state.get("processing_status", {})
                state["processing_status"]["summarizer"] = "error"
                return state
            
            if not main_query_reports and not toc_reports_data:
                logger.warning("[SummarizerAgent] 요약할 기업 리포트 정보가 없습니다 (메인 쿼리 및 TOC 결과 모두 부족). 다른 컨텍스트만으로 진행될 수 있습니다.")
                # 오류로 처리하지 않고 다른 컨텍스트만으로 진행할 수 있도록 허용 (사용자 피드백에 따라 변경 가능)
                # state["errors"] = state.get("errors", []) + [{
                #     "agent": self.get_name(),
                #     "error": "요약할 분석 정보가 없습니다 (ReportAnalyzer 결과 부족).",
                #     "type": "InsufficientDataError",
                #     "timestamp": datetime.now()
                # }]
                # state["processing_status"] = state.get("processing_status", {})
                # state["processing_status"]["summarizer"] = "error"
                # return state

        except Exception as e: # 데이터 준비 과정에서의 예외
            logger.exception(f"SummarizerAgent 정보 준비 중 오류 발생: {e}")
            state["errors"] = state.get("errors", []) + [{
                "agent": self.get_name(),
                "error": f"정보 준비 오류: {str(e)}",
                "type": type(e).__name__,
                "timestamp": datetime.now()
            }]
            state["processing_status"] = state.get("processing_status", {})
            state["processing_status"]["summarizer"] = "error"
            return state

        try:
            user_context = state.get("user_context", {})
            user_id = user_context.get("user_id", None)
            
            summary, summary_by_section = await self.generate_sectioned_summary(
                query=query, 
                user_id=user_id, 
                final_report_toc=final_report_toc,
                main_query_reports=main_query_reports,
                toc_reports_data=toc_reports_data,
                other_agents_context_str=other_agents_context_str, # 다른 에이전트 컨텍스트 전달
                stock_name=stock_name,
                stock_code=stock_code
            )
            
            state["summary"] = summary
            state["summary_by_section"] = summary_by_section
            state["processing_status"] = state.get("processing_status", {})
            state["processing_status"]["summarizer"] = "completed"
            
            return state
        except Exception as e:
            logger.exception(f"SummarizerAgent 요약 생성 중 오류 발생: {e}")
            state["errors"] = state.get("errors", []) + [{
                "agent": self.get_name(),
                "error": f"요약 생성 오류: {str(e)}",
                "type": type(e).__name__,
                "timestamp": datetime.now()
            }]
            state["processing_status"] = state.get("processing_status", {})
            state["processing_status"]["summarizer"] = "error"
            return state
        
    async def generate_sectioned_summary(self,
                                         query: str,
                                         user_id: str,
                                         final_report_toc: Dict[str, Any],
                                         main_query_reports: List[CompanyReportData],
                                         toc_reports_data: Dict[str, List[CompanyReportData]], # 키가 section_id 또는 subsection_id 임
                                         other_agents_context_str: str,
                                         stock_name: Optional[str] = None,
                                         stock_code: Optional[str] = None
                                         ):
        """
        동적 목차에 따라 섹션별로 요약을 생성하고 통합하는 함수.
        각 섹션에 맞는 필터링된 보고서 데이터를 사용하고, 다른 에이전트 컨텍스트를 포함하여 내용을 생성합니다.
        toc_reports_data의 키는 section_id 또는 subsection_id 입니다.
        """
        logger.info("[SummarizerAgent] 동적 목차 기반 섹션별 요약 생성 시작")
        
        toc_reports_summary_for_log = {k: len(v) for k, v in toc_reports_data.items()}
        logger.info(f"[SummarizerAgent] 전달받은 toc_reports_data (키: 리포트 수): {toc_reports_summary_for_log}")
        if not toc_reports_data:
            logger.warning("[SummarizerAgent] toc_reports_data가 비어있습니다.")

        section_tasks = []
        section_details_for_prompting = []

        toc_title = final_report_toc.get("title", "알 수 없는 제목의 보고서")
        toc_sections_from_generator = final_report_toc.get("sections", [])

        if not toc_sections_from_generator:
            logger.warning("[SummarizerAgent] 목차에 섹션 정보가 없습니다. 빈 보고서를 반환합니다.")
            return f"# {toc_title}\n\n목차에 정의된 섹션이 없어 보고서 내용을 생성할 수 없습니다.", {}

        # 1. "핵심 요약" (첫 번째 섹션) 처리
        if toc_sections_from_generator:
            first_section_data = toc_sections_from_generator[0]
            first_section_title = first_section_data.get("title", "핵심 요약")
            first_section_description = first_section_data.get("description", "보고서 전체의 주요 내용을 요약합니다.")
            
            all_reports_for_first_section_list: List[CompanyReportData] = list(main_query_reports)
            
            for reports_list in toc_reports_data.values():
                all_reports_for_first_section_list.extend(reports_list)
            
            logger.info(f"[SummarizerAgent] 핵심 요약: main_query_reports ({len(main_query_reports)}개)와 toc_reports_data 통합 후 리포트 수 (중복 제거 전): {len(all_reports_for_first_section_list)}개")

            # 합쳐진 전체 리스트에 대해 중복 제거
            seen_all_contents_for_first_section = set()
            final_deduplicated_list_for_first_section = []
            for report in all_reports_for_first_section_list:
                content_str = report.get("content", "")
                # content의 앞 100글자를 추출하여 해시
                content_prefix = content_str[:100]
                content_key = hashlib.sha256(content_prefix.encode('utf-8')).hexdigest()
                
                if content_key not in seen_all_contents_for_first_section:
                    seen_all_contents_for_first_section.add(content_key)
                    final_deduplicated_list_for_first_section.append(report)
            
            all_reports_for_first_section_list = final_deduplicated_list_for_first_section
            logger.info(f"[SummarizerAgent] 핵심 요약: 통합 리스트 중복 제거 후 최종 리포트 수: {len(all_reports_for_first_section_list)}개")

            formatted_report_docs_for_first_section = self._format_documents_for_section(all_reports_for_first_section_list)
            combined_context_for_first_section = f"{formatted_report_docs_for_first_section}\n\n{other_agents_context_str}"

            subsections_text_first = ""
            if first_section_data.get("subsections"):
                 subsections_text_first = "\n하위 섹션 목록:\n" + "\n".join([f" - {s.get('title', '')}" for s in first_section_data.get("subsections", [])])

            prompt_str_first = PROMPT_GENERATE_SECTION_CONTENT.format(
                query=query,
                section_title=first_section_title,
                section_description=first_section_description,
                subsections_info=subsections_text_first,
                all_analyses=combined_context_for_first_section,
            )
            messages_first = [HumanMessage(content=prompt_str_first)]
            task_first = asyncio.create_task(self.agent_llm.ainvoke_with_fallback(
                messages_first, user_id=user_id, project_type=ProjectType.STOCKEASY, db=self.db
            ))
            section_tasks.append(task_first)
            section_details_for_prompting.append({"title": first_section_title, "is_first_section": True})
            logger.info(f"[SummarizerAgent] '{first_section_title}' (첫 번째 섹션) 생성 작업 추가. 사용된 리포트 수: {len(all_reports_for_first_section_list)}") # 이미 위에서 로깅됨

        # 2. 나머지 섹션 처리
        for i, section_data in enumerate(toc_sections_from_generator):
            if i == 0:
                continue

            current_section_title = section_data.get("title", f"섹션 {i+1}")
            current_section_description = section_data.get("description", "")
            current_section_id = section_data.get("section_id")
            
            if not current_section_id:
                logger.warning(f"[SummarizerAgent] '{current_section_title}'에 section_id가 없습니다. 이 섹션을 건너뜁니다.")
                continue

            relevant_toc_reports_for_current_section_list: List[CompanyReportData] = []
            
            reports_for_current_section_id = toc_reports_data.get(current_section_id, [])
            relevant_toc_reports_for_current_section_list.extend(reports_for_current_section_id)
            logger.info(f"[SummarizerAgent] 섹션 ID '{current_section_id}' ('{current_section_title}')에 대한 toc_reports: {len(reports_for_current_section_id)}개")
            
            subsections = section_data.get("subsections", [])
            if isinstance(subsections, list):
                for sub_section_item in subsections:
                    if isinstance(sub_section_item, dict):
                        subsection_id = sub_section_item.get("subsection_id")
                        subsection_title = sub_section_item.get("title", "N/A")
                        if subsection_id:
                            reports_for_subsection_id = toc_reports_data.get(subsection_id, [])
                            relevant_toc_reports_for_current_section_list.extend(reports_for_subsection_id)
                            logger.info(f"[SummarizerAgent]   하위 섹션 ID '{subsection_id}' ('{subsection_title}')에 대한 toc_reports: {len(reports_for_subsection_id)}개")
            
            seen_contents = set()
            deduplicated_list = []
            for report in relevant_toc_reports_for_current_section_list:
                content_str = report.get("content", "")
                # content의 앞 100글자를 추출하여 해시
                content_prefix = content_str[:100]
                content_key = hashlib.sha256(content_prefix.encode('utf-8')).hexdigest()

                if content_key not in seen_contents:
                    seen_contents.add(content_key)
                    deduplicated_list.append(report)
            relevant_toc_reports_for_current_section_list = deduplicated_list
            
            logger.info(f"[SummarizerAgent] 섹션 '{current_section_title}' (ID: {current_section_id}) 최종 집계된 고유 리포트 수: {len(relevant_toc_reports_for_current_section_list)}")

            formatted_report_docs_for_current_section = self._format_documents_for_section(relevant_toc_reports_for_current_section_list)
            combined_context_for_current_section = f"{formatted_report_docs_for_current_section}\n\n{other_agents_context_str}"
            
            subsections_text_current = ""
            if subsections:
                 subsections_text_current = "\n하위 섹션 목록:\n" + "\n".join([f" - {s.get('title', '')} ({s.get('description','')})" for s in subsections])

            prompt_str_current = PROMPT_GENERATE_SECTION_CONTENT.format(
                query=query,
                section_title=current_section_title,
                section_description=current_section_description,
                subsections_info=subsections_text_current,
                all_analyses=combined_context_for_current_section
            )
            messages_current = [HumanMessage(content=prompt_str_current)]
            task_current = asyncio.create_task(self.agent_llm.ainvoke_with_fallback(
                messages_current, user_id=user_id, project_type=ProjectType.STOCKEASY, db=self.db
            ))
            section_tasks.append(task_current)
            section_details_for_prompting.append({"title": current_section_title, "is_first_section": False})

        results = await asyncio.gather(*section_tasks, return_exceptions=True)
        
        section_contents_map = {}
        final_report_parts = []

        for i, result_content in enumerate(results):
            original_section_title = section_details_for_prompting[i]["title"]
            is_first_section = section_details_for_prompting[i]["is_first_section"]
            numbered_section_title_for_report = f"{i+1}. {original_section_title}"

            if isinstance(result_content, Exception):
                logger.error(f"[SummarizerAgent] '{original_section_title}' 섹션 생성 실패: {str(result_content)}")
                section_text = f"*오류: '{original_section_title}' 섹션 내용을 생성하는 중 문제가 발생했습니다.*"
            else:
                section_text = result_content.content if hasattr(result_content, 'content') else str(result_content)
                logger.info(f"[SummarizerAgent] '{original_section_title}' 섹션 생성 완료 (길이: {len(section_text)})")
            
            section_contents_map[original_section_title] = section_text
            
            if section_text.strip().startswith("## ") and original_section_title in section_text.split('\n')[0]:
                final_report_parts.append(section_text)
            else:
                final_report_parts.append(f"## {numbered_section_title_for_report}\n{section_text}")

        final_summary = f"# {toc_title}\n\n"
        final_summary += "\n\n".join(final_report_parts)
        
        logger.info("[SummarizerAgent] 동적 목차 기반 섹션별 요약 통합 완료")
        return final_summary, section_contents_map
        
    
