import os
import json
import logging
from google.oauth2 import service_account
import gspread
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

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
            logger.info("GoogleSheetService 초기화 성공")
            
        except Exception as e:
            logger.error(f"구글 스프레드시트 서비스 초기화 실패: {str(e)}")
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
            logger.error(f"스프레드시트 열기 실패: {str(e)}")
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
            logger.error(f"스프레드시트 열기 실패: {str(e)}")
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
            logger.error(f"스프레드시트 데이터 가져오기 실패: {str(e)}")
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
            logger.error(f"스프레드시트 레코드 가져오기 실패: {str(e)}")
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
            logger.error(f"스프레드시트 행 추가 실패: {str(e)}")
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
            logger.error(f"스프레드시트 셀 업데이트 실패: {str(e)}")
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
        
    def get_sector_dict(self, url: str, worksheet_name: str = "섹터") -> Dict[str, Any]:
        """
        구글 스프레드시트에서 종목코드:섹터 딕셔너리를 가져옵니다.
        
        Args:
            url: 구글 스프레드시트 URL (필수)
            worksheet_name: 워크시트 이름 (기본값은 "섹터")
            
        Returns:
            Dict[str, Any]: 종목코드를 키로 하고 섹터 정보를 값으로 하는 딕셔너리
        """
        try:
            # URL이 제공되지 않은 경우 빈 딕셔너리 반환
            if not url:
                logger.error("구글 스프레드시트 URL이 제공되지 않았습니다.")
                return {}
            
            # 워크시트 열기
            try:
                worksheet = self.open_sheet_by_url(url, worksheet_name=worksheet_name)
                logger.info(f"'{worksheet_name}' 워크시트 열기 성공")
            except Exception as e:
                logger.warning(f"'{worksheet_name}' 워크시트를 찾을 수 없어 첫 번째 시트를 사용합니다: {str(e)}")
                worksheet = self.open_sheet_by_url(url)
            
            # 시트 데이터 가져오기
            all_values = self.get_all_values(worksheet)
            logger.info(f"구글 시트에서 {len(all_values)} 행의 데이터를 가져왔습니다.")
            
            # 헤더 행이 없거나 비어있으면 빈 딕셔너리 반환
            if not all_values:
                logger.warning("시트가 비어있습니다.")
                return {}
            
            # 헤더 행 찾기
            header_row = all_values[0]
            
            # 종목코드, 종목명, 섹터 컬럼 인덱스 찾기
            code_idx = header_row.index("종목코드") if "종목코드" in header_row else 0
            sector_idx = header_row.index("섹터") if "섹터" in header_row else 2
            
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
            
            logger.info(f"총 {len(sector_dict)}개 종목의 섹터 정보를 읽었습니다.")
            return sector_dict
            
        except Exception as e:
            logger.error(f"섹터 딕셔너리 가져오기 실패: {str(e)}")
            return {}
        