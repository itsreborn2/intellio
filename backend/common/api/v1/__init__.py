from fastapi import APIRouter
from common.api.v1 import admin, dashboard, session, auth, token_usage
import logging

logger = logging.getLogger(__name__)

api_router_common = APIRouter()

# 라우터 등록 시 로깅 추가
logger.info("COMMON API 라우터 등록 시작")

api_router_common.include_router(session.router) #prefix가 없다. 나중에 추가하는게 유지보수에 좋다.
logger.info("세션 라우터 등록 완료")

api_router_common.include_router(auth.router) #  prefix="/auth", tags=["auth"]
logger.info("인증 라우터 등록 완료")

api_router_common.include_router(token_usage.router) 
logger.info("인증 라우터 등록 완료")

api_router_common.include_router(admin.router) # prefix="/admin", tags=["admin"]
api_router_common.include_router(dashboard.router) # prefix="/dashboard", tags=["dashboard"]
logger.info("관리자 라우터 등록 완료")


logger.info("모든 COMMON API 라우터 등록 완료")
