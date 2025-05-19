# Tavily API 웹 검색 캐싱 구현 체크리스트

이 체크리스트는 Tavily API 웹 검색 결과 캐싱 시스템 구현을 위한 단계별 작업 목록입니다. 각 작업을 완료할 때마다 체크박스를 표시하여 진행 상황을 추적하세요.

## 1. 사전 준비 및 환경 설정

- [X] 구현 계획 및 일정 수립

## 2. 데이터베이스 모델 및 마이그레이션 작업

- [X] SQLAlchemy 2.0 모델 작성
```python
# backend/stockeasy/models/web_search_cache.py 파일 생성
from datetime import datetime
from typing import List, Optional
from sqlalchemy import String, Integer, ForeignKey, Text, DateTime, Column, Index
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.dialects.postgresql import VECTOR

from common.database.base import Base

class WebSearchQueryCache(Base):
    """웹 검색 쿼리 캐시 테이블"""
    __tablename__ = "web_search_query_cache"
    __table_args__ = {"schema": "stockeasy"}
    
    id: Mapped[int] = mapped_column(primary_key=True)
    query: Mapped[str] = mapped_column(Text, nullable=False)
    stock_code: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    stock_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    embedding: Mapped[List[float]] = mapped_column(VECTOR(3072), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    hit_count: Mapped[int] = mapped_column(Integer, default=0)
    last_hit_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    results: Mapped[List["WebSearchResultCache"]] = relationship(
        "WebSearchResultCache", 
        back_populates="query_cache",
        cascade="all, delete-orphan"
    )

class WebSearchResultCache(Base):
    """웹 검색 결과 캐시 테이블"""
    __tablename__ = "web_search_result_cache"
    __table_args__ = {"schema": "stockeasy"}
    
    id: Mapped[int] = mapped_column(primary_key=True)
    query_cache_id: Mapped[int] = mapped_column(ForeignKey("stockeasy.web_search_query_cache.id", ondelete="CASCADE"))
    title: Mapped[Optional[str]] = mapped_column(Text)
    content: Mapped[Optional[str]] = mapped_column(Text)
    url: Mapped[Optional[str]] = mapped_column(Text)
    search_query: Mapped[Optional[str]] = mapped_column(Text)
    search_date: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    query_cache: Mapped["WebSearchQueryCache"] = relationship("WebSearchQueryCache", back_populates="results")
```

- [ ] Alembic 마이그레이션 스크립트 생성. 이 부분은 직접 작업할거니까 대기.
```bash
# 마이그레이션 생성 명령어
alembic revision --autogenerate -m "웹 검색 캐싱 테이블 추가"
```

- [ ] 벡터 인덱스 생성을 위한 마이그레이션 스크립트 수정
```python
# 생성된 마이그레이션 파일에 추가
def upgrade():
    # ... 자동 생성된 코드 ...
    
    # 벡터 검색 인덱스 생성
    op.execute(
        "CREATE INDEX IF NOT EXISTS web_search_query_cache_embedding_idx "
        "ON stockeasy.web_search_query_cache "
        "USING ivfflat (embedding vector_cosine_ops)"
    )
```

- [ ] 마이그레이션 실행 및 테스트
```bash
# 마이그레이션 실행
alembic upgrade head
```

- [ ] 데이터베이스 모델 동작 검증

## 3. 기존 임베딩 서비스 활용

- [X] 기존 EmbeddingService 활용 코드 작성
```python
# WebSearchAgent 클래스에 임베딩 생성 메서드 추가
async def _get_embedding(self, text: str) -> List[float]:
    """
    텍스트를 임베딩 벡터로 변환합니다.
    
    Args:
        text: 임베딩할 텍스트
        
    Returns:
        임베딩 벡터
    """
    from common.services.embedding import EmbeddingService
    from common.services.embedding_models import EmbeddingModelType
    
    # OpenAI의 large 모델(3072 차원) 사용
    embedding_service = EmbeddingService(model_type=EmbeddingModelType.OPENAI_3_LARGE)
    
    try:
        # 단일 텍스트에 대한 임베딩 생성
        embedding = await embedding_service.create_single_embedding_async(text)
        return embedding
    finally:
        # 리소스 정리
        await embedding_service.aclose()
```

- [ ] 임베딩 생성 기능 테스트 및 성능 검증
- [ ] 오류 처리 강화 및 로깅 추가

## 4. 캐시 관리 모듈 구현

