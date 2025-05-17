import asyncio
import json
from loguru import logger # loguru import 추가
import os
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from common.core.database import get_db_session
# 모든 관련 모델 임포트
from stockeasy.models.companies import Company
from stockeasy.models.financial_reports import FinancialReport
from stockeasy.models.financial_data import FinancialItemMapping, FinancialItemRawMapping, SummaryFinancialData

# logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s") # 삭제
# logger = logging.getLogger(__name__) # 삭제

async def insert_companies():
    """
    stock_info.json 파일에서 회사 정보를 읽어 데이터베이스에 삽입합니다.
    """
    # JSON 파일 경로
    json_file_path = os.path.join("stockeasy", "local_cache", "stock_info.json")
    
    if not os.path.exists(json_file_path):
        logger.error(f"파일이 존재하지 않습니다: {json_file_path}")
        return
    
    try:
        # JSON 파일 읽기
        with open(json_file_path, 'r', encoding='utf-8') as f:
            stock_info = json.load(f)
        
        # by_code 키가 없는 경우 처리
        if "by_code" not in stock_info:
            logger.error("JSON 파일에 'by_code' 키가 없습니다.")
            return
        
        # DB 세션 생성
        db = await get_db_session()
        
        try:
            # 각 회사 정보 처리
            company_count = 0
            already_exists = 0
            
            for code, info in stock_info["by_code"].items():
                try:
                    # 이미 존재하는지 확인
                    result = await db.execute(
                        select(Company).where(Company.company_code == code)
                    )
                    existing = result.scalar_one_or_none()
                    
                    if existing:
                        logger.info(f"이미 존재하는 회사: {code} - {info.get('name', '이름 없음')}")
                        already_exists += 1
                        continue
                    
                    # 회사 이름 가져오기
                    company_name = info.get("name", "")
                    if not company_name:
                        logger.warning(f"회사 이름이 없습니다: {code}, 건너뜁니다.")
                        break
                    
                    # 섹터 정보 처리
                    sectors = info.get("sector", [])
                    if isinstance(sectors, list):
                        sector_str = ",".join(sectors)
                    else:
                        sector_str = str(sectors)
                    
                    # 기본 컬럼만 사용하여 회사 데이터 생성 (relationship 제외)
                    company = Company()
                    company.company_code = code
                    company.company_name = company_name
                    company.market_type = "KOSPI"  # 모두 KOSPI로 통일
                    company.sector = sector_str
                    company.is_active = True
                    
                    # DB에 추가
                    db.add(company)
                    company_count += 1
                    
                    # 20개마다 커밋 (대량 삽입 시 성능 향상)
                    if company_count % 20 == 0:
                        await db.commit()
                        logger.info(f"{company_count}개 회사 정보 삽입 완료")
                except Exception as e:
                    logger.error(f"회사 {code} 처리 중 오류: {e}")
                    continue
            
            # 남은 변경사항 커밋
            if company_count % 20 != 0:
                await db.commit()
            
            logger.info(f"총 {company_count}개 회사 정보 삽입 완료, {already_exists}개 기존 회사 건너뜀")
            
        except Exception as e:
            await db.rollback()
            logger.error(f"회사 정보 삽입 중 오류 발생: {e}")
        finally:
            await db.close()
            
    except Exception as e:
        logger.error(f"스크립트 실행 중 오류 발생: {e}")

async def main():
    """메인 함수"""
    await insert_companies()

if __name__ == "__main__":
    asyncio.run(main()) 