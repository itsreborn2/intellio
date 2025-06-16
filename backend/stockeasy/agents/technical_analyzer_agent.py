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
        summary = await self._generate_analysis_summary(
            stock_name, technical_indicators, chart_patterns, 
            trading_signals, market_sentiment, rs_data, stock_info, query, user_id
        )
        
        # 12. 투자 권고사항 생성
        logger.info("투자 권고사항 생성 중...")
        recommendations = await self._generate_recommendations(
            stock_name, technical_indicators, trading_signals, rs_data, user_id
        )
        
        # 결과 구성 (numpy 타입을 Python 타입으로 안전하게 변환)
        current_price = float(df['close'].iloc[-1]) if not df.empty else 0.0
        
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
                    
                    stock_info = response_data.get('data', {})
                    if not stock_info:
                        logger.warning("종목 기본 정보가 비어있습니다.")
                        return None
                    
                    logger.info(f"종목 기본 정보 수신 성공")
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
            market_code = stock_info.get('market') if stock_info else None
            codes_to_fetch = [stock_code]
            
            if market_code in ["KOSPI", "KOSDAQ"]:
                codes_to_fetch.append(market_code)
            else:
                # 시장 정보가 없거나 기타인 경우 KOSPI를 기본으로
                codes_to_fetch.append("KOSPI")
                market_code = "KOSPI"
            
            codes_param = ",".join(codes_to_fetch)
            
            url = f"{self.api_base_url}/api/v1/rs/multiple"
            params = {
                "codes": codes_param,
                "compressed": "false",
                "gzip_enabled": "false"
            }
            
            logger.info(f"여러 종목 RS 데이터 요청: {url}, 종목들: {codes_to_fetch}")
            
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    response_data = await response.json()
                    
                    # 응답 구조 확인
                    if not isinstance(response_data, dict) or 'data' not in response_data:
                        logger.error("잘못된 RS 응답 구조")
                        return None
                    
                    data_list = response_data.get('data', [])
                    successful_count = response_data.get('successful_count', 0)
                    failed_codes = response_data.get('failed_codes', [])
                    
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
                        "market_rs_6m": market_data.get("rs_6m") if market_data else None
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
                        "relative_strength_analysis": self._analyze_relative_strength(
                            target_stock_data, market_data, market_code, stock_info
                        )
                    }
                    
                    return rs_summary
                        
                elif response.status == 404:
                    logger.warning(f"RS 데이터를 찾을 수 없습니다")
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
            analysis = {
                "vs_market": None,
                "market_code": market_code,
                "relative_trend": None,
                "market_specific_analysis": None
            }
            
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
                "strength_level": self._get_relative_strength_level(target_rs - market_rs)
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
                    "momentum": self._get_momentum_level(abs(rs_change_1m))
                }
            
            if target_rs_3m is not None:
                rs_change_3m = target_rs - target_rs_3m
                trend_analysis["3m"] = {
                    "direction": "strengthening" if rs_change_3m > 0 else "weakening",
                    "change": round(rs_change_3m, 2),
                    "momentum": self._get_momentum_level(abs(rs_change_3m))
                }
            
            if target_rs_6m is not None:
                rs_change_6m = target_rs - target_rs_6m
                trend_analysis["6m"] = {
                    "direction": "strengthening" if rs_change_6m > 0 else "weakening",
                    "change": round(rs_change_6m, 2),
                    "momentum": self._get_momentum_level(abs(rs_change_6m))
                }
            
            if trend_analysis:
                analysis["relative_trend"] = trend_analysis
                
                # 전반적인 트렌드 방향 평가
                strengthening_count = sum(1 for period_data in trend_analysis.values() 
                                        if period_data["direction"] == "strengthening")
                total_periods = len(trend_analysis)
                
                analysis["overall_trend_direction"] = {
                    "direction": "strengthening" if strengthening_count > total_periods / 2 else "weakening",
                    "consistency": "consistent" if strengthening_count  in [0, total_periods] else "mixed",
                    "periods_analyzed": list(trend_analysis.keys())
                }
            
            # 시장별 특화 분석
            market_analysis = self._get_market_specific_analysis(
                market_code, target_rs, market_rs
            )
            analysis["market_specific_analysis"] = market_analysis
            
            return analysis
            
        except Exception as e:
            logger.error(f"상대적 강도 분석 중 오류: {e}")
            return {
                "vs_kospi": None,
                "vs_kosdaq": None, 
                "market_leadership": None,
                "relative_trend": None
            }
    
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
            
            return {
                "target_market": market_code,
                "market_position": market_position,
                "recommendation": recommendation,
                "difference": round(diff, 2)
            }
            
        except Exception as e:
            logger.error(f"시장별 특화 분석 중 오류: {e}")
            return {
                "target_market": market_code,
                "market_position": "분석 불가",
                "recommendation": "시장별 분석에 오류가 발생했습니다.",
                "difference": None
            }

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
            
            # # MACD 계산
            macd_values = self._calculate_macd(close) if len(close) >= 26 else {}
            
            # 볼린저 밴드 계산
            bollinger = self._calculate_bollinger_bands(close) if len(close) >= 20 else {}
            
            #스토캐스틱 계산
            stochastic = self._calculate_stochastic(high, low, close) if len(close) >= 14 else {}
            
            # 추세추종 지표들 계산
            # ADX 계산
            adx_values = self._calculate_adx(high, low, close) if len(close) >= 14 else {}
            
            # ADR 계산 (개별 종목용)
            adr_values = self._calculate_adr(close) if len(close) >= 20 else {}
            
            # 슈퍼트렌드 계산
            supertrend_values = self._calculate_supertrend(high, low, close) if len(close) >= 14 else {}
            
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
                "stochastic_d": stochastic.get("d"),
                # 추세추종 지표들
                "adx": adx_values.get("adx"),
                "adx_plus_di": adx_values.get("plus_di"),
                "adx_minus_di": adx_values.get("minus_di"),
                "adr": adr_values.get("adr"),
                "adr_ma": adr_values.get("adr_ma"),
                "supertrend": supertrend_values.get("supertrend"),
                "supertrend_direction": supertrend_values.get("direction")
            }
            
            logger.info(f"기술적 지표 계산 완료")
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
    
    def _calculate_adx(self, high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> Dict[str, Optional[float]]:
        """ADX 지표를 계산합니다."""
        try:
            def safe_float(value):
                """numpy 타입을 안전하게 Python float로 변환"""
                if value is None or pd.isna(value):
                    return None
                return float(value)
            
            # ADX 시계열 데이터 계산
            adx_series = self._calculate_adx_series(high, low, close, period)
            
            return {
                "adx": safe_float(adx_series["adx"].iloc[-1]),
                "plus_di": safe_float(adx_series["plus_di"].iloc[-1]),
                "minus_di": safe_float(adx_series["minus_di"].iloc[-1])
            }
        except:
            return {"adx": None, "plus_di": None, "minus_di": None}
    
    def _calculate_adr(self, close: pd.Series, period: int = 20) -> Dict[str, Optional[float]]:
        """ADR 지표를 계산합니다."""
        try:
            def safe_float(value):
                """numpy 타입을 안전하게 Python float로 변환"""
                if value is None or pd.isna(value):
                    return None
                return float(value)
            
            # ADR 시계열 데이터 계산
            adr_series = self._calculate_adr_series(close, period)
            
            return {
                "adr": safe_float(adr_series["adr"].iloc[-1]),
                "adr_ma": safe_float(adr_series["adr_ma"].iloc[-1])
            }
        except:
            return {"adr": None, "adr_ma": None}
    
    def _calculate_supertrend(self, high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14, multiplier: float = 3.0) -> Dict[str, Optional[float]]:
        """슈퍼트렌드 지표를 계산합니다."""
        try:
            def safe_float(value):
                """numpy 타입을 안전하게 Python float로 변환"""
                if value is None or pd.isna(value):
                    return None
                return float(value)
            
            # 슈퍼트렌드 시계열 데이터 계산
            supertrend_series = self._calculate_supertrend_series(high, low, close, period, multiplier)
            
            return {
                "supertrend": safe_float(supertrend_series["supertrend"].iloc[-1]),
                "direction": safe_float(supertrend_series["direction"].iloc[-1])
            }
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
            close = df['close']
            high = df['high']
            low = df['low']
            volume = df['volume']
            
            # 차트 표시용 기간 설정 (최근 1년, 약 250일)
            chart_length = 250
            chart_start_idx = max(0, len(df) - chart_length)
            
            # 날짜 인덱스를 문자열로 변환 (차트 표시 구간만)
            dates = [date.strftime('%Y-%m-%d') for date in df.index[chart_start_idx:]]
            
            # 안전한 변환 함수 (차트 표시 구간만 추출)
            def safe_series_to_list(series):
                """pandas Series를 안전하게 리스트로 변환 (차트 구간만)"""
                if series is None or series.empty:
                    return []
                chart_series = series.iloc[chart_start_idx:]
                return [float(x) if not pd.isna(x) else None for x in chart_series]
            
            chart_data = {
                "dates": dates,
                "close": safe_series_to_list(close),
                "high": safe_series_to_list(high),
                "low": safe_series_to_list(low),
                "volume": safe_series_to_list(volume)
            }
            
            # 이동평균선
            if len(close) >= 20:
                sma_20 = close.rolling(window=20).mean()
                chart_data["sma_20"] = safe_series_to_list(sma_20)
            
            if len(close) >= 60:
                sma_60 = close.rolling(window=60).mean()
                chart_data["sma_60"] = safe_series_to_list(sma_60)
            
            # 지수이동평균
            if len(close) >= 12:
                ema_12 = close.ewm(span=12).mean()
                chart_data["ema_12"] = safe_series_to_list(ema_12)
            
            if len(close) >= 26:
                ema_26 = close.ewm(span=26).mean()
                chart_data["ema_26"] = safe_series_to_list(ema_26)
            
            # RSI
            if len(close) >= 14:
                rsi_series = self._calculate_rsi_series(close)
                chart_data["rsi"] = safe_series_to_list(rsi_series)
            
            # MACD
            if len(close) >= 26:
                macd_series = self._calculate_macd_series(close)
                chart_data["macd"] = safe_series_to_list(macd_series["macd"])
                chart_data["macd_signal"] = safe_series_to_list(macd_series["signal"])
                chart_data["macd_histogram"] = safe_series_to_list(macd_series["histogram"])
            
            # 볼린저 밴드
            if len(close) >= 20:
                bollinger_series = self._calculate_bollinger_bands_series(close)
                chart_data["bollinger_upper"] = safe_series_to_list(bollinger_series["upper"])
                chart_data["bollinger_middle"] = safe_series_to_list(bollinger_series["middle"])
                chart_data["bollinger_lower"] = safe_series_to_list(bollinger_series["lower"])
            
            # ADX
            if len(close) >= 14:
                adx_series = self._calculate_adx_series(high, low, close)
                chart_data["adx"] = safe_series_to_list(adx_series["adx"])
                chart_data["adx_plus_di"] = safe_series_to_list(adx_series["plus_di"])
                chart_data["adx_minus_di"] = safe_series_to_list(adx_series["minus_di"])
            
            # ADR
            if len(close) >= 20:
                adr_series = self._calculate_adr_series(close)
                chart_data["adr"] = safe_series_to_list(adr_series["adr"])
                chart_data["adr_ma"] = safe_series_to_list(adr_series["adr_ma"])
            
            # 슈퍼트렌드 (14일 기본값 사용)
            if len(close) >= 14:
                supertrend_series = self._calculate_supertrend_series(high, low, close)
                chart_data["supertrend"] = safe_series_to_list(supertrend_series["supertrend"])
                chart_data["supertrend_direction"] = safe_series_to_list(supertrend_series["direction"])
            
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
            
            return {
                "macd": macd,
                "signal": macd_signal,
                "histogram": macd_histogram
            }
        except:
            return {"macd": pd.Series(), "signal": pd.Series(), "histogram": pd.Series()}
    
    def _calculate_bollinger_bands_series(self, close: pd.Series, period: int = 20, std_dev: int = 2) -> Dict[str, pd.Series]:
        """볼린저 밴드 시계열 데이터를 계산합니다."""
        try:
            sma = close.rolling(window=period).mean()
            std = close.rolling(window=period).std()
            
            upper = sma + (std * std_dev)
            lower = sma - (std * std_dev)
            
            return {
                "upper": upper,
                "middle": sma,
                "lower": lower
            }
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
            
            return {
                "adx": adx,
                "plus_di": di_plus,
                "minus_di": di_minus
            }
        except:
            return {"adx": pd.Series(), "plus_di": pd.Series(), "minus_di": pd.Series()}

    def _wilders_smoothing(self, series: pd.Series, period: int) -> pd.Series:
        """Welles Wilder의 스무딩을 적용합니다."""
        alpha = 1.0 / period
        return series.ewm(alpha=alpha, adjust=False).mean()
    
    def _calculate_adr_series(self, close: pd.Series, period: int = 20) -> Dict[str, pd.Series]:
        """ADR 시계열 데이터를 계산합니다 (개별 종목용 - 상승일/하락일 비율)."""
        try:
            # 전일 대비 상승/하락 계산
            price_change = close.diff()
            
            # 상승일과 하락일 카운트 (rolling window)
            up_days = (price_change > 0).rolling(window=period).sum()
            down_days = (price_change < 0).rolling(window=period).sum()
            
            # ADR 계산 (상승일/하락일 비율)
            adr = up_days / (down_days + 1)  # 0으로 나누기 방지
            
            # ADR 이동평균
            adr_ma = adr.rolling(window=period).mean()
            
            return {
                "adr": adr,
                "adr_ma": adr_ma
            }
        except:
            return {"adr": pd.Series(), "adr_ma": pd.Series()}
    
    def _calculate_supertrend_series(self, high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14, multiplier: float = 3.0) -> Dict[str, pd.Series]:
        """슈퍼트렌드 시계열 데이터를 계산합니다."""
        try:
            # ATR 계산
            atr = self._calculate_atr(high, low, close, period)
            
            # HL2 (High + Low) / 2
            hl2 = (high + low) / 2
            
            # 상위 및 하위 밴드 계산
            upper_band = hl2 + (multiplier * atr)
            lower_band = hl2 - (multiplier * atr)
            
            # 슈퍼트렌드 초기화
            supertrend = pd.Series(index=close.index, dtype=float)
            direction = pd.Series(index=close.index, dtype=int)
            
            # 첫 번째 값 설정
            supertrend.iloc[0] = upper_band.iloc[0]
            direction.iloc[0] = 1
            
            # 슈퍼트렌드 계산
            for i in range(1, len(close)):
                if close.iloc[i] <= supertrend.iloc[i-1]:
                    supertrend.iloc[i] = upper_band.iloc[i]
                    direction.iloc[i] = -1  # 하락 추세
                else:
                    supertrend.iloc[i] = lower_band.iloc[i]
                    direction.iloc[i] = 1   # 상승 추세
            
            return {
                "supertrend": supertrend,
                "direction": direction
            }
        except:
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
            
            # ADX 추세강도 신호
            if adx is not None:
                if adx >= 25:
                    if trend_direction == "상승":
                        signals.append({"indicator": "ADX", "signal": "매수", "strength": 0.7, "value": adx, "reason": f"강한 상승추세 (ADX: {adx:.1f})"})
                    elif trend_direction == "하락":
                        signals.append({"indicator": "ADX", "signal": "매도", "strength": 0.7, "value": adx, "reason": f"강한 하락추세 (ADX: {adx:.1f})"})
                    else:
                        signals.append({"indicator": "ADX", "signal": "중립", "strength": 0.4, "value": adx, "reason": f"강한 추세이나 방향 불명확 (ADX: {adx:.1f})"})
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
        rs_data: Optional[Dict[str, Any]],
        stock_info: Optional[Dict[str, Any]],
        query: str, 
        user_id: Optional[str]
    ) -> str:
        """
        LLM을 사용하여 기술적 분석 종합 요약을 생성합니다.
        """
        try:
            # 종목 기본 정보 추가
            stock_basic_info = ""
            if stock_info:
                market = stock_info.get('market', 'N/A')
                sector = stock_info.get('sector', 'N/A')
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
- 현재 RS: {rs_data.get('rs', 'N/A')}
- RS 1개월: {rs_data.get('rs_1m', 'N/A')}
- RS 3개월: {rs_data.get('rs_3m', 'N/A')}
- 업종: {rs_data.get('sector', 'N/A')}
- MMT: {rs_data.get('mmt', 'N/A')}
"""
                
                # 시장 비교 정보 추가
                market_comparison = rs_data.get('market_comparison', {})
                if market_comparison:
                    market_code = market_comparison.get('market_code')
                    market_rs = market_comparison.get('market_rs')
                    market_rs_1m = market_comparison.get('market_rs_1m')
                    market_rs_3m = market_comparison.get('market_rs_3m')
                    market_rs_6m = market_comparison.get('market_rs_6m')
                    
                    if market_code and market_rs is not None:
                        rs_info += f"""
