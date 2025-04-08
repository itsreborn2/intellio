import asyncio
from datetime import datetime
import os
import sys
from pathlib import Path

import pandas as pd

# 프로젝트 루트 디렉토리를 Python 경로에 추가
project_root = str(Path(__file__).parent.parent)
sys.path.append(project_root)

from common.app import LoadEnvGlobal
# 환경 변수 로드
LoadEnvGlobal()


from common.services.llm_models import LLMModels

import logging

from google.oauth2 import service_account

from openai import OpenAI
from common.core.config import settings

from langchain_openai import OpenAIEmbeddings

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_google_vertexai.embeddings import VertexAIEmbeddings


import os
import json
from google.oauth2 import service_account
import gspread
from typing import List, Dict, Any, Optional

class GoogleSheetService:
    """구글 스프레드시트 접근 서비스"""
    
    def __init__(self, credentials_path: str = None):
        """
        구글 스프레드시트 서비스 초기화
        
        Args:
            credentials_path: 서비스 계정 인증 정보 파일 경로
                              기본값은 환경 변수 GOOGLE_APPLICATION_CREDENTIALS
        """
        try:
            if not credentials_path:
                credentials_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "")
                
            if not credentials_path or not os.path.exists(credentials_path):
                raise ValueError("구글 클라우드 인증 정보를 찾을 수 없습니다.")
                
            # 서비스 계정 인증 정보로 OAuth2 인증
            credentials = service_account.Credentials.from_service_account_file(
                credentials_path,
                scopes=["https://www.googleapis.com/auth/spreadsheets", 
                        "https://www.googleapis.com/auth/drive"]
            )
            
            # gspread 클라이언트 초기화
            self.client = gspread.authorize(credentials)
            
        except Exception as e:
            raise RuntimeError(f"구글 스프레드시트 서비스 초기화 실패: {str(e)}")
    
    def open_sheet_by_url(self, url: str, worksheet_name: Optional[str] = None):
        """
        URL로 스프레드시트 열기
        
        Args:
            url: 구글 스프레드시트 URL
            worksheet_name: 워크시트 이름 (지정하지 않으면 첫 번째 시트 사용)
            
        Returns:
            gspread.Worksheet: 워크시트 객체
        """
        try:
            # URL로 스프레드시트 열기
            spreadsheet = self.client.open_by_url(url)
            
            # 워크시트 선택
            if worksheet_name:
                worksheet = spreadsheet.worksheet(worksheet_name)
            else:
                worksheet = spreadsheet.sheet1
                
            return worksheet
        except Exception as e:
            raise RuntimeError(f"스프레드시트 열기 실패: {str(e)}")
            
    def open_sheet_by_key(self, key: str, worksheet_name: Optional[str] = None):
        """
        스프레드시트 ID로 스프레드시트 열기
        
        Args:
            key: 구글 스프레드시트 ID (URL에서 /d/ 다음 부분)
            worksheet_name: 워크시트 이름 (지정하지 않으면 첫 번째 시트 사용)
            
        Returns:
            gspread.Worksheet: 워크시트 객체
        """
        try:
            # ID로 스프레드시트 열기
            spreadsheet = self.client.open_by_key(key)
            
            # 워크시트 선택
            if worksheet_name:
                worksheet = spreadsheet.worksheet(worksheet_name)
            else:
                worksheet = spreadsheet.sheet1
                
            return worksheet
        except Exception as e:
            raise RuntimeError(f"스프레드시트 열기 실패: {str(e)}")
    
    def get_all_values(self, worksheet) -> List[List[str]]:
        """
        워크시트의 모든 값 가져오기
        
        Args:
            worksheet: gspread 워크시트 객체
            
        Returns:
            List[List[str]]: 워크시트의 모든 셀 값 (2차원 배열)
        """
        try:
            return worksheet.get_all_values()
        except Exception as e:
            raise RuntimeError(f"스프레드시트 데이터 가져오기 실패: {str(e)}")
    
    def get_all_records(self, worksheet) -> List[Dict[str, Any]]:
        """
        워크시트의 모든 레코드 가져오기 (첫 번째 행을 헤더로 사용)
        
        Args:
            worksheet: gspread 워크시트 객체
            
        Returns:
            List[Dict[str, Any]]: 워크시트의 모든 행 (첫 번째 행을 헤더로 하는 딕셔너리 리스트)
        """
        try:
            return worksheet.get_all_records()
        except Exception as e:
            raise RuntimeError(f"스프레드시트 레코드 가져오기 실패: {str(e)}")
    
    def append_row(self, worksheet, values: List[Any]) -> None:
        """
        워크시트에 행 추가
        
        Args:
            worksheet: gspread 워크시트 객체
            values: 추가할 행 데이터
        """
        try:
            worksheet.append_row(values)
        except Exception as e:
            raise RuntimeError(f"스프레드시트 행 추가 실패: {str(e)}")
    
    def update_cell(self, worksheet, row: int, col: int, value: Any) -> None:
        """
        특정 셀 업데이트
        
        Args:
            worksheet: gspread 워크시트 객체
            row: 행 번호 (1부터 시작)
            col: 열 번호 (1부터 시작)
            value: 셀에 넣을 값
        """
        try:
            worksheet.update_cell(row, col, value)
        except Exception as e:
            raise RuntimeError(f"스프레드시트 셀 업데이트 실패: {str(e)}")
    
    def update_range(self, worksheet, range_name: str, values: List[List[Any]]) -> None:
        """
        범위 업데이트
        
        Args:
            worksheet: gspread 워크시트 객체
            range_name: 범위 이름 (예: 'A1:B5')
            values: 2차원 배열 데이터
        """
        try:
            worksheet.update(range_name, values)
        except Exception as e:
            raise RuntimeError(f"스프레드시트 범위 업데이트 실패: {str(e)}")
        




# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def read_krx_code():
        # 상장 종목 목록 가져오기 
        #url = 'http://kind.krx.co.kr/corpgeneral/corpList.do?method=download&marketType=kosdaqMkt'
        #url = 'http://kind.krx.co.kr/corpgeneral/corpList.do?method=download&marketType=stockMkt'
        url = 'http://kind.krx.co.kr/corpgeneral/corpList.do?method=download&searchType=13'
        krx = pd.read_html(url, encoding='euc-kr', header=0)[0]
        # 데이터 정리
        krx = krx[['종목코드','회사명', '업종']]
        krx = krx.rename(columns={'종목코드':'code','회사명':'name'})
        krx.code = krx.code.map('{:06d}'.format)
        krx = krx[~krx["name"].str.contains("스팩")]
        
        df1 = pd.DataFrame({'code':['KOSPI','KOSDAQ'],
                    'name':['KOSPI','KOSDAQ'],
                    '업종':['KOSPI','KOSDAQ']})
        
        krx = pd.concat([krx, df1], ignore_index=True)
        return krx

def test_google_sheet_fill_all_data():
    """KRX 종목코드와 종목명을 구글 시트에 업데이트"""
    try:
        print("구글 시트 서비스 초기화 중...")
        # 구글 시트 서비스 초기화
        
        sheet_service = GoogleSheetService(credentials_path=settings.GOOGLE_APPLICATION_CREDENTIALS)
        
        # 스프레드시트 URL로 열기
        sheet_url = "https://docs.google.com/spreadsheets/d/1AgbEpblhoqSBTmryDjSSraqc5lRdgWKNwBUA4VYk2P4/edit"
        print(f"스프레드시트 열기: {sheet_url}")
        
        # 시트 이름을 지정하거나 기본 시트 사용
        worksheet_name = "섹터" # 원하는 시트 이름으로 변경하세요
        try:
            worksheet = sheet_service.open_sheet_by_url(sheet_url, worksheet_name=worksheet_name)
            print(f"'{worksheet_name}' 워크시트 열기 성공")
        except Exception as e:
            logger.warning(f"'{worksheet_name}' 워크시트를 찾을 수 없어 첫 번째 시트를 사용합니다: {str(e)}")
            worksheet = sheet_service.open_sheet_by_url(sheet_url)
        
        # KRX 종목 데이터 가져오기
        print("KRX 종목 정보 가져오는 중...")
        krx_data = read_krx_code()
        print(f"총 {len(krx_data)} 개의 종목 정보를 가져왔습니다.")
        
        # 헤더 행 추가 (시트가 비어있을 경우)
        all_values = worksheet.get_all_values()
        if not all_values:
            print("시트가 비어있어 헤더 행을 추가합니다.")
            worksheet.append_row(["종목코드", "종목명", "섹터"])
        
        # 시트 초기화 (헤더 행은 유지)
        # if len(all_values) > 1:
        #     print("기존 데이터를 지우고 새로운 데이터로 업데이트합니다.")
        #     worksheet.delete_rows(2, len(all_values))  # 헤더 행을 제외한 나머지 행 삭제
        
        # 종목코드와 종목명만 추출하여 2차원 배열 생성 (업종 제외)
        stock_data = []
        for _, row in krx_data.iterrows():
            stock_data.append([row['code'], row['name']])
        
        print(f"구글 시트에 {len(stock_data)}개의 종목 정보를 추가합니다.")
        
        # 배치 방식으로 여러 행 한번에 추가
        # gspread는 대량의 데이터를 한번에 추가할 수 있는 batch_update 기능 제공
        # A2 셀부터 데이터 업데이트 (A1, B1은 헤더)
        range_name = f"A2:B{len(stock_data) + 1}"
        worksheet.update(range_name, stock_data)
        
        print("KRX 종목코드와 종목명 업데이트 완료")
        print(f"시트 URL: {sheet_url}")
        
    except Exception as e:
        logger.error(f"구글 시트 업데이트 실패: {str(e)}")
        raise


