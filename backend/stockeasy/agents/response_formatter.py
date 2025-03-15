"""
응답 포매터 에이전트

이 모듈은 수집된 정보를 기반으로 최종 응답을 생성하는 에이전트를 정의합니다.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
from loguru import logger

from stockeasy.agents.base import BaseAgent

class ResponseFormatterAgent(BaseAgent):
    """수집된 정보를 기반으로 최종 응답을 생성하는 에이전트"""
    
    def __init__(self, should_enhance_response: bool = False):
        """
        에이전트 초기화
        
        Args:
            should_enhance_response: 응답 개선 여부
        """
        super().__init__("response_formatter")
        self.should_enhance_response = should_enhance_response
    
    async def process(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        수집된 정보와 요약을 기반으로 최종 응답을 생성합니다.
        
        Args:
            state: 현재 상태
            
        Returns:
            최종 응답이 포함된 업데이트된 상태
        """
        try:
            # 시작 시간 기록
            start_time = datetime.now()
            
            # 필요한 정보 추출
            query = state.get("query", "")
            stock_code = state.get("stock_code")
            stock_name = state.get("stock_name")
            classification = state.get("classification", {})
            telegram_data = state.get("telegram_data", [])
            report_data = state.get("report_data", [])
            summary = state.get("summary", "")
            integrated_knowledge = state.get("integrated_knowledge", {})
            
            # 응답 생성
            if not summary:
                if telegram_data or report_data:
                    # 데이터는 있지만 요약이 없는 경우
                    response = self._generate_simple_response(
                        query, 
                        stock_code, 
                        stock_name, 
                        telegram_data,
                        report_data,
                        integrated_knowledge
                    )
                else:
                    # 데이터가 없는 경우
                    response = self._generate_fallback_response(query, stock_code, stock_name)
            else:
                # 요약 기반 응답 생성
                response = self._format_response_with_summary(
                    summary, 
                    query, 
                    stock_code, 
                    stock_name, 
                    classification,
                    integrated_knowledge
                )
            
            # 응답 개선 (선택 사항)
            if self.should_enhance_response:
                response = await self._enhance_response(
                    response, 
                    query, 
                    stock_code, 
                    stock_name,
                    classification
                )
            
            # 투자 의견 및 목표가 정보 추가
            response = self._add_investment_opinions_if_available(response, integrated_knowledge)
            
            # 처리 시간 기록
            processing_time = (datetime.now() - start_time).total_seconds()
            
            # 상태 업데이트
            return {
                **state,
                "response": response,
                "response_generation_time": processing_time,
                "processing_status": {
                    **state.get("processing_status", {}),
                    "response_formatter": "completed"
                }
            }
            
        except Exception as e:
            logger.error(f"응답 포맷팅 중 오류 발생: {str(e)}", exc_info=True)
            return {
                **state,
                "errors": state.get("errors", []) + [{
                    "agent": self.get_name(),
                    "error": str(e),
                    "type": type(e).__name__,
                    "timestamp": datetime.now()
                }],
                "response": f"죄송합니다. 응답을 생성하는 중 오류가 발생했습니다. ({str(e)})",
                "processing_status": {
                    **state.get("processing_status", {}),
                    "response_formatter": "error"
                }
            }
    
    def _generate_fallback_response(self, query: str, stock_code: Optional[str], stock_name: Optional[str]) -> str:
        """
        데이터가 없는 경우의 폴백 응답 생성
        
        Args:
            query: 사용자 쿼리
            stock_code: 종목 코드
            stock_name: 종목명
            
        Returns:
            폴백 응답 텍스트
        """
        if stock_name:
            return f"""
# {stock_name}{f' ({stock_code})' if stock_code else ''} 관련 정보

죄송합니다. 현재 {stock_name}에 대한 "{query}" 질문에 답변할 수 있는 충분한 정보를 찾지 못했습니다.

다음과 같이 시도해 보세요:
1. 더 구체적인 질문으로 다시 시도해 보세요.
2. 다른 종목에 대해 문의해 보세요.
3. 일반적인 시장 동향이나 산업 정보에 대해 물어보세요.
"""
        else:
            return f"""
# 검색 결과

죄송합니다. "{query}"에 대한 충분한 정보를 찾지 못했습니다.

다음과 같이 시도해 보세요:
1. 더 구체적인 질문으로 다시 시도해 보세요.
2. 특정 종목명이나 종목코드를 포함하여 질문해 보세요.
3. 일반적인 시장 동향이나 산업 정보에 대해 물어보세요.
"""
    
    def _generate_simple_response(self, query: str, stock_code: Optional[str], stock_name: Optional[str],
                                telegram_data: List[Dict[str, Any]], report_data: List[Dict[str, Any]],
                                integrated_knowledge: Dict[str, Any]) -> str:
        """
        데이터는 있지만 요약이 없는 경우의 간단한 응답 생성
        
        Args:
            query: 사용자 쿼리
            stock_code: 종목 코드
            stock_name: 종목명
            telegram_data: 텔레그램 메시지 데이터
            report_data: 기업리포트 데이터
            integrated_knowledge: 통합된 지식 데이터
            
        Returns:
            응답 텍스트
        """
        response_parts = []
        
        # 주식 정보 헤더
        if stock_name:
            if stock_code:
                response_parts.append(f"# {stock_name} ({stock_code}) 관련 정보\n")
            else:
                response_parts.append(f"# {stock_name} 관련 정보\n")
        else:
            response_parts.append(f"# 검색 결과\n")
        
        # 투자 의견 및 목표가 정보
        investment_info = integrated_knowledge.get("investment_opinions", {})
        if investment_info and investment_info.get("opinions"):
            response_parts.append("\n## 투자의견 및 목표가\n")
            
            # 최근 투자의견
            recent_opinions = investment_info.get("recent_opinions", [])
            if recent_opinions:
                response_parts.append("\n### 최근 투자의견\n")
                for opinion in recent_opinions:
                    source = opinion.get("source", "미상")
                    date = opinion.get("date", "")
                    opinion_text = opinion.get("opinion", "")
                    target_price = opinion.get("target_price")
                    
                    opinion_line = f"- **{source}** ({date}): "
                    if opinion_text:
                        opinion_line += f"{opinion_text}"
                    if target_price:
                        opinion_line += f", 목표가 {target_price:,}원"
                    
                    response_parts.append(opinion_line + "\n")
            
            # 평균 목표가
            avg_price = investment_info.get("avg_target_price")
            if avg_price:
                response_parts.append(f"\n평균 목표가: **{avg_price:,.0f}원**\n")
        
        # 텔레그램 메시지 정보
        if telegram_data:
            response_parts.append("\n## 텔레그램 메시지\n")
            for i, message in enumerate(telegram_data[:5], 1):  # 상위 5개만
                content = message.get("content", "")
                created_at = message.get("created_at", "")
                
                if created_at:
                    response_parts.append(f"{i}. ({created_at}) {content}\n")
                else:
                    response_parts.append(f"{i}. {content}\n")
        
        # 기업리포트 정보
        if report_data:
            response_parts.append("\n## 기업리포트 정보\n")
            for i, report in enumerate(report_data[:3], 1):  # 상위 3개만
                content = report.get("content", "")
                source = report.get("source", "미상")
                date = report.get("date", "")
                
                # 내용 길이 제한
                if len(content) > 300:
                    content = content[:300] + "..."
                
                response_parts.append(f"{i}. **{source}** ({date})\n{content}\n\n")
        
        # 응답 조합
        response = "".join(response_parts)
        
        # 응답이 너무 짧으면 안내 문구 추가
        if len(response) < 100:
            response += "\n\n더 구체적인 질문을 해주시면 더 자세한 정보를 제공해 드릴 수 있습니다."
        
        return response
    
    def _format_response_with_summary(self, summary: str, query: str, stock_code: Optional[str],
                                    stock_name: Optional[str], classification: Dict[str, Any],
                                    integrated_knowledge: Dict[str, Any]) -> str:
        """
        요약 정보를 기반으로 응답 포맷팅
        
        Args:
            summary: 생성된 요약 텍스트
            query: 사용자 쿼리
            stock_code: 종목 코드
            stock_name: 종목명
            classification: 분류 결과
            integrated_knowledge: 통합된 지식 데이터
            
        Returns:
            포맷팅된 응답
        """
        response_parts = []
        
        # 주식 정보 헤더
        if stock_name:
            if stock_code:
                response_parts.append(f"# {stock_name} ({stock_code})\n\n")
            else:
                response_parts.append(f"# {stock_name}\n\n")
        
        # 요약 텍스트 추가
        response_parts.append(f"{summary}\n")
        
        # 투자 의견 섹션 (있는 경우만)
        investment_info = integrated_knowledge.get("investment_opinions", {})
        report_info = integrated_knowledge.get("report", {})
        
        # 전망 관련 질문이거나 투자의견이 있는 경우
        question_type = classification.get("질문주제", 4)
        if (question_type == 1 or investment_info) and "투자의견" not in summary.lower():
            # 요약에 이미 투자의견이 언급되어 있지 않은 경우만 추가
            self._append_investment_opinions(response_parts, investment_info, report_info)
        
        # 출처 정보 추가
        response_parts.append("\n---\n")
        response_parts.append("*이 정보는 최근 텔레그램 메시지와 기업리포트를 기반으로 작성되었습니다.*")
        
        return "".join(response_parts)
    
    def _append_investment_opinions(self, response_parts: List[str], 
                                  investment_info: Dict[str, Any],
                                  report_info: Dict[str, Any]) -> None:
        """
        투자의견 및 목표가 정보를 응답에 추가
        
        Args:
            response_parts: 응답 부분 리스트
            investment_info: 투자의견 정보
            report_info: 리포트 정보
        """
        if not investment_info:
            return
        
        # 최근 투자의견
        recent_opinions = investment_info.get("recent_opinions", [])
        if recent_opinions:
            response_parts.append("\n\n## 투자의견 및 목표가\n")
            
            for opinion in recent_opinions:
                source = opinion.get("source", "미상")
                date = opinion.get("date", "")
                opinion_text = opinion.get("opinion", "")
                target_price = opinion.get("target_price")
                
                opinion_line = f"- **{source}** ({date}): "
                if opinion_text:
                    opinion_line += f"{opinion_text}"
                if target_price:
                    opinion_line += f", 목표가 {target_price:,}원"
                
                response_parts.append(opinion_line + "\n")
        
        # 평균 목표가
        avg_price = investment_info.get("avg_target_price")
        if avg_price:
            response_parts.append(f"\n평균 목표가: **{avg_price:,.0f}원**\n")
        
        # 최고/최저 목표가
        max_price = investment_info.get("max_target_price")
        min_price = investment_info.get("min_target_price")
        
        if max_price and min_price and max_price != min_price:
            response_parts.append(f"목표가 범위: {min_price:,.0f}원 ~ {max_price:,.0f}원\n")
    
    def _add_investment_opinions_if_available(self, response: str, 
                                            integrated_knowledge: Dict[str, Any]) -> str:
        """
        투자 의견이 응답에 없는 경우 추가
        
        Args:
            response: 현재 응답 텍스트
            integrated_knowledge: 통합된 지식 데이터
            
        Returns:
            업데이트된 응답 텍스트
        """
        # 이미 투자의견 섹션이 있으면 변경하지 않음
        if "## 투자의견" in response or "##투자의견" in response:
            return response
        
        # 투자의견 정보 확인
        investment_info = integrated_knowledge.get("investment_opinions", {})
        if not investment_info or not investment_info.get("opinions"):
            return response
        
        # 응답 파싱
        response_parts = []
        
        # 응답에 '---' 구분선이 있으면 그 앞에 추가
        if "---" in response:
            parts = response.split("---", 1)
            response_parts.append(parts[0])
            
            # 투자의견 추가
            self._append_investment_opinions(
                response_parts, 
                investment_info, 
                integrated_knowledge.get("report", {})
            )
            
            # 구분선과 나머지 추가
            response_parts.append("\n---")
            response_parts.append(parts[1])
        else:
            # 구분선이 없으면 끝에 추가
            response_parts.append(response)
            
            # 투자의견 추가
            self._append_investment_opinions(
                response_parts, 
                investment_info, 
                integrated_knowledge.get("report", {})
            )
        
        return "".join(response_parts)
    
    async def _enhance_response(self, response: str, query: str, stock_code: Optional[str],
                              stock_name: Optional[str], classification: Dict[str, Any]) -> str:
        """
        응답 개선 (향후 구현)
        
        Args:
            response: 현재 응답 텍스트
            query: 사용자 쿼리
            stock_code: 종목 코드
            stock_name: 종목명
            classification: 분류 결과
            
        Returns:
            개선된 응답 텍스트
        """
        # 향후 구현 예정
        return response 