시장 지수 비교:
- {market_code} RS: {market_rs} (1M: {market_rs_1m or 'N/A'}, 3M: {market_rs_3m or 'N/A'}, 6M: {market_rs_6m or 'N/A'})
"""
                
                # 상대적 강도 분석 추가
                relative_analysis = rs_data.get('relative_strength_analysis', {})
                if relative_analysis:
                    vs_market = relative_analysis.get('vs_market')
                    if vs_market:
                        market_name = vs_market.get('market_name', '시장')
                        strength_level = vs_market.get('strength_level', 'N/A')
                        difference = vs_market.get('difference', 0)
                        rs_info += f"""
시장 대비 분석: {market_name} 대비 {strength_level} ({'+' if difference >= 0 else ''}{difference})
"""
            
            # 추세추종 지표 정보 추가
            trend_indicators_info = ""
            
            # ADX 정보
            adx = technical_indicators.get('adx')
            adx_plus_di = technical_indicators.get('adx_plus_di')
            adx_minus_di = technical_indicators.get('adx_minus_di')
            if adx is not None:
                trend_strength = "강한 추세" if adx >= 25 else "약한 추세" if adx <= 20 else "보통 추세"
                trend_indicators_info += f"""
ADX (추세강도 지표):
- ADX: {adx:.2f} ({trend_strength})
- +DI: {adx_plus_di:.2f if adx_plus_di else 'N/A'}
- -DI: {adx_minus_di:.2f if adx_minus_di else 'N/A'}
"""
            
            # ADR 정보
            adr = technical_indicators.get('adr')
            adr_ma = technical_indicators.get('adr_ma')
            if adr is not None:
                adr_signal = "상승 우세" if adr > 1.2 else "하락 우세" if adr < 0.8 else "균형"
                trend_indicators_info += f"""
