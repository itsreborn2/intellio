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

from stockeasy.models.agent_io import CompanyReportData, RetrievedTelegramMessage
from stockeasy.services.financial.stock_info_service import StockInfoService
from stockeasy.prompts.summarizer_section_prompt import create_all_section_content, format_other_agent_data, PROMPT_GENERATE_SECTION_CONTENT, PROMPT_GENERATE_EXECUTIVE_SUMMARY
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

            #텔레그램은 toc_results, main_query_results. 기업리포트와는 키 이름이 다르다(toc_reports)
            telegram_data = agent_results.get("telegram_retriever", {}).get("data", {})
            toc_data_telegram_agent: Dict[str, List[RetrievedTelegramMessage]] = telegram_data.get("toc_results", {}) #텔레그램은 toc_results, main_query_results

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
            
            if not main_query_reports and not toc_data_report_agent:
                logger.warning("[SummarizerAgent] 요약할 기업 리포트 정보가 없습니다 (메인 쿼리 및 TOC 결과 모두 부족). 다른 컨텍스트만으로 진행될 수 있습니다.")

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
            #state["agent_results"]["financial_analyzer"]["competitor_info"] = competitor_info
            competitors_infos = state.get("agent_results", {}).get("financial_analyzer", {}).get("competitor_infos", [])
            
            summary, summary_by_section = await self.generate_sectioned_summary_v2(
                query=query, 
                user_id=user_id, 
                final_report_toc=final_report_toc,
                toc_data_company_report=toc_data_report_agent,
                toc_data_telegram_agent=toc_data_telegram_agent,
                other_agents_context_str=other_agents_context_str,
                competitors_infos=competitors_infos,
                stock_name=stock_name,
                stock_code=stock_code
            )
            
            state["summary"] = summary
            state["summary_by_section"] = summary_by_section
            state["processing_status"] = state.get("processing_status", {})
            state["processing_status"]["summarizer"] = "completed"
            logger.info(f"[SummarizerAgent] 요약 생성 완료: 소요시간 {datetime.now() - start_time_process}")
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
        
    async def generate_sectioned_summary_v2(self,
                                         query: str,
                                         user_id: str,
                                         final_report_toc: Dict[str, Any],
                                         toc_data_company_report: Dict[str, List[CompanyReportData]],
                                         toc_data_telegram_agent: Dict[str, List[RetrievedTelegramMessage]],
                                         other_agents_context_str: str,
                                         competitors_infos: List[Dict[str, Any]],
                                         stock_name: Optional[str] = None,
                                         stock_code: Optional[str] = None
                                         ):
        """
        동적 목차에 따라 섹션별로 요약을 생성하고 통합하는 함수 (v2: 핵심요약 후생성).
        1. "핵심 요약"을 제외한 나머지 섹션들을 병렬로 생성.
        2. 생성된 다른 섹션들의 내용을 바탕으로 "핵심 요약" 섹션을 생성.
        3. 모든 섹션 내용을 통합하여 최종 보고서와 섹션별 내용 맵을 반환.
        """
        logger.info("[SummarizerAgent] 동적 목차 기반 섹션별 요약 생성 시작 (v2: 핵심요약 후생성)")
        competitor_keywords = ["경쟁사", "경쟁업체", "경쟁기업", "라이벌", "경쟁자", "업계 경쟁", "경쟁 업체"]
        
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
            if i == 0: # "핵심 요약" 섹션은 나중에 처리
                continue

            current_section_title = section_data.get("title", f"섹션 {i+1}")
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
                subsections_text_current = "\n".join([f" - {s.get('title', '')}\n   섹션설명:({s.get('description','')})" for s in subsections])
                for sub_section_item in subsections:
                    if isinstance(sub_section_item, dict):
                        subsection_id = sub_section_item.get("subsection_id")
                        if subsection_id:
                            current_section_company_report.extend(toc_data_company_report.get(subsection_id, []))
                            current_section_telegram_msgs.extend(toc_data_telegram_agent.get(subsection_id, []))
            
            seen_contents = set()
            deduplicated_list_reports = []
            for report in current_section_company_report:
                content_key = hashlib.sha256(report.get("content", "")[:100].encode('utf-8')).hexdigest()
                if content_key not in seen_contents:
                    seen_contents.add(content_key)
                    deduplicated_list_reports.append(report)
            current_section_company_report = deduplicated_list_reports
            
            seen_telegram_msgs = set()
            deduplicated_list_tele_msgs = []
            for msg in current_section_telegram_msgs:
                msg_key = hashlib.sha256(msg.get("content", "")[:100].encode('utf-8')).hexdigest()
                if msg_key not in seen_telegram_msgs:
                    seen_telegram_msgs.add(msg_key)
                    deduplicated_list_tele_msgs.append(msg)
            current_section_telegram_msgs = deduplicated_list_tele_msgs
            
            logger.info(f"[SummarizerAgent] 섹션 '{current_section_title}' (ID: {current_section_id}, 목차인덱스 {i}) 최종 집계 - 고유 리포트: {len(current_section_company_report)}개, 고유 텔레그램: {len(current_section_telegram_msgs)}개")

            formatted_report_docs = self._format_documents_for_section(current_section_company_report)
            formatted_telegram_msgs = self._format_telegram_messages_for_section(current_section_telegram_msgs)
            
            combined_context_for_current_section = f"{formatted_report_docs}\n\n{formatted_telegram_msgs}\n\n{other_agents_context_str}"
            
            # 경쟁사 목차이면, 경쟁사의 최근 분기별 재무데이터 추가.
            if any(keyword in current_section_title.lower() for keyword in competitor_keywords):
                logger.info(f"[SummarizerAgent] 경쟁사 목차 - 경쟁사의 최근 분기별 재무데이터 추가")
                formatted_data = self._format_competitor_financial_data(competitors_infos)
                combined_context_for_current_section += f"\n<경쟁사 분기별 재무데이터>\n{formatted_data}\n</경쟁사 분기별 재무데이터>"

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
            other_section_tasks.append(task_current)
            other_section_details_for_llm_call.append({
                "title": current_section_title, 
                "original_toc_index": i,
            })

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
                processed_other_sections_data.append({
                    "details": section_detail,
                    "text": f"*오류: '{original_section_title}' 섹션 내용을 생성하는 중 문제가 발생했습니다: {str(raw_result)}*"
                })
                continue
            
            section_text_content = raw_result.content if hasattr(raw_result, 'content') else str(raw_result)
            logger.info(f"[SummarizerAgent] '{original_section_title}' (목차인덱스 {section_detail['original_toc_index']}) 생성 완료 (길이: {len(section_text_content)})")
            
            #generated_texts_for_summary_input.append(f"## {original_section_title}\n{section_text_content}")
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

            summary_section_description = first_section_data_for_summary.get("description", "보고서 전체의 주요 내용을 요약합니다.")
            summary_subsections_info = "" 
            summary_section_subsections = first_section_data_for_summary.get("subsections", [])
            if isinstance(summary_section_subsections, list) and summary_section_subsections:
                 summary_subsections_info = "\n이 핵심 요약 섹션이 다룰 수 있는 하위 주제 목록:\n" + "\n".join([f" - {s.get('title', '')} ({s.get('description','')})" for s in summary_section_subsections])

            # 핵심 요약 프롬프트 사용
            prompt_str_summary = PROMPT_GENERATE_EXECUTIVE_SUMMARY.format(
                original_query=query, # 원본 사용자 질문
                report_title=toc_title, # 보고서 전체 제목
                section_title=summary_section_title, # 현재 섹션 제목 ("핵심 요약")
                # section_description은 EXECUTIVE_SUMMARY 프롬프트에 없음
                # subsections_info도 EXECUTIVE_SUMMARY 프롬프트에 없음
                sections_summary=context_for_summary_llm, # 다른 섹션들의 생성된 내용 + 기타 참고자료
            )
            messages_summary = [HumanMessage(content=prompt_str_summary)]
            
            logger.info(f"[SummarizerAgent] '{summary_section_title}' 생성 작업 시작 (PROMPT_GENERATE_EXECUTIVE_SUMMARY 사용). 컨텍스트 길이(근사치): {len(context_for_summary_llm)}")
            try:
                result_summary_section_raw = await self.agent_llm.ainvoke_with_fallback(
                    messages_summary, user_id=user_id, project_type=ProjectType.STOCKEASY, db=self.db
                )
                if isinstance(result_summary_section_raw, Exception):
                    logger.error(f"[SummarizerAgent] '{summary_section_title}' 생성 실패 (LLM 호출 결과가 예외 객체): {str(result_summary_section_raw)}")
                    summary_section_content_str = "*핵심 요약 생성 중 오류가 발생했습니다.*"
                elif hasattr(result_summary_section_raw, 'content'):
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
        numbered_summary_title_for_report = f"{first_section_data_for_summary.get('original_toc_index', 0) + 1}. {summary_section_title}"
        
        section_contents_map[summary_section_title] = summary_section_content_str
        #final_report_parts.append(f"## {numbered_summary_title_for_report}\n{summary_section_content_str}")
        final_report_parts.append(summary_section_content_str)

        # 나머지 섹션들 추가 (목차 순서대로)
        for item in processed_other_sections_data:
            details = item["details"]
            text_content = item["text"]
            section_title_from_details = details["title"]
            
            numbered_section_title_for_report = f"{details['original_toc_index'] + 1}. {section_title_from_details}"
            
            section_contents_map[section_title_from_details] = text_content
            #final_report_parts.append(f"## {numbered_section_title_for_report}\n{text_content}")
            final_report_parts.append(text_content)
        section_contents_map['면책조항'] = "본 보고서는 투자 참고 자료로만 활용하시기 바라며, 특정 종목의 매수 또는 매도를 권유하지 않습니다. 보고서의 내용이 사실과 다른 내용이 일부 존재할 수 있으니 참고해 주시기 바랍니다. 투자 결정은 투자자 본인의 책임하에 이루어져야 하며, 본 보고서에 기반한 투자로 인한 손실에 대해 작성자와 당사는 어떠한 법적 책임도 지지 않습니다. 모든 투자에는 위험이 수반되므로 투자 전 투자자 본인의 판단과 책임하에 충분한 검토가 필요합니다."
        final_report_parts.append(section_contents_map['면책조항'])

        final_summary_md = f"# {toc_title}\n\n"
        final_summary_md += "\n\n".join(final_report_parts)
        #final_summary_md += "\n\n**면책조항**\n\n본 보고서는 투자 참고 자료로만 활용하시기 바라며, 특정 종목의 매수 또는 매도를 권유하지 않습니다. 보고서의 내용이 사실과 다른 내용이 일부 존재할 수 있으니 참고해 주시기 바랍니다. 투자 결정은 투자자 본인의 책임하에 이루어져야 하며, 본 보고서에 기반한 투자로 인한 손실에 대해 작성자와 당사는 어떠한 법적 책임도 지지 않습니다. 모든 투자에는 위험이 수반되므로 투자 전 투자자 본인의 판단과 책임하에 충분한 검토가 필요합니다."

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

        formatted_texts = []
        text = "<기업리포트>\n"
        for i, report in enumerate(reports):
            text += f" <자료 {i+1}>\n"
            text += f"출처: {report.get('source', '미상')}\n"
            text += f"날짜: {report.get('publish_date', '날짜 정보 없음')}\n"
            # if report.get('title') and report.get('title') != '제목 없음': # title이 유효하면 추가
            #     text += f"제목: {report.get('title')}\n"
            sContent = report.get('content', '내용 없음')
            sContent = sContent.replace("\n\n", "\n")
            text += f"내용:\n{sContent}\n"
            formatted_texts.append(text)
            text += f" </자료 {i+1}>\n"
        text += "</기업리포트>"
        return text
    
    def _format_telegram_messages_for_section(self, messages: List[RetrievedTelegramMessage]) -> str:
        """
        RetrievedTelegramMessage 리스트를 LLM 프롬프트에 적합한 문자열로 변환합니다.
        """
        if not messages:
            return "해당 섹션에 대한 내부DB 참고 자료가 없습니다."
        
        formatted_texts = []
        text = "<내부DB>"
        for i, message in enumerate(messages):
            text += f"\n<자료 {i+1}>\n"
            
            # ISO 형식의 날짜를 년-월-일 형식으로 변환
            created_at = message.get('message_created_at', '')
            formatted_date = '날짜 정보 없음'
            
            if created_at:
                try:
                    dt_obj = datetime.fromisoformat(created_at)
                    formatted_date = dt_obj.strftime('%Y-%m-%d')
                except (ValueError, TypeError):
                    # 날짜 변환 실패 시 원본 값 사용
                    formatted_date = created_at
            
            text += f"날짜: {formatted_date}\n"
            #text += f"채널: {message.get('channel_name', '채널 정보 없음')}\n"
            text += f"내용: {message.get('content', '내용 없음')}\n"
            text += f"</자료 {i+1}>\n"
        text += "</내부DB>"
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
                formatted_data += f"## {stock_name} ({stock_code}) 분기별 재무 데이터\n\n"
                
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
        
    
