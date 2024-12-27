from uuid import UUID
from typing import List, Optional
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, Form, BackgroundTasks, Cookie
from sqlalchemy.ext.asyncio import AsyncSession
import logging

from app.api import deps
from app.schemas.document import (
    DocumentResponse,
    DocumentListResponse,
    DocumentQueryRequest,
    DocumentUploadResponse
)
from app.services.document import DocumentService
from app.services.project import ProjectService
from app.services.rag import RAGService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["documents"])  # prefix 제거, 태그만 설정

@router.post("/projects/{project_id}/upload", response_model=DocumentUploadResponse)
async def upload_documents(
    project_id: UUID,
    files: list[UploadFile] = File(...),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: AsyncSession = Depends(deps.get_async_db),
    session_id: Optional[str] = Cookie(None)
) -> DocumentUploadResponse:
    """문서 업로드 API - 지정된 프로젝트에 문서 업로드"""
    logger.info(f"문서 업로드 시작")
    logger.info(f"업로드된 파일 수: {len(files)}")
    
    if not session_id:
        raise HTTPException(status_code=401, detail="Session ID is required")
        
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")
        
    # 파일 정보 로깅
    for file in files:
        logger.info(f"파일 정보 - 이름: {file.filename}, 타입: {file.content_type}")
    
    try:
        # 프로젝트 존재 여부 확인
        project_service = ProjectService(db)
        project = await project_service.get(project_id, session_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found or not accessible")
        
        # 문서 업로드 처리
        document_service = DocumentService(db)
        documents = await document_service.upload_documents(
            project_id=project_id,
            session_id=session_id,
            files=files,
            background_tasks=background_tasks
        )
        
        return DocumentUploadResponse(
            success=True,
            project_id=project_id,
            document_ids=[doc.id for doc in documents],
            documents=[{
                "id": doc.id,
                "filename": doc.filename,
                "content_type": doc.mime_type,
                "status": doc.status
            } for doc in documents],
            errors=[],
            failed_uploads=0,
            message="Upload started"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"문서 업로드 중 오류 발생: {str(e)}")
        # 더 자세한 에러 메시지 반환
        return DocumentUploadResponse(
            success=False,
            project_id=project_id,
            document_ids=[],
            documents=[],
            errors=[{"filename": file.filename, "error": str(e)} for file in files],
            failed_uploads=len(files),
            message=f"Upload failed: {str(e)}"
        )

@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: UUID,
    document_service: DocumentService = Depends(deps.get_document_service)
) -> DocumentResponse:
    """문서 상세 정보 조회"""
    try:
        document = await document_service.get_document(document_id)
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")
        return DocumentResponse.model_validate(document)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{document_id}")
async def delete_document(
    document_id: UUID,
    document_service: DocumentService = Depends(deps.get_document_service)
) -> dict:
    """문서 삭제"""
    try:
        await document_service.delete_document(document_id)
        return {"success": True, "message": "Document deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/search")
async def search_documents(
    query: str,
    top_k: int = 5,
    document_service: DocumentService = Depends(deps.get_document_service)
) -> List[dict]:
    """문서 검색 API - 질문과 유사한 문서 청크를 검색"""
    try:
        # RAG 서비스를 통한 검색
        rag_service = RAGService()
        results = await rag_service.search_similar(query, top_k=top_k)
        return results
        
    except Exception as e:
        logger.error(f"문서 검색 중 오류 발생: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to search documents: {str(e)}"
        )
