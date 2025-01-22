from typing import List
from uuid import UUID
from celery import group, chain, Task, shared_task
from sqlalchemy.orm import Session
from sqlalchemy import select
from datetime import datetime
import logging
import asyncio
import json
from uuid import UUID
from typing import List, Optional
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, Form, BackgroundTasks, Cookie
from sqlalchemy.ext.asyncio import AsyncSession
import logging
from app.api import deps

from app.core.celery_app import celery
from app.core.database import SessionLocal, get_async_session, AsyncSessionLocal
from app.core.redis import redis_client
from app.models.document import Document
from app.services.storage import StorageService
from app.services.extractor import DocumentExtractor
#from backend_new.app.services.chunker_blocked import RAGOptimizedChunker
from app.services.embedding import EmbeddingService
from app.services.document import DocumentService
from tenacity import retry, stop_after_attempt, wait_exponential

from celery import shared_task, group
from app.core.celery_app import celery

logger = logging.getLogger(__name__)

# 문서 상태 상수
DOCUMENT_STATUS_REGISTERED = 'REGISTERED'
DOCUMENT_STATUS_UPLOADING = 'UPLOADING'
DOCUMENT_STATUS_UPLOADED = 'UPLOADED'
DOCUMENT_STATUS_PROCESSING = 'PROCESSING'
DOCUMENT_STATUS_COMPLETED = 'COMPLETED'
DOCUMENT_STATUS_PARTIAL = 'PARTIAL'
DOCUMENT_STATUS_ERROR = 'ERROR'
DOCUMENT_STATUS_DELETED = 'DELETED'

async def update_document_status_async(session, document_id: str, doc_status: str, metadata: dict = None, error: str = None):
    """Update document status in both database and Redis asynchronously"""
    try:
        # Update database
        doc = await session.get(Document, UUID(document_id))
        if doc:
            doc.status = doc_status
            if error:
                doc.error_message = error
            doc.updated_at = datetime.utcnow()
            await session.commit()

        # Update Redis
        status_data = {
            'status': doc_status,
            'updated_at': datetime.utcnow().isoformat()
        }
        if metadata:
            status_data['metadata'] = metadata
        if error:
            status_data['error_message'] = error
            
        key = f"doc_status:{document_id}"
        redis_client.set_key(key, status_data)
            
    except Exception as e:
        logger.error(f"Error updating document status: {str(e)}")
        raise

def update_document_status(document_id: str, doc_status: str, metadata: dict = None, error: str = None):
    """문서 상태 업데이트 (동기식)"""
    try:
        # DB 업데이트
        with SessionLocal() as db:
            doc = db.query(Document).filter(Document.id == UUID(document_id)).first()
            if doc:
                doc.status = doc_status
                if error:
                    doc.error_message = error
                doc.updated_at = datetime.utcnow()
                db.commit()

        # Redis 업데이트
        status_data = {
            'status': doc_status,
            'updated_at': datetime.utcnow().isoformat()
        }
        if metadata:
            status_data['metadata'] = metadata
        if error:
            status_data['error_message'] = error
            
        key = f"doc_status:{document_id}"
        redis_client.set_key(key, status_data)
            
    except Exception as e:
        logger.error(f"상태 업데이트 실패: {str(e)}")
        raise


@celery.task(name="create_chunk_embedding")
def create_chunk_embedding(doc_id: str, chunk_text: str, chunk_index: int):
    """단일 청크에 대한 임베딩 생성"""
    try:
        embedding_service = EmbeddingService()
        embedding = embedding_service.create_embedding(chunk_text)
        
        # 청크 ID 생성
        chunk_id = f"{doc_id}_chunk_{chunk_index}"
        
        # Pinecone에 저장
        embedding_service.index.upsert(
            vectors=[(
                chunk_id,
                embedding,
                {
                    "document_id": doc_id,
                    "chunk_index": chunk_index,
                    "text": chunk_text
                }
            )]
        )
        
        return chunk_id
    except Exception as e:
        logger.error(f"임베딩 생성 중 오류 발생: {str(e)}")
        raise
# RAGOptimizedChunker TEST
# @celery.task(name="process_document_text")
# def process_document_text(doc_id: str):
#     """문서 텍스트를 처리하고 임베딩을 생성하는 Celery 태스크"""
#     db = SessionLocal()
#     try:
#         logger.info(f"문서 처리 시작[process_document_text]: {doc_id}")
        
