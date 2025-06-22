"""
RS(상대강도) 데이터 수집 및 관리 서비스

이 모듈은 구글 시트에서 RS 데이터를 가져와서 캐시하고 
API 엔드포인트에서 사용할 수 있도록 제공하는 서비스입니다.
"""
import json
import os
import asyncio
import concurrent.futures
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from loguru import logger

from stockeasy.collector.core.config import get_settings

from stockeasy.services.google_sheet_service import GoogleSheetService
from stockeasy.collector.schemas.rs_schemas import (
    RSData, 
    RSDataResponse, 
    CompressedRSDataResponse,
    SingleRSDataResponse
)

settings = get_settings()

class RSService:
    """RS(상대강도) 데이터 수집 및 관리 서비스"""
    
    def __init__(self):
        """서비스 초기화"""
        # 로컬 캐시 디렉토리 경로 설정
        cache_dir = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),  # collector 디렉토리
            "local_cache"
        )
        self.cache_file_path = os.path.join(cache_dir, "rs_data_cache.json")
        self.cache_expiry_hours = 24  # 캐시 만료 시간 (24시간)
        self._cache_data: Optional[Dict[str, Any]] = None
        self._last_update: Optional[datetime] = None
        
        # 구글 시트 설정
        self.credentials_path = "/backend/credentials/kospi-updown-8110d336c4bb.json"
        self.sheet_url = "https://docs.google.com/spreadsheets/d/1NxuYRgYhVTlhivO2_xmsHVEyBQirgB171rcRuF5bmaw/edit?gid=0#gid=0"
        
        # 캐시 디렉토리 생성
        os.makedirs(os.path.dirname(self.cache_file_path), exist_ok=True)
        
        logger.info(f"RSService 초기화 완료 - 캐시 경로: {self.cache_file_path}")
    
    def _safe_float(self, value: Any) -> Optional[float]:
        """안전한 float 변환"""
        if value is None or value == '' or value == '-':
            return None
        try:
            return float(str(value).replace(',', ''))
        except (ValueError, TypeError):
            return None
    
    def _parse_rs_data_from_sheet(self, all_values: List[List[str]]) -> List[RSData]:
        """시트 데이터를 RSData 리스트로 변환"""
        if not all_values or len(all_values) < 2:
            logger.warning("시트에 충분한 데이터가 없습니다")
            return []
        
        # 헤더 행 확인
        header_row = all_values[0]
        logger.info(f"시트 헤더: {header_row}")
        
        # 컬럼 인덱스 찾기
        try:
            code_idx = header_row.index("종목코드")
            name_idx = header_row.index("종목명")
            sector_idx = header_row.index("업종") if "업종" in header_row else None
            rs_idx = header_row.index("RS") if "RS" in header_row else None
            rs_1m_idx = header_row.index("RS_1M") if "RS_1M" in header_row else None
            rs_2m_idx = header_row.index("RS_2M") if "RS_2M" in header_row else None
            rs_3m_idx = header_row.index("RS_3M") if "RS_3M" in header_row else None
            rs_6m_idx = header_row.index("RS_6M") if "RS_6M" in header_row else None
            mmt_idx = header_row.index("MMT") if "MMT" in header_row else None
        except ValueError as e:
            logger.error(f"필수 컬럼을 찾을 수 없습니다: {e}")
            return []
        
        logger.info(f"컬럼 인덱스 - 종목코드: {code_idx}, 종목명: {name_idx}, 업종: {sector_idx}, RS: {rs_idx}")
        
        # 데이터 파싱
        rs_data_list = []
        for i, row in enumerate(all_values[1:], 2):  # 헤더 제외
            try:
                if not row or len(row) <= code_idx or not row[code_idx]:
                    continue
                
                stock_code = row[code_idx].strip()
                stock_name = row[name_idx].strip() if len(row) > name_idx else ""
                
                # 필수 필드 검증
                if not stock_code or not stock_name:
                    continue
                
                rs_data = RSData(
                    stock_code=stock_code,
                    stock_name=stock_name,
                    sector=row[sector_idx].strip() if sector_idx is not None and len(row) > sector_idx else None,
                    rs=self._safe_float(row[rs_idx] if rs_idx is not None and len(row) > rs_idx else None),
                    rs_1m=self._safe_float(row[rs_1m_idx] if rs_1m_idx is not None and len(row) > rs_1m_idx else None),
                    rs_2m=self._safe_float(row[rs_2m_idx] if rs_2m_idx is not None and len(row) > rs_2m_idx else None),
                    rs_3m=self._safe_float(row[rs_3m_idx] if rs_3m_idx is not None and len(row) > rs_3m_idx else None),
                    rs_6m=self._safe_float(row[rs_6m_idx] if rs_6m_idx is not None and len(row) > rs_6m_idx else None),
                    mmt=self._safe_float(row[mmt_idx] if mmt_idx is not None and len(row) > mmt_idx else None)
                )
                rs_data_list.append(rs_data)
                
            except Exception as e:
                logger.warning(f"행 {i} 파싱 실패: {e}")
                continue
        
        logger.info(f"총 {len(rs_data_list)}개의 RS 데이터를 파싱했습니다")
        return rs_data_list
    
    async def _fetch_rs_data_from_google_sheet(self) -> List[RSData]:
        """구글 시트에서 RS 데이터 가져오기"""
        try:
            logger.info("구글 시트에서 RS 데이터 가져오기 시작")
            
            # ThreadPoolExecutor로 실행하고 타임아웃 설정
            executor = concurrent.futures.ThreadPoolExecutor()
            
            def get_rs_from_sheet():
                # 구글 시트 서비스 초기화
                sheet_service = GoogleSheetService(credentials_path=self.credentials_path)
                
                # 시트 열기
                worksheet = sheet_service.open_sheet_by_url(self.sheet_url)
                
                # 모든 데이터 가져오기
                return sheet_service.get_all_values(worksheet)
            
            try:
                logger.info("구글 시트 요청 시작 (60초 타임아웃)")
                future = executor.submit(get_rs_from_sheet)
                all_values = future.result(timeout=60)
                
                logger.info(f"구글 시트에서 {len(all_values)}행의 데이터를 가져왔습니다")
                
                # 데이터 파싱
                rs_data_list = self._parse_rs_data_from_sheet(all_values)
                return rs_data_list
                
            except concurrent.futures.TimeoutError:
                logger.warning("구글 시트 요청 타임아웃 (60초 초과)")
                return []
            finally:
                executor.shutdown(wait=False)
                
        except Exception as e:
            logger.error(f"구글 시트에서 RS 데이터 가져오기 실패: {e}")
            return []
    
    def _load_cache_from_file(self) -> Optional[Dict[str, Any]]:
        """파일에서 캐시 데이터 로드"""
        try:
            if not os.path.exists(self.cache_file_path):
                return None
            
            with open(self.cache_file_path, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
            
            # 캐시 만료 체크
            last_update_str = cache_data.get('last_updated')
            if last_update_str:
                last_update = datetime.fromisoformat(last_update_str)
                if datetime.now() - last_update > timedelta(hours=self.cache_expiry_hours):
                    logger.info("캐시가 만료되었습니다")
                    return None
            
            logger.info(f"캐시에서 {len(cache_data.get('data', []))}개의 RS 데이터를 로드했습니다")
            return cache_data
            
        except Exception as e:
            logger.error(f"캐시 파일 로드 실패: {e}")
            return None
    
    def _save_cache_to_file(self, rs_data_list: List[RSData]) -> None:
        """캐시 데이터를 파일에 저장"""
        try:
            cache_data = {
                'last_updated': datetime.now().isoformat(),
                'count': len(rs_data_list),
                'data': [data.dict() for data in rs_data_list]
            }
            
            with open(self.cache_file_path, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2, default=str)
            
            logger.info(f"캐시 파일에 {len(rs_data_list)}개의 RS 데이터를 저장했습니다")
            
        except Exception as e:
            logger.error(f"캐시 파일 저장 실패: {e}")
    
    async def get_all_rs_data(self, force_update: bool = False) -> List[RSData]:
        """모든 RS 데이터 조회"""
        try:
            # 강제 업데이트가 아니면 캐시부터 확인
            if not force_update and self._cache_data is None:
                self._cache_data = self._load_cache_from_file()
            
            # 캐시가 있고 강제 업데이트가 아니면 캐시 데이터 사용
            if not force_update and self._cache_data is not None:
                rs_data_list = [RSData(**data) for data in self._cache_data['data']]
                self._last_update = datetime.fromisoformat(self._cache_data['last_updated'])
                logger.info(f"캐시에서 {len(rs_data_list)}개의 RS 데이터를 반환합니다")
                return rs_data_list
            
            # 구글 시트에서 새로운 데이터 가져오기
            logger.info("구글 시트에서 최신 RS 데이터를 가져옵니다")
            rs_data_list = await self._fetch_rs_data_from_google_sheet()
            
            if rs_data_list:
                # 메모리 캐시 업데이트
                self._cache_data = {
                    'last_updated': datetime.now().isoformat(),
                    'count': len(rs_data_list),
                    'data': [data.dict() for data in rs_data_list]
                }
                self._last_update = datetime.now()
                
                # 파일 캐시 저장
                self._save_cache_to_file(rs_data_list)
                
                logger.info(f"새로운 RS 데이터 {len(rs_data_list)}개를 가져왔습니다")
            
            return rs_data_list
            
        except Exception as e:
            logger.error(f"RS 데이터 조회 실패: {e}")
            return []
    
    async def get_rs_data_by_code(self, stock_code: str) -> Optional[RSData]:
        """특정 종목의 RS 데이터 조회"""
        try:
            all_data = await self.get_all_rs_data()
            
            for rs_data in all_data:
                if rs_data.stock_code == stock_code:
                    return rs_data
            
            return None
            
        except Exception as e:
            logger.error(f"종목 {stock_code} RS 데이터 조회 실패: {e}")
            return None
    
    async def get_multiple_rs_data(self, stock_codes: List[str]) -> Dict[str, Optional[RSData]]:
        """여러 종목의 RS 데이터 조회"""
        try:
            # 모든 데이터를 한 번에 가져오기
            all_data = await self.get_all_rs_data()
            
            # 종목코드를 키로 하는 딕셔너리 생성
            rs_dict = {rs_data.stock_code: rs_data for rs_data in all_data}
            
            # 요청된 종목들의 데이터 수집
            results = {}
            found_count = 0
            
            for stock_code in stock_codes:
                if stock_code in rs_dict:
                    results[stock_code] = rs_dict[stock_code]
                    found_count += 1
                else:
                    results[stock_code] = None
            
            logger.info(f"여러 종목 RS 데이터 조회 완료: {found_count}/{len(stock_codes)}개 성공")
            return results
            
        except Exception as e:
            logger.error(f"여러 종목 RS 데이터 조회 실패: {e}")
            # 실패 시 모든 종목을 None으로 반환
            return {stock_code: None for stock_code in stock_codes}
    
    async def update_rs_data(self, force_update: bool = False) -> Dict[str, Any]:
        """RS 데이터 업데이트"""
        try:
            logger.info("RS 데이터 업데이트 시작")
            
            rs_data_list = await self.get_all_rs_data(force_update=True)
            
            result = {
                "message": "RS 데이터 업데이트 완료",
                "updated_count": len(rs_data_list),
                "last_updated": datetime.now(),
                "status": "success"
            }
            
            logger.info(f"RS 데이터 업데이트 완료: {len(rs_data_list)}개")
            return result
            
        except Exception as e:
            logger.error(f"RS 데이터 업데이트 실패: {e}")
            return {
                "message": f"RS 데이터 업데이트 실패: {str(e)}",
                "updated_count": 0,
                "last_updated": datetime.now(),
                "status": "error"
            }
    
    def get_last_update_time(self) -> Optional[datetime]:
        """마지막 업데이트 시간 조회"""
        return self._last_update
    
    async def create_standard_response(self, rs_data_list: List[RSData]) -> RSDataResponse:
        """표준 RS 데이터 응답 생성"""
        return RSDataResponse(
            count=len(rs_data_list),
            last_updated=self.get_last_update_time(),
            data=rs_data_list,
            status="success"
        )
    
    async def create_compressed_response(self, rs_data_list: List[RSData]) -> CompressedRSDataResponse:
        """압축된 RS 데이터 응답 생성"""
        headers = ["stock_code", "stock_name", "sector", "rs", "rs_1m", "rs_2m", "rs_3m", "rs_6m", "mmt"]
        
        compressed_data = []
        for rs_data in rs_data_list:
            row = [
                rs_data.stock_code,
                rs_data.stock_name,
                rs_data.sector,
                rs_data.rs,
                rs_data.rs_1m,
                rs_data.rs_2m,
                rs_data.rs_3m,
                rs_data.rs_6m,
                rs_data.mmt
            ]
            compressed_data.append(row)
        
        return CompressedRSDataResponse(
            count=len(rs_data_list),
            last_updated=self.get_last_update_time(),
            compressed=True,
            headers=headers,
            data=compressed_data,
            status="success"
        )


# 전역 인스턴스
rs_service = RSService() 