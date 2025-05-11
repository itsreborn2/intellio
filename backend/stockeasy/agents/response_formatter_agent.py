"""
응답 포맷터 에이전트 모듈

이 모듈은 통합된 지식 정보를 사용자에게 이해하기 쉬운 
형태로 포맷팅하는 응답 포맷터 에이전트 클래스를 구현합니다.
"""

import json
import re
from loguru import logger
from typing import Dict, Any, List, Optional, Callable, AsyncGenerator
import asyncio

from langchain_core.messages import HumanMessage, AIMessage
from common.utils.util import remove_json_block
from common.services.agent_llm import get_agent_llm, get_llm_for_agent
from stockeasy.prompts.response_formatter_prompts import FRIENDLY_RESPONSE_FORMATTER_SYSTEM_PROMPT, FRIENDLY_RESPONSE_FORMATTER_SYSTEM_PROMPT2, format_response_formatter_prompt
from langchain_core.output_parsers import StrOutputParser
from common.models.token_usage import ProjectType
from stockeasy.agents.base import BaseAgent
from sqlalchemy.ext.asyncio import AsyncSession
from common.schemas.chat_components import (
    HeadingComponent, ParagraphComponent, ListComponent, ListItemComponent,
    CodeBlockComponent, BarChartComponent, LineChartComponent, ImageComponent,
    TableComponent, TableHeader, TableData, BarChartData, LineChartData
)
from langchain_core.tools import tool

