"""재무제표 및 사업보고서 분석을 위한 에이전트

이 모듈은 특정 종목의 재무제표, 사업보고서 등 재무 관련 정보를 검색하고 분석하는 에이전트를 정의합니다.
"""

from typing import Dict, Any, List, Optional
from loguru import logger
import time
import json

from stockeasy.agents.base import BaseAgent
from stockeasy.prompts.financial_prompts import FINANCIAL_ANALYSIS_PROMPT
from common.services.llm_models import LLMModels
from common.core.config import settings


class FinancialAnalyzerAgent(BaseAgent):
    """재무제표 및 사업보고서 분석 에이전트"""

    def __init__(self):
        """에이전트 초기화"""
        self.llm = LLMModels()
        self.model_name = settings.OPENAI_MODEL_NAME

    async def process(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """상태를 입력받아 처리하고 업데이트된 상태를 반환

        Args:
            state: 현재 에이전트 상태

        Returns:
            Dict[str, Any]: 업데이트된 에이전트 상태
        """
        try:
            start_time = time.time()
            logger.info(f"재무제표 분석 에이전트 시작: {state.get('query')}")

            # 필요한 파라미터 추출
            query = state.get("query", "")
            stock_code = state.get("stock_code", "")
            stock_name = state.get("stock_name", "")
            classification = state.get("question_classification", {})

            # 실제 분석은 구현되지 않음 - 더미 데이터 반환
            financial_data = self._get_dummy_financial_data(stock_name, stock_code)
            
            # 결과 저장
            if "retrieved_data" not in state:
                state["retrieved_data"] = {}
            
            state["retrieved_data"]["financial_data"] = financial_data
            
            # 처리 시간 측정
            processing_time = time.time() - start_time
            logger.info(f"재무제표 분석 에이전트 완료: {processing_time:.2f}초 소요")
            
            # 메트릭 추가
            if "metrics" not in state:
                state["metrics"] = {}
            state["metrics"]["financial_analyzer_time"] = processing_time
            
            return state
            
        except Exception as e:
            logger.error(f"재무제표 분석 에이전트 오류: {str(e)}", exc_info=True)
            
            # 오류 정보 추가
            if "errors" not in state:
                state["errors"] = []
                
            state["errors"].append({
                "agent": "financial_analyzer",
                "error": str(e),
                "timestamp": time.time()
            })
            
            # 빈 결과라도 반환하여 파이프라인 진행
            if "retrieved_data" not in state:
                state["retrieved_data"] = {}
            state["retrieved_data"]["financial_data"] = []
            
            return state

    def _get_dummy_financial_data(self, stock_name: str, stock_code: str) -> List[Dict[str, Any]]:
        """더미 재무 데이터를 반환합니다.

        Args:
            stock_name: 종목명
            stock_code: 종목코드

        Returns:
            List[Dict[str, Any]]: 더미 재무 데이터
        """
        return [
            {
                "source": "최근 분기보고서",
                "date": "2024-03-31",
                "content": f"{stock_name}({stock_code})의 2024년 1분기 매출액은 전년 동기 대비 15% 증가한 5,230억원, 영업이익은 780억원으로 20% 증가했습니다. 순이익은 620억원으로 영업이익률은 14.9%를 기록했습니다.",
                "financial_indicators": {
                    "매출액": "5,230억원 (YoY +15%)",
                    "영업이익": "780억원 (YoY +20%)",
                    "순이익": "620억원 (YoY +18%)",
                    "영업이익률": "14.9%",
                    "부채비율": "45.2%",
                    "ROE": "12.8%",
                    "EPS": "8,750원"
                }
            },
            {
                "source": "연간 사업보고서",
                "date": "2023-12-31",
                "content": f"{stock_name}의 2023년 연간 매출액은 1조 8,500억원으로 전년 대비 12% 성장했습니다. 영업이익은 2,850억원으로 전년 대비 16% 증가했으며, 당기순이익은 2,200억원을 기록했습니다. 배당금은 주당 1,200원으로 배당성향은 30%입니다.",
                "financial_indicators": {
                    "매출액": "1조 8,500억원 (YoY +12%)",
                    "영업이익": "2,850억원 (YoY +16%)",
                    "순이익": "2,200억원 (YoY +14%)",
                    "영업이익률": "15.4%",
                    "부채비율": "48.5%",
                    "ROE": "14.2%",
                    "EPS": "32,500원",
                    "PER": "12.5배",
                    "PBR": "1.8배",
                    "배당수익률": "3.2%"
                }
            }
        ] 