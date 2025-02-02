"""RAG 검색 기능 테스트"""

import pytest
from httpx import AsyncClient
from typing import AsyncGenerator

from app.main import app

@pytest.mark.asyncio
async def test_rag_table_search(test_client: AsyncGenerator[AsyncClient, None]):
    """RAG 테이블 모드 검색 테스트"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        # 테스트 쿼리
        query = "피고와 원고의 주장을 정리해주세요"
        response = await client.post(
            "/api/v1/rag/table/search",
            json={
                "query": query,
                "mode": "table",
                "document_ids": ["doc1", "doc2"]  # 테스트용 문서 ID
            }
        )
        
        assert response.status_code == 200
        result = response.json()
        
        # 응답 내용 출력
        print("\n=== Table Mode Response ===")
        print(f"Query: {query}")
        
        for column in result["columns"]:
            print(f"\nHeader: {column['header']['name']}")
            print(f"Prompt: {column['header']['prompt']}")
            print("\nContents:")
            for cell in column["cells"]:
                print(f"\nDocument ID: {cell['doc_id']}")
                print(f"Content: {cell['content']}")
        
        # 응답 구조 검증
        assert "columns" in result
        assert isinstance(result["columns"], list)
        assert len(result["columns"]) > 0
        
        # 각 컬럼 검증
        for column in result["columns"]:
            # 헤더 검증
            assert "header" in column
            assert "name" in column["header"]
            assert "prompt" in column["header"]
            assert isinstance(column["header"]["name"], str)
            assert isinstance(column["header"]["prompt"], str)
            
            # 셀 검증
            assert "cells" in column
            assert isinstance(column["cells"], list)
            assert len(column["cells"]) == 2  # doc1, doc2
            
            for cell in column["cells"]:
                assert "doc_id" in cell
                assert "content" in cell
                assert isinstance(cell["content"], str)
                assert len(cell["content"]) > 0

@pytest.fixture
async def test_client() -> AsyncGenerator[AsyncClient, None]:
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client

if __name__ == '__main__':
    pytest.main([__file__, "-v"])
