from uuid import UUID
from typing import List, Optional, Dict
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, Form, BackgroundTasks, Cookie
from sqlalchemy.ext.asyncio import AsyncSession
import logging
from common.models.user import Session
from sse_starlette import EventSourceResponse
import json

from common.core.database import get_db_async
from common.core.deps import get_current_session

from doceasy.core import deps
from doceasy.schemas.document import (
    DocumentResponse,
    DocumentListResponse,
    DocumentQueryRequest,
    DocumentUploadResponse
)
from doceasy.services.document import DocumentService
from doceasy.services.project import ProjectService
from doceasy.services.rag import RAGService

logger = logging.getLogger(__name__)


router = APIRouter()  # prefix 제거, 태그만 설정

@router.post("/projects/{project_id}/upload")
async def upload_documents(
    project_id: UUID,
    files: list[UploadFile] = File(...),
    db: AsyncSession = Depends(get_db_async),
    session: Session = Depends(get_current_session),
) -> EventSourceResponse:
    """문서 업로드 API - 지정된 프로젝트에 문서 업로드
    SSE(Server-Sent Events)를 사용하여 실시간으로 업로드 진행상황을 클라이언트에 전송
    """
    logger.info(f"문서 업로드 시작")
    logger.info(f"업로드된 파일 수: {len(files)}")
    
    if not session.user_id:
        raise HTTPException(status_code=401, detail="Session ID is required")
        
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")

    # 파일 내용을 미리 읽어서 메모리에 저장
    file_contents = []
    failed_files = []
    
    for file in files:
        try:
            content = await file.read()
            file_contents.append({
                "filename": file.filename,
                "content": content,
                "content_type": file.content_type,
                "size": len(content)
            })
        except Exception as e:
            logger.exception(f"파일 읽기 실패 {file.filename}: {str(e)}")
            failed_files.append({
                "filename": file.filename,
                "error": f"파일 읽기 실패: {str(e)}"
            })

    # 파일 읽기 실패가 있으면 바로 에러 응답
    if len(failed_files) == len(files):
        raise HTTPException(
            status_code=400,
            detail={
                "message": "모든 파일 읽기 실패",
                "failed_files": failed_files
            }
        )

    async def event_generator():
        try:
            # 문서 업로드 처리
            document_service = DocumentService(db)
            total_files = len(file_contents)
            processed_files = 0

            # 읽은 파일 내용으로 처리 진행
            for file_data in file_contents:
                try:
                    logger.info(f"Processing file: {file_data['filename']}")
                    document = await document_service.upload_single_document(
                        project_id=project_id,
                        user_id=session.user_id,
                        filename=file_data['filename'],
                        content=file_data['content'],
                        content_type=file_data['content_type'],
                        file_size=file_data['size']
                    )
                    processed_files += 1
                    #logger.warning(f"Processed file: {file_data['filename']}")

                    # 진행상황 전송
                    progress_data = {
                        "filename": file_data['filename'],
                        "total_files": total_files,
                        "processed_files": processed_files,
                        "document": {
                            "id": str(document.id),
                            "filename": document.filename,
                            "content_type": document.file_type,
                            "status": document.status
                        }
                    }
                    result = json.dumps({'event': 'upload_progress', 'data': progress_data})
                    logger.warning(f"Progress data: {result}")
                    yield result

                except Exception as e:
                    logger.exception(f"File processing error: {str(e)}")
                    error_data = {
                        "filename": file_data['filename'],
                        "error": str(e)
                    }
                    yield json.dumps({'event': 'upload_error', 'data': error_data})

            # 실패한 파일이 있으면 에러 메시지 전송
            for failed_file in failed_files:
                yield json.dumps({'event': 'upload_error', 'data': failed_file})

            # 모든 파일 처리 완료
            complete_data = {
                "message": "All files processed",
                "total_processed": processed_files,
                "total_failed": len(failed_files)
            }
            yield json.dumps({'event': 'upload_complete', 'data': complete_data})

        except Exception as e:
            logger.error(f"문서 업로드 중 오류 발생: {str(e)}")
            error_data = {"error": str(e)}
            yield json.dumps({'event': 'error', 'data': error_data})

    return EventSourceResponse(event_generator())

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
        logger.info(f"문서 삭제 시작: {document_id}")
        await document_service.delete_document(document_id)
        logger.info(f"문서 삭제 완료: {document_id}")
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
                #logger.info(f"문서 변환 시도: {doc.id}")
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
