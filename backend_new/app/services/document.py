from uuid import UUID, uuid4
from typing import List, Optional
from fastapi import UploadFile, BackgroundTasks, HTTPException
import logging
import json
import re
from datetime import datetime

from app.models.document import Document
from app.models.project import Project
from app.services.storage import StorageService
from app.services.extractor import DocumentExtractor
from app.core.redis import redis_client
from app.core.celery_app import celery
from sqlalchemy import select

# 문서 상태 상수 정의
DOCUMENT_STATUS_REGISTERED = 'REGISTERED'
DOCUMENT_STATUS_UPLOADING = 'UPLOADING'
DOCUMENT_STATUS_UPLOADED = 'UPLOADED'
DOCUMENT_STATUS_PROCESSING = 'PROCESSING'
DOCUMENT_STATUS_COMPLETED = 'COMPLETED'
DOCUMENT_STATUS_PARTIAL = 'PARTIAL'
DOCUMENT_STATUS_ERROR = 'ERROR'
DOCUMENT_STATUS_DELETED = 'DELETED'

logger = logging.getLogger(__name__)

class DocumentService:
    def __init__(self, db=None):
        self.db = db
        self.allowed_mime_types = [
            'text/plain',
            'application/pdf',
            'application/msword',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'application/vnd.openxmlformats-officedocument.presentationml.presentation',
            'application/x-hwp',  # HWP 파일 MIME 타입
            'application/haansofthwp',  # 대체 HWP MIME 타입
            'application/vnd.hancom.hwp'  # 또 다른 HWP MIME 타입
        ]
        self.storage = StorageService()
        self.extractor = DocumentExtractor()

    def _is_allowed_file(self, content_type: str) -> bool:
        """파일 타입 검증"""
        return content_type in self.allowed_mime_types

    async def process_document_async(self, doc_id: UUID) -> None:
        """문서 처리 Celery 태스크 실행"""
        try:
            # Celery 태스크 이름으로 태스크 실행
            celery.send_task(
                'app.workers.document.process_document',
                args=[str(doc_id)],
                queue='document-processing'
            )
            logger.info(f"문서 처리 태스크 시작됨: {doc_id}")
        except Exception as e:
            logger.error(f"문서 처리 태스크 시작 실패: {doc_id}, error: {str(e)}")
            raise

    async def upload_documents(
        self,
        project_id: UUID,
        user_id: UUID,
        files: List[UploadFile],
        background_tasks: BackgroundTasks
    ) -> List[Document]:
        """문서 업로드 및 처리
        
        Args:
            project_id: 프로젝트 ID
            user_id: 사용자 ID
            files: 업로드할 파일 목록
            background_tasks: 백그라운드 태스크
            
        Returns:
            생성된 Document 객체 목록
        """
        if not files:
            raise HTTPException(status_code=400, detail="No files provided")
            
        # 1. 프로젝트 검증 - user_id로 접근 권한 확인
        project = await self._validate_project(project_id, user_id)
        if not project:
            raise HTTPException(status_code=403, detail="Invalid project access")
            
        failed_files = []
        documents = []
        
        for file in files:
            try:
                logger.info(f"Processing file: {file.filename}")
                
                # 4. 파일 타입 검증
                if not self._is_allowed_file(file.content_type):
                    error_msg = f"Unsupported file type: {file.content_type}"
                    logger.warning(error_msg)
                    failed_files.append({
                        "filename": file.filename,
                        "error": error_msg
                    })
                    continue
                
                # 5. 파일 크기 검증
                if file.size > 100 * 1024 * 1024:  # 100MB 제한
                    error_msg = f"File too large: {file.filename}"
                    logger.warning(error_msg)
                    failed_files.append({
                        "filename": file.filename,
                        "error": error_msg
                    })
                    continue
                
                # 6. 파일명 검증
                if not self._is_valid_filename(file.filename):
                    error_msg = f"Invalid filename: {file.filename}"
                    logger.warning(error_msg)
                    failed_files.append({
                        "filename": file.filename,
                        "error": error_msg
                    })
                    continue
                
                try:
                    # 7. 파일 내용 읽기 및 검증
                    content = await file.read()
                    if not content:
                        raise ValueError("Empty file")
                    
                    file_size = len(content)
                    logger.info(f"File size: {file_size} bytes")
                    
                    # 8. 저장 경로 생성 및 검증
                    doc_id = uuid4()
                    file_path = f"{project_id}/{doc_id}/{file.filename}"
                    
                    # 9. 파일 저장
                    await self.storage.upload_file(file_path, content)
                    
                    # 10. 텍스트 추출
                    try:
                        extracted_text = self.extractor.extract_text(content, file.content_type)
                    except Exception as e:
                        logger.error(f"Text extraction error: {str(e)}")
                        extracted_text = None
                    
                    # 11. Document 객체 생성 및 검증
                    document = Document(
                        id=doc_id,
                        project_id=project_id,
                        filename=file.filename,
                        file_path=file_path,
                        file_type=file.content_type,
                        file_size=file_size,
                        status=DOCUMENT_STATUS_UPLOADED,
                        extracted_text=extracted_text
                    )
                    
                    # 12. DB 저장
                    self.db.add(document)
                    await self.db.commit()
                    await self.db.refresh(document)
                    
                    # 13. Redis에 문서 상태 저장
                    redis_client.set_document_status(
                        str(doc_id),
                        DOCUMENT_STATUS_UPLOADED,
                        None
                    )
                    
                    documents.append(document)
                    
                    # 14. 비동기 처리 태스크 등록
                    background_tasks.add_task(self.process_document_async, doc_id)
                    
                except Exception as e:
                    logger.error(f"File processing error: {str(e)}")
                    await self.db.rollback()
                    failed_files.append({
                        "filename": file.filename,
                        "error": str(e)
                    })
                    
            except Exception as e:
                logger.error(f"Unexpected error: {str(e)}")
                failed_files.append({
                    "filename": file.filename,
                    "error": "Internal server error"
                })
                
        if failed_files:
            raise HTTPException(
                status_code=400,
                detail={
                    "message": "Some files failed to upload",
                    "failed_files": failed_files,
                    "successful_files": [doc.filename for doc in documents]
                }
            )
            
        return documents

    async def _validate_project(self, project_id: UUID, user_id: UUID) -> Project:
        """프로젝트 접근 권한 검증"""
        project = await self.db.execute(
            select(Project).where(
                Project.id == project_id,
                Project.user_id == user_id
            )
        )
        return project.scalar_one_or_none()
        
    def _is_valid_filename(self, filename: str) -> bool:
        """파일명 유효성 검증"""
        if not filename:
            return False
            
        # 파일명 길이 제한
        if len(filename) > 255:
            return False
            
        # 허용되지 않는 문자 검사
        pattern = r'^[가-힣a-zA-Z0-9][가-힣a-zA-Z0-9\s\-_\.]*[가-힣a-zA-Z0-9]$'
        return bool(re.match(pattern, filename))

    async def get_document(self, document_id: UUID) -> Optional[Document]:
        """문서 상세 정보 조회"""
        try:
            result = await self.db.execute(
                select(Document).where(Document.id == document_id)
            )
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error getting document: {str(e)}")
            return None

    def get_document_status(self, document_id: UUID) -> Optional[dict]:
        """문서 상태 조회"""
        try:
            status_key = redis_client._make_key(
                redis_client.DOCUMENT_STATUS_PREFIX,
                str(document_id)
            )
            status_data = redis_client.get_key(status_key)
            if status_data:
                return json.loads(status_data)
            return None
        except Exception as e:
            logger.error(f"Error getting document status: {str(e)}")
            return None

    async def delete_document(self, document_id: UUID) -> bool:
        """문서 삭제"""
        try:
            # 1. 문서 조회
            document = await self.get_document(document_id)
            if not document:
                return False
                
            # 2. 스토리지에서 파일 삭제
            await self.storage.delete_file(document.file_path)
            
            # 3. Redis에서 상태 삭제
            status_key = redis_client._make_key(
                redis_client.DOCUMENT_STATUS_PREFIX,
                str(document_id)
            )
            redis_client.delete_key(status_key)
            
            # 4. DB에서 문서 삭제
            await self.db.delete(document)
            await self.db.commit()
            
            return True
        except Exception as e:
            logger.error(f"Error deleting document: {str(e)}")
            await self.db.rollback()
            return False

    async def process_document(self, document_id: str) -> None:
        """문서 처리 메인 로직"""
        try:
            logger.info(f"문서 처리 태스크 시작됨: {document_id}")
            
            # 1. 문서 상태를 PROCESSING으로 업데이트
            await self._update_document_status(document_id, "PROCESSING")
            
            # 2. 문서 정보 조회
            document = await self._get_document(document_id)
            if not document:
                logger.error(f"문서를 찾을 수 없음: {document_id}")
                return
                
            # 3. 텍스트 추출
            extracted_text = await self._extract_text(document)
            if not extracted_text:
                logger.error(f"텍스트 추출 실패: {document_id}")
                await self._update_document_status(document_id, "ERROR", "텍스트 추출 실패")
                return
                
            # 4. 청크 생성 및 임베딩 처리
            chunk_ids = await self._process_chunks(document_id, extracted_text)
            if not chunk_ids:
                logger.error(f"청크 처리 실패: {document_id}")
                await self._update_document_status(document_id, "ERROR", "청크 처리 실패")
                return
                
            # 5. 문서 상태 업데이트 (임베딩 ID 포함)
            await self._update_document_status(
                document_id,
                "COMPLETED",
                embedding_ids=chunk_ids
            )
            
            logger.info(f"문서 처리 완료: {document_id}")
            
        except Exception as e:
            logger.error(f"문서 처리 중 오류 발생: {str(e)}")
            await self._update_document_status(document_id, "ERROR", str(e))

    async def _update_document_status(self, document_id: str, status: str, error_msg: str = None, embedding_ids: list = None) -> None:
        """문서 상태 업데이트"""
        try:
            # Redis에 문서 상태 저장
            redis_client.set_document_status(
                document_id,
                status,
                error_msg,
                embedding_ids
            )
            
            # DB에 문서 상태 저장
            document = await self.get_document(UUID(document_id))
            if document:
                document.status = status
                if error_msg:
                    document.error_msg = error_msg
                if embedding_ids:
                    document.embedding_ids = embedding_ids
                await self.db.commit()
                await self.db.refresh(document)
                
        except Exception as e:
            logger.error(f"Error updating document status: {str(e)}")

    async def _get_document(self, document_id: str) -> Optional[Document]:
        """문서 정보 조회"""
        try:
            result = await self.db.execute(
                select(Document).where(Document.id == UUID(document_id))
            )
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error getting document: {str(e)}")
            return None

    async def _extract_text(self, document: Document) -> Optional[str]:
        """텍스트 추출"""
        try:
            # 추출 로직 구현
            return "추출된 텍스트"
        except Exception as e:
            logger.error(f"Error extracting text: {str(e)}")
            return None

    async def _process_chunks(self, document_id: str, extracted_text: str) -> Optional[list]:
        """청크 생성 및 임베딩 처리"""
        try:
            # 청크 생성 및 임베딩 로직 구현
            return ["임베딩 ID 1", "임베딩 ID 2"]
        except Exception as e:
            logger.error(f"Error processing chunks: {str(e)}")
            return None

    async def get_documents_by_project(self, project_id: str) -> List[Document]:
        """프로젝트에 속한 모든 문서를 조회합니다."""
        try:
            logger.info(f"프로젝트 {project_id}의 문서 조회 시작")
            async with self.db as session:
                query = select(Document).where(Document.project_id == project_id)
                result = await session.execute(query)
                documents = result.scalars().all()
                logger.info(f"조회된 문서 수: {len(list(documents))}")
                return documents
        except Exception as e:
            logger.error(f"문서 조회 중 오류 발생: {str(e)}")
            raise
