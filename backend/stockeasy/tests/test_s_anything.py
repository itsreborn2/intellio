"""
PostgreSQL 유휴 세션 정리 스크립트
"""

import asyncio
import os
from pprint import pprint
import sys
import logging
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# 환경 변수 설정 - production 환경으로 명시적 설정
os.environ["ENV"] = "production"
os.environ["ENVIRONMENT"] = "production"
from stockeasy.services.financial.data_service_db import FinancialDataServiceDB
from common.core.database import get_db, get_db_async, get_db_session
from dotenv import load_dotenv
# from common.core.config import settings
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
# from common.core.database import get_db_session
from datetime import timedelta

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# 환경 변수 로드
load_dotenv()


async def main():
    db = await get_db_session()
    try:
        service = FinancialDataServiceDB(db)
        seacrh_result = await service.get_financial_data("000660")
        pprint(seacrh_result, indent=2)
    finally:
        await db.close()

    

if __name__ == "__main__":
    asyncio.run(main()) 