from typing import List
from uuid import UUID
from celery import group, shared_task

from sqlalchemy.orm import Session
from datetime import datetime
import asyncio
import json
from uuid import UUID
from typing import List, Optional

from common.models.token_usage import ProjectType, TokenType
from common.app import LoadEnvGlobal
from common.core.database import SessionLocal, get_db_async, AsyncSessionLocal
from common.core.redis import RedisClient
from common.services.embedding import EmbeddingService
from common.services.textsplitter import TextSplitter
from common.services.vector_store_manager import VectorStoreManager

from doceasy.core.celery_app import celery
from doceasy.models.document import Document, DocumentChunk
from doceasy.services.document import DocumentService
from common.core.config import settings

from celery.signals import worker_ready
import os
from loguru import logger
from doceasy.services.document import DocumentDatabaseManager

# 문서 상태 상수
DOCUMENT_STATUS_REGISTERED = 'REGISTERED'
DOCUMENT_STATUS_UPLOADING = 'UPLOADING'
DOCUMENT_STATUS_UPLOADED = 'UPLOADED'
DOCUMENT_STATUS_PROCESSING = 'PROCESSING'
DOCUMENT_STATUS_COMPLETED = 'COMPLETED'
DOCUMENT_STATUS_PARTIAL = 'PARTIAL'
DOCUMENT_STATUS_ERROR = 'ERROR'
DOCUMENT_STATUS_DELETED = 'DELETED'

@worker_ready.connect
def init_worker(sender=None, **kwargs):
    """Document worker 초기화 시 실행되는 함수"""
    try:
        LoadEnvGlobal()
        logger.info(f"Document Worker 초기화 [ProcessID: {os.getpid()}]")
        global redis_client_for_document
        redis_client_for_document = RedisClient()

        # 토큰 사용량 추적 초기화
        try:
            from common.services.embedding_models import TokenUsageQueue
            from common.core.deps import get_db
            
            # 세션 팩토리 함수 (비동기)
            async def session_factory():
                async for db in get_db():
                    yield db
            
            # 토큰 사용량 큐 초기화 - 비동기 함수이므로 실행 불가
            # 대신 동기적 토큰 사용량 추적 방식을 사용함
            logger.info("Celery 워커에서는 비동기 토큰 사용량 큐 대신 동기적 토큰 추적을 사용합니다")
        except Exception as e:
            logger.error(f"토큰 사용량 추적 초기화 중 오류: {str(e)}")

    except Exception as e:
        logger.error(f"Worker 초기화 중 오류 발생: {str(e)}")
        raise


async def update_document_status_async(session, document_id: str, doc_status: str, metadata: dict = None, error: str = None):
    """Update document status in both database and Redis asynchronously"""
    try:
        # Update database
        doc = await session.get(Document, UUID(document_id))
        if doc:
            doc.status = doc_status
            if error:
                doc.error_message = error
            doc.updated_at = datetime.now()
            await session.commit()

        # Update Redis
        status_data = {
            'status': doc_status,
            'updated_at': datetime.now().isoformat()
        }
        if metadata:
            status_data['metadata'] = metadata
        if error:
            status_data['error_message'] = error
            
        key = f"doc_status:{document_id}"
        redis_client_for_document.set_key(key, status_data)
            
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
                doc.updated_at = datetime.now()
                db.commit()

        # Redis 업데이트
        status_data = {
            'status': doc_status,
            'updated_at': datetime.now().isoformat()
        }
        if metadata:
            status_data['metadata'] = metadata
        if error:
            status_data['error_message'] = error
            
        key = f"doc_status:{document_id}"
        redis_client_for_document.set_key(key, status_data)
            
    except Exception as e:
        logger.error(f"상태 업데이트 실패: {str(e)}")
        raise


