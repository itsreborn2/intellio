"""
RS 즐겨찾기 서비스.

RS 즐겨찾기 관련 비즈니스 로직을 처리합니다.
"""

from typing import List, Optional, Tuple
from uuid import UUID

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from loguru import logger

from stockeasy.models.user_rs_favorites import UserRSFavorite


class RSFavoriteService:
    """RS 즐겨찾기 서비스"""
    
    @staticmethod
    async def get_favorites_by_user_id(db: AsyncSession, user_id: UUID) -> List[UserRSFavorite]:
        """사용자의 RS 즐겨찾기 목록을 조회합니다.
        
        Args:
            db: 데이터베이스 세션
            user_id: 사용자 ID
            
        Returns:
            사용자의 RS 즐겨찾기 목록
        """
        try:
            query = select(UserRSFavorite).where(
                UserRSFavorite.user_id == user_id
            ).order_by(UserRSFavorite.created_at.desc())
            
            result = await db.execute(query)
            favorites = result.scalars().all()
            
            logger.info(f"사용자 {user_id}의 RS 즐겨찾기 {len(favorites)}개 조회 완료")
            return list(favorites)
            
        except Exception as e:
            logger.error(f"RS 즐겨찾기 목록 조회 중 오류: {e}")
            raise
    
    @staticmethod
    async def add_favorite(db: AsyncSession, user_id: UUID, stock_code: str, stock_name: Optional[str] = None) -> UserRSFavorite:
        """RS 즐겨찾기에 종목을 추가합니다.
        
        Args:
            db: 데이터베이스 세션
            user_id: 사용자 ID
            stock_code: 종목 코드
            stock_name: 종목명 (선택사항)
            
        Returns:
            생성된 즐겨찾기 객체
            
        Raises:
            ValueError: 이미 즐겨찾기에 추가된 종목인 경우
        """
        try:
            # 이미 존재하는지 확인
            existing_query = select(UserRSFavorite).where(
                UserRSFavorite.user_id == user_id,
                UserRSFavorite.stock_code == stock_code
            )
            existing_result = await db.execute(existing_query)
            existing_favorite = existing_result.scalar_one_or_none()
            
            if existing_favorite:
                raise ValueError(f"종목 {stock_code}는 이미 즐겨찾기에 추가되어 있습니다.")
            
            # 새 즐겨찾기 생성
            new_favorite = UserRSFavorite(
                user_id=user_id,
                stock_code=stock_code,
                stock_name=stock_name
            )
            
            db.add(new_favorite)
            await db.commit()
            await db.refresh(new_favorite)
            
            logger.info(f"사용자 {user_id}가 종목 {stock_code}({stock_name})를 RS 즐겨찾기에 추가")
            return new_favorite
            
        except IntegrityError as e:
            await db.rollback()
            logger.error(f"RS 즐겨찾기 추가 중 무결성 오류: {e}")
            raise ValueError(f"종목 {stock_code}는 이미 즐겨찾기에 추가되어 있습니다.")
        except Exception as e:
            await db.rollback()
            logger.error(f"RS 즐겨찾기 추가 중 오류: {e}")
            raise
    
    @staticmethod
    async def remove_favorite(db: AsyncSession, user_id: UUID, stock_code: str) -> bool:
        """RS 즐겨찾기에서 종목을 제거합니다.
        
        Args:
            db: 데이터베이스 세션
            user_id: 사용자 ID
            stock_code: 종목 코드
            
        Returns:
            삭제 성공 여부
        """
        try:
            delete_query = delete(UserRSFavorite).where(
                UserRSFavorite.user_id == user_id,
                UserRSFavorite.stock_code == stock_code
            )
            
            result = await db.execute(delete_query)
            await db.commit()
            
            deleted_count = result.rowcount
            if deleted_count > 0:
                logger.info(f"사용자 {user_id}가 종목 {stock_code}를 RS 즐겨찾기에서 제거")
                return True
            else:
                logger.warning(f"사용자 {user_id}의 RS 즐겨찾기에서 종목 {stock_code}를 찾을 수 없음")
                return False
                
        except Exception as e:
            await db.rollback()
            logger.error(f"RS 즐겨찾기 제거 중 오류: {e}")
            raise
    
    @staticmethod
    async def is_favorite(db: AsyncSession, user_id: UUID, stock_code: str) -> bool:
        """종목이 사용자의 RS 즐겨찾기에 있는지 확인합니다.
        
        Args:
            db: 데이터베이스 세션
            user_id: 사용자 ID
            stock_code: 종목 코드
            
        Returns:
            즐겨찾기 여부
        """
        try:
            query = select(UserRSFavorite).where(
                UserRSFavorite.user_id == user_id,
                UserRSFavorite.stock_code == stock_code
            )
            
            result = await db.execute(query)
            favorite = result.scalar_one_or_none()
            
            return favorite is not None
            
        except Exception as e:
            logger.error(f"RS 즐겨찾기 확인 중 오류: {e}")
            raise
    
    @staticmethod
    async def toggle_favorite(db: AsyncSession, user_id: UUID, stock_code: str, stock_name: Optional[str] = None) -> Tuple[bool, Optional[UserRSFavorite]]:
        """RS 즐겨찾기를 토글합니다. (있으면 제거, 없으면 추가)
        
        Args:
            db: 데이터베이스 세션
            user_id: 사용자 ID
            stock_code: 종목 코드
            stock_name: 종목명 (선택사항)
            
        Returns:
            (즐겨찾기 여부, 즐겨찾기 객체 또는 None)
        """
        try:
            # 현재 즐겨찾기 상태 확인
            is_currently_favorite = await RSFavoriteService.is_favorite(db, user_id, stock_code)
            
            if is_currently_favorite:
                # 즐겨찾기에서 제거
                await RSFavoriteService.remove_favorite(db, user_id, stock_code)
                return False, None
            else:
                # 즐겨찾기에 추가
                favorite = await RSFavoriteService.add_favorite(db, user_id, stock_code, stock_name)
                return True, favorite
                
        except Exception as e:
            logger.error(f"RS 즐겨찾기 토글 중 오류: {e}")
            raise
    
    @staticmethod
    async def get_favorite_stock_codes(db: AsyncSession, user_id: UUID) -> List[str]:
        """사용자의 RS 즐겨찾기 종목 코드 목록을 조회합니다.
        
        Args:
            db: 데이터베이스 세션
            user_id: 사용자 ID
            
        Returns:
            즐겨찾기 종목 코드 목록
        """
        try:
            query = select(UserRSFavorite.stock_code).where(
                UserRSFavorite.user_id == user_id
            ).order_by(UserRSFavorite.created_at.desc())
            
            result = await db.execute(query)
            stock_codes = result.scalars().all()
            
            return list(stock_codes)
            
        except Exception as e:
            logger.error(f"RS 즐겨찾기 종목 코드 목록 조회 중 오류: {e}")
            raise
