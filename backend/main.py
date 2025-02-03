import uvicorn
from common.app import app                              # 공통 FastAPI 앱 가져오기
#from common.api.v1 import api_router
#from doceasy.main import router as doceasy_router         # 닥이지 서비스 라우터 가져오기

# 이 파일은 백엔드 API의 진입점입니다.
# uvicorn을 사용하여 FastAPI 앱을 실행합니다.

# API 라우터 등록
#app.include_router(api_router, prefix=settings.API_V1_STR) # Common api router 등록

# 닥이지 서비스 라우터 포함
#app.include_router(doceasy_router)

# 스탁이지 라우터도 나중에 포함

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)          # 포트 8000에서 서버 실행
