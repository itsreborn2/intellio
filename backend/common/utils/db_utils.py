"""
데이터베이스 유틸리티 모듈.

이 모듈은 데이터베이스 작업에 유용한 함수들을 제공합니다.
"""
from typing import Any, Optional, TypeVar, Sequence, List

from sqlalchemy import Select
from sqlalchemy.ext.asyncio import AsyncSession

T = TypeVar('T')


async def get_one_or_none(db: AsyncSession, query: Select) -> Optional[Any]:
    """
    쿼리 실행 결과에서 첫 번째 객체를 반환하거나 없으면 None을 반환합니다.
    
    Args:
        db: 비동기 데이터베이스 세션
        query: 실행할 SELECT 쿼리
        
    Returns:
        쿼리 결과의 첫 번째 객체 또는 None
    """
    result = await db.execute(query)
    return result.scalar_one_or_none()


async def get_all(db: AsyncSession, query: Select) -> List[Any]:
    """
    쿼리 실행 결과의 모든 객체를 리스트로 반환합니다.
    
    Args:
        db: 비동기 데이터베이스 세션
        query: 실행할 SELECT 쿼리
        
    Returns:
        쿼리 결과의 모든 객체들의 리스트
    """
    result = await db.execute(query)
    return list(result.scalars().all()) 