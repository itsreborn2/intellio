"""
응답 포맷터 에이전트 모듈

이 모듈은 통합된 지식 정보를 사용자에게 이해하기 쉬운 
형태로 포맷팅하는 응답 포맷터 에이전트 클래스를 구현합니다.
"""

from datetime import datetime
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
    TableComponent, TableHeader, TableData, BarChartData, LineChartData,
    MixedChartComponent, MixedChartData, PriceChartComponent, PriceChartData,
    TechnicalIndicatorChartComponent, TechnicalIndicatorChartData, TechnicalIndicatorData
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
        self.agent_llm = get_agent_llm("response_formatter_agent")
        self.agent_llm_for_tools = get_agent_llm("gemini-lite")
        #self.agent_llm_for_tools = get_agent_llm("gemini-2.0-flash")
        logger.info(f"ResponseFormatterAgent initialized with provider: {self.agent_llm.get_provider()}, model: {self.agent_llm.get_model_name()}")
        self.parser = StrOutputParser()
        self.prompt_template = FRIENDLY_RESPONSE_FORMATTER_SYSTEM_PROMPT

        self.chart_placeholder = "[CHART_PLACEHOLDER:PRICE_CHART]"
        self.technical_indicator_chart_placeholder = "[CHART_PLACEHOLDER:TECHNICAL_INDICATOR_CHART]"
        
        # 새로운 플레이스홀더 추가
        self.trend_following_chart_placeholder = "[CHART_PLACEHOLDER:TREND_FOLLOWING_CHART]"
        self.momentum_chart_placeholder = "[CHART_PLACEHOLDER:MOMENTUM_CHART]"

    def _format_date_for_chart(self, date_value: Any) -> str:
        """
        다양한 날짜 형식을 yyyy-mm-dd 형식으로 변환합니다.
        
        Args:
            date_value: 날짜 값 (ISO 문자열, datetime 객체, 문자열 등)
            
        Returns:
            yyyy-mm-dd 형식의 날짜 문자열
        """
        try:
            if not date_value:
                return ""
            
            # 이미 yyyy-mm-dd 형식인지 확인
            if isinstance(date_value, str) and re.match(r'^\d{4}-\d{2}-\d{2}$', date_value):
                return date_value
            
            # ISO 형식 문자열 처리 (2025-06-12T00:00:00+09:00)
            if isinstance(date_value, str):
                # ISO 형식에서 날짜 부분만 추출
                if 'T' in date_value:
                    date_part = date_value.split('T')[0]
                    if re.match(r'^\d{4}-\d{2}-\d{2}$', date_part):
                        return date_part
                
                # 다른 형식의 날짜 문자열 파싱 시도
                try:
                    from datetime import datetime
                    parsed_date = datetime.fromisoformat(date_value.replace('Z', '+00:00'))
                    return parsed_date.strftime('%Y-%m-%d')
                except ValueError:
                    # 일반적인 날짜 파싱 시도
                    try:
                        parsed_date = datetime.strptime(date_value, '%Y-%m-%d')
                        return parsed_date.strftime('%Y-%m-%d')
                    except ValueError:
                        pass
            
            # datetime 객체 처리
            if hasattr(date_value, 'strftime'):
                return date_value.strftime('%Y-%m-%d')
            
            # 문자열로 변환 후 재시도
            date_str = str(date_value)
            if 'T' in date_str:
                date_part = date_str.split('T')[0]
                if re.match(r'^\d{4}-\d{2}-\d{2}$', date_part):
                    return date_part
            
            logger.warning(f"날짜 형식 변환 실패: {date_value} (type: {type(date_value)})")
            return str(date_value)  # 변환 실패 시 원본 반환
            
        except Exception as e:
            logger.error(f"날짜 형식 변환 중 오류: {e}, 입력값: {date_value}")
            return str(date_value) if date_value else ""
    
    def _create_price_chart_component_directly(self, tech_agent_result: Dict[str, Any], stock_code: str, stock_name: str) -> Dict[str, Any]:
        """
        tech agent 결과를 사용하여 PriceChartComponent를 직접 생성합니다.
        """
        logger.info(f"[DEBUG] _create_price_chart_component_directly 시작")
        logger.info(f"[DEBUG] tech_agent_result 키들: {list(tech_agent_result.keys()) if tech_agent_result else 'None'}")
        
        # tech_agent_result 구조 확인
        # tech_agent_result는 다음 구조를 가집니다:
        # {
        #   "agent_name": "technical_analyzer",
        #   "status": "success", 
        #   "data": {
        #     "chart_data": [{"date": "...", "open": ..., "high": ..., "low": ..., "close": ..., "volume": ...}, ...],
        #     "chart_patterns": {"support_levels": [...], "resistance_levels": [...], ...},
        #     ...
        #   },
        #   ...
        # }
        
        # 실제 데이터는 data 키 안에 있음
        actual_data = tech_agent_result.get("data", {})
        logger.info(f"[DEBUG] actual_data 키들: {list(actual_data.keys()) if actual_data else 'None'}")
        
        chart_data = actual_data.get("chart_data", [])
        chart_patterns = actual_data.get("chart_patterns", {})
        
        logger.info(f"[DEBUG] chart_data 타입: {type(chart_data)}, 길이: {len(chart_data) if isinstance(chart_data, list) else 'N/A'}")
        logger.info(f"[DEBUG] chart_patterns 키들: {list(chart_patterns.keys()) if chart_patterns else 'None'}")
        
        # OHLCV 데이터 변환
        candle_data = []
        logger.info(f"[DEBUG] OHLCV 데이터 변환 시작")
        
        if isinstance(chart_data, list) and chart_data:
            logger.info(f"[DEBUG] chart_data는 리스트이고 {len(chart_data)}개 항목 존재")
            for i, item in enumerate(chart_data):
                if i < 3:  # 처음 3개만 로깅
                    logger.info(f"[DEBUG] 데이터 항목 {i}: {item}")
                if isinstance(item, dict):
                    # timestamp를 date로 변환하거나 date 필드 사용
                    time_value = item.get("date") or item.get("timestamp", "")
                    
                    # ISO 날짜 형식을 yyyy-mm-dd 형식으로 변환
                    formatted_time = self._format_date_for_chart(time_value)
                    
                    candle_item = {
                        "time": formatted_time,
                        "open": int(item.get("open", 0)),
                        "high": int(item.get("high", 0)),
                        "low": int(item.get("low", 0)),
                        "close": int(item.get("close", 0)),
                        "volume": int(item.get("volume", 0))
                    }
                    candle_data.append(candle_item)
                    if i < 3:  # 처음 3개만 로깅
                        logger.info(f"[DEBUG] 캔들 데이터 추가: {candle_item}")
                else:
                    if i < 3:  # 처음 3개만 로깅
                        logger.warning(f"[DEBUG] 유효하지 않은 데이터 항목 {i}: {item}")
        else:
            logger.warning(f"[DEBUG] chart_data가 리스트가 아니거나 비어있음: {type(chart_data)}")
        
        # 지지선/저항선 데이터 변환
        support_lines = []
        resistance_lines = []
        
        if chart_patterns:
            support_levels = chart_patterns.get("support_levels", [])
            resistance_levels = chart_patterns.get("resistance_levels", [])
            
            logger.info(f"[DEBUG] support_levels: {support_levels}")
            logger.info(f"[DEBUG] resistance_levels: {resistance_levels}")
            
            for level in support_levels:
                if level is not None:
                    support_lines.append({
                        "price": int(level),
                        "label": f"지지선 {level:,.0f}원",
                        "color": "#4ade80",  # 녹색
                        "show_label": True,
                        "label_position": "left",
                        "line_style": "dashed",
                        "line_width": 2
                    })
            
            for level in resistance_levels:
                if level is not None:
                    resistance_lines.append({
                        "price": int(level),
                        "label": f"저항선 {level:,.0f}원",
                        "color": "#f87171",  # 빨간색
                        "show_label": True,
                        "label_position": "left", 
                        "line_style": "dashed",
                        "line_width": 2
                    })
        
        # PriceChartComponent 생성
        logger.info(f"[DEBUG] 최종 데이터 요약:")
        logger.info(f"[DEBUG] - candle_data 개수: {len(candle_data)}")
        logger.info(f"[DEBUG] - support_lines 개수: {len(support_lines)}")
        logger.info(f"[DEBUG] - resistance_lines 개수: {len(resistance_lines)}")
        
        price_chart_component = create_price_chart({
            "symbol": stock_code,
            "name": stock_name,
            "title": f"{stock_name}({stock_code}) 주가차트 분석",
            "candle_data": candle_data,
            "support_lines": support_lines if support_lines else None,
            "resistance_lines": resistance_lines if resistance_lines else None,
            "period": "1년",
            "interval": "1일",
            "metadata": {
                "source": "technical_analyzer_agent",
                "timestamp": datetime.now().isoformat()
            }
        })
        
        #logger.info(f"[DEBUG] 생성된 price_chart_component: {price_chart_component}")
        return price_chart_component
    
    def _create_trend_following_chart_component_directly(self, tech_agent_result: Dict[str, Any], stock_code: str, stock_name: str) -> Dict[str, Any]:
        """
        tech agent 결과를 사용하여 추세추종 지표 차트 컴포넌트를 생성합니다.
        ADX, ADR, 슈퍼트렌드 등 추세추종 지표들을 시각화합니다.
        """
        logger.info(f"[기술지표차트] {stock_name}({stock_code}) 기술적 지표 차트 생성 시작")
        
        # 실제 데이터는 data 키 안에 있음
        actual_data = tech_agent_result.get("data", {})
        chart_indicators_data = actual_data.get("chart_indicators_data", {})
        technical_indicators = actual_data.get("technical_indicators", {})
        chart_data = actual_data.get("chart_data", [])  # 캔들 데이터용
        
        logger.info(f"[기술지표차트] 차트 지표 데이터 키: {list(chart_indicators_data.keys()) if chart_indicators_data else '없음'}")
        logger.info(f"[기술지표차트] 차트 데이터 개수: {len(chart_data) if isinstance(chart_data, list) else '없음'}")
        
        # 날짜 배열 가져오기
        dates = chart_indicators_data.get("dates", [])
        
        if not dates:
            logger.warning("[기술지표차트] 날짜 데이터가 없어 기술적 지표 차트를 생성할 수 없습니다")
            return create_paragraph("기술적 지표 차트 데이터가 없습니다.")
        
        # 지표 데이터 목록 생성 (최대 5개)
        indicators = []
        
        # 1. ADX (Average Directional Index) - 추세 강도
        adx_data = chart_indicators_data.get("adx", [])
        if adx_data and any(x is not None for x in adx_data):
            # None 값을 0으로 치환
            processed_adx = [float(x) if x is not None else 0.0 for x in adx_data]
            indicators.append({
                "name": "ADX (추세강도)",
                "data": processed_adx,
                "color": "#3b82f6",  # 파란색
                "chart_type": "line",
                "y_axis_id": "secondary",
                "line_style": "solid"
            })
            logger.info(f"[기술지표차트] ADX 지표 추가 완료 - 데이터 포인트: {len(processed_adx)}개")
        
        # 2. +DI (Positive Directional Indicator)
        plus_di_data = chart_indicators_data.get("adx_plus_di", [])
        if plus_di_data and any(x is not None for x in plus_di_data) and len(indicators) < 5:
            processed_plus_di = [float(x) if x is not None else 0.0 for x in plus_di_data]
            indicators.append({
                "name": "+DI (상승방향지수)",
                "data": processed_plus_di,
                "color": "#10b981",  # 녹색
                "chart_type": "line",
                "y_axis_id": "secondary",
                "line_style": "solid"
            })
            logger.info(f"[기술지표차트] +DI 지표 추가 완료 - 데이터 포인트: {len(processed_plus_di)}개")
        
        # 3. -DI (Negative Directional Indicator)
        minus_di_data = chart_indicators_data.get("adx_minus_di", [])
        if minus_di_data and any(x is not None for x in minus_di_data) and len(indicators) < 5:
            processed_minus_di = [float(x) if x is not None else 0.0 for x in minus_di_data]
            indicators.append({
                "name": "-DI (하락방향지수)",
                "data": processed_minus_di,
                "color": "#ef4444",  # 빨간색
                "chart_type": "line",
                "y_axis_id": "secondary",
                "line_style": "solid"
            })
            logger.info(f"[기술지표차트] -DI 지표 추가 완료 - 데이터 포인트: {len(processed_minus_di)}개")
        
        # 4. ADR (Advance Decline Ratio)
        adr_data = chart_indicators_data.get("adr", [])
        if adr_data and any(x is not None for x in adr_data) and len(indicators) < 5:
            processed_adr = [float(x) if x is not None else 0.0 for x in adr_data]
            indicators.append({
                "name": "ADR (상승하락비율)",
                "data": processed_adr,
                "color": "#8b5cf6",  # 보라색
                "chart_type": "line",
                "y_axis_id": "secondary",
                "line_style": "solid"
            })
            logger.info(f"[기술지표차트] ADR 지표 추가 완료 - 데이터 포인트: {len(processed_adr)}개")
        
        # 5. 슈퍼트렌드 (SuperTrend)
        supertrend_data = chart_indicators_data.get("supertrend", [])
        supertrend_direction_data = chart_indicators_data.get("supertrend_direction", [])
        if supertrend_data and any(x is not None for x in supertrend_data) and len(indicators) < 5:
            # 슈퍼트렌드 실제 값 사용
            processed_supertrend_values = [float(x) if x is not None else 0.0 for x in supertrend_data]
            
            # 방향 데이터도 함께 전달 (프론트에서 색상 변경 등에 활용 가능)
            processed_supertrend_directions = []
            for direction in supertrend_direction_data:
                if direction == 1:
                    processed_supertrend_directions.append(1.0)  # 상승추세
                elif direction == -1:
                    processed_supertrend_directions.append(-1.0)  # 하락추세  
                else:
                    processed_supertrend_directions.append(0.0)  # 중립
            
            indicators.append({
                "name": "슈퍼트렌드",
                "data": processed_supertrend_values,  # 실제 가격 값 사용
                "values": processed_supertrend_values,  # 프론트에서 참조할 수 있도록 추가
                "directions": processed_supertrend_directions,  # 방향 정보도 추가
                "color": "#f59e0b",  # 주황색
                "chart_type": "line",  # 라인 차트로 변경
                "y_axis_id": "primary",  # 가격 캔들 차트와 동일한 Y축 사용 (왼쪽)
                "line_style": "solid"
            })
            logger.info(f"[기술지표차트] 슈퍼트렌드 지표 추가 완료 - 데이터 포인트: {len(processed_supertrend_values)}개")
        
        # 지표가 없는 경우 처리
        if not indicators:
            logger.warning("[기술지표차트] 사용 가능한 기술적 지표 데이터가 없습니다")
            return create_paragraph("기술적 지표 데이터가 충분하지 않습니다.")
        
        # Y축 설정 - 왼쪽은 캔들 데이터(주가) 기준, 오른쪽은 지표 값 기준
        y_axis_configs = {
            "primary": {
                "title": "가격 (원)",
                "position": "left",
                "color": "#f59e0b"
            },
            "secondary": {
                "title": "ADX / DI / ADR 값",
                "position": "right", 
                "color": "#3b82f6"
            }
        }
        
        # 현재 지표 값들을 포함한 설명 생성
        description_parts = []
        
        # ADX 현재값
        if adx_data and len(adx_data) > 0:
            adx_current = adx_data[-1]  # 마지막 값
            if adx_current is not None:
                if adx_current >= 25:
                    trend_strength = "강한 추세"
                elif adx_current <= 20:
                    trend_strength = "약한 추세"
                else:
                    trend_strength = "보통 추세"
                description_parts.append(f"ADX: {adx_current:.1f} ({trend_strength})")
        
        # ADR 현재값
        if adr_data and len(adr_data) > 0:
            adr_current = adr_data[-1]  # 마지막 값
            if adr_current is not None:
                if adr_current > 1.2:
                    adr_status = "상승 우세"
                elif adr_current < 0.8:
                    adr_status = "하락 우세"
                else:
                    adr_status = "균형"
                description_parts.append(f"ADR: {adr_current:.2f} ({adr_status})")
        
        # 슈퍼트렌드 현재값
        if supertrend_data and len(supertrend_data) > 0:
            supertrend_value = supertrend_data[-1]  # 마지막 값
            supertrend_direction = supertrend_direction_data[-1] if supertrend_direction_data and len(supertrend_direction_data) > 0 else None
            if supertrend_value is not None:
                if supertrend_direction == 1:
                    trend_signal = "상승추세"
                elif supertrend_direction == -1:
                    trend_signal = "하락추세"
                else:
                    trend_signal = "중립"
                description_parts.append(f"슈퍼트렌드: {supertrend_value:,.0f}원 ({trend_signal})")
        
        description = " | ".join(description_parts) if description_parts else "추세추종 지표 분석"
        
        # 메타데이터 생성
        # 캔들 데이터 변환 (price_chart_component_directly와 동일한 로직)
        candle_data = []
        logger.info(f"[기술지표차트] OHLCV 데이터 변환 시작")
        
        if isinstance(chart_data, list) and chart_data:
            logger.info(f"[기술지표차트] chart_data는 리스트이고 {len(chart_data)}개 항목 존재")
            for i, item in enumerate(chart_data):
                if i < 3:  # 처음 3개만 로깅
                    logger.info(f"[기술지표차트] 데이터 항목 {i}: {item}")
                if isinstance(item, dict):
                    # timestamp를 date로 변환하거나 date 필드 사용
                    time_value = item.get("date") or item.get("timestamp", "")
                    
                    # ISO 날짜 형식을 yyyy-mm-dd 형식으로 변환
                    formatted_time = self._format_date_for_chart(time_value)
                    
                    candle_item = {
                        "time": formatted_time,
                        "open": int(item.get("open", 0)),
                        "high": int(item.get("high", 0)),
                        "low": int(item.get("low", 0)),
                        "close": int(item.get("close", 0)),
                        "volume": int(item.get("volume", 0))
                    }
                    candle_data.append(candle_item)
                    if i < 3:  # 처음 3개만 로깅
                        logger.info(f"[기술지표차트] 캔들 데이터 추가: {candle_item}")
                else:
                    if i < 3:  # 처음 3개만 로깅
                        logger.warning(f"[기술지표차트] 유효하지 않은 데이터 항목 {i}: {item}")
        else:
            logger.warning(f"[기술지표차트] chart_data가 리스트가 아니거나 비어있음: {type(chart_data)}")
        
        metadata = {
            "description": description,
            "source": "technical_analyzer_agent",
            "timestamp": datetime.now().isoformat(),
            "chart_type": "technical_indicators",
            "indicators": [indicator["name"] for indicator in indicators],
            "data_points": len(dates),
            "candle_data_count": len(candle_data)
        }
        
        logger.info(f"[기술지표차트] 캔들 데이터 개수: {len(candle_data)}")
        
        # 기술적 지표 차트 컴포넌트 생성
        technical_indicator_chart = create_technical_indicator_chart({
            "symbol": stock_code,
            "name": stock_name,
            "dates": dates,
            "indicators": indicators,
            "title": f"{stock_name}({stock_code}) 기술적 지표 분석",
            "candle_data": candle_data if candle_data else None,  # 캔들 데이터 포함
            "y_axis_configs": y_axis_configs,
            "period": None,
            "metadata": metadata
        })
        
        logger.info(f"[기술지표차트] 추세추종 지표 차트 생성 완료 - 지표 개수: {len(indicators)}개")
        return technical_indicator_chart
    
    def _create_momentum_chart_component_directly(self, tech_agent_result: Dict[str, Any], stock_code: str, stock_name: str) -> Dict[str, Any]:
        """
        tech agent 결과를 사용하여 모멘텀 지표 차트 컴포넌트를 생성합니다.
        RSI, MACD 등 모멘텀 지표들을 시각화합니다.
        """
        logger.info(f"[모멘텀지표차트] {stock_name}({stock_code}) 모멘텀 지표 차트 생성 시작")
        
        # 실제 데이터는 data 키 안에 있음
        actual_data = tech_agent_result.get("data", {})
        chart_indicators_data = actual_data.get("chart_indicators_data", {})
        technical_indicators = actual_data.get("technical_indicators", {})
        chart_data = actual_data.get("chart_data", [])  # 캔들 데이터용
        
        logger.info(f"[모멘텀지표차트] 차트 지표 데이터 키: {list(chart_indicators_data.keys()) if chart_indicators_data else '없음'}")
        logger.info(f"[모멘텀지표차트] 차트 데이터 개수: {len(chart_data) if isinstance(chart_data, list) else '없음'}")
        
        # 날짜 배열 가져오기
        dates = chart_indicators_data.get("dates", [])
        
        if not dates:
            logger.warning("[모멘텀지표차트] 날짜 데이터가 없어 모멘텀 지표 차트를 생성할 수 없습니다")
            return create_paragraph("모멘텀 지표 차트 데이터가 없습니다.")
        
        # 지표 데이터 목록 생성 (최대 5개)
        indicators = []
        
        # 1. RSI (Relative Strength Index) - 과매수/과매도 구간
        rsi_data = chart_indicators_data.get("rsi", [])
        if rsi_data and any(x is not None for x in rsi_data):
            # None 값을 0으로 치환
            processed_rsi = [float(x) if x is not None else 0.0 for x in rsi_data]
            indicators.append({
                "name": "RSI (14일)",
                "data": processed_rsi,
                "color": "#e91e63",  # 핑크색
                "chart_type": "line",
                "y_axis_id": "primary",
                "line_style": "solid"
            })
            logger.info(f"[모멘텀지표차트] RSI 지표 추가 완료 - 데이터 포인트: {len(processed_rsi)}개")
        
        # 2. MACD Line
        macd_line_data = chart_indicators_data.get("macd_line", [])
        if macd_line_data and any(x is not None for x in macd_line_data) and len(indicators) < 5:
            processed_macd_line = [float(x) if x is not None else 0.0 for x in macd_line_data]
            indicators.append({
                "name": "MACD Line",
                "data": processed_macd_line,
                "color": "#2196f3",  # 파란색
                "chart_type": "line",
                "y_axis_id": "secondary",
                "line_style": "solid"
            })
            logger.info(f"[모멘텀지표차트] MACD Line 지표 추가 완료 - 데이터 포인트: {len(processed_macd_line)}개")
        
        # 3. MACD Signal Line
        macd_signal_data = chart_indicators_data.get("macd_signal", [])
        if macd_signal_data and any(x is not None for x in macd_signal_data) and len(indicators) < 5:
            processed_macd_signal = [float(x) if x is not None else 0.0 for x in macd_signal_data]
            indicators.append({
                "name": "MACD Signal",
                "data": processed_macd_signal,
                "color": "#ff9800",  # 주황색
                "chart_type": "line",
                "y_axis_id": "secondary",
                "line_style": "dashed"
            })
            logger.info(f"[모멘텀지표차트] MACD Signal 지표 추가 완료 - 데이터 포인트: {len(processed_macd_signal)}개")
        
        # 4. MACD Histogram
        macd_histogram_data = chart_indicators_data.get("macd_histogram", [])
        if macd_histogram_data and any(x is not None for x in macd_histogram_data) and len(indicators) < 5:
            processed_macd_histogram = [float(x) if x is not None else 0.0 for x in macd_histogram_data]
            indicators.append({
                "name": "MACD Histogram",
                "data": processed_macd_histogram,
                "color": "#4caf50",  # 녹색
                "chart_type": "bar",
                "y_axis_id": "secondary",
                "line_style": "solid"
            })
            logger.info(f"[모멘텀지표차트] MACD Histogram 지표 추가 완료 - 데이터 포인트: {len(processed_macd_histogram)}개")
        
        # 5. Stochastic %K
        stoch_k_data = chart_indicators_data.get("stoch_k", [])
        if stoch_k_data and any(x is not None for x in stoch_k_data) and len(indicators) < 5:
            processed_stoch_k = [float(x) if x is not None else 0.0 for x in stoch_k_data]
            indicators.append({
                "name": "Stochastic %K",
                "data": processed_stoch_k,
                "color": "#9c27b0",  # 보라색
                "chart_type": "line",
                "y_axis_id": "primary",
                "line_style": "solid"
            })
            logger.info(f"[모멘텀지표차트] Stochastic %K 지표 추가 완료 - 데이터 포인트: {len(processed_stoch_k)}개")
        
        # 지표가 없는 경우 처리
        if not indicators:
            logger.warning("[모멘텀지표차트] 사용 가능한 모멘텀 지표 데이터가 없습니다")
            return create_paragraph("모멘텀 지표 데이터가 충분하지 않습니다.")
        
        # Y축 설정
        y_axis_configs = {
            "primary": {
                "title": "RSI / Stochastic",
                "position": "left",
                "color": "#e91e63",
                "min": 0,
                "max": 100
            },
            "secondary": {
                "title": "MACD",
                "position": "right", 
                "color": "#2196f3"
            }
        }
        
        # 현재 지표 값들을 포함한 설명 생성
        description_parts = []
        
        # RSI 현재값
        if rsi_data and len(rsi_data) > 0:
            rsi_current = rsi_data[-1]  # 마지막 값
            if rsi_current is not None:
                if rsi_current >= 70:
                    rsi_status = "과매수 구간"
                elif rsi_current <= 30:
                    rsi_status = "과매도 구간"
                else:
                    rsi_status = "중립 구간"
                description_parts.append(f"RSI: {rsi_current:.1f} ({rsi_status})")
        
        # MACD 현재값
        if macd_line_data and len(macd_line_data) > 0:
            macd_current = macd_line_data[-1]  # 마지막 값
            macd_signal_current = macd_signal_data[-1] if macd_signal_data and len(macd_signal_data) > 0 else None
            if macd_current is not None:
                if macd_signal_current is not None:
                    if macd_current > macd_signal_current:
                        macd_status = "상승 신호"
                    elif macd_current < macd_signal_current:
                        macd_status = "하락 신호"
                    else:
                        macd_status = "중립"
                    description_parts.append(f"MACD: {macd_current:.2f} ({macd_status})")
                else:
                    description_parts.append(f"MACD: {macd_current:.2f}")
        
        description = " | ".join(description_parts) if description_parts else "모멘텀 지표 분석"
        
        # 캔들 데이터 변환 (price_chart_component_directly와 동일한 로직)
        candle_data = []
        logger.info(f"[모멘텀지표차트] OHLCV 데이터 변환 시작")
        
        if isinstance(chart_data, list) and chart_data:
            logger.info(f"[모멘텀지표차트] chart_data는 리스트이고 {len(chart_data)}개 항목 존재")
            for i, item in enumerate(chart_data):
                if i < 3:  # 처음 3개만 로깅
                    logger.info(f"[모멘텀지표차트] 데이터 항목 {i}: {item}")
                if isinstance(item, dict):
                    # timestamp를 date로 변환하거나 date 필드 사용
                    time_value = item.get("date") or item.get("timestamp", "")
                    
                    # ISO 날짜 형식을 yyyy-mm-dd 형식으로 변환
                    formatted_time = self._format_date_for_chart(time_value)
                    
                    candle_item = {
                        "time": formatted_time,
                        "open": int(item.get("open", 0)),
                        "high": int(item.get("high", 0)),
                        "low": int(item.get("low", 0)),
                        "close": int(item.get("close", 0)),
                        "volume": int(item.get("volume", 0))
                    }
                    candle_data.append(candle_item)
                    if i < 3:  # 처음 3개만 로깅
                        logger.info(f"[모멘텀지표차트] 캔들 데이터 추가: {candle_item}")
                else:
                    if i < 3:  # 처음 3개만 로깅
                        logger.warning(f"[모멘텀지표차트] 유효하지 않은 데이터 항목 {i}: {item}")
        else:
            logger.warning(f"[모멘텀지표차트] chart_data가 리스트가 아니거나 비어있음: {type(chart_data)}")
        
        # 메타데이터 생성
        metadata = {
            "description": description,
            "source": "technical_analyzer_agent",
            "timestamp": datetime.now().isoformat(),
            "chart_type": "momentum_indicators",
            "indicators": [indicator["name"] for indicator in indicators],
            "data_points": len(dates),
            "candle_data_count": len(candle_data)
        }
        
        logger.info(f"[모멘텀지표차트] 캔들 데이터 개수: {len(candle_data)}")
        
        # 모멘텀 지표 차트 컴포넌트 생성
        momentum_chart = create_technical_indicator_chart({
            "symbol": stock_code,
            "name": stock_name,
            "dates": dates,
            "indicators": indicators,
            "title": f"{stock_name}({stock_code}) 모멘텀 지표 분석",
            "candle_data": candle_data if candle_data else None,  # 캔들 데이터 포함
            "y_axis_configs": y_axis_configs,
            "period": None,
            "metadata": metadata
        })
        
        logger.info(f"[모멘텀지표차트] 모멘텀 지표 차트 생성 완료 - 지표 개수: {len(indicators)}개")
        return momentum_chart
     
    def _find_placeholder_in_component(self, component: Dict[str, Any]) -> str:
        """
        컴포넌트에서 플레이스홀더가 포함된 필드를 찾아 반환합니다.
        반환값: 플레이스홀더가 있는 필드명 (없으면 None)
        """
        component_type = component.get("type")
        logger.info(f"[DEBUG] _find_placeholder_in_component: type={component_type}")
        
        # 컴포넌트 타입별로 플레이스홀더 검색 필드 정의
        search_fields = {
            "paragraph": ["content"],
            "image": ["url", "alt", "caption"],
            "heading": ["content"],
            "code_block": ["content"],
            "table": ["title"]  # 필요에 따라 더 추가 가능
        }
        
        fields_to_search = search_fields.get(component_type, [])
        logger.info(f"[DEBUG] 검색할 필드 목록: {fields_to_search}")
        
        for field in fields_to_search:
            field_value = component.get(field, "")
            logger.info(f"[DEBUG] 필드 '{field}' 검사 중: '{str(field_value)[:50]}...' (type: {type(field_value)})")
            
            if isinstance(field_value, str) and self.chart_placeholder in field_value:
                logger.info(f"[DEBUG] 플레이스홀더 발견! 필드: {field}, 값: '{field_value}'")
                return field
            else:
                if isinstance(field_value, str):
                    logger.info(f"[DEBUG] 필드 '{field}'에서 플레이스홀더 없음")
                else:
                    logger.info(f"[DEBUG] 필드 '{field}'는 문자열이 아님: {type(field_value)}")
        
        logger.info(f"[DEBUG] 컴포넌트에서 플레이스홀더를 찾지 못함")
        return None
    
    def _insert_price_chart_at_marker(self, components: List[Dict[str, Any]], price_chart_component: Dict[str, Any]) -> None:
        """
        컴포넌트 리스트에서 플레이스홀더를 찾아서 주가차트 컴포넌트로 교체합니다.
        다양한 컴포넌트 타입의 여러 필드에서 플레이스홀더를 검색합니다.
        """
        logger.info(f"[DEBUG] _insert_price_chart_at_marker 시작")
        logger.info(f"[DEBUG] 입력 컴포넌트 개수: {len(components)}")
        logger.info(f"[DEBUG] 찾을 플레이스홀더: '{self.chart_placeholder}'")
        
        # 전체 컴포넌트에서 플레이스홀더 존재 여부 사전 확인
        placeholder_exists = False
        for idx, comp in enumerate(components):
            comp_type = comp.get("type", "unknown")
            if comp_type == "paragraph":
                content = comp.get("content", "")
                if self.chart_placeholder in content:
                    placeholder_exists = True
                    logger.info(f"[DEBUG] 컴포넌트 {idx} (paragraph)에서 플레이스홀더 발견: '{content[:100]}...'")
            elif comp_type == "image":
                url = comp.get("url", "")
                if self.chart_placeholder in url:
                    placeholder_exists = True
                    logger.info(f"[DEBUG] 컴포넌트 {idx} (image)에서 플레이스홀더 발견: url='{url}'")
        
        if not placeholder_exists:
            logger.warning(f"[DEBUG] 전체 컴포넌트에서 플레이스홀더 '{self.chart_placeholder}'를 찾을 수 없음")
        
        marker_found = False
        for i, component in enumerate(components):
            logger.info(f"[DEBUG] 컴포넌트 {i} 검사 중: type={component.get('type')}")
            
            placeholder_field = self._find_placeholder_in_component(component)
            logger.info(f"[DEBUG] 컴포넌트 {i} 플레이스홀더 필드 검색 결과: {placeholder_field}")
            
            if placeholder_field:
                marker_found = True
                component_type = component.get("type")
                field_value = component.get(placeholder_field, "")
                
                logger.info(f"[DEBUG] 플레이스홀더 발견! 컴포넌트 {i}: type={component_type}, field={placeholder_field}")
                logger.info(f"[DEBUG] 필드 값: '{field_value}'")
                
                if component_type == "paragraph" and placeholder_field == "content":
                    logger.info(f"[DEBUG] paragraph 컴포넌트 텍스트 분리 처리 시작")
                    
                    # paragraph의 content는 텍스트 분리 후 재구성
                    parts = field_value.split(self.chart_placeholder)
                    before_text = parts[0].strip()
                    after_text = parts[1].strip() if len(parts) > 1 else ""
                    
                    logger.info(f"[DEBUG] 텍스트 분리 결과:")
                    logger.info(f"[DEBUG] - before_text: '{before_text}'")
                    logger.info(f"[DEBUG] - after_text: '{after_text}'")
                    logger.info(f"[DEBUG] - parts 개수: {len(parts)}")
                    
                    # 원래 컴포넌트 제거
                    removed_component = components.pop(i)
                    logger.info(f"[DEBUG] 원본 컴포넌트 {i} 제거: {removed_component}")
                    
                    insert_index = i
                    
                    # 마커 앞 텍스트가 있으면 단락 컴포넌트로 추가
                    if before_text:
                        before_comp = create_paragraph({"content": before_text})
                        components.insert(insert_index, before_comp)
                        logger.info(f"[DEBUG] before_text 컴포넌트 삽입 at {insert_index}: {before_comp}")
                        insert_index += 1
                    
                    # 주가차트 컴포넌트 삽입
                    components.insert(insert_index, price_chart_component)
                    logger.info(f"[DEBUG] 주가차트 컴포넌트 삽입 at {insert_index}")
                    insert_index += 1
                    
                    # 마커 뒤 텍스트가 있으면 단락 컴포넌트로 추가
                    if after_text:
                        after_comp = create_paragraph({"content": after_text})
                        components.insert(insert_index, after_comp)
                        logger.info(f"[DEBUG] after_text 컴포넌트 삽입 at {insert_index}: {after_comp}")
                    
                    logger.info(f"[DEBUG] paragraph 처리 완료. 주가차트 컴포넌트를 {component_type}.{placeholder_field} 마커 위치에 삽입했습니다.")
                
                else:
                    logger.info(f"[DEBUG] 비-paragraph 컴포넌트 전체 교체 처리")
                    original_component = components[i]
                    components[i] = price_chart_component
                    logger.info(f"[DEBUG] 컴포넌트 {i} 교체: {original_component} -> 주가차트")
                    logger.info(f"[DEBUG] 주가차트 컴포넌트를 {component_type}.{placeholder_field} 마커 위치에 삽입했습니다.")
                
                break
        
        # 마커를 찾지 못한 경우 마지막에 추가
        if not marker_found:
            components.append(price_chart_component)
            logger.warning("[DEBUG] 주가차트 플레이스홀더를 찾지 못해 섹션 마지막에 추가했습니다.")
        
        logger.info(f"[DEBUG] _insert_price_chart_at_marker 완료")
        logger.info(f"[DEBUG] 최종 컴포넌트 개수: {len(components)}")
        logger.info(f"[DEBUG] 마커 발견 여부: {marker_found}")
        
        # 최종 컴포넌트 리스트에서 플레이스홀더 잔존 여부 확인
        remaining_placeholders = 0
        for idx, comp in enumerate(components):
            comp_type = comp.get("type", "unknown")
            if comp_type == "paragraph":
                content = comp.get("content", "")
                if self.chart_placeholder in content:
                    remaining_placeholders += 1
                    logger.warning(f"[DEBUG] 처리 후에도 컴포넌트 {idx}에 플레이스홀더 잔존: '{content}'")
            elif comp_type == "image":
                url = comp.get("url", "")
                if self.chart_placeholder in url:
                    remaining_placeholders += 1
                    logger.warning(f"[DEBUG] 처리 후에도 컴포넌트 {idx}에 플레이스홀더 잔존: url='{url}'")
        
        if remaining_placeholders > 0:
            logger.error(f"[DEBUG] 경고: 처리 후에도 {remaining_placeholders}개의 플레이스홀더가 남아있습니다!")
        else:
            logger.info(f"[DEBUG] 확인: 모든 플레이스홀더가 정상적으로 처리되었습니다.")
    
    def _insert_technical_indicator_chart_at_marker(self, components: List[Dict[str, Any]], technical_indicator_chart_component: Dict[str, Any]) -> None:
        """
        컴포넌트 목록에서 기술적 지표 차트 플레이스홀더를 찾아 실제 차트 컴포넌트로 교체합니다.
        """
        logger.info(f"[DEBUG] _insert_technical_indicator_chart_at_marker 시작, 컴포넌트 개수: {len(components)}")
        
        marker_found = False
        for i, component in enumerate(components):
            # 컴포넌트에서 플레이스홀더 포함 필드 찾기
            field = self._find_technical_indicator_placeholder_in_component(component)
            if field:
                marker_found = True
                component_type = component.get("type")
                field_value = component.get(field, "")
                
                logger.info(f"[DEBUG] 기술적 지표 차트 플레이스홀더 발견: 컴포넌트 {i}, 필드 '{field}'")
                
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
                        before_comp = create_paragraph(before_text)
                        components.insert(insert_index, before_comp)
                        insert_index += 1
                    
                    # 기술적 지표 차트 컴포넌트 삽입
                    components.insert(insert_index, technical_indicator_chart_component)
                    insert_index += 1
                    
                    # 마커 뒤 텍스트가 있으면 단락 컴포넌트로 추가
                    if after_text:
                        after_comp = create_paragraph(after_text)
                        components.insert(insert_index, after_comp)
                    
                    logger.info(f"[DEBUG] 기술적 지표 차트 컴포넌트 삽입 완료: 위치 {i}")
                
                else:
                    # 비-paragraph 컴포넌트는 전체 교체
                    components[i] = technical_indicator_chart_component
                    logger.info(f"[DEBUG] 기술적 지표 차트 컴포넌트 교체 완료: 위치 {i}")
                
                break
        
        # 마커를 찾지 못한 경우 마지막에 추가
        if not marker_found:
            components.append(technical_indicator_chart_component)
            logger.warning("[DEBUG] 기술적 지표 차트 플레이스홀더를 찾을 수 없어 컴포넌트 목록 끝에 추가")
    
    def _insert_trend_following_chart_at_marker(self, components: List[Dict[str, Any]], trend_following_chart_component: Dict[str, Any]) -> None:
        """
        컴포넌트 목록에서 추세추종 지표 차트 플레이스홀더를 찾아 실제 차트 컴포넌트로 교체합니다.
        """
        logger.info(f"[DEBUG] _insert_trend_following_chart_at_marker 시작, 컴포넌트 개수: {len(components)}")
        
        marker_found = False
        for i, component in enumerate(components):
            # 컴포넌트에서 플레이스홀더 포함 필드 찾기
            field = self._find_trend_following_placeholder_in_component(component)
            if field:
                marker_found = True
                component_type = component.get("type")
                field_value = component.get(field, "")
                
                logger.info(f"[DEBUG] 추세추종 지표 차트 플레이스홀더 발견: 컴포넌트 {i}, 필드 '{field}'")
                
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
                        before_comp = create_paragraph(before_text)
                        components.insert(insert_index, before_comp)
                        insert_index += 1
                    
                    # 추세추종 지표 차트 컴포넌트 삽입
                    components.insert(insert_index, trend_following_chart_component)
                    insert_index += 1
                    
                    # 마커 뒤 텍스트가 있으면 단락 컴포넌트로 추가
                    if after_text:
                        after_comp = create_paragraph(after_text)
                        components.insert(insert_index, after_comp)
                    
                    logger.info(f"[DEBUG] 추세추종 지표 차트 컴포넌트 삽입 완료: 위치 {i}")
                
                else:
                    # 비-paragraph 컴포넌트는 전체 교체
                    components[i] = trend_following_chart_component
                    logger.info(f"[DEBUG] 추세추종 지표 차트 컴포넌트 교체 완료: 위치 {i}")
                
                break
        
        # 마커를 찾지 못한 경우 마지막에 추가
        if not marker_found:
            components.append(trend_following_chart_component)
            logger.warning("[DEBUG] 추세추종 지표 차트 플레이스홀더를 찾을 수 없어 컴포넌트 목록 끝에 추가")
    
    def _insert_momentum_chart_at_marker(self, components: List[Dict[str, Any]], momentum_chart_component: Dict[str, Any]) -> None:
        """
        컴포넌트 목록에서 모멘텀 지표 차트 플레이스홀더를 찾아 실제 차트 컴포넌트로 교체합니다.
        """
        logger.info(f"[DEBUG] _insert_momentum_chart_at_marker 시작, 컴포넌트 개수: {len(components)}")
        
        marker_found = False
        for i, component in enumerate(components):
            # 컴포넌트에서 플레이스홀더 포함 필드 찾기
            field = self._find_momentum_placeholder_in_component(component)
            if field:
                marker_found = True
                component_type = component.get("type")
                field_value = component.get(field, "")
                
                logger.info(f"[DEBUG] 모멘텀 지표 차트 플레이스홀더 발견: 컴포넌트 {i}, 필드 '{field}'")
                
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
                        before_comp = create_paragraph(before_text)
                        components.insert(insert_index, before_comp)
                        insert_index += 1
                    
                    # 모멘텀 지표 차트 컴포넌트 삽입
                    components.insert(insert_index, momentum_chart_component)
                    insert_index += 1
                    
                    # 마커 뒤 텍스트가 있으면 단락 컴포넌트로 추가
                    if after_text:
                        after_comp = create_paragraph(after_text)
                        components.insert(insert_index, after_comp)
                    
                    logger.info(f"[DEBUG] 모멘텀 지표 차트 컴포넌트 삽입 완료: 위치 {i}")
                
                else:
                    # 비-paragraph 컴포넌트는 전체 교체
                    components[i] = momentum_chart_component
                    logger.info(f"[DEBUG] 모멘텀 지표 차트 컴포넌트 교체 완료: 위치 {i}")
                
                break
        
        # 마커를 찾지 못한 경우 마지막에 추가
        if not marker_found:
            components.append(momentum_chart_component)
            logger.warning("[DEBUG] 모멘텀 지표 차트 플레이스홀더를 찾을 수 없어 컴포넌트 목록 끝에 추가")
    
    def _find_technical_indicator_placeholder_in_component(self, component: Dict[str, Any]) -> str:
        """
        컴포넌트에서 기술적 지표 차트 플레이스홀더가 포함된 필드를 찾아 반환합니다.
        """
        component_type = component.get("type")
        
        # 컴포넌트 타입별로 플레이스홀더 검색 필드 정의
        search_fields = {
            "paragraph": ["content"],
            "image": ["url", "alt", "caption"],
            "heading": ["content"],
            "code_block": ["content"],
            "table": ["title"]
        }
        
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
        search_fields = {
            "paragraph": ["content"],
            "image": ["url", "alt", "caption"],
            "heading": ["content"],
            "code_block": ["content"],
            "table": ["title"]
        }
        
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
        search_fields = {
            "paragraph": ["content"],
            "image": ["url", "alt", "caption"],
            "heading": ["content"],
            "code_block": ["content"],
            "table": ["title"]
        }
        
        fields_to_search = search_fields.get(component_type, [])
        
        for field in fields_to_search:
            field_value = component.get(field, "")
            if isinstance(field_value, str) and self.momentum_chart_placeholder in field_value:
                return field
        
        return None
     
    async def _process_section_async(self, section_data: Dict[str, Any], summary_by_section: Dict[str, str], llm_with_tools: Any, tools: List[Callable], section_content_fallback: str, tech_agent_result: Dict[str, Any] = None, stock_code: str = "", stock_name: str = "") -> tuple[List[Dict[str, Any]], str, str]:
        """
        개별 섹션을 비동기적으로 처리하여 컴포넌트와 포맷된 텍스트를 생성합니다.
        반환값: (생성된 컴포넌트 리스트, 해당 섹션의 LLM 텍스트 응답, 섹션 제목)
        """
        start_time_process_section = datetime.now()
        section_title = section_data.get("title")
        section_components = []
        # 이 섹션 내에서 LLM이 생성한 순수 텍스트 (툴 콜 없이 반환된 내용)
        llm_generated_text_for_section = ""

        if not section_title:
            logger.warning("ResponseFormatterAgent (async): 목차에 제목 없는 섹션 데이터가 있습니다.")
            return [], "", ""

        if section_title in summary_by_section and summary_by_section[section_title]:
            section_content = summary_by_section[section_title]
            
            # 플레이스홀더 처리 - 직접 컴포넌트 생성 방식
            price_chart_component = None
            technical_indicator_chart_component = None
            trend_following_chart_component = None
            momentum_chart_component = None
            
            logger.info(f"[DEBUG] 플레이스홀더 처리 확인 - 섹션: {section_title}")
            logger.info(f"[DEBUG] chart_placeholder in section_content: {self.chart_placeholder in section_content}")
            logger.info(f"[DEBUG] trend_following_chart_placeholder in section_content: {self.trend_following_chart_placeholder in section_content}")
            logger.info(f"[DEBUG] momentum_chart_placeholder in section_content: {self.momentum_chart_placeholder in section_content}")
            logger.info(f"[DEBUG] tech_agent_result 존재: {bool(tech_agent_result)}")
            logger.info(f"[DEBUG] stock_code: {stock_code}")
            logger.info(f"[DEBUG] stock_name: {stock_name}")
            
            if self.chart_placeholder in section_content and tech_agent_result and stock_code and stock_name:
                # 주가차트 컴포넌트를 미리 생성
                price_chart_component = self._create_price_chart_component_directly(tech_agent_result, stock_code, stock_name)
                logger.info(f"[DEBUG] 주가차트 플레이스홀더 발견. 컴포넌트 생성: {section_title}")
                logger.info(f"[DEBUG] price_chart_component 생성됨: {bool(price_chart_component)}")
            else:
                logger.info(f"[DEBUG] 주가차트 컴포넌트 생성 조건 불만족: 섹션 {section_title}")
            
            if self.technical_indicator_chart_placeholder in section_content and tech_agent_result and stock_code and stock_name:
                # 기존 기술적 지표 차트 컴포넌트를 미리 생성 (호환성 유지)
                technical_indicator_chart_component = self._create_trend_following_chart_component_directly(tech_agent_result, stock_code, stock_name)
                logger.info(f"[DEBUG] 기술적 지표 차트 플레이스홀더 발견. 컴포넌트 생성: {section_title}")
                logger.info(f"[DEBUG] technical_indicator_chart_component 생성됨: {bool(technical_indicator_chart_component)}")
            else:
                logger.info(f"[DEBUG] 기술적 지표 차트 컴포넌트 생성 조건 불만족: 섹션 {section_title}")
            
            if self.trend_following_chart_placeholder in section_content and tech_agent_result and stock_code and stock_name:
                # 추세추종 지표 차트 컴포넌트를 미리 생성
                trend_following_chart_component = self._create_trend_following_chart_component_directly(tech_agent_result, stock_code, stock_name)
                logger.info(f"[DEBUG] 추세추종 지표 차트 플레이스홀더 발견. 컴포넌트 생성: {section_title}")
                logger.info(f"[DEBUG] trend_following_chart_component 생성됨: {bool(trend_following_chart_component)}")
            else:
                logger.info(f"[DEBUG] 추세추종 지표 차트 컴포넌트 생성 조건 불만족: 섹션 {section_title}")
            
            if self.momentum_chart_placeholder in section_content and tech_agent_result and stock_code and stock_name:
                # 모멘텀 지표 차트 컴포넌트를 미리 생성
                momentum_chart_component = self._create_momentum_chart_component_directly(tech_agent_result, stock_code, stock_name)
                logger.info(f"[DEBUG] 모멘텀 지표 차트 플레이스홀더 발견. 컴포넌트 생성: {section_title}")
                logger.info(f"[DEBUG] momentum_chart_component 생성됨: {bool(momentum_chart_component)}")
            else:
                logger.info(f"[DEBUG] 모멘텀 지표 차트 컴포넌트 생성 조건 불만족: 섹션 {section_title}")
            
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
- create_line_chart: 연속적인 추세나 시계열 데이터는 선 차트로 표현하세요. 특히 다음과 같은 데이터:
  1. 주가 추이 데이터
  2. 장기간에 걸친 성장률이나 지표 변화
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

