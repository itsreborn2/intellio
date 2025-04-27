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
from stockeasy.prompts.financial_prompts import format_financial_data
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
        r = await test_find매출(code, "올해 실적 전망은?", "최근 2년")
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
    financial_data = await financial_analyzer_agent.financial_service_pdf.get_financial_data(stock_code, date_range)
    
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
    
    print(f"financial_data_str: {financial_data_str}")
    human_prompt = """
당신은 재무 분석 전문가입니다. 주어진 사업보고서 내용을 분석하여 다음 정보를 추출해주세요.

분석 전략:
1. 아래 제공된 재무제표/사업보고서 내용을 분석하여 사용자의 질문에 명확하게 답변하세요.
2. 제공된 보고서에 나타난 숫자와 데이터를 정확히 인용하세요.
3. 텍스트에서 표 데이터가 깨져 있더라도 숫자와 항목을 적절히 연결하여 분석하세요.
4. 질문의 내용에 따라 다음에 집중하세요:
   - 재무 실적: 매출액, 영업이익, 순이익 등의 성장률과 규모 분석 (반드시 전년동기대비(YoY), 직전분기대비(QoQ) 성장률 포함)
   - 재무 비율: PER, PBR, ROE, 부채비율 등 주요 투자 지표 설명
   - 현금 흐름: 영업/투자/재무 활동 현금흐름과 잉여현금흐름(FCF) 분석
   - 배당 정책: 배당금, 배당성향, 배당수익률 등의 주주환원 정책 설명

5. 분기별 데이터 처리 및 분석:
   - 항상 최근 5개 분기의 핵심 재무지표(매출, 영업이익, 순이익)를 표 형태로 정리하여 제시하세요.
   - 다음 출처의 보고서를 사용하세요 : '2024년 annual 보고서', '2024년 Q3 보고서', '2024년 semiannual 보고서', '2023년 Q2 보고서', '2023년 Q1 보고서'
   - 연간 보고서(사업보고서): 연간 데이터와 함께 5분기 데이터도 반드시 함께 분석하여 제공
   - 4분기 데이터 계산 방법: 연간 합계에서 1~3분기 합계를 차감하세요.
     * 4분기 매출 = 연간 매출 - (1분기 매출 + 2분기 매출 + 3분기 매출)
     * 4분기 영업이익 = 연간 영업이익 - (1분기 영업이익 + 2분기 영업이익 + 3분기 영업이익)
     * 4분기 순이익 = 연간 순이익 - (1분기 순이익 + 2분기 순이익 + 3분기 순이익)
   - 분기 보고서(1분기, 2분기/반기, 3분기): 해당 분기의 데이터를 상세히 분석하고, 직전 분기 및 전년 동기와의 비교 분석 제공
   - 누적 데이터와 해당 분기 데이터를 명확히 구분하세요(예: 반기보고서는 1분기+2분기 합산 데이터와 2분기 단독 데이터를 구분)
   - 모든 재무 실적은 QoQ(전분기대비), YoY(전년동기대비) 성장률을 반드시 명시하세요.

6. 최근 5개 분기 데이터 분석:
   - 답변 시작 부분에 항상 최근 5개 분기의 핵심 지표(매출액, 영업이익, 순이익)를 표 형태로 제시하세요.
   - 반드시 실제 최신 분기를 기준으로 역순으로 5개 분기를 표시하세요 (예: 현재가 2025년 1분기라면, 1Q2025, 4Q2024, 3Q2024, 2Q2024, 1Q2024, 순)
   - 연도와 분기를 명확히 표시하고 현재 연도에 맞게 적용하세요. 과거 연도(예: 2023년)의 분기가 아닌 실제 최근 5개 분기를 사용하세요.
   - 표 형식의 예시:
   
   【최근 5개 분기 실적】(단위: 억원or백만원)
  |                | 4Q2023    |  1Q2024 | 2Q2024 | 3Q2024 | 4Q2024 | 
  |------------------|--------|--------|--------|--------|--------|
  | 매출액        | 3,000  | 3,200  | 3,400  | 3,600  | 3,800 |
  |  (YoY)         | +6.8%  | +7.5%  | +8.2%  | +9.1%  | +10.3% |
  |  (QoQ)         | +4.2%  | -2.0%  | +6.3%  | +5.9%  | +5.6%  |
  | 영업이익      | 300    | 320    | 340    | 360    | 380    |
  |  (YoY)         | +11.0% | +12.5% | +13.2% | +14.1% | +15.3% |
  |  (QoQ)         | +3.5%  | -5.0%  | +6.3%  | +5.9%  | +5.6%  |
  | 순이익        | 230    | 250    | 270    | 290    | 310    |
  |  (YoY)         | +14.0% | +15.5% | +16.2% | +17.1% | +18.3% |
  |  (QoQ)         | +2.7%  | -7.0%  | +8.0%  | +7.4%  | +6.9%  |
   
   - 항상 문서 생성 시점 기준의 실제 최근 4개 분기를 정확하게 표시하세요. 임의로 과거 연도를 사용하지 마세요.
   - 데이터가 일부 누락된 경우에도 가능한 한 최근 4개 분기 데이터를 추정하여 표를 작성하세요.

7. 시간적 측면에서 다음과 같이 분석하세요:
   - 단기(최근 분기): 직전 분기 대비 변화와 계절성 고려
   - 중기(1~2년): 연간 성장률과 실적 변화 추세
   - 장기(3년 이상): 장기적 성장 패턴과 재무 안정성 평가

8. 분석 시 주의사항:
   - 계산 과정은 반드시 생략하고, 결과만 제시하세요.
   - 모든 수치는 적절한 단위(억원, %, 원 등)를 명시하세요.
   - 산업 평균과 비교 관점을 제공하세요.
   - 재무 변화의 원인과 향후 전망에 대한 통찰을 제공하세요.
   - 불확실한 정보가 있으면 명시하고, 확인된 사실만 인용하세요.
   - 핵심 재무 지표(매출, 영업이익, 순이익 등)는 항상 성장률(YoY, QoQ)과 함께 제시하여 변화 추세를 명확히 보여주세요.

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