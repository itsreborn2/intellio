import uvicorn
from common.app import app                              # 공통 FastAPI 앱 가져오기
from common.api.v1 import api_router_common
from common.core.config import settings
from doceasy.api.v1 import api_router_doceasy         # 닥이지 서비스 라우터 가져오기
from stockeasy.api.v1 import stockeasy_router         # 스탁이지 서비스 라우터 가져오기
from dotenv import load_dotenv
import logging
from loguru import logger
from datetime import datetime
import pytz

# 서울 타임존 설정
seoul_tz = pytz.timezone('Asia/Seoul')

class SeoulFormatter(logging.Formatter):
    def formatTime(self, record, datefmt=None):
        dt = datetime.fromtimestamp(record.created, seoul_tz)
        if datefmt:
            return dt.strftime(datefmt)
        else:
            return dt.isoformat()

# 로깅 설정
logging.basicConfig(level=logging.DEBUG)

# 핸들러에 포맷터 설정
for handler in logging.getLogger().handlers:
    handler.setFormatter(SeoulFormatter())

logger.info(f"시작 : {settings.API_V1_STR}")

# API 라우터 등록
app.include_router(api_router_common, prefix=settings.API_V1_STR) # Common api router 등록

# 닥이지 서비스 라우터 포함
app.include_router(api_router_doceasy, prefix=settings.API_V1_STR)

# 스탁이지 라우터
app.include_router(stockeasy_router, prefix=settings.API_V1_STR)

# if __name__ == "__main__":
#     uvicorn.run(app, host="0.0.0.0", port=8000)          # 포트 8000에서 서버 실행