**중요**: [CHART_PLACEHOLDER:PRICE_CHART] 문자열이 있다면 이를 그대로 유지하고 변경하지 마세요. 이는 주가차트 위치를 표시하는 플레이스홀더입니다.
"""
            try:
                section_response = await llm_with_tools.ainvoke(input=tool_calling_prompt)
                
                llm_generated_text_for_section = section_response.content if hasattr(section_response, 'content') else ""

                if hasattr(section_response, 'tool_calls') and section_response.tool_calls:
                    first_heading_found = False
                    processed_components = []

                    for tool_call in section_response.tool_calls:
                        tool_name = tool_call["name"]
                        tool_args = tool_call["args"]
                        
                        if 'level' in tool_args and isinstance(tool_args['level'], float):
                            tool_args['level'] = int(tool_args['level'])
                        
                        tool_func = next((t for t in tools if t.name == tool_name), None)
                        #logger.info(f"Tool name : {tool_name}, args : {tool_args}, tool_func: {tool_func}")
                        if tool_func:
                            component_dict = tool_func.invoke(tool_args)

                            if component_dict.get("type") == "heading":
                                first_heading_found = True
                                heading_content_candidate = component_dict.get("content", "").strip()
                                # 볼드체(bold)로 시작하거나 불릿 포인트(*, •, -)로 시작하는 텍스트는 heading이 아닌 paragraph나 list로 처리
                                if (heading_content_candidate.startswith('**') or 
                                    heading_content_candidate.startswith('*') or
                                    heading_content_candidate.startswith('•') or
                                    heading_content_candidate.startswith('-')):
                                    logger.info(f"Heading candidate '{heading_content_candidate}' starts with bold or bullet. Converting to appropriate component.")
                                    
                                    # 불릿 포인트로 시작하면 list 컴포넌트로 변환
                                    if (heading_content_candidate.startswith('*') and not heading_content_candidate.startswith('**')) or heading_content_candidate.startswith('•') or heading_content_candidate.startswith('-'):
                                        list_tool_func = next((t for t in tools if t.name == "create_list"), None)
                                        if list_tool_func:
                                            # 불릿 포인트 제거하고 내용 추출
                                            content = re.sub(r'^[\*\•\-]\s*', '', heading_content_candidate)
                                            component_dict = list_tool_func.invoke({"ordered": False, "items": [content]})
                                        else:
                                            logger.warning("create_list tool not found. Falling back to paragraph.")
                                            paragraph_tool_func = next((t for t in tools if t.name == "create_paragraph"), None)
                                            if paragraph_tool_func:
                                                component_dict = paragraph_tool_func.invoke({"content": heading_content_candidate})
                                            else:
                                                component_dict = ParagraphComponent({"content":heading_content_candidate}).dict()
                                    else:
                                        # 볼드체로 시작하는 경우 paragraph로 변환
                                        paragraph_tool_func = next((t for t in tools if t.name == "create_paragraph"), None)
                                        if paragraph_tool_func:
                                            component_dict = paragraph_tool_func.invoke({"content": heading_content_candidate})
                                        else:
                                            component_dict = ParagraphComponent({"content":heading_content_candidate}).dict()
                                else:
                                    level_3_match = re.match(r"^(\d+)\.(\d+)\.?\s*(.*)", heading_content_candidate)
                                    level_2_match = re.match(r"^(\d+)\.?\s*(.*)", heading_content_candidate)
                                    if level_3_match: component_dict["level"] = 3
                                    elif level_2_match: component_dict["level"] = 2
                                    else: component_dict["level"] = 4

                                    if heading_content_candidate.startswith('# '):
                                        heading_content_candidate = heading_content_candidate[2:]
                                    elif heading_content_candidate.startswith('## '):
                                        heading_content_candidate = heading_content_candidate[3:]
                                    elif heading_content_candidate.startswith('### '):
                                        heading_content_candidate = heading_content_candidate[4:]

                            processed_components.append(component_dict)
                    
                    # 첫 번째 컴포넌트가 없거나 헤딩이 아니거나 내용이 섹션 제목과 다른 경우 강제로 헤딩 추가
                    if (not processed_components or 
                        processed_components[0].get("type") != "heading" or
                        processed_components[0].get("content", "").strip() != section_title.strip()):
                        
                        logger.info(f"섹션 '{section_title}'에 대한 첫 번째 컴포넌트가 헤딩이 아니거나 섹션 제목과 일치하지 않습니다. 강제로 헤딩 추가")
                        heading_component = create_heading({"level": 2, "content": section_title})
                        section_components.append(heading_component)
                    
                    # 처리된 컴포넌트들 추가
                    section_components.extend(processed_components)
                    
                    # 주가차트 컴포넌트가 있으면 마커를 찾아서 교체
                    logger.info(f"[DEBUG] 주가차트 교체 실행 전 - price_chart_component: {bool(price_chart_component)}")
                    if price_chart_component:
                        logger.info(f"[DEBUG] 주가차트 플레이스홀더 교체 시작 - 섹션: {section_title}")
                        self._insert_price_chart_at_marker(section_components, price_chart_component)
                        logger.info(f"[DEBUG] 주가차트 플레이스홀더 교체 완료 - 섹션: {section_title}")
                    else:
                        logger.warning(f"[DEBUG] 주가차트 컴포넌트가 없어 교체하지 않음 - 섹션: {section_title}")
                    
                    # 기술적 지표 차트 플레이스홀더 처리 (호환성 유지)
                    logger.info(f"[DEBUG] 기술적 지표 차트 교체 실행 전 - technical_indicator_chart_component: {bool(technical_indicator_chart_component)}")
                    if technical_indicator_chart_component:
                        logger.info(f"[DEBUG] 기술적 지표 차트 플레이스홀더 교체 시작 - 섹션: {section_title}")
                        self._insert_technical_indicator_chart_at_marker(section_components, technical_indicator_chart_component)
                        logger.info(f"[DEBUG] 기술적 지표 차트 플레이스홀더 교체 완료 - 섹션: {section_title}")
                    else:
                        logger.warning(f"[DEBUG] 기술적 지표 차트 컴포넌트가 없어 교체하지 않음 - 섹션: {section_title}")
                    
                    # 추세추종 지표 차트 플레이스홀더 처리
                    logger.info(f"[DEBUG] 추세추종 지표 차트 교체 실행 전 - trend_following_chart_component: {bool(trend_following_chart_component)}")
                    if trend_following_chart_component:
                        logger.info(f"[DEBUG] 추세추종 지표 차트 플레이스홀더 교체 시작 - 섹션: {section_title}")
                        self._insert_trend_following_chart_at_marker(section_components, trend_following_chart_component)
                        logger.info(f"[DEBUG] 추세추종 지표 차트 플레이스홀더 교체 완료 - 섹션: {section_title}")
                    else:
                        logger.warning(f"[DEBUG] 추세추종 지표 차트 컴포넌트가 없어 교체하지 않음 - 섹션: {section_title}")
                    
                    # 모멘텀 지표 차트 플레이스홀더 처리
                    logger.info(f"[DEBUG] 모멘텀 지표 차트 교체 실행 전 - momentum_chart_component: {bool(momentum_chart_component)}")
                    if momentum_chart_component:
                        logger.info(f"[DEBUG] 모멘텀 지표 차트 플레이스홀더 교체 시작 - 섹션: {section_title}")
                        self._insert_momentum_chart_at_marker(section_components, momentum_chart_component)
                        logger.info(f"[DEBUG] 모멘텀 지표 차트 플레이스홀더 교체 완료 - 섹션: {section_title}")
                    else:
                        logger.warning(f"[DEBUG] 모멘텀 지표 차트 컴포넌트가 없어 교체하지 않음 - 섹션: {section_title}")
                
                elif llm_generated_text_for_section.strip(): # 툴 콜 없이 텍스트만 반환된 경우
                    logger.info(f"ResponseFormatterAgent (async): 섹션 '{section_title}'에 대해 Tool calling 없이 일반 텍스트 응답을 받았습니다.")
                    # 섹션 제목 강제 추가
                    section_components.append(create_heading({"level": 2, "content": section_title}))
                    
                    cleaned_text = remove_json_block(llm_generated_text_for_section)
                    if cleaned_text.strip():
                         section_components.append(create_paragraph({"content": cleaned_text}))
                
                # 성공적으로 처리되면 (툴콜이 있든 없든) 컴포넌트들과 LLM 텍스트, 제목 반환
                logger.info(f"섹션 '{section_title}' 처리 완료: 소요시간 {datetime.now() - start_time_process_section}")
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
            return [create_heading({"level": 2, "content": section_title}), create_paragraph({"content": "내용 준비 중입니다."})], "", section_title

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
            final_report_toc = state.get("final_report_toc") # 동적 목차 정보 가져오기
            
            # 플레이스홀더 처리를 위해 agent_results에서 technical_analyzer 결과 가져오기
            agent_results = state.get("agent_results", {})
            tech_agent_result = agent_results.get("technical_analyzer", {})
            
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
                create_mixed_chart,
                create_image
            ]
            
            llm_with_tools = self.agent_llm_for_tools.get_llm().bind_tools(tools)

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
                
                # 면책조항 내용을 summary_by_section에서 가져오기 (LLM 요청 없이)
                disclaimer_content = summary_by_section.get("면책조항", "")
                # fallback으로 기본 면책조항 사용
                if not disclaimer_content.strip():
                    logger.info("ResponseFormatterAgent: summary_by_section에 면책조항이 없어 기본 면책조항을 사용합니다.")
                    disclaimer_content = """본 보고서는 투자 참고 자료로만 활용하시기 바라며, 특정 종목의 매수 또는 매도를 권유하지 않습니다. 보고서의 내용이 사실과 다른 내용이 일부 존재할 수 있으니 참고해 주시기 바랍니다. 투자 결정은 투자자 본인의 책임하에 이루어져야 하며, 본 보고서에 기반한 투자로 인한 손실에 대해 작성자와 당사는 어떠한 법적 책임도 지지 않습니다. 모든 투자에는 위험이 수반되므로 투자 전 투자자 본인의 판단과 책임하에 충분한 검토가 필요합니다."""
                
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
                        section_content_fallback_for_task,
                        tech_agent_result,
                        stock_code,
                        stock_name
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
                
                # 면책조항 컴포넌트 추가 (고정된 내용)
                all_components.append(create_heading({"level": 3, "content": "면책조항"}))
                all_components.append(create_paragraph({"content": disclaimer_content}))
                formatted_response_parts.append(f"**면책조항**\n\n{disclaimer_content}\n\n")
           
            # 최종 formatted_response 조합
            formatted_response = "".join(formatted_response_parts).strip()
            
            # 플레이스홀더 제거 (컴포넌트에서는 이미 대체되었지만 텍스트에서는 남아있을 수 있음)
            formatted_response = formatted_response.replace(self.chart_placeholder, "")
            
            # 컴포넌트가 제목 외에 없는 경우 (모든 섹션 내용이 없거나 파싱 실패)
            if len(all_components) <= 1: # 보고서 전체 제목 컴포넌트만 있는 경우
                logger.warning("ResponseFormatterAgent: 동적 목차 기반 컴포넌트 생성 결과가 거의 비어있습니다. 기존 요약(summary)으로 대체 처리를 시도합니다.")
                if summary: 
                    state["formatted_response"] = summary.replace(self.chart_placeholder, "")
                    all_components_fallback = await self.make_full_components(state)
                    all_components = [comp.dict() for comp in all_components_fallback if hasattr(comp, 'dict')]
                    formatted_response = summary.replace(self.chart_placeholder, "")
                else: 
                    logger.warning("ResponseFormatterAgent: 대체할 summary 내용도 없습니다.")
                    # 이미 title 컴포넌트는 추가되어 있을 수 있음
                    if not any(comp.get("type") == "paragraph" for comp in all_components): # 내용이 전혀 없는 경우
                         all_components.append(create_paragraph({"content": "보고서 내용을 생성하지 못했습니다."}))
                    if not formatted_response: # 텍스트 응답도 비어있다면
                         formatted_response = "보고서 내용을 생성하지 못했습니다."

            # 결과 저장 (플레이스홀더 제거된 텍스트 사용)
            state["formatted_response"] = formatted_response
            state["answer"] = formatted_response
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
                                    for idx, header in enumerate(header_cells):
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
                                if '날짜' in header_lower or '분기' in header_lower or '연도' in header_lower or '년' in header_lower or 'q' in header_lower:
                                    period_col_idx = idx
                                # 항목/매출처/회사 열 감지
                                elif '항목' in header_lower or '매출처' in header_lower or '회사' in header_lower or '거래처' in header_lower:
                                    item_col_idx = idx
                                # 수치 데이터 열 감지
                                elif ('액' in header_lower or '이익' in header_lower or '매출' in header_lower or 
                                      '값' in header_lower or '수치' in header_lower or '비중' in header_lower):
                                    metric_col_idx = idx
                            
                            # 증감률 열 감지 (QoQ, YoY 등)
                            growth_rate_col_idx = -1
                            for idx, header in enumerate(header_cells):
                                header_lower = header.lower()
                                if ('증감률' in header_lower or 'yoy' in header_lower or 'qoq' in header_lower or 
                                    '성장률' in header_lower or '전년비' in header_lower or '전분기비' in header_lower or
                                    '%' in header_lower):
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
                                            bar_datasets.append({
                                                "label": metric_label,
                                                "data": [period_values.get(period, 0) for period in periods]
                                            })
                                        
                                        # 선 차트 데이터셋 구성
                                        for growth_label, period_values in growth_values.items():
                                            line_datasets.append({
                                                "label": growth_label,
                                                "data": [period_values.get(period, 0) for period in periods]
                                            })
                                        
                                        # Y축 제목 설정
                                        y_axis_left_title = None
                                        y_axis_right_title = None
                                        
                                        if "매출액" in header_cells[metric_col_idx]:
                                            y_axis_left_title = "매출액 (억원)"
                                        elif "이익" in header_cells[metric_col_idx]:
                                            y_axis_left_title = "이익 (억원)"
                                            
                                        if "증감률" in header_cells[growth_rate_col_idx] or "yoy" in header_cells[growth_rate_col_idx].lower() or "qoq" in header_cells[growth_rate_col_idx].lower():
                                            y_axis_right_title = "증감률 (%)"
                                        
                                        # 혼합 차트 컴포넌트 생성
                                        title = table_title if table_title else f"{header_cells[metric_col_idx]} 및 {header_cells[growth_rate_col_idx]} 추이"
                                        
                                        components.append(MixedChartComponent(
                                            title=title,
                                            data=MixedChartData(
                                                labels=periods,
                                                bar_datasets=bar_datasets,
                                                line_datasets=line_datasets,
                                                y_axis_left_title=y_axis_left_title,
                                                y_axis_right_title=y_axis_right_title
                                            )
                                        ))
                                        chart_created = True
                                except Exception as mixed_chart_error:
                                    logger.error(f"혼합 차트 변환 오류: {mixed_chart_error}")
                            
                            # 차트가 생성되지 않은 경우에만 테이블 컴포넌트 생성
                            if not chart_created:
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
        "#FFC107"   # 노란색
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
        "yoy": 0,     # YoY는 기본 색상
        "전년": 0,
        "qoq": 1,     # QoQ는 기본 색상에서 1번 오프셋
        "전분기": 1,
        "mom": 2,     # MoM은 기본 색상에서 2번 오프셋
        "전월": 2
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
            pattern1_match = re.search(r'^(.*?)\s*\(\s*(yoy|qoq|mom|전년|전분기|전월)\s*\)', label_lower, re.IGNORECASE)
            
            # 패턴 2: "항목명 증감률유형" - 예: "매출액 YoY", "영업이익 QoQ"
            pattern2_match = re.search(r'^(.*?)\s+(yoy|qoq|mom|전년|전분기|전월)$', label_lower, re.IGNORECASE)
            
            if pattern1_match:
                item_name = pattern1_match.group(1).strip()
                rate_type = pattern1_match.group(2).lower()
                #logger.info(f"패턴1 매칭: '{label}' -> 항목: '{item_name}', 증감률: '{rate_type}'")
            elif pattern2_match:
                item_name = pattern2_match.group(1).strip()
                rate_type = pattern2_match.group(2).lower()
                #logger.info(f"패턴2 매칭: '{label}' -> 항목: '{item_name}', 증감률: '{rate_type}'")
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
                        
                        #logger.info(f"기타 패턴 매칭: '{label}' -> 항목: '{item_name}', 증감률: '{rate_type}'")
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
                        
                    #logger.info(f"라인 데이터셋 '{label}': 항목 '{item_name}', 증감률 '{rate_type}'에 색상 {assigned_color} 할당")
            
            # 항목별 할당 실패 시 일반 로직으로 색상 할당
            if not assigned_color:
                # 키워드 기반으로 증감률 유형만 식별된 경우
                if rate_type:
                    for offset_key, offset_value in rate_type_variations.items():
                        if offset_key == rate_type:
                            # 해당 증감률 유형에 맞는 색상 선택
                            color_index = (i + offset_value) % len(color_palette)
                            assigned_color = color_palette[color_index]
                            #logger.info(f"라인 데이터셋 '{label}': 증감률 '{rate_type}'에 색상 {assigned_color} 할당")
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
                    
                    #logger.info(f"라인 데이터셋 '{label}': 자동 색상 {assigned_color} 할당")
            
            # 색상 할당 및 사용된 색상 추적
            dataset["borderColor"] = assigned_color
            used_colors.add(assigned_color)
        else:
            used_colors.add(dataset["borderColor"])
            #logger.info(f"라인 데이터셋 '{dataset.get('label')}': 기존 색상 {dataset['borderColor']} 유지")
        
        # 선 굵기 설정
        if "borderWidth" not in dataset:
            dataset["borderWidth"] = 2
        
        # 곡선 부드러움 설정
        if "tension" not in dataset:
            dataset["tension"] = 0.1
    
    return LineChartComponent(
        title=title,
        data=LineChartData(labels=labels, datasets=datasets)
    ).dict()

@tool
def create_mixed_chart(title: str, labels: List[str], bar_datasets: List[Dict[str, Any]], line_datasets: List[Dict[str, Any]], y_axis_left_title: Optional[str] = None, y_axis_right_title: Optional[str] = None) -> Dict:
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
            if (line_label in unique_line_labels or 
                line_label in ["YoY (%)", "QoQ (%)", "증감률 (%)", "%", "증감률"]):
                
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
            elif "영업이익" in label_lower :
                dataset["backgroundColor"] = "#FC847E"  # 영업이익 핑크빛빨간색
            elif "순이익" in label_lower  :
                dataset["backgroundColor"] = "#92E492"  # 영업이익 녹색계열
            else:
                # 기본 색상 순환 (데이터셋이 1개인 경우 랜덤 시작점 사용)
                color_idx = (random_start + i) % len(bar_color_palette)
                dataset["backgroundColor"] = bar_color_palette[color_idx]
    
    # 선 차트 데이터셋에 색상 할당
    # 기본 색상 팔레트 확장 (중복 방지를 위해 다양한 색상 추가)
    line_color_palette = [
        "#FF5630", "#FFAB00", "#6554C0", "#00B8D9", "#8993A4", 
        "#36B37E", "#998DD9", "#E95D0F", "#0747A6", "#5243AA",
        "#00875A", "#D13438", "#0052CC", "#42526E", "#E37933"
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
        "yoy": 0,     # YoY는 기본 색상
        "전년": 0,
        "qoq": 1,     # QoQ는 기본 색상에서 1번 오프셋
        "전분기": 1,
        "mom": 2,     # MoM은 기본 색상에서 2번 오프셋
        "전월": 2
    }
    
    # 주요 항목 키워드 (우선 매칭할 키워드)
    major_items = ["매출액", "매출", "영업이익", "순이익", "당기순이익", "자산", "부채", "자본"]
    
    for i, dataset in enumerate(line_datasets):
        #if "borderColor" not in dataset:
        label = dataset.get("label", "")
        label_lower = label.lower()
        
        # 라벨에서 항목명과 증감률 유형 추출 시도
        item_name = None
        rate_type = None
        
        # 패턴 1: "항목명(증감률유형)" - 예: "매출액(YoY)", "영업이익(QoQ)"
        pattern1_match = re.search(r'^(.*?)\s*\(\s*(yoy|qoq|mom|전년|전분기|전월)\s*\)', label_lower, re.IGNORECASE)
        
        # 패턴 2: "항목명 증감률유형" - 예: "매출액 YoY", "영업이익 QoQ"
        pattern2_match = re.search(r'^(.*?)\s+(yoy|qoq|mom|전년|전분기|전월)$', label_lower, re.IGNORECASE)
        
        if pattern1_match:
            item_name = pattern1_match.group(1).strip()
            rate_type = pattern1_match.group(2).lower()
            #logger.info(f"패턴1 매칭: '{label}' -> 항목: '{item_name}', 증감률: '{rate_type}'")
        elif pattern2_match:
            item_name = pattern2_match.group(1).strip()
            rate_type = pattern2_match.group(2).lower()
            #logger.info(f"패턴2 매칭: '{label}' -> 항목: '{item_name}', 증감률: '{rate_type}'")
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
                    
                    logger.info(f"기타 패턴 매칭: '{label}' -> 항목: '{item_name}', 증감률: '{rate_type}'")
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
                    
                #logger.info(f"라인 데이터셋 '{label}': 항목 '{item_name}', 증감률 '{rate_type}'에 색상 {assigned_color} 할당")
        
        # 항목별 할당 실패 시 일반 로직으로 색상 할당
        if not assigned_color:
            # 키워드 기반으로 증감률 유형만 식별된 경우
            if rate_type:
                for offset_key, offset_value in rate_type_variations.items():
                    if offset_key == rate_type:
                        # 해당 증감률 유형에 맞는 색상 선택 (데이터셋이 1개인 경우 랜덤 시작점 사용)
                        color_index = (random_start + i + offset_value) % len(line_color_palette)
                        assigned_color = line_color_palette[color_index]
                        #logger.info(f"라인 데이터셋 '{label}': 증감률 '{rate_type}'에 색상 {assigned_color} 할당")
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
                
                #logger.info(f"라인 데이터셋 '{label}': 자동 색상 {assigned_color} 할당")
        
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
        data=MixedChartData(
            labels=labels,
            bar_datasets=bar_datasets,
            line_datasets=line_datasets,
            y_axis_left_title=y_axis_left_title,
            y_axis_right_title=y_axis_right_title
        )
    ).dict()

@tool
def create_code_block(language: Optional[str], content: str) -> Dict:
    """코드 블록 컴포넌트를 생성합니다. language는 언어(선택), content는 코드 내용입니다."""
    return CodeBlockComponent(language=language, content=content).dict()

@tool
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
    metadata: Optional[Dict[str, Any]] = None
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
            metadata=metadata
        )
    ).dict()

@tool
def create_technical_indicator_chart(
    symbol: str,
    name: str,
    dates: List[str],
    indicators: List[Dict[str, Any]],
    title: Optional[str] = None,
    candle_data: Optional[List[Dict[str, Any]]] = None,
    y_axis_configs: Optional[Dict[str, Dict[str, Any]]] = None,
    period: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None
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
    for i, indicator in enumerate(indicators[:5]):  # 최대 5개만 허용
        processed_indicators.append(TechnicalIndicatorData(
            name=indicator.get('name', f'지표{i+1}'),
            data=indicator.get('data', []),
            color=indicator.get('color'),
            chart_type=indicator.get('chart_type', 'line'),
            y_axis_id=indicator.get('y_axis_id', 'primary'),
            line_style=indicator.get('line_style', 'solid')
        ))
    
    return TechnicalIndicatorChartComponent(
        title=title,
        data=TechnicalIndicatorChartData(
            symbol=symbol,
            name=name,
            dates=dates,
            candle_data=candle_data,
            indicators=processed_indicators,
            y_axis_configs=y_axis_configs,
            period=period,
            metadata=metadata
        )
    ).dict()


@tool
def create_image(url: str, alt: str, caption: Optional[str] = None) -> Dict:
    """이미지 컴포넌트를 생성합니다. url은 이미지 주소, alt는 대체 텍스트, caption은 캡션(선택)입니다."""
    return ImageComponent(url=url, alt=alt, caption=caption).dict()

