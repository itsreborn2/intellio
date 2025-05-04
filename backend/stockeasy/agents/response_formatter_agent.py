"""
응답 포맷터 에이전트 모듈

이 모듈은 통합된 지식 정보를 사용자에게 이해하기 쉬운 
형태로 포맷팅하는 응답 포맷터 에이전트 클래스를 구현합니다.
"""

import json
import re
from loguru import logger
from typing import Dict, Any, List, Optional, Callable, AsyncGenerator

from langchain_core.messages import HumanMessage, AIMessage
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
        logger.info(f"ResponseFormatterAgent initialized with provider: {self.agent_llm.get_provider()}, model: {self.agent_llm.get_model_name()}")
        self.parser = StrOutputParser()
        self.prompt_template = FRIENDLY_RESPONSE_FORMATTER_SYSTEM_PROMPT

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
            
            integrated_response = integrated_knowledge.get("integrated_response", state.get("integrated_response", ""))
            core_insights = integrated_knowledge.get("core_insights", [])
            
            analysis = integrated_knowledge.get("analysis", {})
            confidence_assessment = analysis.get("confidence_assessment", {})
            uncertain_areas = analysis.get("uncertain_areas", [])
            
            logger.info(f"ResponseFormatterAgent formatting response for query: {query}")
            
            summary = state.get("summary", "")
            processing_status = state.get("processing_status", {})
            summarizer_status = processing_status.get("summarizer", "not_started")

            context_response_agent = state["agent_results"].get("context_response_agent", {})
            context_based_answer = ""
            if context_response_agent:
                context_based_answer = context_response_agent.get("answer", "")
                summary = context_based_answer
            
            # 통합된 응답이 없는 경우 처리
            if not context_based_answer and (not summary or summarizer_status != "completed"):
                logger.warning(f"No summary response available.")
                logger.warning(f"processing_status: {processing_status}")
                logger.warning(f"Summarizer status: {summarizer_status}")
                state["formatted_response"] = "죄송합니다. 현재 요청에 대한 정보를 찾을 수 없습니다. 다른 질문을 해 주시거나 나중에 다시 시도해 주세요."
                state["answer"] = "죄송합니다. 현재 요청에 대한 정보를 찾을 수 없습니다. 다른 질문을 해 주시거나 나중에 다시 시도해 주세요."
                return state
            
            # 프롬프트 준비 (Tool Calling을 위한 지시사항 추가)
            tool_calling_system_prompt = """
당신은 금융 정보를 구조화된 컴포넌트로 변환하는 전문가입니다.
사용자의 쿼리에 대한 응답을 다음 도구들을 사용하여 구조화된 형식으로 생성해주세요:

1. create_heading: 제목과 소제목 생성
2. create_paragraph: 설명 텍스트 생성
3. create_list: 순서 있는/없는 항목 목록 생성
4. create_table: 표 형식 데이터 생성 - 재무제표, 분기별 실적, 시장 점유율 등 표 형태의 데이터는 반드시 이 도구를 사용하세요!
5. create_bar_chart: 바 차트 데이터 시각화
6. create_line_chart: 라인 차트 데이터 시각화
7. create_image: 이미지 참조

응답을 생성할 때 다음 사항을 지켜주세요:
- 항상 제목(level 1)부터 시작하세요.
- 내용의 흐름이 논리적이고 이해하기 쉽게 구성하세요.
- 테이블과 차트는 적절한 데이터가 있을 때만 사용하세요.
- 가능한 한 시각적으로 풍부하고 사용자가 이해하기 쉬운 형식으로 구성하세요.

각 도구의 정확한 형식과 파라미터를 따라 호출하세요.
"""
            
            # 프롬프트에 Tool Calling 시스템 프롬프트 추가
            custom_prompt_from_state = state.get("custom_prompt_template")
            if custom_prompt_from_state:
                system_prompt = custom_prompt_from_state
            else:
                system_prompt = tool_calling_system_prompt
            
            prompt = format_response_formatter_prompt(
                query=query,
                stock_name=stock_name,
                stock_code=stock_code,
                integrated_response=summary,
                core_insights=core_insights,
                confidence_assessment=confidence_assessment,
                uncertain_areas=uncertain_areas,
                system_prompt=system_prompt
            )
            
            user_context = state.get("user_context", {})
            user_id = user_context.get("user_id", None)
            
            # Tool Calling 설정
            tools = [
                create_heading,
                create_paragraph,
                create_list,
                create_table,
                create_bar_chart,
                create_line_chart,
                #create_code_block,
                create_image
            ]
            
            # LLM에 도구 바인딩
            llm_with_tools = self.agent_llm.get_llm().bind_tools(tools)
            
            # LLM 호출
            response = await llm_with_tools.ainvoke(
                input=prompt.format_prompt().to_string(),
                # user_id=user_id,
                # project_type=ProjectType.STOCKEASY,
                # db=self.db
            )
            
            # 응답 텍스트 저장
            formatted_response = response.content
            state["formatted_response"] = formatted_response
            state["answer"] = formatted_response
            
            # Tool Calls 확인 및 컴포넌트 생성
            components = []
            if hasattr(response, 'tool_calls') and response.tool_calls:
                for tool_call in response.tool_calls:
                    # 도구 함수를 직접 호출하여 컴포넌트 생성
                    tool_name = tool_call["name"]
                    tool_args = tool_call["args"]
                    
                    # level 값이 float이면 int로 변환
                    if 'level' in tool_args and isinstance(tool_args['level'], float):
                        tool_args['level'] = int(tool_args['level'])
                    
                    # 도구 이름에 맞는 함수 찾기
                    tool_func = next((t for t in tools if t.name == tool_name), None)
                    
                    if tool_func:
                        # 신규 방식: invoke() 메서드 사용
                        component_dict = tool_func.invoke(tool_args)
                        components.append(component_dict)
            
            # 컴포넌트가 없으면 텍스트 응답을 기반으로 기존 방식으로 컴포넌트 생성
            if not components:
                logger.info("Tool Calls이 없어 기존 방식으로 컴포넌트를 생성합니다.")
                components = await self.make_components(state)
                components = [comp.dict() for comp in components]
            
            # 결과 저장
            state["components"] = components
            
            # 처리 상태 업데이트
            state["processing_status"] = state.get("processing_status", {})
            state["processing_status"]["response_formatter"] = "completed"
            
            return state
            
        except Exception as e:
            logger.exception(f"Error in ResponseFormatterAgent: {str(e)}")
            state["error"] = f"응답 포맷터 에이전트 오류: {str(e)}"
            state["formatted_response"] = "죄송합니다. 응답을 포맷팅하는 중 오류가 발생했습니다."
            state["answer"] = state["formatted_response"]
            return state 

    async def make_components(self, state: Dict[str, Any]):
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
        
        # 마크다운을 줄 단위로 분리
        lines = formatted_response.split('\n')
        
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
    """제목 컴포넌트를 생성합니다. level은 1-6 사이의 정수, content는 제목 내용입니다."""
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

