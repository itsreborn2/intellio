# Tavily API 웹 검색 캐싱 시스템 명세서

## 1. 소개

### 1.1 배경
현재 주식 정보 검색 시스템은 사용자의 질문을 받아 여러 검색 쿼리(멀티 쿼리)를 생성하고, Tavily API를 통해 웹 검색을 수행합니다. 이 과정에서 API 호출 비용이 발생하며, 유사한 쿼리가 반복될 경우 불필요한 비용이 지속적으로 발생합니다.

### 1.2 목표
- Tavily API 이용 요금 절감을 위한 캐싱 시스템 구축
- PostgreSQL과 벡터 확장을 이용한 효율적인 유사 쿼리 검색 구현
- 멀티 쿼리와 웹 검색 결과를 데이터베이스에 저장하고 재사용
- 캐시 적중률 추적 및 모니터링

### 1.3 기대 효과
- API 호출 비용 절감
- 반복 쿼리에 대한 응답 시간 단축
- 검색 결과의 일관성 유지
- 시스템 안정성 향상

## 2. 시스템 설계

### 2.1 데이터베이스 스키마

#### 2.1.1 SQLAlchemy 모델 정의
SQLAlchemy 2.0과 Alembic을 사용하여 데이터베이스 모델과 마이그레이션을 관리합니다. 
다음과 같이 `backend/stockeasy/models` 폴더에 모델을 정의합니다:

```python
# backend/stockeasy/models/web_search_cache.py
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
    
    # 벡터 검색을 위한 인덱스는 Alembic 마이그레이션에서 별도로 정의

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

#### 2.1.2 벡터 인덱스 생성을 위한 Alembic 마이그레이션
PostgreSQL 벡터 확장을 사용하여 효율적인 임베딩 검색을 위한 인덱스를 마이그레이션에서 생성합니다:

```python
# Alembic 마이그레이션 파일에 추가
from alembic import op

# 마이그레이션 업그레이드 함수에 추가
def upgrade():
    # 모델에 의한 테이블 생성 후 추가
    
    # 벡터 검색 인덱스 생성
    op.execute(
        "CREATE INDEX IF NOT EXISTS web_search_query_cache_embedding_idx "
        "ON stockeasy.web_search_query_cache "
        "USING ivfflat (embedding vector_cosine_ops)"
    )
```

### 2.2 시스템 동작 흐름

#### 2.2.1 기본 흐름
1. 사용자 질문 수신
2. 멀티 쿼리 생성
3. 각 쿼리의 임베딩 생성 (OpenAI / larger3 모델)
4. 데이터베이스에서 유사 쿼리 검색 (코사인 유사도)
5. 캐시 히트 시: 데이터베이스에서 결과 검색, 히트 카운트 증가
6. 캐시 미스 시: Tavily API 호출, 결과 및 쿼리 저장
7. 결과 반환

#### 2.2.2 캐시 검색 알고리즘
1. 쿼리 임베딩 생성
2. 코사인 유사도 기반 벡터 검색 수행
3. 유사도 임계값(예: 0.89) 이상인 쿼리를 캐시 히트로 판단
4. 여러 히트 중 유사도가 가장 높은 것 선택
5. 히트가 없을 경우 API 호출

## 3. 구현 상세

### 3.1 필요 모듈

#### 3.1.1 임베딩 생성 모듈
- 기존 EmbeddingService 활용하여 쿼리 텍스트의 임베딩 벡터 생성
- OpenAI_3_LARGE 모델 사용 (3072 차원)
- create_single_embedding_async 메서드 활용

```python
async def get_embedding(text: str) -> List[float]:
    """
    텍스트를 임베딩 벡터로 변환합니다.
    
    Args:
        text: 임베딩할 텍스트
        
    Returns:
        임베딩 벡터
    """
    # 기존 EmbeddingService 활용
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

#### 3.1.2 캐시 조회 모듈
- 생성된 쿼리로 데이터베이스 검색
- 코사인 유사도를 사용한 벡터 검색 수행
- 임계값 설정 및 필터링

```python
async def check_cache(queries: List[str], stock_code: Optional[str], stock_name: Optional[str]) -> Tuple[List[Dict[str, Any]], List[str]]:
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
```

#### 3.1.3 캐시 저장 모듈
- 쿼리 정보 및 임베딩 저장
- 검색 결과 저장
- 트랜잭션 처리

```python
async def save_to_cache(query: str, stock_code: Optional[str], stock_name: Optional[str], embedding: List[float], results: List[Dict[str, Any]]) -> None:
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
```

#### 3.1.4 캐시 히트 관리 모듈
- 히트 카운트 증가
- 마지막 히트 시간 업데이트

```python
async def update_hit_count(query_cache_id: int) -> None:
    """
    캐시 히트 카운트를 증가시키고 타임스탬프를 업데이트합니다.
    
    Args:
        query_cache_id: 쿼리 캐시 ID
    """
    # 구현 코드
```