class ResponseFormatterAgent(BaseAgent):
    """
    최종 응답을 형식화하는 에이전트
    
    이 에이전트는 knowledge_integrator 또는 summarizer의 결과를 받아
    사용자 친화적인 형태로 가공합니다.
    """
    
    def __init__(self, name: Optional[str] = None, db: Optional[AsyncSession] = None):
        """
        응답 형식화 에이전트 초기화
        
        Args:
            name: 에이전트 이름 (지정하지 않으면 클래스명 사용)
            db: 데이터베이스 세션 객체 (선택적)
        """
        super().__init__(name, db)
        #self.llm, self.model_name, self.provider = get_llm_for_agent("response_formatter_agent")
        self.agent_llm = get_agent_llm("response_formatter_agent")
        self.agent_llm_lite = get_agent_llm("gemini-lite")
        logger.info(f"ResponseFormatterAgent initialized with provider: {self.agent_llm.get_provider()}, model: {self.agent_llm.get_model_name()}")
        self.parser = StrOutputParser()
        self.prompt_template = FRIENDLY_RESPONSE_FORMATTER_SYSTEM_PROMPT

    async def _process_section_async(self, section_data: Dict[str, Any], summary_by_section: Dict[str, str], llm_with_tools: Any, tools: List[Callable], section_content_fallback: str) -> tuple[List[Dict[str, Any]], str, str]:
        """
        개별 섹션을 비동기적으로 처리하여 컴포넌트와 포맷된 텍스트를 생성합니다.
        반환값: (생성된 컴포넌트 리스트, 해당 섹션의 LLM 텍스트 응답, 섹션 제목)
        """
        section_title = section_data.get("title")
        section_components = []
        # 이 섹션 내에서 LLM이 생성한 순수 텍스트 (툴 콜 없이 반환된 내용)
        llm_generated_text_for_section = ""

        if not section_title:
            logger.warning("ResponseFormatterAgent (async): 목차에 제목 없는 섹션 데이터가 있습니다.")
            return [], "", ""

        if section_title in summary_by_section and summary_by_section[section_title]:
            section_content = summary_by_section[section_title]
            
            # 본문에 섹션 제목이 있으니, 여기서는 추가하지 않음.
            # 1. 섹션 제목 컴포넌트 추가 (항상 추가)  
            # section_heading_component = create_heading({"level": 2, "content": section_title})
            #section_components.append(section_heading_component)
            
            # 2. 섹션 내용에 대한 구조화된 컴포넌트 생성 시도
            tool_calling_prompt = f"""
다음 섹션의 내용을 구조화된 컴포넌트로 변환하세요:

<섹션 제목>
{section_title}
</섹션 제목>

<섹션 내용>
{section_content}
</섹션 내용>

해당 내용을 분석하여 다음 컴포넌트들을 적절히 사용해 구조화하세요:
- create_heading: 각 상/하위 섹션 제목(넘버링 반드시 포함, ||level=2(1. 2. 3. 등)||level=3(1.1 1.2 2.1 등)||level=4(넘버링되지 않은 헤딩)||). 마크다운 문법으로 명확하게 헤딩 # 이 있는 경우에만 heading으로 처리합니다.
- create_paragraph: 일반 텍스트 단락. 텍스트 내에 강조문법, 마크다운 볼드체(**text** 또는 __text__)가 있다면 그대로 컴포넌트의 내용에 포함시키세요. 짧은 용어나 구문 뒤에 콜론이 오는 경우 (예: '성장 잠재력:', '핵심 요약:')는 헤딩이 아니라 별도의 단락으로 처리해야 합니다.
- create_list: 순서 있는/없는 목록. 각 목록 아이템의 텍스트 내에 강조문법, 마크다운 볼드체(**text** 또는 __text__)가 있다면 그대로 컴포넌트의 내용에 포함시키세요.
- create_table: 표 형식 데이터 (실적 등)
- create_bar_chart: 바 차트로 표현할 수 있는 데이터 (예: 매출액 추이, 실적 추이, 실적 예상, 분기별 실적, 월별 데이터 등)
- create_line_chart: 선 차트로 표현할 수 있는 데이터(주가 데이터, 추세, 추이)

표, 차트, 목록 등은 내용에 적합한 경우에만 사용하세요.
섹션 제목은 이미 추가되었으니 다시 추가하지 마세요.
주의: 마크다운 볼드체(**text** 또는 __text__)는 반드시 컴포넌트의 실제 내용 값에 포함되어야 합니다. 예를 들어, "목록 아이템 **중요**"는 "목록 아이템 **중요**"로 그대로 출력해야 합니다.
"""
            try:
                section_response = await llm_with_tools.ainvoke(input=tool_calling_prompt)
                
                llm_generated_text_for_section = section_response.content if hasattr(section_response, 'content') else ""
                
                if hasattr(section_response, 'tool_calls') and section_response.tool_calls:
                    for tool_call in section_response.tool_calls:
                        tool_name = tool_call["name"]
                        tool_args = tool_call["args"]
                        
                        if 'level' in tool_args and isinstance(tool_args['level'], float):
                            tool_args['level'] = int(tool_args['level'])
                        
                        tool_func = next((t for t in tools if t.name == tool_name), None)
                        
                        if tool_func:
                            component_dict = tool_func.invoke(tool_args)
                            
                            if component_dict.get("type") == "heading":
                                heading_content_candidate = component_dict.get("content", "").strip()
                                if heading_content_candidate.startswith('**'):
                                    logger.info(f"Heading candidate '{heading_content_candidate}' starts with **. Converting to ParagraphComponent.")
                                    paragraph_tool_func = next((t for t in tools if t.name == "create_paragraph"), None)
                                    if paragraph_tool_func:
                                        component_dict = paragraph_tool_func.invoke({"content": heading_content_candidate})
                                    else:
                                        logger.warning("create_paragraph tool not found. Manually creating ParagraphComponent.")
                                        component_dict = ParagraphComponent({"content":heading_content_candidate}).dict()
                                else:
                                    level_3_match = re.match(r"(\d+)\.(\d+)\.?\s*(.*)", heading_content_candidate)
                                    level_2_match = re.match(r"(\d+)\.?\s*(.*)", heading_content_candidate)
                                    if level_3_match: component_dict["level"] = 3
                                    elif level_2_match: component_dict["level"] = 2

                                    if heading_content_candidate.startswith('# '):
                                        heading_content_candidate = heading_content_candidate[2:]
                                    elif heading_content_candidate.startswith('## '):
                                        heading_content_candidate = heading_content_candidate[3:]
                                    elif heading_content_candidate.startswith('### '):
                                        heading_content_candidate = heading_content_candidate[4:]

                            section_components.append(component_dict)
                
                elif llm_generated_text_for_section.strip(): # 툴 콜 없이 텍스트만 반환된 경우
                    logger.info(f"ResponseFormatterAgent (async): 섹션 '{section_title}'에 대해 Tool calling 없이 일반 텍스트 응답을 받았습니다.")
                    cleaned_text = remove_json_block(llm_generated_text_for_section)
                    if cleaned_text.strip():
                         section_components.append(create_paragraph({"content": cleaned_text}))
                
                # 성공적으로 처리되면 (툴콜이 있든 없든) 컴포넌트들과 LLM 텍스트, 제목 반환
                return section_components, llm_generated_text_for_section, section_title

            except Exception as e:
                logger.error(f"비동기 섹션 '{section_title}' 컴포넌트 생성 중 오류: {str(e)}")
                # 오류 발생 시, 이미 추가된 섹션 제목 컴포넌트 외에 원본 내용을 단락으로 추가
                section_components.append(create_paragraph({"content": section_content_fallback}))
                # 오류 시 LLM 생성 텍스트는 없고, 원본 내용을 텍스트로 반환 (오류 복구용)
                return section_components, section_content_fallback, section_title
        else: # summary_by_section에 내용이 없는 경우
            logger.info(f"ResponseFormatterAgent (async): 섹션 '{section_title}'에 대한 내용이 summary_by_section에 없습니다. 빈 컴포넌트를 반환합니다.")
            # 제목 컴포넌트만 있는 리스트와 빈 텍스트, 제목 반환
            return [create_heading({"level": 2, "content": section_title})], "", section_title

    async def process(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        통합된 정보를 기반으로 사용자에게 이해하기 쉬운 응답을 생성합니다.
        
        Args:
            state: 현재 상태 정보를 포함하는 딕셔너리
            
        Returns:
            업데이트된 상태 딕셔너리
        """
        try:
            # 현재 사용자 쿼리 및 종목 정보 추출
            query = state.get("query", "")
            stock_code = state.get("stock_code")
            stock_name = state.get("stock_name")
            
            # 통합된 응답 및 인사이트 추출
            integrated_knowledge = state.get("integrated_knowledge", {})
            # integrated_response = integrated_knowledge.get("integrated_response", state.get("integrated_response", "")) # 사용되지 않음
            # core_insights = integrated_knowledge.get("core_insights", []) # 사용되지 않음
            
            # analysis = integrated_knowledge.get("analysis", {}) # 사용되지 않음
            # confidence_assessment = analysis.get("confidence_assessment", {}) # 사용되지 않음
            # uncertain_areas = analysis.get("uncertain_areas", []) # 사용되지 않음
            
            logger.info(f"ResponseFormatterAgent formatting response for query: {query}")
            
            # 요약 및 섹션별 요약 가져오기
            summary = state.get("summary", "")
            summary_by_section = state.get("summary_by_section", {})
            final_report_toc = state.get("final_report_toc") # 동적 목차 정보 가져오기
            
            processing_status = state.get("processing_status", {})
            summarizer_status = processing_status.get("summarizer", "not_started")

            context_response_agent = state["agent_results"].get("context_response_agent", {})
            context_based_answer = ""
            if context_response_agent:
                context_based_answer = context_response_agent.get("answer", "")
                summary = context_based_answer # summary를 context_based_answer로 덮어쓰기
            
            # 통합된 응답이 없는 경우 처리
            if not context_based_answer and (not summary or summarizer_status != "completed"):
                logger.warning(f"No summary response available.")
                logger.warning(f"processing_status: {processing_status}")
                logger.warning(f"Summarizer status: {summarizer_status}")
                state["formatted_response"] = "죄송합니다. 현재 요청에 대한 정보를 찾을 수 없습니다. 다른 질문을 해 주시거나 나중에 다시 시도해 주세요."
                state["answer"] = "죄송합니다. 현재 요청에 대한 정보를 찾을 수 없습니다. 다른 질문을 해 주시거나 나중에 다시 시도해 주세요."
                state["components"] = []
                return state
            
            # Tool Calling 설정
            tools = [
                create_heading,
                create_paragraph,
                create_list,
                create_table,
                create_bar_chart,
                create_line_chart,
                create_image
            ]
            
            llm_with_tools = self.agent_llm_lite.get_llm().bind_tools(tools)

            all_components = []
            formatted_response_parts = [] # 최종 문자열 응답을 위한 조각들

            if not final_report_toc or not final_report_toc.get("sections"):
                logger.warning("ResponseFormatterAgent: 동적 목차 정보(final_report_toc)가 없거나 섹션이 비어있습니다. 기본 처리를 시도합니다.")
                if summary:
                    state["formatted_response"] = summary # make_full_components는 state의 formatted_response를 사용
                    all_components_fallback = await self.make_full_components(state)
                    all_components = [comp.dict() for comp in all_components_fallback if hasattr(comp, 'dict')]
                    formatted_response_parts.append(summary)
                else:
                    state["formatted_response"] = "죄송합니다. 보고서 목차 정보를 찾을 수 없어 내용을 생성할 수 없습니다."
                    state["answer"] = state["formatted_response"]
                    state["components"] = []
                    return state
            else: # 동적 목차가 있는 경우
                report_title = final_report_toc.get("title")
                if not report_title: # final_report_toc에 title이 없는 경우 대비
                    report_title = f"{stock_name}({stock_code}) 분석 리포트" if stock_name and stock_code else "주식 분석 리포트"

                # 보고서 전체 제목 컴포넌트 및 텍스트 추가
                title_component = create_heading({"level": 1, "content": report_title})
                all_components.append(title_component)
                formatted_response_parts.append(f"# {report_title}\n\n")
                
                toc_sections = final_report_toc.get("sections", [])
                
                tasks = []
                for section_data_item in toc_sections: # 변수명 변경 (section_data -> section_data_item)
                    section_title_for_task = section_data_item.get("title")
                    # fallback content는 해당 섹션의 원본 요약 내용
                    section_content_fallback_for_task = summary_by_section.get(section_title_for_task, "")
                    tasks.append(self._process_section_async(
                        section_data_item, 
                        summary_by_section, 
                        llm_with_tools, 
                        tools,
                        section_content_fallback_for_task
                    ))
                
                # section_results_with_exceptions: List[Union[Tuple[List[Dict], str, str], Exception]]]
                section_results_with_exceptions = await asyncio.gather(*tasks, return_exceptions=True)

                for i, res_or_exc in enumerate(section_results_with_exceptions):
                    original_section_data = toc_sections[i] # 순서대로 매칭
                    processed_section_title_from_res = "" # 결과에서 가져올 제목

                    if isinstance(res_or_exc, Exception):
                        # 병렬 작업에서 예외 발생 시
                        current_section_title = original_section_data.get("title", f"제목 없는 섹션 {i+1}")
                        logger.error(f"섹션 '{current_section_title}' 처리 중 병렬 작업 오류: {res_or_exc}")
                        
                        # 오류난 섹션의 제목 컴포넌트와 텍스트 추가
                        all_components.append(create_heading({"level": 2, "content": current_section_title}))
                        formatted_response_parts.append(f"## {current_section_title}\n\n")
                        
                        # 오류 시 대체 컨텐츠 (원본 요약)
                        error_fallback_content = summary_by_section.get(current_section_title, "이 섹션의 내용을 불러오는 데 실패했습니다.")
                        all_components.append(create_paragraph({"content": error_fallback_content}))
                        formatted_response_parts.append(error_fallback_content + "\n\n")
                        
                    elif res_or_exc: 
                        # 정상 결과: (components_from_section, llm_text_for_section, processed_section_title)
                        components_from_section, llm_text_for_section, processed_section_title_from_res = res_or_exc
                        
                        # _process_section_async는 항상 섹션 제목을 포함한 컴포넌트를 반환
                        all_components.extend(components_from_section) 
                        
                        if processed_section_title_from_res: # 제목이 있는 섹션만 텍스트 추가
                            # formatted_response_parts 에는 섹션 제목 텍스트를 여기서 추가
                            # (단, components_from_section 에 이미 제목 컴포넌트가 있으므로 중복 추가되지 않도록 주의)
                            # _process_section_async에서 컴포넌트 리스트의 첫번째가 제목이므로, 여기서는 제목 텍스트만 추가.

                            #formatted_response_parts.append(f"## {processed_section_title_from_res}\n\n") # 제목이 본문에 포함되어 있으므로, 제거

                            # LLM이 생성한 텍스트 (툴 콜이 없었을 경우) 또는 툴 콜 오류 시 fallback 텍스트
                            if llm_text_for_section.strip():
                                formatted_response_parts.append(llm_text_for_section + "\n\n")
                            # 만약 llm_text_for_section이 비어있고 components_from_section에 내용이 있다면,
                            # (즉, 툴콜링으로만 컴포넌트가 만들어진 경우) 해당 텍스트는 이미 컴포넌트로 변환되었으므로 추가 텍스트 불필요.
            
            # 최종 formatted_response 조합
            formatted_response = "".join(formatted_response_parts).strip()

            # 컴포넌트가 제목 외에 없는 경우 (모든 섹션 내용이 없거나 파싱 실패)
            if len(all_components) <= 1: # 보고서 전체 제목 컴포넌트만 있는 경우
                logger.warning("ResponseFormatterAgent: 동적 목차 기반 컴포넌트 생성 결과가 거의 비어있습니다. 기존 요약(summary)으로 대체 처리를 시도합니다.")
                if summary: 
                    state["formatted_response"] = summary 
                    all_components_fallback = await self.make_full_components(state)
                    all_components = [comp.dict() for comp in all_components_fallback if hasattr(comp, 'dict')]
                    formatted_response = summary 
                else: 
                    logger.warning("ResponseFormatterAgent: 대체할 summary 내용도 없습니다.")
                    # 이미 title 컴포넌트는 추가되어 있을 수 있음
                    if not any(comp.get("type") == "paragraph" for comp in all_components): # 내용이 전혀 없는 경우
                         all_components.append(create_paragraph({"content": "보고서 내용을 생성하지 못했습니다."}))
                    if not formatted_response: # 텍스트 응답도 비어있다면
                         formatted_response = "보고서 내용을 생성하지 못했습니다."

            # 결과 저장
            state["formatted_response"] = formatted_response
            state["answer"] = formatted_response 
            state["components"] = all_components
            
            # 처리 상태 업데이트
            state["processing_status"] = state.get("processing_status", {})
            state["processing_status"]["response_formatter"] = "completed"
            
            return state
            
        except Exception as e:
            logger.exception(f"Error in ResponseFormatterAgent: {str(e)}")
            state["error"] = f"응답 포맷터 에이전트 오류: {str(e)}"
            state["formatted_response"] = "죄송합니다. 응답을 포맷팅하는 중 오류가 발생했습니다."
            state["answer"] = state["formatted_response"]
            state["components"] = [] # 오류 시 컴포넌트 초기화
            return state 
        
    async def make_components(self, markdown_context:str):

        components = []
        # 마크다운을 줄 단위로 분리
        lines = markdown_context.split('\n')
        
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            
            # 빈 줄 건너뛰기
            if not line:
                i += 1
                continue
            
            # 1. 헤딩 처리 (# 헤딩)
            heading_match = re.match(r'^(#{1,6})\s+(.+)$', line)
            if heading_match:
                level = len(heading_match.group(1))
                content = heading_match.group(2).strip()
                components.append(HeadingComponent(
                    level=level,
                    content=content
                ))
                i += 1
                continue
            
            # 2. 테이블 처리 (| 구분 | 컬럼1 | 컬럼2 | ... |)
            if line.startswith('|') and '|' in line[1:]:
                # 테이블 시작 감지
                table_lines = []
                table_title = ""
                
                # 테이블 제목이 있는지 확인 (이전 줄이 단락이고 테이블에 관한 내용인 경우)
                if i > 0 and components and components[-1].type == 'paragraph':
                    paragraph_content = components[-1].content
                    if '표' in paragraph_content or '데이터' in paragraph_content or '재무' in paragraph_content:
                        table_title = paragraph_content
                        # 이미 추가된 제목 단락을 제거 (테이블 컴포넌트에 제목으로 포함될 예정)
                        components.pop()
                
                # 테이블 줄 수집
                while i < len(lines) and lines[i].strip().startswith('|'):
                    table_lines.append(lines[i].strip())
                    i += 1
                
                # 테이블 파싱 시도
                try:
                    # 최소 2줄 이상 있어야 테이블로 인식 (헤더, 구분선)
                    if len(table_lines) >= 2:
                        # 헤더 파싱
                        header_line = table_lines[0]
                        header_cells = [cell.strip() for cell in header_line.split('|')[1:-1]]
                        
                        # 구분선 확인 (두 번째 줄이 구분선인지 확인)
                        separator_line = table_lines[1]
                        # 구분선이 있으면 테이블로 처리
                        if any('-' in cell for cell in separator_line.split('|')[1:-1]):
                            # 데이터 행 파싱
                            data_rows = []
                            # 구분선 다음 줄부터 데이터 행
                            for row_line in table_lines[2:]:
                                row_cells = [cell.strip() for cell in row_line.split('|')[1:-1]]
                                if len(row_cells) == len(header_cells):
                                    row_data = {}
                                    for idx, _ in enumerate(header_cells):
                                        # 숫자 데이터인 경우 숫자로 변환 시도
                                        cell_value = row_cells[idx] if idx < len(row_cells) else ""
                                        try:
                                            # 콤마 제거 후 숫자 변환 시도
                                            cell_value_clean = cell_value.replace(',', '')
                                            if '.' in cell_value_clean and cell_value_clean.replace('.', '').replace('-', '').isdigit():
                                                cell_value = float(cell_value_clean)
                                            elif cell_value_clean.replace('-', '').isdigit():
                                                cell_value = int(cell_value_clean)
                                        except (ValueError, TypeError):
                                            # 숫자 변환 실패 시 텍스트 그대로 사용
                                            pass
                                        row_data[f"col{idx}"] = cell_value
                                    data_rows.append(row_data)
                            
                            # 테이블 컴포넌트 생성
                            # 데이터 행이 비어있더라도 테이블 컴포넌트 생성
                            table_component = TableComponent(
                                title=table_title,
                                data=TableData(
                                    headers=[TableHeader(key=f"col{idx}", label=header) for idx, header in enumerate(header_cells)],
                                    rows=data_rows if data_rows else [{}]
                                )
                            )
                            components.append(table_component)
                            continue
                except Exception as e:
                    logger.error(f"테이블 파싱 오류: {e}")
                    # 테이블 파싱 실패 시에도 테이블 컴포넌트로 처리
                    try:
                        # 간단한 테이블 컴포넌트로 변환 시도
                        if len(table_lines) >= 2:
                            header_line = table_lines[0]
                            header_cells = [cell.strip() for cell in header_line.split('|')[1:-1]]
                            
                            # 기본 빈 데이터라도 테이블 컴포넌트 생성
                            table_component = TableComponent(
                                title=table_title,
                                data=TableData(
                                    headers=[TableHeader(key=f"col{idx}", label=header) for idx, header in enumerate(header_cells)],
                                    rows=[{}]
                                )
                            )
                            components.append(table_component)
                            continue
                    except Exception as e2:
                        logger.error(f"테이블 컴포넌트 생성 오류: {e2}")
                
                # 위의 모든 파싱 시도가 실패하더라도 단락으로 변환하지 않고 기본 테이블 컴포넌트 생성
                if table_lines:
                    try:
                        # 가장 기본적인 테이블 컴포넌트 생성 시도
                        first_line = table_lines[0]
                        header_count = first_line.count('|') - 1
                        header_cells = ["열 " + str(i+1) for i in range(header_count)]
                        
                        table_component = TableComponent(
                            title=table_title,
                            data=TableData(
                                headers=[TableHeader(key=f"col{idx}", label=header) for idx, header in enumerate(header_cells)],
                                rows=[{}]
                            )
                        )
                        components.append(table_component)
                    except Exception as e3:
                        logger.error(f"기본 테이블 컴포넌트 생성 오류: {e3}")
                        # 정말 실패한 경우만 텍스트로 처리
                        table_text = '\n'.join(table_lines)
                        components.append(ParagraphComponent(
                            content="[테이블 형식] " + table_title
                        ))
                continue
            
            # 3. 코드 블록 처리 (```언어 ... ```)
            if line.startswith('```'):
                code_content = []
                language = line[3:].strip()
                i += 1
                
                while i < len(lines) and not lines[i].strip().startswith('```'):
                    code_content.append(lines[i])
                    i += 1
                
                if i < len(lines):  # 코드 블록 종료 확인
                    i += 1  # '```' 다음 줄로 이동
                
                components.append(CodeBlockComponent(
                    language=language if language else None,
                    content='\n'.join(code_content)
                ))
                continue
            
            # 4. 순서 있는 목록 처리 (1. 항목)
            if re.match(r'^\d+\.\s+', line):
                list_items = []
                ordered = True
                
                while i < len(lines) and re.match(r'^\d+\.\s+', lines[i].strip()):
                    content = re.sub(r'^\d+\.\s+', '', lines[i].strip())
                    list_items.append(ListItemComponent(content=content))
                    i += 1
                
                components.append(ListComponent(
                    ordered=ordered,
                    items=list_items
                ))
                continue
            
            # 5. 순서 없는 목록 처리 (-, *, •)
            if re.match(r'^[\-\*\•]\s+', line):
                list_items = []
                ordered = False
                
                while i < len(lines) and re.match(r'^[\-\*\•]\s+', lines[i].strip()):
                    content = re.sub(r'^[\-\*\•]\s+', '', lines[i].strip())
                    list_items.append(ListItemComponent(content=content))
                    i += 1
                
                components.append(ListComponent(
                    ordered=ordered,
                    items=list_items
                ))
                continue
            
            # 6. 단락 처리
            paragraph_lines = []
            
            while i < len(lines) and lines[i].strip() and not (
                    re.match(r'^(#{1,6})\s+', lines[i]) or  # 헤딩이 아님
                    re.match(r'^\d+\.\s+', lines[i]) or  # 순서 있는 목록이 아님
                    re.match(r'^[\-\*\•]\s+', lines[i]) or  # 순서 없는 목록이 아님
                    lines[i].strip().startswith('```') or  # 코드 블록이 아님
                    lines[i].strip().startswith('|')  # 테이블이 아님
            ):
                paragraph_lines.append(lines[i])
                i += 1
            
            if paragraph_lines:
                components.append(ParagraphComponent(
                    content=' '.join([line.strip() for line in paragraph_lines])
                ))
                continue
            
            # 그 외의 경우 다음 줄로 이동
            i += 1
        return components
        
    async def make_full_components(self, state: Dict[str, Any]):
        """
        포맷팅된 응답을 구조화된 컴포넌트로 변환합니다.
        마크다운 형식의 텍스트를 구조화된 컴포넌트(헤딩, 단락, 목록 등)로 파싱합니다.
        """
        components = []
        
        # 상태에서 정보 추출
        stock_name = state.get("stock_name", "삼성전자")
        stock_code = state.get("stock_code", "005930")
        formatted_response = state.get("formatted_response", "")
        
        # 헤더 컴포넌트 추가
        components.append(HeadingComponent(
            level=1,
            content=f"{stock_name}({stock_code}) 분석 결과"
        ))
        
        # 빈 응답이면 기본 컴포넌트만 반환
        if not formatted_response.strip():
            components.append(ParagraphComponent(
                content="분석 결과를 찾을 수 없습니다."
            ))
            return components
        
        components = await self.make_components(formatted_response)
        
        return components
    
    async def make_components_sample(self, state: Dict[str, Any]):
        """
        포맷팅된 응답을 구조화된 컴포넌트로 변환합니다.
        """
        components = []
        
        # 상태에서 정보 추출
        stock_name = state.get("stock_name", "삼성전자")
        stock_code = state.get("stock_code", "005930")
        formatted_response = state.get("formatted_response", "")
        
        # 1. 헤딩 컴포넌트 (여러 레벨)
        components.append(HeadingComponent(
            level=1,
            content=f"{stock_name}({stock_code}) 분석 결과"
        ))
        
        # 2. 단락 컴포넌트
        components.append(ParagraphComponent(
            content=f"{stock_name}의 최근 실적과 시장 동향을 분석한 결과입니다. 아래 데이터를 참고하여 투자 결정에 활용하시기 바랍니다."
        ))
        
        # 3. 부제목 (2단계 헤딩)
        components.append(HeadingComponent(
            level=2,
            content="주요 재무 지표"
        ))
        
        # 4. 목록 컴포넌트 (순서 없는 목록)
        components.append(ListComponent(
            ordered=False,
            items=[
                ListItemComponent(content="최근 분기 매출액: 7.8조원 (전년 대비 5.2% 증가)"),
                ListItemComponent(content="영업이익률: 15.3% (전년 대비 2.1%p 상승)"),
                ListItemComponent(content="ROE: 12.7% (업계 평균 대비 양호)"),
                ListItemComponent(content="부채비율: 45.2% (안정적인 재무구조 유지)")
            ]
        ))
        
        # 5. 두 번째 부제목
        components.append(HeadingComponent(
            level=2,
            content="실적 추이"
        ))
        
        # 6. 바차트 컴포넌트
        components.append(BarChartComponent(
            title="분기별 매출 및 영업이익 추이",
            data=BarChartData(
                labels=["1Q 2023", "2Q 2023", "3Q 2023", "4Q 2023", "1Q 2024"],
                datasets=[
                    {
                        "label": "매출액(조원)",
                        "data": [63.7, 67.4, 71.2, 74.8, 78.5],
                        "backgroundColor": "#4C9AFF"
                    },
                    {
                        "label": "영업이익(조원)",
                        "data": [8.2, 9.1, 10.3, 11.2, 12.0],
                        "backgroundColor": "#FF5630"
                    }
                ]
            )
        ))
        
        # 7. 차트 설명 단락
        components.append(ParagraphComponent(
            content=f"위 차트는 {stock_name}의 최근 5개 분기 매출액과 영업이익 추이를 보여줍니다. 지속적인 성장세를 유지하고 있습니다."
        ))
        
        # 8. 세 번째 부제목
        components.append(HeadingComponent(
            level=2,
            content="주가 동향"
        ))
        
        # 9. 라인차트 컴포넌트
        components.append(LineChartComponent(
            title="최근 6개월 주가 추이",
            data=LineChartData(
                labels=["11월", "12월", "1월", "2월", "3월", "4월"],
                datasets=[
                    {
                        "label": "주가(원)",
                        "data": [67000, 70200, 72800, 69500, 74200, 76800],
                        "borderColor": "#36B37E",
                        "tension": 0.1
                    },
                    {
                        "label": "KOSPI(pt)",
                        "data": [2450, 2520, 2580, 2510, 2650, 2700],
                        "borderColor": "#FF8B00",
                        "tension": 0.1,
                        "borderDash": [5, 5]
                    }
                ]
            )
        ))
        
        # 10. 네 번째 부제목
        components.append(HeadingComponent(
            level=2,
            content="주요 재무제표"
        ))
        
        # 11. 테이블 컴포넌트
        components.append(TableComponent(
            title="요약 재무제표",
            data=TableData(
                headers=[
                    TableHeader(key="item", label="항목"),
                    TableHeader(key="2022", label="2022년"),
                    TableHeader(key="2023", label="2023년"),
                    TableHeader(key="yoy", label="증감률(%)")
                ],
                rows=[
                    {"item": "매출액", "2022": "280조원", "2023": "302조원", "yoy": "+7.9%"},
                    {"item": "영업이익", "2022": "36.5조원", "2023": "42.8조원", "yoy": "+17.3%"},
                    {"item": "당기순이익", "2022": "28.1조원", "2023": "33.7조원", "yoy": "+19.9%"},
                    {"item": "자산총계", "2022": "420.2조원", "2023": "456.8조원", "yoy": "+8.7%"},
                    {"item": "부채총계", "2022": "187.5조원", "2023": "195.2조원", "yoy": "+4.1%"},
                    {"item": "자본총계", "2022": "232.7조원", "2023": "261.6조원", "yoy": "+12.4%"}
                ]
            )
        ))
        
        # 12. 다섯 번째 부제목
        components.append(HeadingComponent(
            level=2,
            content="산업 비교 분석"
        ))
        
        # 13. 순서 있는 목록
        components.append(ListComponent(
            ordered=True,
            items=[
                ListItemComponent(content="시장점유율: 글로벌 시장에서 1위 유지 (점유율 22.3%)"),
                ListItemComponent(content="기술 경쟁력: 주요 경쟁사 대비 R&D 투자금액 15% 이상 높음"),
                ListItemComponent(content="수익성: 업계 평균 영업이익률 9.7% 대비 5.6%p 높은 수준"),
                ListItemComponent(content="성장성: 2024년 예상 성장률 8.5%로 업계 평균(5.2%) 상회")
            ]
        ))
        
        # 14. 여섯 번째 부제목
        components.append(HeadingComponent(
            level=2,
            content="코드 예시"
        ))
        
        # 15. 코드 블록 컴포넌트
        components.append(CodeBlockComponent(
            language="python",
            content="""
import pandas as pd
import matplotlib.pyplot as plt

# 삼성전자 재무데이터 로드
df = pd.read_csv('samsung_financial.csv')

# 분기별 매출 추이 차트
plt.figure(figsize=(12, 6))
plt.plot(df['quarter'], df['revenue'], marker='o')
plt.title('삼성전자 분기별 매출 추이')
plt.grid(True)
plt.show()
            """
        ))
        
        # 16. 일곱 번째 부제목
        components.append(HeadingComponent(
            level=2,
            content="투자 의견"
        ))
        
        # 17. 마지막 단락
        components.append(ParagraphComponent(
            content=f"{stock_name}는 안정적인 재무구조와 지속적인 성장세를 보이고 있으며, 업계 내 경쟁우위를 유지하고 있습니다. 단기적인 시장 변동성에도 불구하고 중장기 성장 잠재력이 높다고 판단됩니다. 다만, 글로벌 경제 불확실성과 산업 내 경쟁 심화는 리스크 요인으로 작용할 수 있습니다."
        ))
        
        # 18. 이미지 컴포넌트 (샘플)
        components.append(ImageComponent(
            url="https://example.com/chart_image.png",
            alt="삼성전자 사업부문별 매출 비중",
            caption="2023년 사업부문별 매출 비중"
        ))
        
        # 19. 면책조항
        components.append(ParagraphComponent(
            content="※ 위 정보는 투자 참고 목적으로 제공되며, 투자 결정은 개인의 판단에 따라 신중하게 이루어져야 합니다."
        ))
        
        return components

# 각 컴포넌트에 대한 도구 함수 정의
@tool
def create_heading(level: int, content: str) -> Dict:
    """제목 컴포넌트를 생성합니다. 
    level은 1-6 사이의 정수이며, content는 제목 내용입니다.
    - level=1: 문서 전체 제목 (자동 생성)
    - level=2: 주요 섹션 제목 (예: 1., 2., 3.)
    - level=3: 하위 섹션 제목 (예: 1.1, 1.2, 2.1)
    - level=4: 필요한 경우 추가적인 하위 제목 (넘버링 없음)
    """
    return HeadingComponent(level=level, content=content).dict()

@tool
def create_paragraph(content: str) -> Dict:
    """단락 컴포넌트를 생성합니다. content는 단락 내용입니다."""
    return ParagraphComponent(content=content).dict()

@tool
def create_list(ordered: bool, items: List[str]) -> Dict:
    """목록 컴포넌트를 생성합니다. ordered는 순서가 있는지 여부, items는 목록 항목입니다."""
    list_items = [ListItemComponent(content=item) for item in items]
    return ListComponent(ordered=ordered, items=list_items).dict()

@tool
def create_table(title: str, headers: List[Dict[str, str]], rows: List[Dict[str, Any]]) -> Dict:
    """테이블 컴포넌트를 생성합니다. 
    title은 테이블 제목, 
    headers는 [{"key": "col0", "label": "항목명"}] 형식의 헤더 목록, 
    rows는 테이블 데이터입니다."""
    table_headers = [TableHeader(**header) for header in headers]
    return TableComponent(
        title=title, 
        data=TableData(headers=table_headers, rows=rows)
    ).dict()

@tool
def create_bar_chart(title: str, labels: List[str], datasets: List[Dict[str, Any]]) -> Dict:
    """바 차트 컴포넌트를 생성합니다.
    title은 차트 제목,
    labels은 x축 라벨,
    datasets는 [{"label": "매출액", "data": [100, 200], "backgroundColor": "#4C9AFF"}] 형식의 데이터셋 목록입니다."""
    return BarChartComponent(
        title=title,
        data=BarChartData(labels=labels, datasets=datasets)
    ).dict()

@tool
def create_line_chart(title: str, labels: List[str], datasets: List[Dict[str, Any]]) -> Dict:
    """라인 차트 컴포넌트를 생성합니다.
    title은 차트 제목,
    labels은 x축 라벨,
    datasets는 [{"label": "주가(원)", "data": [67000, 70200], "borderColor": "#36B37E"}] 형식의 데이터셋 목록입니다."""
    return LineChartComponent(
        title=title,
        data=LineChartData(labels=labels, datasets=datasets)
    ).dict()

@tool
def create_code_block(language: Optional[str], content: str) -> Dict:
    """코드 블록 컴포넌트를 생성합니다. language는 언어(선택), content는 코드 내용입니다."""
    return CodeBlockComponent(language=language, content=content).dict()

@tool
def create_image(url: str, alt: str, caption: Optional[str] = None) -> Dict:
    """이미지 컴포넌트를 생성합니다. url은 이미지 주소, alt는 대체 텍스트, caption은 캡션(선택)입니다."""
    return ImageComponent(url=url, alt=alt, caption=caption).dict()