#         # DB에서 문서 가져오기
#         doc = db.query(Document).filter(Document.id == UUID(doc_id)).first()
#         if not doc:
#             raise ValueError(f"Document {doc_id} not found")
        
#         # 상태 업데이트: PROCESSING
#         update_document_status(
#             db=db,
#             document_id=doc_id,
#             doc_status=DOCUMENT_STATUS_PROCESSING,
#             metadata={"status": "Processing document text"}
#         )

#         # 텍스트 가져오기
#         extracted_text = doc.extracted_text
#         if not extracted_text:
#             raise ValueError(f"No extracted text found for document {doc_id}")

#         # 임베딩 생성 로직 직접 처리
#         process_document_text_direct(db, doc_id, extracted_text)
        
#         logger.info(f"문서 처리 완료: {doc_id}")
#         return True
            
#     except Exception as e:
#         logger.error(f"문서 처리 중 오류 발생: {doc_id}, error: {str(e)}")
#         update_document_status(
#             db=db,
#             document_id=doc_id,
#             doc_status=DOCUMENT_STATUS_ERROR,
#             error=str(e)
#         )
#         raise
#     finally:
#         db.close()
# RAGOptimizedChunker TEST
# async def process_document_text_direct(db: Session, doc_id: str, text: str):
#     """문서 텍스트 처리 및 임베딩 생성"""
#     try:
#         # 청크 생성
#         chunker = RAGOptimizedChunker()
#         chunks = chunker.create_chunks(text)
        
#         if not chunks:
#             raise ValueError(f"Failed to create chunks for document {doc_id}")

#         logger.info(f"문서 {doc_id}의 청크 생성 완료: {len(chunks)}개")

#         # 임베딩 생성 및 저장
#         async_session = get_async_session()
#         async with async_session() as session:
#             embedding_service = EmbeddingService()
#             chunk_ids = []
#             failed_chunks = []
            
#             for i, chunk_text in enumerate(chunks):
#                 try:
#                     # 청크 텍스트가 딕셔너리인 경우 처리
#                     if isinstance(chunk_text, dict):
#                         chunk_content = chunk_text.get('text', '')
#                     else:
#                         chunk_content = chunk_text

#                     if not chunk_content:
#                         logger.warning(f"빈 청크 발견 - 문서: {doc_id}, 청크: {i}")
#                         failed_chunks.append(i)
#                         continue

#                     # 중간 상태 업데이트
#                     await update_document_status_async(
#                         session,
#                         document_id=doc_id,
#                         doc_status=DOCUMENT_STATUS_PROCESSING,
#                         metadata={"progress": f"Processing chunk {i+1}/{len(chunks)}"}
#                     )
                    
#                     logger.info(f"청크 {i+1} 처리 시작 - 길이: {len(chunk_content)}")
                    
#                     # 임베딩 생성
#                     embedding = await embedding_service.create_embedding_with_retry(chunk_content)
                    
#                     if embedding and len(embedding) > 0:
#                         chunk_id = f"{doc_id}_chunk_{i}"
#                         # Pinecone에 저장
#                         embedding_service.index.upsert(
#                             vectors=[(
#                                 chunk_id,
#                                 embedding,
#                                 {
#                                     "document_id": doc_id,
#                                     "chunk_index": i,
#                                     "text": chunk_content
#                                 }
#                             )]
#                         )
#                         chunk_ids.append(chunk_id)
#                         logger.info(f"청크 {i+1} 임베딩 생성 및 저장 완료")
#                     else:
#                         failed_chunks.append(i)
#                         logger.warning(f"임베딩 생성 실패 - 문서: {doc_id}, 청크: {i}, 임베딩이 비어있음")
                    
#                 except Exception as chunk_error:
#                     failed_chunks.append(i)
#                     logger.error(f"청크 처리 실패 - 문서: {doc_id}, 청크: {i}, 오류: {str(chunk_error)}")
#                     continue
            
#             if not chunk_ids:
#                 raise ValueError(f"모든 청크의 임베딩 생성이 실패했습니다: {doc_id}")
            