### 3.2 WebSearchAgent 클래스 수정

현재 WebSearchAgent 클래스는 다음과 같이 수정되어야 합니다:

#### 3.2.1 초기화 메서드 수정
```python
def __init__(self, name: Optional[str] = None, db: Optional[AsyncSession] = None):
    # 기존 코드
    
    # 캐싱 관련 설정 추가
    self.use_cache = True  # 캐싱 기능 활성화 여부
    self.similarity_threshold = 0.85  # 유사도 임계값
    self.embedding_dimension = 3072  # larger3 모델 임베딩 차원
    self.cache_expiry_days = 15  # 캐시 유효기한 (일)
    
    # 캐싱 지표
    self.cache_hits = 0
    self.cache_misses = 0
```

#### 3.2.2 process 메서드 수정
- 캐시 히트/미스 지표 추가
- 캐시 사용 여부에 따른 분기 처리

#### 3.2.3 _perform_web_searches 메서드 수정
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
    try:
        all_results = []
        
        if self.use_cache:
            # 캐시 검색
            cache_results, cache_miss_queries = await self._check_cache(search_queries, stock_code, stock_name)
            
            # 캐시 히트 결과 추가
            if cache_results:
                all_results.extend(cache_results)
                self.cache_hits += len(search_queries) - len(cache_miss_queries)
                logger.info(f"캐시 히트: {len(search_queries) - len(cache_miss_queries)}개 쿼리")
            
            # 캐시 미스 쿼리만 API 호출
            if cache_miss_queries:
                self.cache_misses += len(cache_miss_queries)
                logger.info(f"캐시 미스: {len(cache_miss_queries)}개 쿼리, API 호출")
                api_results = await self.tavily_service.batch_search_async(
                    queries=cache_miss_queries,
                    search_depth="advanced",
                    max_results=self.max_results_per_query,
                    topic="general",
                    time_range="year"
                )
                
                # 결과 캐싱
                for i, query in enumerate(cache_miss_queries):
                    query_results = [r for r in api_results if r.get("search_query") == query]
                    if query_results:
                        # 임베딩 생성 및 캐시 저장 (EmbeddingService 활용)
                        embedding = await self._get_embedding(query)  # EmbeddingService의 create_single_embedding_async 메서드 활용
                        await self._save_to_cache(query, stock_code, stock_name, embedding, query_results)
                
                all_results.extend(api_results)
        else:
            # 캐시 사용하지 않고 모든 쿼리 API 호출
            all_results = await self.tavily_service.batch_search_async(
                queries=search_queries,
                search_depth="advanced",
                max_results=self.max_results_per_query,
                topic="general",
                time_range="year"
            )
        
        return all_results
            
    except Exception as e:
        logger.error(f"웹 검색 수행 중 오류 발생: {str(e)}", exc_info=True)
        return []
```

### 3.3 캐시 관리 전략

#### 3.3.1 캐시 만료 정책
- 시간 기반 만료: 생성된 지 15일이 지난 캐시 항목 제거
- 히트 기반 유지: 히트 카운트가 높은 항목은 더 오래 유지

#### 3.3.2 캐시 정리 작업
- 주기적인 배치 작업으로 오래된 캐시 정리 (15일 초과 항목)
- 시스템 부하가 적은 시간에 실행

#### 3.3.3 캐시 크기 관리
- 데이터베이스 공간 모니터링
- 필요 시 가장 오래되고 사용 빈도가 낮은 항목부터 제거

## 4. 모니터링 및 평가

### 4.1 성능 지표
- 캐시 적중률 (%)
- API 호출 절감 수 (횟수)
- 평균 응답 시간 (ms)
- 데이터베이스 공간 사용량 (MB)

### 4.2 로깅
- 캐시 히트/미스 이벤트 로깅
- 유사도 점수 로깅
- 오류 및 예외 상황 로깅


## 5. 구현 계획 및 일정

### 5.1 단계별 구현
1. 데이터베이스 스키마 생성 및 인덱스 설정
2. 임베딩 생성 모듈 구현
3. 캐시 조회 및 저장 모듈 구현
4. WebSearchAgent 클래스 수정
5. 캐시 관리 및 정리 기능 구현


## 6. 제약사항 및 고려사항

### 6.1. 제약사항
- PostgreSQL의 벡터 확장이 올바르게 설치되어 있어야 함
- OpenAI API가 정상 작동해야 임베딩 생성 가능
- 임베딩 생성에도 API 비용 발생 (비용 대비 효율 고려)

### 6.2. 고려사항
- 웹 데이터는 시간이 지남에 따라 최신성이 떨어질 수 있음
- 캐시 만료 정책을 통해 데이터 최신성 관리 필요 (15일 만료 기준)
- 유사도 임계값 조정을 통한 캐시 적중률과 정확도 간 균형 조정

### 6.3. 확장성 고려
- 캐시 크기 증가에 따른 성능 영향 분석
- 임베딩 모델 변경 시 마이그레이션 전략