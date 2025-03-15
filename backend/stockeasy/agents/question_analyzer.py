"""
질문 분석 에이전트

이 모듈은 사용자 질문을 분석하고 분류하는 에이전트를 정의합니다.
분류 결과는 다른 에이전트들이 참조하여 효율적인 정보 검색에 활용합니다.
"""

from typing import Dict, Any, List, Optional
import re
from datetime import datetime
from loguru import logger

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser

from stockeasy.agents.base import BaseAgent
from stockeasy.models.agent_io import AgentState, QuestionClassification
from common.core.config import settings


class QuestionAnalyzerAgent(BaseAgent):
    """사용자 질문을 분석하고 분류하는 에이전트"""
    
    def __init__(self):
        """에이전트 초기화"""
        super().__init__("question_analyzer")
        self.llm = ChatOpenAI(
            model=settings.OPENAI_MODEL_NAME,
            temperature=0.0,
            api_key=settings.OPENAI_API_KEY
        )
        self.parser = JsonOutputParser()
    
    async def process(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        질문을 분석하고 분류합니다.
        
        Args:
            state: 현재 상태 (query, stock_code, stock_name 등 포함)
            
        Returns:
            업데이트된 상태 (classification 추가)
        """
        try:
            query = state.get("query", "")
            stock_code = state.get("stock_code")
            stock_name = state.get("stock_name")
            
            if not query:
                return {
                    **state,
                    "errors": state.get("errors", []) + [{
                        "agent": self.get_name(),
                        "error": "질문이 제공되지 않았습니다.",
                        "type": "InvalidInputError",
                        "timestamp": datetime.now()
                    }],
                    "processing_status": {
                        **state.get("processing_status", {}),
                        "question_analyzer": "error"
                    }
                }
            
            # 질문 분석 프롬프트 생성
            prompt = self._create_prompt(query, stock_code, stock_name)
            
            # LLM으로 질문 분석
            chain = prompt | self.llm | self.parser
            classification_result = await chain.ainvoke({})
            
            # 분류 결과 후처리
            classification = self._postprocess_classification(classification_result, stock_code, stock_name)
            
            # 날짜 관련 키워드 추출
            time_range = self._extract_time_range(query)
            if time_range:
                classification["시간범위"] = time_range
            
            # 상태 업데이트
            return {
                **state,
                "classification": classification,
                "processing_status": {
                    **state.get("processing_status", {}),
                    "question_analyzer": "completed"
                }
            }
            
        except Exception as e:
            logger.error(f"질문 분석 중 오류 발생: {e}", exc_info=True)
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
                    "question_analyzer": "error"
                }
            }
    
    def _create_prompt(self, query: str, stock_code: Optional[str] = None, stock_name: Optional[str] = None) -> ChatPromptTemplate:
        """질문 분석을 위한 프롬프트 생성"""
        template = """
당신은 금융 질문 분석 전문가입니다. 다음 사용자 질문을 세밀하게 분석하세요:

사용자 질문: {query}
{stock_info}

1. 질문 분류:
   - 질문주제: [0: 종목기본정보, 1: 전망, 2: 재무분석, 3: 산업동향, 4: 기타]
   - 답변수준: [0: 간단한답변, 1: 긴설명요구, 2: 종합적판단, 3: 전문가분석]

2. 식별된 엔티티:
   - 종목명: {extracted_stock_name}
   - 종목코드: {extracted_stock_code}
   - 산업분류: (관련 산업 또는 섹터 식별)

3. 필요한 데이터 소스:
   - 텔레그램 메시지 관련도: [높음/중간/낮음]
   - 기업리포트 관련도: [높음/중간/낮음]
   - 사업보고서 관련도: [높음/중간/낮음]
   - 산업분석 관련도: [높음/중간/낮음]

JSON 형식으로 응답하세요. 예시:
{
  "질문주제": 1,
  "답변수준": 2,
  "종목명": "삼성전자",
  "종목코드": "005930",
  "산업분류": "반도체",
  "텔레그램 메시지 관련도": "높음",
  "기업리포트 관련도": "높음",
  "사업보고서 관련도": "중간",
  "산업분석 관련도": "높음"
}
"""
        # 주어진 종목 정보가 있을 경우 포함
        stock_info = ""
        if stock_code or stock_name:
            stock_info = f"종목 정보: {stock_name or ''} ({stock_code or ''})"
        
        # 프롬프트 생성
        return ChatPromptTemplate.from_template(template).partial(
            query=query,
            stock_info=stock_info,
            extracted_stock_code=stock_code or "(질문에서 추출)",
            extracted_stock_name=stock_name or "(질문에서 추출)"
        )
    
    def _postprocess_classification(self, classification: Dict[str, Any], 
                                   stock_code: Optional[str] = None, 
                                   stock_name: Optional[str] = None) -> QuestionClassification:
        """
        분류 결과를 후처리합니다.
        
        Args:
            classification: LLM이 생성한 분류 결과
            stock_code: 사용자가 제공한 종목 코드
            stock_name: 사용자가 제공한 종목명
            
        Returns:
            처리된 분류 결과
        """
        result: QuestionClassification = {}
        
        # 정수형 값으로 변환
        if "질문주제" in classification:
            try:
                result["질문주제"] = int(classification["질문주제"])
            except (ValueError, TypeError):
                result["질문주제"] = 4  # 기타
                
        if "답변수준" in classification:
            try:
                result["답변수준"] = int(classification["답변수준"])
            except (ValueError, TypeError):
                result["답변수준"] = 1  # 긴설명요구
        
        # 종목 정보 처리
        if stock_code:
            result["종목코드"] = stock_code
        elif "종목코드" in classification and classification["종목코드"] not in ["(질문에서 추출)", ""]:
            result["종목코드"] = classification["종목코드"]
            
        if stock_name:
            result["종목명"] = stock_name
        elif "종목명" in classification and classification["종목명"] not in ["(질문에서 추출)", ""]:
            result["종목명"] = classification["종목명"]
        
        # 산업분류 처리
        if "산업분류" in classification and classification["산업분류"] not in ["(관련 산업 또는 섹터 식별)", ""]:
            result["산업분류"] = classification["산업분류"]
            
        # 데이터 소스 관련도 처리
        data_sources = ["텔레그램 메시지 관련도", "기업리포트 관련도", "사업보고서 관련도", "산업분석 관련도"]
        for source in data_sources:
            if source in classification:
                result[source] = classification[source]
        
        return result
    
    def _extract_time_range(self, query: str) -> Optional[str]:
        """
        질문에서 시간 범위 관련 정보를 추출합니다.
        
        Args:
            query: 사용자 질문
            
        Returns:
            추출된 시간 범위 또는 None
        """
        # 현재 년도
        current_year = datetime.now().year
        
        # 시간 관련 키워드 패턴
        year_pattern = r'(20\d{2})년'  # 20XX년
        quarter_pattern = r'(\d)분기'   # X분기
        month_pattern = r'(\d{1,2})월'  # X월
        
        # 상대적 시간 패턴
        relative_patterns = [
            r'최근', r'지난', r'이번', r'작년', r'전년', 
            r'올해', r'내년', r'다음 해',
            r'현재'
        ]
        
        # 시간 패턴 매칭
        time_info = []
        
        # 연도 매칭
        year_matches = re.findall(year_pattern, query)
        if year_matches:
            for year in year_matches:
                if 2010 <= int(year) <= current_year + 2:  # 합리적인 연도 범위
                    time_info.append(f"{year}년")
        
        # 분기 매칭
        quarter_matches = re.findall(quarter_pattern, query)
        if quarter_matches:
            for quarter in quarter_matches:
                if 1 <= int(quarter) <= 4:
                    time_info.append(f"{quarter}분기")
        
        # 월 매칭
        month_matches = re.findall(month_pattern, query)
        if month_matches:
            for month in month_matches:
                if 1 <= int(month) <= 12:
                    time_info.append(f"{month}월")
        
        # 상대적 시간 매칭
        for pattern in relative_patterns:
            if re.search(pattern, query):
                time_info.append(pattern)
        
        # 결과 반환
        if time_info:
            return ", ".join(time_info)
        
        return None 