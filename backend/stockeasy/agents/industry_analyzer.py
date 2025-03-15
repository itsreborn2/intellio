"""산업 및 시장 동향 분석을 위한 에이전트

이 모듈은 산업 및 시장 동향 정보를 검색하고 분석하는 에이전트를 정의합니다.
"""

from typing import Dict, Any, List, Optional
from loguru import logger
import time
import json

from stockeasy.agents.base import BaseAgent
from stockeasy.prompts.industry_prompts import INDUSTRY_ANALYSIS_PROMPT
from common.services.llm_models import LLMModels
from common.core.config import settings


class IndustryAnalyzerAgent(BaseAgent):
    """산업 및 시장 동향 분석 에이전트"""

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
            logger.info(f"산업 분석 에이전트 시작: {state.get('query')}")

            # 필요한 파라미터 추출
            query = state.get("query", "")
            stock_code = state.get("stock_code", "")
            stock_name = state.get("stock_name", "")
            classification = state.get("classification", {})
            
            # 산업/섹터 정보 추출
            sector = classification.get("산업/섹터", "")
            if not sector and stock_name:
                # 실제로는 여기서 종목명으로부터 산업/섹터 정보를 조회하는 로직이 필요
                sector = self._get_dummy_sector(stock_name)

            # 실제 분석은 구현되지 않음 - 더미 데이터 반환
            industry_data = self._get_dummy_industry_data(stock_name, sector)
            
            # 결과 저장
            if "retrieved_data" not in state:
                state["retrieved_data"] = {}
            
            state["retrieved_data"]["industry_data"] = industry_data
            
            # 처리 시간 측정
            processing_time = time.time() - start_time
            logger.info(f"산업 분석 에이전트 완료: {processing_time:.2f}초 소요")
            
            # 메트릭 추가
            if "metrics" not in state:
                state["metrics"] = {}
            state["metrics"]["industry_analyzer_time"] = processing_time
            
            return state
            
        except Exception as e:
            logger.error(f"산업 분석 에이전트 오류: {str(e)}", exc_info=True)
            
            # 오류 정보 추가
            if "errors" not in state:
                state["errors"] = []
                
            state["errors"].append({
                "agent": "industry_analyzer",
                "error": str(e),
                "timestamp": time.time()
            })
            
            # 빈 결과라도 반환하여 파이프라인 진행
            if "retrieved_data" not in state:
                state["retrieved_data"] = {}
            state["retrieved_data"]["industry_data"] = []
            
            return state

    def _get_dummy_sector(self, stock_name: str) -> str:
        """종목명으로부터 더미 산업/섹터 정보를 반환합니다.

        Args:
            stock_name: 종목명

        Returns:
            str: 더미 산업/섹터 정보
        """
        # 실제로는 DB나 API를 통해 산업 정보를 조회해야 함
        sectors = {
            "삼성전자": "전자/반도체",
            "SK하이닉스": "반도체",
            "네이버": "인터넷/플랫폼",
            "카카오": "인터넷/플랫폼",
            "현대차": "자동차",
            "기아": "자동차",
            "LG화학": "화학/배터리",
            "삼성바이오로직스": "바이오/제약",
            "셀트리온": "바이오/제약",
            "POSCO홀딩스": "철강/금속"
        }
        
        return sectors.get(stock_name, "IT/소프트웨어")  # 기본값

    def _get_dummy_industry_data(self, stock_name: str, sector: str) -> List[Dict[str, Any]]:
        """더미 산업 동향 데이터를 반환합니다.

        Args:
            stock_name: 종목명
            sector: 산업/섹터

        Returns:
            List[Dict[str, Any]]: 더미 산업 동향 데이터
        """
        return [
            {
                "source": "산업 동향 보고서",
                "date": "2024-04-15",
                "title": f"{sector} 산업 동향 분석",
                "content": f"{sector} 산업은 2024년 상반기에 글로벌 수요 회복과 함께 성장세를 보이고 있습니다. 특히 {stock_name}이 속한 세부 분야는 전년 대비 약 12% 성장이 예상됩니다. 주요 성장 동력은 기술 혁신과 규제 환경 변화로 분석됩니다.",
                "key_trends": [
                    "디지털 전환 가속화로 인한 수요 증가",
                    "친환경 기술 투자 확대",
                    "글로벌 공급망 재편",
                    "핵심 원자재 가격 안정화"
                ]
            },
            {
                "source": "시장 조사 리포트",
                "date": "2024-03-20",
                "title": f"{sector} 시장 전망",
                "content": f"{sector} 시장은 2024-2028년 연평균 8.5% 성장이 전망됩니다. {stock_name}을 포함한 국내 기업들의 시장 점유율은 글로벌 시장에서 약 15%를 차지하고 있으며, 향후 기술 경쟁력 강화를 통해 20%까지 확대될 것으로 예상됩니다.",
                "market_data": {
                    "시장규모": "50조원 (2023년 기준)",
                    "연평균성장률": "8.5% (2024-2028 전망)",
                    "국내기업 점유율": "15%",
                    "주요 경쟁사": "글로벌 Top 5 기업 및 주요 점유율"
                }
            },
            {
                "source": "산업 뉴스 분석",
                "date": "2024-04-01",
                "title": f"{sector} 최근 이슈 및 정책 동향",
                "content": f"최근 정부는 {sector} 산업 경쟁력 강화를 위한 지원책을 발표했습니다. 약 2조원 규모의 R&D 지원과 세제 혜택이 포함되어 있어 {stock_name}을 포함한 국내 기업들에게 긍정적 영향이 예상됩니다. 또한 규제 완화를 통한 신사업 진출 기회도 확대될 전망입니다.",
                "policy_changes": [
                    "산업 지원 펀드 조성",
                    "기술 개발 세제 혜택 확대",
                    "신산업 규제 샌드박스 도입",
                    "해외 진출 지원 강화"
                ]
            }
        ] 