def test_google_sheet2():
    """KRX 종목코드와 종목명을 구글 시트에 업데이트"""
    try:
        print("구글 시트 서비스 초기화 중...")
        # 구글 시트 서비스 초기화
        
        sheet_service = GoogleSheetService(credentials_path=settings.GOOGLE_APPLICATION_CREDENTIALS)
        
        # 스프레드시트 URL로 열기
        sheet_url = "https://docs.google.com/spreadsheets/d/1AgbEpblhoqSBTmryDjSSraqc5lRdgWKNwBUA4VYk2P4/edit"
        print(f"스프레드시트 열기: {sheet_url}")
        
        # 시트 이름을 지정하거나 기본 시트 사용
        worksheet_name = "섹터" # 원하는 시트 이름으로 변경하세요
        try:
            worksheet = sheet_service.open_sheet_by_url(sheet_url, worksheet_name=worksheet_name)
            print(f"'{worksheet_name}' 워크시트 열기 성공")
        except Exception as e:
            logger.warning(f"'{worksheet_name}' 워크시트를 찾을 수 없어 첫 번째 시트를 사용합니다: {str(e)}")
            worksheet = sheet_service.open_sheet_by_url(sheet_url)
        
        # KRX 종목 데이터 가져오기
        print("KRX 종목 정보 가져오는 중...")
        krx_data = read_krx_code()
        print(f"총 {len(krx_data)} 개의 종목 정보를 가져왔습니다.")
        
        # KRX 데이터를 딕셔너리로 변환 (종목코드를 키로)
        krx_dict = {}
        for _, row in krx_data.iterrows():
            krx_dict[row["code"]] = {
                "name": row["name"]
            }
        
        # 시트 데이터 가져오기
        print("구글 시트 데이터 가져오는 중...")
        all_values = worksheet.get_all_values()
        print(f"구글 시트에서 {len(all_values)} 행의 데이터를 가져왔습니다.")
        
        # 헤더 행이 없으면 추가
        if not all_values:
            print("시트가 비어있어 헤더 행을 추가합니다.")
            worksheet.append_row(["종목코드", "종목명", "섹터"])
            all_values = [["종목코드", "종목명", "섹터"]]
        
        # 시트 데이터를 종목코드를 키로 하는 딕셔너리로 변환
        sheet_dict = {}
        header_row = all_values[0]
        print(f"시트 헤더: {header_row}")
        
        # 종목코드, 종목명, 섹터 컬럼 인덱스 찾기
        code_idx = header_row.index("종목코드") if "종목코드" in header_row else 0
        name_idx = header_row.index("종목명") if "종목명" in header_row else 1
        sector_idx = header_row.index("섹터") if "섹터" in header_row else 2
        print(f"컬럼 인덱스 - 종목코드: {code_idx}, 종목명: {name_idx}, 섹터: {sector_idx}")
        
        # 헤더 제외한 데이터 행만 처리
        for i, row in enumerate(all_values[1:], 2):  # i는 스프레드시트의 행 번호(2부터 시작, 1은 헤더)
            if row and len(row) > code_idx and row[code_idx]:  # 비어있지 않은 행만 처리
                stock_code = row[code_idx]
                sheet_dict[stock_code] = {
                    "name": row[name_idx] if len(row) > name_idx else "",
                    "sector": row[sector_idx] if len(row) > sector_idx else "",
                    "row": i  # 시트에서의 행 번호 저장 (1부터 시작)
                }
        
        print(f"구글 시트에서 {len(sheet_dict)} 개의 종목 정보를 가져왔습니다.")
        
        # 1. 종목명 변경 업데이트
        name_changes = []
        for code, data in sheet_dict.items():
            if code in krx_dict and krx_dict[code]["name"] != data["name"]:
                name_changes.append({
                    "code": code,
                    "old_name": data["name"],
                    "new_name": krx_dict[code]["name"],
                    "row": data["row"]
                })
        
        # 종목명 변경 처리
        if name_changes:
            print(f"{len(name_changes)}개 종목의 이름이 변경되었습니다. 업데이트 중...")
            for change in name_changes:
                worksheet.update_cell(change["row"], name_idx + 1, change["new_name"])  # 0-인덱스를 1-인덱스로 변환(gspread는 1부터 시작)
                print(f"종목명 변경: {change['code']} - {change['old_name']} → {change['new_name']}")
        else:
            print("변경된 종목명이 없습니다.")
        
        # 2. 상장 폐지된 종목 찾기 - 시트에는 있지만 KRX에는 없는 종목
        delisted = []
        for code, data in sheet_dict.items():
            if code not in krx_dict:
                delisted.append({
                    "code": code,
                    "name": data["name"],
                    "row": data["row"]
                })
        
        # 상장 폐지 종목 처리 - 행 번호 역순으로 정렬하여 삭제 (높은 행 번호부터 삭제해야 인덱스 변화가 없음)
        if delisted:
            delisted.sort(key=lambda x: x["row"], reverse=True)
            print(f"{len(delisted)}개 종목이 상장 폐지되었습니다. 시트에서 삭제 중...")
            for item in delisted:
                worksheet.delete_rows(item["row"])
                print(f"상장 폐지 종목 삭제: {item['code']} - {item['name']}")
        else:
            print("상장 폐지된 종목이 없습니다.")
        
        # 3. 신규 상장 종목 찾기 - KRX에는 있지만 시트에는 없는 종목
        new_listings = []
        for code, data in krx_dict.items():
            # KOSPI, KOSDAQ은 추가하지 않음
            if code not in sheet_dict and code not in ["KOSPI", "KOSDAQ"]:
                new_listings.append({
                    "code": code,
                    "name": data["name"]
                })
        
        # 신규 상장 종목 처리 - 맨 아래에 추가
        if new_listings:
            print(f"{len(new_listings)}개의 신규 상장 종목을 추가합니다.")
            for item in new_listings:
                # 종목코드, 종목명, 섹터(빈 값)
                worksheet.append_row([item["code"], item["name"], ""])
                print(f"신규 상장 종목 추가: {item['code']} - {item['name']}")
        else:
            print("신규 상장 종목이 없습니다.")
        
        print("KRX 종목코드와 종목명 업데이트 완료")
        print(f"시트 URL: {sheet_url}")
        print(f"총 처리결과: 종목명 변경 {len(name_changes)}개, 상장 폐지 {len(delisted)}개, 신규 상장 {len(new_listings)}개")
    except Exception as e:
        logger.error(f"구글 시트 업데이트 중 오류 발생: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        raise

def test_google_sheet3():
    """구글 시트의 섹터 탭에서 종목코드:섹터 딕셔너리 생성"""
    try:
        print("구글 시트 서비스 초기화 중...")
        # 구글 시트 서비스 초기화
        sheet_service = GoogleSheetService(credentials_path=settings.GOOGLE_APPLICATION_CREDENTIALS)
        
        # 스프레드시트 URL로 열기
        sheet_url = "https://docs.google.com/spreadsheets/d/1AgbEpblhoqSBTmryDjSSraqc5lRdgWKNwBUA4VYk2P4/edit"
        print(f"스프레드시트 열기: {sheet_url}")
        
        # 시트 이름을 지정하거나 기본 시트 사용
        worksheet_name = "섹터" # 원하는 시트 이름으로 변경하세요
        try:
            worksheet = sheet_service.open_sheet_by_url(sheet_url, worksheet_name=worksheet_name)
            print(f"'{worksheet_name}' 워크시트 열기 성공")
        except Exception as e:
            logger.warning(f"'{worksheet_name}' 워크시트를 찾을 수 없어 첫 번째 시트를 사용합니다: {str(e)}")
            worksheet = sheet_service.open_sheet_by_url(sheet_url)
        
        # 시트 데이터 가져오기
        print("구글 시트 데이터 가져오는 중...")
        all_values = worksheet.get_all_values()
        print(f"구글 시트에서 {len(all_values)} 행의 데이터를 가져왔습니다.")
        
        # 헤더 행이 없거나 비어있으면 오류 출력
        if not all_values:
            print("시트가 비어있습니다.")
            return
        
        # 헤더 행 찾기
        header_row = all_values[0]
        print(f"시트 헤더: {header_row}")
        
        # 종목코드, 종목명, 섹터 컬럼 인덱스 찾기
        code_idx = header_row.index("종목코드") if "종목코드" in header_row else 0
        sector_idx = header_row.index("섹터") if "섹터" in header_row else 2
        print(f"컬럼 인덱스 - 종목코드: {code_idx}, 섹터: {sector_idx}")
        
        # 종목코드:섹터 딕셔너리 생성
        sector_dict = {}
        
        # 헤더 제외한 데이터 행만 처리
        for row in all_values[1:]:  # 헤더 제외
            if row and len(row) > max(code_idx, sector_idx):  # 행이 충분히 길고
                stock_code = row[code_idx]
                sector_value = row[sector_idx]
                
                if stock_code and sector_value:  # 종목코드와 섹터 값이 모두 있을 때만
                    # 콤마로 구분된 섹터를 리스트로 분리
                    if ',' in sector_value:
                        # 각 섹터 항목 앞뒤 공백 제거하여 리스트로 저장
                        sectors = [s.strip() for s in sector_value.split(',')]
                        sector_dict[stock_code] = sectors
                    else:
                        sector_dict[stock_code] = sector_value.strip()
        
        print(f"총 {len(sector_dict)}개 종목의 섹터 정보를 읽었습니다.")
        
        # 샘플 출력 (처음 10개만)
        print("\n===== 종목코드:섹터 딕셔너리 샘플 =====")
        sample_items = list(sector_dict.items())[:10]  # 처음 10개만
        for code, sector in sample_items:
            print(f"{code}: {sector}")
        
        # 섹터별 종목 수 카운트
        sector_count = {}
        for sectors in sector_dict.values():
            if isinstance(sectors, list):
                # 리스트인 경우 각 섹터별로 카운트
                for sector in sectors:
                    sector_count[sector] = sector_count.get(sector, 0) + 1
            else:
                # 단일 섹터인 경우
                sector_count[sectors] = sector_count.get(sectors, 0) + 1
        
        # 섹터별 종목 수 출력
        print("\n===== 섹터별 종목 수 =====")
        for sector, count in sorted(sector_count.items(), key=lambda x: x[1], reverse=True):
            print(f"{sector}: {count}개 종목")
        
        return sector_dict
        
    except Exception as e:
        print(f"오류 발생: {str(e)}")
        import traceback
        traceback.print_exc()
        return {}

def get_stocks_by_sector(sector_dict, target_sector):
    """
    특정 섹터에 속하는 모든 종목코드 리스트 반환
    
    Args:
        sector_dict: 종목코드:섹터 딕셔너리
        target_sector: 찾을 섹터명
        
    Returns:
        List[str]: 해당 섹터에 속하는 종목코드 리스트
    """
    result = []
    
    for code, sectors in sector_dict.items():
        if isinstance(sectors, list):
            # 섹터가 리스트인 경우 (콤마로 구분된 여러 섹터)
            if target_sector in sectors:
                result.append(code)
        else:
            # 섹터가 단일 문자열인 경우
            if sectors == target_sector:
                result.append(code)
    
    return result

def update_stock_info_with_sectors(stock_info_cache, sector_dict):
    """
    종목 정보 캐시에 섹터 정보를 업데이트합니다.
    
    Args:
        stock_info_cache: 종목 정보 캐시 딕셔너리 (by_code, by_name 등 포함)
        sector_dict: 종목코드:섹터 딕셔너리
        
    Returns:
        Dict: 섹터 정보가 업데이트된 종목 정보 캐시
    """
    # 캐시 복사본 생성 (원본 변경 방지)
    updated_cache = stock_info_cache.copy()
    
    # sector 키가 없으면 추가
    if "sector" not in updated_cache:
        updated_cache["sector"] = {}
    
    # by_code에 있는 종목 정보에 섹터 추가
    if "by_code" in updated_cache:
        for code, stock_info in updated_cache["by_code"].items():
            # 해당 종목코드가 섹터 딕셔너리에 있으면 섹터 정보 추가
            if code in sector_dict:
                # 종목 정보에 섹터 필드 추가/업데이트
                stock_info["sector"] = sector_dict[code]
                
                # sector 섹션에도 추가 (종목코드 -> 섹터 매핑)
                updated_cache["sector"][code] = sector_dict[code]
    
    print(f"총 {len(updated_cache['sector'])}개 종목의 섹터 정보가 업데이트되었습니다.")
    return updated_cache

async def test_sector_by_code():
    """종목코드로 섹터 정보 조회 테스트"""
    try:
        from stockeasy.services.financial.stock_info_service import StockInfoService
        
        # StockInfoService 인스턴스 생성
        stock_service = StockInfoService()
        
        # 테스트할 종목코드 목록
        test_codes = ["005930", "000660", "035420", "051910", "207940", "035720"]
        
        print("\n===== 종목코드별 섹터 정보 =====")
        for code in test_codes:
            sector = await stock_service.get_sector_by_code(code)
            print(f"{code} 섹터 정보: {sector}")
            
        # 검색을 통해 특정 종목 정보 확인
        search_query = "삼성전자"
        stocks = await stock_service.search_stocks(search_query, limit=1)
        if stocks:
            stock = stocks[0]
            code = stock["code"]
            name = stock["name"]
            sector = await stock_service.get_sector_by_code(code)
            print(f"\n검색 결과 - {name}({code}) 섹터 정보: {sector}")
        
    except ImportError as e:
        print(f"모듈 가져오기 실패: {str(e)}")
    except Exception as e:
        print(f"테스트 실행 중 오류 발생: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    # test_google_sheet_fill_all_data()  # 주석 처리하여 실행하지 않음
    # test_google_sheet2()  # 주석 처리하여 실행하지 않음
    
    # 시트에서 종목코드:섹터 딕셔너리 가져오기
    print("\n===== 섹터별 종목 가져오기 =====")
    sector_dict = test_google_sheet3()
    
    # 가상의 종목 정보 캐시 생성 (테스트용)
    # 실제로는 StockInfoService에서 _stock_info_cache를 사용할 것입니다
    sample_stock_info = {
        "by_code": {
            "005930": {"code": "005930", "name": "삼성전자"},
            "000660": {"code": "000660", "name": "SK하이닉스"},
            "207940": {"code": "207940", "name": "삼성바이오로직스"},
            "035420": {"code": "035420", "name": "NAVER"},
        },
        "by_name": {
            "삼성전자": {"code": "005930", "name": "삼성전자"},
            "SK하이닉스": {"code": "000660", "name": "SK하이닉스"},
            "삼성바이오로직스": {"code": "207940", "name": "삼성바이오로직스"},
            "NAVER": {"code": "035420", "name": "NAVER"},
        }
    }
    
    # 종목 정보에 섹터 추가
    updated_stock_info = update_stock_info_with_sectors(sample_stock_info, sector_dict)
    
    # 업데이트된 정보 확인
    print("\n===== 업데이트된 종목 정보 (섹터 포함) =====")
    for code, info in updated_stock_info["by_code"].items():
        sector_info = info.get("sector", "섹터 정보 없음")
        print(f"{code} - {info['name']}: {sector_info}")
    
    # 섹터 섹션 확인
    print("\n===== 전체 섹터 정보 =====")
    print(f"섹터 정보가 있는 종목 수: {len(updated_stock_info['sector'])}")
    
    # 섹터별 종목 목록 출력
    print("\n===== 섹터별 종목 목록 =====")
    sector_groups = {}
    
    # 종목을 섹터별로 그룹화
    for code, sector in updated_stock_info["sector"].items():
        if isinstance(sector, list):
            # 섹터가 리스트인 경우, 첫 번째 섹터로 그룹화 (또는 별도 처리 가능)
            main_sector = sector[0]
            if main_sector not in sector_groups:
                sector_groups[main_sector] = []
            sector_groups[main_sector].append(code)
        else:
            # 섹터가 문자열인 경우
            if sector not in sector_groups:
                sector_groups[sector] = []
            sector_groups[sector].append(code)
    
    # 그룹화된 섹터별 종목 출력
    for sector, codes in sector_groups.items():
        print(f"\n{sector} ({len(codes)}개 종목):")
        for code in codes:
            name = updated_stock_info["by_code"][code]["name"]
            print(f"  - {code}: {name}")
    
    # 특정 섹터의 종목 가져오기
    target_sector = "반도체"
    semiconductor_stocks = get_stocks_by_sector(sector_dict, target_sector)
    print(f"\n'{target_sector}' 섹터에 속하는 종목 ({len(semiconductor_stocks)}개):")
    for code in semiconductor_stocks:
        if code in updated_stock_info["by_code"]:
            name = updated_stock_info["by_code"][code]["name"]
            print(f"- {code}: {name}")
        else:
            print(f"- {code}")
            
    # 삼성전자 정보 출력
    if '005930' in updated_stock_info["by_code"]:
        samsung = updated_stock_info["by_code"]["005930"]
        print("\n삼성전자 전체 정보:")
        for key, value in samsung.items():
            print(f"  {key}: {value}")

    # 섹터 정보 조회 테스트
    asyncio.run(test_sector_by_code())

