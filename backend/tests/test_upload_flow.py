"""문서 업로드 플로우 테스트"""

import sys
from pathlib import Path
import pytest
from uuid import UUID
import asyncio
from typing import AsyncGenerator, List, Set
from httpx import AsyncClient
from app.main import app
from app.models.document import DocumentStatus
from app.services.embedding import EmbeddingService
import logging

logger = logging.getLogger(__name__)

def prepare_test_file():
    """테스트 파일 준비"""
    test_file_path = Path("C:/Users/itsre/CascadeProjects/intellio/backend_new/test_files/판례_2018다212610.pdf")
    if not test_file_path.exists():
        raise FileNotFoundError(f"Test PDF file not found at {test_file_path}")
    return test_file_path.read_bytes()

def clear_embeddings():
    """테스트 전 임베딩 인덱스 초기화"""
    embedding_service = EmbeddingService()
    embedding_service.clear_index()
    logger.info("임베딩 인덱스 초기화 완료")

async def create_test_project(client: AsyncClient):
    """테스트용 프로젝트 생성"""
    project_data = {
        "name": "Test Project",
        "description": "Test project for document upload",
        "is_temporary": True,
        "retention_period": "FIVE_DAYS"
    }
    response = await client.post('/api/v1/projects/', json=project_data)
    assert response.status_code == 200
    return response.json()['id']

async def monitor_document_status(client: AsyncClient, document_id: str) -> Set[str]:
    """문서 처리 상태 모니터링"""
    max_retries = 120
    retry_delay = 2
    expected_states = ["REGISTERED", "UPLOADING", "PROCESSING", "COMPLETED"]
    seen_states = set()

    for _ in range(max_retries):
        response = await client.get(f'/api/v1/documents/{document_id}')
        assert response.status_code == 200
        doc_data = response.json()
        current_status = doc_data["status"]
        
        seen_states.add(current_status)
        if current_status == "COMPLETED":
            break
        if current_status == "ERROR":
            logger.error(f"Document processing error: {doc_data['error_message']}")
            break
            
        await asyncio.sleep(retry_delay)
    
    return seen_states

async def verify_embeddings(client: AsyncClient, document_id: str) -> dict:
    """임베딩 생성 확인"""
    max_retries = 10
    retry_delay = 1

    for _ in range(max_retries):
        response = await client.get(f'/api/v1/documents/{document_id}')
        assert response.status_code == 200
        doc_data = response.json()
        
        if doc_data["status"] in ["COMPLETED", "PARTIAL"]:
            return doc_data
            
        await asyncio.sleep(retry_delay)
    
    return doc_data

async def cleanup_test_data(client: AsyncClient, project_id: UUID, document_ids: List[str]):
    """테스트 데이터 정리"""
    # 문서 삭제
    for doc_id in document_ids:
        try:
            await client.delete(f'/api/v1/documents/{doc_id}')
        except Exception as e:
            logger.warning(f"Failed to delete document {doc_id}: {e}")
    
    # 프로젝트 삭제
    try:
        await client.delete(f'/api/v1/projects/{project_id}')
    except Exception as e:
        logger.warning(f"Failed to delete project {project_id}: {e}")

async def test_similarity_search(client: AsyncClient, document_id: str) -> None:
    """유사도 검색 테스트"""
    # 문서 처리 완료 대기
    max_retries = 30
    retry_delay = 2
    
    for _ in range(max_retries):
        response = await client.get(f'/api/v1/documents/{document_id}')
        assert response.status_code == 200
        doc_data = response.json()
        
        if doc_data["status"] == "COMPLETED":
            # 유사도 검색 테스트
            search_data = {
                "query": "법원의 판결",
                "top_k": 5
            }
            response = await client.post('/api/v1/documents/search', json=search_data)
            assert response.status_code == 200
            search_results = response.json()
            
            # 검색 결과 검증
            assert isinstance(search_results, list)
            assert len(search_results) > 0
            break
            
        if doc_data["status"] == "ERROR":
            raise Exception(f"Document processing failed: {doc_data['error_message']}")
            
        await asyncio.sleep(retry_delay)
    
    assert doc_data["status"] == "COMPLETED", "Document processing did not complete in time"

@pytest.mark.asyncio
async def test_document_upload_flow(test_client: AsyncGenerator[AsyncClient, None]):
    """문서 업로드 전체 플로우 테스트"""
    # 테스트 전 임베딩 초기화
    clear_embeddings()
    
    client = await anext(test_client)
    project_id = None
    document_ids = []
    
    try:
        # 1. 프로젝트 생성
        project_id = await create_test_project(client)
        
        # 2. 문서 업로드 및 처리
        test_file = prepare_test_file()
        files = {"files": ("test.pdf", test_file, "application/pdf")}
        response = await client.post(
            f'/api/v1/documents/projects/{project_id}/upload',
            files=files
        )
        
        assert response.status_code == 200
        response_data = response.json()
        document_id = response_data["document_ids"][0]
        document_ids.append(document_id)
        
        # 3. 문서 처리 상태 모니터링
        seen_states = await monitor_document_status(client, document_id)
        assert "COMPLETED" in seen_states
        
        # 4. 임베딩 생성 확인
        doc_data = await verify_embeddings(client, document_id)
        assert doc_data["status"] in ["COMPLETED", "PARTIAL"]
        
        if doc_data["status"] == "COMPLETED":
            # 임베딩 ID 검증
            assert "embedding_ids" in doc_data
            assert len(doc_data["embedding_ids"]) > 0
            assert all(isinstance(id, str) for id in doc_data["embedding_ids"])
            assert all(id.startswith(f"{document_id}_chunk_") for id in doc_data["embedding_ids"])
            
            # 5. 유사도 검색 테스트 (문서 처리가 완료된 후에만)
            await test_similarity_search(client, document_id)
            
            # 테스트에 사용할 document_id 출력
            print(f"\nTest document ID for RAG: {document_id}\n")
        
    finally:
        # 테스트 데이터 정리 (주석 처리)
        # await cleanup_test_data(client, project_id, document_ids)
        pass

@pytest.fixture
async def test_client() -> AsyncGenerator[AsyncClient, None]:
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client

if __name__ == '__main__':
    pytest.main([__file__, "-v"])
