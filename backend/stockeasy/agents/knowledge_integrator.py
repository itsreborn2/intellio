"""
지식 통합 에이전트

이 모듈은 다양한 정보 소스에서 수집된 데이터를 통합하는 에이전트를 정의합니다.
"""

from typing import Dict, Any, List
from datetime import datetime
from loguru import logger

from stockeasy.agents.base import BaseAgent

class KnowledgeIntegratorAgent(BaseAgent):
    """다양한 정보 소스에서 수집된 데이터를 통합하는 에이전트"""
    
    def __init__(self):
        """에이전트 초기화"""
        super().__init__("knowledge_integrator")
    
    async def process(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        다양한 정보 소스에서 수집된 데이터를 통합합니다.
        
        Args:
            state: 현재 상태
            
        Returns:
            통합된 정보가 추가된 업데이트된 상태
        """
        try:
            # 시작 시간 기록
            start_time = datetime.now()
            
            # 필요한 정보 추출
            query = state.get("query", "")
            stock_code = state.get("stock_code")
            stock_name = state.get("stock_name")
            telegram_data = state.get("telegram_data", [])
            report_data = state.get("report_data", [])
            financial_data = state.get("financial_data", {})
            industry_data = state.get("industry_data", {})
            classification = state.get("classification", {})
            
            # 수집된 정보가 없으면 오류 반환
            if not telegram_data and not report_data and not financial_data and not industry_data:
                logger.warning(f"통합할 데이터가 없습니다. 쿼리: {query}")
                return {
                    **state,
                    "integrated_knowledge": {},
                    "errors": state.get("errors", []) + [{
                        "agent": self.get_name(),
                        "error": "통합할 데이터가 없습니다.",
                        "type": "NoDataError",
                        "timestamp": datetime.now()
                    }],
                    "processing_status": {
                        **state.get("processing_status", {}),
                        "knowledge_integrator": "error_no_data"
                    }
                }
            
            # 데이터 통합 및 우선순위 부여
            integrated_data = {}
            
            # 1. 텔레그램 메시지 정보 가공
            if telegram_data:
                integrated_data["telegram"] = self._process_telegram_data(telegram_data)
            
            # 2. 기업리포트 정보 가공
            if report_data:
                integrated_data["report"] = self._process_report_data(report_data)
                
                # 투자의견 및 목표가 정보 추출
                investment_opinions = self._extract_investment_opinions(report_data)
                if investment_opinions:
                    integrated_data["investment_opinions"] = investment_opinions
            
            # 3. 재무 정보 가공
            if financial_data:
                integrated_data["financial"] = self._process_financial_data(financial_data)
            
            # 4. 산업 동향 정보 가공
            if industry_data:
                integrated_data["industry"] = self._process_industry_data(industry_data)
            
            # 5. 종합적인 정보 우선순위 결정 (질문 유형에 따라 가중치 조정)
            question_type = classification.get("질문주제", 4)
            integrated_data["priorities"] = self._determine_data_priorities(
                question_type, 
                bool(telegram_data), 
                bool(report_data), 
                bool(financial_data), 
                bool(industry_data)
            )
            
            # 6. 처리 시간 기록
            processing_time = (datetime.now() - start_time).total_seconds()
            
            # 상태 업데이트
            return {
                **state,
                "integrated_knowledge": integrated_data,
                "knowledge_integration_time": processing_time,
                "processing_status": {
                    **state.get("processing_status", {}),
                    "knowledge_integrator": "completed"
                }
            }
        
        except Exception as e:
            logger.error(f"지식 통합 중 오류 발생: {str(e)}", exc_info=True)
            return {
                **state,
                "errors": state.get("errors", []) + [{
                    "agent": self.get_name(),
                    "error": str(e),
                    "type": type(e).__name__,
                    "timestamp": datetime.now()
                }],
                "processing_status": {
                    **state.get("processing_status", {}),
                    "knowledge_integrator": "error"
                },
                "integrated_knowledge": {}
            }
    
    def _process_telegram_data(self, telegram_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        텔레그램 메시지 데이터 처리
        
        Args:
            telegram_data: 텔레그램 메시지 목록
            
        Returns:
            처리된 텔레그램 데이터
        """
        # 구현할 예정
        return {"count": len(telegram_data), "messages": telegram_data}
    
    def _process_report_data(self, report_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        기업리포트 데이터 처리
        
        Args:
            report_data: 리포트 데이터 목록
            
        Returns:
            처리된 리포트 데이터
        """
        if not report_data:
            return {}
        
        # 리포트 출처별로 그룹화
        sources = {}
        for report in report_data:
            source = report.get("source", "미상")
            if source not in sources:
                sources[source] = []
            sources[source].append(report)
        
        # 투자의견 및 목표가 정보 정리
        opinions_summary = {}
        target_prices = []
        
        for report in report_data:
            # 투자의견 추출
            opinions = report.get("investment_opinions", [])
            for opinion in opinions:
                source = opinion.get("source")
                if source and opinion.get("opinion"):
                    if source not in opinions_summary:
                        opinions_summary[source] = []
                    
                    opinions_summary[source].append({
                        "opinion": opinion.get("opinion"),
                        "date": opinion.get("date", ""),
                        "target_price": opinion.get("target_price")
                    })
                    
                    # 목표가 추출
                    if opinion.get("target_price"):
                        target_prices.append({
                            "price": opinion.get("target_price"),
                            "source": source,
                            "date": opinion.get("date", "")
                        })
        
        # 주요 키워드 및 정보 추출 (향후 구현)
        
        # 최신 정보 우선 정렬
        for source in sources:
            sources[source].sort(key=lambda x: x.get("date", ""), reverse=True)
        
        # 목표가 평균 계산
        avg_target_price = None
        if target_prices:
            prices = [item["price"] for item in target_prices if item["price"]]
            if prices:
                avg_target_price = sum(prices) / len(prices)
        
        return {
            "sources": sources,
            "opinions": opinions_summary,
            "target_prices": target_prices,
            "avg_target_price": avg_target_price,
            "count": len(report_data)
        }
    
    def _process_financial_data(self, financial_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        재무 데이터 처리
        
        Args:
            financial_data: 재무 데이터
            
        Returns:
            처리된 재무 데이터
        """
        # 구현할 예정
        return financial_data
    
    def _process_industry_data(self, industry_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        산업 동향 데이터 처리
        
        Args:
            industry_data: 산업 동향 데이터
            
        Returns:
            처리된 산업 동향 데이터
        """
        # 구현할 예정
        return industry_data
    
    def _extract_investment_opinions(self, report_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        투자의견 및 목표가 정보 추출
        
        Args:
            report_data: 리포트 데이터 목록
            
        Returns:
            추출된 투자의견 정보
        """
        result = {
            "opinions": [],
            "target_prices": [],
            "avg_target_price": None,
            "recent_opinions": [],
            "max_target_price": None,
            "min_target_price": None
        }
        
        if not report_data:
            return result
        
        # 모든 투자의견 수집
        all_opinions = []
        target_prices = []
        
        for report in report_data:
            opinions = report.get("investment_opinions", [])
            for opinion in opinions:
                if opinion.get("opinion") or opinion.get("target_price"):
                    all_opinions.append(opinion)
                    
                    if opinion.get("target_price"):
                        target_prices.append({
                            "price": opinion.get("target_price"),
                            "source": opinion.get("source", ""),
                            "date": opinion.get("date", "")
                        })
        
        # 최신순 정렬
        all_opinions.sort(key=lambda x: x.get("date", ""), reverse=True)
        target_prices.sort(key=lambda x: x.get("date", ""), reverse=True)
        
        # 최근 3개 의견만 선택
        recent_opinions = all_opinions[:3] if len(all_opinions) > 3 else all_opinions
        
        # 목표가 통계
        if target_prices:
            prices = [item["price"] for item in target_prices if item["price"] is not None]
            if prices:
                result["avg_target_price"] = sum(prices) / len(prices)
                result["max_target_price"] = max(prices)
                result["min_target_price"] = min(prices)
        
        result["opinions"] = all_opinions
        result["target_prices"] = target_prices
        result["recent_opinions"] = recent_opinions
        
        return result
    
    def _determine_data_priorities(self, question_type: int, has_telegram: bool,
                                has_report: bool, has_financial: bool, has_industry: bool) -> Dict[str, float]:
        """
        질문 유형에 따라 데이터 소스의 우선순위 결정
        
        Args:
            question_type: 질문 유형 (0: 기본정보, 1: 전망, 2: 재무분석, 3: 산업동향, 4: 기타)
            has_telegram: 텔레그램 데이터 존재 여부
            has_report: 리포트 데이터 존재 여부
            has_financial: 재무 데이터 존재 여부
            has_industry: 산업 데이터 존재 여부
            
        Returns:
            각 소스별 우선순위 가중치
        """
        # 기본 가중치
        weights = {
            "telegram": 0.25,
            "report": 0.25,
            "financial": 0.25,
            "industry": 0.25
        }
        
        # 질문 유형별 가중치 조정
        if question_type == 0:  # 종목 기본 정보
            weights = {
                "telegram": 0.3,
                "report": 0.4,
                "financial": 0.2,
                "industry": 0.1
            }
        elif question_type == 1:  # 전망
            weights = {
                "telegram": 0.3,
                "report": 0.4,
                "financial": 0.2,
                "industry": 0.1
            }
        elif question_type == 2:  # 재무 분석
            weights = {
                "telegram": 0.1,
                "report": 0.3,
                "financial": 0.5,
                "industry": 0.1
            }
        elif question_type == 3:  # 산업 동향
            weights = {
                "telegram": 0.2,
                "report": 0.3,
                "financial": 0.1,
                "industry": 0.4
            }
        
        # 데이터 존재 여부에 따라 가중치 조정
        if not has_telegram:
            weights["telegram"] = 0
        if not has_report:
            weights["report"] = 0
        if not has_financial:
            weights["financial"] = 0
        if not has_industry:
            weights["industry"] = 0
        
        # 가중치 합이 0인 경우 처리
        total_weight = sum(weights.values())
        if total_weight == 0:
            # 모든 소스에 동일한 가중치 부여
            available_sources = []
            if has_telegram:
                available_sources.append("telegram")
            if has_report:
                available_sources.append("report")
            if has_financial:
                available_sources.append("financial")
            if has_industry:
                available_sources.append("industry")
            
            if available_sources:
                equal_weight = 1.0 / len(available_sources)
                for source in available_sources:
                    weights[source] = equal_weight
        elif total_weight != 1.0:
            # 가중치 정규화
            for source in weights:
                weights[source] = weights[source] / total_weight
        
        return weights 