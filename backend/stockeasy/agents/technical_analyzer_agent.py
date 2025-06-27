"""
기술적 분석 에이전트 모듈

이 모듈은 stock-data-collector API를 통해 주가 데이터를 수집하고,
기술적 지표, 차트 패턴, 매매 신호 등을 분석하는 TechnicalAnalyzerAgent 클래스를 구현합니다.
"""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import aiohttp
import numpy as np
import pandas as pd
from loguru import logger

from common.models.token_usage import ProjectType
from common.services.agent_llm import get_agent_llm
from common.utils.util import format_date_for_chart, safe_float, safe_float_or_none, safe_int, safe_price_float
from stockeasy.agents.base import BaseAgent
from stockeasy.models.agent_io import AgentState, ChartPatternAnalysis, MarketSentiment, TechnicalAnalysisResult, TechnicalIndicators, TradingSignals

from .response_formatter_agent import create_momentum_chart_component_directly, create_price_chart_component_directly, create_trend_following_chart_component_directly


class TechnicalAnalyzerAgent(BaseAgent):
    """
    기술적 분석 에이전트

    이 에이전트는 stock-data-collector API를 통해 주가 데이터를 수집하고,
    다음과 같은 기술적 분석을 수행합니다:
    1. 기술적 지표 계산 (RSI, MACD, 볼린저 밴드 등)
    2. 차트 패턴 분석 (지지선, 저항선, 추세 등)
    3. 매매 신호 생성
    4. 시장 정서 분석
    """

    def __init__(self, name: Optional[str] = None, db: Optional[Any] = None):
        """
        기술적 분석 에이전트 초기화

        Args:
            name: 에이전트 이름 (지정하지 않으면 클래스명 사용)
            db: 데이터베이스 세션 객체 (선택적)
        """
        super().__init__(name, db)
        self.agent_llm = get_agent_llm("technical_analyzer_agent")

        # stock-data-collector API 설정
        self.api_base_url = "http://stock-data-collector:8001"
        self.session: Optional[aiohttp.ClientSession] = None

        logger.info(f"TechnicalAnalyzerAgent initialized with provider: {self.agent_llm.get_provider()}, model: {self.agent_llm.get_model_name()}")

    async def __aenter__(self):
        """비동기 컨텍스트 매니저 진입"""
        self.session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30))
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """비동기 컨텍스트 매니저 종료"""
        if self.session:
            await self.session.close()

    async def process(self, state: AgentState) -> AgentState:
        """
        기술적 분석을 수행하여 상태를 업데이트합니다.

        Args:
            state: 현재 상태 정보를 포함하는 딕셔너리

        Returns:
            업데이트된 상태 딕셔너리
        """
        try:
            # 성능 측정 시작
            start_time = datetime.now()
            logger.info("TechnicalAnalyzerAgent 기술적 분석 시작")

            # 필요한 정보 추출
            stock_code = state.get("stock_code", "")
            stock_name = state.get("stock_name", "")
            query = state.get("query", "")

            if not stock_code:
                logger.warning("종목코드가 없어 기술적 분석을 수행할 수 없습니다.")
                self._add_error(state, "종목코드가 필요합니다.")
                return state

            # 사용자 컨텍스트 추출
            user_context = state.get("user_context", {})
            user_id = user_context.get("user_id", None)

            logger.info(f"종목 {stock_name}({stock_code})에 대한 기술적 분석 수행")

            # 기술적 분석 수행
            async with self:
                technical_analysis_result = await self._perform_technical_analysis(stock_code, stock_name, query, user_id)

            # 차트 컴포넌트 생성 및 스트리밍 전송
            preliminary_components = await self._create_preliminary_chart_components(technical_analysis_result, stock_code, stock_name)

            # preliminary_chart_callback으로 즉시 전송
            send_preliminary_chart = state.get("send_preliminary_chart")
            logger.info(
                f"preliminary_chart 전송 시작: send_preliminary_chart={send_preliminary_chart is not None}, preliminary_components={len(preliminary_components) if preliminary_components else 0}개"
            )

            if send_preliminary_chart and preliminary_components:
                try:
                    message = f"📊 {stock_name}의 기술적 분석 차트가 준비되었습니다. 추가 분석을 진행하는 동안 차트를 먼저 확인해보세요."
                    elapsed_time = (datetime.now() - start_time).total_seconds()

                    # 종목 기본 정보도 함께 전송 (이미 수집한 데이터 재사용)
                    stock_info = technical_analysis_result.get("stock_info", {})
                    # preliminary_chart_callback 호출 (event: preliminary_chart 형태로 전송)
                    success = await send_preliminary_chart(preliminary_components, message, elapsed_time, stock_info)

                    if success:
                        logger.info(f"preliminary_chart 이벤트 전송 완료: {stock_name}({stock_code})")
                    else:
                        logger.warning(f"preliminary_chart 이벤트 전송 실패: {stock_name}({stock_code})")

                except Exception as stream_error:
                    logger.error(f"preliminary_chart 이벤트 전송 중 오류: {str(stream_error)}", exc_info=True)
                    # 전송 실패해도 계속 진행
            else:
                if not send_preliminary_chart:
                    logger.warning("send_preliminary_chart 콜백 함수가 None입니다.")
                if not preliminary_components:
                    logger.warning("preliminary_components가 비어있습니다.")

            # 결과를 상태에 저장
            state["agent_results"] = state.get("agent_results", {})
            state["agent_results"]["technical_analyzer"] = {
                "agent_name": "technical_analyzer",
                "status": "success",
                "data": technical_analysis_result,
                "error": None,
                "execution_time": (datetime.now() - start_time).total_seconds(),
                "preliminary_sent": bool(send_preliminary_chart and preliminary_components),
                "metadata": {"stock_code": stock_code, "stock_name": stock_name, "analysis_date": datetime.now()},
            }

            # retrieved_data에도 저장
            state["retrieved_data"] = state.get("retrieved_data", {})
            state["retrieved_data"]["technical_analysis_data"] = technical_analysis_result

            # 성능 지표 업데이트
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()

            # 메트릭 기록
            state["metrics"] = state.get("metrics", {})
            state["metrics"]["technical_analyzer"] = {
                "start_time": start_time,
                "end_time": end_time,
                "duration": duration,
                "status": "completed",
                "error": None,
                "model_name": self.agent_llm.get_model_name(),
            }

            # 처리 상태 업데이트
            state["processing_status"] = state.get("processing_status", {})
            state["processing_status"]["technical_analyzer"] = "completed"

            logger.info(f"TechnicalAnalyzerAgent 완료: {duration:.2f}초 소요")
            return state

        except Exception as e:
            logger.exception(f"TechnicalAnalyzerAgent 오류: {str(e)}")
            self._add_error(state, f"기술적 분석 에이전트 오류: {str(e)}")
            return state

    async def _perform_technical_analysis(self, stock_code: str, stock_name: str, query: str, user_id: Optional[str]) -> TechnicalAnalysisResult:
        """
        실제 기술적 분석을 수행합니다.

        Args:
            stock_code: 종목코드
            stock_name: 종목명
            query: 사용자 질문
            user_id: 사용자 ID

        Returns:
            기술적 분석 결과
        """
        logger.info(f"종목 {stock_code}에 대한 기술적 분석 수행 중...")

        # 1. 종목 기본 정보 수집
        logger.info("종목 기본 정보 수집 중...")
        stock_info = await self._fetch_stock_info(stock_code)

        # 2. 주가 데이터 수집 (ATR 등 순차적 지표의 정확성을 위해 2년치 데이터 수집)
        logger.info("주가/수급 데이터 수집 중...")
        chart_data = await self._fetch_chart_data(stock_code, period="2y", interval="1d")
        if not chart_data:
            raise Exception("주가 데이터를 가져올 수 없습니다.")

        # 3. 수급 데이터 수집
        supply_demand_data = await self._fetch_supply_demand_data(stock_code)

        # 4. RS(상대강도) 데이터 수집
        logger.info("RS(상대강도) 데이터 수집 중...")
        rs_data = await self._fetch_rs_data(stock_code, stock_info)

        # 5. 시장지수 데이터 수집
        market_indices = await self._fetch_market_indices()

        # 6. 데이터를 DataFrame으로 변환
        df = self._convert_to_dataframe(chart_data)

        # 거래량 분석을 위해 현재 DataFrame 저장
        self._current_df = df

        # 7. 기술적 지표 계산
        logger.info("기술적 지표 계산 중...")
        technical_indicators = self._calculate_technical_indicators(df)

        # 7-1. 차트용 지표 시계열 데이터 생성
        logger.info("차트용 지표 시계열 데이터 생성 중...")
        chart_indicators_data = self._generate_chart_indicators_data(df)

        # 8. 차트 패턴 분석
        logger.info("차트 패턴 분석 중...")
        chart_patterns = self._analyze_chart_patterns(df)

        # 9. 매매 신호 생성
        logger.info("매매 신호 생성 중...")
        trading_signals = self._generate_trading_signals(df, technical_indicators)

        # 10. 시장 정서 분석
        logger.info("시장 정서 분석 중...")
        market_sentiment = self._analyze_market_sentiment(df, supply_demand_data)

        # 11. LLM을 사용한 종합 분석
        logger.info("LLM을 사용한 종합 분석 중...")
        # summary = await self._generate_analysis_summary(
        #     stock_name, technical_indicators, chart_patterns,
        #     trading_signals, market_sentiment, rs_data, stock_info, query, user_id
        # )
        summary = "임시 메시지"

        # 12. 투자 권고사항 생성
        # logger.info("투자 권고사항 생성 중...")
        # recommendations = await self._generate_recommendations(
        #     stock_name, technical_indicators, trading_signals, rs_data, user_id
        # )

        # 결과 구성 (numpy 타입을 Python 타입으로 안전하게 변환)
        current_price = float(df["close"].iloc[-1]) if not df.empty else 0.0

        return {
            "stock_code": stock_code,
            "stock_name": stock_name,
            "analysis_date": datetime.now(),
            "current_price": float(current_price),
            "stock_info": stock_info,
            "chart_patterns": chart_patterns,
            "chart_data": chart_data,
            "chart_indicators_data": chart_indicators_data,
            "supply_demand_data": supply_demand_data,
            "rs_data": rs_data,
            "market_indices": market_indices,
            "technical_indicators": technical_indicators,
            "trading_signals": trading_signals,
            "market_sentiment": market_sentiment,
            "summary": summary,
            # "recommendations": recommendations
        }

    def _add_error(self, state: AgentState, error_message: str) -> None:
        """
        상태 객체에 오류 정보를 추가합니다.

        Args:
            state: 상태 객체
            error_message: 오류 메시지
        """
        state["errors"] = state.get("errors", [])
        state["errors"].append(
            {
                "agent": "technical_analyzer",
                "error": error_message,
                "type": "processing_error",
                "timestamp": datetime.now(),
                "context": {"stock_code": state.get("stock_code", ""), "query": state.get("query", "")},
            }
        )

        # 처리 상태 업데이트
        state["processing_status"] = state.get("processing_status", {})
        state["processing_status"]["technical_analyzer"] = "failed"

    # ========================================
    # 데이터 수집 메서드들 (Phase 2.2)
    # ========================================

    async def _fetch_stock_info(self, stock_code: str) -> Optional[Dict[str, Any]]:
        """
        stock-data-collector API에서 종목 기본 정보를 가져옵니다.

        Args:
            stock_code: 종목코드

        Returns:
            파싱된 종목 기본 정보 또는 None (실패 시)
        """
        try:
            url = f"{self.api_base_url}/api/v1/stock/info/{stock_code}"

            logger.info(f"종목 기본 정보 요청: {url}")

            async with self.session.get(url) as response:
                if response.status == 200:
                    response_data = await response.json()

                    # 응답 구조 확인
                    if not isinstance(response_data, dict):
                        logger.error("잘못된 종목 기본 정보 응답 구조")
                        return None

                    stock_info = response_data.get("data", {})
                    if not stock_info:
                        logger.warning("종목 기본 정보가 비어있습니다.")
                        return None

                    logger.info("종목 기본 정보 수신 성공")
                    logger.info(f"종목명: {stock_info.get('name')}, 시장: {stock_info.get('market')}, 업종: {stock_info.get('sector')}")

                    return stock_info
                else:
                    logger.warning(f"종목 기본 정보 요청 실패: HTTP {response.status}")
                    return None

        except Exception as e:
            logger.warning(f"종목 기본 정보 수집 중 오류: {str(e)}")
            return None

    async def _fetch_chart_data(self, stock_code: str, period: str = "1y", interval: str = "1d") -> Optional[List[Dict[str, Any]]]:
        """
        stock-data-collector API에서 주가 차트 데이터를 가져옵니다.

        Args:
            stock_code: 종목코드
            period: 조회 기간 (1d, 1w, 1m, 3m, 6m, 1y, 2y, 5y)
            interval: 간격 (1m, 5m, 15m, 30m, 1h, 1d, 1w, 1M)

        Returns:
            파싱된 차트 데이터 리스트 또는 None (실패 시)
        """
        try:
            url = f"{self.api_base_url}/api/v1/stock/chart/{stock_code}"
            params = {"period": period, "interval": interval, "compressed": "true"}

            logger.info(f"주가 데이터 요청: {url}, 파라미터: {params}")

            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    response_data = await response.json()

                    # 응답 구조 확인
                    if not isinstance(response_data, dict) or "data" not in response_data:
                        logger.error("잘못된 응답 구조: data 필드가 없습니다.")
                        return None

                    inner_data = response_data["data"]

                    # 스키마 필드 순서 확인
                    schema = inner_data.get("schema", {})
                    fields = schema.get("fields", [])

                    if not fields:
                        logger.error("스키마 필드 정보가 없습니다.")
                        return None

                    # 실제 데이터 배열 가져오기
                    data_rows = inner_data.get("data", [])

                    if not data_rows:
                        logger.warning("주가 데이터가 비어있습니다.")
                        return []

                    logger.info(f"주가 데이터 수신 성공: {len(data_rows)}개 레코드")
                    logger.info(f"스키마 필드: {fields}")

                    # 데이터 파싱
                    chart_data = []
                    for row in data_rows:
                        if len(row) < len(fields):
                            logger.warning(f"불완전한 데이터 행: {row}")
                            continue

                        # 필드명과 값을 매핑하여 딕셔너리 생성
                        row_dict = {}
                        for i, field in enumerate(fields):
                            value = row[i]

                            # timestamp를 date로 변환
                            if field == "timestamp":
                                row_dict["date"] = value
                            else:
                                row_dict[field] = value

                        chart_data.append(row_dict)

                    # 최신 5개 데이터 샘플 로깅
                    if chart_data:
                        recent_data = chart_data[-5:] if len(chart_data) >= 5 else chart_data
                        logger.info(f"최신 {len(recent_data)}개 주가 데이터 샘플:")
                        for i, item in enumerate(recent_data, 1):
                            date_val = item.get("date")
                            close_val = item.get("close")
                            logger.info(f"  {i}. {date_val}: 종가 {close_val}")

                    return chart_data
                else:
                    logger.error(f"주가 데이터 요청 실패: HTTP {response.status}")
                    return None

        except Exception as e:
            logger.error(f"주가 데이터 수집 중 오류: {str(e)}")
            return None

    async def _fetch_supply_demand_data(self, stock_code: str, days_back: int = 30) -> Optional[List[Dict[str, Any]]]:
        """
        stock-data-collector API에서 수급 데이터를 가져옵니다.

        Args:
            stock_code: 종목코드
            days_back: 조회할 일수 (기본 30일)

        Returns:
            파싱된 수급 데이터 리스트 또는 None (실패 시)
        """
        try:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days_back)

            url = f"{self.api_base_url}/api/v1/stock/supply-demand/{stock_code}"
            params = {"start_date": start_date.strftime("%Y%m%d"), "end_date": end_date.strftime("%Y%m%d"), "compressed": "true"}

            logger.info(f"수급 데이터 요청: {url}, 파라미터: {params}")

            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    response_data = await response.json()

                    # 응답 구조 확인
                    if not isinstance(response_data, dict) or "data" not in response_data:
                        logger.error("잘못된 응답 구조: data 필드가 없습니다.")
                        return None

                    inner_data = response_data["data"]

                    # 스키마 필드 순서 확인
                    schema = inner_data.get("schema", {})
                    fields = schema.get("fields", [])

                    if not fields:
                        logger.error("스키마 필드 정보가 없습니다.")
                        return None

                    # 실제 데이터 배열 가져오기
                    data_rows = inner_data.get("data", [])

                    if not data_rows:
                        logger.warning("수급 데이터가 비어있습니다.")
                        return []

                    logger.info(f"수급 데이터 수신 성공: {len(data_rows)}개 레코드")
                    logger.info(f"스키마 필드: {fields}")

                    # 데이터 파싱
                    supply_data = []
                    for row in data_rows:
                        if len(row) < len(fields):
                            logger.warning(f"불완전한 데이터 행: {row}")
                            continue

                        # 필드명과 값을 매핑하여 딕셔너리 생성
                        row_dict = {}
                        for i, field in enumerate(fields):
                            value = row[i]

                            # null 값 처리
                            if value is None:
                                row_dict[field] = None
                            else:
                                row_dict[field] = value

                        supply_data.append(row_dict)

                    # 최신 5개 데이터 샘플 로깅
                    if supply_data:
                        recent_data = supply_data[-5:] if len(supply_data) >= 5 else supply_data
                        logger.info(f"최신 {len(recent_data)}개 수급 데이터 샘플:")
                        for i, item in enumerate(recent_data, 1):
                            date_val = item.get("date")
                            individual = item.get("individual_investor")
                            foreign = item.get("foreign_investor")
                            institution = item.get("institution_total")
                            logger.info(f"  {i}. {date_val}: 개인 {individual}, 외국인 {foreign}, 기관 {institution}")

                    return supply_data
                else:
                    logger.warning(f"수급 데이터 요청 실패: HTTP {response.status}")
                    return None

        except Exception as e:
            logger.warning(f"수급 데이터 수집 중 오류: {str(e)}")
            return None

    async def _fetch_rs_data(self, stock_code: str, stock_info: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """
        stock-data-collector API에서 RS(상대강도) 데이터를 가져옵니다.
        현재 종목 + KOSPI + KOSDAQ을 함께 조회하여 시장 대비 비교 분석이 가능합니다.

        Args:
            stock_code: 종목코드

        Returns:
            파싱된 RS 데이터 (종목 + 시장 지수 포함) 또는 None (실패 시)
        """
        try:
            # 종목의 market_code에 맞는 시장지수만 가져오기
            market_code = stock_info.get("market") if stock_info else None
            codes_to_fetch = [stock_code]

            if market_code in ["KOSPI", "KOSDAQ"]:
                codes_to_fetch.append(market_code)
            else:
                # 시장 정보가 없거나 기타인 경우 KOSPI를 기본으로
                codes_to_fetch.append("KOSPI")
                market_code = "KOSPI"

            codes_param = ",".join(codes_to_fetch)

            url = f"{self.api_base_url}/api/v1/rs/multiple"
            params = {"codes": codes_param, "compressed": "false", "gzip_enabled": "false"}

            logger.info(f"여러 종목 RS 데이터 요청: {url}, 종목들: {codes_to_fetch}")

            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    response_data = await response.json()

                    # 응답 구조 확인
                    if not isinstance(response_data, dict) or "data" not in response_data:
                        logger.error("잘못된 RS 응답 구조")
                        return None

                    data_list = response_data.get("data", [])
                    successful_count = response_data.get("successful_count", 0)
                    failed_codes = response_data.get("failed_codes", [])

                    logger.info(f"RS 데이터 조회 결과: {successful_count}개 성공, 실패: {failed_codes}")

                    # 종목별로 데이터 분류
                    target_stock_data = None
                    market_data = None

                    for rs_data in data_list:
                        code = rs_data.get("stock_code")
                        if code == stock_code:
                            target_stock_data = rs_data
                        elif code == market_code:
                            market_data = rs_data

                    # 메인 종목 데이터가 없으면 실패로 처리
                    if target_stock_data is None:
                        logger.warning(f"종목 {stock_code}의 RS 데이터가 없습니다")
                        return None

                    logger.info(f"종목 {stock_code} RS 데이터 수신 성공")
                    logger.info(f"RS 값: {target_stock_data.get('rs')}, RS_1M: {target_stock_data.get('rs_1m')}, 업종: {target_stock_data.get('sector')}")

                    # 시장 지수 정보 로깅
                    if market_data:
                        logger.info(f"{market_code} RS: {market_data.get('rs')}")

                    # 시장 비교 정보 구성
                    market_comparison = {
                        "market_code": market_code,
                        "market_rs": market_data.get("rs") if market_data else None,
                        "market_rs_1m": market_data.get("rs_1m") if market_data else None,
                        "market_rs_3m": market_data.get("rs_3m") if market_data else None,
                        "market_rs_6m": market_data.get("rs_6m") if market_data else None,
                    }

                    # 종합 RS 데이터 구성
                    rs_summary = {
                        # 메인 종목 정보
                        "stock_code": target_stock_data.get("stock_code"),
                        "stock_name": target_stock_data.get("stock_name"),
                        "sector": target_stock_data.get("sector"),
                        "rs": target_stock_data.get("rs"),
                        "rs_1m": target_stock_data.get("rs_1m"),
                        "rs_3m": target_stock_data.get("rs_3m"),
                        "rs_6m": target_stock_data.get("rs_6m"),
                        "mmt": target_stock_data.get("mmt"),
                        "updated_at": target_stock_data.get("updated_at"),
                        # 시장 지수 비교 정보 (시장별 맞춤)
                        "market_comparison": market_comparison,
                        # 상대적 강도 분석
                        "relative_strength_analysis": self._analyze_relative_strength(target_stock_data, market_data, market_code, stock_info),
                    }

                    return rs_summary

                elif response.status == 404:
                    logger.warning("RS 데이터를 찾을 수 없습니다")
                    return None
                else:
                    logger.error(f"RS 데이터 요청 실패: HTTP {response.status}")
                    return None

        except Exception as e:
            logger.error(f"RS 데이터 수집 중 오류: {str(e)}")
            return None

    def _analyze_relative_strength(self, target_stock: Dict, market_data: Optional[Dict], market_code: str, stock_info: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        종목의 RS를 해당 시장 지수와 비교하여 상대적 강도를 분석합니다.

        Args:
            target_stock: 분석 대상 종목의 RS 데이터
            market_data: 시장 지수 RS 데이터 (KOSPI 또는 KOSDAQ)
            market_code: 시장 코드 (KOSPI 또는 KOSDAQ)
            stock_info: 종목 기본 정보 (시장, 업종 등)

        Returns:
            상대적 강도 분석 결과
        """
        try:
            analysis = {"vs_market": None, "market_code": market_code, "relative_trend": None, "market_specific_analysis": None}

            target_rs = target_stock.get("rs")
            target_rs_1m = target_stock.get("rs_1m")
            target_rs_3m = target_stock.get("rs_3m")
            target_rs_6m = target_stock.get("rs_6m")

            if target_rs is None or market_data is None:
                return analysis

            # 해당 시장 대비 분석
            market_rs = market_data.get("rs")
            market_rs_1m = market_data.get("rs_1m")
            market_rs_3m = market_data.get("rs_3m")
            market_rs_6m = market_data.get("rs_6m")

            analysis["vs_market"] = {
                "market_name": market_code,
                "difference": round(target_rs - market_rs, 2),
                "outperforming": target_rs > market_rs,
                "strength_level": self._get_relative_strength_level(target_rs - market_rs),
            }

            # 다기간 트렌드 비교
            trends = {}
            if target_rs_1m is not None and market_rs_1m is not None:
                current_gap = target_rs - market_rs
                prev_gap_1m = target_rs_1m - market_rs_1m
                trends["1m"] = "improving" if current_gap > prev_gap_1m else "weakening"

            if target_rs_3m is not None and market_rs_3m is not None:
                current_gap = target_rs - market_rs
                prev_gap_3m = target_rs_3m - market_rs_3m
                trends["3m"] = "improving" if current_gap > prev_gap_3m else "weakening"

            if target_rs_6m is not None and market_rs_6m is not None:
                current_gap = target_rs - market_rs
                prev_gap_6m = target_rs_6m - market_rs_6m
                trends["6m"] = "improving" if current_gap > prev_gap_6m else "weakening"

            if trends:
                analysis["vs_market"]["trends"] = trends
                # 전반적인 트렌드 평가
                improving_count = sum(1 for trend in trends.values() if trend == "improving")
                analysis["vs_market"]["overall_trend"] = "improving" if improving_count > len(trends) / 2 else "weakening"

            # 전반적인 상대적 트렌드 (다기간 분석)
            trend_analysis = {}

            if target_rs_1m is not None:
                rs_change_1m = target_rs - target_rs_1m
                trend_analysis["1m"] = {
                    "direction": "strengthening" if rs_change_1m > 0 else "weakening",
                    "change": round(rs_change_1m, 2),
                    "momentum": self._get_momentum_level(abs(rs_change_1m)),
                }

            if target_rs_3m is not None:
                rs_change_3m = target_rs - target_rs_3m
                trend_analysis["3m"] = {
                    "direction": "strengthening" if rs_change_3m > 0 else "weakening",
                    "change": round(rs_change_3m, 2),
                    "momentum": self._get_momentum_level(abs(rs_change_3m)),
                }

            if target_rs_6m is not None:
                rs_change_6m = target_rs - target_rs_6m
                trend_analysis["6m"] = {
                    "direction": "strengthening" if rs_change_6m > 0 else "weakening",
                    "change": round(rs_change_6m, 2),
                    "momentum": self._get_momentum_level(abs(rs_change_6m)),
                }

            if trend_analysis:
                analysis["relative_trend"] = trend_analysis

                # 전반적인 트렌드 방향 평가
                strengthening_count = sum(1 for period_data in trend_analysis.values() if period_data["direction"] == "strengthening")
                total_periods = len(trend_analysis)

                analysis["overall_trend_direction"] = {
                    "direction": "strengthening" if strengthening_count > total_periods / 2 else "weakening",
                    "consistency": "consistent" if strengthening_count in [0, total_periods] else "mixed",
                    "periods_analyzed": list(trend_analysis.keys()),
                }

            # 시장별 특화 분석
            market_analysis = self._get_market_specific_analysis(market_code, target_rs, market_rs)
            analysis["market_specific_analysis"] = market_analysis

            return analysis

        except Exception as e:
            logger.error(f"상대적 강도 분석 중 오류: {e}")
            return {"vs_kospi": None, "vs_kosdaq": None, "market_leadership": None, "relative_trend": None}

    def _get_relative_strength_level(self, difference: float) -> str:
        """RS 차이값에 따른 강도 레벨 반환"""
        if difference >= 20:
            return "매우 강함"
        elif difference >= 10:
            return "강함"
        elif difference >= 0:
            return "보통"
        elif difference >= -10:
            return "약함"
        else:
            return "매우 약함"

    def _get_momentum_level(self, change: float) -> str:
        """RS 변화량에 따른 모멘텀 레벨 반환"""
        if change >= 10:
            return "강한 모멘텀"
        elif change >= 5:
            return "중간 모멘텀"
        elif change >= 2:
            return "약한 모멘텀"
        else:
            return "모멘텀 없음"

    def _get_market_specific_analysis(self, market_code: str, target_rs: float, market_rs: float) -> Dict[str, Any]:
        """
        종목이 속한 시장에 따른 특화 분석을 제공합니다.

        Args:
            market_code: 시장 코드 (KOSPI, KOSDAQ 등)
            target_rs: 종목의 RS 값
            market_rs: 시장 지수의 RS 값

        Returns:
            시장별 특화 분석 결과
        """
        try:
            diff = target_rs - market_rs

            if diff >= 20:
                market_position = f"{market_code} 내 강력한 우위"
                recommendation = f"동종 시장({market_code}) 내에서 매우 우수한 성과를 보이고 있어 긍정적입니다."
            elif diff >= 0:
                market_position = f"{market_code} 내 우위"
                recommendation = f"{market_code} 시장 평균보다 양호한 성과를 보이고 있습니다."
            elif diff >= -10:
                market_position = f"{market_code} 내 평균 수준"
                recommendation = f"{market_code} 시장 평균과 비슷한 수준입니다."
            else:
                market_position = f"{market_code} 내 하위"
                recommendation = f"{market_code} 시장 평균 대비 부진한 모습이므로 주의가 필요합니다."

            return {"target_market": market_code, "market_position": market_position, "recommendation": recommendation, "difference": round(diff, 2)}

        except Exception as e:
            logger.error(f"시장별 특화 분석 중 오류: {e}")
            return {"target_market": market_code, "market_position": "분석 불가", "recommendation": "시장별 분석에 오류가 발생했습니다.", "difference": None}

    async def _fetch_market_indices(self) -> Optional[Dict[str, Any]]:
        """
        stock-data-collector API에서 시장지수 데이터를 가져옵니다.

        Returns:
            시장지수 데이터 또는 None (실패 시)
        """
        try:
            url = f"{self.api_base_url}/api/v1/market/indices"

            logger.info(f"시장지수 데이터 요청: {url}")

            async with self.session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    logger.info("시장지수 데이터 수신 성공")
                    return data.get("indices", {})
                else:
                    logger.warning(f"시장지수 데이터 요청 실패: HTTP {response.status}")
                    return None

        except Exception as e:
            logger.warning(f"시장지수 데이터 수집 중 오류: {str(e)}")
            return None

    # ========================================
    # 데이터 변환 및 분석 메서드들 (Phase 2.3)
    # ========================================

    def _convert_to_dataframe(self, chart_data: List[Dict[str, Any]]) -> pd.DataFrame:
        """
        차트 데이터를 pandas DataFrame으로 변환합니다.

        Args:
            chart_data: 차트 데이터 리스트

        Returns:
            변환된 DataFrame
        """
        try:
            if not chart_data:
                return pd.DataFrame()

            # 공통 유틸리티 함수 사용 (중복 제거)

            # 데이터 변환
            df_data = []
            for item in chart_data:
                try:
                    df_data.append(
                        {
                            "date": pd.to_datetime(item.get("date")),
                            "open": safe_float(item.get("open")),
                            "high": safe_float(item.get("high")),
                            "low": safe_float(item.get("low")),
                            "close": safe_float(item.get("close")),
                            "volume": safe_int(item.get("volume")),
                        }
                    )
                except Exception as e:
                    logger.warning(f"데이터 변환 중 개별 항목 오류: {item}, 오류: {str(e)}")
                    continue

            df = pd.DataFrame(df_data)

            # DataFrame이 비어있는지 확인
            if df.empty:
                logger.warning("변환된 DataFrame이 비어있습니다.")
                return pd.DataFrame()

            # 필수 컬럼 검증
            required_columns = ["date", "open", "high", "low", "close", "volume"]
            missing_columns = [col for col in required_columns if col not in df.columns]
            if missing_columns:
                logger.error(f"필수 컬럼이 누락됨: {missing_columns}")
                return pd.DataFrame()

            # 인덱스 설정 및 정렬
            df.set_index("date", inplace=True)
            df.sort_index(inplace=True)

            # 유효한 데이터 검증
            if len(df) == 0:
                logger.warning("유효한 데이터가 없습니다.")
                return pd.DataFrame()

            logger.info(f"DataFrame 변환 완료: {len(df)}개 레코드")
            return df

        except Exception as e:
            logger.error(f"DataFrame 변환 중 오류: {str(e)}")
            return pd.DataFrame()

    def _calculate_technical_indicators(self, df: pd.DataFrame) -> TechnicalIndicators:
        """
        기술적 지표를 계산합니다.

        Args:
            df: 주가 DataFrame

        Returns:
            기술적 지표 결과
        """
        try:
            if df.empty:
                return {}

            close = df["close"]
            high = df["high"]
            low = df["low"]
            df["volume"]

            # 이동평균선 계산
            sma_20 = close.rolling(window=20).mean().iloc[-1] if len(close) >= 20 else None
            sma_60 = close.rolling(window=60).mean().iloc[-1] if len(close) >= 60 else None

            # 지수이동평균 계산
            ema_12 = close.ewm(span=12).mean().iloc[-1] if len(close) >= 12 else None
            ema_26 = close.ewm(span=26).mean().iloc[-1] if len(close) >= 26 else None

            # RSI 계산
            rsi = self._calculate_rsi(close) if len(close) >= 14 else None

            # # MACD 계산
            macd_values = self._calculate_macd(close) if len(close) >= 26 else {}

            # 볼린저 밴드 계산
            bollinger = self._calculate_bollinger_bands(close) if len(close) >= 20 else {}

            # 스토캐스틱 계산
            stochastic = self._calculate_stochastic(high, low, close) if len(close) >= 14 else {}

            # 추세추종 지표들 계산
            # ADX 계산
            adx_values = self._calculate_adx(high, low, close) if len(close) >= 14 else {}

            # ADR 계산 (Average Daily Range)
            adr_values = self._calculate_adr(high, low) if len(close) >= 20 else {}

            # 슈퍼트렌드 계산
            supertrend_values = self._calculate_supertrend(high, low, close) if len(close) >= 14 else {}

            # 공통 유틸리티 함수 사용

            indicators = {
                "sma_20": safe_float_or_none(sma_20),
                "sma_60": safe_float_or_none(sma_60),
                "ema_12": safe_float_or_none(ema_12),
                "ema_26": safe_float_or_none(ema_26),
                "rsi": safe_float_or_none(rsi),
                "macd": macd_values.get("macd"),
                "macd_signal": macd_values.get("signal"),
                "macd_histogram": macd_values.get("histogram"),
                "bollinger_upper": bollinger.get("upper"),
                "bollinger_middle": bollinger.get("middle"),
                "bollinger_lower": bollinger.get("lower"),
                "stochastic_k": stochastic.get("k"),
                "stochastic_d": stochastic.get("d"),
                # 추세추종 지표들
                "adx": adx_values.get("adx"),
                "adx_plus_di": adx_values.get("plus_di"),
                "adx_minus_di": adx_values.get("minus_di"),
                "adr": adr_values.get("adr"),
                "adr_ma": adr_values.get("adr_ma"),
                "supertrend": supertrend_values.get("supertrend"),
                "supertrend_direction": supertrend_values.get("direction"),
            }

            logger.info("기술적 지표 계산 완료")
            return indicators

        except Exception as e:
            logger.error(f"기술적 지표 계산 중 오류: {str(e)}")
            return {}

    def _calculate_rsi(self, close: pd.Series, period: int = 14) -> Optional[float]:
        """RSI 지표를 계산합니다 (Wilder's Smoothing 적용)."""
        try:
            delta = close.diff()
            gain = delta.where(delta > 0, 0)
            loss = -delta.where(delta < 0, 0)

            # Wilder's Smoothing 적용
            gain_smooth = self._wilders_smoothing(gain, period)
            loss_smooth = self._wilders_smoothing(loss, period)

            rs = gain_smooth / loss_smooth
            rsi = 100 - (100 / (1 + rs))
            return rsi.iloc[-1]
        except:
            return None

    def _calculate_macd(self, close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> Dict[str, Optional[float]]:
        """MACD 지표를 계산합니다."""
        try:
            ema_fast = close.ewm(span=fast).mean()
            ema_slow = close.ewm(span=slow).mean()
            macd = ema_fast - ema_slow
            macd_signal = macd.ewm(span=signal).mean()
            macd_histogram = macd - macd_signal

            return {"macd": safe_float_or_none(macd.iloc[-1]), "signal": safe_float_or_none(macd_signal.iloc[-1]), "histogram": safe_float_or_none(macd_histogram.iloc[-1])}
        except:
            return {"macd": None, "signal": None, "histogram": None}

    def _calculate_bollinger_bands(self, close: pd.Series, period: int = 20, std_dev: int = 2) -> Dict[str, Optional[float]]:
        """볼린저 밴드를 계산합니다."""
        try:
            sma = close.rolling(window=period).mean()
            std = close.rolling(window=period).std()

            upper = sma + (std * std_dev)
            lower = sma - (std * std_dev)

            return {"upper": safe_float_or_none(upper.iloc[-1]), "middle": safe_float_or_none(sma.iloc[-1]), "lower": safe_float_or_none(lower.iloc[-1])}
        except:
            return {"upper": None, "middle": None, "lower": None}

    def _calculate_stochastic(self, high: pd.Series, low: pd.Series, close: pd.Series, k_period: int = 14, d_period: int = 3) -> Dict[str, Optional[float]]:
        """스토캐스틱 지표를 계산합니다."""
        try:
            lowest_low = low.rolling(window=k_period).min()
            highest_high = high.rolling(window=k_period).max()

            k_percent = 100 * ((close - lowest_low) / (highest_high - lowest_low))
            d_percent = k_percent.rolling(window=d_period).mean()

            return {"k": safe_float_or_none(k_percent.iloc[-1]), "d": safe_float_or_none(d_percent.iloc[-1])}
        except:
            return {"k": None, "d": None}

    def _calculate_adx(self, high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> Dict[str, Optional[float]]:
        """ADX 지표를 계산합니다."""
        try:
            # ADX 시계열 데이터 계산
            adx_series = self._calculate_adx_series(high, low, close, period)

            return {
                "adx": safe_float_or_none(adx_series["adx"].iloc[-1]),
                "plus_di": safe_float_or_none(adx_series["plus_di"].iloc[-1]),
                "minus_di": safe_float_or_none(adx_series["minus_di"].iloc[-1]),
            }
        except:
            return {"adx": None, "plus_di": None, "minus_di": None}

    def _calculate_adr(self, high: pd.Series, low: pd.Series, period: int = 20) -> Dict[str, Optional[float]]:
        """ADR 지표를 계산합니다."""
        try:
            # ADR 시계열 데이터 계산
            adr_series = self._calculate_adr_series(high, low, period)

            return {"adr": safe_float_or_none(adr_series["adr"].iloc[-1]), "adr_ma": safe_float_or_none(adr_series["adr_ma"].iloc[-1])}
        except:
            return {"adr": None, "adr_ma": None}

    def _calculate_supertrend(self, high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14, multiplier: float = 3.0) -> Dict[str, Optional[float]]:
        """슈퍼트렌드 지표를 계산합니다."""
        try:
            # 슈퍼트렌드 시계열 데이터 계산
            supertrend_series = self._calculate_supertrend_series(high, low, close, period, multiplier)

            return {"supertrend": safe_float_or_none(supertrend_series["supertrend"].iloc[-1]), "direction": safe_float_or_none(supertrend_series["direction"].iloc[-1])}
        except:
            return {"supertrend": None, "direction": None}

    def _calculate_atr(self, high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
        """ATR 지표를 계산합니다 (Wilder's Smoothing 적용)."""
        try:
            true_range1 = high - low
            true_range2 = abs(high - close.shift(1))
            true_range3 = abs(low - close.shift(1))
            true_range = pd.concat([true_range1, true_range2, true_range3], axis=1).max(axis=1)

            # Wilder's Smoothing 적용 (단순이동평균 대신)
            atr = self._wilders_smoothing(true_range, period)
            return atr
        except:
            return pd.Series()

    def _generate_chart_indicators_data(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        차트에 그릴 지표들의 1년 시계열 데이터를 생성합니다.

        Args:
            df: 주가 DataFrame (2년치 데이터)

        Returns:
            차트용 지표 시계열 데이터 (1년치 표시)
        """
        try:
            if df.empty:
                return {}

            # 전체 2년 데이터로 지표 계산 후 최근 1년만 추출 (일관성 및 정확성 확보)
            # 슈퍼트렌드, ATR, ADX 등 순차 계산 지표는 전체 기간으로 계산해야 정확함
            close = df["close"]
            high = df["high"]
            low = df["low"]
            volume = df["volume"]

            # 차트 표시용 기간 설정 (최근 1년, 약 250일)
            chart_length = 250
            chart_start_idx = max(0, len(df) - chart_length)

            # 날짜 인덱스를 문자열로 변환 (차트 표시 구간만)
            # JSON 직렬화 시 ISO 형식 변환을 방지하기 위해 명시적으로 문자열 처리
            dates = []
            for date in df.index[chart_start_idx:]:
                if hasattr(date, "strftime"):
                    dates.append(date.strftime("%Y-%m-%d"))
                elif isinstance(date, str):
                    # 이미 문자열인 경우 ISO 형식을 YYYY-MM-DD로 변환
                    if "T" in date:
                        dates.append(date.split("T")[0])
                    else:
                        dates.append(date)
                else:
                    dates.append(str(date))

            # 안전한 변환 함수 (차트 표시 구간만 추출)
            def safe_chart_series_to_list(series):
                """pandas Series를 안전하게 리스트로 변환 (차트 구간만)"""
                if series is None or series.empty:
                    return []
                chart_series = series.iloc[chart_start_idx:]
                return [safe_float_or_none(x) for x in chart_series]

            chart_data = {
                "dates": dates,
                "open": safe_chart_series_to_list(df["open"]),  # open 데이터 추가
                "close": safe_chart_series_to_list(close),
                "high": safe_chart_series_to_list(high),
                "low": safe_chart_series_to_list(low),
                "volume": safe_chart_series_to_list(volume),
            }

            # 이동평균선
            if len(close) >= 20:
                sma_20 = close.rolling(window=20).mean()
                chart_data["sma_20"] = safe_chart_series_to_list(sma_20)

            if len(close) >= 60:
                sma_60 = close.rolling(window=60).mean()
                chart_data["sma_60"] = safe_chart_series_to_list(sma_60)

            # 지수이동평균
            if len(close) >= 12:
                ema_12 = close.ewm(span=12).mean()
                chart_data["ema_12"] = safe_chart_series_to_list(ema_12)

            if len(close) >= 26:
                ema_26 = close.ewm(span=26).mean()
                chart_data["ema_26"] = safe_chart_series_to_list(ema_26)

            # RSI
            if len(close) >= 14:
                rsi_series = self._calculate_rsi_series(close)
                chart_data["rsi"] = safe_chart_series_to_list(rsi_series)

            # MACD
            if len(close) >= 26:
                macd_series = self._calculate_macd_series(close)
                chart_data["macd"] = safe_chart_series_to_list(macd_series["macd"])
                chart_data["macd_signal"] = safe_chart_series_to_list(macd_series["signal"])
                chart_data["macd_histogram"] = safe_chart_series_to_list(macd_series["histogram"])

            # 볼린저 밴드
            if len(close) >= 20:
                bollinger_series = self._calculate_bollinger_bands_series(close)
                chart_data["bollinger_upper"] = safe_chart_series_to_list(bollinger_series["upper"])
                chart_data["bollinger_middle"] = safe_chart_series_to_list(bollinger_series["middle"])
                chart_data["bollinger_lower"] = safe_chart_series_to_list(bollinger_series["lower"])

            # ADX
            if len(close) >= 14:
                adx_series = self._calculate_adx_series(high, low, close)
                chart_data["adx"] = safe_chart_series_to_list(adx_series["adx"])
                chart_data["adx_plus_di"] = safe_chart_series_to_list(adx_series["plus_di"])
                chart_data["adx_minus_di"] = safe_chart_series_to_list(adx_series["minus_di"])

            # ADR (Average Daily Range)
            if len(close) >= 20:
                adr_series = self._calculate_adr_series(high, low)
                chart_data["adr"] = safe_chart_series_to_list(adr_series["adr"])
                chart_data["adr_ma"] = safe_chart_series_to_list(adr_series["adr_ma"])

            # 슈퍼트렌드 (14일 기본값 사용)
            if len(close) >= 14:
                supertrend_series = self._calculate_supertrend_series(high, low, close)
                chart_data["supertrend"] = safe_chart_series_to_list(supertrend_series["supertrend"])
                chart_data["supertrend_direction"] = safe_chart_series_to_list(supertrend_series["direction"])

            logger.info(f"차트용 지표 데이터 생성 완료: 전체 {len(df)}일 중 최근 {len(dates)}일 표시")
            return chart_data

        except Exception as e:
            logger.error(f"차트용 지표 데이터 생성 중 오류: {str(e)}")
            return {}

    def _calculate_rsi_series(self, close: pd.Series, period: int = 14) -> pd.Series:
        """RSI 시계열 데이터를 계산합니다 (Wilder's Smoothing 적용)."""
        try:
            delta = close.diff()
            gain = delta.where(delta > 0, 0)
            loss = -delta.where(delta < 0, 0)

            # Wilder's Smoothing 적용
            gain_smooth = self._wilders_smoothing(gain, period)
            loss_smooth = self._wilders_smoothing(loss, period)

            rs = gain_smooth / loss_smooth
            rsi = 100 - (100 / (1 + rs))
            return rsi
        except:
            return pd.Series()

    def _calculate_macd_series(self, close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> Dict[str, pd.Series]:
        """MACD 시계열 데이터를 계산합니다."""
        try:
            ema_fast = close.ewm(span=fast).mean()
            ema_slow = close.ewm(span=slow).mean()
            macd = ema_fast - ema_slow
            macd_signal = macd.ewm(span=signal).mean()
            macd_histogram = macd - macd_signal

            return {"macd": macd, "signal": macd_signal, "histogram": macd_histogram}
        except:
            return {"macd": pd.Series(), "signal": pd.Series(), "histogram": pd.Series()}

    def _calculate_bollinger_bands_series(self, close: pd.Series, period: int = 20, std_dev: int = 2) -> Dict[str, pd.Series]:
        """볼린저 밴드 시계열 데이터를 계산합니다."""
        try:
            sma = close.rolling(window=period).mean()
            std = close.rolling(window=period).std()

            upper = sma + (std * std_dev)
            lower = sma - (std * std_dev)

            return {"upper": upper, "middle": sma, "lower": lower}
        except:
            return {"upper": pd.Series(), "middle": pd.Series(), "lower": pd.Series()}

    def _calculate_adx_series(self, high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> Dict[str, pd.Series]:
        """ADX 시계열 데이터를 계산합니다 (Wilder's Smoothing 적용)."""
        try:
            # True Range 계산
            tr1 = high - low
            tr2 = abs(high - close.shift(1))
            tr3 = abs(low - close.shift(1))
            true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

            # +DM, -DM 계산
            dm_plus = high - high.shift(1)
            dm_minus = low.shift(1) - low

            dm_plus = dm_plus.where((dm_plus > dm_minus) & (dm_plus > 0), 0)
            dm_minus = dm_minus.where((dm_minus > dm_plus) & (dm_minus > 0), 0)

            # Wilder's Smoothing 적용 (단순이동평균 대신)
            atr = self._wilders_smoothing(true_range, period)
            dm_plus_smooth = self._wilders_smoothing(dm_plus, period)
            dm_minus_smooth = self._wilders_smoothing(dm_minus, period)

            # +DI, -DI 계산
            di_plus = (dm_plus_smooth / atr) * 100
            di_minus = (dm_minus_smooth / atr) * 100

            # DX 계산
            dx = abs(di_plus - di_minus) / (di_plus + di_minus) * 100

            # ADX 계산 (DX에 Wilder's Smoothing 적용)
            adx = self._wilders_smoothing(dx, period)

            return {"adx": adx, "plus_di": di_plus, "minus_di": di_minus}
        except:
            return {"adx": pd.Series(), "plus_di": pd.Series(), "minus_di": pd.Series()}

    def _wilders_smoothing(self, series: pd.Series, period: int) -> pd.Series:
        """Welles Wilder의 스무딩을 적용합니다."""
        alpha = 1.0 / period
        return series.ewm(alpha=alpha, adjust=False).mean()

    def _calculate_adr_series(self, high: pd.Series, low: pd.Series, period: int = 20) -> Dict[str, pd.Series]:
        """ADR 시계열 데이터를 계산합니다 (Average Daily Range - 일중 평균 변동폭)."""
        try:
            # 일일 변동폭 계산 (High - Low)
            daily_range = high - low

            # ADR 계산 (일일 변동폭의 이동평균)
            adr = daily_range.rolling(window=period).mean()

            # ADR의 이동평균 (추가적인 스무딩)
            adr_ma = adr.rolling(window=period).mean()

            return {"adr": adr, "adr_ma": adr_ma}
        except:
            return {"adr": pd.Series(), "adr_ma": pd.Series()}

    def _calculate_supertrend_series(self, high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14, multiplier: float = 3.0) -> Dict[str, pd.Series]:
        """슈퍼트렌드 시계열 데이터를 계산합니다 (표준 알고리즘)."""
        try:
            # ATR 계산
            atr = self._calculate_atr(high, low, close, period)

            # HL2 (High + Low) / 2
            hl2 = (high + low) / 2

            # Basic Upper/Lower Band 계산
            basic_upper_band = hl2 + (multiplier * atr)
            basic_lower_band = hl2 - (multiplier * atr)

            # Final Upper/Lower Band 초기화
            final_upper_band = pd.Series(index=close.index, dtype=float)
            final_lower_band = pd.Series(index=close.index, dtype=float)
            supertrend = pd.Series(index=close.index, dtype=float)
            direction = pd.Series(index=close.index, dtype=int)

            # 첫 번째 값 설정
            final_upper_band.iloc[0] = basic_upper_band.iloc[0]
            final_lower_band.iloc[0] = basic_lower_band.iloc[0]
            supertrend.iloc[0] = final_upper_band.iloc[0]
            direction.iloc[0] = 1

            # 슈퍼트렌드 계산 (표준 알고리즘)
            for i in range(1, len(close)):
                # Final Upper Band 계산
                if basic_upper_band.iloc[i] < final_upper_band.iloc[i - 1] or close.iloc[i - 1] > final_upper_band.iloc[i - 1]:
                    final_upper_band.iloc[i] = basic_upper_band.iloc[i]
                else:
                    final_upper_band.iloc[i] = final_upper_band.iloc[i - 1]

                # Final Lower Band 계산
                if basic_lower_band.iloc[i] > final_lower_band.iloc[i - 1] or close.iloc[i - 1] < final_lower_band.iloc[i - 1]:
                    final_lower_band.iloc[i] = basic_lower_band.iloc[i]
                else:
                    final_lower_band.iloc[i] = final_lower_band.iloc[i - 1]

                # 슈퍼트렌드 결정
                if supertrend.iloc[i - 1] == final_upper_band.iloc[i - 1] and close.iloc[i] <= final_upper_band.iloc[i]:
                    supertrend.iloc[i] = final_upper_band.iloc[i]
                    direction.iloc[i] = -1  # 하락 추세
                elif supertrend.iloc[i - 1] == final_upper_band.iloc[i - 1] and close.iloc[i] > final_upper_band.iloc[i]:
                    supertrend.iloc[i] = final_lower_band.iloc[i]
                    direction.iloc[i] = 1  # 상승 추세
                elif supertrend.iloc[i - 1] == final_lower_band.iloc[i - 1] and close.iloc[i] >= final_lower_band.iloc[i]:
                    supertrend.iloc[i] = final_lower_band.iloc[i]
                    direction.iloc[i] = 1  # 상승 추세
                elif supertrend.iloc[i - 1] == final_lower_band.iloc[i - 1] and close.iloc[i] < final_lower_band.iloc[i]:
                    supertrend.iloc[i] = final_upper_band.iloc[i]
                    direction.iloc[i] = -1  # 하락 추세
                else:
                    # 이전 값 유지
                    supertrend.iloc[i] = supertrend.iloc[i - 1]
                    direction.iloc[i] = direction.iloc[i - 1]

            return {"supertrend": supertrend, "direction": direction}
        except Exception as e:
            logger.error(f"슈퍼트렌드 계산 중 오류: {str(e)}")
            return {"supertrend": pd.Series(), "direction": pd.Series()}

    def _analyze_chart_patterns(self, df: pd.DataFrame) -> ChartPatternAnalysis:
        """
        차트 패턴을 분석합니다.

        Args:
            df: 주가 DataFrame

        Returns:
            차트 패턴 분석 결과
        """
        try:
            if df.empty:
                return {}

            # DataFrame을 인스턴스 변수로 저장 (현재가 참조용)
            self._current_df = df

            close = df["close"]
            high = df["high"]
            low = df["low"]

            # 지지선/저항선 계산
            support_levels = self._find_support_levels(low, 60, 10)
            resistance_levels = self._find_resistance_levels(high, 60, 10)

            # 추세 방향 분석
            trend_direction, trend_strength = self._analyze_trend(close)

            # 차트 패턴 식별
            patterns = self._identify_chart_patterns(df)

            # 돌파 신호 분석
            breakout_signals = self._analyze_breakout_signals(df, support_levels, resistance_levels)

            return {
                "support_levels": support_levels,
                "resistance_levels": resistance_levels,
                "trend_direction": trend_direction,
                "trend_strength": trend_strength,
                "patterns": patterns,
                "breakout_signals": breakout_signals,
            }

        except Exception as e:
            logger.error(f"차트 패턴 분석 중 오류: {str(e)}")
            return {}

    def _find_support_levels(self, low: pd.Series, window: int = 60, compress_pct: float = 5.0) -> List[float]:
        """가격 집중도 기반 지지선을 찾습니다 (시고저종 가격이 뭉치는 구간)."""
        try:
            logger.info(f"가격 집중도 기반 지지선 계산 시작: window={window}, low 데이터 길이={len(low)}")

            # 현재가 정보 확인 (DataFrame의 종가 사용, 없으면 저가의 마지막 값)
            current_price = None
            if hasattr(self, "_current_df") and self._current_df is not None and "close" in self._current_df.columns:
                current_price = float(self._current_df["close"].iloc[-1])
                # logger.info(f"현재가(종가): {current_price:.0f}원")
            elif len(low) > 0:
                current_price = float(low.iloc[-1])
                # logger.info(f"현재가(저가 기준): {current_price:.0f}원")

            if current_price is None:
                logger.warning("현재가 정보를 가져올 수 없어 빈 리스트 반환")
                return []

            # DataFrame에서 시고저종 가격 데이터 수집
            if hasattr(self, "_current_df") and self._current_df is not None:
                df_recent = self._current_df.tail(window)
                logger.info(f"가격 집중도 분석용 데이터: 최근 {len(df_recent)}일")

                # 지지선용 가격 수집: 시가, 저가, 종가 (고가 제외)
                support_prices = []
                for _, row in df_recent.iterrows():
                    support_prices.extend([float(row["open"]), float(row["low"]), float(row["close"])])

                # 현재가보다 낮은 가격들만 필터링 (지지선 후보)
                support_candidates = [p for p in support_prices if p < current_price * 0.995]  # 0.5% 이상 낮은 가격
                logger.info(f"지지선 분석용 가격(시/저/종): {len(support_prices)}개 → 현재가({current_price:.0f}원)보다 낮은 후보: {len(support_candidates)}개")

                if support_candidates:
                    # 가격대별 집중도 계산 (100원 단위로 그룹화)
                    initial_clusters = self._find_price_clusters(support_candidates, cluster_size=100)
                    logger.info(f"초기 클러스터 분석 완료: {len(initial_clusters)}개 클러스터")

                    # 모든 클러스터를 대상으로 5% 범위로 재압축
                    if initial_clusters:
                        compressed_levels = self._compress_similar_levels([cluster["avg_price"] for cluster in initial_clusters], is_support=True, threshold_pct=compress_pct)
                        logger.info(f"{compress_pct}% 범위 압축 완료: {len(initial_clusters)}개 → {len(compressed_levels)}개")

                        # 압축된 결과에서 상위 2개만 선택
                        final_support_levels = compressed_levels[:2]

                        if final_support_levels:
                            # 지지선은 낮은 순으로 정렬
                            final_support_levels.sort()
                            logger.info(f"최종 지지선 {len(final_support_levels)}개: {[f'{s:.0f}원' for s in final_support_levels]}")
                            return final_support_levels

            # Fallback: 기존 방식으로 지지선 찾기
            logger.info("가격 집중도 방식 실패, 기존 방식으로 fallback")
            return self._find_support_levels_fallback(low, window, current_price)

        except Exception as e:
            logger.warning(f"가격 집중도 기반 지지선 계산 중 오류: {str(e)}")
            return self._find_support_levels_simple(low, window)

    def _find_support_levels_fallback(self, low: pd.Series, window: int, current_price: float) -> List[float]:
        """기존 방식의 지지선 찾기 (fallback)"""
        try:
            logger.info("Fallback 지지선 계산 시작")

            # 현재가 대비 합리적한 범위 설정 (현재가의 70% ~ 99% 범위)
            min_support = current_price * 0.70
            max_support = current_price * 0.99
            logger.info(f"Fallback 지지선 범위: {min_support:.0f}원 ~ {max_support:.0f}원")

            # 최근 저점들 중에서 현재가보다 낮은 것들을 찾기
            recent_low_values = low.tail(window)
            low_points = []

            for i in range(2, len(recent_low_values) - 2):
                if (
                    recent_low_values.iloc[i] < recent_low_values.iloc[i - 1]
                    and recent_low_values.iloc[i] < recent_low_values.iloc[i + 1]
                    and min_support <= recent_low_values.iloc[i] <= max_support
                ):
                    low_points.append(float(recent_low_values.iloc[i]))

            if low_points:
                # 중복 제거 및 상위 3개 선택 (높은 순)
                unique_points = list(set(low_points))
                sorted_points = sorted(unique_points, reverse=True)[:3]
                logger.info(f"Fallback 지지선 {len(sorted_points)}개: {[f'{p:.0f}원' for p in sorted_points]}")
                return sorted_points

            logger.info("Fallback에서도 지지선을 찾지 못함")
            return []

        except Exception as e:
            logger.warning(f"Fallback 지지선 계산 중 오류: {str(e)}")
            return []

    def _find_resistance_levels(self, high: pd.Series, window: int = 120, compress_pct: float = 5.0) -> List[float]:
        """가격 집중도 기반 저항선을 찾습니다 (시고저종 가격이 뭉치는 구간)."""
        try:
            logger.info(f"가격 집중도 기반 저항선 계산 시작: window={window}, high 데이터 길이={len(high)}")

            # 현재가 정보 확인 (DataFrame의 종가 사용, 없으면 고가의 마지막 값)
            current_price = None
            if hasattr(self, "_current_df") and self._current_df is not None and "close" in self._current_df.columns:
                current_price = float(self._current_df["close"].iloc[-1])
                logger.info(f"현재가(종가): {current_price:.0f}원")
            elif len(high) > 0:
                current_price = float(high.iloc[-1])
                logger.info(f"현재가(고가 기준): {current_price:.0f}원")

            if current_price is None:
                logger.warning("현재가 정보를 가져올 수 없어 빈 리스트 반환")
                return []

            # DataFrame에서 시고저종 가격 데이터 수집
            if hasattr(self, "_current_df") and self._current_df is not None:
                df_recent = self._current_df.tail(window)
                logger.info(f"가격 집중도 분석용 데이터: 최근 {len(df_recent)}일")

                # 저항선용 가격 수집: 시가, 고가, 종가 (저가 제외)
                resistance_prices = []
                for _, row in df_recent.iterrows():
                    resistance_prices.extend([float(row["open"]), float(row["high"]), float(row["close"])])

                # 현재가보다 높은 가격들만 필터링 (저항선 후보)
                resistance_candidates = [p for p in resistance_prices if p > current_price * 1.005]  # 0.5% 이상 높은 가격
                logger.info(f"저항선 분석용 가격(시/고/종): {len(resistance_prices)}개 → 현재가({current_price:.0f}원)보다 높은 후보: {len(resistance_candidates)}개")

                if resistance_candidates:
                    # 가격대별 집중도 계산 (100원 단위로 그룹화)
                    initial_clusters = self._find_price_clusters(resistance_candidates, cluster_size=100)
                    logger.info(f"초기 클러스터 분석 완료: {len(initial_clusters)}개 클러스터")

                    # 모든 클러스터를 대상으로 5% 범위로 재압축
                    if initial_clusters:
                        compressed_levels = self._compress_similar_levels([cluster["avg_price"] for cluster in initial_clusters], is_support=False, threshold_pct=compress_pct)
                        logger.info(f"{compress_pct}% 범위 압축 완료: {len(initial_clusters)}개 → {len(compressed_levels)}개")

                        # 압축된 결과에서 상위 2개만 선택
                        final_resistance_levels = compressed_levels[:2]

                        if final_resistance_levels:
                            # 저항선은 높은 순으로 정렬
                            final_resistance_levels.sort(reverse=True)
                            logger.info(f"최종 저항선 {len(final_resistance_levels)}개: {[f'{r:.0f}원' for r in final_resistance_levels]}")
                            return final_resistance_levels

            # Fallback: 기존 방식으로 저항선 찾기
            logger.info("가격 집중도 방식 실패, 기존 방식으로 fallback")
            return self._find_resistance_levels_fallback(high, window, current_price)

        except Exception as e:
            logger.warning(f"가격 집중도 기반 저항선 계산 중 오류: {str(e)}")
            return self._find_resistance_levels_simple(high, window)

    def _compress_similar_levels(self, levels: List[float], is_support: bool = True, threshold_pct: float = 5.0) -> List[float]:
        """
        비슷한 가격대의 레벨들을 5% 범위로 압축합니다.

        Args:
            levels: 압축할 가격 레벨 리스트
            is_support: True면 지지선, False면 저항선
            threshold_pct: 압축 기준 비율 (기본 5%)

        Returns:
            압축된 레벨 리스트 (강도 순으로 정렬됨)
        """
        try:
            # logger.info(f"가격 레벨 압축 시작: {'지지선' if is_support else '저항선'} {len(levels)}개, 임계값={threshold_pct}%")

            if not levels or len(levels) <= 1:
                logger.info("압축할 레벨이 1개 이하이므로 그대로 반환")
                return levels

            # 정렬된 레벨 (지지선: 낮은순, 저항선: 높은순)
            sorted_levels = sorted(levels) if is_support else sorted(levels, reverse=True)
            # logger.info(f"정렬된 레벨들: {[f'{l:.0f}원' for l in sorted_levels]}")

            compressed_groups = []
            i = 0

            while i < len(sorted_levels):
                current_level = sorted_levels[i]
                group_levels = [current_level]

                # 현재 레벨과 비슷한 레벨들을 찾아서 그룹화
                j = i + 1
                while j < len(sorted_levels):
                    next_level = sorted_levels[j]

                    # 두 레벨 사이의 차이를 백분율로 계산
                    reference_price = max(current_level, next_level)
                    diff_pct = abs(current_level - next_level) / reference_price * 100

                    # logger.info(f"레벨 비교: {current_level:.0f}원 vs {next_level:.0f}원, 차이={diff_pct:.1f}%")

                    if diff_pct <= threshold_pct:
                        group_levels.append(next_level)
                        # logger.info(f"그룹에 추가: {next_level:.0f}원")
                        j += 1
                    else:
                        break

                # 그룹의 평균값과 강도 계산
                avg_price = sum(group_levels) / len(group_levels)
                strength = len(group_levels)  # 그룹 크기가 강도

                compressed_groups.append({"avg_price": avg_price, "strength": strength, "count": len(group_levels)})

                if len(group_levels) > 1:
                    logger.info(f"레벨 그룹 압축: {[f'{l:.0f}원' for l in group_levels]} → {avg_price:.0f}원 (강도: {strength})")

                # 다음 인덱스로 이동
                i = j

            # 강도 순으로 정렬하여 상위 레벨들을 반환
            compressed_groups.sort(key=lambda x: x["strength"], reverse=True)

            result_levels = [group["avg_price"] for group in compressed_groups]

            # logger.info(f"압축 완료: {len(levels)}개 → {len(result_levels)}개")
            # logger.info(f"강도별 압축 결과:")
            # for i, group in enumerate(compressed_groups):
            #     logger.info(f"  {i+1}. {group['avg_price']:.0f}원 (강도: {group['strength']}, 개수: {group['count']})")

            return result_levels

        except Exception as e:
            logger.warning(f"가격 레벨 압축 중 오류: {str(e)}")
            return levels

    def _find_price_clusters(self, prices: List[float], cluster_size: int = 100) -> List[Dict[str, Any]]:
        """가격들을 클러스터별로 그룹화하고 빈도수를 계산합니다."""
        try:
            if not prices:
                return []

            # 가격대별 빈도수 계산
            price_counts = {}
            for price in prices:
                # cluster_size 단위로 반올림 (예: 100원 단위)
                cluster_key = round(price / cluster_size) * cluster_size
                price_counts[cluster_key] = price_counts.get(cluster_key, 0) + 1

            # 클러스터 정보 구성
            clusters = []
            for cluster_price, count in price_counts.items():
                # 해당 클러스터에 속하는 실제 가격들의 평균 계산
                cluster_prices = [p for p in prices if abs(p - cluster_price) <= cluster_size / 2]
                avg_price = sum(cluster_prices) / len(cluster_prices) if cluster_prices else cluster_price

                clusters.append(
                    {
                        "cluster_key": cluster_price,
                        "avg_price": avg_price,
                        "count": count,
                        "strength": count * (1.0 + len(cluster_prices) / len(prices)),  # 강도 점수
                    }
                )

            # 강도 순으로 정렬
            clusters.sort(key=lambda x: x["strength"], reverse=True)

            # logger.info(f"상위 클러스터들:")
            # for i, cluster in enumerate(clusters[:5]):
            #     logger.info(f"  {i+1}. {cluster['avg_price']:.0f}원 (빈도: {cluster['count']}, 강도: {cluster['strength']:.2f})")

            return clusters

        except Exception as e:
            logger.warning(f"가격 클러스터 계산 중 오류: {str(e)}")
            return []

    def _find_resistance_levels_fallback(self, high: pd.Series, window: int, current_price: float) -> List[float]:
        """기존 방식의 저항선 찾기 (fallback)"""
        try:
            logger.info("Fallback 저항선 계산 시작")

            # 현재가 대비 합리적한 범위 설정 (현재가의 101% ~ 150% 범위)
            min_resistance = current_price * 1.01
            max_resistance = current_price * 1.50
            logger.info(f"Fallback 저항선 범위: {min_resistance:.0f}원 ~ {max_resistance:.0f}원")

            # 최근 고점들 중에서 현재가보다 높은 것들을 찾기
            recent_high_values = high.tail(window)
            high_peaks = []

            for i in range(2, len(recent_high_values) - 2):
                if (
                    recent_high_values.iloc[i] > recent_high_values.iloc[i - 1]
                    and recent_high_values.iloc[i] > recent_high_values.iloc[i + 1]
                    and min_resistance <= recent_high_values.iloc[i] <= max_resistance
                ):
                    high_peaks.append(float(recent_high_values.iloc[i]))

            if high_peaks:
                # 중복 제거 및 상위 3개 선택
                unique_peaks = list(set(high_peaks))
                sorted_peaks = sorted(unique_peaks, reverse=True)[:3]
                logger.info(f"Fallback 저항선 {len(sorted_peaks)}개: {[f'{p:.0f}원' for p in sorted_peaks]}")
                return sorted_peaks

            logger.info("Fallback에서도 저항선을 찾지 못함")
            return []

        except Exception as e:
            logger.warning(f"Fallback 저항선 계산 중 오류: {str(e)}")
            return []

    def _merge_adjacent_levels(self, levels: List[float], is_support: bool = True, threshold_pct: float = 2.5) -> List[float]:
        """
        인접한 지지선/저항선들을 통합합니다.

        Args:
            levels: 지지선 또는 저항선 리스트
            is_support: True면 지지선, False면 저항선
            threshold_pct: 통합 기준 비율 (기본 2.5%)

        Returns:
            통합된 레벨 리스트
        """
        try:
            logger.info(f"레벨 통합 시작: {'지지선' if is_support else '저항선'} {len(levels)}개, 임계값={threshold_pct}%")

            if not levels or len(levels) <= 1:
                logger.info("통합할 레벨이 1개 이하이므로 그대로 반환")
                return levels

            # 정렬된 레벨 로그
            sorted_levels = sorted(levels) if is_support else sorted(levels, reverse=True)
            # logger.info(f"정렬된 레벨들: {[f'{l:.0f}원' for l in sorted_levels]}")

            merged_levels = []
            i = 0

            while i < len(sorted_levels):
                current_level = sorted_levels[i]
                levels_to_merge = [current_level]

                # 다음 레벨들과 비교하여 인접한 것들을 찾음
                j = i + 1
                while j < len(sorted_levels):
                    next_level = sorted_levels[j]

                    # 두 레벨 사이의 차이를 백분율로 계산
                    if is_support:
                        # 지지선의 경우: 더 높은 가격을 기준으로 계산
                        reference_price = max(current_level, next_level)
                        diff_pct = abs(current_level - next_level) / reference_price * 100
                    else:
                        # 저항선의 경우: 더 높은 가격을 기준으로 계산
                        reference_price = max(current_level, next_level)
                        diff_pct = abs(current_level - next_level) / reference_price * 100

                    # logger.info(f"레벨 비교: {current_level:.0f}원 vs {next_level:.0f}원, 차이={diff_pct:.1f}%")

                    if diff_pct <= threshold_pct:
                        levels_to_merge.append(next_level)
                        # logger.info(f"통합 대상에 추가: {next_level:.0f}원")
                        j += 1
                    else:
                        break

                # 통합된 레벨 계산 (평균값 사용)
                merged_level = sum(levels_to_merge) / len(levels_to_merge)
                merged_levels.append(merged_level)

                # if len(levels_to_merge) > 1:
                #     logger.info(f"레벨 통합: {[f'{l:.0f}원' for l in levels_to_merge]} → {merged_level:.0f}원")

                # 다음 인덱스로 이동
                i = j

            # 지지선은 낮은 순, 저항선은 높은 순으로 정렬
            if is_support:
                merged_levels.sort()
            else:
                merged_levels.sort(reverse=True)

            # logger.info(f"레벨 통합 완료: {len(levels)}개 → {len(merged_levels)}개")
            logger.info(f"최종 통합 레벨: {[f'{l:.0f}원' for l in merged_levels]}")

            return merged_levels

        except Exception as e:
            logger.warning(f"레벨 통합 중 오류: {str(e)}")
            return levels

    def _find_support_candidates_with_strength(self, low: pd.Series, window: int, min_price: float, max_price: float) -> List[Dict[str, Any]]:
        """강도 점수와 함께 지지선 후보를 찾습니다."""
        try:
            recent_lows = low.tail(window)
            candidates = []

            # 1. 기본 지지선 후보 찾기
            for i in range(2, len(recent_lows) - 2):
                if (
                    recent_lows.iloc[i] < recent_lows.iloc[i - 1]
                    and recent_lows.iloc[i] < recent_lows.iloc[i + 1]
                    and recent_lows.iloc[i] < recent_lows.iloc[i - 2]
                    and recent_lows.iloc[i] < recent_lows.iloc[i + 2]
                ):
                    support_price = float(recent_lows.iloc[i])
                    if min_price <= support_price <= max_price:
                        candidates.append(
                            {
                                "price": support_price,
                                "index": i,
                                "strength": 1.0,  # 기본 강도
                            }
                        )

            # 2. 강도 점수 계산
            candidates = self._calculate_level_strength(candidates, recent_lows, is_support=True)

            # logger.info(f"지지선 후보 강도 계산 완료: {len(candidates)}개")
            for candidate in candidates:
                logger.debug(f"지지선 후보: {candidate['price']:.0f}원, 강도: {candidate['strength']:.2f}")

            return candidates

        except Exception as e:
            logger.warning(f"지지선 후보 강도 계산 중 오류: {str(e)}")
            return []

    def _find_resistance_candidates_with_strength(self, high: pd.Series, window: int, min_price: float, max_price: float) -> List[Dict[str, Any]]:
        """강도 점수와 함께 저항선 후보를 찾습니다."""
        try:
            recent_highs = high.tail(window)
            candidates = []

            # 1. 기본 저항선 후보 찾기
            for i in range(2, len(recent_highs) - 2):
                if (
                    recent_highs.iloc[i] > recent_highs.iloc[i - 1]
                    and recent_highs.iloc[i] > recent_highs.iloc[i + 1]
                    and recent_highs.iloc[i] > recent_highs.iloc[i - 2]
                    and recent_highs.iloc[i] > recent_highs.iloc[i + 2]
                ):
                    resistance_price = float(recent_highs.iloc[i])
                    if min_price <= resistance_price <= max_price:
                        candidates.append(
                            {
                                "price": resistance_price,
                                "index": i,
                                "strength": 1.0,  # 기본 강도
                            }
                        )

            # 2. 강도 점수 계산
            candidates = self._calculate_level_strength(candidates, recent_highs, is_support=False)

            logger.info(f"저항선 후보 강도 계산 완료: {len(candidates)}개")
            for candidate in candidates:
                logger.debug(f"저항선 후보: {candidate['price']:.0f}원, 강도: {candidate['strength']:.2f}")

            return candidates

        except Exception as e:
            logger.warning(f"저항선 후보 강도 계산 중 오류: {str(e)}")
            return []

    def _calculate_level_strength(self, candidates: List[Dict[str, Any]], price_series: pd.Series, is_support: bool = True) -> List[Dict[str, Any]]:
        """레벨들의 강도를 계산합니다."""
        try:
            if not candidates:
                return candidates

            # 강도 계산을 위한 임계값 (3% 이내의 가격을 비슷한 가격대로 간주)
            similarity_threshold = 0.03

            for i, candidate in enumerate(candidates):
                base_price = candidate["price"]
                strength = 1.0  # 기본 강도

                # 1. 비슷한 가격대의 다른 후보들과의 근접도로 강도 증가
                nearby_count = 0
                for j, other_candidate in enumerate(candidates):
                    if i != j:
                        other_price = other_candidate["price"]
                        price_diff_pct = abs(base_price - other_price) / max(base_price, other_price)

                        if price_diff_pct <= similarity_threshold:
                            nearby_count += 1
                            strength += 0.5  # 비슷한 가격대마다 강도 +0.5

                # 2. 가격 시리즈에서 해당 가격대 근처의 터치 횟수 계산
                touch_count = 0
                for price in price_series:
                    price_diff_pct = abs(base_price - float(price)) / max(base_price, float(price))
                    if price_diff_pct <= similarity_threshold:
                        touch_count += 1

                # 터치 횟수에 따른 강도 증가 (많이 터치될수록 강한 레벨)
                strength += (touch_count - 1) * 0.2  # 첫 터치 제외하고 추가 터치마다 +0.2

                # 3. 최근성 가중치 (최근 레벨일수록 더 중요)
                recency_weight = 1.0 + (candidate["index"] / len(price_series)) * 0.3
                strength *= recency_weight

                candidates[i]["strength"] = strength
                candidates[i]["nearby_count"] = nearby_count
                candidates[i]["touch_count"] = touch_count

                logger.debug(f"{'지지선' if is_support else '저항선'} {base_price:.0f}원: 강도={strength:.2f}, 근접={nearby_count}개, 터치={touch_count}회")

            return candidates

        except Exception as e:
            logger.warning(f"레벨 강도 계산 중 오류: {str(e)}")
            return candidates

    def _select_top_levels_by_strength(self, candidates: List[Dict[str, Any]], is_support: bool = True, top_n: int = 3) -> List[float]:
        """강도 순으로 상위 레벨들을 선택합니다."""
        try:
            if not candidates:
                return []

            # 강도 순으로 정렬 (높은 강도 먼저)
            sorted_candidates = sorted(candidates, key=lambda x: x["strength"], reverse=True)

            # 중복 가격 제거 (비슷한 가격대는 하나만 선택)
            selected_levels = []
            similarity_threshold = 0.025  # 2.5% 이내는 같은 레벨로 간주

            for candidate in sorted_candidates:
                candidate_price = candidate["price"]
                is_duplicate = False

                for selected_price in selected_levels:
                    price_diff_pct = abs(candidate_price - selected_price) / max(candidate_price, selected_price)
                    if price_diff_pct <= similarity_threshold:
                        is_duplicate = True
                        break

                if not is_duplicate:
                    selected_levels.append(candidate_price)
                    logger.info(
                        f"선택된 {'지지선' if is_support else '저항선'}: "
                        f"{candidate_price:.0f}원 (강도: {candidate['strength']:.2f}, "
                        f"근접: {candidate.get('nearby_count', 0)}개, "
                        f"터치: {candidate.get('touch_count', 0)}회)"
                    )

                    if len(selected_levels) >= top_n:
                        break

            # 지지선은 높은 순, 저항선은 높은 순으로 정렬 (강도 기준으로 이미 정렬됨)
            return selected_levels

        except Exception as e:
            logger.warning(f"상위 레벨 선택 중 오류: {str(e)}")
            return [candidate["price"] for candidate in candidates[:top_n]]

    def _get_recent_dataframe(self, window: int) -> pd.DataFrame:
        """최근 window 기간의 DataFrame을 반환합니다."""
        try:
            # 현재 처리 중인 DataFrame에서 최근 데이터 추출
            if hasattr(self, "_current_df") and not self._current_df.empty:
                return self._current_df.tail(window)
            return pd.DataFrame()
        except:
            return pd.DataFrame()

    def _find_support_levels_simple(self, low: pd.Series, window: int = 60) -> List[float]:
        """기본적인 지지선 찾기 (현재가 대비 합리적 범위 적용)"""
        try:
            logger.info(f"단순 지지선 계산 시작: window={window}")

            # 현재가 정보 확인
            current_price = float(low.iloc[-1]) if len(low) > 0 else None
            if current_price is None:
                logger.warning("현재가 정보를 가져올 수 없어 빈 리스트 반환")
                return []

            logger.info(f"현재가: {current_price:.0f}원")

            # 현재가 대비 합리적인 범위 설정 (현재가의 50% ~ 95% 범위)
            min_support = current_price * 0.50
            max_support = current_price * 0.95
            logger.info(f"지지선 유효 범위: {min_support:.0f}원 ~ {max_support:.0f}원")

            # 기존 방식으로 지지선 계산
            supports = []
            recent_lows = low.tail(window)

            for i in range(2, len(recent_lows) - 2):
                if (
                    recent_lows.iloc[i] < recent_lows.iloc[i - 1]
                    and recent_lows.iloc[i] < recent_lows.iloc[i + 1]
                    and recent_lows.iloc[i] < recent_lows.iloc[i - 2]
                    and recent_lows.iloc[i] < recent_lows.iloc[i + 2]
                ):
                    support_price = float(recent_lows.iloc[i])

                    # 현재가 대비 합리적인 범위 내의 지지선만 선택
                    if min_support <= support_price <= max_support:
                        supports.append(support_price)
                        logger.debug(f"유효한 단순 지지선 후보: {support_price:.0f}원")
                    else:
                        logger.debug(f"범위 외 단순 지지선 후보 제외: {support_price:.0f}원")

            logger.info(f"유효 범위 내 단순 지지선 후보 {len(supports)}개 발견")
            supports = sorted(list(set(supports)), reverse=True)  # 높은 순서대로 정렬
            supports = self._merge_adjacent_levels(supports, is_support=True)
            final_supports = supports[:3]  # 3개로 증가
            logger.info(f"최종 단순 지지선 {len(final_supports)}개: {[f'{s:.0f}원' for s in final_supports]}")
            return final_supports

        except Exception as e:
            logger.warning(f"단순 지지선 계산 중 오류: {str(e)}")
            return []

    def _find_resistance_levels_simple(self, high: pd.Series, window: int = 120) -> List[float]:
        """기본적인 저항선 찾기 (현재가 대비 합리적 범위 적용)"""
        try:
            logger.info(f"단순 저항선 계산 시작: window={window}")

            # 현재가 정보 확인
            current_price = float(high.iloc[-1]) if len(high) > 0 else None
            if current_price is None:
                logger.warning("현재가 정보를 가져올 수 없어 빈 리스트 반환")
                return []

            logger.info(f"현재가 기준: {current_price:.0f}원")

            # 현재가 대비 합리적인 범위 설정 (현재가의 105% ~ 200% 범위)
            min_resistance = current_price * 1.05
            max_resistance = current_price * 2.00
            logger.info(f"저항선 유효 범위: {min_resistance:.0f}원 ~ {max_resistance:.0f}원")

            # 기존 방식으로 저항선 계산
            resistances = []
            recent_highs = high.tail(window)

            for i in range(2, len(recent_highs) - 2):
                if (
                    recent_highs.iloc[i] > recent_highs.iloc[i - 1]
                    and recent_highs.iloc[i] > recent_highs.iloc[i + 1]
                    and recent_highs.iloc[i] > recent_highs.iloc[i - 2]
                    and recent_highs.iloc[i] > recent_highs.iloc[i + 2]
                ):
                    resistance_price = float(recent_highs.iloc[i])

                    # 현재가 대비 합리적인 범위 내의 저항선만 선택
                    if min_resistance <= resistance_price <= max_resistance:
                        resistances.append(resistance_price)
                        logger.debug(f"유효한 단순 저항선 후보: {resistance_price:.0f}원")
                    else:
                        logger.debug(f"범위 외 단순 저항선 후보 제외: {resistance_price:.0f}원")

            logger.info(f"유효 범위 내 단순 저항선 후보 {len(resistances)}개 발견")
            resistances = sorted(list(set(resistances)), reverse=True)
            resistances = self._merge_adjacent_levels(resistances, is_support=False)
            final_resistances = resistances[:3]  # 3개로 증가
            logger.info(f"최종 단순 저항선 {len(final_resistances)}개: {[f'{r:.0f}원' for r in final_resistances]}")
            return final_resistances

        except Exception as e:
            logger.warning(f"단순 저항선 계산 중 오류: {str(e)}")
            return []

    def _find_volume_based_supports(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """거래량 집중 구간에서 지지선을 찾습니다 (Volume Profile 개념)."""
        try:
            logger.info(f"거래량 기반 지지선 계산 시작: 데이터 개수={len(df)}")

            if df.empty or len(df) < 10:
                logger.warning(f"데이터 부족으로 거래량 기반 지지선 계산 불가: 데이터 개수={len(df)}")
                return []

            supports = []

            # 가격대별 거래량 집계 (Price-Volume Distribution)
            price_volume_dist = self._calculate_price_volume_distribution(df)
            logger.info(f"가격-거래량 분포 계산 완료: 구간 개수={len(price_volume_dist)}")

            if price_volume_dist.empty:
                logger.warning("가격-거래량 분포가 비어있음")
                return []

            # 거래량이 많이 몰린 가격대 중 현재가보다 낮은 구간을 지지선으로 간주
            current_price = float(df["close"].iloc[-1])
            volume_threshold = price_volume_dist["volume"].quantile(0.8)  # 상위 20% 거래량
            max_volume = price_volume_dist["volume"].max()

            logger.info(f"현재가: {current_price:.0f}원, 거래량 임계값: {volume_threshold:.0f}, 최대 거래량: {max_volume:.0f}")

            # 현재가보다 낮은 가격대 필터링
            lower_prices = price_volume_dist[price_volume_dist["price"] < current_price]
            logger.info(f"현재가보다 낮은 가격대: {len(lower_prices)}개")

            # 거래량 임계값 이상 필터링
            high_volume_prices = lower_prices[lower_prices["volume"] >= volume_threshold]
            logger.info(f"거래량 임계값 이상인 가격대: {len(high_volume_prices)}개")

            if len(high_volume_prices) == 0:
                logger.info("거래량 기준을 만족하는 지지선 후보가 없음 - 임계값을 낮춰서 재시도")
                # 임계값을 낮춰서 재시도 (상위 50%)
                volume_threshold = price_volume_dist["volume"].quantile(0.5)
                high_volume_prices = lower_prices[lower_prices["volume"] >= volume_threshold]
                logger.info(f"임계값 완화 후 후보: {len(high_volume_prices)}개 (임계값: {volume_threshold:.0f})")

            for _, row in high_volume_prices.iterrows():
                support_price = float(row["price"])
                volume = float(row["volume"])
                strength = volume / max_volume if max_volume > 0 else 0.5

                supports.append(
                    {
                        "price": support_price,
                        "index": -1,  # Volume-based는 특정 인덱스가 없음
                        "strength": strength,  # 정규화된 강도
                    }
                )
                logger.debug(f"거래량 기반 지지선 후보: {support_price:.0f}원, 거래량={volume:.0f}, 강도={strength:.2f}")

            logger.info(f"거래량 기반 지지선 후보 {len(supports)}개 발견")
            return supports

        except Exception as e:
            logger.warning(f"거래량 기반 지지선 계산 중 오류: {str(e)}")
            return []

    def _find_volume_based_resistances(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """거래량 집중 구간에서 저항선을 찾습니다 (Volume Profile 개념)."""
        try:
            logger.info(f"거래량 기반 저항선 계산 시작: 데이터 개수={len(df)}")

            if df.empty or len(df) < 10:
                logger.warning(f"데이터 부족으로 거래량 기반 저항선 계산 불가: 데이터 개수={len(df)}")
                return []

            resistances = []

            # 가격대별 거래량 집계
            price_volume_dist = self._calculate_price_volume_distribution(df)
            logger.info(f"가격-거래량 분포 계산 완료: 구간 개수={len(price_volume_dist)}")

            if price_volume_dist.empty:
                logger.warning("가격-거래량 분포가 비어있음")
                return []

            # 거래량이 많이 몰린 가격대 중 현재가보다 높은 구간을 저항선으로 간주
            current_price = float(df["close"].iloc[-1])
            volume_threshold = price_volume_dist["volume"].quantile(0.8)  # 상위 20% 거래량
            max_volume = price_volume_dist["volume"].max()

            logger.info(f"현재가: {current_price:.0f}원, 거래량 임계값: {volume_threshold:.0f}, 최대 거래량: {max_volume:.0f}")

            # 현재가보다 높은 가격대 필터링
            higher_prices = price_volume_dist[price_volume_dist["price"] > current_price]
            logger.info(f"현재가보다 높은 가격대: {len(higher_prices)}개")

            # 거래량 임계값 이상 필터링
            high_volume_prices = higher_prices[higher_prices["volume"] >= volume_threshold]
            logger.info(f"거래량 임계값 이상인 가격대: {len(high_volume_prices)}개")

            if len(high_volume_prices) == 0:
                logger.info("거래량 기준을 만족하는 저항선 후보가 없음 - 임계값을 낮춰서 재시도")
                # 임계값을 낮춰서 재시도 (상위 50%)
                volume_threshold = price_volume_dist["volume"].quantile(0.5)
                high_volume_prices = higher_prices[higher_prices["volume"] >= volume_threshold]
                logger.info(f"임계값 완화 후 후보: {len(high_volume_prices)}개 (임계값: {volume_threshold:.0f})")

            for _, row in high_volume_prices.iterrows():
                resistance_price = float(row["price"])
                volume = float(row["volume"])
                strength = volume / max_volume if max_volume > 0 else 0.5

                resistances.append(
                    {
                        "price": resistance_price,
                        "index": -1,  # Volume-based는 특정 인덱스가 없음
                        "strength": strength,  # 정규화된 강도
                    }
                )
                logger.debug(f"거래량 기반 저항선 후보: {resistance_price:.0f}원, 거래량={volume:.0f}, 강도={strength:.2f}")

            logger.info(f"거래량 기반 저항선 후보 {len(resistances)}개 발견")
            return resistances

        except Exception as e:
            logger.warning(f"거래량 기반 저항선 계산 중 오류: {str(e)}")
            return []

    def _calculate_price_volume_distribution(self, df: pd.DataFrame) -> pd.DataFrame:
        """가격대별 거래량 분포를 계산합니다 (Volume Profile)."""
        try:
            if df.empty:
                logger.warning("가격-거래량 분포 계산: 빈 데이터프레임")
                return pd.DataFrame()

            # 가격 범위를 여러 구간으로 나누어 거래량 집계
            min_price = df["low"].min()
            max_price = df["high"].max()
            price_range = max_price - min_price

            logger.info(f"가격 범위: {min_price:.0f}원 ~ {max_price:.0f}원 (범위: {price_range:.0f}원)")

            # 50개 구간으로 나누어 분석
            price_bins = np.linspace(min_price, max_price, 51)
            logger.info(f"가격 구간: 50개 구간으로 분할 (구간당 약 {price_range / 50:.0f}원)")

            volume_distribution = []
            total_volume = 0
            non_zero_bins = 0

            for i in range(len(price_bins) - 1):
                bin_low = price_bins[i]
                bin_high = price_bins[i + 1]
                bin_center = (bin_low + bin_high) / 2

                # 해당 가격 구간에 포함되는 캔들들의 거래량 합계
                volume_in_bin = df[(df["low"] <= bin_high) & (df["high"] >= bin_low)]["volume"].sum()

                volume_distribution.append({"price": bin_center, "volume": volume_in_bin})

                total_volume += volume_in_bin
                if volume_in_bin > 0:
                    non_zero_bins += 1
                    logger.debug(f"구간 {i}: {bin_low:.0f}~{bin_high:.0f}원, 거래량={volume_in_bin:.0f}")

            result_df = pd.DataFrame(volume_distribution)
            logger.info(f"가격-거래량 분포 완료: 총 거래량={total_volume:.0f}, 거래량 있는 구간={non_zero_bins}개")

            if total_volume == 0:
                logger.warning("모든 가격 구간의 거래량이 0임 - 데이터 문제 가능성")

            return result_df

        except Exception as e:
            logger.warning(f"가격-거래량 분포 계산 중 오류: {str(e)}")
            return pd.DataFrame()

    def _find_volume_spike_supports(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """거래량 터진 캔들의 저점에서 지지선을 찾습니다."""
        try:
            if df.empty or len(df) < 20:
                return []

            supports = []

            # 평균 거래량 계산
            avg_volume = df["volume"].rolling(window=20).mean()

            # 거래량이 평균의 2배 이상 터진 캔들들 찾기
            volume_spikes = df[df["volume"] >= avg_volume * 2.0]

            current_price = float(df["close"].iloc[-1])

            for idx, row in volume_spikes.iterrows():
                low_price = float(row["low"])
                volume_ratio = float(row["volume"] / avg_volume.loc[idx]) if not pd.isna(avg_volume.loc[idx]) else 1.0

                # 현재가보다 낮은 저점만 지지선으로 간주
                if low_price < current_price:
                    # 양봉인지 음봉인지도 고려 (양봉의 저점이 더 강한 지지선)
                    candle_strength = 1.2 if row["close"] > row["open"] else 1.0

                    supports.append(
                        {
                            "price": low_price,
                            "index": df.index.get_loc(idx),
                            "strength": min(volume_ratio * candle_strength, 3.0),  # 최대 3.0으로 제한
                        }
                    )

            return supports

        except Exception as e:
            logger.warning(f"거래량 급증 지지선 계산 중 오류: {str(e)}")
            return []

    def _find_volume_spike_resistances(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """거래량 터진 캔들의 고점에서 저항선을 찾습니다."""
        try:
            logger.info(f"거래량 급증 저항선 계산 시작: 데이터 개수={len(df)}")

            if df.empty or len(df) < 20:
                logger.warning(f"데이터 부족으로 거래량 급증 저항선 계산 불가: 데이터 개수={len(df)}")
                return []

            resistances = []

            # 평균 거래량 계산
            avg_volume = df["volume"].rolling(window=20).mean()
            recent_avg_volume = avg_volume.dropna().iloc[-10:].mean()  # 최근 10일 평균
            logger.info(f"최근 평균 거래량: {recent_avg_volume:.0f}")

            # 거래량이 평균의 2배 이상 터진 캔들들 찾기
            volume_spikes = df[df["volume"] >= avg_volume * 2.0]
            logger.info(f"거래량 급증 캔들 발견: {len(volume_spikes)}개 (기준: 평균의 2배 이상)")

            current_price = float(df["close"].iloc[-1])
            higher_spikes = 0

            for idx, row in volume_spikes.iterrows():
                high_price = float(row["high"])
                volume = float(row["volume"])
                volume_ratio = float(row["volume"] / avg_volume.loc[idx]) if not pd.isna(avg_volume.loc[idx]) else 1.0

                # 현재가보다 높은 고점만 저항선으로 간주
                if high_price > current_price:
                    higher_spikes += 1
                    # 음봉인지 양봉인지도 고려 (음봉의 고점이 더 강한 저항선)
                    is_bearish = row["close"] < row["open"]
                    candle_strength = 1.2 if is_bearish else 1.0
                    final_strength = min(volume_ratio * candle_strength, 3.0)

                    resistances.append(
                        {
                            "price": high_price,
                            "index": df.index.get_loc(idx),
                            "strength": final_strength,  # 최대 3.0으로 제한
                        }
                    )

                    logger.debug(
                        f"거래량 급증 저항선 후보: {high_price:.0f}원, 거래량={volume:.0f} (비율:{volume_ratio:.1f}x), "
                        f"{'음봉' if is_bearish else '양봉'}, 강도={final_strength:.2f}"
                    )
                else:
                    logger.debug(f"현재가보다 낮은 급증 캔들 제외: {high_price:.0f}원 (현재가: {current_price:.0f}원)")

            logger.info(f"거래량 급증 저항선 후보: 전체 {len(volume_spikes)}개 중 현재가보다 높은 것 {higher_spikes}개, 최종 후보 {len(resistances)}개")

            return resistances

        except Exception as e:
            logger.warning(f"거래량 급증 저항선 계산 중 오류: {str(e)}")
            return []

    def _apply_volume_weights(self, levels: List[Dict[str, Any]], df: pd.DataFrame, is_support: bool = True) -> List[Dict[str, Any]]:
        """거래량 기반 가중치를 적용하여 지지/저항선을 정렬합니다."""
        try:
            if not levels:
                logger.info("가중치 적용: 입력 레벨이 비어있음")
                return []

            # 현재가 기준으로 거리에 따른 가중치도 적용
            current_price = float(df["close"].iloc[-1])
            logger.info(f"가중치 적용: 현재가={current_price:.0f}원, {'지지선' if is_support else '저항선'} 처리")

            # 거리 제한 적용
            if is_support:
                min_price = current_price * 0.75  # 지지선: 25% 하락까지
                max_price = current_price
                logger.info(f"지지선 범위: {min_price:.0f}원 ~ {max_price:.0f}원")
            else:
                min_price = current_price
                max_price = current_price * 1.5  # 저항선: 50% 상승까지
                logger.info(f"저항선 범위: {min_price:.0f}원 ~ {max_price:.0f}원")

            weighted_levels = []
            excluded_count = 0

            for level in levels:
                price = level["price"]
                base_strength = level["strength"]

                # 거리 제한 체크
                if not (min_price <= price <= max_price):
                    excluded_count += 1
                    logger.debug(f"범위 초과로 제외: {price:.0f}원 (범위: {min_price:.0f}~{max_price:.0f})")
                    continue  # 범위를 벗어나면 제외

                # 거리에 따른 가중치 (현재가에서 가까울수록 높은 가중치)
                distance_pct = abs(price - current_price) / current_price * 100
                max_distance = 25.0 if is_support else 50.0  # 지지선 25%, 저항선 50%
                distance_weight = max(0.5, 1.0 - distance_pct / max_distance)

                # 최종 가중치 계산
                final_strength = base_strength * distance_weight

                weighted_levels.append({"price": price, "strength": final_strength, "distance_pct": distance_pct})
                logger.debug(f"가중치 적용: {price:.0f}원, 거리={distance_pct:.1f}%, 기본강도={base_strength:.2f}, 최종강도={final_strength:.2f}")

            logger.info(f"가중치 적용 결과: {len(weighted_levels)}개 유효, {excluded_count}개 범위초과로 제외")

            # 강도순으로 정렬
            weighted_levels.sort(key=lambda x: x["strength"], reverse=True)

            if weighted_levels:
                logger.info(
                    f"상위 3개 {'지지선' if is_support else '저항선'}: " + ", ".join([f"{level['price']:.0f}원(강도:{level['strength']:.2f})" for level in weighted_levels[:3]])
                )

            return weighted_levels

        except Exception as e:
            logger.warning(f"거래량 가중치 적용 중 오류: {str(e)}")
            return [{"price": level["price"], "strength": level.get("strength", 1.0)} for level in levels]

    def _find_meaningful_resistances(self, df: pd.DataFrame) -> List[float]:
        """의미있는 저항선을 찾습니다 (단순 high가 아닌 실제 저항을 받는 가격대)"""
        try:
            if df.empty or len(df) < 10:
                return []

            resistances = []
            current_price = float(df["close"].iloc[-1])

            # 1. 여러 번 테스트된 저항선 찾기 (close 기준)
            tested_resistances = self._find_tested_levels(df, is_support=False)
            resistances.extend(tested_resistances)

            # 2. 거래량 많은 구간에서 저항받는 패턴 찾기
            volume_resistances = self._find_volume_rejection_levels(df, is_support=False)
            resistances.extend(volume_resistances)

            # 3. 실제 마감가 기준 저항선 (high가 아닌 close 기준)
            close_resistances = self._find_close_based_resistances(df)
            resistances.extend(close_resistances)

            # 현재가보다 높고 50% 이내의 저항선만 필터링 (지지선보다 넓은 범위)
            max_resistance_price = current_price * 1.5  # 현재가의 150% (50% 상승선)
            valid_resistances = [r for r in resistances if current_price < r <= max_resistance_price]

            # 중복 제거 및 인접 레벨 통합
            valid_resistances = sorted(list(set(valid_resistances)), reverse=True)
            merged_resistances = self._merge_adjacent_levels(valid_resistances, is_support=False)

            return merged_resistances[:2]

        except Exception as e:
            logger.warning(f"의미있는 저항선 계산 중 오류: {str(e)}")
            return []

    def _find_meaningful_supports(self, df: pd.DataFrame) -> List[float]:
        """의미있는 지지선을 찾습니다 (단순 low가 아닌 실제 지지받는 가격대)"""
        try:
            if df.empty or len(df) < 10:
                return []

            supports = []
            current_price = float(df["close"].iloc[-1])

            # 1. 여러 번 테스트된 지지선 찾기 (close 기준)
            tested_supports = self._find_tested_levels(df, is_support=True)
            supports.extend(tested_supports)

            # 2. 거래량 많은 구간에서 지지받는 패턴 찾기
            volume_supports = self._find_volume_rejection_levels(df, is_support=True)
            supports.extend(volume_supports)

            # 3. 실제 마감가 기준 지지선 (low가 아닌 close 기준)
            close_supports = self._find_close_based_supports(df)
            supports.extend(close_supports)

            # 현재가보다 낮고 25% 이내의 지지선만 필터링
            min_support_price = current_price * 0.75  # 현재가의 75% (25% 하락선)
            valid_supports = [s for s in supports if min_support_price <= s < current_price]

            # 중복 제거 및 인접 레벨 통합
            valid_supports = sorted(list(set(valid_supports)))
            merged_supports = self._merge_adjacent_levels(valid_supports, is_support=True)

            return merged_supports[:2]

        except Exception as e:
            logger.warning(f"의미있는 지지선 계산 중 오류: {str(e)}")
            return []

    def _find_tested_levels(self, df: pd.DataFrame, is_support: bool = True, tolerance_pct: float = 1.5) -> List[float]:
        """여러 번 테스트된 지지/저항선을 찾습니다 (같은 가격대에서 여러 번 반응)"""
        try:
            if df.empty or len(df) < 5:
                return []

            levels = []
            test_prices = df["close"].values if is_support else df["close"].values

            # 각 가격을 기준으로 tolerance 범위 내에서 몇 번 테스트되었는지 확인
            for i, price in enumerate(test_prices):
                if i < 2 or i >= len(test_prices) - 2:  # 양 끝 제외
                    continue

                # 해당 가격 근처에서 반응한 횟수 세기
                reactions = 0
                reference_price = price

                for j, other_price in enumerate(test_prices):
                    if abs(i - j) < 3:  # 너무 가까운 봉은 제외
                        continue

                    # tolerance 범위 내에 있는지 확인
                    if abs(other_price - reference_price) / reference_price * 100 <= tolerance_pct:
                        reactions += 1

                # 2번 이상 테스트된 가격대를 유효한 지지/저항으로 간주
                if reactions >= 2:
                    levels.append(price)

            return levels

        except Exception as e:
            logger.warning(f"테스트된 레벨 계산 중 오류: {str(e)}")
            return []

    def _find_volume_rejection_levels(self, df: pd.DataFrame, is_support: bool = True) -> List[float]:
        """거래량이 많은 구간에서 저항/지지를 받는 가격대를 찾습니다"""
        try:
            if df.empty or len(df) < 10:
                return []

            levels = []
            avg_volume = df["volume"].rolling(window=10).mean()

            # 거래량이 평균 이상인 캔들들 중에서 반전 패턴 찾기
            for i in range(1, len(df) - 1):
                current_volume = df["volume"].iloc[i]
                current_avg_volume = avg_volume.iloc[i]

                if pd.isna(current_avg_volume) or current_volume < current_avg_volume * 1.5:
                    continue

                if is_support:
                    # 지지: 거래량 많은 날에 하락 후 반등
                    prev_close = df["close"].iloc[i - 1]
                    curr_close = df["close"].iloc[i]
                    next_close = df["close"].iloc[i + 1]

                    if (
                        curr_close < prev_close  # 당일 하락
                        and next_close > curr_close
                    ):  # 다음날 반등
                        levels.append(float(curr_close))
                else:
                    # 저항: 거래량 많은 날에 상승 후 반락
                    prev_close = df["close"].iloc[i - 1]
                    curr_close = df["close"].iloc[i]
                    next_close = df["close"].iloc[i + 1]

                    if (
                        curr_close > prev_close  # 당일 상승
                        and next_close < curr_close
                    ):  # 다음날 반락
                        levels.append(float(curr_close))

            return levels

        except Exception as e:
            logger.warning(f"거래량 기반 반응 레벨 계산 중 오류: {str(e)}")
            return []

    def _find_close_based_resistances(self, df: pd.DataFrame) -> List[float]:
        """실제 마감가 기준으로 저항받는 가격대를 찾습니다 (단순 high가 아닌)"""
        try:
            if df.empty or len(df) < 5:
                return []

            resistances = []

            # 상승 후 저항받아 하락하는 패턴 찾기
            for i in range(2, len(df) - 2):
                close_prices = df["close"].iloc[i - 2 : i + 3].values
                high_prices = df["high"].iloc[i - 2 : i + 3].values

                # 현재 봉이 상승 후 저항받는 패턴인지 확인
                if (
                    close_prices[2] > close_prices[1]  # 상승
                    and close_prices[3] < close_prices[2]  # 저항받아 하락
                    and close_prices[4] < close_prices[2]
                ):  # 지속 하락
                    # 윗꼬리가 너무 길면 제외 (실제 마감가 기준 저항)
                    upper_shadow = high_prices[2] - close_prices[2]
                    body_size = abs(close_prices[2] - df["open"].iloc[i])

                    if body_size > 0 and upper_shadow / body_size < 2.0:  # 윗꼬리가 몸통의 2배 이하
                        resistances.append(float(close_prices[2]))

            return resistances

        except Exception as e:
            logger.warning(f"마감가 기반 저항선 계산 중 오류: {str(e)}")
            return []

    def _find_close_based_supports(self, df: pd.DataFrame) -> List[float]:
        """실제 마감가 기준으로 지지받는 가격대를 찾습니다 (단순 low가 아닌)"""
        try:
            if df.empty or len(df) < 5:
                return []

            supports = []

            # 하락 후 지지받아 반등하는 패턴 찾기
            for i in range(2, len(df) - 2):
                close_prices = df["close"].iloc[i - 2 : i + 3].values
                low_prices = df["low"].iloc[i - 2 : i + 3].values

                # 현재 봉이 하락 후 지지받는 패턴인지 확인
                if (
                    close_prices[2] < close_prices[1]  # 하락
                    and close_prices[3] > close_prices[2]  # 지지받아 반등
                    and close_prices[4] > close_prices[2]
                ):  # 지속 상승
                    # 아래꼬리가 너무 길면 제외 (실제 마감가 기준 지지)
                    lower_shadow = close_prices[2] - low_prices[2]
                    body_size = abs(close_prices[2] - df["open"].iloc[i])

                    if body_size > 0 and lower_shadow / body_size < 2.0:  # 아래꼬리가 몸통의 2배 이하
                        supports.append(float(close_prices[2]))

            return supports

        except Exception as e:
            logger.warning(f"마감가 기반 지지선 계산 중 오류: {str(e)}")
            return []

    def _analyze_trend(self, close: pd.Series) -> Tuple[str, str]:
        """추세 방향과 강도를 분석합니다."""
        try:
            if len(close) < 20:
                return "불명확", "약함"

            # 단기, 중기 이동평균
            sma_5 = close.rolling(5).mean()
            sma_20 = close.rolling(20).mean()

            # 현재 가격과 이동평균 비교 (numpy 타입을 Python 타입으로 변환)
            current_price = float(close.iloc[-1])
            sma_5_current = float(sma_5.iloc[-1])
            sma_20_current = float(sma_20.iloc[-1])

            # 추세 방향 결정
            if current_price > sma_5_current > sma_20_current:
                direction = "상승"
            elif current_price < sma_5_current < sma_20_current:
                direction = "하락"
            else:
                direction = "횡보"

            # 추세 강도 계산 (가격 변동성 기반)
            price_change_5d = abs((close.iloc[-1] - close.iloc[-5]) / close.iloc[-5]) * 100 if len(close) >= 5 else 0

            if price_change_5d > 5:
                strength = "강함"
            elif price_change_5d > 2:
                strength = "보통"
            else:
                strength = "약함"

            return direction, strength

        except:
            return "불명확", "약함"

    def _identify_chart_patterns(self, df: pd.DataFrame) -> List[str]:
        """차트 패턴을 식별합니다."""
        try:
            patterns = []

            if len(df) < 20:
                return patterns

            close = df["close"]
            high = df["high"]
            low = df["low"]

            # 골든크로스/데드크로스 확인
            if len(close) >= 50:
                sma_20 = close.rolling(20).mean()
                sma_50 = close.rolling(50).mean()

                if sma_20.iloc[-1] > sma_50.iloc[-1] and sma_20.iloc[-2] <= sma_50.iloc[-2]:
                    patterns.append("골든크로스")
                elif sma_20.iloc[-1] < sma_50.iloc[-1] and sma_20.iloc[-2] >= sma_50.iloc[-2]:
                    patterns.append("데드크로스")

            # 상승삼각형/하락삼각형 패턴 (단순화된 버전)
            recent_highs = high.tail(10)
            recent_lows = low.tail(10)

            if len(recent_highs) >= 5:
                # 상승삼각형: 고점은 유지되고 저점이 상승
                high_trend = np.polyfit(range(len(recent_highs)), recent_highs, 1)[0]
                low_trend = np.polyfit(range(len(recent_lows)), recent_lows, 1)[0]

                if abs(high_trend) < 0.5 and low_trend > 0.5:
                    patterns.append("상승삼각형")
                elif abs(low_trend) < 0.5 and high_trend < -0.5:
                    patterns.append("하락삼각형")

            return patterns

        except Exception as e:
            logger.warning(f"차트 패턴 식별 중 오류: {str(e)}")
            return []

    def _analyze_breakout_signals(self, df: pd.DataFrame, support_levels: List[float], resistance_levels: List[float]) -> List[Dict[str, Any]]:
        """돌파 신호를 분석합니다."""
        try:
            logger.info(f"돌파 신호 분석 시작: 지지선 {len(support_levels)}개, 저항선 {len(resistance_levels)}개")
            signals = []

            if df.empty or len(df) < 5:
                logger.warning("데이터가 부족하여 돌파 신호 분석 불가")
                return signals

            close = df["close"]
            volume = df["volume"]
            current_price = float(close.iloc[-1])
            avg_volume = float(volume.tail(20).mean())
            recent_volume = float(volume.iloc[-1])

            # 최근 5일간의 가격 범위 확인 (돌파 확인용)
            recent_prices = close.tail(5)
            recent_high = float(recent_prices.max())
            recent_low = float(recent_prices.min())

            # logger.info(f"현재가: {current_price:.0f}원, 최근5일 고점: {recent_high:.0f}원, 저점: {recent_low:.0f}원")
            # logger.info(f"거래량: 현재={recent_volume:,.0f}, 평균={avg_volume:,.0f}, 배율={recent_volume/avg_volume:.1f}배")

            # 저항선 돌파 또는 접근 확인
            # logger.info(f"저항선 {len(resistance_levels)}개 분석 시작: {[f'{r:.0f}원' for r in resistance_levels]}")
            for i, resistance in enumerate(resistance_levels):
                # logger.debug(f"저항선 {i+1}/{len(resistance_levels)}: {resistance:.0f}원 분석")

                # 현재가가 저항선을 돌파한 경우 (0.5% 돌파)
                if current_price > resistance * 1.005:
                    signal = {
                        "type": "저항선_돌파",
                        "level": float(resistance),
                        "current_price": float(current_price),
                        "volume_confirmation": bool(recent_volume > avg_volume * 1.5),
                    }
                    signals.append(signal)
                    # logger.info(f"저항선 돌파 신호 발견: {resistance:.0f}원 → {current_price:.0f}원 (돌파율: {((current_price/resistance-1)*100):.1f}%)")

                # 최근 고점이 저항선을 돌파했지만 현재는 아래 있는 경우
                elif recent_high > resistance * 1.005 and current_price <= resistance:
                    signal = {
                        "type": "저항선_테스트_후_반락",
                        "level": float(resistance),
                        "current_price": float(current_price),
                        "test_high": float(recent_high),
                        "volume_confirmation": bool(recent_volume > avg_volume * 1.5),
                    }
                    signals.append(signal)
                    # logger.info(f"저항선 테스트 후 반락 신호: {resistance:.0f}원 테스트 고점 {recent_high:.0f}원, 현재가 {current_price:.0f}원")

                # 저항선에 근접한 경우 (10% 이내)
                elif abs(current_price - resistance) / resistance <= 0.10:
                    distance_pct = abs(current_price - resistance) / resistance * 100
                    signal = {
                        "type": "저항선_근접",
                        "level": float(resistance),
                        "current_price": float(current_price),
                        "distance_pct": float(distance_pct),
                        "volume_confirmation": bool(recent_volume > avg_volume * 1.5),
                    }
                    signals.append(signal)
                    # logger.info(f"저항선 근접 신호: {resistance:.0f}원에 {distance_pct:.1f}% 거리로 근접")
                else:
                    # 조건에 맞지 않는 경우도 로그
                    distance_pct = abs(current_price - resistance) / resistance * 100
                    # logger.debug(f"저항선 {resistance:.0f}원: 조건 미충족 (거리: {distance_pct:.1f}%)")

            # 지지선 이탈 또는 접근 확인
            # logger.info(f"지지선 {len(support_levels)}개 분석 시작: {[f'{s:.0f}원' for s in support_levels]}")
            for i, support in enumerate(support_levels):
                # logger.debug(f"지지선 {i+1}/{len(support_levels)}: {support:.0f}원 분석")

                # 현재가가 지지선을 이탈한 경우 (0.5% 이탈)
                if current_price < support * 0.995:
                    signal = {"type": "지지선_이탈", "level": float(support), "current_price": float(current_price), "volume_confirmation": bool(recent_volume > avg_volume * 1.5)}
                    signals.append(signal)
                    logger.info(f"지지선 이탈 신호 발견: {support:.0f}원 → {current_price:.0f}원 (이탈율: {((1 - current_price / support) * 100):.1f}%)")

                # 최근 저점이 지지선을 이탈했지만 현재는 위에 있는 경우
                elif recent_low < support * 0.995 and current_price >= support:
                    signal = {
                        "type": "지지선_테스트_후_반등",
                        "level": float(support),
                        "current_price": float(current_price),
                        "test_low": float(recent_low),
                        "volume_confirmation": bool(recent_volume > avg_volume * 1.5),
                    }
                    signals.append(signal)
                    logger.info(f"지지선 테스트 후 반등 신호: {support:.0f}원 테스트 저점 {recent_low:.0f}원, 현재가 {current_price:.0f}원")

                # 지지선에 근접한 경우 (15% 이내)
                elif abs(current_price - support) / support <= 0.15:
                    distance_pct = abs(current_price - support) / support * 100
                    signal = {
                        "type": "지지선_근접",
                        "level": float(support),
                        "current_price": float(current_price),
                        "distance_pct": float(distance_pct),
                        "volume_confirmation": bool(recent_volume > avg_volume * 1.5),
                    }
                    signals.append(signal)
                    # logger.info(f"지지선 근접 신호: {support:.0f}원에 {distance_pct:.1f}% 거리로 근접")
                else:
                    # 조건에 맞지 않는 경우도 로그
                    distance_pct = abs(current_price - support) / support * 100
                    # logger.debug(f"지지선 {support:.0f}원: 조건 미충족 (거리: {distance_pct:.1f}%)")

            # logger.info(f"돌파 신호 분석 완료: 총 {len(signals)}개 신호 발견")
            for i, signal in enumerate(signals):
                logger.info(f"  신호 {i + 1}: {signal['type']} - {signal['level']:.0f}원")

            return signals

        except Exception as e:
            logger.warning(f"돌파 신호 분석 중 오류: {str(e)}")
            return []

    def _generate_trading_signals(self, df: pd.DataFrame, technical_indicators: TechnicalIndicators) -> TradingSignals:
        """
        기술적 지표를 바탕으로 매매 신호를 생성합니다.

        Args:
            df: 주가 DataFrame
            technical_indicators: 기술적 지표 결과

        Returns:
            매매 신호 분석 결과
        """
        try:
            signals = []
            entry_points = []
            exit_points = []

            if df.empty:
                return {"overall_signal": "중립", "confidence": 0.0, "signals": [], "entry_points": [], "exit_points": [], "stop_loss": None, "target_price": None}

            float(df["close"].iloc[-1])

            # 추세추종 지표 먼저 분석 (추세 방향 파악)
            adx = technical_indicators.get("adx")
            adx_plus_di = technical_indicators.get("adx_plus_di")
            adx_minus_di = technical_indicators.get("adx_minus_di")
            supertrend_direction = technical_indicators.get("supertrend_direction")

            # 추세 상태 판단
            trend_strength = "약함"
            trend_direction = "중립"

            if adx is not None:
                if adx >= 25:
                    trend_strength = "강함"
                    if adx_plus_di is not None and adx_minus_di is not None:
                        if adx_plus_di > adx_minus_di:
                            trend_direction = "상승"
                        else:
                            trend_direction = "하락"
                elif adx >= 20:
                    trend_strength = "보통"
                else:
                    trend_strength = "약함"

            # 슈퍼트렌드로 추세 방향 보완
            if supertrend_direction is not None:
                if supertrend_direction == 1:
                    trend_direction = "상승" if trend_direction == "중립" else trend_direction
                elif supertrend_direction == -1:
                    trend_direction = "하락" if trend_direction == "중립" else trend_direction

            # RSI 신호 분석 (추세 상태에 따라 조정)
            rsi = technical_indicators.get("rsi")
            if rsi is not None:
                if trend_strength == "강함":
                    # 강한 추세 중에는 RSI 기준을 완화
                    if trend_direction == "상승":
                        # 상승추세에서는 RSI > 30일 때만 매수 고려
                        if rsi < 40:
                            signals.append({"indicator": "RSI", "signal": "매수", "strength": 0.6, "value": rsi, "reason": "상승추세 중 과매도"})
                        elif rsi > 80:
                            signals.append({"indicator": "RSI", "signal": "매도", "strength": 0.4, "value": rsi, "reason": "상승추세 중 극도과매수"})
                        else:
                            signals.append({"indicator": "RSI", "signal": "중립", "strength": 0.2, "value": rsi, "reason": "상승추세 중 정상범위"})
                    elif trend_direction == "하락":
                        # 하락추세에서는 RSI < 70일 때만 매도 고려
                        if rsi > 60:
                            signals.append({"indicator": "RSI", "signal": "매도", "strength": 0.6, "value": rsi, "reason": "하락추세 중 과매수"})
                        elif rsi < 20:
                            signals.append({"indicator": "RSI", "signal": "매수", "strength": 0.4, "value": rsi, "reason": "하락추세 중 극도과매도"})
                        else:
                            signals.append({"indicator": "RSI", "signal": "중립", "strength": 0.2, "value": rsi, "reason": "하락추세 중 정상범위"})
                    else:
                        # 강한 추세이지만 방향 불명확
                        if rsi < 25:
                            signals.append({"indicator": "RSI", "signal": "매수", "strength": 0.5, "value": rsi, "reason": "극도과매도"})
                        elif rsi > 75:
                            signals.append({"indicator": "RSI", "signal": "매도", "strength": 0.5, "value": rsi, "reason": "극도과매수"})
                        else:
                            signals.append({"indicator": "RSI", "signal": "중립", "strength": 0.3, "value": rsi, "reason": "중립"})
                else:
                    # 약한 추세나 횡보 시에는 전통적인 RSI 신호 활용
                    if rsi < 30:
                        signals.append({"indicator": "RSI", "signal": "매수", "strength": 0.8, "value": rsi, "reason": "과매도"})
                    elif rsi > 70:
                        signals.append({"indicator": "RSI", "signal": "매도", "strength": 0.8, "value": rsi, "reason": "과매수"})
                    else:
                        signals.append({"indicator": "RSI", "signal": "중립", "strength": 0.3, "value": rsi, "reason": "중립"})

            # ADX 추세강도 신호 (80 이상은 극도로 강한 추세로 반전 위험 고려)
            if adx is not None:
                if adx >= 80:
                    # 극도로 강한 추세 - 과도한 추세로 반전 가능성 높음, 매우 보수적 접근
                    if trend_direction == "상승":
                        signals.append({"indicator": "ADX", "signal": "매수", "strength": 0.1, "value": adx, "reason": f"극도 상승추세, 반전 위험 (ADX: {adx:.1f})"})
                    elif trend_direction == "하락":
                        signals.append({"indicator": "ADX", "signal": "매도", "strength": 0.1, "value": adx, "reason": f"극도 하락추세, 반전 위험 (ADX: {adx:.1f})"})
                    else:
                        signals.append({"indicator": "ADX", "signal": "중립", "strength": 0.6, "value": adx, "reason": f"극도 강한 추세, 방향 불명확 (ADX: {adx:.1f})"})
                elif adx >= 60:
                    # 매우 강한 추세 - 보수적 접근
                    if trend_direction == "상승":
                        signals.append({"indicator": "ADX", "signal": "매수", "strength": 0.4, "value": adx, "reason": f"매우 강한 상승추세, 조심스러운 진입 (ADX: {adx:.1f})"})
                    elif trend_direction == "하락":
                        signals.append({"indicator": "ADX", "signal": "매도", "strength": 0.4, "value": adx, "reason": f"매우 강한 하락추세, 조심스러운 진입 (ADX: {adx:.1f})"})
                    else:
                        signals.append({"indicator": "ADX", "signal": "중립", "strength": 0.4, "value": adx, "reason": f"매우 강한 추세이나 방향 불명확 (ADX: {adx:.1f})"})
                elif adx >= 40:
                    # 강한 추세 - 일반적인 접근
                    if trend_direction == "상승":
                        signals.append({"indicator": "ADX", "signal": "매수", "strength": 0.6, "value": adx, "reason": f"강한 상승추세 (ADX: {adx:.1f})"})
                    elif trend_direction == "하락":
                        signals.append({"indicator": "ADX", "signal": "매도", "strength": 0.6, "value": adx, "reason": f"강한 하락추세 (ADX: {adx:.1f})"})
                    else:
                        signals.append({"indicator": "ADX", "signal": "중립", "strength": 0.4, "value": adx, "reason": f"강한 추세이나 방향 불명확 (ADX: {adx:.1f})"})
                elif adx >= 25:
                    # 추세 확인 - 적극적 접근 가능
                    if trend_direction == "상승":
                        signals.append({"indicator": "ADX", "signal": "매수", "strength": 0.7, "value": adx, "reason": f"상승추세 확인 (ADX: {adx:.1f})"})
                    elif trend_direction == "하락":
                        signals.append({"indicator": "ADX", "signal": "매도", "strength": 0.7, "value": adx, "reason": f"하락추세 확인 (ADX: {adx:.1f})"})
                    else:
                        signals.append({"indicator": "ADX", "signal": "중립", "strength": 0.4, "value": adx, "reason": f"추세 확인되나 방향 불명확 (ADX: {adx:.1f})"})
                elif adx >= 20:
                    if trend_direction == "상승":
                        signals.append({"indicator": "ADX", "signal": "매수", "strength": 0.5, "value": adx, "reason": f"보통 상승추세 (ADX: {adx:.1f})"})
                    elif trend_direction == "하락":
                        signals.append({"indicator": "ADX", "signal": "매도", "strength": 0.5, "value": adx, "reason": f"보통 하락추세 (ADX: {adx:.1f})"})
                    else:
                        signals.append({"indicator": "ADX", "signal": "중립", "strength": 0.3, "value": adx, "reason": f"보통 추세 (ADX: {adx:.1f})"})
                else:
                    signals.append({"indicator": "ADX", "signal": "중립", "strength": 0.5, "value": adx, "reason": f"약한 추세/횡보 (ADX: {adx:.1f})"})

            # 슈퍼트렌드 신호
            if supertrend_direction is not None:
                if supertrend_direction == 1:
                    strength = 0.7 if trend_strength == "강함" else 0.5
                    signals.append({"indicator": "슈퍼트렌드", "signal": "매수", "strength": strength, "value": supertrend_direction, "reason": "상승추세 확인"})
                elif supertrend_direction == -1:
                    strength = 0.7 if trend_strength == "강함" else 0.5
                    signals.append({"indicator": "슈퍼트렌드", "signal": "매도", "strength": strength, "value": supertrend_direction, "reason": "하락추세 확인"})

            # MACD 신호 분석 (모멘텀 확인용, 추세와 일치할 때 가중치 증가)
            macd = technical_indicators.get("macd")
            macd_signal = technical_indicators.get("macd_signal")
            macd_histogram = technical_indicators.get("macd_histogram")

            if macd is not None and macd_signal is not None:
                if macd > macd_signal and macd_histogram is not None and macd_histogram > 0:
                    # MACD 상승교차가 추세와 일치하는지 확인
                    strength = 0.7 if trend_direction == "상승" else 0.4
                    reason = "상승교차 (추세일치)" if trend_direction == "상승" else "상승교차"
                    signals.append({"indicator": "MACD", "signal": "매수", "strength": strength, "value": macd, "reason": reason})
                elif macd < macd_signal and macd_histogram is not None and macd_histogram < 0:
                    # MACD 하락교차가 추세와 일치하는지 확인
                    strength = 0.7 if trend_direction == "하락" else 0.4
                    reason = "하락교차 (추세일치)" if trend_direction == "하락" else "하락교차"
                    signals.append({"indicator": "MACD", "signal": "매도", "strength": strength, "value": macd, "reason": reason})
                else:
                    signals.append({"indicator": "MACD", "signal": "중립", "strength": 0.3, "value": macd, "reason": "중립"})

            # 종합 신호 계산
            buy_strength = sum([s["strength"] for s in signals if s["signal"] == "매수"])
            sell_strength = sum([s["strength"] for s in signals if s["signal"] == "매도"])
            neutral_strength = sum([s["strength"] for s in signals if s["signal"] == "중립"])

            total_strength = buy_strength + sell_strength + neutral_strength
            confidence = max(buy_strength, sell_strength) / total_strength if total_strength > 0 else 0

            if buy_strength > sell_strength + 0.5:
                overall_signal = "강력매수" if buy_strength > 2.5 else "매수"
            elif sell_strength > buy_strength + 0.5:
                overall_signal = "강력매도" if sell_strength > 2.5 else "매도"
            else:
                overall_signal = "중립"

            # 손절가 및 목표가 계산
            stop_loss = None
            target_price = None

            # if overall_signal in ["매수", "강력매수"]:
            #     stop_loss = current_price * 0.95
            #     target_price = current_price * (1.1 if overall_signal == "매수" else 1.15)
            #     entry_points.append(current_price)
            # elif overall_signal in ["매도", "강력매도"]:
            #     target_price = current_price * (0.95 if overall_signal == "매도" else 0.9)
            #     exit_points.append(current_price)

            return {
                "overall_signal": overall_signal,
                "confidence": round(confidence, 2),
                "signals": signals,
                "entry_points": entry_points,
                "exit_points": exit_points,
                "stop_loss": stop_loss,
                "target_price": target_price,
            }

        except Exception as e:
            logger.error(f"매매 신호 생성 중 오류: {str(e)}")
            return {"overall_signal": "중립", "confidence": 0.0, "signals": [], "entry_points": [], "exit_points": [], "stop_loss": None, "target_price": None}

    def _analyze_market_sentiment(self, df: pd.DataFrame, supply_demand_data: Optional[Dict[str, Any]]) -> MarketSentiment:
        """
        시장 정서를 분석합니다.
        """
        try:
            if df.empty:
                return {"volume_trend": "보통", "price_volume_relation": "중립", "foreign_flow": None, "institution_flow": None}

            # 거래량 추이 분석
            volume = df["volume"]
            if len(volume) >= 20:
                recent_volume = volume.tail(5).mean()
                avg_volume = volume.tail(20).mean()

                if recent_volume > avg_volume * 1.2:
                    volume_trend = "증가"
                elif recent_volume < avg_volume * 0.8:
                    volume_trend = "감소"
                else:
                    volume_trend = "보통"
            else:
                volume_trend = "보통"

            return {"volume_trend": volume_trend, "price_volume_relation": "중립", "foreign_flow": None, "institution_flow": None}

        except Exception as e:
            logger.error(f"시장 정서 분석 중 오류: {str(e)}")
            return {"volume_trend": "보통", "price_volume_relation": "중립", "foreign_flow": None, "institution_flow": None}

    async def _generate_analysis_summary(
        self,
        stock_name: str,
        technical_indicators: TechnicalIndicators,
        chart_patterns: ChartPatternAnalysis,
        trading_signals: TradingSignals,
        market_sentiment: MarketSentiment,
        rs_data: Optional[Dict[str, Any]],
        stock_info: Optional[Dict[str, Any]],
        query: str,
        user_id: Optional[str],
    ) -> str:
        """
        LLM을 사용하여 기술적 분석 종합 요약을 생성합니다.
        """
        try:
            # 종목 기본 정보 추가
            stock_basic_info = ""
            if stock_info:
                market = stock_info.get("market", "N/A")
                sector = stock_info.get("sector", "N/A")
                stock_basic_info = f"""
종목 기본 정보:
- 소속 시장: {market}
- 업종: {sector}
"""

            # RS 데이터 정보 추가 (시장 비교 포함)
            rs_info = ""
            if rs_data:
                # 기본 RS 정보
                rs_info = f"""
RS(상대강도) 정보:
- 현재 RS: {rs_data.get("rs", "N/A")}
- RS 1개월: {rs_data.get("rs_1m", "N/A")}
- RS 3개월: {rs_data.get("rs_3m", "N/A")}
- 업종: {rs_data.get("sector", "N/A")}
- MMT: {rs_data.get("mmt", "N/A")}
"""

                # 시장 비교 정보 추가
                market_comparison = rs_data.get("market_comparison", {})
                if market_comparison:
                    market_code = market_comparison.get("market_code")
                    market_rs = market_comparison.get("market_rs")
                    market_rs_1m = market_comparison.get("market_rs_1m")
                    market_rs_3m = market_comparison.get("market_rs_3m")
                    market_rs_6m = market_comparison.get("market_rs_6m")

                    if market_code and market_rs is not None:
                        rs_info += f"""
시장 지수 비교:
- {market_code} RS: {market_rs} (1M: {market_rs_1m or "N/A"}, 3M: {market_rs_3m or "N/A"}, 6M: {market_rs_6m or "N/A"})
"""

                # 상대적 강도 분석 추가
                relative_analysis = rs_data.get("relative_strength_analysis", {})
                if relative_analysis:
                    vs_market = relative_analysis.get("vs_market")
                    if vs_market:
                        market_name = vs_market.get("market_name", "시장")
                        strength_level = vs_market.get("strength_level", "N/A")
                        difference = vs_market.get("difference", 0)
                        rs_info += f"""
시장 대비 분석: {market_name} 대비 {strength_level} ({"+" if difference >= 0 else ""}{difference})
"""

            # 추세추종 지표 정보 추가
            trend_indicators_info = ""

            # ADX 정보
            adx = technical_indicators.get("adx")
            adx_plus_di = technical_indicators.get("adx_plus_di")
            adx_minus_di = technical_indicators.get("adx_minus_di")
            if adx is not None:
                trend_strength = "강한 추세" if adx >= 25 else "약한 추세" if adx <= 20 else "보통 추세"
                plus_di_str = f"{adx_plus_di:.2f}" if adx_plus_di is not None else "N/A"
                minus_di_str = f"{adx_minus_di:.2f}" if adx_minus_di is not None else "N/A"
                trend_indicators_info += f"""
ADX (추세강도 지표):
- ADX: {adx:.2f} ({trend_strength})
- +DI: {plus_di_str}
- -DI: {minus_di_str}
"""

            # ADR 정보
            adr = technical_indicators.get("adr")
            adr_ma = technical_indicators.get("adr_ma")
            if adr is not None:
                adr_ma_str = f"{adr_ma:.2f}" if adr_ma is not None else "N/A"
                # ADR은 변동성 지표이므로 높을수록 변동성이 크다
                volatility_level = "높은 변동성" if adr > adr_ma * 1.2 else "낮은 변동성" if adr < adr_ma * 0.8 else "보통 변동성"
                trend_indicators_info += f"""
ADR (Average Daily Range - 일중 평균 변동폭):
- ADR: {adr:.0f}원 ({volatility_level})
- ADR 이동평균: {adr_ma_str}원
"""

            # 슈퍼트렌드 정보
            supertrend = technical_indicators.get("supertrend")
            supertrend_direction = technical_indicators.get("supertrend_direction")
            if supertrend is not None:
                trend_signal = "상승추세" if supertrend_direction == 1 else "하락추세" if supertrend_direction == -1 else "중립"
                trend_indicators_info += f"""
슈퍼트렌드:
- 현재값: {supertrend:,.0f}원
- 추세방향: {trend_signal}
"""

            prompt = f"""
당신은 전문 기술적 분석가입니다. {stock_name}의 기술적 분석 결과를 바탕으로 종합적인 분석 요약을 작성해주세요.

{stock_basic_info}

기본 기술적 지표:
- RSI: {technical_indicators.get("rsi", "N/A")}
- MACD: {technical_indicators.get("macd", "N/A")}
- 종합 매매 신호: {trading_signals.get("overall_signal", "N/A")}

추세추종 지표:{trend_indicators_info}

{rs_info}

사용자 질문: {query}

다음 지표들의 의미:
- RS(상대강도): 시장 대비 주식의 상대적 강도를 나타내며, 높을수록 시장을 아웃퍼폼
- ADX: 25 이상이면 강한 추세, 20 이하면 약한 추세
- ADR: 일중 평균 변동폭을 나타내며, 높을수록 변동성이 크고, 낮을수록 변동성이 작음
- 슈퍼트렌드: 추세 변화를 감지하는 지표

분석 시 고려사항:
1. 종목이 소속된 시장(코스피/코스닥)의 특성을 고려하여 분석하세요.
2. 시장별 상대강도 분석 결과가 있다면 이를 적극 활용하세요.
3. 추세추종 지표들과 시장 소속정보를 종합하여 투자 관점을 제시하세요.

추세추종 지표들(ADX, ADR, 슈퍼트렌드)과 시장별 RS 분석을 중심으로 현재 추세 상황과 투자 시사점을 3-4문장으로 간결하게 설명해주세요.
"""

            response = await self.agent_llm.ainvoke_with_fallback(prompt, project_type=ProjectType.STOCKEASY, user_id=user_id, db=self.db)

            return response.content

        except Exception as e:
            logger.error(f"분석 요약 생성 중 오류: {str(e)}")
            return f"{stock_name}의 기술적 분석을 완료했습니다. 종합 매매 신호는 '{trading_signals.get('overall_signal', '중립')}'입니다."

    async def _generate_recommendations(
        self, stock_name: str, technical_indicators: TechnicalIndicators, trading_signals: TradingSignals, rs_data: Optional[Dict[str, Any]], user_id: Optional[str]
    ) -> List[str]:
        """
        투자 권고사항을 생성합니다.
        """
        try:
            recommendations = []

            overall_signal = trading_signals.get("overall_signal", "중립")
            trading_signals.get("confidence", 0)

            # 기본 매매 신호 추천
            if overall_signal == "강력매수":
                recommendations.append("강력한 매수 신호가 확인되었습니다.")
            elif overall_signal == "매수":
                recommendations.append("매수 신호가 나타났습니다.")
            elif overall_signal == "매도":
                recommendations.append("매도 신호가 확인되었습니다.")
            else:
                recommendations.append("현재 중립적 상황입니다.")

            # RS 데이터 기반 추가 권고사항 (향상된 분석)
            if rs_data:
                rs_value = rs_data.get("rs")
                rs_data.get("rs_1m")

                # 기본 RS 수준 분석
                if rs_value is not None:
                    try:
                        rs_float = float(rs_value)
                        if rs_float >= 80:
                            recommendations.append(f"RS(상대강도)가 {rs_float}로 매우 높아 시장 대비 강세를 보이고 있습니다.")
                        elif rs_float >= 60:
                            recommendations.append(f"RS(상대강도)가 {rs_float}로 양호하여 시장 대비 우수한 성과를 보이고 있습니다.")
                        elif rs_float <= 20:
                            recommendations.append(f"RS(상대강도)가 {rs_float}로 낮아 시장 대비 약세를 보이고 있으므로 주의가 필요합니다.")
                        elif rs_float <= 40:
                            recommendations.append(f"RS(상대강도)가 {rs_float}로 평균 이하이며 시장 대비 부진한 모습입니다.")
                    except (ValueError, TypeError):
                        pass

                # 시장 대비 상대강도 분석
                relative_analysis = rs_data.get("relative_strength_analysis", {})
                if relative_analysis:
                    vs_market = relative_analysis.get("vs_market")
                    if vs_market:
                        market_name = vs_market.get("market_name", "시장")
                        outperforming = vs_market.get("outperforming", False)
                        strength_level = vs_market.get("strength_level", "")
                        market_rs = vs_market.get("market_rs")

                        if outperforming:
                            recommendations.append(f"{market_name}({market_rs}) 대비 상대적 우위를 보이고 있습니다. ({strength_level})")
                        else:
                            recommendations.append(f"{market_name}({market_rs}) 대비 상대적으로 부진한 모습입니다. ({strength_level})")

                        # 트렌드 분석
                        vs_market.get("overall_trend")
                        vs_market.get("trends", {})

                        # RS 트렌드 제거
                        # if overall_trend == 'improving':
                        #     improving_periods = [period for period, trend in trends.items() if trend == 'improving']
                        #     if improving_periods:
                        #         recommendations.append(f"{market_name} 대비 상대강도가 {', '.join(improving_periods)} 기간에서 개선되는 추세입니다.")
                        # elif overall_trend == 'weakening':
                        #     weakening_periods = [period for period, trend in trends.items() if trend == 'weakening']
                        #     if weakening_periods:
                        #         recommendations.append(f"{market_name} 대비 상대강도가 {', '.join(weakening_periods)} 기간에서 약화되는 추세입니다.")

                    # 시장별 특화 분석 기반 권고
                    market_analysis = relative_analysis.get("market_specific_analysis")
                    if market_analysis:
                        market_recommendation = market_analysis.get("recommendation")
                        if market_recommendation:
                            recommendations.append(market_recommendation)

                # 업종 정보 추가
                sector = rs_data.get("sector")
                if sector:
                    recommendations.append(f"{sector} 섹터의 동향도 함께 고려하시기 바랍니다.")

            # 공통 권고사항
            # recommendations.append("분할 매수/매도를 통해 리스크를 관리하세요.")
            recommendations.append("손절선을 미리 설정하고 계획적인 매수/매도를 하세요.")

            return recommendations

        except Exception as e:
            logger.error(f"투자 권고사항 생성 중 오류: {str(e)}")
            return [f"{stock_name}에 대한 기술적 분석을 참고하여 신중한 투자 결정을 내리시기 바랍니다."]

    async def _create_preliminary_chart_components(self, technical_analysis_result: TechnicalAnalysisResult, stock_code: str, stock_name: str) -> List[Dict[str, Any]]:
        """
        기술적 분석 결과를 사용하여 차트 컴포넌트들을 생성합니다.
        preliminary_chart 이벤트를 위한 즉시 전송용 컴포넌트들입니다.
        """
        components = []

        try:
            logger.info(f"차트 컴포넌트 생성 시작: {stock_name}({stock_code})")

            # candle_data 생성
            candle_data = self._create_candle_data(technical_analysis_result)
            if not candle_data:
                logger.warning(f"캔들 데이터가 없습니다: {stock_name}({stock_code})")
                return components

            logger.info(f"캔들 데이터 생성 완료: {stock_name}({stock_code}), 데이터 개수: {len(candle_data)}")

            # tech_agent_result 형식으로 변환
            tech_agent_result = {"data": technical_analysis_result, "agent_name": "technical_analyzer", "status": "success", "error": None}

            # 주가차트 컴포넌트 생성
            price_chart_component = create_price_chart_component_directly(tech_agent_result, stock_code, stock_name)
            if price_chart_component:
                components.append(price_chart_component)
                logger.info(f"주가차트 컴포넌트 생성 완료: {stock_name}({stock_code})")

            # 추세추종 지표 차트 컴포넌트 생성
            trend_following_chart_component = create_trend_following_chart_component_directly(tech_agent_result, stock_code, stock_name)
            if trend_following_chart_component:
                components.append(trend_following_chart_component)
                logger.info(f"추세추종 차트 컴포넌트 생성 완료: {stock_name}({stock_code})")

            # 모멘텀 지표 차트 컴포넌트 생성
            momentum_chart_component = create_momentum_chart_component_directly(tech_agent_result, stock_code, stock_name)
            if momentum_chart_component:
                components.append(momentum_chart_component)
                logger.info(f"모멘텀 차트 컴포넌트 생성 완료: {stock_name}({stock_code})")

            logger.info(f"전체 차트 컴포넌트 생성 완료: {stock_name}({stock_code}), 총 {len(components)}개")

        except Exception as e:
            logger.error(f"차트 컴포넌트 생성 중 오류 발생: {stock_name}({stock_code})")
            logger.error(f"오류 내용: {str(e)}")
            logger.exception("차트 컴포넌트 생성 중 예외 발생")

        return components

    def _create_candle_data(self, technical_analysis_result: TechnicalAnalysisResult) -> List[Dict[str, Any]]:
        """
        chart_data를 사용하여 캔들 데이터를 생성합니다.
        chart_data는 list[dict] 형태이며, 각 dict의 'date' 필드를 ISO 형식에서 yyyy-mm-dd로 변환합니다.
        """
        candle_data = []
        chart_data = technical_analysis_result.get("chart_data", [])

        if not chart_data or not isinstance(chart_data, list):
            logger.warning("chart_data가 비어있거나 올바른 형태가 아닙니다.")
            return candle_data

        for item in chart_data:
            try:
                # 'date' 필드의 ISO 시간 문자열을 yyyy-mm-dd 형식으로 변환
                date_value = item.get("date")
                if not date_value:
                    logger.warning(f"날짜 정보가 없는 데이터: {item}")
                    continue

                # ISO 형식 (2024-06-19T00:00:00+09:00)을 yyyy-mm-dd로 변환
                normalized_date = format_date_for_chart(date_value)

                candle_data.append(
                    {
                        "time": normalized_date,
                        "open": safe_price_float(item.get("open")),
                        "high": safe_price_float(item.get("high")),
                        "low": safe_price_float(item.get("low")),
                        "close": safe_price_float(item.get("close")),
                        "volume": safe_price_float(item.get("volume")),
                    }
                )
            except Exception as e:
                logger.warning(f"캔들 데이터 생성 중 오류: {item}, 오류: {str(e)}")
                continue

        logger.info(f"캔들 데이터 생성 완료: {len(candle_data)}개")
        return candle_data
