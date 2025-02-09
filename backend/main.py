import uvicorn
from common.app import app                              # 공통 FastAPI 앱 가져오기
from common.api.v1 import api_router_common
from common.core.config import settings
from doceasy.api.v1 import api_router_doceasy         # 닥이지 서비스 라우터 가져오기
from stockeasy.api.v1 import stockeasy_router         # 스탁이지 서비스 라우터 가져오기
from dotenv import load_dotenv
import logging
from loguru import logger
# 이 파일은 백엔드 API의 진입점입니다.

# uvicorn을 사용하여 FastAPI 앱을 실행합니다.
# 환경변수를 가장 먼저 로드

logger.info(f"시작 : {settings.API_V1_STR}")


# API 라우터 등록
app.include_router(api_router_common, prefix=settings.API_V1_STR) # Common api router 등록

# 닥이지 서비스 라우터 포함
app.include_router(api_router_doceasy, prefix=settings.API_V1_STR)

# 스탁이지 라우터
app.include_router(stockeasy_router, prefix=settings.API_V1_STR)

# if __name__ == "__main__":
#     uvicorn.run(app, host="0.0.0.0", port=8000)          # 포트 8000에서 서버 실행
