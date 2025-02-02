from uuid import UUID
from typing import List, Optional, Dict
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, Form, BackgroundTasks, Cookie
from sqlalchemy.ext.asyncio import AsyncSession
import logging
from app.models.user import Session

from app.api import deps
from app.core.deps import get_current_session
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
logger.setLevel(logging.DEBUG)


router = APIRouter()  # prefix 제거, 태그만 설정

@router.post("/projects/{project_id}/upload", response_model=DocumentUploadResponse)
async def upload_documents(
    project_id: UUID,
    files: list[UploadFile] = File(...),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: AsyncSession = Depends(deps.get_async_db),
    session: Session = Depends(get_current_session),
) -> DocumentUploadResponse:
    #print("upload_documents 여기 오나 안오나")
    """문서 업로드 API - 지정된 프로젝트에 문서 업로드"""
    logger.info(f"문서 업로드 시작")
    logger.info(f"업로드된 파일 수: {len(files)}")
    
    if not session.user_id:
        raise HTTPException(status_code=401, detail="Session ID is required")
        
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")
        
    # 파일 정보 로깅
    for file in files:
        logger.info(f"파일 정보 - 이름: {file.filename}, 타입: {file.content_type}")
    
    try:
        logger.info(f"프로젝트 확인")
        # 프로젝트 존재 여부 확인
        project_service = ProjectService(db)
        project = await project_service.get(project_id, session.user_id)#session_id)
        if not project:
            logger.info(f"Project not found or not accessible")
            raise HTTPException(status_code=404, detail="Project not found or not accessible")
        logger.info(f"문서 업로드 중.")
        # 문서 업로드 처리
        document_service = DocumentService(db)
        documents = await document_service.upload_documents(
            project_id=project_id,
            user_id=session.user_id,
            files=files,
            background_tasks=background_tasks
        )
        logger.info(f"완료")
        logger.info(f"user id:{session.user_id}, prject id:{project_id}")
        for doc in documents:
            logger.info(f"doc_id:{doc.id}, file:{doc.filename}, status:{doc.status}")
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

@router.get("/list/{project_id}")
async def get_document_list(
    project_id: str,
    document_service: DocumentService = Depends(deps.get_document_service)
) -> DocumentListResponse:
    """프로젝트에 속한 모든 문서 목록을 반환합니다."""
    try:
        logger.info(f"문서 리스트 요청 : {project_id}")
        # document_service를 사용하여 프로젝트의 문서 목록 조회
        documents = await document_service.get_documents_by_project(project_id)
        logger.info(f"조회된 문서 목록: {documents}")
        
        # export interface IDocument {
        # id: string
        # filename: string
        # project_id: string
        # status: IDocumentStatus
        # content_type?: string
        # added_col_context?: Array<ICell> // 추가된 셀. 헤더정보(name), 셀내용
        # }
        # Document 모델을 DocumentResponse로 변환
        document_responses = []
        for doc in documents:
            try:
                logger.info(f"문서 변환 시도: {doc.id}")
                response = DocumentResponse(
                    id=doc.id,
                    project_id=doc.project_id,
                    filename=doc.filename,
                    created_at=doc.created_at if hasattr(doc, 'created_at') else None,
                    updated_at=doc.updated_at if hasattr(doc, 'updated_at') else None,
                    mime_type=None,  # Optional 필드로 변경됨
                    file_size=doc.file_size,
                    file_path=doc.file_path,
                    status=doc.status,
                    error_message=doc.error_message if hasattr(doc, 'error_message') else None,
                    chunk_count=doc.chunk_count if hasattr(doc, 'chunk_count') else 0,
                    download_url=None,  # 필요한 경우 URL 생성 로직 추가
                    embedding_ids=doc.embedding_ids if hasattr(doc, 'embedding_ids') else None,
                    extracted_text=doc.extracted_text if hasattr(doc, 'extracted_text') else None
                )
                document_responses.append(response)
                logger.info(f"문서 변환 성공: {doc.id}")
            except Exception as e:
                logger.error(f"문서 변환 실패 {doc.id}: {str(e)}")
                continue
        
        logger.info(f"변환 완료된 문서 수: {len(document_responses)}")
        
        # DocumentListResponse 형식으로 반환
        return DocumentListResponse(
            items=document_responses
        )
        
    except Exception as e:
        logger.error(f"문서 목록 조회 중 오류 발생: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"문서 목록 조회 중 오류가 발생했습니다: {str(e)}"
        )
