#!/usr/bin/env python3
"""
Stock Data Collector 컨테이너 통신 테스트 스크립트

목표: stock-data-collector 컨테이너에 SK하이닉스 주가차트를 요청하고 출력하는 테스트
- 컨테이너 간 통신 확인
- API 응답 검증
- 데이터 출력 및 분석
"""
import asyncio
import json
import os
import sys
from datetime import datetime
from typing import Dict, Any, Optional

import httpx
from loguru import logger

# SK하이닉스 종목 코드
SK_HYNIX_CODE = "000660"

# Docker 환경에서 컨테이너 간 통신용 URL
# 컨테이너명이 stock-data-collector이고 포트가 8001일 때
STOCK_DATA_COLLECTOR_BASE_URL = "http://stock-data-collector:8001"

# 로컬 테스트용 URL (Docker 외부에서 테스트할 때)
LOCAL_BASE_URL = "http://localhost:8001"

class StockDataCollectorTester:
    """Stock Data Collector 테스트 클래스"""
    
    def __init__(self, base_url: str = None):
        """
        테스트 클래스 초기화
        
        Args:
            base_url: API 기본 URL (기본값: 컨테이너 간 통신 URL)
        """
        self.base_url = base_url or STOCK_DATA_COLLECTOR_BASE_URL
        self.client = None
        
        # 로거 설정
        logger.remove()
        logger.add(
            sys.stdout,
            format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | {message}",
            level="INFO"
        )
        
        logger.info(f"Stock Data Collector 테스터 초기화 - 기본 URL: {self.base_url}")
    
    async def __aenter__(self):
        """비동기 컨텍스트 매니저 진입"""
        self.client = httpx.AsyncClient(
            timeout=30.0,
            verify=False,  # SSL 검증 비활성화 (테스트용)
            follow_redirects=True
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """비동기 컨텍스트 매니저 종료"""
        if self.client:
            await self.client.aclose()
    
    async def check_health(self) -> bool:
        """서비스 헬스체크"""
        try:
            logger.info(f"📋 서비스 헬스체크 수행 중... {self.base_url}")
            
            response = await self.client.get(f"{self.base_url}/health")
            
            if response.status_code == 200:
                health_data = response.json()
                logger.success(f"✅ 서비스 상태: 정상 - {health_data}")
                return True
            else:
                logger.error(f"❌ 헬스체크 실패: HTTP {response.status_code}")
                return False
                
        except httpx.ConnectError as e:
            logger.error(f"❌ 연결 실패: {e}")
            logger.info(f"💡 연결 URL 확인: {self.base_url}")
            return False
        except Exception as e:
            logger.error(f"❌ 헬스체크 중 오류: {e}")
            return False
    
    async def get_stock_list(self) -> Optional[Dict[str, Any]]:
        """종목 리스트 조회"""
        try:
            logger.info("📈 종목 리스트 조회 중...")
            
            response = await self.client.get(f"{self.base_url}/api/v1/stock/list")
            
            if response.status_code == 200:
                stock_list = response.json()
                logger.success(f"✅ 종목 리스트 조회 성공: {stock_list.get('count', 0)}개 종목")
                
                # SK하이닉스 존재 여부 확인
                sk_hynix_found = False
                for stock in stock_list.get('stocks', []):
                    if stock.get('code') == SK_HYNIX_CODE:
                        sk_hynix_found = True
                        logger.info(f"🎯 SK하이닉스 발견: {stock}")
                        break
                
                if not sk_hynix_found:
                    logger.warning(f"⚠️ SK하이닉스({SK_HYNIX_CODE}) 종목을 찾을 수 없습니다")
                
                return stock_list
            else:
                logger.error(f"❌ 종목 리스트 조회 실패: HTTP {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"❌ 종목 리스트 조회 중 오류: {e}")
            return None
    
    async def get_stock_chart(
        self, 
        symbol: str = SK_HYNIX_CODE,
        period: str = "1m",
        interval: str = "1d",
        compressed: bool = False,
        gzip_enabled: bool = False
    ) -> Optional[Dict[str, Any]]:
        """
        주가차트 데이터 조회
        
        Args:
            symbol: 종목 코드 (기본값: SK하이닉스)
            period: 조회 기간 (1d, 1w, 1m, 3m, 6m, 1y, 2y, 5y)
            interval: 간격 (1m, 5m, 15m, 30m, 1h, 1d, 1w, 1M)
            compressed: 압축된 형태로 반환
            gzip_enabled: gzip 압축 사용
        """
        try:
            logger.info(f"📊 주가차트 조회 중 - 종목: {symbol}, 기간: {period}, 간격: {interval}")
            
            params = {
                "period": period,
                "interval": interval,
                "compressed": compressed,
                "gzip_enabled": gzip_enabled
            }
            
            response = await self.client.get(
                f"{self.base_url}/api/v1/stock/chart/{symbol}",
                params=params
            )
            
            if response.status_code == 200:
                chart_data = response.json()
                logger.success(f"✅ 주가차트 조회 성공")
                
                # 데이터 요약 정보 출력
                data = chart_data.get('data', {})
                if isinstance(data, dict):
                    data_points = data.get('data', [])
                    logger.info(f"📈 차트 데이터 포인트: {len(data_points)}개")
                    
                    if data_points:
                        # 첫 번째와 마지막 데이터 포인트 출력
                        first_point = data_points[0] if data_points else None
                        last_point = data_points[-1] if data_points else None
                        
                        if first_point:
                            logger.info(f"📅 첫 번째 데이터: {first_point}")
                        if last_point and len(data_points) > 1:
                            logger.info(f"📅 마지막 데이터: {last_point}")
                
                return chart_data
            else:
                logger.error(f"❌ 주가차트 조회 실패: HTTP {response.status_code}")
                logger.error(f"응답 내용: {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"❌ 주가차트 조회 중 오류: {e}")
            return None
    
    async def get_stock_info(self, symbol: str = SK_HYNIX_CODE) -> Optional[Dict[str, Any]]:
        """종목 기본정보 조회"""
        try:
            logger.info(f"ℹ️ 종목 정보 조회 중 - 종목: {symbol}")
            
            response = await self.client.get(f"{self.base_url}/api/v1/stock/info/{symbol}")
            
            if response.status_code == 200:
                stock_info = response.json()
                logger.success(f"✅ 종목 정보 조회 성공")
                logger.info(f"🏢 종목 정보: {stock_info.get('data', {})}")
                return stock_info
            else:
                logger.error(f"❌ 종목 정보 조회 실패: HTTP {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"❌ 종목 정보 조회 중 오류: {e}")
            return None
    
    
    
    def format_chart_data(self, chart_data: Dict[str, Any]) -> None:
        """차트 데이터를 보기 좋게 포맷하여 출력"""
        logger.info("📊 차트 데이터 상세 분석:")
        
        if not chart_data:
            logger.warning("⚠️ 차트 데이터가 없습니다")
            return
        
        # 기본 정보
        symbol = chart_data.get('symbol', 'N/A')
        period = chart_data.get('period', 'N/A')
        interval = chart_data.get('interval', 'N/A')
        
        logger.info(f"📈 종목: {symbol} | 기간: {period} | 간격: {interval}")
        
        # 데이터 분석
        data = chart_data.get('data', {})
        if isinstance(data, dict):
            data_points = data.get('data', [])
            
            if data_points:
                logger.info(f"📊 총 데이터 포인트: {len(data_points)}개")
                
                # 최신 5개 데이터 포인트 표시
                logger.info("📋 최신 5개 데이터 포인트:")
                for i, point in enumerate(data_points[-5:], 1):
                    if isinstance(point, dict):
                        # timestamp에서 날짜 부분만 추출
                        timestamp = point.get('timestamp', 'N/A')
                        if timestamp != 'N/A':
                            try:
                                # timestamp가 문자열인 경우 datetime으로 변환 후 날짜만 추출
                                if isinstance(timestamp, str):
                                    from datetime import datetime
                                    # ISO 형식이나 일반적인 datetime 문자열 처리
                                    if 'T' in timestamp:
                                        dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                                    else:
                                        dt = datetime.strptime(timestamp.split()[0], '%Y-%m-%d')
                                    date = dt.strftime('%Y-%m-%d')
                                else:
                                    # datetime 객체인 경우
                                    date = timestamp.strftime('%Y-%m-%d')
                            except (ValueError, AttributeError):
                                # 파싱 실패 시 원본 그대로 표시
                                date = str(timestamp)
                        else:
                            date = 'N/A'
                        
                        # 안전한 숫자 변환 함수
                        def safe_number_format(value, default=0):
                            try:
                                if value is None:
                                    return default
                                # 문자열이면 숫자로 변환 시도
                                if isinstance(value, str):
                                    # 빈 문자열이면 기본값 반환
                                    if not value.strip():
                                        return default
                                    # 콤마 제거 후 변환
                                    cleaned = value.replace(',', '')
                                    return float(cleaned)
                                # 이미 숫자면 그대로 반환
                                return float(value)
                            except (ValueError, TypeError):
                                return default
                        
                        open_price = safe_number_format(point.get('open'))
                        high = safe_number_format(point.get('high'))
                        low = safe_number_format(point.get('low'))
                        close = safe_number_format(point.get('close'))
                        volume = safe_number_format(point.get('volume'))
                        
                        logger.info(f"  {i}. 날짜: {date} | 시가: {open_price:,.0f} | 고가: {high:,.0f} | 저가: {low:,.0f} | 종가: {close:,.0f} | 거래량: {volume:,.0f}")
                    elif isinstance(point, list) and len(point) >= 6:
                        # 압축된 데이터 형태
                        logger.info(f"  {i}. 데이터: {point}")
            else:
                logger.warning("⚠️ 차트 데이터 포인트가 없습니다")
        else:
            logger.warning("⚠️ 예상하지 못한 데이터 형태입니다")
    
    async def run_comprehensive_test(self) -> Dict[str, bool]:
        """종합 테스트 실행"""
        results = {}
        
        logger.info("🚀 Stock Data Collector 종합 테스트 시작")
        logger.info("=" * 60)
        
        # 1. 헬스체크
        results['health_check'] = await self.check_health()
        
        if not results['health_check']:
            logger.error("❌ 헬스체크 실패로 테스트를 중단합니다")
            return results
        
        # 2. 종목 리스트 조회
        stock_list = await self.get_stock_list()
        results['stock_list'] = stock_list is not None
        
        # 3. 종목 정보 조회
        stock_info = await self.get_stock_info()
        results['stock_info'] = stock_info is not None
        
        
        # 5. 주가차트 조회 (여러 기간)
        chart_periods = ["1w", "1m", "3m"]
        results['chart_data'] = {}
        
        for period in chart_periods:
            logger.info(f"📊 {period} 기간 차트 데이터 조회 중...")
            chart_data = await self.get_stock_chart(period=period)
            results['chart_data'][period] = chart_data is not None
            
            if chart_data:
                self.format_chart_data(chart_data)
        
        # 결과 요약
        logger.info("=" * 60)
        logger.info("📋 테스트 결과 요약:")
        
        for test_name, result in results.items():
            if isinstance(result, dict):
                for sub_test, sub_result in result.items():
                    status = "✅ 성공" if sub_result else "❌ 실패"
                    logger.info(f"  {test_name}_{sub_test}: {status}")
            else:
                status = "✅ 성공" if result else "❌ 실패"
                logger.info(f"  {test_name}: {status}")
        
        return results


async def main():
    """메인 함수"""
    # 환경 변수나 인자를 통해 URL 설정 가능
    base_url = os.getenv('STOCK_DATA_COLLECTOR_URL', STOCK_DATA_COLLECTOR_BASE_URL)
    
    # 로컬 테스트 모드 확인
    if len(sys.argv) > 1 and sys.argv[1] == '--local':
        base_url = LOCAL_BASE_URL
        logger.info("🔧 로컬 테스트 모드로 실행")
    
    async with StockDataCollectorTester(base_url) as tester:
        # 종합 테스트 실행
        results = await tester.run_comprehensive_test()
        
        # 테스트 성공 여부 확인
        all_success = True
        for test_result in results.values():
            if isinstance(test_result, dict):
                if not all(test_result.values()):
                    all_success = False
                    break
            elif not test_result:
                all_success = False
                break
        
        if all_success:
            logger.success("🎉 모든 테스트가 성공했습니다!")
            sys.exit(0)
        else:
            logger.error("❌ 일부 테스트가 실패했습니다")
            sys.exit(1)


if __name__ == "__main__":
    # 비동기 실행
    asyncio.run(main()) 