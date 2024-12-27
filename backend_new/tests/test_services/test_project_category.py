import pytest
from uuid import UUID
from datetime import datetime

from app.models.project_category import ProjectCategory, CategoryType
from app.schemas.project_category import ProjectCategoryCreate, ProjectCategoryUpdate
from app.services.project_category import ProjectCategoryService

@pytest.fixture
async def category_service(async_session):
    return ProjectCategoryService(async_session)

@pytest.mark.asyncio
async def test_create_category(category_service):
    """카테고리 생성 테스트"""
    category_data = ProjectCategoryCreate(
        name="테스트 카테고리",
        description="테스트용 카테고리입니다",
        type=CategoryType.GENERAL
    )
    
    category = await category_service.create_category(category_data)
    assert category.name == "테스트 카테고리"
    assert category.description == "테스트용 카테고리입니다"
    assert category.type == CategoryType.GENERAL
    assert isinstance(category.id, UUID)
    assert isinstance(category.created_at, datetime)
    assert isinstance(category.updated_at, datetime)

@pytest.mark.asyncio
async def test_create_nested_categories(category_service):
    """계층형 카테고리 생성 테스트"""
    # 부모 카테고리 생성
    parent_data = ProjectCategoryCreate(
        name="부모 카테고리",
        type=CategoryType.GENERAL
    )
    parent = await category_service.create_category(parent_data)
    
    # 자식 카테고리 생성
    child_data = ProjectCategoryCreate(
        name="자식 카테고리",
        parent_id=parent.id
    )
    child = await category_service.create_category(child_data)
    
    assert child.parent_id == parent.id
    
    # 트리 구조 확인
    categories = await category_service.get_category_tree()
    assert len(categories) == 1  # 최상위 카테고리 1개
    assert len(categories[0].children) == 1  # 자식 카테고리 1개

@pytest.mark.asyncio
async def test_update_category(category_service):
    """카테고리 업데이트 테스트"""
    # 카테고리 생성
    category_data = ProjectCategoryCreate(name="원래 이름")
    category = await category_service.create_category(category_data)
    
    # 카테고리 업데이트
    update_data = ProjectCategoryUpdate(
        name="변경된 이름",
        description="새로운 설명"
    )
    updated = await category_service.update_category(category.id, update_data)
    
    assert updated.name == "변경된 이름"
    assert updated.description == "새로운 설명"

@pytest.mark.asyncio
async def test_delete_category(category_service):
    """카테고리 삭제 테스트"""
    # 카테고리 생성
    category_data = ProjectCategoryCreate(name="삭제될 카테고리")
    category = await category_service.create_category(category_data)
    
    # 카테고리 삭제
    result = await category_service.delete_category(category.id)
    assert result == True
    
    # 삭제 확인
    deleted = await category_service.get_category(category.id)
    assert deleted is None
