from enum import Enum

class RetentionPeriod(str, Enum):
    """보관 기간"""
    FIVE_DAYS = "5_days"

    @property
    def days(self) -> int:
        """일 수로 변환"""
        return 5

class CategoryType(str, Enum):
    """프로젝트 카테고리 타입"""
    GENERAL = "GENERAL"  # 일반 카테고리
    SYSTEM = "SYSTEM"    # 시스템 카테고리
