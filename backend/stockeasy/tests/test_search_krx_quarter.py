"""
리랭커 테스트 예제
"""

import asyncio
import json
import os
import re
import sys
from typing import Any, Dict, List
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from loguru import logger
from dotenv import load_dotenv
from common.core.config import settings
import fitz  # PyMuPDF 라이브러리
import pdfplumber
import glob
from pathlib import Path
from datetime import datetime, timedelta
# LangChain 관련 라이브러리
from langchain_core.prompts import ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.messages import AIMessage
# OpenAI 모델 임포트 추가
#from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from stockeasy.agents.financial_analyzer_agent import FinancialAnalyzerAgent
from backend.stockeasy.prompts.revenue_breakdown_prompt import format_financial_data
# markdown을 html로 변환하는 라이브러리 추가
import markdown

# 환경 변수 로드
load_dotenv()
# 설정 의존성 제거
# from dotenv import load_dotenv
# from common.core.config import settings
# from common.services.retrievers.models import DocumentWithScore

# 환경 변수 로드 대신 API 키 직접 설정 (실제 API 키로 교체해야 함)
# load_dotenv()
# GEMINI_API_KEY를 사용자가 입력해야 합니다
GEMINI_API_KEY = settings.GEMINI_API_KEY
# OpenAI API 키 설정
OPENAI_API_KEY = settings.OPENAI_API_KEY

async def test_all():
    # stockeasy/local_cache/financial_reports/정기보고서/103590
    base_dir = "stockeasy/local_cache/financial_reports/정기보고서"
    #code_list = ["005380","103590", "005930", "044340", "195870", "326030", "140410", "049800", "267260"]
    code_list = ["005380"]

    result = ""
    for code in code_list:
        r = await test_find매출(code, "24년 3분기의 영업이익은? 3개월", "24년 3분기")
        result += r
        print(f"code: {code}\n답변 : \n{r}\n\n")
    #print(result)
    return result

def _determine_year_range( query: str, data_requirements: Dict[str, Any]) -> int:
    """
    질문과 데이터 요구사항을 기반으로 분석할 연도 범위를 결정합니다.
    
    Args:
        query: 사용자 쿼리
        data_requirements: 데이터 요구사항
        
    Returns:
        연도 범위 (몇 년치 데이터를 분석할지)
    """
    # 기본값 설정
    default_range = 2
    
    # 데이터 요구사항에서 시간 범위 확인
    time_range = data_requirements.get("time_range", "")
    if isinstance(time_range, str) and time_range:
        # "최근 X년" 패턴
        recent_years_match = re.search(r'최근\s*(\d+)\s*년', time_range)
        if recent_years_match:
            years = int(recent_years_match.group(1))
            return min(max(years, 1), 5)  # 1~5년 사이로 제한
            
        # "최근 X개월" 패턴 - 1년 이하는 1년으로, 그 이상은 올림하여 연단위로 변환
        recent_months_match = re.search(r'최근\s*(\d+)\s*개월', time_range)
        if recent_months_match:
            months = int(recent_months_match.group(1))
            years = (months + 11) // 12  # 올림 나눗셈
            return min(max(years, 1), 5)
            
        # "YYYY년" 패턴 - 현재 연도와의 차이를 계산
        year_match = re.search(r'(20\d{2})년', time_range)
        if year_match:
            target_year = int(year_match.group(1))
            current_year = datetime.now().year
            return min(max(current_year - target_year + 1, 1), 5)
            
        # "X분기" 패턴 - 분기 데이터는 1년치로 처리
        quarter_match = re.search(r'(\d)분기', time_range)
        if quarter_match:
            return 1
    
    # 쿼리에서 연도 범위 파악
    year_patterns = [
        r"(\d+)년간",
        r"(\d+)년\s*동안",
        r"지난\s*(\d+)년",
        r"최근\s*(\d+)년",
        r"(\d+)년치",
        r"(\d+)년\s*데이터",
        r"(\d+)\s*년",
        r"(\d+)\s*years"
    ]
    
    for pattern in year_patterns:
        match = re.search(pattern, query)
        if match:
            try:
                year_range = int(match.group(1))
                return min(max(year_range, 1), 5)  # 1~5년 사이로 제한
            except ValueError:
                pass
    
    # 특정 키워드에 기반한 범위 결정
    if any(keyword in query or keyword in str(time_range) 
            for keyword in ["장기", "전체", "역대", "모든", "전부"]):
        return 5
    elif any(keyword in query or keyword in str(time_range)
            for keyword in ["중장기", "3년", "삼년"]):
        return 3
    elif any(keyword in query or keyword in str(time_range)
            for keyword in ["단기", "1년", "일년", "올해"]):
        return 1
        
    return default_range

