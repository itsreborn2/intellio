import uvicorn
from common.app import app                              # 공통 FastAPI 앱 가져오기
from common.api.v1.admin import router as admin_router   # 관리자 API 라우터 가져오기
from common.api.v1.auth import router as auth_router    # 인증 API 라우터 가져오기
from common.api.v1.session import router as session_router  # 세션 API 라우터 가져오기
from common.auth import router as auth_router           # 공통 인증 라우터 가져오기
from doceasy.main import router as doceasy_router         # 도큐시 서비스 라우터 가져오기

# 이 파일은 백엔드 API의 진입점입니다.
# uvicorn을 사용하여 FastAPI 앱을 실행합니다.
# 공통 인증 라우터를 '/auth' 경로로 포함
app.include_router(auth_router, prefix="/auth")
# 공통 API 라우터 등록
app.include_router(admin_router, prefix="/api/v1/admin")    # 관리자 API 등록
app.include_router(auth_router, prefix="/api/v1/auth")     # 인증 API 등록
app.include_router(session_router, prefix="/api/v1/session")  # 세션 API 등록
# 도큐시 서비스 라우터 포함
app.include_router(doceasy_router)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)          # 포트 8000에서 서버 실행
