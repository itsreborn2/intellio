from fastapi import APIRouter
from . import document, project, rag, session, auth, category, admin
import logging

logger = logging.getLogger(__name__)

api_router = APIRouter()

# 라우터 등록 시 로깅 추가
logger.info("API 라우터 등록 시작")

api_router.include_router(document.router, prefix="/documents", tags=["documents"])
logger.info("문서 라우터 등록 완료")

api_router.include_router(project.router, prefix="/projects", tags=["projects"])
logger.info("프로젝트 라우터 등록 완료")

api_router.include_router(rag.router, prefix="/rag", tags=["rag"])
logger.info("RAG 라우터 등록 완료")

api_router.include_router(session.router, tags=["sessions"]) #prefix가 없다. 나중에 추가하는게 유지보수에 좋다.
logger.info("세션 라우터 등록 완료")

api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
logger.info("인증 라우터 등록 완료")

api_router.include_router(category.router, prefix="/categories", tags=["categories"])
logger.info("카테고리 라우터 등록 완료")

api_router.include_router(admin.router, prefix="/admin", tags=["admin"])
logger.info("관리자 라우터 등록 완료")

logger.info("모든 API 라우터 등록 완료")