def _determine_date_range(query: str, time_range:str) -> Dict[str, datetime]:
    """
    질문과 데이터 요구사항을 기반으로 분석할 날짜 범위를 결정합니다.
    
    Args:
        query: 사용자 쿼리
        data_requirements: 데이터 요구사항
        
    Returns:
        날짜 범위 (시작일, 종료일)
    """
    # 현재 날짜 기준
    end_date = datetime.now()
    start_date = end_date
    target_year = end_date.year
    default_years = 2
    
    # 데이터 요구사항에서 시간 범위 확인
    #time_range = data_requirements.get("time_range", "")
    if isinstance(time_range, str) and time_range:
        # "X분기" 패턴 - 분기 데이터만 처리
        quarter_match = re.search(r'(\d)분기', time_range)
        if quarter_match:
            short_year_match = re.search(r'(\d{2})년', time_range)
            if short_year_match:
                year_suffix = int(short_year_match.group(1))
                # 2000년대로 가정
                target_year = 2000 + year_suffix
            quarter = int(quarter_match.group(1))
            current_year = target_year
            
            # 분기 시작/종료일 계산
            if quarter == 1:
                start_date = datetime(current_year, 4, 1)
                end_date = datetime(current_year, 5, 16)
            elif quarter == 2:
                start_date = datetime(current_year, 7, 1)
                end_date = datetime(current_year, 8, 16)
            elif quarter == 3: # 3분기
                start_date = datetime(current_year, 10, 1)
                end_date = datetime(current_year, 11, 16)
            elif quarter == 4: # 4분기는 1~3월에 마감. 연간 사업보고서에는 4분기 실적이 따로 없으므로, 연간보고서 - 3분기실적 으로 처리.
                start_date = datetime(current_year, 10, 1)
                end_date = datetime(current_year+1, 3, 31)
            
            return {"start_date": start_date, "end_date": end_date}
        
        # "최근 X년" 패턴
        recent_years_match = re.search(r'최근\s*(\d+)\s*년', time_range)
        if recent_years_match:
            years = int(recent_years_match.group(1))
            years = min(max(years, 1), 5)  # 1~5년 사이로 제한
            start_date = end_date - timedelta(days=years*365)
            return {"start_date": start_date, "end_date": end_date}
            
        # "최근 X개월" 패턴
        recent_months_match = re.search(r'최근\s*(\d+)\s*개월', time_range)
        if recent_months_match:
            months = int(recent_months_match.group(1))
            start_date = end_date - timedelta(days=months*30)
            return {"start_date": start_date, "end_date": end_date}
            
        # "YYYY년" 패턴 - 현재 연도와의 차이를 계산
        year_match = re.search(r'(20\d{2})년', time_range)
        if year_match:
            target_year = int(year_match.group(1))
            start_date = datetime(target_year, 1, 1)
            end_date = datetime(target_year, 12, 31)
            return {"start_date": start_date, "end_date": end_date}
            
        # "YY년" 패턴 (2자리 연도) - 20을 앞에 붙여서 4자리 연도로 변환
        short_year_match = re.search(r'(\d{2})년', time_range)
        if short_year_match:
            year_suffix = int(short_year_match.group(1))
            # 2000년대로 가정
            target_year = 2000 + year_suffix
            # 미래 연도인 경우 현재 연도 이하로 조정
            current_year = datetime.now().year
            if target_year > current_year:
                target_year = current_year
            
            start_date = datetime(target_year, 1, 1)
            end_date = datetime(target_year, 12, 31)
            return {"start_date": start_date, "end_date": end_date}
            
        
    
    # 쿼리에서 연도 범위 파악
    
    # 1. 특정 연도 매칭 패턴 (예: 2023년, 23년)
    year_specific_patterns = [
        r"(20\d{2})년",  # 4자리 연도 (YYYY년)
        r"(\d{2})년"     # 2자리 연도 (YY년)
    ]
    
    for pattern in year_specific_patterns:
        match = re.search(pattern, query)
        if match:
            try:
                group = match.group(1)
                # 연도 처리
                if len(group) == 4 and group.startswith('20'):
                    target_year = int(group)
                else:  # 2자리 연도
                    year_suffix = int(group)
                    target_year = 2000 + year_suffix
                
                # 미래 연도인 경우 현재 연도 이하로 조정
                current_year = datetime.now().year
                if target_year > current_year:
                    target_year = current_year
                    
                start_date = datetime(target_year, 1, 1)
                end_date = datetime(target_year, 12, 31)
                return {"start_date": start_date, "end_date": end_date}
            except ValueError:
                pass
    
    # 2. 기간 매칭 패턴 (예: 3년간, 5년 동안)
    period_patterns = [
        r"(\d+)년간",
        r"(\d+)년\s*동안",
        r"지난\s*(\d+)년",
        r"최근\s*(\d+)년",
        r"(\d+)년치",
        r"(\d+)년\s*데이터",
        r"(\d+)\s*년",
        r"(\d+)\s*years"
    ]
    
    for pattern in period_patterns:
        match = re.search(pattern, query)
        if match:
            try:
                year_range = int(match.group(1))
                year_range = min(max(year_range, 1), 5)  # 1~5년 사이로 제한
                start_date = end_date - timedelta(days=year_range*365)
                return {"start_date": start_date, "end_date": end_date}
            except ValueError:
                pass
    
    # 특정 키워드에 기반한 범위 결정
    if any(keyword in query or keyword in str(time_range) 
            for keyword in ["장기", "전체", "역대", "모든", "전부"]):
        start_date = end_date - timedelta(days=5*365)  # 5년
    elif any(keyword in query or keyword in str(time_range)
            for keyword in ["중장기", "3년", "삼년"]):
        start_date = end_date - timedelta(days=3*365)  # 3년
    elif any(keyword in query or keyword in str(time_range)
            for keyword in ["단기", "1년", "일년", "올해"]):
        start_date = end_date - timedelta(days=1*365)  # 1년
    else:
        # 기본값: 2년
        start_date = end_date - timedelta(days=default_years*365)
    
    return {"start_date": start_date, "end_date": end_date}