ADR (상승일/하락일 비율):
- ADR: {adr:.2f} ({adr_signal})
- ADR 이동평균: {adr_ma:.2f if adr_ma else 'N/A'}
"""
            
            # 슈퍼트렌드 정보
            supertrend = technical_indicators.get('supertrend')
            supertrend_direction = technical_indicators.get('supertrend_direction')
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
- RSI: {technical_indicators.get('rsi', 'N/A')}
- MACD: {technical_indicators.get('macd', 'N/A')}
- 종합 매매 신호: {trading_signals.get('overall_signal', 'N/A')}

추세추종 지표:{trend_indicators_info}

{rs_info}

사용자 질문: {query}

다음 지표들의 의미:
- RS(상대강도): 시장 대비 주식의 상대적 강도를 나타내며, 높을수록 시장을 아웃퍼폼
- ADX: 25 이상이면 강한 추세, 20 이하면 약한 추세
- ADR: 1.2 이상이면 상승 우세, 0.8 이하면 하락 우세
- 슈퍼트렌드: 추세 변화를 감지하는 지표

분석 시 고려사항:
1. 종목이 소속된 시장(코스피/코스닥)의 특성을 고려하여 분석하세요.
2. 시장별 상대강도 분석 결과가 있다면 이를 적극 활용하세요.
3. 추세추종 지표들과 시장 소속정보를 종합하여 투자 관점을 제시하세요.

추세추종 지표들(ADX, ADR, 슈퍼트렌드)과 시장별 RS 분석을 중심으로 현재 추세 상황과 투자 시사점을 3-4문장으로 간결하게 설명해주세요.
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
        rs_data: Optional[Dict[str, Any]],
        user_id: Optional[str]
    ) -> List[str]:
        """
        투자 권고사항을 생성합니다.
        """
        try:
            recommendations = []
            
            overall_signal = trading_signals.get("overall_signal", "중립")
            confidence = trading_signals.get("confidence", 0)
            
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
                rs_value = rs_data.get('rs')
                rs_1m = rs_data.get('rs_1m')
                
                # 기본 RS 수준 분석
                if rs_value is not None:
                    try:
                        rs_float = float(rs_value)
                        if rs_float >= 80:
                            recommendations.append("RS(상대강도)가 매우 높아 시장 대비 강세를 보이고 있습니다.")
                        elif rs_float >= 60:
                            recommendations.append("RS(상대강도)가 양호하여 시장 대비 우수한 성과를 보이고 있습니다.")
                        elif rs_float <= 20:
                            recommendations.append("RS(상대강도)가 낮아 시장 대비 약세를 보이고 있으므로 주의가 필요합니다.")
                        elif rs_float <= 40:
                            recommendations.append("RS(상대강도)가 평균 이하로 시장 대비 부진한 모습입니다.")
                    except (ValueError, TypeError):
                        pass
                
                # 시장 대비 상대강도 분석
                relative_analysis = rs_data.get('relative_strength_analysis', {})
                if relative_analysis:
                    vs_market = relative_analysis.get('vs_market')
                    if vs_market:
                        market_name = vs_market.get('market_name', '시장')
                        outperforming = vs_market.get('outperforming', False)
                        strength_level = vs_market.get('strength_level', '')
                        
                        if outperforming:
                            recommendations.append(f"{market_name} 대비 상대적 우위를 보이고 있습니다. ({strength_level})")
                        else:
                            recommendations.append(f"{market_name} 대비 상대적으로 부진한 모습입니다. ({strength_level})")
                        
                        # 트렌드 분석
                        overall_trend = vs_market.get('overall_trend')
                        trends = vs_market.get('trends', {})
                        
                        if overall_trend == 'improving':
                            improving_periods = [period for period, trend in trends.items() if trend == 'improving']
                            if improving_periods:
                                recommendations.append(f"{market_name} 대비 상대강도가 {', '.join(improving_periods)} 기간에서 개선되는 추세입니다.")
                        elif overall_trend == 'weakening':
                            weakening_periods = [period for period, trend in trends.items() if trend == 'weakening']
                            if weakening_periods:
                                recommendations.append(f"{market_name} 대비 상대강도가 {', '.join(weakening_periods)} 기간에서 약화되는 추세입니다.")
                    
                    # 시장별 특화 분석 기반 권고
                    market_analysis = relative_analysis.get('market_specific_analysis')
                    if market_analysis:
                        market_recommendation = market_analysis.get('recommendation')
                        if market_recommendation:
                            recommendations.append(market_recommendation)
                
                # 업종 정보 추가
                sector = rs_data.get('sector')
                if sector:
                    recommendations.append(f"{sector} 섹터의 동향도 함께 고려하시기 바랍니다.")
            
            # 공통 권고사항
            recommendations.append("분할 매수/매도를 통해 리스크를 관리하세요.")
            recommendations.append("손절선을 미리 설정하고 감정적 거래를 피하세요.")
            
            return recommendations
            
        except Exception as e:
            logger.error(f"투자 권고사항 생성 중 오류: {str(e)}")
            return [f"{stock_name}에 대한 기술적 분석을 참고하여 신중한 투자 결정을 내리시기 바랍니다."] 