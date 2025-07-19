"""
응답 포맷터 에이전트 모듈

이 모듈은 통합된 지식 정보를 사용자에게 이해하기 쉬운
형태로 포맷팅하는 응답 포맷터 에이전트 클래스를 구현합니다.
"""

import asyncio
import re
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from langchain_core.output_parsers import StrOutputParser
from langchain_core.tools import tool
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from common.schemas.chat_components import (
    BarChartComponent,
    BarChartData,
    CodeBlockComponent,
    HeadingComponent,
    ImageComponent,
    LineChartComponent,
    LineChartData,
    ListComponent,
    ListItemComponent,
    MixedChartComponent,
    MixedChartData,
    ParagraphComponent,
    PriceChartComponent,
    PriceChartData,
    TableComponent,
    TableData,
    TableHeader,
    TechnicalIndicatorChartComponent,
    TechnicalIndicatorChartData,
    TechnicalIndicatorData,
)
from common.services.agent_llm import get_agent_llm
from common.utils.util import format_date_for_chart, remove_json_block, safe_float, safe_int
from stockeasy.agents.base import BaseAgent
from stockeasy.prompts.response_formatter_prompts import FRIENDLY_RESPONSE_FORMATTER_SYSTEM_PROMPT


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
        self.agent_llm = get_agent_llm("response_formatter_agent")
        self.agent_llm_for_tools = get_agent_llm("gemini-lite")
        # self.agent_llm_for_tools = get_agent_llm("gemini-2.0-flash")
        logger.info(f"ResponseFormatterAgent initialized with provider: {self.agent_llm.get_provider()}, model: {self.agent_llm.get_model_name()}")
        self.parser = StrOutputParser()
        self.prompt_template = FRIENDLY_RESPONSE_FORMATTER_SYSTEM_PROMPT

        self.chart_placeholder = "[CHART_PLACEHOLDER:PRICE_CHART]"
        self.technical_indicator_chart_placeholder = "[CHART_PLACEHOLDER:TECHNICAL_INDICATOR_CHART]"

        # 새로운 플레이스홀더 추가
        self.trend_following_chart_placeholder = "[CHART_PLACEHOLDER:TREND_FOLLOWING_CHART]"
        self.momentum_chart_placeholder = "[CHART_PLACEHOLDER:MOMENTUM_CHART]"

    def _find_placeholder_in_component(self, component: Dict[str, Any]) -> str:
        """
        컴포넌트에서 플레이스홀더가 포함된 필드를 찾아 반환합니다.
        반환값: 플레이스홀더가 있는 필드명 (없으면 None)
        """
        component_type = component.get("type")

        # 컴포넌트 타입별로 플레이스홀더 검색 필드 정의
        search_fields = {
            "paragraph": ["content"],
            "image": ["url", "alt", "caption"],
            "heading": ["content"],
            "code_block": ["content"],
            "table": ["title"],  # 필요에 따라 더 추가 가능
        }

        fields_to_search = search_fields.get(component_type, [])

        for field in fields_to_search:
            field_value = component.get(field, "")
            if isinstance(field_value, str) and self.chart_placeholder in field_value:
                return field

        return None

    def _insert_price_chart_at_marker(self, components: List[Dict[str, Any]], price_chart_component: Dict[str, Any]) -> None:
        """
        컴포넌트 리스트에서 플레이스홀더를 찾아서 주가차트 컴포넌트로 교체합니다.
        다양한 컴포넌트 타입의 여러 필드에서 플레이스홀더를 검색합니다.
        """
        marker_found = False
        for i, component in enumerate(components):
            placeholder_field = self._find_placeholder_in_component(component)

            if placeholder_field:
                marker_found = True
                component_type = component.get("type")
                field_value = component.get(placeholder_field, "")

                if component_type == "paragraph" and placeholder_field == "content":
                    # paragraph의 content는 텍스트 분리 후 재구성
                    parts = field_value.split(self.chart_placeholder)
                    before_text = parts[0].strip()
                    after_text = parts[1].strip() if len(parts) > 1 else ""

                    # 원래 컴포넌트 제거
                    components.pop(i)

                    insert_index = i

                    # 마커 앞 텍스트가 있으면 단락 컴포넌트로 추가
                    if before_text:
                        before_comp = create_paragraph({"content": before_text})
                        components.insert(insert_index, before_comp)
                        insert_index += 1

                    # 주가차트 컴포넌트 삽입
                    components.insert(insert_index, price_chart_component)
                    insert_index += 1

                    # 마커 뒤 텍스트가 있으면 단락 컴포넌트로 추가
                    if after_text:
                        after_comp = create_paragraph({"content": after_text})
                        components.insert(insert_index, after_comp)

                else:
                    components[i] = price_chart_component

                break

        # 마커를 찾지 못한 경우 마지막에 추가
        if not marker_found:
            components.append(price_chart_component)

    def _insert_technical_indicator_chart_at_marker(self, components: List[Dict[str, Any]], technical_indicator_chart_component: Dict[str, Any]) -> None:
        """
        컴포넌트 목록에서 기술적 지표 차트 플레이스홀더를 찾아 실제 차트 컴포넌트로 교체합니다.
        """
        marker_found = False
        for i, component in enumerate(components):
            # 컴포넌트에서 플레이스홀더 포함 필드 찾기
            field = self._find_technical_indicator_placeholder_in_component(component)
            if field:
                marker_found = True
                component_type = component.get("type")
                field_value = component.get(field, "")

                if component_type == "paragraph" and field == "content":
                    # paragraph의 content는 텍스트 분리 후 재구성
                    parts = field_value.split(self.technical_indicator_chart_placeholder)
                    before_text = parts[0].strip()
                    after_text = parts[1].strip() if len(parts) > 1 else ""

                    # 원래 컴포넌트 제거
                    components.pop(i)

                    insert_index = i

                    # 마커 앞 텍스트가 있으면 단락 컴포넌트로 추가
                    if before_text:
                        before_comp = create_paragraph({"content": before_text})
                        components.insert(insert_index, before_comp)
                        insert_index += 1

                    # 기술적 지표 차트 컴포넌트 삽입
                    components.insert(insert_index, technical_indicator_chart_component)
                    insert_index += 1

                    # 마커 뒤 텍스트가 있으면 단락 컴포넌트로 추가
                    if after_text:
                        after_comp = create_paragraph({"content": after_text})
                        components.insert(insert_index, after_comp)

                else:
                    # 비-paragraph 컴포넌트는 전체 교체
                    components[i] = technical_indicator_chart_component

                break

        # 마커를 찾지 못한 경우 마지막에 추가
        if not marker_found:
            components.append(technical_indicator_chart_component)

    def _insert_trend_following_chart_at_marker(self, components: List[Dict[str, Any]], trend_following_chart_component: Dict[str, Any]) -> None:
        """
        컴포넌트 목록에서 추세추종 지표 차트 플레이스홀더를 찾아 실제 차트 컴포넌트로 교체합니다.
        """
        marker_found = False
        for i, component in enumerate(components):
            # 컴포넌트에서 플레이스홀더 포함 필드 찾기
            field = self._find_trend_following_placeholder_in_component(component)
            if field:
                marker_found = True
                component_type = component.get("type")
                field_value = component.get(field, "")

                if component_type == "paragraph" and field == "content":
                    # paragraph의 content는 텍스트 분리 후 재구성
                    parts = field_value.split(self.trend_following_chart_placeholder)
                    before_text = parts[0].strip()
                    after_text = parts[1].strip() if len(parts) > 1 else ""

                    # 원래 컴포넌트 제거
                    components.pop(i)

                    insert_index = i

                    # 마커 앞 텍스트가 있으면 단락 컴포넌트로 추가
                    if before_text:
                        before_comp = create_paragraph({"content": before_text})
                        components.insert(insert_index, before_comp)
                        insert_index += 1

                    # 추세추종 지표 차트 컴포넌트 삽입
                    components.insert(insert_index, trend_following_chart_component)
                    insert_index += 1

                    # 마커 뒤 텍스트가 있으면 단락 컴포넌트로 추가
                    if after_text:
                        after_comp = create_paragraph({"content": after_text})
                        components.insert(insert_index, after_comp)

                else:
                    # 비-paragraph 컴포넌트는 전체 교체
                    components[i] = trend_following_chart_component

                break

        # 마커를 찾지 못한 경우 마지막에 추가
        if not marker_found:
            components.append(trend_following_chart_component)

    def _insert_momentum_chart_at_marker(self, components: List[Dict[str, Any]], momentum_chart_component: Dict[str, Any]) -> None:
        """
        컴포넌트 목록에서 모멘텀 지표 차트 플레이스홀더를 찾아 실제 차트 컴포넌트로 교체합니다.
        """
        marker_found = False
        for i, component in enumerate(components):
            # 컴포넌트에서 플레이스홀더 포함 필드 찾기
            field = self._find_momentum_placeholder_in_component(component)
            if field:
                marker_found = True
                component_type = component.get("type")
                field_value = component.get(field, "")

                if component_type == "paragraph" and field == "content":
                    # paragraph의 content는 텍스트 분리 후 재구성
                    parts = field_value.split(self.momentum_chart_placeholder)
                    before_text = parts[0].strip()
                    after_text = parts[1].strip() if len(parts) > 1 else ""

                    # 원래 컴포넌트 제거
                    components.pop(i)

                    insert_index = i

                    # 마커 앞 텍스트가 있으면 단락 컴포넌트로 추가
                    if before_text:
                        before_comp = create_paragraph({"content": before_text})
                        components.insert(insert_index, before_comp)
                        insert_index += 1

                    # 모멘텀 지표 차트 컴포넌트 삽입
                    components.insert(insert_index, momentum_chart_component)
                    insert_index += 1

                    # 마커 뒤 텍스트가 있으면 단락 컴포넌트로 추가
                    if after_text:
                        after_comp = create_paragraph({"content": after_text})
                        components.insert(insert_index, after_comp)

                else:
                    # 비-paragraph 컴포넌트는 전체 교체
                    components[i] = momentum_chart_component

                break

        # 마커를 찾지 못한 경우 마지막에 추가
        if not marker_found:
            components.append(momentum_chart_component)

    def _find_technical_indicator_placeholder_in_component(self, component: Dict[str, Any]) -> str:
        """
        컴포넌트에서 기술적 지표 차트 플레이스홀더가 포함된 필드를 찾아 반환합니다.
        """
        component_type = component.get("type")

        # 컴포넌트 타입별로 플레이스홀더 검색 필드 정의
        search_fields = {"paragraph": ["content"], "image": ["url", "alt", "caption"], "heading": ["content"], "code_block": ["content"], "table": ["title"]}

        fields_to_search = search_fields.get(component_type, [])

        for field in fields_to_search:
            field_value = component.get(field, "")
            if isinstance(field_value, str) and self.technical_indicator_chart_placeholder in field_value:
                return field

        return None

    def _find_trend_following_placeholder_in_component(self, component: Dict[str, Any]) -> str:
        """
        컴포넌트에서 추세추종 지표 차트 플레이스홀더가 포함된 필드를 찾아 반환합니다.
        """
        component_type = component.get("type")

        # 컴포넌트 타입별로 플레이스홀더 검색 필드 정의
        search_fields = {"paragraph": ["content"], "image": ["url", "alt", "caption"], "heading": ["content"], "code_block": ["content"], "table": ["title"]}

        fields_to_search = search_fields.get(component_type, [])

        for field in fields_to_search:
            field_value = component.get(field, "")
            if isinstance(field_value, str) and self.trend_following_chart_placeholder in field_value:
                return field

        return None

    def _find_momentum_placeholder_in_component(self, component: Dict[str, Any]) -> str:
        """
        컴포넌트에서 모멘텀 지표 차트 플레이스홀더가 포함된 필드를 찾아 반환합니다.
        """
        component_type = component.get("type")

        # 컴포넌트 타입별로 플레이스홀더 검색 필드 정의
        search_fields = {"paragraph": ["content"], "image": ["url", "alt", "caption"], "heading": ["content"], "code_block": ["content"], "table": ["title"]}

        fields_to_search = search_fields.get(component_type, [])

        for field in fields_to_search:
            field_value = component.get(field, "")
            if isinstance(field_value, str) and self.momentum_chart_placeholder in field_value:
                return field

        return None

    async def _try_tool_calling_with_retry(self, llm_with_tools: Any, tool_calling_prompt: str, section_title: str, llm_start_time: datetime) -> tuple[Any, str]:
        """
        Tool calling을 시도하고 MALFORMED_FUNCTION_CALL 에러 발생 시 재시도합니다.

        Args:
            llm_with_tools: LLM 인스턴스
            tool_calling_prompt: Tool calling 프롬프트
            section_title: 섹션 제목
            llm_start_time: LLM 호출 시작 시간

        Returns:
            tuple: (section_response, llm_generated_text_for_section)
                   실패 시 (None, "")
        """
        max_retries = 1

        for attempt in range(max_retries + 1):  # 0: 첫 시도, 1: 재시도
            try:
                section_response = await llm_with_tools.ainvoke(input=tool_calling_prompt)

                llm_end_time = datetime.now()
                llm_duration = (llm_end_time - llm_start_time).total_seconds()
                logger.info(f"[LLM호출완료] 섹션 '{section_title}' LLM 호출 완료 - 소요시간: {llm_duration:.2f}초 (시도 {attempt + 1})")

                # MALFORMED_FUNCTION_CALL 에러 감지
                is_malformed = self._detect_malformed_function_call(section_response, section_title, attempt + 1)

                if is_malformed and attempt < max_retries:
                    # 재시도 가능한 경우
                    logger.warning(f"[MALFORMED재시도] 섹션 '{section_title}' MALFORMED_FUNCTION_CALL 감지 - 재시도 진행 (시도 {attempt + 2}/{max_retries + 1})")
                    await asyncio.sleep(0.2)  # 잠시 대기 후 재시도
                    continue
                elif is_malformed and attempt >= max_retries:
                    # 재시도 횟수 초과
                    logger.error(f"[MALFORMED최종실패] 섹션 '{section_title}' MALFORMED_FUNCTION_CALL 재시도 실패 - 최대 재시도 횟수 초과")
                    return None, ""
                else:
                    # 정상 응답
                    llm_generated_text_for_section = section_response.content if hasattr(section_response, "content") else ""
                    logger.debug(f"[LLM응답분석] 섹션 '{section_title}' - LLM 생성 텍스트 길이: {len(llm_generated_text_for_section)}자 (시도 {attempt + 1})")
                    return section_response, llm_generated_text_for_section

            except Exception as e:
                logger.error(f"[LLM호출오류] 섹션 '{section_title}' LLM 호출 중 예외 발생 (시도 {attempt + 1}): {e}")
                if attempt >= max_retries:
                    # 재시도 횟수 초과 시 예외 재발생
                    raise e
                else:
                    # 재시도 가능한 경우 잠시 대기 후 계속
                    await asyncio.sleep(1)
                    continue

        # 여기까지 오면 안됨 (안전장치)
        logger.error(f"[LLM호출비정상종료] 섹션 '{section_title}' 비정상적인 재시도 루프 종료")
        return None, ""

    def _detect_malformed_function_call(self, section_response: Any, section_title: str, attempt_num: int) -> bool:
        """
        MALFORMED_FUNCTION_CALL 에러를 감지합니다.

        Args:
            section_response: LLM 응답 객체
            section_title: 섹션 제목 (로깅용)
            attempt_num: 시도 번호 (로깅용)

        Returns:
            bool: MALFORMED_FUNCTION_CALL 에러인지 여부
        """
        try:
            # 1. response_metadata에서 finish_reason 확인
            if hasattr(section_response, "response_metadata"):
                finish_reason = section_response.response_metadata.get("finish_reason")
                if finish_reason == "MALFORMED_FUNCTION_CALL":
                    logger.warning(f"[MALFORMED감지] 섹션 '{section_title}' (시도 {attempt_num}) - finish_reason: {finish_reason}")
                    return True
                elif finish_reason == "MAX_TOKENS":
                    # MAX_TOKENS인 경우 재시도하지 않고 현재 content를 활용
                    logger.warning(f"[MAX_TOKENS감지] 섹션 '{section_title}' (시도 {attempt_num}) - finish_reason: {finish_reason}, 현재 content 활용")
                    return False  # MAX_TOKENS는 MALFORMED가 아니므로 False 반환

            # 2. tool_calls와 content가 모두 비어있는지 확인
            has_tool_calls = hasattr(section_response, "tool_calls") and section_response.tool_calls
            has_content = hasattr(section_response, "content") and section_response.content.strip()

            if not has_tool_calls and not has_content:
                logger.warning(f"[MALFORMED감지] 섹션 '{section_title}' (시도 {attempt_num}) - tool_calls와 content 모두 비어있음")
                return True

            # 3. invalid_tool_calls 확인 (있다면)
            if hasattr(section_response, "invalid_tool_calls") and section_response.invalid_tool_calls:
                logger.warning(f"[MALFORMED감지] 섹션 '{section_title}' (시도 {attempt_num}) - invalid_tool_calls 존재: {len(section_response.invalid_tool_calls)}개")
                return True

            return False

        except Exception as e:
            logger.error(f"[MALFORMED감지오류] 섹션 '{section_title}' (시도 {attempt_num}) MALFORMED_FUNCTION_CALL 감지 중 오류: {e}")
            # 오류 발생 시 안전하게 False 반환 (정상으로 판단)
            return False

    def _detect_truncated_json(self, text: str) -> bool:
        """
        텍스트가 MAX_TOKENS로 인해 잘린 JSON인지 감지합니다.

        Args:
            text: 검사할 텍스트

        Returns:
            bool: 잘린 JSON인지 여부
        """
        try:
            import re
            
            # 1. ```json으로 시작하지만 ```로 끝나지 않는 경우
            if text.strip().startswith('```json') and not text.strip().endswith('```'):
                logger.debug("[잘린JSON감지] ```json으로 시작하지만 ```로 끝나지 않음")
                return True
            
            # 2. [ 로 시작하지만 ] 로 끝나지 않는 경우
            json_array_pattern = r"\[.*"
            if re.search(json_array_pattern, text, re.DOTALL):
                if not text.strip().endswith(']'):
                    logger.debug("[잘린JSON감지] [로 시작하지만 ]로 끝나지 않음")
                    return True
            
            # 3. JSON 객체가 중간에 끊어진 경우 (불완전한 중괄호)
            brace_count = 0
            in_string = False
            escape_next = False
            
            for char in text:
                if escape_next:
                    escape_next = False
                    continue
                    
                if char == '\\':
                    escape_next = True
                    continue
                    
                if char == '"' and not escape_next:
                    in_string = not in_string
                    
                if not in_string:
                    if char == '{':
                        brace_count += 1
                    elif char == '}':
                        brace_count -= 1
            
            # 중괄호가 맞지 않으면 잘린 것으로 판단
            if brace_count != 0:
                logger.debug(f"[잘린JSON감지] 중괄호 불균형 (brace_count: {brace_count})")
                return True
            
            # 4. JSON 문자열이 끝나지 않은 채로 끝나는 경우
            if text.strip().endswith('"') and text.count('"') % 2 != 0:
                logger.debug("[잘린JSON감지] 문자열이 닫히지 않음")
                return True
                
            # 5. 일반적인 잘림 패턴들
            # - 마지막이 콤마나 콜론으로 끝나는 경우
            # - "content": "...로 끝나는 경우 (완성되지 않은 content 필드)
            last_line = text.strip().split('\n')[-1].strip()
            if (last_line.endswith(',') or last_line.endswith(':') or 
                last_line.endswith('"content":') or last_line.endswith('"content": "')):
                logger.debug(f"[잘린JSON감지] 일반적인 잘림 패턴: {last_line[-20:]}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"[잘린JSON감지] 잘린 JSON 감지 중 오류: {e}")
            return False

    def _parse_json_fallback(self, text: str, tools: List[Callable], section_title: str) -> List[Dict[str, Any]]:
        """
        LLM이 tool calling 대신 JSON 텍스트로 응답한 경우를 파싱하여 컴포넌트를 생성합니다.

        Args:
            text: LLM이 반환한 텍스트 (JSON 포함)
            tools: 사용 가능한 tool 함수들
            section_title: 섹션 제목

        Returns:
            파싱된 컴포넌트들의 리스트, 파싱 실패 시 빈 리스트
        """
        try:
            import json
            import re

            # MAX_TOKENS로 인해 잘린 JSON인지 감지
            is_truncated_json = self._detect_truncated_json(text)
            
            if is_truncated_json:
                logger.info(f"[JSON처리] 섹션 '{section_title}' 잘린 JSON 감지, 부분 파싱 시도")
                return self._parse_partial_json(text, tools, section_title)

            # JSON 블록 추출 (```json ... ``` 또는 단순 JSON 배열)
            json_pattern = r"```json\s*(\[.*?\])\s*```"
            json_match = re.search(json_pattern, text, re.DOTALL)

            if json_match:
                json_text = json_match.group(1)
            else:
                # ```json``` 블록이 없는 경우, 전체 텍스트에서 JSON 배열 찾기
                json_array_pattern = r"(\[.*?\])"
                json_array_match = re.search(json_array_pattern, text, re.DOTALL)
                if json_array_match:
                    json_text = json_array_match.group(1)
                else:
                    logger.warning(f"JSON 패턴을 찾을 수 없음: {text[:200]}...")
                    # 패턴을 찾을 수 없는 경우에도 부분 파싱 시도
                    return self._parse_partial_json(text, tools, section_title)

            # JSON 파싱
            try:
                components_data = json.loads(json_text)
            except json.JSONDecodeError as e:
                logger.error(f"JSON 파싱 오류: {e}, JSON 텍스트: {json_text[:200]}...")
                # JSON 파싱 실패 시 부분 파싱 시도
                logger.info(f"[JSON처리] 섹션 '{section_title}' 표준 JSON 파싱 실패, 부분 파싱 시도")
                return self._parse_partial_json(text, tools, section_title)

            if not isinstance(components_data, list):
                logger.warning(f"JSON이 배열 형태가 아님: {type(components_data)}")
                return self._parse_partial_json(text, tools, section_title)

            # 컴포넌트 생성
            processed_components = []
            first_component_added = False

            for i, component_data in enumerate(components_data):
                if not isinstance(component_data, dict) or "type" not in component_data:
                    logger.warning(f"잘못된 컴포넌트 데이터: {component_data}")
                    continue

                component_type = component_data.get("type")

                try:
                    if component_type == "heading":
                        # 첫 번째 컴포넌트가 헤딩이 아니거나 섹션 제목과 다른 경우 섹션 제목 추가
                        if not first_component_added:
                            heading_content = component_data.get("content", "").strip()
                            if heading_content != section_title.strip():
                                section_heading = create_heading({"level": 2, "content": section_title})
                                processed_components.append(section_heading)
                            first_component_added = True

                        level = component_data.get("level", 2)
                        content = component_data.get("content", "")
                        if isinstance(level, float):
                            level = int(level)

                        tool_func = next((t for t in tools if t.name == "create_heading"), None)
                        if tool_func:
                            component_dict = tool_func.invoke({"level": level, "content": content})
                            processed_components.append(component_dict)

                    elif component_type == "paragraph":
                        if not first_component_added:
                            section_heading = create_heading({"level": 2, "content": section_title})
                            processed_components.append(section_heading)
                            first_component_added = True

                        content = component_data.get("content", "")
                        tool_func = next((t for t in tools if t.name == "create_paragraph"), None)
                        if tool_func:
                            component_dict = tool_func.invoke({"content": content})
                            processed_components.append(component_dict)

                    elif component_type == "list":
                        if not first_component_added:
                            section_heading = create_heading({"level": 2, "content": section_title})
                            processed_components.append(section_heading)
                            first_component_added = True

                        ordered = component_data.get("ordered", False)
                        items = component_data.get("items", [])

                        # items가 문자열 리스트인지 확인
                        if isinstance(items, list) and all(isinstance(item, str) for item in items):
                            tool_func = next((t for t in tools if t.name == "create_list"), None)
                            if tool_func:
                                component_dict = tool_func.invoke({"ordered": ordered, "items": items})
                                processed_components.append(component_dict)

                    elif component_type == "table":
                        if not first_component_added:
                            section_heading = create_heading({"level": 2, "content": section_title})
                            processed_components.append(section_heading)
                            first_component_added = True

                        title = component_data.get("title")
                        headers = component_data.get("headers", [])
                        rows = component_data.get("rows", [])

                        tool_func = next((t for t in tools if t.name == "create_table"), None)
                        if tool_func:
                            component_dict = tool_func.invoke({"headers": headers, "rows": rows, "title": title})
                            processed_components.append(component_dict)

                    elif component_type == "bar_chart":
                        if not first_component_added:
                            section_heading = create_heading({"level": 2, "content": section_title})
                            processed_components.append(section_heading)
                            first_component_added = True

                        title = component_data.get("title", "")
                        labels = component_data.get("labels", [])
                        datasets = component_data.get("datasets", [])

                        tool_func = next((t for t in tools if t.name == "create_bar_chart"), None)
                        if tool_func:
                            component_dict = tool_func.invoke({"title": title, "labels": labels, "datasets": datasets})
                            processed_components.append(component_dict)

                    elif component_type == "line_chart":
                        if not first_component_added:
                            section_heading = create_heading({"level": 2, "content": section_title})
                            processed_components.append(section_heading)
                            first_component_added = True

                        title = component_data.get("title", "")
                        labels = component_data.get("labels", [])
                        datasets = component_data.get("datasets", [])

                        tool_func = next((t for t in tools if t.name == "create_line_chart"), None)
                        if tool_func:
                            component_dict = tool_func.invoke({"title": title, "labels": labels, "datasets": datasets})
                            processed_components.append(component_dict)

                    elif component_type == "mixed_chart":
                        if not first_component_added:
                            section_heading = create_heading({"level": 2, "content": section_title})
                            processed_components.append(section_heading)
                            first_component_added = True

                        title = component_data.get("title", "")
                        labels = component_data.get("labels", [])
                        bar_datasets = component_data.get("bar_datasets", [])
                        line_datasets = component_data.get("line_datasets", [])
                        y_axis_left_title = component_data.get("y_axis_left_title")
                        y_axis_right_title = component_data.get("y_axis_right_title")

                        tool_func = next((t for t in tools if t.name == "create_mixed_chart"), None)
                        if tool_func:
                            component_dict = tool_func.invoke(
                                {
                                    "title": title,
                                    "labels": labels,
                                    "bar_datasets": bar_datasets,
                                    "line_datasets": line_datasets,
                                    "y_axis_left_title": y_axis_left_title,
                                    "y_axis_right_title": y_axis_right_title,
                                }
                            )
                            processed_components.append(component_dict)

                    elif component_type == "code_block":
                        if not first_component_added:
                            section_heading = create_heading({"level": 2, "content": section_title})
                            processed_components.append(section_heading)
                            first_component_added = True

                        language = component_data.get("language")
                        content = component_data.get("content", "")

                        tool_func = next((t for t in tools if t.name == "create_code_block"), None)
                        if tool_func:
                            component_dict = tool_func.invoke({"language": language, "content": content})
                            processed_components.append(component_dict)

                    else:
                        logger.warning(f"지원하지 않는 컴포넌트 타입: {component_type}")
                        continue

                except Exception as e:
                    logger.error(f"컴포넌트 생성 오류 (타입: {component_type}): {e}")
                    continue

            # 섹션 제목이 아직 추가되지 않은 경우 추가
            if not first_component_added and processed_components:
                section_heading = create_heading({"level": 2, "content": section_title})
                processed_components.insert(0, section_heading)
            elif not processed_components:
                # 컴포넌트가 하나도 없는 경우 기본 섹션 제목 추가
                section_heading = create_heading({"level": 2, "content": section_title})
                processed_components.append(section_heading)

            logger.info(f"JSON fallback 파싱 완료: {len(processed_components)}개 컴포넌트 생성")
            return processed_components

        except Exception as e:
            logger.error(f"JSON fallback 파싱 중 오류: {e}")
            return []

    def _parse_partial_json(self, text: str, tools: List[Callable], section_title: str) -> List[Dict[str, Any]]:
        """
        MAX_TOKENS로 인해 잘린 JSON을 가능한 한 파싱하여 컴포넌트를 생성합니다.

        Args:
            text: LLM이 반환한 텍스트 (불완전한 JSON 포함)
            tools: 사용 가능한 tool 함수들
            section_title: 섹션 제목

        Returns:
            파싱된 컴포넌트들의 리스트
        """
        try:
            import json
            import re

            logger.info(f"[부분JSON파싱] 섹션 '{section_title}' 부분 JSON 파싱 시작")

            # JSON 블록 추출 (```json ... ``` 또는 단순 JSON 배열)
            json_pattern = r"```json\s*(.*?)(?:```|$)"
            json_match = re.search(json_pattern, text, re.DOTALL)

            raw_json_text = ""
            if json_match:
                raw_json_text = json_match.group(1).strip()
            else:
                # ```json``` 블록이 없는 경우, [ 로 시작하는 부분부터 끝까지
                json_array_pattern = r"(\[.*?)(?:\s*$)"
                json_array_match = re.search(json_array_pattern, text, re.DOTALL)
                if json_array_match:
                    raw_json_text = json_array_match.group(1).strip()
                else:
                    logger.warning(f"[부분JSON파싱] JSON 패턴을 찾을 수 없음: {text[:200]}...")
                    return self._fallback_to_text_parsing(text, tools, section_title)

            if not raw_json_text:
                logger.warning(f"[부분JSON파싱] 추출된 JSON 텍스트가 비어있음")
                return self._fallback_to_text_parsing(text, tools, section_title)

            # 완전한 JSON 객체들만 추출하려고 시도
            processed_components = []
            
            # 1. 먼저 완전한 JSON 배열로 파싱 시도
            try:
                # 닫는 괄호 추가하여 완성 시도
                if raw_json_text.startswith('[') and not raw_json_text.rstrip().endswith(']'):
                    complete_json_text = raw_json_text.rstrip()
                    # 마지막 완전하지 않은 객체 제거
                    if complete_json_text.endswith(','):
                        complete_json_text = complete_json_text[:-1]
                    complete_json_text += ']'
                    
                    components_data = json.loads(complete_json_text)
                    logger.info(f"[부분JSON파싱] 완성된 JSON으로 파싱 성공: {len(components_data)}개 객체")
                    
                    # 성공적으로 파싱된 경우 컴포넌트 생성
                    processed_components = self._create_components_from_data(components_data, tools, section_title)
                    
                    if processed_components:
                        return processed_components
                        
            except json.JSONDecodeError:
                logger.info(f"[부분JSON파싱] 완성된 JSON 파싱 실패, 개별 객체 파싱 시도")
                pass

            # 2. 개별 JSON 객체들을 하나씩 파싱 시도
            json_objects = self._extract_individual_json_objects(raw_json_text)
            logger.info(f"[부분JSON파싱] 추출된 개별 JSON 객체 수: {len(json_objects)}")
            
            for i, obj_text in enumerate(json_objects):
                try:
                    component_data = json.loads(obj_text)
                    if isinstance(component_data, dict) and "type" in component_data:
                        component = self._create_single_component(component_data, tools, section_title, processed_components)
                        if component:
                            processed_components.append(component)
                            logger.debug(f"[부분JSON파싱] 객체 {i+1} 파싱 성공: {component_data.get('type')}")
                    
                except json.JSONDecodeError as e:
                    logger.warning(f"[부분JSON파싱] 객체 {i+1} 파싱 실패: {e}")
                    continue
                except Exception as e:
                    logger.error(f"[부분JSON파싱] 객체 {i+1} 처리 중 오류: {e}")
                    continue

            # 3. 아무것도 파싱되지 않은 경우 텍스트 기반 처리
            if not processed_components:
                logger.warning(f"[부분JSON파싱] JSON 파싱 완전 실패, 텍스트 기반 처리로 전환")
                return self._fallback_to_text_parsing(text, tools, section_title)

            # 섹션 제목 추가
            if not any(comp.get("type") == "heading" and comp.get("content", "").strip() == section_title.strip() for comp in processed_components):
                section_heading = create_heading({"level": 2, "content": section_title})
                processed_components.insert(0, section_heading)

            logger.info(f"[부분JSON파싱] 섹션 '{section_title}' 부분 JSON 파싱 완료: {len(processed_components)}개 컴포넌트 생성")
            return processed_components

        except Exception as e:
            logger.error(f"[부분JSON파싱] 섹션 '{section_title}' 부분 JSON 파싱 중 오류: {e}")
            return self._fallback_to_text_parsing(text, tools, section_title)

    def _extract_individual_json_objects(self, json_text: str) -> List[str]:
        """
        JSON 텍스트에서 개별 객체들을 추출합니다.
        """
        objects = []
        try:
            # [ 다음부터 시작하여 { } 쌍을 찾아 개별 객체 추출
            if not json_text.strip().startswith('['):
                return objects
                
            content = json_text.strip()[1:]  # 첫 번째 [ 제거
            
            brace_count = 0
            current_object = ""
            in_string = False
            escape_next = False
            
            for char in content:
                if escape_next:
                    current_object += char
                    escape_next = False
                    continue
                    
                if char == '\\':
                    escape_next = True
                    current_object += char
                    continue
                    
                if char == '"' and not escape_next:
                    in_string = not in_string
                    
                current_object += char
                
                if not in_string:
                    if char == '{':
                        brace_count += 1
                    elif char == '}':
                        brace_count -= 1
                        
                        if brace_count == 0:
                            # 완전한 객체 발견
                            objects.append(current_object.strip().rstrip(',').strip())
                            current_object = ""
                            
            return objects
            
        except Exception as e:
            logger.error(f"[개별객체추출] JSON 객체 추출 중 오류: {e}")
            return objects

    def _create_components_from_data(self, components_data: List[Dict], tools: List[Callable], section_title: str) -> List[Dict[str, Any]]:
        """
        파싱된 JSON 데이터에서 컴포넌트들을 생성합니다.
        """
        processed_components = []
        first_component_added = False
        
        for component_data in components_data:
            if not isinstance(component_data, dict) or "type" not in component_data:
                continue
                
            component = self._create_single_component(component_data, tools, section_title, processed_components)
            if component:
                processed_components.append(component)
                if not first_component_added:
                    first_component_added = True
                    
        return processed_components

    def _create_single_component(self, component_data: Dict, tools: List[Callable], section_title: str, existing_components: List) -> Dict[str, Any]:
        """
        단일 컴포넌트 데이터에서 컴포넌트를 생성합니다.
        """
        try:
            component_type = component_data.get("type")
            
            if component_type == "heading":
                level = component_data.get("level", 2)
                content = component_data.get("content", "")
                if isinstance(level, float):
                    level = int(level)
                    
                tool_func = next((t for t in tools if t.name == "create_heading"), None)
                if tool_func:
                    return tool_func.invoke({"level": level, "content": content})
                    
            elif component_type == "paragraph":
                content = component_data.get("content", "")
                tool_func = next((t for t in tools if t.name == "create_paragraph"), None)
                if tool_func:
                    return tool_func.invoke({"content": content})
                    
            elif component_type == "list":
                ordered = component_data.get("ordered", False)
                items = component_data.get("items", [])
                
                if isinstance(items, list) and all(isinstance(item, str) for item in items):
                    tool_func = next((t for t in tools if t.name == "create_list"), None)
                    if tool_func:
                        return tool_func.invoke({"ordered": ordered, "items": items})
                        
            elif component_type == "table":
                title = component_data.get("title")
                headers = component_data.get("headers", [])
                rows = component_data.get("rows", [])
                
                tool_func = next((t for t in tools if t.name == "create_table"), None)
                if tool_func:
                    return tool_func.invoke({"headers": headers, "rows": rows, "title": title})
                    
            elif component_type == "bar_chart":
                title = component_data.get("title", "")
                labels = component_data.get("labels", [])
                datasets = component_data.get("datasets", [])
                
                tool_func = next((t for t in tools if t.name == "create_bar_chart"), None)
                if tool_func:
                    return tool_func.invoke({"title": title, "labels": labels, "datasets": datasets})
                    
            elif component_type == "line_chart":
                title = component_data.get("title", "")
                labels = component_data.get("labels", [])
                datasets = component_data.get("datasets", [])
                
                tool_func = next((t for t in tools if t.name == "create_line_chart"), None)
                if tool_func:
                    return tool_func.invoke({"title": title, "labels": labels, "datasets": datasets})
                    
            elif component_type == "mixed_chart":
                title = component_data.get("title", "")
                labels = component_data.get("labels", [])
                bar_datasets = component_data.get("bar_datasets", [])
                line_datasets = component_data.get("line_datasets", [])
                y_axis_left_title = component_data.get("y_axis_left_title")
                y_axis_right_title = component_data.get("y_axis_right_title")
                
                tool_func = next((t for t in tools if t.name == "create_mixed_chart"), None)
                if tool_func:
                    return tool_func.invoke({
                        "title": title,
                        "labels": labels,
                        "bar_datasets": bar_datasets,
                        "line_datasets": line_datasets,
                        "y_axis_left_title": y_axis_left_title,
                        "y_axis_right_title": y_axis_right_title,
                    })
                    
            elif component_type == "code_block":
                language = component_data.get("language")
                content = component_data.get("content", "")
                
                tool_func = next((t for t in tools if t.name == "create_code_block"), None)
                if tool_func:
                    return tool_func.invoke({"language": language, "content": content})
                    
            else:
                logger.warning(f"[단일컴포넌트생성] 지원하지 않는 컴포넌트 타입: {component_type}")
                # 지원하지 않는 타입의 경우 content를 paragraph로 변환
                content = component_data.get("content", str(component_data))
                if content and content.strip():
                    tool_func = next((t for t in tools if t.name == "create_paragraph"), None)
                    if tool_func:
                        return tool_func.invoke({"content": content})
            
        except Exception as e:
            logger.error(f"[단일컴포넌트생성] 컴포넌트 생성 오류 (타입: {component_data.get('type')}): {e}")
            
        return None

    def _fallback_to_text_parsing(self, text: str, tools: List[Callable], section_title: str) -> List[Dict[str, Any]]:
        """
        JSON 파싱이 완전히 실패한 경우 텍스트 기반으로 컴포넌트를 생성합니다.
        """
        components = []
        
        # 섹션 제목 추가
        components.append(create_heading({"level": 2, "content": section_title}))
        
        # JSON 마커나 불완전한 구조 제거하고 의미있는 텍스트만 추출
        cleaned_text = self._extract_meaningful_text(text)
        
        if cleaned_text.strip():
            components.append(create_paragraph({"content": cleaned_text}))
            logger.info(f"[텍스트기반처리] 섹션 '{section_title}' 텍스트 기반 컴포넌트 생성 완료")
        else:
            components.append(create_paragraph({"content": "내용을 불러오는 중 문제가 발생했습니다."}))
            logger.warning(f"[텍스트기반처리] 섹션 '{section_title}' 의미있는 텍스트를 찾을 수 없음")
        
        return components

    def _extract_meaningful_text(self, text: str) -> str:
        """
        텍스트에서 의미있는 내용만 추출합니다.
        """
        # JSON 구조나 마커 제거
        import re
        
        # ```json ... ``` 블록 제거
        text = re.sub(r'```json.*?```', '', text, flags=re.DOTALL)
        
        meaningful_parts = []
        
        # 1. content": "..." 패턴에서 내용 추출
        content_matches = re.findall(r'"content":\s*"([^"]*)"', text)
        for content in content_matches:
            if content.strip() and len(content.strip()) > 3:  # 의미있는 길이의 텍스트만
                meaningful_parts.append(content.strip())
        
        # 2. 잘린 content": "... 패턴 처리 (마지막에 끝나지 않은 경우)
        truncated_content_match = re.search(r'"content":\s*"([^"]*?)(?:\s*$)', text)
        if truncated_content_match and truncated_content_match.group(1).strip():
            truncated_content = truncated_content_match.group(1).strip()
            if len(truncated_content) > 10 and truncated_content not in meaningful_parts:
                meaningful_parts.append(truncated_content)
                logger.debug(f"[의미텍스트추출] 잘린 content 추출: {truncated_content[:50]}...")
        
        # 3. 한국어 문장이 포함된 부분을 직접 추출
        korean_sentences = re.findall(r'[가-힣][가-힣\s\.\,\(\)\-\d]+[가-힣\.]', text)
        for sentence in korean_sentences:
            if len(sentence.strip()) > 15:  # 충분히 긴 문장만
                meaningful_parts.append(sentence.strip())
        
        # 4. content가 없으면 일반 텍스트에서 추출
        if not meaningful_parts:
            # JSON 구조 문자들 제거하고 의미있는 텍스트만 남기기
            cleaned = re.sub(r'[{}\[\],:"\\]', ' ', text)
            cleaned = re.sub(r'\s+', ' ', cleaned)
            cleaned = cleaned.strip()
            
            # type, level, content 등 키워드 제거
            cleaned = re.sub(r'\b(type|level|content|heading|paragraph|list|ordered|items)\b', '', cleaned)
            cleaned = re.sub(r'\s+', ' ', cleaned).strip()
            
            if cleaned and len(cleaned) > 10:
                meaningful_parts.append(cleaned)
        
        # 중복 제거 및 정리
        unique_parts = []
        for part in meaningful_parts:
            if part not in unique_parts and part.strip():
                unique_parts.append(part.strip())
        
        result = ' '.join(unique_parts)
        return result.strip() if result else ""

    async def _process_section_async(
        self,
        section_data: Dict[str, Any],
        summary_by_section: Dict[str, str],
        llm_with_tools: Any,
        tools: List[Callable],
        section_content_fallback: str,
        tech_agent_result: Dict[str, Any] = None,
        stock_code: str = "",
        stock_name: str = "",
    ) -> tuple[List[Dict[str, Any]], str, str]:
        """
        개별 섹션을 비동기적으로 처리하여 컴포넌트와 포맷된 텍스트를 생성합니다.
        반환값: (생성된 컴포넌트 리스트, 해당 섹션의 LLM 텍스트 응답, 섹션 제목)
        """
        start_time_process_section = datetime.now()
        section_title = section_data.get("title")
        section_components = []
        # 이 섹션 내에서 LLM이 생성한 순수 텍스트 (툴 콜 없이 반환된 내용)
        llm_generated_text_for_section = ""

        # 입력 데이터 검증 및 로깅
        logger.info(f"[섹션처리시작] 섹션 '{section_title}' 처리 시작")
        logger.debug(f"[섹션데이터검증] section_data 키들: {list(section_data.keys()) if section_data else 'None'}")
        logger.debug(f"[섹션데이터검증] summary_by_section에 '{section_title}' 존재 여부: {section_title in summary_by_section if section_title else False}")
        logger.debug(f"[섹션데이터검증] 섹션 내용 길이: {len(summary_by_section.get(section_title, '')) if section_title else 0}자")

        if not section_title:
            logger.warning("ResponseFormatterAgent (async): 목차에 제목 없는 섹션 데이터가 있습니다.")
            logger.warning(f"[섹션처리실패] 섹션 데이터: {section_data}")
            return [], "", ""

        if section_title in summary_by_section and summary_by_section[section_title]:
            section_content = summary_by_section[section_title]
            logger.info(f"[섹션내용확인] 섹션 '{section_title}' 내용 발견 - 길이: {len(section_content)}자")

            # 플레이스홀더 처리 - 직접 컴포넌트 생성 방식
            price_chart_component = None
            technical_indicator_chart_component = None
            trend_following_chart_component = None
            momentum_chart_component = None

            if self.chart_placeholder in section_content and tech_agent_result and stock_code and stock_name:
                # 주가차트 컴포넌트를 미리 생성
                price_chart_component = create_price_chart_component_directly(tech_agent_result, stock_code, stock_name)

            if self.technical_indicator_chart_placeholder in section_content and tech_agent_result and stock_code and stock_name:
                # 기존 기술적 지표 차트 컴포넌트를 미리 생성 (호환성 유지)
                technical_indicator_chart_component = create_trend_following_chart_component_directly(tech_agent_result, stock_code, stock_name)

            if self.trend_following_chart_placeholder in section_content and tech_agent_result and stock_code and stock_name:
                # 추세추종 지표 차트 컴포넌트를 미리 생성
                trend_following_chart_component = create_trend_following_chart_component_directly(tech_agent_result, stock_code, stock_name)

            if self.momentum_chart_placeholder in section_content and tech_agent_result and stock_code and stock_name:
                # 모멘텀 지표 차트 컴포넌트를 미리 생성
                momentum_chart_component = create_momentum_chart_component_directly(tech_agent_result, stock_code, stock_name)

            # 본문에 섹션 제목이 있으니, 여기서는 추가하지 않음.
            # 1. 섹션 제목 컴포넌트 추가 (항상 추가)
            # section_heading_component = create_heading({"level": 2, "content": section_title})
            # section_components.append(section_heading_component)

            tool_calling_prompt = f"""
다음 섹션의 내용을 구조화된 컴포넌트로 변환하세요:

<섹션 제목>
{section_title}
</섹션 제목>

<섹션 내용>
{section_content}
</섹션 내용>

<섹션 내용>을 분석하여 다음 컴포넌트들을 적절히 사용해 구조화하세요:
- create_heading: 각 상/하위 섹션 제목(넘버링 반드시 포함, ||level=2(1. 2. 3. 등)||level=3(1.1 1.2 2.1 등)||level=4(넘버링되지 않은 헤딩)||). 마크다운 문법으로 명확하게 헤딩 # 이 있는 경우에만 heading으로 처리합니다.
- create_paragraph: 일반 텍스트 단락. 텍스트 내에 강조문법, 마크다운 볼드체(**text** 또는 __text__)가 있다면 그대로 컴포넌트의 내용에 포함시키세요. 짧은 용어나 구문 뒤에 콜론이 오는 경우 (예: '성장 잠재력:', '핵심 요약:')는 헤딩이 아니라 별도의 단락으로 처리해야 합니다.
- create_list: 순서 있는/없는 목록. 각 목록 아이템의 텍스트 내에 강조문법, 마크다운 볼드체(**text** 또는 __text__)가 있다면 그대로 컴포넌트의 내용에 포함시키세요. 특히 다음 패턴의 텍스트는 반드시 목록으로 처리하세요:
  1. 불릿 포인트(•, *, -)로 시작하는 텍스트 라인
  2. "**제목:** 내용" 형식처럼 볼드체로 시작하는 항목 설명
  3. 항목이 볼드체와 일반 텍스트가 섞인 복합 문장인 경우에도 하나의 목록 항목으로 처리
  4. 항목 텍스트에 이탤릭체(*text*)가 포함된 경우에도 그대로 유지하며 단일 목록 항목으로 처리
- create_table: 표 형식 데이터 중 바차트나 라인차트로 표현하기 어려운 복잡한 데이터일 때만 사용하세요.
- create_bar_chart: 시간에 따른 변화를 보여주는 수치형 데이터는 바 차트로 표현하세요. 특히 다음과 같은 데이터는 반드시 바차트로 표현하세요:
  1. 분기별/월별/연도별 매출액, 영업이익, 순이익 등의 실적 데이터
  2. YoY(전년 동기 대비), QoQ(전 분기 대비) 증감률 데이터
  3. 시간에 따른 변화를 보여주는 다른 지표들
- create_line_chart: 연속적인 추세나 시계열 데이터는 선 차트로 표현하세요.
- create_mixed_chart: 다음과 같은 경우 혼합 차트(막대 차트 + 선 그래프)를 사용하세요:
  1. 같은 기간에 대해 수치와 비율(%)을 함께 보여줘야 할 때 (예: 매출액과 증감률)
  2. 왼쪽 Y축에는 막대 차트(매출액, 영업이익 등 금액), 오른쪽 Y축에는 선 그래프(YoY, QoQ 등 증감률)
  3. 서로 다른 단위(억원과 %)를 동시에 표현해야 할 때
  4. 특히 매출액/영업이익/순이익과 같은 주요 지표와 그에 대한 증감률을 동시에 표현할 때
  5. **중요**: line_datasets의 각 라벨은 구체적이어야 합니다. "YoY (%)"가 아닌 "매출액 YoY (%)", "영업이익 YoY (%)" 형태로 작성하세요.


표 데이터를 발견하면 단순히 테이블로 변환하지 말고, 다음 규칙을 따르세요:
1. 시간 순서(연도별, 분기별)로 나열된 수치 데이터는 바차트나 라인차트로 변환하세요.
2. 특히 '매출액', '영업이익', '당기순이익'과 같은 재무 지표와 '(YoY)', '(QoQ)' 같은 증감률 데이터는 함께 나타날 경우 혼합 차트(mixed_chart)로 표현하세요.
3. 하나의 표에 여러 지표가 있다면, 각 지표별로 별도의 바차트나 라인차트를 생성하세요.
4. 표 형식이 너무 복잡하거나 다양한 종류의 데이터가 혼합되어 있을 때만 테이블 컴포넌트를 사용하세요.
5. 중요: 동일한 매출처/회사/항목이 여러 분기/시간에 걸쳐 나타나는 경우, 반드시 하나의 차트에 통합해서 표현하세요. x축은 기간(분기/연도)으로 하고, 각 항목은 서로 다른 데이터셋으로 표현합니다.
6. 같은 표에 수치(금액)와 증감률(%)이 함께 있는 경우, 혼합 차트(mixed_chart)를 사용하여 직관적으로 보여주세요. 이때 line_datasets의 라벨은 "항목명 + 증감률 타입"으로 구체적으로 명명하세요 (예: "매출액 YoY (%)", "영업이익 YoY (%)").
7. 표의 행이 서로 다른 항목(매출액, 영업이익, 순이익 등)을 나타내고, 열이 시간(연도/분기)과 증감률을 나타내는 경우, 각 항목에 대해 별도의 막대 차트와 선 차트 데이터셋을 생성하세요.

표, 차트, 목록 등은 내용에 적합한 경우에만 사용하세요.
섹션 제목은 이미 추가되었으니 다시 추가하지 마세요.
주의: 마크다운 볼드체(**text** 또는 __text__)는 반드시 컴포넌트의 실제 내용 값에 포함되어야 합니다.

**중요**: '[CHART_PLACEHOLDER:'로 시작하는 문자열은 create_paragraph 컴포넌트를 호출합니다.
"""
            llm_start_time = datetime.now()

            # Tool calling 시도 (재시도 로직 포함)
            try:
                section_response, llm_generated_text_for_section = await self._try_tool_calling_with_retry(llm_with_tools, tool_calling_prompt, section_title, llm_start_time)

                if section_response is None:
                    # MALFORMED_FUNCTION_CALL로 인한 최종 실패 - 섹션 생략
                    logger.error(f"[섹션생략] 섹션 '{section_title}' MALFORMED_FUNCTION_CALL 재시도 실패로 섹션 생략")
                    return [], "", ""

                if hasattr(section_response, "tool_calls") and section_response.tool_calls:
                    processed_components = []

                    for i, tool_call in enumerate(section_response.tool_calls):
                        tool_name = tool_call["name"]
                        tool_args = tool_call["args"]
                        component_dict = None  # 명시적 초기화

                        if "level" in tool_args and isinstance(tool_args["level"], float):
                            tool_args["level"] = int(tool_args["level"])

                        tool_func = next((t for t in tools if t.name == tool_name), None)
                        if tool_func:
                            try:
                                component_dict = tool_func.invoke(tool_args)
                            except Exception as tool_error:
                                logger.error(f"[툴콜실패] 섹션 '{section_title}' - {tool_name} 호출 실패: {tool_error}")
                                logger.exception(f"[툴콜실패상세] 섹션 '{section_title}' - {tool_name} 스택 트레이스")
                                continue
                        else:
                            logger.warning(f"[툴콜누락] 섹션 '{section_title}' - 알 수 없는 tool: {tool_name}")
                            continue

                        # component_dict가 성공적으로 생성된 경우에만 처리
                        if component_dict is not None:
                            if component_dict.get("type") == "heading":
                                heading_content_candidate = component_dict.get("content", "").strip()
                                # 볼드체(bold)로 시작하거나 불릿 포인트(*, •, -)로 시작하는 텍스트는 heading이 아닌 paragraph나 list로 처리
                                if (
                                    heading_content_candidate.startswith("**")
                                    or heading_content_candidate.startswith("*")
                                    or heading_content_candidate.startswith("•")
                                    or heading_content_candidate.startswith("-")
                                ):
                                    logger.info(f"Heading candidate '{heading_content_candidate}' starts with bold or bullet. Converting to appropriate component.")

                                    # 불릿 포인트로 시작하면 list 컴포넌트로 변환
                                    if (
                                        (heading_content_candidate.startswith("*") and not heading_content_candidate.startswith("**"))
                                        or heading_content_candidate.startswith("•")
                                        or heading_content_candidate.startswith("-")
                                    ):
                                        list_tool_func = next((t for t in tools if t.name == "create_list"), None)
                                        if list_tool_func:
                                            # 불릿 포인트 제거하고 내용 추출
                                            content = re.sub(r"^[\*\•\-]\s*", "", heading_content_candidate)
                                            component_dict = list_tool_func.invoke({"ordered": False, "items": [content]})
                                        else:
                                            logger.warning("create_list tool not found. Falling back to paragraph.")
                                            paragraph_tool_func = next((t for t in tools if t.name == "create_paragraph"), None)
                                            if paragraph_tool_func:
                                                component_dict = paragraph_tool_func.invoke({"content": heading_content_candidate})
                                            else:
                                                component_dict = ParagraphComponent({"content": heading_content_candidate}).dict()
                                    else:
                                        # 볼드체로 시작하는 경우 paragraph로 변환
                                        paragraph_tool_func = next((t for t in tools if t.name == "create_paragraph"), None)
                                        if paragraph_tool_func:
                                            component_dict = paragraph_tool_func.invoke({"content": heading_content_candidate})
                                        else:
                                            component_dict = ParagraphComponent({"content": heading_content_candidate}).dict()
                                else:
                                    level_3_match = re.match(r"^(\d+)\.(\d+)\.?\s*(.*)", heading_content_candidate)
                                    level_2_match = re.match(r"^(\d+)\.?\s*(.*)", heading_content_candidate)
                                    if level_3_match:
                                        component_dict["level"] = 3
                                    elif level_2_match:
                                        component_dict["level"] = 2
                                    else:
                                        component_dict["level"] = 4

                                    if heading_content_candidate.startswith("# "):
                                        heading_content_candidate = heading_content_candidate[2:]
                                    elif heading_content_candidate.startswith("## "):
                                        heading_content_candidate = heading_content_candidate[3:]
                                    elif heading_content_candidate.startswith("### "):
                                        heading_content_candidate = heading_content_candidate[4:]

                            processed_components.append(component_dict)

                    # 첫 번째 컴포넌트가 없거나 헤딩이 아니거나 내용이 섹션 제목과 다른 경우 강제로 헤딩 추가
                    if not processed_components or processed_components[0].get("type") != "heading" or processed_components[0].get("content", "").strip() != section_title.strip():
                        logger.info(f"섹션 '{section_title}'에 대한 첫 번째 컴포넌트가 헤딩이 아니거나 섹션 제목과 일치하지 않습니다. 강제로 헤딩 추가")
                        heading_component = create_heading({"level": 2, "content": section_title})
                        section_components.append(heading_component)

                    # 처리된 컴포넌트들 추가
                    section_components.extend(processed_components)
                    # 주가차트 컴포넌트가 있으면 마커를 찾아서 교체
                    if price_chart_component:
                        self._insert_price_chart_at_marker(section_components, price_chart_component)

                    # 기술적 지표 차트 플레이스홀더 처리 (호환성 유지)
                    if technical_indicator_chart_component:
                        self._insert_technical_indicator_chart_at_marker(section_components, technical_indicator_chart_component)

                    # 추세추종 지표 차트 플레이스홀더 처리
                    if trend_following_chart_component:
                        self._insert_trend_following_chart_at_marker(section_components, trend_following_chart_component)

                    # 모멘텀 지표 차트 플레이스홀더 처리
                    if momentum_chart_component:
                        self._insert_momentum_chart_at_marker(section_components, momentum_chart_component)

                elif llm_generated_text_for_section.strip():  # 툴 콜 없이 텍스트만 반환된 경우
                    logger.warning(f"[툴콜없음] 섹션 '{section_title}'에 대해 Tool calling 없이 일반 텍스트 응답을 받았습니다.")

                    # MAX_TOKENS인지 확인 (section_response의 finish_reason 체크)
                    is_max_tokens = False
                    if hasattr(section_response, "response_metadata"):
                        finish_reason = section_response.response_metadata.get("finish_reason")
                        if finish_reason == "MAX_TOKENS":
                            is_max_tokens = True
                            logger.info(f"[MAX_TOKENS처리] 섹션 '{section_title}' MAX_TOKENS로 인한 텍스트 응답, 부분 파싱 진행")

                    # JSON 형태의 tool calling 결과가 텍스트로 반환된 경우 파싱 시도
                    if is_max_tokens:
                        # MAX_TOKENS인 경우 부분 파싱 우선 시도
                        fallback_components = self._parse_partial_json(llm_generated_text_for_section, tools, section_title)
                        if not fallback_components:
                            # 부분 파싱도 실패한 경우 일반 fallback 시도
                            fallback_components = self._parse_json_fallback(llm_generated_text_for_section, tools, section_title)
                    else:
                        # 일반적인 경우 기존 fallback 처리
                        fallback_components = self._parse_json_fallback(llm_generated_text_for_section, tools, section_title)

                    if fallback_components:
                        # JSON 파싱 성공 시 fallback 컴포넌트들 사용
                        section_components.extend(fallback_components)

                        # 주가차트 컴포넌트가 있으면 마커를 찾아서 교체
                        if price_chart_component:
                            self._insert_price_chart_at_marker(section_components, price_chart_component)
                            logger.info(f"[차트교체완료-Fallback] 섹션 '{section_title}'에서 주가차트 플레이스홀더 교체 완료")

                        # 기술적 지표 차트 플레이스홀더 처리 (호환성 유지)
                        if technical_indicator_chart_component:
                            self._insert_technical_indicator_chart_at_marker(section_components, technical_indicator_chart_component)
                            logger.info(f"[차트교체완료-Fallback] 섹션 '{section_title}'에서 기술적지표차트 플레이스홀더 교체 완료")

                        # 추세추종 지표 차트 플레이스홀더 처리
                        if trend_following_chart_component:
                            self._insert_trend_following_chart_at_marker(section_components, trend_following_chart_component)
                            logger.info(f"[차트교체완료-Fallback] 섹션 '{section_title}'에서 추세추종차트 플레이스홀더 교체 완료")

                        # 모멘텀 지표 차트 플레이스홀더 처리
                        if momentum_chart_component:
                            self._insert_momentum_chart_at_marker(section_components, momentum_chart_component)
                            logger.info(f"[차트교체완료-Fallback] 섹션 '{section_title}'에서 모멘텀차트 플레이스홀더 교체 완료")
                    else:
                        # JSON 파싱 실패 시 기존 텍스트 처리 방식 사용
                        logger.warning(f"[JSON파싱실패] 섹션 '{section_title}'에서 JSON fallback 파싱 실패, 일반 텍스트로 처리")
                        # 섹션 제목 강제 추가
                        section_components.append(create_heading({"level": 2, "content": section_title}))

                        cleaned_text = remove_json_block(llm_generated_text_for_section)

                        # 텍스트에서 마스크를 플레이스홀더로 복원
                        restored_text = cleaned_text

                        if restored_text.strip():
                            section_components.append(create_paragraph({"content": restored_text}))
                            logger.info(f"[텍스트변환완료] 섹션 '{section_title}'에서 텍스트를 단락 컴포넌트로 변환 완료")
                else:
                    logger.warning(f"[LLM응답없음] 섹션 '{section_title}'에서 LLM 응답이 비어있습니다.")

                return section_components, llm_generated_text_for_section, section_title

            except Exception as e:
                error_processing_time = (datetime.now() - start_time_process_section).total_seconds()
                logger.error(f"[섹션처리오류] 섹션 '{section_title}' 컴포넌트 생성 중 오류 - 소요시간: {error_processing_time:.2f}초")
                logger.error(f"[섹션처리오류상세] 섹션 '{section_title}' 오류 메시지: {str(e)}")
                logger.exception(f"[섹션처리오류스택] 섹션 '{section_title}' 스택 트레이스")

                # 오류 발생 시, 이미 추가된 섹션 제목 컴포넌트 외에 원본 내용을 단락으로 추가
                logger.info(f"[오류복구시작] 섹션 '{section_title}' 오류 복구 시작 - fallback 내용 길이: {len(section_content_fallback)}자")

                # 오류 복구 시에도 마스크를 플레이스홀더로 복원
                restored_fallback = section_content_fallback

                section_components.append(create_paragraph({"content": restored_fallback}))
                # 오류 시 LLM 생성 텍스트는 없고, 원본 내용을 텍스트로 반환 (오류 복구용)
                return section_components, restored_fallback, section_title
        else:  # summary_by_section에 내용이 없는 경우
            logger.warning(f"[섹션내용없음] 섹션 '{section_title}'에 대한 내용이 summary_by_section에 없습니다.")
            logger.debug(f"[섹션내용없음상세] summary_by_section 키들: {list(summary_by_section.keys())}")

            # 제목 컴포넌트만 있는 리스트와 빈 텍스트, 제목 반환
            empty_components = [create_heading({"level": 2, "content": section_title}), create_paragraph({"content": "내용 준비 중입니다."})]
            logger.info(f"[빈섹션처리완료] 섹션 '{section_title}' 빈 컴포넌트 반환 완료")
            return empty_components, "", section_title

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
            start_time_process_query = datetime.now()
            query = state.get("query", "")
            stock_code = state.get("stock_code")
            stock_name = state.get("stock_name")

            logger.info(f"ResponseFormatterAgent formatting response for query: {query}")

            # 요약 및 섹션별 요약 가져오기
            summary = state.get("summary", "")
            summary_by_section = state.get("summary_by_section", {})
            final_report_toc = state.get("final_report_toc")  # 동적 목차 정보 가져오기

            # 플레이스홀더 처리를 위해 agent_results에서 technical_analyzer 결과 가져오기
            agent_results = state.get("agent_results", {})
            tech_agent_result = agent_results.get("technical_analyzer", {})

            processing_status = state.get("processing_status", {})
            summarizer_status = processing_status.get("summarizer", "not_started")

            context_response_agent = state["agent_results"].get("context_response_agent", {})
            context_based_answer = ""
            if context_response_agent:
                context_based_answer = context_response_agent.get("answer", "")
                summary = context_based_answer  # summary를 context_based_answer로 덮어쓰기

            # 통합된 응답이 없는 경우 처리
            if not context_based_answer and (not summary or summarizer_status != "completed"):
                logger.warning("No summary response available.")
                logger.warning(f"processing_status: {processing_status}")
                logger.warning(f"Summarizer status: {summarizer_status}")
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
                create_mixed_chart,
                # create_image
            ]

            llm_with_tools = self.agent_llm_for_tools.get_llm().bind_tools(tools)

            all_components = []
            formatted_response_parts = []  # 최종 문자열 응답을 위한 조각들

            if not final_report_toc or not final_report_toc.get("sections"):
                logger.warning("ResponseFormatterAgent: 동적 목차 정보(final_report_toc)가 없거나 섹션이 비어있습니다. 기본 처리를 시도합니다.")
                if summary:
                    all_components_fallback = await self.make_full_components(state)
                    all_components = [comp.dict() for comp in all_components_fallback if hasattr(comp, "dict")]
                    formatted_response_parts.append(summary)
                else:
                    state["answer"] = "죄송합니다. 보고서 목차 정보를 찾을 수 없어 내용을 생성할 수 없습니다."
                    state["components"] = []
                    return state
            else:  # 동적 목차가 있는 경우
                report_title = final_report_toc.get("title")
                if not report_title:  # final_report_toc에 title이 없는 경우 대비
                    report_title = f"{stock_name}({stock_code}) 분석 리포트" if stock_name and stock_code else "주식 분석 리포트"

                # 보고서 전체 제목 컴포넌트 및 텍스트 추가
                title_component = create_heading({"level": 1, "content": report_title})
                all_components.append(title_component)
                formatted_response_parts.append(f"# {report_title}\n\n")

                toc_sections = final_report_toc.get("sections", [])

                # 면책조항 내용을 summary_by_section에서 가져오기 (LLM 요청 없이)
                disclaimer_content = summary_by_section.get("면책조항", "")
                # fallback으로 기본 면책조항 사용
                if not disclaimer_content.strip():
                    logger.info("ResponseFormatterAgent: summary_by_section에 면책조항이 없어 기본 면책조항을 사용합니다.")
                    disclaimer_content = """본 보고서는 투자 참고 자료로만 활용하시기 바라며, 특정 종목의 매수 또는 매도를 권유하지 않습니다. 보고서의 내용이 사실과 다른 내용이 일부 존재할 수 있으니 참고해 주시기 바랍니다. 투자 결정은 투자자 본인의 책임하에 이루어져야 하며, 본 보고서에 기반한 투자로 인한 손실에 대해 작성자와 당사는 어떠한 법적 책임도 지지 않습니다. 모든 투자에는 위험이 수반되므로 투자 전 투자자 본인의 판단과 책임하에 충분한 검토가 필요합니다."""

                tasks = []
                for section_data_item in toc_sections:  # 변수명 변경 (section_data -> section_data_item)
                    section_title_for_task = section_data_item.get("title")
                    # fallback content는 해당 섹션의 원본 요약 내용
                    section_content_fallback_for_task = summary_by_section.get(section_title_for_task, "")
                    tasks.append(
                        self._process_section_async(
                            section_data_item, summary_by_section, llm_with_tools, tools, section_content_fallback_for_task, tech_agent_result, stock_code, stock_name
                        )
                    )

                # section_results_with_exceptions: List[Union[Tuple[List[Dict], str, str], Exception]]]
                section_results_with_exceptions = await asyncio.gather(*tasks, return_exceptions=True)

                for i, res_or_exc in enumerate(section_results_with_exceptions):
                    original_section_data = toc_sections[i]  # 순서대로 매칭
                    processed_section_title_from_res = ""  # 결과에서 가져올 제목

                    if isinstance(res_or_exc, Exception):
                        # 병렬 작업에서 예외 발생 시
                        current_section_title = original_section_data.get("title", f"제목 없는 섹션 {i + 1}")
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

                        if processed_section_title_from_res:  # 제목이 있는 섹션만 텍스트 추가
                            # formatted_response_parts 에는 섹션 제목 텍스트를 여기서 추가
                            # (단, components_from_section 에 이미 제목 컴포넌트가 있으므로 중복 추가되지 않도록 주의)
                            # _process_section_async에서 컴포넌트 리스트의 첫번째가 제목이므로, 여기서는 제목 텍스트만 추가.

                            # formatted_response_parts.append(f"## {processed_section_title_from_res}\n\n") # 제목이 본문에 포함되어 있으므로, 제거

                            # LLM이 생성한 텍스트 (툴 콜이 없었을 경우) 또는 툴 콜 오류 시 fallback 텍스트
                            if llm_text_for_section.strip():
                                formatted_response_parts.append(llm_text_for_section + "\n\n")
                            # 만약 llm_text_for_section이 비어있고 components_from_section에 내용이 있다면,
                            # (즉, 툴콜링으로만 컴포넌트가 만들어진 경우) 해당 텍스트는 이미 컴포넌트로 변환되었으므로 추가 텍스트 불필요.

                # 면책조항 컴포넌트 추가 (고정된 내용)
                all_components.append(create_heading({"level": 3, "content": "면책조항"}))
                all_components.append(create_paragraph({"content": disclaimer_content}))
                formatted_response_parts.append(f"**면책조항**\n\n{disclaimer_content}\n\n")

            # 최종 formatted_response 조합
            formatted_response = "".join(formatted_response_parts).strip()

            # 플레이스홀더 제거 (컴포넌트에서는 이미 대체되었지만 텍스트에서는 남아있을 수 있음)
            formatted_response = formatted_response.replace(self.chart_placeholder, "")

            # 컴포넌트가 제목 외에 없는 경우 (모든 섹션 내용이 없거나 파싱 실패)
            if len(all_components) <= 1:  # 보고서 전체 제목 컴포넌트만 있는 경우
                logger.warning("ResponseFormatterAgent: 동적 목차 기반 컴포넌트 생성 결과가 거의 비어있습니다. 기존 요약(summary)으로 대체 처리를 시도합니다.")
                if summary:
                    state["answer"] = summary.replace(self.chart_placeholder, "")
                    all_components_fallback = await self.make_full_components(state)
                    all_components = [comp.dict() for comp in all_components_fallback if hasattr(comp, "dict")]
                    formatted_response = summary.replace(self.chart_placeholder, "")
                else:
                    logger.warning("ResponseFormatterAgent: 대체할 summary 내용도 없습니다.")
                    # 이미 title 컴포넌트는 추가되어 있을 수 있음
                    if not any(comp.get("type") == "paragraph" for comp in all_components):  # 내용이 전혀 없는 경우
                        all_components.append(create_paragraph({"content": "보고서 내용을 생성하지 못했습니다."}))
                    if not formatted_response:  # 텍스트 응답도 비어있다면
                        formatted_response = "보고서 내용을 생성하지 못했습니다."

            # 결과 저장 (플레이스홀더 제거된 텍스트 사용)
            state["answer"] = summary
            state["components"] = all_components

            # answer 키 설정 확인 로그 추가
            logger.info(f"[ResponseFormatterAgent] answer 키 설정 완료: {bool(state.get('answer'))}, 길이: {len(state.get('answer', ''))}")
            logger.info(f"[ResponseFormatterAgent] state 키들: {list(state.keys())}")

            # 처리 상태 업데이트
            state["processing_status"] = state.get("processing_status", {})
            state["processing_status"]["response_formatter"] = "completed"
            logger.info(f"[ResponseFormatterAgent] process 완료: 소요시간 {datetime.now() - start_time_process_query}")
            return state

        except Exception as e:
            logger.exception(f"Error in ResponseFormatterAgent: {str(e)}")
            state["error"] = f"응답 포맷터 에이전트 오류: {str(e)}"
            state["answer"] = "죄송합니다. 응답을 포맷팅하는 중 오류가 발생했습니다."
            state["components"] = []  # 오류 시 컴포넌트 초기화
            return state

    async def make_components(self, markdown_context: str):
        components = []
        # 마크다운을 줄 단위로 분리
        lines = markdown_context.split("\n")

        i = 0
        while i < len(lines):
            line = lines[i].strip()

            # 빈 줄 건너뛰기
            if not line:
                i += 1
                continue

            # 1. 헤딩 처리 (# 헤딩)
            heading_match = re.match(r"^(#{1,6})\s+(.+)$", line)
            if heading_match:
                level = len(heading_match.group(1))
                content = heading_match.group(2).strip()
                components.append(HeadingComponent(level=level, content=content))
                i += 1
                continue

            # 2. 테이블 처리 (| 구분 | 컬럼1 | 컬럼2 | ... |)
            if line.startswith("|") and "|" in line[1:]:
                # 테이블 시작 감지
                table_lines = []
                table_title = ""

                # 테이블 제목이 있는지 확인 (이전 줄이 단락이고 테이블에 관한 내용인 경우)
                if i > 0 and components and components[-1].type == "paragraph":
                    paragraph_content = components[-1].content
                    if "표" in paragraph_content or "데이터" in paragraph_content or "재무" in paragraph_content:
                        table_title = paragraph_content
                        # 이미 추가된 제목 단락을 제거 (테이블 컴포넌트에 제목으로 포함될 예정)
                        components.pop()

                # 테이블 줄 수집
                while i < len(lines) and lines[i].strip().startswith("|"):
                    table_lines.append(lines[i].strip())
                    i += 1

                # 테이블 파싱 시도
                try:
                    # 최소 2줄 이상 있어야 테이블로 인식 (헤더, 구분선)
                    if len(table_lines) >= 2:
                        # 헤더 파싱
                        header_line = table_lines[0]
                        header_cells = [cell.strip() for cell in header_line.split("|")[1:-1]]

                        # 구분선 확인 (두 번째 줄이 구분선인지 확인)
                        separator_line = table_lines[1]
                        # 구분선이 있으면 테이블로 처리
                        if any("-" in cell for cell in separator_line.split("|")[1:-1]):
                            # 데이터 행 파싱
                            data_rows = []
                            # 구분선 다음 줄부터 데이터 행
                            for row_line in table_lines[2:]:
                                row_cells = [cell.strip() for cell in row_line.split("|")[1:-1]]
                                if len(row_cells) == len(header_cells):
                                    row_data = {}
                                    for idx, header in enumerate(header_cells):
                                        # 숫자 데이터인 경우 숫자로 변환 시도
                                        cell_value = row_cells[idx] if idx < len(row_cells) else ""
                                        try:
                                            # None 체크 추가
                                            if cell_value is None or cell_value == "":
                                                cell_value = ""
                                            else:
                                                # 콤마 제거 후 숫자 변환 시도
                                                cell_value_clean = str(cell_value).replace(",", "")
                                                if "." in cell_value_clean and cell_value_clean.replace(".", "").replace("-", "").isdigit():
                                                    cell_value = float(cell_value_clean)
                                                elif cell_value_clean.replace("-", "").isdigit():
                                                    cell_value = int(cell_value_clean)
                                        except (ValueError, TypeError):
                                            # 숫자 변환 실패 시 텍스트 그대로 사용
                                            pass
                                        row_data[f"col{idx}"] = cell_value
                                        # 열 이름도 저장 (차트 변환 시 사용)
                                        row_data[f"header{idx}"] = header
                                    data_rows.append(row_data)

                            # 테이블을 차트로 변환 가능한지 확인
                            # 분기/연도 열이 있고 수치 데이터가 있는지 확인
                            period_col_idx = -1
                            metric_col_idx = -1
                            item_col_idx = -1

                            for idx, header in enumerate(header_cells):
                                header_lower = header.lower()
                                # 날짜/분기/연도 열 감지
                                if "날짜" in header_lower or "분기" in header_lower or "연도" in header_lower or "년" in header_lower or "q" in header_lower:
                                    period_col_idx = idx
                                # 항목/매출처/회사 열 감지
                                elif "항목" in header_lower or "매출처" in header_lower or "회사" in header_lower or "거래처" in header_lower:
                                    item_col_idx = idx
                                # 수치 데이터 열 감지
                                elif (
                                    "액" in header_lower
                                    or "이익" in header_lower
                                    or "매출" in header_lower
                                    or "값" in header_lower
                                    or "수치" in header_lower
                                    or "비중" in header_lower
                                ):
                                    metric_col_idx = idx

                            # 증감률 열 감지 (QoQ, YoY 등)
                            growth_rate_col_idx = -1
                            for idx, header in enumerate(header_cells):
                                header_lower = header.lower()
                                if (
                                    "증감률" in header_lower
                                    or "yoy" in header_lower
                                    or "qoq" in header_lower
                                    or "성장률" in header_lower
                                    or "전년비" in header_lower
                                    or "전분기비" in header_lower
                                    or "%" in header_lower
                                ):
                                    growth_rate_col_idx = idx
                                    break

                            # 차트 변환 플래그
                            chart_created = False

                            # 혼합 차트 가능성 확인 - 분기별 매출액과 증감률이 함께 있는 경우
                            if len(data_rows) > 1 and period_col_idx >= 0 and metric_col_idx >= 0 and growth_rate_col_idx >= 0:
                                try:
                                    # 기간별 데이터 정리
                                    periods = []
                                    metric_values = {}  # 매출액 등 막대 차트 데이터
                                    growth_values = {}  # 증감률 등 선 차트 데이터

                                    # 항목이 있으면 항목별로 구분
                                    if item_col_idx >= 0:
                                        # 항목별 매트릭과 증감률 추적
                                        for row in data_rows:
                                            period = str(row[f"col{period_col_idx}"])
                                            item = str(row[f"col{item_col_idx}"])
                                            metric_value = row[f"col{metric_col_idx}"] if isinstance(row[f"col{metric_col_idx}"], (int, float)) else 0
                                            growth_value = row[f"col{growth_rate_col_idx}"] if isinstance(row[f"col{growth_rate_col_idx}"], (int, float)) else 0

                                            if period not in periods:
                                                periods.append(period)

                                            metric_key = f"{item} {header_cells[metric_col_idx]}"
                                            growth_key = f"{item} {header_cells[growth_rate_col_idx]}"

                                            if metric_key not in metric_values:
                                                metric_values[metric_key] = {}

                                            if growth_key not in growth_values:
                                                growth_values[growth_key] = {}

                                            metric_values[metric_key][period] = metric_value
                                            growth_values[growth_key][period] = growth_value
                                    else:
                                        # 항목 없이 단순 매트릭과 증감률만 추적
                                        for row in data_rows:
                                            period = str(row[f"col{period_col_idx}"])
                                            metric_value = row[f"col{metric_col_idx}"] if isinstance(row[f"col{metric_col_idx}"], (int, float)) else 0
                                            growth_value = row[f"col{growth_rate_col_idx}"] if isinstance(row[f"col{growth_rate_col_idx}"], (int, float)) else 0

                                            if period not in periods:
                                                periods.append(period)

                                            if header_cells[metric_col_idx] not in metric_values:
                                                metric_values[header_cells[metric_col_idx]] = {}

                                            if header_cells[growth_rate_col_idx] not in growth_values:
                                                growth_values[header_cells[growth_rate_col_idx]] = {}

                                            metric_values[header_cells[metric_col_idx]][period] = metric_value
                                            growth_values[header_cells[growth_rate_col_idx]][period] = growth_value

                                    # 혼합 차트 생성을 위한 데이터셋 구성
                                    if len(periods) > 1 and len(metric_values) > 0 and len(growth_values) > 0:
                                        bar_datasets = []
                                        line_datasets = []

                                        # 막대 차트 데이터셋 구성
                                        for metric_label, period_values in metric_values.items():
                                            bar_datasets.append({"label": metric_label, "data": [period_values.get(period, 0) for period in periods]})

                                        # 선 차트 데이터셋 구성
                                        for growth_label, period_values in growth_values.items():
                                            line_datasets.append({"label": growth_label, "data": [period_values.get(period, 0) for period in periods]})

                                        # Y축 제목 설정
                                        y_axis_left_title = None
                                        y_axis_right_title = None

                                        if "매출액" in header_cells[metric_col_idx]:
                                            y_axis_left_title = "매출액 (억원)"
                                        elif "이익" in header_cells[metric_col_idx]:
                                            y_axis_left_title = "이익 (억원)"

                                        if (
                                            "증감률" in header_cells[growth_rate_col_idx]
                                            or "yoy" in header_cells[growth_rate_col_idx].lower()
                                            or "qoq" in header_cells[growth_rate_col_idx].lower()
                                        ):
                                            y_axis_right_title = "증감률 (%)"

                                        # 혼합 차트 컴포넌트 생성
                                        title = table_title if table_title else f"{header_cells[metric_col_idx]} 및 {header_cells[growth_rate_col_idx]} 추이"

                                        components.append(
                                            MixedChartComponent(
                                                title=title,
                                                data=MixedChartData(
                                                    labels=periods,
                                                    bar_datasets=bar_datasets,
                                                    line_datasets=line_datasets,
                                                    y_axis_left_title=y_axis_left_title,
                                                    y_axis_right_title=y_axis_right_title,
                                                ),
                                            )
                                        )
                                        chart_created = True
                                except Exception as mixed_chart_error:
                                    logger.error(f"혼합 차트 변환 오류: {mixed_chart_error}")

                            # 차트가 생성되지 않은 경우에만 테이블 컴포넌트 생성
                            if not chart_created:
                                table_component = TableComponent(
                                    title=table_title,
                                    data=TableData(
                                        headers=[TableHeader(key=f"col{idx}", label=header) for idx, header in enumerate(header_cells)], rows=data_rows if data_rows else [{}]
                                    ),
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
                            header_cells = [cell.strip() for cell in header_line.split("|")[1:-1]]

                            # 기본 빈 데이터라도 테이블 컴포넌트 생성
                            table_component = TableComponent(
                                title=table_title, data=TableData(headers=[TableHeader(key=f"col{idx}", label=header) for idx, header in enumerate(header_cells)], rows=[{}])
                            )
                            components.append(table_component)
                            continue
                    except Exception as e2:
                        logger.error(f"테이블 컴포넌트 생성 오류: {e2}")
                        # 정말 실패한 경우만 텍스트로 처리
                        "\n".join(table_lines)
                        components.append(ParagraphComponent(content="[테이블 형식] " + table_title))
                continue

            # 3. 코드 블록 처리 (```언어 ... ```)
            if line.startswith("```"):
                code_content = []
                language = line[3:].strip()
                i += 1

                while i < len(lines) and not lines[i].strip().startswith("```"):
                    code_content.append(lines[i])
                    i += 1

                if i < len(lines):  # 코드 블록 종료 확인
                    i += 1  # '```' 다음 줄로 이동

                components.append(CodeBlockComponent(language=language if language else None, content="\n".join(code_content)))
                continue

            # 4. 순서 있는 목록 처리 (1. 항목)
            if re.match(r"^\d+\.\s+", line):
                list_items = []
                ordered = True

                while i < len(lines) and re.match(r"^\d+\.\s+", lines[i].strip()):
                    content = re.sub(r"^\d+\.\s+", "", lines[i].strip())
                    list_items.append(ListItemComponent(content=content))
                    i += 1

                components.append(ListComponent(ordered=ordered, items=list_items))
                continue

            # 5. 순서 없는 목록 처리 (-, *, •)
            if re.match(r"^[\-\*\•]\s+", line):
                list_items = []
                ordered = False

                while i < len(lines) and re.match(r"^[\-\*\•]\s+", lines[i].strip()):
                    content = re.sub(r"^[\-\*\•]\s+", "", lines[i].strip())
                    list_items.append(ListItemComponent(content=content))
                    i += 1

                components.append(ListComponent(ordered=ordered, items=list_items))
                continue

            # 6. 단락 처리
            paragraph_lines = []

            while (
                i < len(lines)
                and lines[i].strip()
                and not (
                    re.match(r"^(#{1,6})\s+", lines[i])  # 헤딩이 아님
                    or re.match(r"^\d+\.\s+", lines[i])  # 순서 있는 목록이 아님
                    or re.match(r"^[\-\*\•]\s+", lines[i])  # 순서 없는 목록이 아님
                    or lines[i].strip().startswith("```")  # 코드 블록이 아님
                    or lines[i].strip().startswith("|")  # 테이블이 아님
                )
            ):
                paragraph_lines.append(lines[i])
                i += 1

            if paragraph_lines:
                components.append(ParagraphComponent(content=" ".join([line.strip() for line in paragraph_lines])))
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
        formatted_response = state.get("answer", "")

        # 헤더 컴포넌트 추가
        components.append(HeadingComponent(level=1, content=f"{stock_name}({stock_code}) 분석 결과"))

        # 빈 응답이면 기본 컴포넌트만 반환
        if not formatted_response.strip():
            components.append(ParagraphComponent(content="분석 결과를 찾을 수 없습니다."))
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

        # 1. 헤딩 컴포넌트 (여러 레벨)
        components.append(HeadingComponent(level=1, content=f"{stock_name}({stock_code}) 분석 결과"))

        # 2. 단락 컴포넌트
        components.append(ParagraphComponent(content=f"{stock_name}의 최근 실적과 시장 동향을 분석한 결과입니다. 아래 데이터를 참고하여 투자 결정에 활용하시기 바랍니다."))

        # 3. 부제목 (2단계 헤딩)
        components.append(HeadingComponent(level=2, content="주요 재무 지표"))

        # 4. 목록 컴포넌트 (순서 없는 목록)
        components.append(
            ListComponent(
                ordered=False,
                items=[
                    ListItemComponent(content="최근 분기 매출액: 7.8조원 (전년 대비 5.2% 증가)"),
                    ListItemComponent(content="영업이익률: 15.3% (전년 대비 2.1%p 상승)"),
                    ListItemComponent(content="ROE: 12.7% (업계 평균 대비 양호)"),
                    ListItemComponent(content="부채비율: 45.2% (안정적인 재무구조 유지)"),
                ],
            )
        )

        # 5. 두 번째 부제목
        components.append(HeadingComponent(level=2, content="실적 추이"))

        # 6. 바차트 컴포넌트
        components.append(
            BarChartComponent(
                title="분기별 매출 및 영업이익 추이",
                data=BarChartData(
                    labels=["1Q 2023", "2Q 2023", "3Q 2023", "4Q 2023", "1Q 2024"],
                    datasets=[
                        {"label": "매출액(조원)", "data": [63.7, 67.4, 71.2, 74.8, 78.5], "backgroundColor": "#4C9AFF"},
                        {"label": "영업이익(조원)", "data": [8.2, 9.1, 10.3, 11.2, 12.0], "backgroundColor": "#FF5630"},
                    ],
                ),
            )
        )

        # 7. 차트 설명 단락
        components.append(ParagraphComponent(content=f"위 차트는 {stock_name}의 최근 5개 분기 매출액과 영업이익 추이를 보여줍니다. 지속적인 성장세를 유지하고 있습니다."))

        # 8. 세 번째 부제목
        components.append(HeadingComponent(level=2, content="주가 동향"))

        # 9. 라인차트 컴포넌트
        components.append(
            LineChartComponent(
                title="최근 6개월 주가 추이",
                data=LineChartData(
                    labels=["11월", "12월", "1월", "2월", "3월", "4월"],
                    datasets=[
                        {"label": "주가(원)", "data": [67000, 70200, 72800, 69500, 74200, 76800], "borderColor": "#36B37E", "tension": 0.1},
                        {"label": "KOSPI(pt)", "data": [2450, 2520, 2580, 2510, 2650, 2700], "borderColor": "#FF8B00", "tension": 0.1, "borderDash": [5, 5]},
                    ],
                ),
            )
        )

        # 10. 네 번째 부제목
        components.append(HeadingComponent(level=2, content="주요 재무제표"))

        # 11. 테이블 컴포넌트
        components.append(
            TableComponent(
                title="요약 재무제표",
                data=TableData(
                    headers=[
                        TableHeader(key="item", label="항목"),
                        TableHeader(key="2022", label="2022년"),
                        TableHeader(key="2023", label="2023년"),
                        TableHeader(key="yoy", label="증감률(%)"),
                    ],
                    rows=[
                        {"item": "매출액", "2022": "280조원", "2023": "302조원", "yoy": "+7.9%"},
                        {"item": "영업이익", "2022": "36.5조원", "2023": "42.8조원", "yoy": "+17.3%"},
                        {"item": "당기순이익", "2022": "28.1조원", "2023": "33.7조원", "yoy": "+19.9%"},
                        {"item": "자산총계", "2022": "420.2조원", "2023": "456.8조원", "yoy": "+8.7%"},
                        {"item": "부채총계", "2022": "187.5조원", "2023": "195.2조원", "yoy": "+4.1%"},
                        {"item": "자본총계", "2022": "232.7조원", "2023": "261.6조원", "yoy": "+12.4%"},
                    ],
                ),
            )
        )

        # 12. 다섯 번째 부제목
        components.append(HeadingComponent(level=2, content="산업 비교 분석"))

        # 13. 순서 있는 목록
        components.append(
            ListComponent(
                ordered=True,
                items=[
                    ListItemComponent(content="시장점유율: 글로벌 시장에서 1위 유지 (점유율 22.3%)"),
                    ListItemComponent(content="기술 경쟁력: 주요 경쟁사 대비 R&D 투자금액 15% 이상 높음"),
                    ListItemComponent(content="수익성: 업계 평균 영업이익률 9.7% 대비 5.6%p 높은 수준"),
                    ListItemComponent(content="성장성: 2024년 예상 성장률 8.5%로 업계 평균(5.2%) 상회"),
                ],
            )
        )

        # 14. 여섯 번째 부제목
        components.append(HeadingComponent(level=2, content="코드 예시"))

        # 15. 코드 블록 컴포넌트
        components.append(
            CodeBlockComponent(
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
            """,
            )
        )

        # 16. 일곱 번째 부제목
        components.append(HeadingComponent(level=2, content="투자 의견"))

        # 17. 마지막 단락
        components.append(
            ParagraphComponent(
                content=f"{stock_name}는 안정적인 재무구조와 지속적인 성장세를 보이고 있으며, 업계 내 경쟁우위를 유지하고 있습니다. 단기적인 시장 변동성에도 불구하고 중장기 성장 잠재력이 높다고 판단됩니다. 다만, 글로벌 경제 불확실성과 산업 내 경쟁 심화는 리스크 요인으로 작용할 수 있습니다."
            )
        )

        # 18. 이미지 컴포넌트 (샘플)
        components.append(ImageComponent(url="https://example.com/chart_image.png", alt="삼성전자 사업부문별 매출 비중", caption="2023년 사업부문별 매출 비중"))

        # 19. 면책조항
        components.append(ParagraphComponent(content="※ 위 정보는 투자 참고 목적으로 제공되며, 투자 결정은 개인의 판단에 따라 신중하게 이루어져야 합니다."))

        return components

    def _restore_placeholders_in_component(self, component_dict: Dict[str, Any], mask_to_placeholder: Dict[str, str]) -> Dict[str, Any]:
        """
        컴포넌트의 텍스트 필드에서 마스크를 원래 플레이스홀더로 복원합니다.
        """
        if not component_dict or not mask_to_placeholder:
            return component_dict

        # 복사본 생성
        restored_component = component_dict.copy()

        # 텍스트 필드들을 검사하여 마스크 복원
        text_fields = ["content", "title", "alt", "caption"]

        for field in text_fields:
            if field in restored_component and isinstance(restored_component[field], str):
                original_text = restored_component[field]
                restored_text = original_text

                # 모든 마스크를 플레이스홀더로 복원
                for mask, placeholder in mask_to_placeholder.items():
                    if mask in restored_text:
                        restored_text = restored_text.replace(mask, placeholder)

                restored_component[field] = restored_text

        # 리스트 항목들도 처리 (list 컴포넌트의 경우)
        if "items" in restored_component and isinstance(restored_component["items"], list):
            restored_items = []
            for item in restored_component["items"]:
                if isinstance(item, dict) and "content" in item:
                    restored_item = item.copy()
                    original_content = restored_item["content"]
                    restored_content = original_content

                    for mask, placeholder in mask_to_placeholder.items():
                        if mask in restored_content:
                            restored_content = restored_content.replace(mask, placeholder)

                    restored_item["content"] = restored_content
                    restored_items.append(restored_item)
                else:
                    restored_items.append(item)

            restored_component["items"] = restored_items

        return restored_component


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
    if content.startswith("# "):
        content = content[2:]
    elif content.startswith("## "):
        content = content[3:]
    elif content.startswith("### "):
        content = content[4:]

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
def create_table(headers: List[Dict[str, str]], rows: List[Dict[str, Any]], title: Optional[str] = None) -> Dict:
    """테이블 컴포넌트를 생성합니다.
    headers는 [{"key": "col0", "label": "항목명"}] 형식의 헤더 목록,
    rows는 테이블 데이터,
    title은 테이블 제목(선택적)입니다."""
    table_headers = [TableHeader(**header) for header in headers]
    return TableComponent(title=title, data=TableData(headers=table_headers, rows=rows)).dict()


@tool
def create_bar_chart(title: str, labels: List[str], datasets: List[Dict[str, Any]]) -> Dict:
    """바 차트 컴포넌트를 생성합니다.
    title은 차트 제목,
    labels은 x축 라벨,
    y_axis_left_title은 왼쪽 Y축 제목/단위 (선택, 예: "매출액 (억원)"),
    datasets는 [{"label": "매출액", "data": [100, 200], "backgroundColor": "#4C9AFF"}] 형식의 데이터셋 목록입니다.
    backgroundColor는 흰색에 가까운 색상을 하지 않습니다.
    """
    # 뚜렷하게 구분되는 색상 팔레트 (서로 다른 색상)
    color_palette = [
        "#FF5630",  # 빨간색
        "#36B37E",  # 녹색
        "#4C9AFF",  # 파란색
        "#FFAB00",  # 주황색
        "#6554C0",  # 보라색
        "#00B8D9",  # 청록색
        "#E91E63",  # 핑크색
        "#8BC34A",  # 라이트 그린
        "#795548",  # 갈색
        "#FF9800",  # 다른 주황색
        "#9C27B0",  # 보라색 계열
        "#607D8B",  # 블루 그레이
        "#F44336",  # 다른 빨간색
        "#009688",  # 틸색
        "#3F51B5",  # 인디고
        "#FFC107",  # 노란색
    ]

    # 이미 사용된 색상 추적
    used_colors = set()

    # 데이터셋이 1개인 경우 랜덤하게 색상 선택
    import random

    random_start = random.randint(0, len(color_palette) - 1) if len(datasets) == 1 else 0

    for i, dataset in enumerate(datasets):
        if "backgroundColor" not in dataset:
            assigned_color = None

            # 사용되지 않은 색상 중에서 순차적으로 선택
            for j in range(len(color_palette)):
                color_idx = (random_start + i + j) % len(color_palette)
                candidate_color = color_palette[color_idx]
                if candidate_color not in used_colors:
                    assigned_color = candidate_color
                    used_colors.add(assigned_color)
                    break

            # 모든 색상이 사용된 경우 순환하여 할당
            if not assigned_color:
                color_idx = (random_start + i) % len(color_palette)
                assigned_color = color_palette[color_idx]

            dataset["backgroundColor"] = assigned_color

    return BarChartComponent(title=title, data=BarChartData(labels=labels, datasets=datasets)).dict()


@tool
def create_line_chart(title: str, labels: List[str], datasets: List[Dict[str, Any]]) -> Dict:
    """라인 차트 컴포넌트를 생성합니다.
    title은 차트 제목,
    labels은 x축 라벨,
    datasets는 [{"label": "주가(원)", "data": [67000, 70200], "borderColor": "#36B37E"}] 형식의 데이터셋 목록입니다."""
    # 데이터셋에 색상이 없는 경우 기본 색상 할당
    color_palette = ["#36B37E", "#4C9AFF", "#FF5630", "#FFAB00", "#6554C0", "#00B8D9", "#8993A4"]

    # 데이터셋이 1개인 경우 랜덤하게 색상 선택
    import random

    random_start = random.randint(0, len(color_palette) - 1) if len(datasets) == 1 else 0

    # 이미 할당된 색상 추적
    used_colors = set()

    # 항목별 색상 매핑을 위한 사전
    item_colors = {}

    # 증감률 유형별 변형 색상을 위한 오프셋
    rate_type_variations = {
        "yoy": 0,  # YoY는 기본 색상
        "전년": 0,
        "qoq": 1,  # QoQ는 기본 색상에서 1번 오프셋
        "전분기": 1,
        "mom": 2,  # MoM은 기본 색상에서 2번 오프셋
        "전월": 2,
    }

    # 주요 항목 키워드 (우선 매칭할 키워드)
    major_items = ["매출액", "매출", "영업이익", "순이익", "당기순이익", "자산", "부채", "자본"]

    for i, dataset in enumerate(datasets):
        if "borderColor" not in dataset:
            label = dataset.get("label", "")
            label_lower = label.lower()

            # 라벨에서 항목명과 증감률 유형 추출 시도
            item_name = None
            rate_type = None

            # 패턴 1: "항목명(증감률유형)" - 예: "매출액(YoY)", "영업이익(QoQ)"
            pattern1_match = re.search(r"^(.*?)\s*\(\s*(yoy|qoq|mom|전년|전분기|전월)\s*\)", label_lower, re.IGNORECASE)

            # 패턴 2: "항목명 증감률유형" - 예: "매출액 YoY", "영업이익 QoQ"
            pattern2_match = re.search(r"^(.*?)\s+(yoy|qoq|mom|전년|전분기|전월)$", label_lower, re.IGNORECASE)

            if pattern1_match:
                item_name = pattern1_match.group(1).strip()
                rate_type = pattern1_match.group(2).lower()
                # logger.info(f"패턴1 매칭: '{label}' -> 항목: '{item_name}', 증감률: '{rate_type}'")
            elif pattern2_match:
                item_name = pattern2_match.group(1).strip()
                rate_type = pattern2_match.group(2).lower()
                # logger.info(f"패턴2 매칭: '{label}' -> 항목: '{item_name}', 증감률: '{rate_type}'")
            else:
                # 기타 패턴: 주요 항목이 포함되어 있는지 확인
                for item in major_items:
                    if item.lower() in label_lower:
                        item_name = item.lower()

                        # 증감률 유형 확인
                        for rate_key in rate_type_variations.keys():
                            if rate_key in label_lower:
                                rate_type = rate_key
                                break

                        break

            assigned_color = None

            # 항목명과 증감률 유형이 모두 식별된 경우
            if item_name and rate_type:
                # 해당 항목의 기본 색상이 아직 없으면 할당
                if item_name not in item_colors:
                    # 사용 가능한 색상 중에서 선택
                    available_colors = [c for c in color_palette if c not in used_colors]
                    if available_colors:
                        item_colors[item_name] = available_colors[0]
                        used_colors.add(available_colors[0])
                    else:
                        # 사용 가능한 색상이 없으면 팔레트에서 순환하여 선택
                        palette_index = len(item_colors) % len(color_palette)
                        item_colors[item_name] = color_palette[palette_index]

                # 증감률 유형에 따라 색상 변형
                base_color = item_colors.get(item_name)
                if base_color:
                    # 기본 색상에 변형 적용
                    offset = rate_type_variations.get(rate_type, 0)
                    if offset == 0:  # YoY 또는 기본
                        assigned_color = base_color
                    else:
                        # 팔레트 내에서 오프셋을 적용한 색상 선택
                        base_index = color_palette.index(base_color) if base_color in color_palette else 0
                        variant_index = (base_index + offset) % len(color_palette)
                        assigned_color = color_palette[variant_index]

                    # logger.info(f"라인 데이터셋 '{label}': 항목 '{item_name}', 증감률 '{rate_type}'에 색상 {assigned_color} 할당")

            # 항목별 할당 실패 시 일반 로직으로 색상 할당
            if not assigned_color:
                # 키워드 기반으로 증감률 유형만 식별된 경우
                if rate_type:
                    for offset_key, offset_value in rate_type_variations.items():
                        if offset_key == rate_type:
                            # 해당 증감률 유형에 맞는 색상 선택
                            color_index = (i + offset_value) % len(color_palette)
                            assigned_color = color_palette[color_index]
                            # logger.info(f"라인 데이터셋 '{label}': 증감률 '{rate_type}'에 색상 {assigned_color} 할당")
                            break

                # 여전히 할당 실패 시 사용 가능한 색상 중 하나 선택
                if not assigned_color:
                    available_colors = [c for c in color_palette if c not in used_colors]
                    if available_colors:
                        assigned_color = available_colors[0]
                        used_colors.add(assigned_color)
                    else:
                        # 모든 색상이 사용된 경우 인덱스 기반으로 할당 (데이터셋이 1개인 경우 랜덤 시작점 사용)
                        color_idx = (random_start + i) % len(color_palette)
                        assigned_color = color_palette[color_idx]

                    # logger.info(f"라인 데이터셋 '{label}': 자동 색상 {assigned_color} 할당")

            # 색상 할당 및 사용된 색상 추적
            dataset["borderColor"] = assigned_color
            used_colors.add(assigned_color)
        else:
            used_colors.add(dataset["borderColor"])
            # logger.info(f"라인 데이터셋 '{dataset.get('label')}': 기존 색상 {dataset['borderColor']} 유지")

        # 선 굵기 설정
        if "borderWidth" not in dataset:
            dataset["borderWidth"] = 2

        # 곡선 부드러움 설정
        if "tension" not in dataset:
            dataset["tension"] = 0.1

    return LineChartComponent(title=title, data=LineChartData(labels=labels, datasets=datasets)).dict()


@tool
def create_mixed_chart(
    title: str,
    labels: List[str],
    bar_datasets: List[Dict[str, Any]],
    line_datasets: List[Dict[str, Any]],
    y_axis_left_title: Optional[str] = None,
    y_axis_right_title: Optional[str] = None,
) -> Dict:
    """혼합 차트 컴포넌트를 생성합니다. 막대 차트와 선 차트가 결합된 차트입니다.
    title은 차트 제목,
    labels은 x축 라벨,
    bar_datasets는 왼쪽 Y축에 표시될 막대 차트 데이터셋 목록 (예: [{"label": "매출액 (억원)", "data": [100, 200]}]),
    line_datasets는 오른쪽 Y축에 표시될 선 차트 데이터셋 목록입니다.

    중요: line_datasets의 각 항목은 구체적인 라벨을 가져야 합니다:
    - 올바른 예: [{"label": "매출액 YoY (%)", "data": [5.2, 7.3]}, {"label": "영업이익 YoY (%)", "data": [8.1, 9.2]}]
    - 잘못된 예: [{"label": "YoY (%)", "data": [5.2, 7.3]}, {"label": "YoY (%)", "data": [8.1, 9.2]}]

    bar_datasets와 line_datasets의 개수가 같은 경우, 각각은 동일한 항목에 대한 값과 증감률을 나타냅니다.
    y_axis_left_title은 왼쪽 Y축 제목 (선택, 예: "억원"),
    y_axis_right_title은 오른쪽 Y축 제목 (선택, 예: "%")
    """
    # Line 데이터셋 라벨 개선 로직
    # 같은 라벨이 여러 개 있는 경우, bar_datasets의 라벨을 참조하여 구체적인 라벨로 변경
    if len(bar_datasets) == len(line_datasets):
        unique_line_labels = set()
        for i, line_dataset in enumerate(line_datasets):
            line_label = line_dataset.get("label", "")
            # 동일한 라벨이 반복되거나 너무 일반적인 경우
            if line_label in unique_line_labels or line_label in ["YoY (%)", "QoQ (%)", "증감률 (%)", "%", "증감률"]:
                # 대응하는 bar_dataset의 라벨에서 항목명 추출
                if i < len(bar_datasets):
                    bar_label = bar_datasets[i].get("label", "")
                    # bar_label에서 항목명 추출 (예: "매출액 (억원)" -> "매출액")
                    item_name = bar_label.split(" (")[0].split("(")[0].strip()

                    # 원래 line_label에서 증감률 타입 추출
                    if "yoy" in line_label.lower() or "전년" in line_label:
                        rate_type = "YoY"
                    elif "qoq" in line_label.lower() or "전분기" in line_label:
                        rate_type = "QoQ"
                    elif "mom" in line_label.lower() or "전월" in line_label:
                        rate_type = "MoM"
                    else:
                        rate_type = "YoY"  # 기본값

                    # 새로운 구체적인 라벨 생성
                    new_label = f"{item_name} {rate_type} (%)"
                    line_dataset["label"] = new_label
                    unique_line_labels.add(new_label)
                else:
                    unique_line_labels.add(line_label)
            else:
                unique_line_labels.add(line_label)

                # 막대 차트 데이터셋에 색상 할당
    bar_color_palette = ["#4C9AFF", "#36B37E", "#FF5630", "#FFAB00", "#6554C0", "#00B8D9"]

    # 데이터셋이 1개인 경우 랜덤하게 색상 선택
    import random

    random_start = random.randint(0, len(bar_color_palette) - 1) if len(bar_datasets) == 1 else 0

    for i, dataset in enumerate(bar_datasets):
        if "backgroundColor" not in dataset:
            # 특정 키워드에 따라 색상 할당
            label_lower = dataset.get("label", "").lower()
            if "매출" in label_lower or "revenue" in label_lower or "sales" in label_lower:
                dataset["backgroundColor"] = "#4C9AFF"  # 매출은 파란색
            elif "영업이익" in label_lower:
                dataset["backgroundColor"] = "#FC847E"  # 영업이익 핑크빛빨간색
            elif "순이익" in label_lower:
                dataset["backgroundColor"] = "#92E492"  # 영업이익 녹색계열
            else:
                # 기본 색상 순환 (데이터셋이 1개인 경우 랜덤 시작점 사용)
                color_idx = (random_start + i) % len(bar_color_palette)
                dataset["backgroundColor"] = bar_color_palette[color_idx]

    # 선 차트 데이터셋에 색상 할당
    # 기본 색상 팔레트 확장 (중복 방지를 위해 다양한 색상 추가)
    line_color_palette = [
        "#FF5630",
        "#FFAB00",
        "#6554C0",
        "#00B8D9",
        "#8993A4",
        "#36B37E",
        "#998DD9",
        "#E95D0F",
        "#0747A6",
        "#5243AA",
        "#00875A",
        "#D13438",
        "#0052CC",
        "#42526E",
        "#E37933",
    ]

    # 데이터셋이 1개인 경우 랜덤하게 색상 선택
    import random

    random_start = random.randint(0, len(line_color_palette) - 1) if len(line_datasets) == 1 else 0

    # 이미 할당된 색상 추적
    used_colors = set()

    # 항목별 색상 매핑을 위한 사전
    item_colors = {}

    # 증감률 유형별 변형 색상을 위한 오프셋
    rate_type_variations = {
        "yoy": 0,  # YoY는 기본 색상
        "전년": 0,
        "qoq": 1,  # QoQ는 기본 색상에서 1번 오프셋
        "전분기": 1,
        "mom": 2,  # MoM은 기본 색상에서 2번 오프셋
        "전월": 2,
    }

    # 주요 항목 키워드 (우선 매칭할 키워드)
    major_items = ["매출액", "매출", "영업이익", "순이익", "당기순이익", "자산", "부채", "자본"]

    for i, dataset in enumerate(line_datasets):
        # if "borderColor" not in dataset:
        label = dataset.get("label", "")
        label_lower = label.lower()

        # 라벨에서 항목명과 증감률 유형 추출 시도
        item_name = None
        rate_type = None

        # 패턴 1: "항목명(증감률유형)" - 예: "매출액(YoY)", "영업이익(QoQ)"
        pattern1_match = re.search(r"^(.*?)\s*\(\s*(yoy|qoq|mom|전년|전분기|전월)\s*\)", label_lower, re.IGNORECASE)

        # 패턴 2: "항목명 증감률유형" - 예: "매출액 YoY", "영업이익 QoQ"
        pattern2_match = re.search(r"^(.*?)\s+(yoy|qoq|mom|전년|전분기|전월)$", label_lower, re.IGNORECASE)

        if pattern1_match:
            item_name = pattern1_match.group(1).strip()
            rate_type = pattern1_match.group(2).lower()
            # logger.info(f"패턴1 매칭: '{label}' -> 항목: '{item_name}', 증감률: '{rate_type}'")
        elif pattern2_match:
            item_name = pattern2_match.group(1).strip()
            rate_type = pattern2_match.group(2).lower()
            # logger.info(f"패턴2 매칭: '{label}' -> 항목: '{item_name}', 증감률: '{rate_type}'")
        else:
            # 기타 패턴: 주요 항목이 포함되어 있는지 확인
            for item in major_items:
                if item.lower() in label_lower:
                    item_name = item.lower()

                    # 증감률 유형 확인
                    for rate_key in rate_type_variations.keys():
                        if rate_key in label_lower:
                            rate_type = rate_key
                            break

                    break

        assigned_color = None

        # 항목명과 증감률 유형이 모두 식별된 경우
        if item_name and rate_type:
            # 해당 항목의 기본 색상이 아직 없으면 할당
            if item_name not in item_colors:
                # 사용 가능한 색상 중에서 선택
                available_colors = [c for c in line_color_palette if c not in used_colors]
                if available_colors:
                    item_colors[item_name] = available_colors[0]
                    used_colors.add(available_colors[0])
                else:
                    # 사용 가능한 색상이 없으면 팔레트에서 순환하여 선택 (데이터셋이 1개인 경우 랜덤 시작점 사용)
                    palette_index = (random_start + len(item_colors)) % len(line_color_palette)
                    item_colors[item_name] = line_color_palette[palette_index]

            # 증감률 유형에 따라 색상 변형
            base_color = item_colors.get(item_name)
            if base_color:
                # 기본 색상에 변형 적용
                offset = rate_type_variations.get(rate_type, 0)
                if offset == 0:  # YoY 또는 기본
                    assigned_color = base_color
                else:
                    # 팔레트 내에서 오프셋을 적용한 색상 선택
                    base_index = line_color_palette.index(base_color) if base_color in line_color_palette else 0
                    variant_index = (base_index + offset) % len(line_color_palette)
                    assigned_color = line_color_palette[variant_index]

                # logger.info(f"라인 데이터셋 '{label}': 항목 '{item_name}', 증감률 '{rate_type}'에 색상 {assigned_color} 할당")

        # 항목별 할당 실패 시 일반 로직으로 색상 할당
        if not assigned_color:
            # 키워드 기반으로 증감률 유형만 식별된 경우
            if rate_type:
                for offset_key, offset_value in rate_type_variations.items():
                    if offset_key == rate_type:
                        # 해당 증감률 유형에 맞는 색상 선택 (데이터셋이 1개인 경우 랜덤 시작점 사용)
                        color_index = (random_start + i + offset_value) % len(line_color_palette)
                        assigned_color = line_color_palette[color_index]
                        # logger.info(f"라인 데이터셋 '{label}': 증감률 '{rate_type}'에 색상 {assigned_color} 할당")
                        break

            # 여전히 할당 실패 시 사용 가능한 색상 중 하나 선택
            if not assigned_color:
                available_colors = [c for c in line_color_palette if c not in used_colors]
                if available_colors:
                    assigned_color = available_colors[0]
                    used_colors.add(assigned_color)
                else:
                    # 모든 색상이 사용된 경우 인덱스 기반으로 할당 (데이터셋이 1개인 경우 랜덤 시작점 사용)
                    color_idx = (random_start + i) % len(line_color_palette)
                    assigned_color = line_color_palette[color_idx]

                # logger.info(f"라인 데이터셋 '{label}': 자동 색상 {assigned_color} 할당")

        # 색상 할당 및 사용된 색상 추적
        dataset["borderColor"] = assigned_color
        used_colors.add(assigned_color)
        # else:
        #     used_colors.add(dataset["borderColor"])
        #     logger.info(f"라인 데이터셋 '{dataset.get('label')}': 기존 색상 {dataset['borderColor']} 유지")

        # 선 굵기 설정
        if "borderWidth" not in dataset:
            dataset["borderWidth"] = 2

        # 곡선 부드러움 설정
        if "tension" not in dataset:
            dataset["tension"] = 0.1

        # 점선 효과 추가 (점선 패턴)
        if "borderDash" not in dataset:
            dataset["borderDash"] = [5, 5]

    return MixedChartComponent(
        title=title,
        data=MixedChartData(labels=labels, bar_datasets=bar_datasets, line_datasets=line_datasets, y_axis_left_title=y_axis_left_title, y_axis_right_title=y_axis_right_title),
    ).dict()


def create_price_chart(
    symbol: str,
    name: str,
    title: Optional[str] = None,
    candle_data: Optional[List[Dict[str, Any]]] = None,
    volume_data: Optional[List[Dict[str, Any]]] = None,
    moving_averages: Optional[List[Dict[str, Any]]] = None,
    support_lines: Optional[List[Dict[str, Any]]] = None,
    resistance_lines: Optional[List[Dict[str, Any]]] = None,
    period: Optional[str] = None,
    interval: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict:
    """주가차트 컴포넌트를 생성합니다.
    symbol은 종목코드, name은 종목명, title은 차트 제목,
    candle_data는 OHLCV 캔들 데이터, volume_data는 거래량 데이터,
    moving_averages는 이동평균선 데이터, support_lines는 지지선 데이터,
    resistance_lines는 저항선 데이터입니다."""

    # 기본 캔들 데이터가 없는 경우 빈 리스트로 초기화
    if candle_data is None:
        candle_data = []

    # 기본 제목 설정
    if title is None:
        title = f"{name}({symbol}) 주가차트"

    return PriceChartComponent(
        title=title,
        data=PriceChartData(
            symbol=symbol,
            name=name,
            candle_data=candle_data,
            volume_data=volume_data,
            moving_averages=moving_averages,
            support_lines=support_lines,
            resistance_lines=resistance_lines,
            period=period,
            interval=interval,
            metadata=metadata,
        ),
    ).dict()


def create_technical_indicator_chart(
    symbol: str,
    name: str,
    dates: List[str],
    indicators: List[Dict[str, Any]],
    title: Optional[str] = None,
    candle_data: Optional[List[Dict[str, Any]]] = None,
    y_axis_configs: Optional[Dict[str, Dict[str, Any]]] = None,
    period: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict:
    """기술적 지표 차트 컴포넌트를 생성합니다.
    symbol은 종목코드, name은 종목명, dates는 날짜 배열,
    indicators는 지표 데이터 목록(최대 5개), title은 차트 제목,
    candle_data는 선택적 주가 캔들 데이터입니다."""

    # 기본 제목 설정
    if title is None:
        title = f"{name}({symbol}) 기술적 지표 분석"

    # 지표 데이터 변환 및 검증
    processed_indicators = []
    # for i, indicator in enumerate(indicators[:5]):  # 최대 5개만 허용
    for i, indicator in enumerate(indicators):  # 최대 5개만 허용
        # directions 필드 처리 추가
        indicator_data = TechnicalIndicatorData(
            name=indicator.get("name", f"지표{i + 1}"),
            data=indicator.get("data", []),
            color=indicator.get("color"),
            chart_type=indicator.get("chart_type", "line"),
            y_axis_id=indicator.get("y_axis_id", "primary"),
            line_style=indicator.get("line_style", "solid"),
        )

        # directions 필드가 있으면 추가 (슈퍼트렌드용)
        if "directions" in indicator:
            indicator_data.directions = indicator.get("directions", [])

        processed_indicators.append(indicator_data)

    return TechnicalIndicatorChartComponent(
        title=title,
        data=TechnicalIndicatorChartData(
            symbol=symbol, name=name, dates=dates, candle_data=candle_data, indicators=processed_indicators, y_axis_configs=y_axis_configs, period=period, metadata=metadata
        ),
    ).dict()


@tool
def create_image(url: str, alt: str, caption: Optional[str] = None) -> Dict:
    """이미지 컴포넌트를 생성합니다. url은 이미지 주소, alt는 대체 텍스트, caption은 캡션(선택)입니다."""
    return ImageComponent(url=url, alt=alt, caption=caption).dict()


# 차트 생성 유틸리티 함수들 - 클래스 외부에서 사용 가능
def create_price_chart_component_directly(tech_agent_result: Dict[str, Any], stock_code: str, stock_name: str) -> Dict[str, Any]:
    """
    tech agent 결과를 사용하여 PriceChartComponent를 직접 생성합니다.
    """
    # 실제 데이터는 data 키 안에 있음
    actual_data = tech_agent_result.get("data", {})

    chart_data = actual_data.get("chart_data", [])
    chart_patterns = actual_data.get("chart_patterns", {})

    # OHLCV 데이터 변환
    candle_data = []

    if isinstance(chart_data, list) and chart_data:
        for i, item in enumerate(chart_data):
            if isinstance(item, dict):
                # timestamp를 date로 변환하거나 date 필드 사용
                time_value = item.get("date") or item.get("timestamp", "")

                # ISO 날짜 형식을 yyyy-mm-dd 형식으로 변환
                formatted_time = format_date_for_chart(time_value)

                candle_item = {
                    "time": formatted_time,
                    "open": safe_int(item.get("open", 0)),
                    "high": safe_int(item.get("high", 0)),
                    "low": safe_int(item.get("low", 0)),
                    "close": safe_int(item.get("close", 0)),
                    "volume": safe_int(item.get("volume", 0)),
                    "price_change_percent": safe_float(item.get("price_change_percent", 0)),
                }
                candle_data.append(candle_item)

    # 지지선/저항선 데이터 변환
    support_lines = []
    resistance_lines = []

    if chart_patterns:
        support_levels = chart_patterns.get("support_levels", [])
        resistance_levels = chart_patterns.get("resistance_levels", [])

        for level in support_levels:
            if level is not None:
                support_lines.append(
                    {
                        "price": safe_int(level),
                        "label": f"지지선 {level:,.0f}원",
                        "color": "#4ade80",  # 녹색
                        "show_label": True,
                        "label_position": "left",
                        "line_style": "dashed",
                        "line_width": 2,
                    }
                )

        for level in resistance_levels:
            if level is not None:
                resistance_lines.append(
                    {
                        "price": safe_int(level),
                        "label": f"저항선 {level:,.0f}원",
                        "color": "#f87171",  # 빨간색
                        "show_label": True,
                        "label_position": "left",
                        "line_style": "dashed",
                        "line_width": 2,
                    }
                )

    price_chart_component = create_price_chart(
        symbol=stock_code,
        name=stock_name,
        title="주가, 지지/저항 분석",  # title=f"{stock_name}({stock_code}) 주가차트 분석",
        candle_data=candle_data,
        support_lines=support_lines if support_lines else None,
        resistance_lines=resistance_lines if resistance_lines else None,
        period="1년",
        interval="1일",
        metadata={"source": "technical_analyzer_agent", "timestamp": datetime.now().isoformat()},
    )

    return price_chart_component


def create_trend_following_chart_component_directly(tech_agent_result: Dict[str, Any], stock_code: str, stock_name: str) -> Dict[str, Any]:
    """
    tech agent 결과를 사용하여 추세추종 지표 차트 컴포넌트를 생성합니다.
    ADX, ADR, 슈퍼트렌드 등 추세추종 지표들을 시각화합니다.
    """
    # logger.info(f"[기술지표차트] {stock_name}({stock_code}) 기술적 지표 차트 생성 시작")

    # 실제 데이터는 data 키 안에 있음
    actual_data = tech_agent_result.get("data", {})
    chart_indicators_data = actual_data.get("chart_indicators_data", {})
    chart_data = actual_data.get("chart_data", [])  # 캔들 데이터용

    # 날짜 배열 가져오기
    dates = chart_indicators_data.get("dates", [])

    if not dates:
        logger.warning("[기술지표차트] 날짜 데이터가 없어 기술적 지표 차트를 생성할 수 없습니다")
        return create_paragraph({"content": "기술적 지표 차트 데이터가 없습니다."})

    # 지표 데이터 목록 생성 (최대 5개)
    indicators = []

    # 1. ADX (Average Directional Index) - 추세 강도
    adx_data = chart_indicators_data.get("adx", [])
    if adx_data and any(x is not None for x in adx_data):
        processed_adx = [float(x) if x is not None else 0.0 for x in adx_data]
        indicators.append(
            {
                "name": "ADX (추세강도)",
                "data": processed_adx,
                "color": "#3b82f6",  # 파란색
                "chart_type": "line",
                "y_axis_id": "primary",
                "line_style": "solid",
            }
        )
        # logger.info(f"[기술지표차트] ADX 지표 추가 완료 - 데이터 포인트: {len(processed_adx)}개")

    # 2. +DI (Positive Directional Indicator)
    plus_di_data = chart_indicators_data.get("adx_plus_di", [])
    if plus_di_data and any(x is not None for x in plus_di_data) and len(indicators) < 5:
        processed_plus_di = [float(x) if x is not None else 0.0 for x in plus_di_data]
        indicators.append(
            {
                "name": "+DI (상승방향지수)",
                "data": processed_plus_di,
                "color": "#10b981",  # 녹색
                "chart_type": "line",
                "y_axis_id": "primary",
                "line_style": "solid",
            }
        )

    # 3. -DI (Negative Directional Indicator)
    minus_di_data = chart_indicators_data.get("adx_minus_di", [])
    if minus_di_data and any(x is not None for x in minus_di_data) and len(indicators) < 5:
        processed_minus_di = [float(x) if x is not None else 0.0 for x in minus_di_data]
        indicators.append(
            {
                "name": "-DI (하락방향지수)",
                "data": processed_minus_di,
                "color": "#ef4444",  # 빨간색
                "chart_type": "line",
                "y_axis_id": "primary",
                "line_style": "solid",
            }
        )

    # 4. 슈퍼트렌드 (SuperTrend)
    supertrend_data = chart_indicators_data.get("supertrend", [])
    supertrend_direction_data = chart_indicators_data.get("supertrend_direction", [])

    if supertrend_data and any(x is not None for x in supertrend_data) and len(indicators) < 5:
        processed_supertrend_values = [float(x) if x is not None else 0.0 for x in supertrend_data]

        processed_supertrend_directions = []
        for i, direction in enumerate(supertrend_direction_data):
            if direction == 1:
                processed_supertrend_directions.append(1.0)  # 상승추세
            elif direction == -1:
                processed_supertrend_directions.append(-1.0)  # 하락추세
            else:
                processed_supertrend_directions.append(0.0)  # 중립

        supertrend_indicator = {
            "name": "슈퍼트렌드",
            "data": processed_supertrend_values,
            "directions": processed_supertrend_directions,
            "color": "#f59e0b",  # 주황색
            "chart_type": "line",
            "y_axis_id": "secondary",
            "line_style": "solid",
        }

        indicators.append(supertrend_indicator)
        # logger.info(f"[기술지표차트] 슈퍼트렌드 지표 추가 완료 - 데이터 포인트: {len(processed_supertrend_values)}개")

    # 지표가 없는 경우 처리
    if not indicators:
        logger.warning("[기술지표차트] 사용 가능한 기술적 지표 데이터가 없습니다")
        return create_paragraph({"content": "기술적 지표 데이터가 충분하지 않습니다."})

    # Y축 설정
    y_axis_configs = {"primary": {"title": "ADX / DI 값", "position": "left", "color": "#3b82f6"}, "secondary": {"title": "가격(원)", "position": "right", "color": "#f59e0b"}}

    # 캔들 데이터 변환
    candle_data = []
    if isinstance(chart_data, list) and chart_data:
        for i, item in enumerate(chart_data):
            if isinstance(item, dict):
                time_value = item.get("date") or item.get("timestamp", "")
                formatted_time = format_date_for_chart(time_value)

                candle_item = {
                    "time": formatted_time,
                    "open": safe_int(item.get("open", 0)),
                    "high": safe_int(item.get("high", 0)),
                    "low": safe_int(item.get("low", 0)),
                    "close": safe_int(item.get("close", 0)),
                    "volume": safe_int(item.get("volume", 0)),
                    "price_change_percent": safe_float(item.get("price_change_percent", 0)),
                }
                candle_data.append(candle_item)

    metadata = {
        "description": "추세추종 지표 분석",
        "source": "technical_analyzer_agent",
        "timestamp": datetime.now().isoformat(),
        "chart_type": "technical_indicators",
        "indicators": [indicator["name"] for indicator in indicators],
        "data_points": len(dates),
        "candle_data_count": len(candle_data),
    }

    # 추세추종 지표 차트 컴포넌트 생성
    technical_indicator_chart = create_technical_indicator_chart(
        symbol=stock_code,
        name=stock_name,
        dates=dates,
        indicators=indicators,
        title="추세추종 지표 분석",  # title=f"{stock_name}({stock_code}) 추세추종 지표 분석",
        candle_data=candle_data if candle_data else None,
        y_axis_configs=y_axis_configs,
        period=None,
        metadata=metadata,
    )

    # logger.info(f"[기술지표차트] 추세추종 지표 차트 생성 완료 - 지표 개수: {len(indicators)}개")
    return technical_indicator_chart


def create_momentum_chart_component_directly(tech_agent_result: Dict[str, Any], stock_code: str, stock_name: str) -> Dict[str, Any]:
    """
    tech agent 결과를 사용하여 모멘텀 지표 차트 컴포넌트를 생성합니다.
    RSI, MACD 등 모멘텀 지표들을 시각화합니다.
    """
    # logger.info(f"[모멘텀지표차트] {stock_name}({stock_code}) 모멘텀 지표 차트 생성 시작")

    # 실제 데이터는 data 키 안에 있음
    actual_data = tech_agent_result.get("data", {})
    chart_indicators_data = actual_data.get("chart_indicators_data", {})
    chart_data = actual_data.get("chart_data", [])

    # 날짜 배열 가져오기
    dates = chart_indicators_data.get("dates", [])

    if not dates:
        logger.warning("[모멘텀지표차트] 날짜 데이터가 없어 모멘텀 지표 차트를 생성할 수 없습니다")
        return create_paragraph({"content": "모멘텀 지표 차트 데이터가 없습니다."})

    # 지표 데이터 목록 생성
    indicators = []

    # 1. RSI (Relative Strength Index)
    rsi_data = chart_indicators_data.get("rsi", [])
    if rsi_data and any(x is not None for x in rsi_data):
        processed_rsi = [safe_float(x) for x in rsi_data]
        indicators.append(
            {
                "name": "RSI (14일)",
                "data": processed_rsi,
                "color": "#e91e63",  # 핑크색
                "chart_type": "line",
                "y_axis_id": "primary",
                "line_style": "solid",
            }
        )

    # 2. MACD Line
    macd_line_data = chart_indicators_data.get("macd", [])
    if macd_line_data and any(x is not None for x in macd_line_data) and len(indicators) < 5:
        processed_macd_line = [float(x) if x is not None else 0.0 for x in macd_line_data]
        indicators.append(
            {
                "name": "MACD Line",
                "data": processed_macd_line,
                "color": "#2196f3",  # 파란색
                "chart_type": "line",
                "y_axis_id": "hidden",
                "line_style": "solid",
            }
        )

    # 3. MACD Signal Line
    macd_signal_data = chart_indicators_data.get("macd_signal", [])
    if macd_signal_data and any(x is not None for x in macd_signal_data) and len(indicators) < 5:
        processed_macd_signal = [float(x) if x is not None else 0.0 for x in macd_signal_data]
        indicators.append(
            {
                "name": "MACD Signal",
                "data": processed_macd_signal,
                "color": "#ff9800",  # 주황색
                "chart_type": "line",
                "y_axis_id": "hidden",
                "line_style": "dashed",
            }
        )

    # 4. MACD Histogram
    macd_histogram_data = chart_indicators_data.get("macd_histogram", [])
    if macd_histogram_data and any(x is not None for x in macd_histogram_data) and len(indicators) < 5:
        processed_macd_histogram = [float(x) if x is not None else 0.0 for x in macd_histogram_data]
        indicators.append({"name": "MACD Histogram", "data": processed_macd_histogram, "color": "#4caf5080", "chart_type": "bar", "y_axis_id": "hidden", "line_style": "solid"})

    # 지표가 없는 경우 처리
    if not indicators:
        logger.warning("[모멘텀지표차트] 사용 가능한 모멘텀 지표 데이터가 없습니다")
        return create_paragraph({"content": "모멘텀 지표 데이터가 충분하지 않습니다."})

    # Y축 설정
    y_axis_configs = {
        "primary": {"title": "RSI", "position": "left", "color": "#e91e63", "min": 0, "max": 100},
        "hidden": {"title": "Hidden Axis", "position": "right", "color": "#2196f3", "display": False, "visible": False},
    }

    # 캔들 데이터 변환
    candle_data = []
    if isinstance(chart_data, list) and chart_data:
        for i, item in enumerate(chart_data):
            if isinstance(item, dict):
                time_value = item.get("date") or item.get("timestamp", "")
                formatted_time = format_date_for_chart(time_value)

                candle_item = {
                    "time": formatted_time,
                    "open": safe_int(item.get("open", 0)),
                    "high": safe_int(item.get("high", 0)),
                    "low": safe_int(item.get("low", 0)),
                    "close": safe_int(item.get("close", 0)),
                    "volume": safe_int(item.get("volume", 0)),
                    "price_change_percent": safe_float(item.get("price_change_percent", 0)),
                }
                candle_data.append(candle_item)

    # 메타데이터 생성
    metadata = {
        "description": "모멘텀 지표 분석",
        "source": "technical_analyzer_agent",
        "timestamp": datetime.now().isoformat(),
        "chart_type": "momentum_indicators",
        "indicators": [indicator["name"] for indicator in indicators],
        "data_points": len(dates),
        "candle_data_count": len(candle_data),
    }

    # 모멘텀 지표 차트 컴포넌트 생성
    momentum_chart = create_technical_indicator_chart(
        symbol=stock_code,
        name=stock_name,
        dates=dates,
        indicators=indicators,
        title="모멘텀 지표 분석",  # title=f"{stock_name}({stock_code}) 모멘텀 지표 분석",
        candle_data=candle_data if candle_data else None,
        y_axis_configs=y_axis_configs,
        period=None,
        metadata=metadata,
    )

    # logger.info(f"[모멘텀지표차트] 모멘텀 지표 차트 생성 완료 - 지표 개수: {len(indicators)}개")
    return momentum_chart
