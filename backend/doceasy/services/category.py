"""카테고리 서비스"""

from typing import List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.category import Category
from app.schemas.category import CategoryCreate, CategoryResponse
from app.core.redis import RedisClient
import json
import logging

logger = logging.getLogger(__name__)

class CategoryService:
    """카테고리 서비스"""
    
    def __init__(self, db: AsyncSession, redis_client: RedisClient):
        self.db = db
        self.redis_client = redis_client
    
    async def get_categories(self) -> List[CategoryResponse]:
        """카테고리 목록을 조회합니다."""
        cache_key = "categories"
        
        # Redis에서 캐시된 데이터 조회
        cached_data = await self.redis_client.get_key(cache_key)
        if cached_data:
            logger.info("카테고리 데이터를 Redis 캐시에서 조회했습니다.")
            return [CategoryResponse(**item) for item in cached_data]
            
        logger.info("카테고리 데이터를 DB에서 조회합니다.")
        result = await self.db.execute(select(Category))
        categories = result.scalars().all()
            
        # 응답 데이터 생성
        response_data = [
            CategoryResponse(
                id=str(category.id),
                name=category.name,
                type=category.type,
                created_at=category.created_at
            ) for category in categories
        ]
            
        # Redis에 캐시 저장
        cache_data = [category.model_dump(mode='json') for category in response_data]
        await self.redis_client.set_key(cache_key, json.dumps(cache_data), expire_in_seconds=3600)
        logger.info("카테고리 데이터 Redis 캐시 저장 성공")
            
        return response_data

    async def create_category(self, category_in: CategoryCreate) -> Category:
        """새로운 카테고리를 생성합니다."""
        # 동일한 이름의 카테고리가 있는지 확인
        stmt = select(Category).where(Category.name == category_in.name)
        result = await self.db.execute(stmt)
        existing_category = result.scalar_one_or_none()
        
        if existing_category:
            raise ValueError(f"이미 존재하는 카테고리 이름입니다: {category_in.name}")
        
        # 새 카테고리 생성
        category = Category(**category_in.dict())
        self.db.add(category)
        await self.db.commit()
        await self.db.refresh(category)
        
        # 캐시 삭제
        await self.redis_client.delete_key("categories")
        
        return category

    async def delete_category(self, category_id: str) -> bool:
        """카테고리를 삭제합니다."""
        stmt = select(Category).where(Category.id == category_id)
        result = await self.db.execute(stmt)
        category = result.scalar_one_or_none()
        
        if not category:
            return False
        
        await self.db.delete(category)
        await self.db.commit()
        
        # 캐시 삭제
        await self.redis_client.delete_key("categories")
        
        return True