#             # 최종 상태 업데이트
#             final_status = DOCUMENT_STATUS_COMPLETED if not failed_chunks else DOCUMENT_STATUS_PARTIAL
#             await update_document_status_async(
#                 session,
#                 document_id=doc_id,
#                 doc_status=final_status,
#                 metadata={
#                     "chunk_ids": chunk_ids,
#                     "failed_chunks": failed_chunks,
#                     "total_chunks": len(chunks),
#                     "successful_chunks": len(chunk_ids)
#                 }
#             )
            
#             logger.info(f"문서 {doc_id} 처리 완료 - 성공: {len(chunk_ids)}, 실패: {len(failed_chunks)}")
#             return chunk_ids
        
#     except Exception as e:
#         logger.error(f"문서 텍스트 처리 중 오류 발생: {doc_id}, error: {str(e)}")
#         await update_document_status_async(
#             session,
#             document_id=doc_id,
#             doc_status=DOCUMENT_STATUS_ERROR,
#             error=str(e)
#         )
#         raise

def get_document(db: Session, document_id: str) -> Document:
    """문서 조회"""
    doc = db.query(Document).filter(Document.id == UUID(document_id)).first()
    if not doc:
        raise ValueError(f"문서를 찾을 수 없습니다: {document_id}")
    return doc

def validate_document_text(doc: Document, document_id: str) -> str:
    """문서 텍스트 유효성 검사"""
    if not doc.extracted_text:
        raise ValueError(f"추출된 텍스트가 없습니다: {document_id}")
    return doc.extracted_text

# def create_chunk_tasks(document_id: str, chunks: List[str], batch_size: int = 50) -> List[str]:
#     """청크 처리 태스크 생성"""
#     chunk_tasks = []
#     for i in range(0, len(chunks), batch_size):
#         batch = chunks[i:i + batch_size]
#         task = process_chunk_batch.delay(document_id, batch, i)
#         chunk_tasks.append(task.id)
#     return chunk_tasks

@shared_task(
    bind=True,
    name="app.workers.document.process_document",
    queue="document-processing",
    max_retries=3
)
def process_document(self, document_id: str):
    """문서 처리 태스크"""
    try:
        with SessionLocal() as db:
            # 문서 가져오기
            doc = db.query(Document).filter(Document.id == UUID(document_id)).first()
            if not doc:
                raise ValueError(f"문서를 찾을 수 없습니다: {document_id}")

            # 문서 상태를 PROCESSING으로 업데이트
            update_document_status(
                document_id=document_id,
                doc_status=DOCUMENT_STATUS_PROCESSING,
                metadata={"status": "Started processing document"}
            )
            
            # 텍스트 추출이 이미 되어있는지 확인
            extracted_text = doc.extracted_text
            if not extracted_text:
                raise ValueError(f"추출된 텍스트가 없습니다: {document_id}")

            # 임베딩 생성 및 저장
            chunks = split_text(extracted_text, chunk_size=1500)
            if not chunks:
                raise ValueError(f"문서를 청크로 분할할 수 없습니다: {document_id}")

            # 청크를 배치로 나누어 처리
            batch_size = 50  # OpenAI API의 토큰 제한을 고려한 배치 크기
            total_chunks = len(chunks)
            
            logger.info(f"임베딩 생성 시작: 총 {total_chunks}개 청크")
            
            # 청크 처리 태스크 생성
            chunk_tasks = []
            for i in range(0, len(chunks), batch_size):
                batch = chunks[i:i + batch_size]
                task = process_chunk_batch.delay(document_id, batch, i)
                #task = asyncio.create_task(process_chunk_batch(document_id, batch, i))
                chunk_tasks.append(task.id)
            
            # 상태 업데이트
            update_document_status(
                document_id=document_id,
                doc_status=DOCUMENT_STATUS_PROCESSING,
                metadata={
                    "total_chunks": total_chunks,
                    "task_ids": chunk_tasks
                }
            )
            
            return {
                "status": "PROCESSING",
                "total_chunks": total_chunks,
                "task_ids": chunk_tasks
            }
            
    except Exception as e:
        logger.error(f"문서 처리 실패 ({document_id}): {str(e)}")
        update_document_status(
            document_id=document_id,
            doc_status=DOCUMENT_STATUS_ERROR,
            error=str(e)
        )
        if self.request.retries < self.max_retries:
            raise self.retry(exc=e)
        raise