- [X] WebSearchCacheService 클래스 생성
```python
# stockeasy/services/web_search_cache_service.py 파일 생성
from typing import List, Dict, Any, Tuple, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, insert, update, func, desc, text
from datetime import datetime
from loguru import logger

from common.services.embedding_service import EmbeddingService

class WebSearchCacheService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.embedding_service = EmbeddingService()
        self.similarity_threshold = 0.85  # 코사인 유사도 임계값
        
    async def check_cache(self, queries: List[str], stock_code: Optional[str], stock_name: Optional[str]) -> Tuple[List[Dict[str, Any]], List[str]]:
        """
        캐시에서 유사한 쿼리와 결과를 검색합니다.
        
        Args:
            queries: 검색할 쿼리 목록
            stock_code: 종목 코드
            stock_name: 종목 이름
            
        Returns:
            캐시 히트 결과와 캐시 미스 쿼리의 튜플
        """
        # 구현 코드
        
    async def save_to_cache(self, query: str, stock_code: Optional[str], stock_name: Optional[str], embedding: List[float], results: List[Dict[str, Any]]) -> None:
        """
        검색 쿼리와 결과를 캐시에 저장합니다.
        
        Args:
            query: 검색 쿼리
            stock_code: 종목 코드
            stock_name: 종목 이름
            embedding: 쿼리 임베딩
            results: 검색 결과 목록
        """
        # 구현 코드
        
    async def update_hit_count(self, query_cache_id: int) -> None:
        """
        캐시 히트 카운트를 증가시키고, 마지막 히트 시간을 업데이트합니다.
        
        Args:
            query_cache_id: 쿼리 캐시 ID
        """
        # 구현 코드
        
    async def cleanup_old_cache(self, max_age_days: int = 15, exclude_min_hits: int = 5) -> int:
        """
        오래된 캐시 항목을 정리합니다.
        
        Args:
            max_age_days: 최대 보관 일수 (기본값: 15일)
            exclude_min_hits: 이 값 이상의 히트 카운트를 가진 항목은 보존
            
        Returns:
            삭제된 항목 수
        """
        # 구현 코드
```

- [X] 캐시 조회 기능 구현 (check_cache 메서드)
- [X] 캐시 저장 기능 구현 (save_to_cache 메서드)
- [X] 히트 카운트 업데이트 기능 구현 (update_hit_count 메서드)
- [X] 캐시 정리 기능 구현 (cleanup_old_cache 메서드, 15일 기준)
- [X] 오류 처리 및 예외 상황 관리
- [X] 트랜잭션 처리 구현

## 5. WebSearchAgent 클래스 수정

- [X] 웹 검색 에이전트에 캐시 서비스 통합
```python
from stockeasy.services.web_search_cache_service import WebSearchCacheService

class WebSearchAgent(BaseAgent):
    def __init__(self, name: Optional[str] = None, db: Optional[AsyncSession] = None):
        super().__init__(name, db)
        # 기존 코드...
        
        # 캐싱 관련 설정 추가
        self.use_cache = True  # 캐싱 기능 활성화 여부
        self.cache_service = WebSearchCacheService(db) if db else None
        self.cache_expiry_days = 15  # 캐시 유효기한 (일)
        
        # 캐싱 지표
        self.cache_hits = 0
        self.cache_misses = 0
```

- [X] _perform_web_searches 메서드 수정
```python
async def _perform_web_searches(self, search_queries: List[str], stock_code: Optional[str] = None, stock_name: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    생성된 쿼리를 사용하여 웹 검색을 수행합니다. 캐시를 먼저 확인하고 없는 경우 API를 호출합니다.
    
    Args:
        search_queries: 검색할 쿼리 목록
        stock_code: 종목 코드
        stock_name: 종목 이름
        
    Returns:
        검색 결과 목록
    """
    # 구현 코드
```

- [X] process 메서드에 캐싱 관련 지표 추가
- [X] EmbeddingService의 create_single_embedding_async 메서드를 활용한 임베딩 생성 기능 구현
- [X] 캐시 사용 여부 옵션 설정 및 관리

## 6. 캐시 관리 및 유지보수 기능 구현

- [X] 주기적 캐시 정리 스케줄러 작업 추가
```python
# stockeasy/tasks/cache_maintenance.py 파일 생성
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from loguru import logger
from datetime import datetime

from common.core.config import settings
from stockeasy.services.web_search_cache_service import WebSearchCacheService

async def cleanup_web_search_cache(db: Optional[AsyncSession] = None, max_age_days: int = 15) -> None:
    """
    웹 검색 캐시를 정리하는 예약 작업입니다.
    
    Args:
        db: 데이터베이스 세션 (없으면 새로 생성)
        max_age_days: 최대 보관 일수 (기본값: 15일)
    """
    # 구현 코드
```

- [ ] 캐시 통계 수집 및 모니터링 기능 구현
- [ ] 캐시 상태 보고서 생성 기능
- [ ] 캐시 성능 분석 기능

## 7. 테스트 및 성능 최적화

- [ ] 단위 테스트 작성 및 실행
- [ ] 통합 테스트 작성 및 실행
- [ ] 부하 테스트 및 성능 분석
- [ ] 캐시 히트율 측정 및 개선
- [ ] 임계값 및 파라미터 최적화

## 8. 문서화 및 배포