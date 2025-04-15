"""
매출 및 수주 현황 분석 에이전트

한국 상장 기업의 사업보고서에서 매출 및 수주 관련 정보를 추출하고 구조화합니다.
"""

import re
import json
import asyncio
from typing import Dict, List, Any, Optional, cast, Tuple
from datetime import datetime, timedelta
from loguru import logger

from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import JsonOutputParser
from langchain.prompts import PromptTemplate
from langchain_core.messages import AIMessage

from stockeasy.prompts.revenue_breakdown_prompt import REVENUE_BREAKDOWN_SYSTEM_PROMPT, REVENUE_BREAKDOWN_USER_PROMPT, REVENUE_BREAKDOWN_SYSTEM_PROMPT2
from common.core.config import settings
from stockeasy.services.financial.data_service import FinancialDataService
from stockeasy.services.financial.stock_info_service import StockInfoService
from stockeasy.models.agent_io import RetrievedAllAgentData, FinancialData
from common.services.agent_llm import get_llm_for_agent, get_agent_llm
from common.models.token_usage import ProjectType
from stockeasy.agents.base import BaseAgent
from sqlalchemy.ext.asyncio import AsyncSession

class RevenueBreakdownAgent(BaseAgent):
    """매출 및 수주 현황 분석 에이전트"""

    def __init__(self, name: Optional[str] = None, db: Optional[AsyncSession] = None):
        """
        매출 및 수주 현황 분석 에이전트 초기화
        
        Args:
            name: 에이전트 이름 (지정하지 않으면 클래스명 사용)
            db: 데이터베이스 세션 객체 (선택적)
        """
        super().__init__(name, db)
        self.agent_llm = get_agent_llm("revenue_breakdown_agent")
        logger.info(f"RevenueBreakdownAgent initialized with provider: {self.agent_llm.get_provider()}, model: {self.agent_llm.get_model_name()}")
        self.financial_service = FinancialDataService()
        self.stock_service = StockInfoService()
        self.prompt_template = REVENUE_BREAKDOWN_SYSTEM_PROMPT2
        logger.info(f"RevenueBreakdownAgent 구현 완료 - 매출 및 수주 현황 정보 추출 준비 완료")

    

    async def process(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        매출 및 수주 현황 분석을 수행합니다.
        
        Args:
            state: 현재 상태 정보를 포함하는 딕셔너리
            
        Returns:
            업데이트된 상태 딕셔너리
        """
        try:
            # 성능 측정 시작
            start_time = datetime.now()
            logger.info("RevenueBreakdownAgent 처리 시작")
            
            # 현재 쿼리 및 세션 정보 추출
            query = state.get("query", "")
            
            # 질문 분석 결과 추출
            question_analysis = state.get("question_analysis", {})
            entities = question_analysis.get("entities", {})
            classification = question_analysis.get("classification", {})
            data_requirements = question_analysis.get("data_requirements", {})
            
            # 엔티티에서 종목 정보 추출
            stock_code = entities.get("stock_code", state.get("stock_code"))
            stock_name = entities.get("stock_name", state.get("stock_name"))
            
            if not stock_code and not stock_name:
                logger.warning("매출 및 수주 분석을 위한 종목 정보가 없습니다.")
                self._add_error(state, "매출 및 수주 분석을 위한 종목 정보가 없습니다.")
                return self._set_error_state(state, "종목 정보 없음")
                
            logger.info(f"RevenueBreakdownAgent 종목 분석: {stock_code or stock_name}")
            
            # 종목 코드가 없으면 종목명으로 조회
            if not stock_code and stock_name:
                stock_info = await self.stock_service.get_stock_by_name(stock_name)
                if stock_info:
                    stock_code = stock_info.get("code")
                    logger.info(f"{stock_name}에 대한 종목 코드 {stock_code} 찾음")
                    
            if not stock_code:
                logger.warning(f"{stock_name}에 대한 종목 코드를 찾을 수 없습니다.")
                self._add_error(state, f"종목 코드를 찾을 수 없습니다: {stock_name}")
                return self._set_error_state(state, f"종목 코드를 찾을 수 없음: {stock_name}")
                
            # 분석 기간 파악
            date_range = self._determine_date_range(query, data_requirements)
            logger.info(f"분석 기간: {date_range}")
            
            # 재무 데이터 조회 (GCS에서 PDF 파일을 가져와서 처리)
            revenue_breakdown_data = await self.financial_service.get_financial_revenue_breakdown(stock_code, date_range)
            
            if not revenue_breakdown_data or len(revenue_breakdown_data) == 0:
                logger.warning(f"종목 {stock_code}에 대한 재무(매출,수주)  데이터를 찾을 수 없습니다.")
                return self._set_error_state(state, "재무(매출,수주) 데이터를 찾을 수 없음", start_time)
            
            # 매출 및 수주 데이터 추출 및 분석
            analysis_results = await self._analyze_revenue_breakdown(
                revenue_breakdown_data,
                query,
                stock_code,
                stock_name or ""
            )
            
            # 실행 시간 계산
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            # 성공 상태 설정
            state["agent_results"] = state.get("agent_results", {})
            state["agent_results"]["revenue_breakdown"] = {
                "agent_name": "revenue_breakdown",
                "status": "success",
                "data": analysis_results,
                "error": None,
                "execution_time": duration,
                "metadata": {
                    "stock_code": stock_code,
                    "stock_name": stock_name,
                    "date_range": date_range
                }
            }
            
            # 타입 주석을 사용한 데이터 할당
            if "retrieved_data" not in state:
                state["retrieved_data"] = {}
            retrieved_data = cast(RetrievedAllAgentData, state["retrieved_data"])
            
            # 검색된 데이터가 없을 경우 빈 리스트로 초기화
            if not hasattr(retrieved_data, "revenue_breakdown"):
                retrieved_data["revenue_breakdown"] = []
            
            # 데이터 추가
            retrieved_data["revenue_breakdown"].append(analysis_results)
            
            state["processing_status"] = state.get("processing_status", {})
            state["processing_status"]["revenue_breakdown"] = "completed"
            logger.info(f"RevenueBreakdownAgent processing_status: {state['processing_status']}")
            
            # 메트릭 기록
            state["metrics"] = state.get("metrics", {})
            state["metrics"]["revenue_breakdown"] = {
                "start_time": start_time,
                "end_time": end_time,
                "duration": duration,
                "status": "completed",
                "error": None,
                "model_name": self.agent_llm.get_model_name()
            }
            
            logger.info(f"RevenueBreakdownAgent {duration:.2f}초 내에 완료됨")
            return state
            
        except Exception as e:
            logger.exception(f"RevenueBreakdownAgent 처리 중 오류: {str(e)}")
            return self._set_error_state(state, str(e)) 

    def _set_error_state(self, state: Dict[str, Any], error_message: str, start_time: datetime = None) -> Dict[str, Any]:
        """
        오류 상태를 설정합니다.
        
        Args:
            state: 현재 상태
            error_message: 오류 메시지
            start_time: 시작 시간 (선택적)
            
        Returns:
            업데이트된 상태
        """
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds() if start_time else 0
        
        # 상태 업데이트
        state["agent_results"] = state.get("agent_results", {})
        state["agent_results"]["revenue_breakdown"] = {
            "agent_name": "revenue_breakdown",
            "status": "failed",
            "data": {},
            "error": error_message,
            "execution_time": duration,
            "metadata": {}
        }
        
        # 타입 주석을 사용한 데이터 할당
        if "retrieved_data" not in state:
            state["retrieved_data"] = {}
        
        # 처리 상태 업데이트
        state["processing_status"] = state.get("processing_status", {})
        state["processing_status"]["revenue_breakdown"] = "error"
        
        return state
        
    def _determine_date_range(self, query: str, data_requirements: Dict[str, Any]) -> Dict[str, datetime]:
        """
        질문과 데이터 요구사항을 기반으로 분석할 날짜 범위를 결정합니다.
        기본적으로 최근 1년(4개 분기) 데이터만 확인합니다.
        
        Args:
            query: 사용자 쿼리
            data_requirements: 데이터 요구사항
            
        Returns:
            날짜 범위 (시작일, 종료일)
        """
        # 현재 날짜 기준
        end_date = datetime.now()
        
        # 기본값: 최근 1년 데이터
        start_date = end_date - timedelta(days=420)
        
        return {"start_date": start_date, "end_date": end_date}

    async def _prepare_financial_data(self, financial_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        PDF에서 추출한 재무 데이터를 분석 가능한 형식으로 변환합니다.
        
        Args:
            financial_data: PDF에서 추출한 재무 데이터
            
        Returns:
            분석 가능한 형식의 재무 데이터 리스트
        """
        reports = financial_data.get("reports", {})
        stock_code = financial_data.get("stock_code", "")
        formatted_data = []
        
        for key, report in reports.items():
            metadata = report.get("metadata", {})
            content = report.get("content", "")
            
            # 보고서 데이터 구조화
            year = int(metadata.get("year", ""))
            report_type = metadata.get('type')
            # if report_type.lower() == "annual":
            #     year = year - 1

            formatted_report = {
                "source": f"{year}년 {self._get_report_type_name(report_type)} 보고서",
                "date": metadata.get("date", ""),
                "content": content,
                "type": report_type,
                "year": year,
                "metadata": metadata
            }
            
            formatted_data.append(formatted_report)
        
        # 날짜 기준으로 정렬 (최신 데이터가 앞에 오도록)
        formatted_data.sort(key=lambda x: (x["year"], self._get_report_order(x["type"])), reverse=True)
        
        return formatted_data
    
    def _get_report_type_name(self, report_type: str) -> str:
        """
        보고서 유형의 한글 이름을 반환합니다.
        
        Args:
            report_type: 보고서 유형 코드
            
        Returns:
            보고서 유형 한글 이름
        """
        report_type_map = {
            "Q1": "1분기",
            "Q3": "3분기",
            "semiannual": "반기",
            "annual": "연간"
        }
        return report_type_map.get(report_type, report_type)
    
    def _get_report_order(self, report_type: str) -> int:
        """
        보고서 유형의 순서 값을 반환합니다.
        
        Args:
            report_type: 보고서 유형 코드
            
        Returns:
            정렬을 위한 순서 값
        """
        report_order_map = {
            "annual": 4,
            "Q3": 3,
            "semiannual": 2,
            "Q1": 1
        }
        return report_order_map.get(report_type.lower(), 0)
        
    async def _analyze_revenue_breakdown(self, 
                                  revenue_breakdown_data: str,
                                  query: str,
                                  stock_code: str,
                                  stock_name: str) -> Dict[str, Any]:
        """
        매출 및 수주 현황 데이터를 분석합니다.
        
        Args:
            revenue_breakdown_data: 사업보고서에서 4. 매출 및 수주상황, II. 사업의 내용 추출./
            query: 사용자 쿼리
            stock_code: 종목 코드
            stock_name: 종목명
            
        Returns:
            분석 결과
        """
        try:
            # 데이터 준비
            # revenue_breakdown_data = await self._extract_revenue_breakdown_data(revenue_breakdown_data)
            
            # # 매출 및 수주 관련 데이터를 문자열로 변환
            # data_str = self._format_revenue_data(revenue_breakdown_data)
            
            # 메시지 구성
            from langchain_core.messages import SystemMessage, HumanMessage
            
            messages = [
                SystemMessage(content=REVENUE_BREAKDOWN_SYSTEM_PROMPT2),
                HumanMessage(content=REVENUE_BREAKDOWN_USER_PROMPT.format(
                                            query=query, 
                                            stock_code=stock_code, 
                                            stock_name=stock_name, 
                                            revenue_breakdown_data=revenue_breakdown_data))

            ]
            
            # LLM 호출
            user_context = {}
            user_id = user_context.get("user_id", None)
            
            # 폴백 메커니즘을 사용하여 LLM 호출
            response: AIMessage = await self.agent_llm.ainvoke_with_fallback(
                messages,
                user_id=user_id,
                project_type=ProjectType.STOCKEASY,
                db=self.db
            )
            
            # 응답 처리 및 JSON 변환
            analysis_content = response.content if response else "분석 결과를 생성할 수 없습니다."
            
            # # JSON 추출
            # try:
            #     # JSON 부분 추출
            #     json_text = self._extract_json_from_text(analysis_content)
            #     result = json.loads(json_text) if json_text else {}
            # except Exception as e:
            #     logger.error(f"JSON 파싱 오류: {str(e)}")
            #     # 오류 시 원본 텍스트 반환
            #     result = {"raw_response": analysis_content}
            
            # return {
            #     "stock_code": stock_code,
            #     "stock_name": stock_name,
            #     "analysis": result,
            #     "source_data": "데이터 있음"  # 원본 데이터는 너무 길어서 간략하게 표시
            # }
            return analysis_content
            
        except Exception as e:
            logger.exception(f"매출 및 수주 분석 중 오류: {str(e)}")
            return {
                "stock_code": stock_code,
                "stock_name": stock_name,
                "analysis": {"error": f"매출 및 수주 분석 중 오류 발생: {str(e)}"},
                "source_data": "오류 발생"
            } 

    async def _extract_revenue_breakdown_data(self, formatted_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        매출 및 수주 관련 데이터를 추출합니다.
        
        Args:
            formatted_data: 포맷된 재무 데이터
            
        Returns:
            매출 및 수주 관련 데이터
        """
        result = []
        
        for report in formatted_data:
            content = report.get("content", "")
            
            # 매출 및 수주 관련 텍스트 섹션 찾기
            sales_section = self._extract_sales_and_order_section(content)
            
            # 해당 섹션이 없으면 전체 컨텐츠를 사용
            section_text = sales_section if sales_section else content
            
            # 특정 키워드가 포함된 페이지나 섹션 찾기
            revenue_data = {
                "source": report.get("source", ""),
                "date": report.get("date", ""),
                "year": report.get("year", ""),
                "type": report.get("type", ""),
                "content": section_text,
                "key_sections": {
                    "매출처": self._extract_key_customer_data(section_text),
                    "수주현황": self._extract_order_data(section_text),
                    "사업부문별매출": self._extract_business_segment_data(section_text),
                    "제품별매출": self._extract_product_data(section_text),
                    "지역별매출": self._extract_regional_data(section_text)
                }
            }
            
            result.append(revenue_data)
        
        return result
        
    def _extract_sales_and_order_section(self, text: str) -> str:
        """
        사업보고서에서 매출 및 수주 현황 관련 섹션을 추출합니다.
        
        Args:
            text: 전체 보고서 텍스트
            
        Returns:
            매출 및 수주 현황 관련 섹션
        """
        # 섹션 시작 패턴들
        section_start_patterns = [
            r"(?:^|\n)\s*[가-힣\s]*매출\s*현황[가-힣\s]*(?:\n|$)",
            r"(?:^|\n)\s*[가-힣\s]*매출\s*및\s*수주\s*상황[가-힣\s]*(?:\n|$)",
            r"(?:^|\n)\s*[가-힣\s]*수주\s*현황[가-힣\s]*(?:\n|$)",
            r"(?:^|\n)\s*[0-9]+\.\s*매출\s*현황[가-힣\s]*(?:\n|$)",
            r"(?:^|\n)\s*[0-9]+\.\s*매출\s*및\s*수주\s*상황[가-힣\s]*(?:\n|$)",
            r"(?:^|\n)\s*[가나다라마바사아자차카타파하]\.\s*매출\s*현황[가-힣\s]*(?:\n|$)",
            r"(?:^|\n)\s*[가나다라마바사아자차카타파하]\.\s*매출\s*및\s*수주\s*상황[가-힣\s]*(?:\n|$)",
            r"(?:^|\n)\s*[①②③④⑤⑥⑦⑧⑨⑩]\s*매출\s*현황[가-힣\s]*(?:\n|$)",
            r"(?:^|\n)\s*[①②③④⑤⑥⑦⑧⑨⑩]\s*매출\s*및\s*수주\s*상황[가-힣\s]*(?:\n|$)",
            r"(?:^|\n)\s*사업부문별\s*매출\s*현황[가-힣\s]*(?:\n|$)",
            r"(?:^|\n)\s*제품별\s*매출\s*현황[가-힣\s]*(?:\n|$)",
            r"(?:^|\n)\s*지역별\s*매출\s*현황[가-힣\s]*(?:\n|$)"
        ]
        
        # 섹션 끝 패턴들 (다음 섹션의 시작)
        section_end_patterns = [
            r"(?:^|\n)\s*[0-9]+\.\s*판매경로[가-힣\s]*(?:\n|$)",
            r"(?:^|\n)\s*[0-9]+\.\s*시장점유율[가-힣\s]*(?:\n|$)",
            r"(?:^|\n)\s*[0-9]+\.\s*시장의\s*특성[가-힣\s]*(?:\n|$)",
            r"(?:^|\n)\s*[0-9]+\.\s*신규사업[가-힣\s]*(?:\n|$)",
            r"(?:^|\n)\s*[0-9]+\.\s*외부자금조달[가-힣\s]*(?:\n|$)",
            r"(?:^|\n)\s*[0-9]+\.\s*부동산[가-힣\s]*(?:\n|$)",
            r"(?:^|\n)\s*[0-9]+\.\s*투자계획[가-힣\s]*(?:\n|$)",
            r"(?:^|\n)\s*[가나다라마바사아자차카타파하]\.\s*판매경로[가-힣\s]*(?:\n|$)",
            r"(?:^|\n)\s*[가나다라마바사아자차카타파하]\.\s*시장점유율[가-힣\s]*(?:\n|$)",
            r"(?:^|\n)\s*[가나다라마바사아자차카타파하]\.\s*시장의\s*특성[가-힣\s]*(?:\n|$)",
            r"(?:^|\n)\s*III\.[가-힣\s]*(?:\n|$)",  # 다음 큰 섹션 (예: III. 재무에 관한 사항)
            r"(?:^|\n)\s*Ⅲ\.[가-힣\s]*(?:\n|$)"    # 다음 큰 섹션 (유니코드 로마자)
        ]
        
        # 가장 먼저 나오는 섹션 시작 패턴 찾기
        start_pos = -1
        start_pattern_used = None
        
        for pattern in section_start_patterns:
            match = re.search(pattern, text)
            if match and (start_pos == -1 or match.start() < start_pos):
                start_pos = match.start()
                start_pattern_used = pattern
        
        if start_pos == -1:
            # 섹션 시작을 찾지 못한 경우, 키워드 기반으로 찾기
            keywords = ["매출", "수주", "사업부문별", "제품별", "지역별"]
            for keyword in keywords:
                pos = text.find(keyword)
                if pos != -1 and (start_pos == -1 or pos < start_pos):
                    # 키워드 앞의 줄 시작 위치 찾기
                    line_start = text.rfind("\n", 0, pos)
                    if line_start == -1:
                        line_start = 0
                    else:
                        line_start += 1  # \n 다음 위치
                    
                    start_pos = line_start
            
            # 그래도 못 찾으면 전체 텍스트 반환
            if start_pos == -1:
                return text
        
        # 해당 시작점 이후에 나오는 첫 번째 섹션 끝 패턴 찾기
        end_pos = -1
        
        for pattern in section_end_patterns:
            match = re.search(pattern, text[start_pos:])
            if match:
                # 상대적 위치를 절대 위치로 변환
                current_end = start_pos + match.start()
                if end_pos == -1 or current_end < end_pos:
                    end_pos = current_end
        
        # 끝 패턴을 찾지 못한 경우 텍스트 끝까지
        if end_pos == -1:
            end_pos = len(text)
        
        # 매출 및 수주 섹션 추출
        return text[start_pos:end_pos]
        
    def _extract_key_customer_data(self, text: str) -> str:
        """
        주요 매출처 정보를 추출합니다.
        
        Args:
            text: 섹션 텍스트
            
        Returns:
            주요 매출처 관련 텍스트
        """
        # 주요 매출처 관련 패턴
        patterns = [
            r"(?:^|\n).*?주요.*?(?:매출처|거래처|고객).*?(?:\n|$)([\s\S]*?)(?:\n\s*[0-9가-힣①-⑩]+\.|\n\s*$|$)",
            r"(?:^|\n).*?(?:매출처|거래처|고객).*?(?:현황|구성).*?(?:\n|$)([\s\S]*?)(?:\n\s*[0-9가-힣①-⑩]+\.|\n\s*$|$)"
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1).strip()
        
        # 키워드 주변 텍스트 찾기
        keywords = ["주요 매출처", "주요 거래처", "주요 고객", "매출처별", "거래처별"]
        for keyword in keywords:
            index = text.find(keyword)
            if index != -1:
                # 키워드가 포함된 문단 찾기
                start = text.rfind("\n", 0, index) + 1
                end = text.find("\n\n", index)
                if end == -1:
                    end = len(text)
                
                # 문단 앞뒤로 더 넓게 추출 (테이블 포함 가능성)
                start_extended = max(0, start - 200)
                end_extended = min(len(text), end + 500)
                
                return text[start_extended:end_extended].strip()
        
        return ""
        
    def _extract_order_data(self, text: str) -> str:
        """
        수주 현황 정보를 추출합니다.
        
        Args:
            text: 섹션 텍스트
            
        Returns:
            수주 현황 관련 텍스트
        """
        # 수주 현황 관련 패턴
        patterns = [
            r"(?:^|\n).*?수주.*?(?:현황|상황|실적|내역).*?(?:\n|$)([\s\S]*?)(?:\n\s*[0-9가-힣①-⑩]+\.|\n\s*$|$)",
            r"(?:^|\n).*?(?:수주잔고|수주량|계약).*?(?:\n|$)([\s\S]*?)(?:\n\s*[0-9가-힣①-⑩]+\.|\n\s*$|$)"
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1).strip()
        
        # 키워드 주변 텍스트 찾기
        keywords = ["수주 현황", "수주 계약", "수주 잔고", "수주실적", "계약실적"]
        for keyword in keywords:
            index = text.find(keyword)
            if index != -1:
                # 키워드가 포함된 더 넓은 범위 추출 (테이블 포함 가능성)
                start = max(0, index - 100)
                end = min(len(text), index + 1000)  # 수주 테이블은 큰 경우가 많음
                
                return text[start:end].strip()
        
        return ""
        
    def _extract_business_segment_data(self, text: str) -> str:
        """
        사업부문별 매출 현황 정보를 추출합니다.
        
        Args:
            text: 섹션 텍스트
            
        Returns:
            사업부문별 매출 현황 관련 텍스트
        """
        # 사업부문별 매출 현황 관련 패턴
        patterns = [
            r"(?:^|\n).*?사업부문별.*?(?:매출|실적|현황).*?(?:\n|$)([\s\S]*?)(?:\n\s*[0-9가-힣①-⑩]+\.|\n\s*$|$)",
            r"(?:^|\n).*?부문별.*?(?:매출|실적).*?(?:\n|$)([\s\S]*?)(?:\n\s*[0-9가-힣①-⑩]+\.|\n\s*$|$)",
            r"(?:^|\n).*?(?:사업)?부문별\s+매출.*?(?:\n|$)([\s\S]*?)(?:\n\s*[0-9가-힣①-⑩]+\.|\n\s*$|$)"
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1).strip()
        
        # 키워드 주변 텍스트 찾기
        keywords = ["사업부문별 매출", "부문별 매출", "사업부 매출", "사업 부문별", "부문별 실적"]
        for keyword in keywords:
            index = text.find(keyword)
            if index != -1:
                # 키워드가 포함된 더 넓은 범위 추출 (테이블 포함 가능성)
                start = max(0, index - 100)
                end = min(len(text), index + 800)
                
                return text[start:end].strip()
        
        return ""
        
    def _extract_product_data(self, text: str) -> str:
        """
        제품별 매출 현황 정보를 추출합니다.
        
        Args:
            text: 섹션 텍스트
            
        Returns:
            제품별 매출 현황 관련 텍스트
        """
        # 제품별 매출 현황 관련 패턴
        patterns = [
            r"(?:^|\n).*?제품별.*?(?:매출|실적|현황).*?(?:\n|$)([\s\S]*?)(?:\n\s*[0-9가-힣①-⑩]+\.|\n\s*$|$)",
            r"(?:^|\n).*?(?:제품|품목|상품).*?(?:매출|실적).*?(?:\n|$)([\s\S]*?)(?:\n\s*[0-9가-힣①-⑩]+\.|\n\s*$|$)",
            r"(?:^|\n).*?주요\s+제품.*?(?:\n|$)([\s\S]*?)(?:\n\s*[0-9가-힣①-⑩]+\.|\n\s*$|$)"
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1).strip()
        
        # 키워드 주변 텍스트 찾기
        keywords = ["제품별 매출", "품목별 매출", "주요 제품", "제품 및 서비스", "품목별 실적"]
        for keyword in keywords:
            index = text.find(keyword)
            if index != -1:
                # 키워드가 포함된 더 넓은 범위 추출 (테이블 포함 가능성)
                start = max(0, index - 100)
                end = min(len(text), index + 800)
                
                return text[start:end].strip()
        
        return ""
        
    def _extract_regional_data(self, text: str) -> str:
        """
        지역별 매출 현황 정보를 추출합니다.
        
        Args:
            text: 섹션 텍스트
            
        Returns:
            지역별 매출 현황 관련 텍스트
        """
        # 지역별 매출 현황 관련 패턴
        patterns = [
            r"(?:^|\n).*?지역별.*?(?:매출|실적|현황).*?(?:\n|$)([\s\S]*?)(?:\n\s*[0-9가-힣①-⑩]+\.|\n\s*$|$)",
            r"(?:^|\n).*?(?:국내|해외|수출|내수).*?(?:매출|실적).*?(?:\n|$)([\s\S]*?)(?:\n\s*[0-9가-힣①-⑩]+\.|\n\s*$|$)",
            r"(?:^|\n).*?수출[^\n]*?내수.*?(?:\n|$)([\s\S]*?)(?:\n\s*[0-9가-힣①-⑩]+\.|\n\s*$|$)"
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1).strip()
        
        # 키워드 주변 텍스트 찾기
        keywords = ["지역별 매출", "국내/해외", "수출/내수", "지역별 판매", "해외매출"]
        for keyword in keywords:
            index = text.find(keyword)
            if index != -1:
                # 키워드가 포함된 더 넓은 범위 추출 (테이블 포함 가능성)
                start = max(0, index - 100)
                end = min(len(text), index + 800)
                
                return text[start:end].strip()
        
        return ""
        
    def _format_revenue_data(self, revenue_data: List[Dict[str, Any]]) -> str:
        """
        매출 및 수주 관련 데이터를 문자열로 포맷팅합니다.
        
        Args:
            revenue_data: 매출 및 수주 관련 데이터
            
        Returns:
            포맷팅된 문자열
        """
        if not revenue_data:
            return "매출 및 수주 관련 데이터가 없습니다."
        
        result_strings = []
        
        for idx, item in enumerate(revenue_data):
            source = item.get("source", "알 수 없는 출처")
            date = item.get("date", "날짜 없음")
            key_sections = item.get("key_sections", {})
            
            data_str = f"[출처: {source} ({date})]\n\n"
            
            # 주요 섹션 추가
            for section_name, section_text in key_sections.items():
                if section_text:
                    data_str += f"## {section_name} 관련 정보:\n{section_text}\n\n"
            
            # 결과 문자열 목록에 추가
            result_strings.append(data_str)
        
        # 모든 포맷팅된 문자열을 구분선으로 연결하여 반환
        return "\n\n===== 보고서 구분선 =====\n\n".join(result_strings)
        
    def _extract_json_from_text(self, text: str) -> str:
        """
        텍스트에서 JSON 부분을 추출합니다.
        
        Args:
            text: 텍스트
            
        Returns:
            JSON 텍스트
        """
        # JSON 시작과 끝 찾기
        json_patterns = [
            r"```json\s*([\s\S]*?)\s*```",  # ```json ... ``` 형식
            r"```\s*([\s\S]*?)\s*```",      # ``` ... ``` 형식
            r"\{[\s\S]*\}"                   # { ... } 형식
        ]
        
        for pattern in json_patterns:
            matches = re.findall(pattern, text)
            if matches:
                # 가장 긴 매치를 반환 (완전한 JSON 객체일 가능성이 높음)
                return max(matches, key=len)
        
        # JSON 패턴을 찾지 못한 경우 전체 텍스트가 JSON인지 확인
        if text.strip().startswith("{") and text.strip().endswith("}"):
            return text
            
        return "" 