@celery.task(name="create_chunk_embedding")
def create_chunk_embedding(doc_id: str, chunk_text: str, chunk_index: int):
    """단일 청크에 대한 임베딩 생성"""
    try:
        embedding_service = EmbeddingService()
        #embedding = embedding_service.create_embedding(chunk_text)
        embedding = embedding_service.create_single_embedding(chunk_text)
        
        # 청크 ID 생성
        chunk_id = f"{doc_id}_chunk_{chunk_index}"
        
        # Pinecone에 저장
        embedding_service.pinecone_index.upsert(
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
    name="doceasy.workers.document.process_document_chucking",
    queue="document-processing",
    max_retries=3
)
def process_document_chucking(self, document_id: str, user_id: str = None):
    """업로드 후 문서 처리 작업
        1. 텍스트 추출
        2. 청킹
        3. 임베딩(make_embedding_data_batch, 배치 처리)
    """
    try:
        logger.info(f"문서 처리 작업 시작: document_id={document_id}, user_id={user_id}")
        with SessionLocal() as db:
            # DB 매니저 초기화
            db_manager = DocumentDatabaseManager(db)
            
            # 문서 가져오기
            doc = db_manager.get_document(UUID(document_id))
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

            # 청크 생성
            text_splitter = TextSplitter() 
            chunks = text_splitter.split_text(extracted_text)

            # 청크를 PostgreSQL에 저장
            #logger.info(f"청크 삭제 시작: {document_id}")
            db_manager.delete_document_chunks(UUID(document_id))
            
            db_manager.create_document_chunks(UUID(document_id), chunks, doc.filename)
            logger.info(f"청크 DB 저장[{len(chunks)}개]: {document_id}")

            # 청크를 배치로 나누어 처리
            batch_size = 50  # OpenAI API의 토큰 제한을 고려한 배치 크기
            total_chunks = len(chunks)
            
            logger.info(f"임베딩 생성 시작: 총 {total_chunks}개 청크")
            
            # 청크로 임베딩 데이터 생성 태스크
            chunk_tasks = []
            for i in range(0, len(chunks), batch_size):
                batch = chunks[i:i + batch_size]
                # user_id가 None이 아닌 경우에만 전달
                if user_id is not None:
                    task = make_embedding_data_batch.delay(document_id, batch, i, user_id)
                else:
                    task = make_embedding_data_batch.delay(document_id, batch, i)
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
        logger.error(f"문서 처리 실패 ({document_id}): {str(e)}", exc_info=True)
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
            if redis_client_for_document.get_key(key):
                logger.info(f"문서 {document_id}는 이미 처리 중입니다.")
                return {"status": "ALREADY_PROCESSING"}
                
            # 처리 시작 표시
            redis_client_for_document.set_key(key, "1", ex=3600)  # 1시간 후 만료
            
            # 문서 상태를 PROCESSING으로 업데이트
            await update_document_status_async(None, document_id, DOCUMENT_STATUS_PROCESSING)
            
            document_service = DocumentService(get_db_async())
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
                        embedding = await embedding_service.create_embeddings_batch([chunk_content])
                        # 빈 배열 체크
                        if not embedding or len(embedding) == 0:
                            failed_chunks.append(i)
                            logger.warning(f"임베딩 생성 실패 - 문서: {document_id}, 청크: {i}, 임베딩이 비어있음")
                            continue
                        embedding = embedding[0]
                        
                        if embedding and len(embedding) > 0:
                            chunk_id = f"{document_id}_chunk_{i}"
                            # Pinecone에 저장
                            await embedding_service.pinecone_index.upsert_async(
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
            redis_client_for_document.delete_key(key)

    # 비동기 함수 실행
    loop = asyncio.get_event_loop()
    return loop.run_until_complete(async_process())

@celery.task(bind=True, max_retries=3, acks_late=True)
def make_embedding_data_batch(self, document_id: str, chunks: List[str], batch_start_idx: int, user_id: str = None):
    """
    문서의 청크들을 임베딩하고 벡터 스토어에 저장하는 배치 작업
    Args:
        document_id: 문서 ID
        chunks: 청크 텍스트 리스트
        batch_start_idx: 배치 시작 인덱스
        user_id: 사용자 ID
    """
    try:
        logger.info(f"청크 배치 처리 시작: document_id={document_id}, batch_start_idx={batch_start_idx}, user_id={user_id}")
        # Redis에서 배치 처리 상태 확인
        key = f"chunk_batch:{document_id}:{batch_start_idx}"
        if redis_client_for_document.get_key(key):
            logger.info(f"배치 {batch_start_idx}는 이미 처리 중입니다.")
            return {"status": "ALREADY_PROCESSING"}
            
        # 처리 시작 표시
        redis_client_for_document.set_key(key, "1", expire=1800)  # 30분 후 만료
        embedding_service = EmbeddingService()
        
        # 임포트
        from common.services.token_usage_service import track_token_usage_sync
        from common.core.database import SessionLocal
        
        # 먼저 모든 청크의 임베딩을 생성
        embeddings = embedding_service.create_embeddings_batch_sync(
            texts=chunks, 
            user_id=UUID(user_id) if user_id else None, 
            project_type=ProjectType.DOCEASY
        )

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
        
       
        
        # 벡터 저장 (동기)
        vs_manager = VectorStoreManager(embedding_model_type=embedding_service.get_model_type(), 
                                        project_name="doceasy",
                                        namespace=settings.PINECONE_NAMESPACE_DOCEASY)
        vs_manager.store_vectors(vectors)
            
        # 모든 청크가 처리되었는지 확인
        with SessionLocal() as db:
            doc = db.query(Document).filter(Document.id == UUID(document_id)).first()
            if doc:
                # 문서의 총 청크 수 먼저 확인 및 설정
                total_key = f"total_chunks:{document_id}"
                total_chunks = redis_client_for_document.get_key(total_key)
                if not total_chunks:
                    if doc.extracted_text:
                        all_chunks = split_text(doc.extracted_text)
                        total_chunks = len(all_chunks)
                        redis_client_for_document.set_key(total_key, str(total_chunks))
                else:
                    total_chunks = int(total_chunks)

                # Redis에서 현재까지 처리된 총 청크 수 확인 및 업데이트
                processed_key = f"processed_chunks:{document_id}"
                current_processed = redis_client_for_document.incr(processed_key, len(chunks))  # 원자적 증가

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
                    doc.updated_at = datetime.now()
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
                    doc.updated_at = datetime.now()
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
        logger.exception(f"청크 배치 처리 실패 (문서: {document_id}, 배치: {batch_start_idx}): {str(e)}")
        if self.request.retries < self.max_retries:
            raise self.retry(exc=e)
        raise
    finally:
        # 처리 완료 표시 제거
        redis_client_for_document.delete_key(key)
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
