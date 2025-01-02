from fastapi import APIRouter
from . import document, project, rag, session, auth, category

api_router = APIRouter()
api_router.include_router(document.router, prefix="/documents", tags=["documents"])
api_router.include_router(project.router, prefix="/projects", tags=["projects"])
api_router.include_router(rag.router, prefix="/rag", tags=["rag"])
api_router.include_router(session.router, tags=["sessions"]) #prefix가 없다. 나중에 추가하는게 유지보수에 좋다.
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(category.router, prefix="/categories", tags=["categories"])
