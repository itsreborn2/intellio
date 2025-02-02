import asyncio
import httpx
import json
from datetime import datetime
from uuid import UUID

BASE_URL = "http://localhost:8000/api/v1"

async def test_project_lifecycle():
    async with httpx.AsyncClient() as client:
        # 1. 영구 보관용 카테고리 생성
        response = await client.post(
            f"{BASE_URL}/projects/categories/",
            json={"name": "Important Projects"}
        )
        print(f"Category creation response status: {response.status_code}")
        print(f"Category creation response body: {response.text}")
        assert response.status_code == 200
        category = response.json()
        category_id = category["id"]
        print(f"Created category: {category}")

        # 2. 임시 프로젝트 생성
        response = await client.post(
            f"{BASE_URL}/projects/",
            json={
                "name": "Test Project",
                "description": "This is a test project"
            }
        )
        assert response.status_code == 200
        project = response.json()
        project_id = project["id"]
        print(f"\nCreated project: {project}")
        
        # 3. 프로젝트 조회 (last_accessed_at 갱신 확인)
        response = await client.get(f"{BASE_URL}/projects/{project_id}")
        assert response.status_code == 200
        updated_project = response.json()
        print(f"\nProject after access: {updated_project}")
        
        # 4. 프로젝트를 영구 보관으로 전환
        response = await client.post(
            f"{BASE_URL}/projects/{project_id}/category/{category_id}"
        )
        assert response.status_code == 200
        permanent_project = response.json()
        print(f"\nProject after making permanent: {permanent_project}")

if __name__ == "__main__":
    asyncio.run(test_project_lifecycle())
