import asyncio
import pytest
from httpx import AsyncClient
from uuid import UUID

from app.main import app
from app.models.project import Project
from app.models.user import User
from app.core.config import settings

@pytest.mark.asyncio
async def test_user_project_integration():
    """UUID 관리 및 User-Project 관계 테스트"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        # 1. 익명 사용자 생성
        response = await client.post("/api/v1/users/anonymous")
        assert response.status_code == 200
        user_data = response.json()
        assert "id" in user_data
        user_id = user_data["id"]
        
        # UUID 형식 검증
        try:
            UUID(user_id)
        except ValueError:
            pytest.fail("Invalid UUID format for user_id")

        # 2. 프로젝트 생성
        project_data = {
            "name": "Test Project",
            "description": "Test Description",
            "retention_period": "ONE_DAY"
        }
        response = await client.post(
            "/api/v1/projects/",
            json=project_data,
            headers={"X-User-ID": user_id}
        )
        assert response.status_code == 200
        project = response.json()
        
        # UUID 형식 검증
        try:
            UUID(project["id"])
        except ValueError:
            pytest.fail("Invalid UUID format for project_id")
            
        # user_id 관계 검증
        assert project["user_id"] == user_id

        # 3. 프로젝트 조회
        response = await client.get(f"/api/v1/projects/{project['id']}")
        assert response.status_code == 200
        retrieved_project = response.json()
        assert retrieved_project["id"] == project["id"]
        assert retrieved_project["user_id"] == user_id

        # 4. 프로젝트 목록 조회
        response = await client.get("/api/v1/projects/")
        assert response.status_code == 200
        projects = response.json()["items"]
        assert len(projects) > 0
        assert any(p["id"] == project["id"] for p in projects)

if __name__ == "__main__":
    asyncio.run(test_user_project_integration())
