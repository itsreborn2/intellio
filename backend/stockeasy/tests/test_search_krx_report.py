"""
리랭커 테스트 예제
"""

import asyncio
import os
import sys
import time
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from loguru import logger
from dotenv import load_dotenv
from common.core.config import settings
from common.services.retrievers.models import DocumentWithScore
import fitz  # PyMuPDF 라이브러리
import pdfplumber
import glob
from pathlib import Path
from datetime import datetime
# LangChain 관련 라이브러리
from langchain_core.prompts import ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.messages import AIMessage
# OpenAI 모델 임포트 추가
#from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
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
    start_time = time.time()
    # stockeasy/local_cache/financial_reports/정기보고서/103590
    base_dir = "stockeasy/local_cache/financial_reports/정기보고서"
    #code_list = ["005380","103590", "005930", "044340", "195870", "326030", "140410", "049800", "267260"]
    # 103590 일진전기
    # 049880 우진플람
    # 214450 파마리서치, 010140 삼성중공업, 112610 씨에스윈드, 014620 성광벤드, 329180 현대중공업
    #code_list = ["112610", "014620", "329180"]
    code_list = ["278470"]

    result = ""
    for code in code_list:
        result += await test_find매출_수주현황_사업부별매출(f"{base_dir}/{code}")

    print(result)
    # 마크다운 파일로 저장
    with open("D:/Work/intellio/md/2.md", "w", encoding="utf-8") as f:
        f.write(result)
    
    # 마크다운을 HTML로 변환하여 저장
    html_content = markdown.markdown(result, extensions=['tables', 'fenced_code'])
    
    # HTML 기본 스타일을 적용
    styled_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>사업보고서 매출 및 수주상황 분석</title>
        <style>
            body {{
                font-family: 'Malgun Gothic', Arial, sans-serif;
                line-height: 1.6;
                margin: 0;
                padding: 20px;
                color: #333;
                background-color: #f8f9fa;
            }}
            .container {{
                max-width: 1200px;
                margin: 0 auto;
                background-color: white;
                padding: 20px;
                box-shadow: 0 0 10px rgba(0, 0, 0, 0.1);
                border-radius: 5px;
            }}
            h2 {{
                color: #2c3e50;
                border-bottom: 2px solid #3498db;
                padding-bottom: 10px;
                margin-top: 30px;
            }}
            table {{
                border-collapse: collapse;
                width: 100%;
                margin: 15px 0;
            }}
            th, td {{
                padding: 12px;
                border: 1px solid #ddd;
                text-align: left;
            }}
            th {{
                background-color: #f2f2f2;
                font-weight: bold;
            }}
            tr:nth-child(even) {{
                background-color: #f9f9f9;
            }}
            hr {{
                border: 0;
                height: 1px;
                background: #ddd;
                margin: 30px 0;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            {html_content}
        </div>
    </body>
    </html>
    """
    
    # HTML 파일로 저장
    with open("D:/Work/intellio/md/2.html", "w", encoding="utf-8") as f:
        f.write(styled_html)
    
    end_time = time.time()
    print(f"총 실행 시간: {end_time - start_time}초")
    return result
async def extract_분기별데이터(target_report: str):
    
    base_file_name = os.path.basename(target_report)
    print(f"최신 사업보고서: {base_file_name}")
    #  20250320_메지온_140410_일반서비스_annual_DART.pdf
    year = base_file_name.split("_")[0]
    year = year[:4]
    quater_file = base_file_name.split("_")[4]
    if quater_file == "annual":
        year = int(year) - 1
    report_type_map = {
            "Q1": "1분기",
            "Q3": "3분기",
            "semiannual": "2분기",
            "annual": "4분기"
        }
    print("test1")
    quater = report_type_map[quater_file]

    # 3. fitz를 사용하여 목차 내용 추출
    doc = fitz.open(target_report)
    toc = doc.get_toc()  # 목차 가져오기
    print(f"toc: {len(toc)}")
    if not toc:
        logger.error("목차를 찾을 수 없습니다.")
        doc.close()
        return
    
    # 4. 목차에서 'II. 사업의 내용' 및 '매출 및 수주상황' 찾기
    business_content_start_page = None
    business_content_end_page = None
    sales_section_start_page = None
    sales_section_end_page = None
    
    for i, item in enumerate(toc):
        level, title, page_num = item
        
        # 'II. 사업의 내용' 목차 찾기
        if "사업의 내용" in title and (title.startswith("II.") or title.startswith("Ⅱ.")):
            business_content_start_page = page_num - 1  # 0-based 페이지 번호로 변환
            
            # 다음 대분류 목차를 찾아 끝 페이지 결정
            for next_item in toc[i+1:]:
                next_level, next_title, next_page = next_item
                if next_level <= level and (next_title.startswith("III.") or next_title.startswith("Ⅲ.") or 
                                           next_title.startswith("IV.") or next_title.startswith("Ⅳ.")):
                    business_content_end_page = next_page - 2  # 다음 대분류 시작 전 페이지
                    break
            
            # 다음 대분류가 없으면 문서 끝까지를 범위로 설정
            if business_content_end_page is None:
                business_content_end_page = len(doc) - 1
        
        # '매출 및 수주상황' 목차 찾기 (II. 사업의 내용 아래에 있어야 함)
        if business_content_start_page is not None and "매출" in title and "수주" in title:
            sales_section_start_page = page_num - 1  # 0-based 페이지 번호로 변환
            
            # 다음 동일 레벨 또는 상위 레벨 목차를 찾아 끝 페이지 결정
            for next_item in toc[i+1:]:
                next_level, next_title, next_page = next_item
                if next_level <= level:
                    sales_section_end_page = next_page - 2  # 다음 섹션 시작 전 페이지
                    break
            
            # 다음 섹션이 없으면 사업의 내용 끝까지를 범위로 설정
            if sales_section_end_page is None and business_content_end_page is not None:
                sales_section_end_page = business_content_end_page
            
            break  # 매출 및 수주상황 섹션을 찾았으므로 검색 종료
    
    # 5. 페이지 범위 결정 (매출 및 수주상황을 찾지 못했다면 사업의 내용 전체를 사용)
    if sales_section_start_page is not None and sales_section_end_page is not None:
        start_page = sales_section_start_page
        end_page = sales_section_end_page
        logger.info(f"'매출 및 수주상황' 섹션을 찾았습니다: 페이지 {start_page+1}~{end_page+1}")
    elif business_content_start_page is not None and business_content_end_page is not None:
        start_page = business_content_start_page
        end_page = business_content_end_page
        logger.info(f"'II. 사업의 내용' 섹션을 찾았습니다: 페이지 {start_page+1}~{end_page+1}")
    else:
        logger.error("관련 섹션을 찾을 수 없습니다.")
        doc.close()
        return
    
    # 6. pdfplumber를 사용하여 해당 페이지 내용 추출
    extracted_text = f"-----------------------------\n\n"
    extracted_text += f"## {year}년 {quater} 데이터\n\n"
    print(f"{extracted_text}")
    with pdfplumber.open(target_report) as pdf:
        # 페이지 범위가 너무 크면 최대 10페이지로 제한
        max_pages = 30
        if end_page - start_page > max_pages:
            logger.warning(f"페이지 범위가 너무 큽니다. 처음 {max_pages}페이지만 추출합니다.")
            end_page = start_page + max_pages
        
        for page_num in range(start_page, end_page + 1):
            if page_num < len(pdf.pages):
                page = pdf.pages[page_num]
                text = page.extract_text()
                if text:
                    extracted_text += f"\n\n--- 페이지 {page_num + 1} ---\n\n{text}"
    
    extracted_text += f"\n\n--- 데이터 끝 ---\n\n"
    if not extracted_text:
        logger.error("추출된 텍스트가 없습니다.")
        doc.close()
        return
    return extracted_text
async def test_find매출_수주현황_사업부별매출(dir_path: str):
    """
    """
    # 1. 삼성전자(005930) 사업보고서 폴더 경로

    report_folder = Path(dir_path)
    
    # 2. 가장 최신 사업보고서 파일 찾기 (파일명에 annual이 포함된 파일)
    annual_reports = list(report_folder.glob("*.pdf"))
    annual_reports.sort(key=lambda x: x.name, reverse=True)  # 파일명 기준 내림차순 정렬
    
    if not annual_reports:
        logger.error("사업보고서 파일을 찾을 수 없습니다.")
        return
    
    file_list = annual_reports[:4]
    extracted_text = ""
    for file in file_list:
        extracted_text += await extract_분기별데이터(file)

    print(f"length: {len(extracted_text)}")


    # 7. LLM을 사용하여 매출처, 수주현황, 사업부별 매출 정보 추출
    try:
        # LLM 초기화 (Google Gemini 모델 직접 초기화)
        # Gemini 모델 사용 부분 주석 처리
            
        llm = ChatGoogleGenerativeAI(
            #model="gemini-2.0-flash-lite", #"gemini-2.0-flash","gemini-2.0-flash-lite"
            model="gemini-2.0-flash",
            google_api_key=GEMINI_API_KEY,
            temperature=0.1,
            max_output_tokens=8000
        )
        
        # 프롬프트 템플릿 설정
        system_prompt = """
당신은 기업 분석 전문가입니다. 주어진 사업보고서 내용을 분석하여 다음 정보를 표로 정리해주세요:

1. 주요 매출처 (주요 거래처, 주요 고객)
2. 수주 현황 (계약, 수주 잔고 등)
3. 수주 현황의 분기별 증감율 현황
4. 사업부문별 매출 현황과 지난 분기 대비 증감율(QoQ)
5. 제품별 매출 현황과 지난 분기 대비 증감율(QoQ)
6. 지역별 매출 현황과 지난 분기 대비 증감율(QoQ)
7. 사업부문별 매출 비중 (전체 매출 대비 각 사업부의 비율, %)

**요청 사항:**
- 위 정보를 간결한 **표** 형태로 정리해주세요.
- 정보가 없는 항목은 생략합니다.
- 항목 4~6번은 각각 별도의 표로 구분하여 작성해주세요.
- 항목 7번은 항목 4번의 매출을 기반으로 비중을 계산해주세요.
- 4~6번 표는 다음 형식으로 출력해주세요:

[📊 표 예시: 제품별 매출]

| 분기 | 나동선 | 알루미늄 | 내수 |
|------|--------|-----------|--------|
| 2024년 1분기 | 470,626 (5.2%) | 220,000 (2.1%) | 110,000 (3.5%) |
| 2024년 2분기 | 667,098 (11.3%) | 250,000 (13.6%) | 130,000 (18.2%) |
| 2024년 3분기 | 911,377 (10.1%) | 285,000 (9.2%) | 150,000 (15.4%) |

[📈 표 예시: 사업부문별 매출 비중]

| 분기 | 전선 | 중전기 | 기타 |
|------|------|--------|------|
| 2024년 1분기 | 65.2% | 32.5% | 2.3% |
| 2024년 2분기 | 66.1% | 31.4% | 2.5% |
| 2024년 3분기 | 67.3% | 30.1% | 2.6% |

※ 모든 금액 단위는 **백만원**, 괄호 안은 전 분기 대비 증감율(QoQ)입니다.
※ 매출 비중(%)은 각 분기 총 매출 기준으로 계산된 비율입니다.
※ 매출액이 없는 항목은 ‘-’로 표기해주세요.

        """
        
        human_prompt = """
        다음은 사업보고서의 일부입니다. 이 내용에서 매출처, 수주현황, 사업부별 매출 정보를 추출해주세요:
        
        {content}
        """
        
        # 프롬프트 체인 설정
        prompt = ChatPromptTemplate.from_messages([
            SystemMessagePromptTemplate.from_template(system_prompt),
            HumanMessagePromptTemplate.from_template(human_prompt)
        ])
        
        # LLM 체인 구성 및 실행
        chain = prompt | llm | StrOutputParser()
        result = chain.invoke({"content": extracted_text})  # 토큰 제한을 고려하여 내용 잘라냄
        
        base_files = ""
        for file in file_list:
            base_file_name = f"{os.path.basename(file)}"
            base_files += f"{base_file_name}\n\n"

        answer = f"-----------------------------\n\n## 파일 : {base_files}\n\n-----------------------------\n\n{result}\n\n"
        return answer
        
    except Exception as e:
        logger.exception(f"LLM 처리 중 오류 발생: {str(e)}")
    
    return

if __name__ == "__main__":
    asyncio.run(test_all()) 