async def test_find매출(stock_code: str, query:str, time_range:str):
    """
    사업보고서의 매출처, 수주현황, 사업부별 매출 등의 정보를 추출합니다.
    
    1. 지정된 폴더에서 가장 최신 사업보고서를 찾습니다.
    2. 'II. 사업의 내용' 목차 하위의 '매출 및 수주상황' 목차를 찾습니다.
    3. 찾지 못했다면, 'II. 사업의 내용' 목차를 찾습니다.
    4. 찾은 목차의 시작 페이지와 끝 페이지를 이용해 해당 내용을 추출합니다.
    5. LLM을 이용해 매출처, 수주현황, 사업부별 매출 정보를 추출합니다.
    """
    
    classification = {"primary_intent": "재무정보", "complexity": "복합"}
    date_range = _determine_date_range(query, time_range)
    print(f"date_range: {date_range}")
    financial_analyzer_agent = FinancialAnalyzerAgent()
    #year_range = financial_analyzer_agent._determine_year_range(query, data_requirements)
    #logger.info(f"year_range: {year_range}")
    # 재무 데이터 조회 (GCS에서 PDF 파일을 가져와서 처리)
    year_range = 1
    financial_data = await financial_analyzer_agent.financial_service.get_financial_data(stock_code, date_range)
    
    required_metrics = financial_analyzer_agent._identify_required_metrics(classification, query)
    # 추출된 재무 데이터를 LLM에 전달할 형식으로 변환
    formatted_data = await financial_analyzer_agent._prepare_financial_data_for_llm(
        financial_data, 
        query, 
        required_metrics,
        None,
    )

    # 데이터 형식 변환
    financial_data_str = format_financial_data(formatted_data)
    
    #print(f"financial_data_str: {financial_data_str}")
    human_prompt = """
당신은 재무 분석 전문가입니다. 주어진 사업보고서 내용을 분석하여 다음 정보를 추출해주세요.

핵심 지침:

'분기'와 '누적 분기' 요청 구분: 질문에서 요구하는 기간 단위를 반드시 구분하여 답변해야 합니다. 이것이 가장 중요합니다.
세부 지침:

'X분기' 정보 요청 시 (예: '3분기 매출', '2분기 영업이익'):

오직 해당 특정 분기(X분기) 동안 발생한 데이터만 추출해야 합니다.
절대로 1분기부터 해당 분기까지 합산된 누적 데이터를 답변해서는 안 됩니다.
예시: '2분기 영업이익' 질문에는 오직 4월 1일부터 6월 30일까지의 영업이익만 답변합니다. (만약 보고서에 분기별 데이터가 없다면, 그 사실을 명시해야 합니다.)
'X분기 누적' 정보 요청 시 (예: '3분기 누적 매출', '반기 누적 순이익'):

해당 회계연도의 1분기부터 요청된 X분기까지 합산된 누적 데이터를 추출합니다.
예시: '3분기 누적 매출' 질문에는 1월 1일부터 9월 30일까지의 총 매출을 답변합니다.
금액 단위 표시:

모든 금액 정보는 단위를 명확히 표시해야 합니다.
백만원(1,000,000원), 억원(100,000,000원), 조원(1,000,000,000,000원) 단위를 사용하며, 가독성을 위해 적절히 변환합니다.
예시: 15,000백만원 -> 150억원, 20,000억원 -> 2조원
요청:

주어진 사업보고서 텍스트를 바탕으로 위의 지침에 따라 정확한 정보를 추출하여 답변해주세요.

    질문 : {query}
    
    사업보고서 내용 :
    {content}
    """            
    # 메시지 구성
    from langchain_core.messages import SystemMessage, HumanMessage
    
    messages = [
        #SystemMessage(content=self.prompt_template),
        HumanMessage(content=human_prompt.format(query=query, content=financial_data_str))
    ]
    #print(f"[테스트] LLM에 전달되는 메시지 길이: {len(human_prompt.format(query=query, content=financial_data_str))}")
    import time
    start_time = time.time()
    # 폴백 메커니즘을 사용하여 LLM 호출
    response: AIMessage = await financial_analyzer_agent.agent_llm.ainvoke_with_fallback(
        messages,
        user_id=None,
    )
    end_time = time.time()
    print(f"[테스트] LLM 호출 시간: {end_time - start_time:.2f}초")
    return response.content
        
   
    return

if __name__ == "__main__":
    asyncio.run(test_all()) 