@celery.task(bind=True, max_retries=3, default_retry_delay=60)
def process_document_task(self, document_id: str):
    """문서 처리 및 임베딩 생성 태스크"""
    async def async_process():
        try:
            logger.info(f"Starting document processing for {document_id}")
            
            # Redis에서 처리 상태 확인
            key = f"doc_processing:{document_id}"
            if redis_client.get_key(key):
                logger.info(f"문서 {document_id}는 이미 처리 중입니다.")
                return {"status": "ALREADY_PROCESSING"}
                
            # 처리 시작 표시
            redis_client.set_key(key, "1", ex=3600)  # 1시간 후 만료
            
            # 문서 상태를 PROCESSING으로 업데이트
            await update_document_status_async(None, document_id, DOCUMENT_STATUS_PROCESSING)
            
            document_service = DocumentService(deps.get_async_db())
            # 문서 처리
            document = document_service.get_document(document_id)
            if not document:
                raise ValueError(f"Document {document_id} not found")
                
            # 텍스트 추출 및 청크 생성
            chunks = document_service.process_document_text(document)
            if not chunks:
                raise ValueError(f"No text chunks extracted from document {document_id}")
                
            logger.info(f"Created {len(chunks)} chunks for document {document_id}")
            
            # 임베딩 생성 및 저장
            async with AsyncSessionLocal() as session:
                embedding_service = EmbeddingService()
                chunk_ids = []
                failed_chunks = []
                
                for i, chunk_text in enumerate(chunks):
                    try:
                        # 청크 텍스트가 딕셔너리인 경우 처리
                        if isinstance(chunk_text, dict):
                            chunk_content = chunk_text.get('text', '')
                        else:
                            chunk_content = chunk_text

                        if not chunk_content:
                            logger.warning(f"빈 청크 발견 - 문서: {document_id}, 청크: {i}")
                            failed_chunks.append(i)
                            continue

                        # 중간 상태 업데이트
                        await update_document_status_async(
                            session,
                            document_id=document_id,
                            doc_status=DOCUMENT_STATUS_PROCESSING,
                            metadata={"progress": f"Processing chunk {i+1}/{len(chunks)}"}
                        )
                        
                        logger.info(f"청크 {i+1} 처리 시작 - 길이: {len(chunk_content)}")
                        
                        # 임베딩 생성
                        embedding = await embedding_service.create_embedding_with_retry(chunk_content)
                        
                        if embedding and len(embedding) > 0:
                            chunk_id = f"{document_id}_chunk_{i}"
                            # Pinecone에 저장
                            await embedding_service.index.upsert_async(
                                vectors=[(
                                    chunk_id,
                                    embedding,
                                    {
                                        "document_id": document_id,
                                        "chunk_index": i,
                                        "text": chunk_content
                                    }
                                )]
                            )
                            chunk_ids.append(chunk_id)
                            logger.info(f"청크 {i+1} 임베딩 생성 및 저장 완료")
                        else:
                            failed_chunks.append(i)
                            logger.warning(f"임베딩 생성 실패 - 문서: {document_id}, 청크: {i}, 임베딩이 비어있음")
                        
                    except Exception as chunk_error:
                        failed_chunks.append(i)
                        logger.error(f"청크 처리 실패 - 문서: {document_id}, 청크: {i}, 오류: {str(chunk_error)}")
                        continue
                
                if not chunk_ids:
                    raise ValueError(f"모든 청크의 임베딩 생성이 실패했습니다: {document_id}")
                
                # 최종 상태 업데이트
                final_status = DOCUMENT_STATUS_COMPLETED if not failed_chunks else DOCUMENT_STATUS_PARTIAL
                await update_document_status_async(
                    session,
                    document_id=document_id,
                    doc_status=final_status,
                    metadata={
                        "chunk_ids": chunk_ids,
                        "failed_chunks": failed_chunks,
                        "total_chunks": len(chunks),
                        "successful_chunks": len(chunk_ids)
                    }
                )
                
                logger.info(f"문서 {document_id} 처리 완료 - 성공: {len(chunk_ids)}, 실패: {len(failed_chunks)}")
                return chunk_ids
            
        except Exception as e:
            logger.error(f"문서 처리 실패 ({document_id}): {str(e)}")
            await update_document_status_async(
                None,
                document_id=document_id,
                doc_status=DOCUMENT_STATUS_ERROR,
                error=str(e)
            )
            if self.request.retries < self.max_retries:
                raise self.retry(exc=e)
            raise
        finally:
            # 처리 완료 표시 제거
            redis_client.delete_key(key)

    # 비동기 함수 실행
    loop = asyncio.get_event_loop()
    return loop.run_until_complete(async_process())

