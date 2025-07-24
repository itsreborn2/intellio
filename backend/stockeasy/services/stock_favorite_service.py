"""
관심기업(즐겨찾기) 서비스.

관심기업(즐겨찾기) 관련 비즈니스 로직을 처리합니다.
PM 지시사항에 따른 카테고리별 관리, 정렬, 메모 기능 포함
"""

from typing import List, Optional, Tuple, Dict
from uuid import UUID

from sqlalchemy import select, delete, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from loguru import logger

from stockeasy.models.user_stock_favorites import UserStockFavorite


class StockFavoriteService:
    """관심기업(즐겨찾기) 서비스"""
    
    @staticmethod
    async def get_favorites_by_user_id(
        db: AsyncSession, 
        user_id: UUID, 
        category: Optional[str] = None
    ) -> List[UserStockFavorite]:
        """사용자의 관심기업(즐겨찾기) 목록을 조회합니다.
        
        Args:
            db: 데이터베이스 세션
            user_id: 사용자 ID
            category: 카테고리명 (선택사항)
            
        Returns:
            사용자의 관심기업(즐겨찾기) 목록 (카테고리 내 순서대로 정렬)
        """
        try:
            query = select(UserStockFavorite).where(
                UserStockFavorite.user_id == user_id
            )
            
            if category:
                query = query.where(UserStockFavorite.category == category)
            
            # 카테고리별, 표시순서별로 정렬
            query = query.order_by(
                UserStockFavorite.category,
                UserStockFavorite.display_order,
                UserStockFavorite.created_at
            )
            
            result = await db.execute(query)
            favorites = result.scalars().all()
            
            logger.info(f"사용자 {user_id}의 관심기업 {len(favorites)}개 조회 완료 (카테고리: {category or '전체'})")
            return list(favorites)
            
        except Exception as e:
            logger.error(f"관심기업 목록 조회 중 오류: {e}")
            raise
    
    @staticmethod
    async def get_favorites_by_category(
        db: AsyncSession, 
        user_id: UUID
    ) -> Dict[str, List[UserStockFavorite]]:
        """사용자의 관심기업을 카테고리별로 그룹화하여 조회합니다.
        
        Args:
            db: 데이터베이스 세션
            user_id: 사용자 ID
            
        Returns:
            카테고리별로 그룹화된 관심기업 딕셔너리
        """
        try:
            favorites = await StockFavoriteService.get_favorites_by_user_id(db, user_id)
            
            # 카테고리별로 그룹화
            grouped = {}
            for favorite in favorites:
                if favorite.category not in grouped:
                    grouped[favorite.category] = []
                grouped[favorite.category].append(favorite)
            
            logger.info(f"사용자 {user_id}의 관심기업을 {len(grouped)}개 카테고리로 그룹화")
            return grouped
            
        except Exception as e:
            logger.error(f"카테고리별 관심기업 조회 중 오류: {e}")
            raise
    
    @staticmethod
    async def get_categories_by_user_id(db: AsyncSession, user_id: UUID) -> List[Dict[str, any]]:
        """사용자의 카테고리 목록과 각 카테고리별 종목 수를 조회합니다.
        
        Args:
            db: 데이터베이스 세션
            user_id: 사용자 ID
            
        Returns:
            카테고리별 정보 목록 (카테고리명, 종목 수)
        """
        try:
            query = select(
                UserStockFavorite.category,
                func.count(UserStockFavorite.id).label('count')
            ).where(
                UserStockFavorite.user_id == user_id
            ).group_by(
                UserStockFavorite.category
            ).order_by(
                UserStockFavorite.category
            )
            
            result = await db.execute(query)
            categories = result.all()
            
            category_list = [
                {"category": category, "count": count}
                for category, count in categories
            ]
            
            logger.info(f"사용자 {user_id}의 카테고리 {len(category_list)}개 조회 완료")
            return category_list
            
        except Exception as e:
            logger.error(f"카테고리 목록 조회 중 오류: {e}")
            raise
    
    @staticmethod
    async def add_favorite(
        db: AsyncSession, 
        user_id: UUID, 
        stock_code: str, 
        stock_name: Optional[str] = None,
        category: str = "default",
        memo: Optional[str] = None
    ) -> UserStockFavorite:
        """관심기업(즐겨찾기)에 종목을 추가합니다.
        
        Args:
            db: 데이터베이스 세션
            user_id: 사용자 ID
            stock_code: 종목 코드
            stock_name: 종목명 (선택사항)
            category: 카테고리명 (기본값: "default")
            memo: 사용자 메모 (선택사항)
            
        Returns:
            생성된 관심기업 객체
            
        Raises:
            IntegrityError: 이미 해당 카테고리에 동일한 종목이 존재하는 경우
        """
        try:
            # 해당 카테고리에서 다음 표시 순서 계산
            max_order_query = select(func.coalesce(func.max(UserStockFavorite.display_order), 0)).where(
                and_(
                    UserStockFavorite.user_id == user_id,
                    UserStockFavorite.category == category
                )
            )
            result = await db.execute(max_order_query)
            next_order = result.scalar() + 1
            
            favorite = UserStockFavorite(
                user_id=user_id,
                stock_code=stock_code,
                stock_name=stock_name,
                category=category,
                display_order=next_order,
                memo=memo
            )
            
            db.add(favorite)
            await db.commit()
            await db.refresh(favorite)
            
            logger.info(f"사용자 {user_id}가 종목 {stock_code}를 카테고리 '{category}'에 추가")
            return favorite
            
        except IntegrityError as e:
            await db.rollback()
            logger.warning(f"중복 관심기업 추가 시도: 사용자 {user_id}, 종목 {stock_code}, 카테고리 {category}")
            raise ValueError(f"해당 카테고리에 이미 동일한 종목이 존재합니다.")
        except Exception as e:
            await db.rollback()
            logger.error(f"관심기업 추가 중 오류: {e}")
            raise
    
    @staticmethod
    async def remove_favorite_by_id(
        db: AsyncSession, 
        user_id: UUID, 
        favorite_id: int
    ) -> bool:
        """관심기업(즐겨찾기)에서 ID로 종목을 제거합니다.
        
        Args:
            db: 데이터베이스 세션
            user_id: 사용자 ID
            favorite_id: 관심기업 ID
            
        Returns:
            제거 성공 여부
        """
        try:
            query = delete(UserStockFavorite).where(
                and_(
                    UserStockFavorite.id == favorite_id,
                    UserStockFavorite.user_id == user_id
                )
            )
            
            result = await db.execute(query)
            await db.commit()
            
            if result.rowcount > 0:
                logger.info(f"사용자 {user_id}가 관심기업 ID {favorite_id} 제거")
                return True
            else:
                logger.warning(f"제거할 관심기업을 찾을 수 없음: 사용자 {user_id}, ID {favorite_id}")
                return False
                
        except Exception as e:
            await db.rollback()
            logger.error(f"관심기업 제거 중 오류: {e}")
            raise
    
    @staticmethod
    async def remove_favorite(
        db: AsyncSession, 
        user_id: UUID, 
        stock_code: str, 
        category: str = "default"
    ) -> bool:
        """관심기업(즐겨찾기)에서 종목을 제거합니다.
        
        Args:
            db: 데이터베이스 세션
            user_id: 사용자 ID
            stock_code: 종목 코드
            category: 카테고리명 (기본값: "default")
            
        Returns:
            제거 성공 여부
        """
        try:
            query = delete(UserStockFavorite).where(
                and_(
                    UserStockFavorite.user_id == user_id,
                    UserStockFavorite.stock_code == stock_code,
                    UserStockFavorite.category == category
                )
            )
            
            result = await db.execute(query)
            await db.commit()
            
            if result.rowcount > 0:
                logger.info(f"사용자 {user_id}가 종목 {stock_code}를 카테고리 '{category}'에서 제거")
                return True
            else:
                logger.warning(f"제거할 관심기업을 찾을 수 없음: 사용자 {user_id}, 종목 {stock_code}, 카테고리 {category}")
                return False
                
        except Exception as e:
            await db.rollback()
            logger.error(f"관심기업 제거 중 오류: {e}")
            raise
    

    @staticmethod
    async def check_favorite(
        db: AsyncSession, 
        user_id: UUID, 
        stock_code: str, 
        category: str = "default"
    ) -> Optional[UserStockFavorite]:
        """특정 종목이 관심기업(즐겨찾기)에 포함되어 있는지 확인합니다.
        
        Args:
            db: 데이터베이스 세션
            user_id: 사용자 ID
            stock_code: 종목 코드
            category: 카테고리명 (기본값: "default")
            
        Returns:
            관심기업 객체 또는 None
        """
        try:
            query = select(UserStockFavorite).where(
                and_(
                    UserStockFavorite.user_id == user_id,
                    UserStockFavorite.stock_code == stock_code,
                    UserStockFavorite.category == category
                )
            )
            
            result = await db.execute(query)
            favorite = result.scalar_one_or_none()
            
            return favorite
            
        except Exception as e:
            logger.error(f"관심기업 확인 중 오류: {e}")
            raise
    
    @staticmethod
    async def get_favorite_stock_codes(
        db: AsyncSession, 
        user_id: UUID, 
        category: Optional[str] = None
    ) -> List[str]:
        """사용자의 관심기업 종목 코드 목록을 조회합니다.
        
        Args:
            db: 데이터베이스 세션
            user_id: 사용자 ID
            category: 카테고리명 (선택사항)
            
        Returns:
            종목 코드 목록
        """
        try:
            query = select(UserStockFavorite.stock_code).where(
                UserStockFavorite.user_id == user_id
            )
            
            if category:
                query = query.where(UserStockFavorite.category == category)
            
            result = await db.execute(query)
            stock_codes = result.scalars().all()
            
            logger.info(f"사용자 {user_id}의 관심기업 종목 코드 {len(stock_codes)}개 조회")
            return list(stock_codes)
            
        except Exception as e:
            logger.error(f"관심기업 종목 코드 조회 중 오류: {e}")
            raise
    
    @staticmethod
    async def update_favorite(
        db: AsyncSession,
        user_id: UUID,
        favorite_id: int,
        stock_name: Optional[str] = None,
        category: Optional[str] = None,
        display_order: Optional[int] = None,
        memo: Optional[str] = None
    ) -> Optional[UserStockFavorite]:
        """관심기업 정보를 수정합니다.
        
        Args:
            db: 데이터베이스 세션
            user_id: 사용자 ID
            favorite_id: 관심기업 ID
            stock_name: 종목명 (선택사항)
            category: 카테고리명 (선택사항)
            display_order: 표시 순서 (선택사항)
            memo: 사용자 메모 (선택사항)
            
        Returns:
            수정된 관심기업 객체 또는 None
        """
        try:
            query = select(UserStockFavorite).where(
                and_(
                    UserStockFavorite.id == favorite_id,
                    UserStockFavorite.user_id == user_id
                )
            )
            
            result = await db.execute(query)
            favorite = result.scalar_one_or_none()
            
            if not favorite:
                logger.warning(f"수정할 관심기업을 찾을 수 없음: ID {favorite_id}, 사용자 {user_id}")
                return None
            
            # 필드 업데이트
            if stock_name is not None:
                favorite.stock_name = stock_name
            if category is not None:
                favorite.category = category
            if display_order is not None:
                favorite.display_order = display_order
            if memo is not None:
                favorite.memo = memo
            
            await db.commit()
            await db.refresh(favorite)
            
            logger.info(f"사용자 {user_id}의 관심기업 ID {favorite_id} 수정 완료")
            return favorite
            
        except Exception as e:
            await db.rollback()
            logger.error(f"관심기업 수정 중 오류: {e}")
            raise
    
    @staticmethod
    async def reorder_favorites(
        db: AsyncSession,
        user_id: UUID,
        category: str,
        stock_code_orders: List[Tuple[str, int]]
    ) -> bool:
        """카테고리 내 관심기업들의 순서를 재정렬합니다.
        
        Args:
            db: 데이터베이스 세션
            user_id: 사용자 ID
            category: 카테고리명
            stock_code_orders: (종목코드, 순서) 튜플 리스트
            
        Returns:
            재정렬 성공 여부
        """
        try:
            for stock_code, order in stock_code_orders:
                query = select(UserStockFavorite).where(
                    and_(
                        UserStockFavorite.user_id == user_id,
                        UserStockFavorite.stock_code == stock_code,
                        UserStockFavorite.category == category
                    )
                )
                
                result = await db.execute(query)
                favorite = result.scalar_one_or_none()
                
                if favorite:
                    favorite.display_order = order
            
            await db.commit()
            
            logger.info(f"사용자 {user_id}의 카테고리 '{category}' 관심기업 순서 재정렬 완료")
            return True
            
        except Exception as e:
            await db.rollback()
            logger.error(f"관심기업 순서 재정렬 중 오류: {e}")
            raise
