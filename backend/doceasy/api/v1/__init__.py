from fastapi import APIRouter
from . import document, project, rag,  category, table_history
from loguru import logger

# logger = logging.getLogger(__name__)

api_router_doceasy = APIRouter()

# 라우터 등록 시 로깅 추가
logger.info("API 라우터 등록 시작")

api_router_doceasy.include_router(document.router, prefix="/documents", tags=["documents"])
logger.info("문서 라우터 등록 완료")

api_router_doceasy.include_router(project.router, prefix="/projects", tags=["projects"])
logger.info("프로젝트 라우터 등록 완료")

api_router_doceasy.include_router(rag.router)
logger.info("RAG 라우터 등록 완료")

api_router_doceasy.include_router(category.router, prefix="/categories", tags=["categories"])
logger.info("카테고리 라우터 등록 완료")

api_router_doceasy.include_router(table_history.router)
logger.info("테이블 히스토리 라우터 등록 완료")

logger.info("모든 API 라우터 등록 완료")