@celery.task(bind=True, max_retries=3, acks_late=True)
def process_chunk_batch(self, document_id: str, chunks: List[str], batch_start_idx: int):
    """청크 배치 처리"""
    try:
        # Redis에서 배치 처리 상태 확인
        key = f"chunk_batch:{document_id}:{batch_start_idx}"
        if redis_client.get_key(key):
            logger.info(f"배치 {batch_start_idx}는 이미 처리 중입니다.")
            return {"status": "ALREADY_PROCESSING"}
            
        # 처리 시작 표시
        redis_client.set_key(key, "1", expire=1800)  # 30분 후 만료
        
        embedding_service = EmbeddingService()
        
        bApplyAsync = True
        #embeddings = await embedding_service.create_embeddings_batch(chunks)

        #embeddings = loop.run_until_complete(embedding_service.create_embeddings_batch(chunks))
        #embeddings = run_async(embedding_service.create_embeddings_batch(chunks))
        embeddings = embedding_service.create_embeddings_batch_sync(chunks)

        if not embeddings:
            raise ValueError("임베딩 생성 실패")
            
        # 벡터 저장용 데이터 준비
        vectors = []
        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            chunk_id = f"{document_id}_chunk_{batch_start_idx + i}"
            vectors.append({
                "id": chunk_id,
                "values": embedding,
                "metadata": {
                    "document_id": document_id,
                    "chunk_index": batch_start_idx + i,
                    "text": chunk
                }
            })
        
        # 벡터 저장 (비동기)
        # if bApplyAsync:
        #     loop.run_until_complete(embedding_service.store_vectors(vectors))
        # else:
        embedding_service.store_vectors(vectors)
            
        # 모든 청크가 처리되었는지 확인
        with SessionLocal() as db:
            doc = db.query(Document).filter(Document.id == UUID(document_id)).first()
            if doc:
                # 문서의 총 청크 수 먼저 확인 및 설정
                total_key = f"total_chunks:{document_id}"
                total_chunks = redis_client.get_key(total_key)
                if not total_chunks:
                    if doc.extracted_text:
                        all_chunks = split_text(doc.extracted_text)
                        total_chunks = len(all_chunks)
                        redis_client.set_key(total_key, str(total_chunks))
                else:
                    total_chunks = int(total_chunks)

                # Redis에서 현재까지 처리된 총 청크 수 확인 및 업데이트
                processed_key = f"processed_chunks:{document_id}"
                current_processed = redis_client.incr(processed_key, len(chunks))  # 원자적 증가

                # 생성된 청크 ID 저장
                chunk_ids = [v["id"] for v in vectors]
                try:
                    if not doc.embedding_ids:
                        doc.embedding_ids = json.dumps(chunk_ids)
                    else:
                        existing_ids = json.loads(doc.embedding_ids) if doc.embedding_ids else []
                        existing_ids.extend(chunk_ids)
                        doc.embedding_ids = json.dumps(existing_ids)
                except Exception as e:
                    logger.error(f"embedding_ids 처리 중 오류: {str(e)}")
                    doc.embedding_ids = json.dumps(chunk_ids)

                # 상태 업데이트
                if total_chunks > 0 and current_processed >= total_chunks:  # 모든 청크가 처리되었을 때
                    logger.info(f"문서 {document_id} 처리 완료: {current_processed}/{total_chunks} 청크")
                    doc.status = DOCUMENT_STATUS_COMPLETED
                    doc.updated_at = datetime.utcnow()
                    db.commit()
                    
                    update_document_status(
                        document_id,
                        DOCUMENT_STATUS_COMPLETED,
                        metadata={
                            "processed_chunks": current_processed,
                            "total_chunks": total_chunks,
                            "status": "COMPLETED",
                            "embedding_ids": doc.embedding_ids
                        }
                    )
                else:
                    logger.info(f"문서 {document_id} 처리 중: {current_processed}/{total_chunks} 청크")
                    doc.status = DOCUMENT_STATUS_PARTIAL
                    doc.updated_at = datetime.utcnow()
                    db.commit()
                    
                    update_document_status(
                        document_id,
                        DOCUMENT_STATUS_PARTIAL,
                        metadata={
                            "processed_chunks": current_processed,
                            "total_chunks": total_chunks,
                            "status": "PROCESSING",
                            "embedding_ids": doc.embedding_ids
                        }
                    )

        return {
            "status": "SUCCESS",
            "chunk_ids": [v["id"] for v in vectors],
            "batch_index": batch_start_idx,
            "processed_chunks": current_processed if 'current_processed' in locals() else 0,
            "total_chunks": total_chunks if 'total_chunks' in locals() else 0
        }
        
    except Exception as e:
        logger.error(f"청크 배치 처리 실패 (문서: {document_id}, 배치: {batch_start_idx}): {str(e)}")
        if self.request.retries < self.max_retries:
            raise self.retry(exc=e)
        raise
    finally:
        # 처리 완료 표시 제거
        redis_client.delete_key(key)
        # if bApplyAsync:
            #     loop.close()


