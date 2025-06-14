"""
기술적 분석 에이전트 모듈

이 모듈은 stock-data-collector API를 통해 주가 데이터를 수집하고,
기술적 지표, 차트 패턴, 매매 신호 등을 분석하는 TechnicalAnalyzerAgent 클래스를 구현합니다.
"""

import json
import asyncio
import aiohttp
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
from loguru import logger
import numpy as np
import pandas as pd

from stockeasy.agents.base import BaseAgent
from stockeasy.models.agent_io import (
    AgentState, 
    TechnicalAnalysisResult,
    TechnicalIndicators,
    ChartPatternAnalysis,
    TradingSignals,
    MarketSentiment
)
from common.models.token_usage import ProjectType
from common.services.agent_llm import get_agent_llm
from common.core.config import settings


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
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30)
        )
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
            
            # 기술적 분석 데이터 요구사항 확인
            data_requirements = state.get("question_analysis", {}).get("data_requirements", {})
            if not data_requirements.get("technical_analysis_needed", False):
                logger.info("기술적 분석이 필요하지 않습니다. 건너뜁니다.")
                return state
            
            # 사용자 컨텍스트 추출
            user_context = state.get("user_context", {})
            user_id = user_context.get("user_id", None)
            
            logger.info(f"종목 {stock_name}({stock_code})에 대한 기술적 분석 수행")
            
            # 기술적 분석 수행
            async with self:
                technical_analysis_result = await self._perform_technical_analysis(
                    stock_code, stock_name, query, user_id
                )
            
            # 결과를 상태에 저장
            state["agent_results"] = state.get("agent_results", {})
            state["agent_results"]["technical_analyzer"] = {
                "agent_name": "technical_analyzer",
                "status": "success",
                "data": technical_analysis_result,
                "error": None,
                "execution_time": (datetime.now() - start_time).total_seconds(),
                "metadata": {
                    "stock_code": stock_code,
                    "stock_name": stock_name,
                    "analysis_date": datetime.now()
                }
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
                "model_name": self.agent_llm.get_model_name()
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
    
    async def _perform_technical_analysis(
        self, 
        stock_code: str, 
        stock_name: str, 
        query: str, 
        user_id: Optional[str]
    ) -> TechnicalAnalysisResult:
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
        
        # 1. 주가 데이터 수집
        logger.info("주가/수급 데이터 수집 중...")
        chart_data = await self._fetch_chart_data(stock_code, period="1y", interval="1d")
        if not chart_data:
            raise Exception("주가 데이터를 가져올 수 없습니다.")
        
        # 2. 수급 데이터 수집
        supply_demand_data = await self._fetch_supply_demand_data(stock_code)
        
        # 3. 시장지수 데이터 수집
        market_indices = await self._fetch_market_indices()
        
        # 4. 데이터를 DataFrame으로 변환
        df = self._convert_to_dataframe(chart_data)
        
        # 5. 기술적 지표 계산
        logger.info("기술적 지표 계산 중...")
        technical_indicators = self._calculate_technical_indicators(df)
        
        # 6. 차트 패턴 분석
        logger.info("차트 패턴 분석 중...")
        chart_patterns = self._analyze_chart_patterns(df)
        
        # 7. 매매 신호 생성
        logger.info("매매 신호 생성 중...")
        trading_signals = self._generate_trading_signals(df, technical_indicators)
        
        # 8. 시장 정서 분석
        logger.info("시장 정서 분석 중...")
        market_sentiment = self._analyze_market_sentiment(df, supply_demand_data)
        
        # 9. LLM을 사용한 종합 분석
        logger.info("LLM을 사용한 종합 분석 중...")
        summary = await self._generate_analysis_summary(
            stock_name, technical_indicators, chart_patterns, 
            trading_signals, market_sentiment, query, user_id
        )
        
        # 10. 투자 권고사항 생성
        logger.info("투자 권고사항 생성 중...")
        recommendations = await self._generate_recommendations(
            stock_name, technical_indicators, trading_signals, user_id
        )
        
        # 결과 구성 (numpy 타입을 Python 타입으로 안전하게 변환)
        current_price = float(df['close'].iloc[-1]) if not df.empty else 0.0
        
        return {
            "stock_code": stock_code,
            "stock_name": stock_name,
            "analysis_date": datetime.now(),
            "current_price": float(current_price),
            "chart_patterns": chart_patterns,
            "chart_data": chart_data,
            "supply_demand_data": supply_demand_data,
            "market_indices": market_indices,
            "technical_indicators": technical_indicators,
            "trading_signals": trading_signals,
            "market_sentiment": market_sentiment,
            "summary": summary,
            "recommendations": recommendations
        }
    
    def _add_error(self, state: AgentState, error_message: str) -> None:
        """
        상태 객체에 오류 정보를 추가합니다.
        
        Args:
            state: 상태 객체
            error_message: 오류 메시지
        """
        state["errors"] = state.get("errors", [])
        state["errors"].append({
            "agent": "technical_analyzer",
            "error": error_message,
            "type": "processing_error",
            "timestamp": datetime.now(),
            "context": {
                "stock_code": state.get("stock_code", ""),
                "query": state.get("query", "")
            }
        })
        
        # 처리 상태 업데이트
        state["processing_status"] = state.get("processing_status", {})
        state["processing_status"]["technical_analyzer"] = "failed"
    
    # ========================================
    # 데이터 수집 메서드들 (Phase 2.2)
    # ========================================
    
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
            params = {
                "period": period,
                "interval": interval,
                "compressed": "true"
            }
            
            logger.info(f"주가 데이터 요청: {url}, 파라미터: {params}")
            
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    response_data = await response.json()
                    
                    # 응답 구조 확인
                    if not isinstance(response_data, dict) or 'data' not in response_data:
                        logger.error("잘못된 응답 구조: data 필드가 없습니다.")
                        return None
                    
                    inner_data = response_data['data']
                    
                    # 스키마 필드 순서 확인
                    schema = inner_data.get('schema', {})
                    fields = schema.get('fields', [])
                    
                    if not fields:
                        logger.error("스키마 필드 정보가 없습니다.")
                        return None
                    
                    # 실제 데이터 배열 가져오기
                    data_rows = inner_data.get('data', [])
                    
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
                            if field == 'timestamp':
                                row_dict['date'] = value
                            else:
                                row_dict[field] = value
                        
                        chart_data.append(row_dict)
                    
                    # 최신 5개 데이터 샘플 로깅
                    if chart_data:
                        recent_data = chart_data[-5:] if len(chart_data) >= 5 else chart_data
                        logger.info(f"최신 {len(recent_data)}개 주가 데이터 샘플:")
                        for i, item in enumerate(recent_data, 1):
                            date_val = item.get('date')
                            close_val = item.get('close')
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
            params = {
                "start_date": start_date.strftime("%Y%m%d"),
                "end_date": end_date.strftime("%Y%m%d"),
                "compressed": "true"
            }
            
            logger.info(f"수급 데이터 요청: {url}, 파라미터: {params}")
            
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    response_data = await response.json()
                    
                    # 응답 구조 확인
                    if not isinstance(response_data, dict) or 'data' not in response_data:
                        logger.error("잘못된 응답 구조: data 필드가 없습니다.")
                        return None
                    
                    inner_data = response_data['data']
                    
                    # 스키마 필드 순서 확인
                    schema = inner_data.get('schema', {})
                    fields = schema.get('fields', [])
                    
                    if not fields:
                        logger.error("스키마 필드 정보가 없습니다.")
                        return None
                    
                    # 실제 데이터 배열 가져오기
                    data_rows = inner_data.get('data', [])
                    
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
                            date_val = item.get('date')
                            individual = item.get('individual_investor')
                            foreign = item.get('foreign_investor')
                            institution = item.get('institution_total')
                            logger.info(f"  {i}. {date_val}: 개인 {individual}, 외국인 {foreign}, 기관 {institution}")
                    
                    return supply_data
                else:
                    logger.warning(f"수급 데이터 요청 실패: HTTP {response.status}")
                    return None
                    
        except Exception as e:
            logger.warning(f"수급 데이터 수집 중 오류: {str(e)}")
            return None
    
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
                    logger.info(f"시장지수 데이터 수신 성공")
                    return data.get('indices', {})
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
            
            # 데이터 변환
            df_data = []
            for item in chart_data:
                df_data.append({
                    'date': pd.to_datetime(item.get('date')),
                    'open': float(item.get('open', 0)),
                    'high': float(item.get('high', 0)),
                    'low': float(item.get('low', 0)),
                    'close': float(item.get('close', 0)),
                    'volume': int(item.get('volume', 0))
                })
            
            df = pd.DataFrame(df_data)
            df.set_index('date', inplace=True)
            df.sort_index(inplace=True)
            
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
            
            close = df['close']
            high = df['high']
            low = df['low']
            volume = df['volume']
            
            # 이동평균선 계산
            sma_20 = close.rolling(window=20).mean().iloc[-1] if len(close) >= 20 else None
            sma_60 = close.rolling(window=60).mean().iloc[-1] if len(close) >= 60 else None
            
            # 지수이동평균 계산
            ema_12 = close.ewm(span=12).mean().iloc[-1] if len(close) >= 12 else None
            ema_26 = close.ewm(span=26).mean().iloc[-1] if len(close) >= 26 else None
            
            # RSI 계산
            rsi = self._calculate_rsi(close) if len(close) >= 14 else None
            
            # MACD 계산
            macd_values = self._calculate_macd(close) if len(close) >= 26 else {}
            
            # 볼린저 밴드 계산
            bollinger = self._calculate_bollinger_bands(close) if len(close) >= 20 else {}
            
            # 스토캐스틱 계산
            stochastic = self._calculate_stochastic(high, low, close) if len(close) >= 14 else {}
            
            # 안전한 float 변환 함수
            def safe_float(value):
                """numpy 타입을 안전하게 Python float로 변환"""
                if value is None:
                    return None
                if pd.isna(value):  # pandas isna로 확인
                    return None
                return float(value)
            
            indicators = {
                "sma_20": safe_float(sma_20),
                "sma_60": safe_float(sma_60),
                "ema_12": safe_float(ema_12),
                "ema_26": safe_float(ema_26),
                "rsi": safe_float(rsi),
                "macd": macd_values.get("macd"),
                "macd_signal": macd_values.get("signal"),
                "macd_histogram": macd_values.get("histogram"),
                "bollinger_upper": bollinger.get("upper"),
                "bollinger_middle": bollinger.get("middle"),
                "bollinger_lower": bollinger.get("lower"),
                "stochastic_k": stochastic.get("k"),
                "stochastic_d": stochastic.get("d")
            }
            
            logger.info(f"기술적 지표 계산 완료")
            return indicators
            
        except Exception as e:
            logger.error(f"기술적 지표 계산 중 오류: {str(e)}")
            return {}
    
    def _calculate_rsi(self, close: pd.Series, period: int = 14) -> Optional[float]:
        """RSI 지표를 계산합니다."""
        try:
            delta = close.diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            return rsi.iloc[-1]
        except:
            return None
    
    def _calculate_macd(self, close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> Dict[str, Optional[float]]:
        """MACD 지표를 계산합니다."""
        try:
            def safe_float(value):
                """numpy 타입을 안전하게 Python float로 변환"""
                if value is None or pd.isna(value):
                    return None
                return float(value)
            
            ema_fast = close.ewm(span=fast).mean()
            ema_slow = close.ewm(span=slow).mean()
            macd = ema_fast - ema_slow
            macd_signal = macd.ewm(span=signal).mean()
            macd_histogram = macd - macd_signal
            
            return {
                "macd": safe_float(macd.iloc[-1]),
                "signal": safe_float(macd_signal.iloc[-1]),
                "histogram": safe_float(macd_histogram.iloc[-1])
            }
        except:
            return {"macd": None, "signal": None, "histogram": None}
    
    def _calculate_bollinger_bands(self, close: pd.Series, period: int = 20, std_dev: int = 2) -> Dict[str, Optional[float]]:
        """볼린저 밴드를 계산합니다."""
        try:
            def safe_float(value):
                """numpy 타입을 안전하게 Python float로 변환"""
                if value is None or pd.isna(value):
                    return None
                return float(value)
            
            sma = close.rolling(window=period).mean()
            std = close.rolling(window=period).std()
            
            upper = sma + (std * std_dev)
            lower = sma - (std * std_dev)
            
            return {
                "upper": safe_float(upper.iloc[-1]),
                "middle": safe_float(sma.iloc[-1]),
                "lower": safe_float(lower.iloc[-1])
            }
        except:
            return {"upper": None, "middle": None, "lower": None}
    
    def _calculate_stochastic(self, high: pd.Series, low: pd.Series, close: pd.Series, k_period: int = 14, d_period: int = 3) -> Dict[str, Optional[float]]:
        """스토캐스틱 지표를 계산합니다."""
        try:
            def safe_float(value):
                """numpy 타입을 안전하게 Python float로 변환"""
                if value is None or pd.isna(value):
                    return None
                return float(value)
            
            lowest_low = low.rolling(window=k_period).min()
            highest_high = high.rolling(window=k_period).max()
            
            k_percent = 100 * ((close - lowest_low) / (highest_high - lowest_low))
            d_percent = k_percent.rolling(window=d_period).mean()
            
            return {
                "k": safe_float(k_percent.iloc[-1]),
                "d": safe_float(d_percent.iloc[-1])
            }
        except:
            return {"k": None, "d": None}
    
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
            
            close = df['close']
            high = df['high']
            low = df['low']
            
            # 지지선/저항선 계산
            support_levels = self._find_support_levels(low)
            resistance_levels = self._find_resistance_levels(high)
            
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
                "breakout_signals": breakout_signals
            }
            
        except Exception as e:
            logger.error(f"차트 패턴 분석 중 오류: {str(e)}")
            return {}
    
    def _find_support_levels(self, low: pd.Series, window: int = 20) -> List[float]:
        """지지선을 찾습니다."""
        try:
            supports = []
            recent_lows = low.tail(window)
            
            # 최근 저점들 중에서 지지선 후보를 찾음
            for i in range(2, len(recent_lows) - 2):
                if (recent_lows.iloc[i] < recent_lows.iloc[i-1] and 
                    recent_lows.iloc[i] < recent_lows.iloc[i+1] and
                    recent_lows.iloc[i] < recent_lows.iloc[i-2] and 
                    recent_lows.iloc[i] < recent_lows.iloc[i+2]):
                    supports.append(float(recent_lows.iloc[i]))
            
            # 중복 제거 및 정렬
            supports = sorted(list(set(supports)))[-3:]  # 최근 3개만
            return supports
            
        except:
            return []
    
    def _find_resistance_levels(self, high: pd.Series, window: int = 20) -> List[float]:
        """저항선을 찾습니다."""
        try:
            resistances = []
            recent_highs = high.tail(window)
            
            # 최근 고점들 중에서 저항선 후보를 찾음
            for i in range(2, len(recent_highs) - 2):
                if (recent_highs.iloc[i] > recent_highs.iloc[i-1] and 
                    recent_highs.iloc[i] > recent_highs.iloc[i+1] and
                    recent_highs.iloc[i] > recent_highs.iloc[i-2] and 
                    recent_highs.iloc[i] > recent_highs.iloc[i+2]):
                    resistances.append(float(recent_highs.iloc[i]))
            
            # 중복 제거 및 정렬
            resistances = sorted(list(set(resistances)), reverse=True)[:3]  # 최근 3개만
            return resistances
            
        except:
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
            
            close = df['close']
            high = df['high']
            low = df['low']
            
            # 골든크로스/데드크로스 확인
            if len(close) >= 50:
                sma_20 = close.rolling(20).mean()
                sma_50 = close.rolling(50).mean()
                
                if (sma_20.iloc[-1] > sma_50.iloc[-1] and 
                    sma_20.iloc[-2] <= sma_50.iloc[-2]):
                    patterns.append("골든크로스")
                elif (sma_20.iloc[-1] < sma_50.iloc[-1] and 
                      sma_20.iloc[-2] >= sma_50.iloc[-2]):
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
            signals = []
            
            if df.empty or len(df) < 5:
                return signals
            
            close = df['close']
            volume = df['volume']
            current_price = float(close.iloc[-1])
            avg_volume = float(volume.tail(20).mean())
            recent_volume = float(volume.iloc[-1])
            
            # 저항선 돌파 확인
            for resistance in resistance_levels:
                if current_price > resistance * 1.01:  # 1% 이상 돌파
                    signals.append({
                        "type": "저항선_돌파",
                        "level": float(resistance),
                        "current_price": float(current_price),
                        "volume_confirmation": bool(recent_volume > avg_volume * 1.5)
                    })
            
            # 지지선 이탈 확인
            for support in support_levels:
                if current_price < support * 0.99:  # 1% 이상 이탈
                    signals.append({
                        "type": "지지선_이탈",
                        "level": float(support),
                        "current_price": float(current_price),
                        "volume_confirmation": bool(recent_volume > avg_volume * 1.5)
                    })
            
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
                return {
                    "overall_signal": "중립",
                    "confidence": 0.0,
                    "signals": [],
                    "entry_points": [],
                    "exit_points": [],
                    "stop_loss": None,
                    "target_price": None
                }
            
            current_price = float(df['close'].iloc[-1])
            
            # RSI 신호 분석
            rsi = technical_indicators.get("rsi")
            if rsi is not None:
                if rsi < 30:
                    signals.append({"indicator": "RSI", "signal": "매수", "strength": 0.8, "value": rsi, "reason": "과매도"})
                elif rsi > 70:
                    signals.append({"indicator": "RSI", "signal": "매도", "strength": 0.8, "value": rsi, "reason": "과매수"})
                else:
                    signals.append({"indicator": "RSI", "signal": "중립", "strength": 0.3, "value": rsi, "reason": "중립"})
            
            # MACD 신호 분석
            macd = technical_indicators.get("macd")
            macd_signal = technical_indicators.get("macd_signal")
            macd_histogram = technical_indicators.get("macd_histogram")
            
            if macd is not None and macd_signal is not None:
                if macd > macd_signal and macd_histogram is not None and macd_histogram > 0:
                    signals.append({"indicator": "MACD", "signal": "매수", "strength": 0.7, "value": macd, "reason": "상승교차"})
                elif macd < macd_signal and macd_histogram is not None and macd_histogram < 0:
                    signals.append({"indicator": "MACD", "signal": "매도", "strength": 0.7, "value": macd, "reason": "하락교차"})
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
            
            if overall_signal in ["매수", "강력매수"]:
                stop_loss = current_price * 0.95
                target_price = current_price * (1.1 if overall_signal == "매수" else 1.15)
                entry_points.append(current_price)
            elif overall_signal in ["매도", "강력매도"]:
                target_price = current_price * (0.95 if overall_signal == "매도" else 0.9)
                exit_points.append(current_price)
            
            return {
                "overall_signal": overall_signal,
                "confidence": round(confidence, 2),
                "signals": signals,
                "entry_points": entry_points,
                "exit_points": exit_points,
                "stop_loss": stop_loss,
                "target_price": target_price
            }
            
        except Exception as e:
            logger.error(f"매매 신호 생성 중 오류: {str(e)}")
            return {
                "overall_signal": "중립",
                "confidence": 0.0,
                "signals": [],
                "entry_points": [],
                "exit_points": [],
                "stop_loss": None,
                "target_price": None
            }

    def _analyze_market_sentiment(self, df: pd.DataFrame, supply_demand_data: Optional[Dict[str, Any]]) -> MarketSentiment:
        """
        시장 정서를 분석합니다.
        """
        try:
            if df.empty:
                return {
                    "volume_trend": "보통",
                    "price_volume_relation": "중립",
                    "foreign_flow": None,
                    "institution_flow": None
                }
            
            # 거래량 추이 분석
            volume = df['volume']
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
            
            return {
                "volume_trend": volume_trend,
                "price_volume_relation": "중립",
                "foreign_flow": None,
                "institution_flow": None
            }
            
        except Exception as e:
            logger.error(f"시장 정서 분석 중 오류: {str(e)}")
            return {
                "volume_trend": "보통",
                "price_volume_relation": "중립", 
                "foreign_flow": None,
                "institution_flow": None
            }

    async def _generate_analysis_summary(
        self, 
        stock_name: str, 
        technical_indicators: TechnicalIndicators, 
        chart_patterns: ChartPatternAnalysis, 
        trading_signals: TradingSignals, 
        market_sentiment: MarketSentiment, 
        query: str, 
        user_id: Optional[str]
    ) -> str:
        """
        LLM을 사용하여 기술적 분석 종합 요약을 생성합니다.
        """
        try:
            prompt = f"""
당신은 전문 기술적 분석가입니다. {stock_name}의 기술적 분석 결과를 바탕으로 종합적인 분석 요약을 작성해주세요.

기술적 지표:
- RSI: {technical_indicators.get('rsi', 'N/A')}
- MACD: {technical_indicators.get('macd', 'N/A')}
- 종합 매매 신호: {trading_signals.get('overall_signal', 'N/A')}

사용자 질문: {query}

3-4문장으로 간결하게 현재 기술적 상황과 투자 시사점을 설명해주세요.
"""
            
            response = await self.agent_llm.ainvoke_with_fallback(
                prompt,
                project_type=ProjectType.STOCKEASY,
                user_id=user_id,
                db=self.db
            )
            
            return response.content
            
        except Exception as e:
            logger.error(f"분석 요약 생성 중 오류: {str(e)}")
            return f"{stock_name}의 기술적 분석을 완료했습니다. 종합 매매 신호는 '{trading_signals.get('overall_signal', '중립')}'입니다."

    async def _generate_recommendations(
        self, 
        stock_name: str, 
        technical_indicators: TechnicalIndicators, 
        trading_signals: TradingSignals, 
        user_id: Optional[str]
    ) -> List[str]:
        """
        투자 권고사항을 생성합니다.
        """
        try:
            recommendations = []
            
            overall_signal = trading_signals.get("overall_signal", "중립")
            confidence = trading_signals.get("confidence", 0)
            
            if overall_signal == "강력매수":
                recommendations.append("강력한 매수 신호가 확인되었습니다.")
            elif overall_signal == "매수":
                recommendations.append("매수 신호가 나타났습니다.")
            elif overall_signal == "매도":
                recommendations.append("매도 신호가 확인되었습니다.")
            else:
                recommendations.append("현재 중립적 상황입니다.")
            
            recommendations.append("분할 매수/매도를 통해 리스크를 관리하세요.")
            recommendations.append("손절선을 미리 설정하고 감정적 거래를 피하세요.")
            
            return recommendations
            
        except Exception as e:
            logger.error(f"투자 권고사항 생성 중 오류: {str(e)}")
            return [f"{stock_name}에 대한 기술적 분석을 참고하여 신중한 투자 결정을 내리시기 바랍니다."] 