@celery.task(
    name="process_documents_batch",
    queue="document-processing"
)
def process_documents_batch(document_ids: List[str]):
    """문서 일괄 처리"""
    try:
        logger.warn(f"일괄 처리 시작: {document_ids}")
        # 각 문서에 대해 별도의 작업 생성
        jobs = group(process_document_task.s(doc_id) for doc_id in document_ids)
        result = jobs.apply_async()
        
        logger.info(f"일괄 처리 시작: {document_ids}")
        return {
            "status": "started",
            "document_ids": document_ids,
            "task_id": result.id
        }
        
    except Exception as e:
        logger.error(f"일괄 처리 실패: {str(e)}")
        raise

def process_chunk(embedding_service, chunk: str, chunk_index: int, document_id: str) -> Optional[str]:
    """단일 청크 처리 함수"""
    try:
        # 임베딩 생성
        embedding = embedding_service.create_embedding_with_retry(chunk)
        
        if embedding and len(embedding) > 0:
            chunk_id = f"{document_id}_chunk_{chunk_index}"
            # Pinecone에 저장
            embedding_service.index.upsert(
                vectors=[(
                    chunk_id,
                    embedding,
                    {
                        "document_id": document_id,
                        "chunk_index": chunk_index,
                        "text": chunk
                    }
                )]
            )
            return chunk_id
    except Exception as e:
        raise e
    
    return None

def split_text(text: str, chunk_size: int = 1500):
    """텍스트를 일정 크기의 청크로 분할합니다.
    
    Args:
        text (str): 분할할 텍스트
        chunk_size (int, optional): 각 청크의 최대 크기. Defaults to 1500.
    
    Returns:
        List[str]: 분할된 텍스트 청크 리스트
    """
    if not text:
        return []
        
    # 문장 단위로 분할
    sentences = text.split('\n')
    chunks = []
    current_chunk = []
    current_size = 0
    
    for sentence in sentences:
        # 빈 문장은 건너뜀
        if not sentence.strip():
            continue
            
        sentence_size = len(sentence)
        
        # 현재 청크가 비어있고 문장이 chunk_size보다 큰 경우
        if not current_chunk and sentence_size > chunk_size:
            # 문장을 강제로 분할
            for i in range(0, len(sentence), chunk_size):
                chunks.append(sentence[i:i + chunk_size])
            continue
            
        # 현재 청크에 문장을 추가할 수 있는 경우
        if current_size + sentence_size <= chunk_size:
            current_chunk.append(sentence)
            current_size += sentence_size
        else:
            # 현재 청크를 저장하고 새로운 청크 시작
            if current_chunk:
                chunks.append('\n'.join(current_chunk))
            current_chunk = [sentence]
            current_size = sentence_size
    
    # 마지막 청크 처리
    if current_chunk:
        chunks.append('\n'.join(current_chunk))
    
    return chunks
