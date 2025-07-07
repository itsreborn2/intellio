# TimescaleDB 구현 체크리스트

## 📝 개요
TimescaleDB 마이크로아키텍처 구현을 위한 단계별 체크리스트입니다.  
각 단계를 완료한 후 체크박스를 표시하고 다음 단계로 진행하세요.

---

## 🎯 Phase 1: 환경 구축 및 기본 설정 (예상 시간: 2일)

### 1.1 Docker 구성 업데이트
- [x] `docker-compose.yml`에 TimescaleDB 컨테이너 추가
- [x] `docker-compose.yml`에 PgBouncer-TimescaleDB 컨테이너 추가
- [x] 볼륨 설정 추가 (`timescale_data`)
- [x] 네트워크 설정 확인
- [x] 포트 충돌 확인 (5433, 6433)

**완료 조건**: `docker-compose up timescaledb pgbouncer-timescale` 성공 ✅

### 1.2 환경변수 설정
- [x] `.env.development`에 TimescaleDB 환경변수 추가 (`.env.example` 생성)
  ```bash
  TIMESCALE_HOST=pgbouncer-timescale
  TIMESCALE_PORT=6432
  TIMESCALE_USER=collector_user
  TIMESCALE_PASSWORD=강력한_비밀번호
  TIMESCALE_DB=stockeasy_collector
  COLLECTOR_DB_PASSWORD=강력한_비밀번호
  ```
- [x] `.env.example` 파일 업데이트
- [x] 비밀번호 보안성 확인 (최소 16자, 특수문자 포함)

**완료 조건**: 환경변수 로드 확인 ✅

### 1.3 데이터베이스 초기화 스크립트
- [x] `backend/stockeasy/collector/database/init/` 디렉토리 생성
- [x] `01_init_timescaledb.sql` 스크립트 작성
  ```sql
  -- TimescaleDB 확장 설치
  CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;
  
  -- 기본 사용자 및 권한 설정
  GRANT ALL PRIVILEGES ON DATABASE stockeasy_collector TO collector_user;
  ```
- [x] 권한 설정 확인

**완료 조건**: 컨테이너 시작 시 TimescaleDB 확장 자동 설치 ✅

### 1.4 연결 테스트
- [x] TimescaleDB 컨테이너 정상 시작 확인
- [x] PgBouncer-TimescaleDB 연결 확인
- [x] 외부에서 TimescaleDB 접속 테스트
- [x] 헬스체크 정상 동작 확인

**테스트 결과**:
```bash
# TimescaleDB 직접 연결 ✅
PostgreSQL 15.13 on x86_64-pc-linux-musl, compiled by gcc (Alpine 13.2.1_git20240309) 13.2.1 20240309, 64-bit

# TimescaleDB 확장 확인 ✅
timescaledb | 2.20.2

# PgBouncer를 통한 연결 - 수동 테스트 필요
```

**완료 조건**: 모든 연결 테스트 성공 ✅

---

## 🔧 Phase 2: 애플리케이션 설정 (예상 시간: 2일)

### 2.1 설정 파일 업데이트
- [x] `backend/stockeasy/collector/core/config.py` TimescaleDB 설정 추가
  ```python
  # TimescaleDB 설정
  TIMESCALE_HOST: str = Field(default="pgbouncer-timescale")
  TIMESCALE_PORT: int = Field(default=6432)
  TIMESCALE_USER: str = Field(default="collector_user")
  TIMESCALE_PASSWORD: str = Field(...)
  TIMESCALE_DB: str = Field(default="stockeasy_collector")
  
  @property
  def TIMESCALE_DATABASE_URL(self) -> str:
      return f"postgresql+psycopg2://{self.TIMESCALE_USER}:{self.TIMESCALE_PASSWORD}@{self.TIMESCALE_HOST}:{self.TIMESCALE_PORT}/{self.TIMESCALE_DB}"
  
  @property
  def TIMESCALE_ASYNC_DATABASE_URL(self) -> str:
      return f"postgresql+asyncpg://{self.TIMESCALE_USER}:{self.TIMESCALE_PASSWORD}@{self.TIMESCALE_HOST}:{self.TIMESCALE_PORT}/{self.TIMESCALE_DB}"
  ```
- [x] 설정 검증 로직 추가
- [x] 환경변수 바인딩 테스트

**완료 조건**: 설정 값 정상 로드 확인 ✅

### 2.2 데이터베이스 연결 모듈
- [x] `backend/stockeasy/collector/core/timescale_database.py` 생성
  ```python
  from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
  from .config import get_settings
  
  settings = get_settings()
  
  # TimescaleDB 전용 엔진
  timescale_engine = create_async_engine(
      settings.TIMESCALE_ASYNC_DATABASE_URL,
      pool_size=20,
      max_overflow=30,
      pool_timeout=30,
      pool_recycle=3600,
      pool_pre_ping=True,
      echo=False
  )
  
  # TimescaleDB 전용 세션 팩토리
  TimescaleSessionLocal = async_sessionmaker(
      timescale_engine, 
      expire_on_commit=False
  )
  
  async def get_timescale_session():
      """TimescaleDB 세션 생성"""
      async with TimescaleSessionLocal() as session:
          yield session
  ```
- [x] 연결 풀 설정 최적화
- [x] 세션 생명주기 관리

**완료 조건**: 데이터베이스 연결 성공 ✅

### 2.3 Stock Collector 서비스 의존성 업데이트
- [x] `docker-compose.yml`에서 `stock-data-collector` 의존성 추가
  ```yaml
  depends_on:
    - pgbouncer              # 기존 DB
    - pgbouncer-timescale    # TimescaleDB
    - redis
  ```
- [x] 서비스 재시작 테스트
- [x] 의존성 순서 확인

**완료 조건**: Stock Collector 서비스 정상 시작 ✅

---

## 📊 Phase 3: 데이터 모델 구현 (예상 시간: 3일)

### 3.1 SQLAlchemy 모델 정의
- [ ] `backend/stockeasy/collector/models/timescale_models.py` 생성
  ```python
  from sqlalchemy import Column, String, Numeric, BigInteger, Index
  from sqlalchemy.dialects.postgresql import TIMESTAMP
  from sqlalchemy.ext.declarative import declarative_base
  
  TimescaleBase = declarative_base()
  
  class StockPrice(TimescaleBase):
      __tablename__ = "stock_prices"
      
      time = Column(TIMESTAMP(timezone=True), primary_key=True)
      symbol = Column(String(10), primary_key=True)
      open = Column(Numeric(12,2))
      high = Column(Numeric(12,2))
      low = Column(Numeric(12,2))
      close = Column(Numeric(12,2))
      volume = Column(BigInteger)
      trading_value = Column(BigInteger)
      
      __table_args__ = (
          Index('idx_stock_prices_symbol_time', 'symbol', 'time'),
      )
  
  class SupplyDemand(TimescaleBase):
      __tablename__ = "supply_demand"
      
      date = Column(TIMESTAMP(timezone=True), primary_key=True)
      symbol = Column(String(10), primary_key=True)
      institution_amount = Column(BigInteger)
      foreign_amount = Column(BigInteger)
      individual_amount = Column(BigInteger)
  
  class RealtimePrice(TimescaleBase):
      __tablename__ = "realtime_prices"
      
      time = Column(TIMESTAMP(timezone=True), primary_key=True)
      symbol = Column(String(10), primary_key=True)
      price = Column(Numeric(12,2))
      volume = Column(BigInteger)
      bid_price = Column(Numeric(12,2))
      ask_price = Column(Numeric(12,2))
      bid_volume = Column(BigInteger)
      ask_volume = Column(BigInteger)
  ```
- [ ] 모델 임포트 확인
- [ ] 관계 설정 (필요시)

**완료 조건**: 모델 정의 완료 및 임포트 테스트 성공

### 3.2 Pydantic 스키마 정의
- [ ] `backend/stockeasy/collector/schemas/timescale_schemas.py` 생성
  ```python
  from pydantic import BaseModel, Field
  from datetime import datetime
  from decimal import Decimal
  from typing import Optional
  
  class StockPriceCreate(BaseModel):
      time: datetime
      symbol: str = Field(..., max_length=10)
      open: Optional[Decimal] = None
      high: Optional[Decimal] = None
      low: Optional[Decimal] = None
      close: Optional[Decimal] = None
      volume: Optional[int] = None
      trading_value: Optional[int] = None
  
  class StockPriceResponse(StockPriceCreate):
      class Config:
          from_attributes = True
  
  class SupplyDemandCreate(BaseModel):
      date: datetime
      symbol: str = Field(..., max_length=10)
      institution_amount: Optional[int] = None
      foreign_amount: Optional[int] = None
      individual_amount: Optional[int] = None
  
  class RealtimePriceCreate(BaseModel):
      time: datetime
      symbol: str = Field(..., max_length=10)
      price: Optional[Decimal] = None
      volume: Optional[int] = None
      bid_price: Optional[Decimal] = None
      ask_price: Optional[Decimal] = None
      bid_volume: Optional[int] = None
      ask_volume: Optional[int] = None
  ```
- [ ] 검증 로직 추가
- [ ] 타입 힌트 확인

**완료 조건**: 스키마 정의 완료 및 검증 테스트

### 3.3 데이터베이스 마이그레이션
- [ ] Alembic 설정 (TimescaleDB용)
- [ ] 초기 마이그레이션 스크립트 생성
- [ ] 테이블 생성 확인
- [ ] 하이퍼테이블 생성 스크립트
  ```sql
  -- 하이퍼테이블 생성
  SELECT create_hypertable('stock_prices', 'time', chunk_time_interval => INTERVAL '1 day');
  SELECT create_hypertable('supply_demand', 'date', chunk_time_interval => INTERVAL '7 days');
  SELECT create_hypertable('realtime_prices', 'time', chunk_time_interval => INTERVAL '1 hour');
  ```

**완료 조건**: 모든 테이블과 하이퍼테이블 생성 성공

---

## 🚀 Phase 4: 비즈니스 로직 구현 (예상 시간: 3일)

### 4.1 TimescaleDB 서비스 클래스
- [ ] `backend/stockeasy/collector/services/timescale_service.py` 생성
  ```python
  from typing import List, Optional, Dict, Any
  from datetime import datetime, timedelta
  from sqlalchemy.ext.asyncio import AsyncSession
  from sqlalchemy import text, select, insert
  from ..models.timescale_models import StockPrice, SupplyDemand, RealtimePrice
  from ..schemas.timescale_schemas import StockPriceCreate, SupplyDemandCreate
  from ..core.timescale_database import TimescaleSessionLocal
  
  class TimescaleService:
      async def bulk_insert_stock_prices(self, prices: List[StockPriceCreate]):
          """주가 데이터 대량 삽입"""
          
      async def get_stock_prices(self, symbol: str, start_date: datetime, end_date: datetime):
          """주가 데이터 조회"""
          
      async def insert_supply_demand(self, supply_demand: SupplyDemandCreate):
          """수급 데이터 삽입"""
          
      async def get_realtime_price(self, symbol: str) -> Optional[Dict[str, Any]]:
          """실시간 가격 조회"""
  ```
- [ ] CRUD 메서드 구현
- [ ] 에러 핸들링 추가
- [ ] 로깅 설정

**완료 조건**: 기본 CRUD operations 구현 완료

### 4.2 배치 처리 최적화
- [ ] 대량 삽입 최적화 (bulk_insert_mappings 사용)
- [ ] 트랜잭션 관리
- [ ] 배치 크기 최적화 (1000건 단위)
- [ ] 에러 발생 시 롤백 처리

**완료 조건**: 1만건 데이터 배치 삽입 성능 테스트 통과

### 4.3 기존 DataCollectorService 연동
- [ ] `data_collector.py`에 TimescaleService 연동
- [ ] 실시간 데이터를 TimescaleDB에 저장하는 로직 추가
- [ ] 기존 캐시 로직과 병행 처리
- [ ] 에러 발생 시 기존 로직으로 폴백

**완료 조건**: 실시간 데이터 수집이 TimescaleDB와 Redis 양쪽에 저장

---

## 🔧 Phase 5: API 엔드포인트 구현 (예상 시간: 2일)

### 5.1 TimescaleDB API 라우터
- [ ] `backend/stockeasy/collector/api/v1/timescale.py` 생성
  ```python
  from fastapi import APIRouter, Depends, HTTPException, Query
  from datetime import datetime, timedelta
  from typing import List, Optional
  from ...services.timescale_service import TimescaleService
  from ...schemas.timescale_schemas import StockPriceResponse
  
  router = APIRouter(prefix="/timescale", tags=["TimescaleDB"])
  
  @router.get("/stock-prices/{symbol}")
  async def get_stock_prices(
      symbol: str,
      start_date: Optional[datetime] = Query(default=None),
      end_date: Optional[datetime] = Query(default=None),
      timescale_service: TimescaleService = Depends()
  ):
      """주가 데이터 조회"""
  
  @router.get("/realtime/{symbol}")
  async def get_realtime_price(
      symbol: str,
      timescale_service: TimescaleService = Depends()
  ):
      """실시간 가격 조회"""
  ```
- [ ] 의존성 주입 설정
- [ ] 에러 핸들링 추가
- [ ] API 문서화 (docstring)

**완료 조건**: API 엔드포인트 정상 동작

### 5.2 기존 API에 TimescaleDB 연동
- [ ] 기존 API에서 TimescaleDB 데이터 조회 옵션 추가
- [ ] 성능 비교 엔드포인트 추가
- [ ] 데이터 일관성 검증 엔드포인트 추가

**완료 조건**: 기존 API와 새 API 모두 정상 동작

---

## �� Phase 6: TimescaleDB 특화 기능 구현 (예상 시간: 3일)

### 6.1 연속 집계 (Continuous Aggregates) 설정
- [ ] 일봉 자동 생성 뷰 생성
  ```sql
  CREATE MATERIALIZED VIEW daily_candles
  WITH (timescaledb.continuous) AS
  SELECT 
      time_bucket('1 day', time) as day,
      symbol,
      first(open, time) as open,
      max(high) as high,
      min(low) as low,
      last(close, time) as close,
      sum(volume) as volume,
      sum(trading_value) as trading_value
  FROM stock_prices
  GROUP BY day, symbol;
  ```
- [ ] 자동 갱신 정책 설정
  ```sql
  SELECT add_continuous_aggregate_policy('daily_candles',
      start_offset => INTERVAL '3 days',
      end_offset => INTERVAL '1 hour',
      schedule_interval => INTERVAL '1 hour');
  ```
- [ ] 주봉, 월봉 뷰도 생성

**완료 조건**: 연속 집계 뷰 정상 동작 및 자동 갱신 확인

### 6.2 압축 정책 설정
- [ ] 테이블별 압축 설정
  ```sql
  ALTER TABLE stock_prices SET (
      timescaledb.compress,
      timescaledb.compress_segmentby = 'symbol'
  );
  
  SELECT add_compression_policy('stock_prices', INTERVAL '30 days');
  ```
- [ ] 압축률 모니터링 쿼리 작성
- [ ] 압축 설정 최적화

**완료 조건**: 압축 정책 적용 및 압축률 확인

### 6.3 데이터 보관 정책
- [ ] 오래된 데이터 삭제 정책 설정
  ```sql
  SELECT add_retention_policy('realtime_prices', INTERVAL '7 days');
  ```
- [ ] 중요 데이터는 압축만 적용
- [ ] 보관 정책 모니터링

**완료 조건**: 데이터 보관 정책 정상 동작

---

## 🧪 Phase 7: 테스트 및 성능 최적화 (예상 시간: 2일)

### 7.1 단위 테스트
- [ ] TimescaleService 단위 테스트 작성
- [ ] API 엔드포인트 테스트
- [ ] 에러 케이스 테스트
- [ ] 모킹을 사용한 독립적인 테스트

**완료 조건**: 테스트 커버리지 80% 이상

### 7.2 통합 테스트
- [ ] 전체 데이터 플로우 테스트
- [ ] 실시간 데이터 수집 → 저장 → 조회 테스트
- [ ] 대용량 데이터 처리 테스트
- [ ] 동시성 테스트

**완료 조건**: 모든 통합 테스트 통과

### 7.3 성능 벤치마크
- [ ] 대량 데이터 삽입 성능 측정
- [ ] 쿼리 성능 측정 (기존 vs TimescaleDB)
- [ ] 메모리 사용량 모니터링
- [ ] 디스크 사용량 모니터링

**목표 성능**:
- [ ] 1분봉 데이터 1만건 삽입 < 1초
- [ ] 일봉 데이터 1년치 조회 < 100ms
- [ ] 실시간 가격 조회 < 10ms

### 7.4 부하 테스트
- [ ] 동시 사용자 100명 시뮬레이션
- [ ] API 응답 시간 측정
- [ ] 리소스 사용량 모니터링
- [ ] 병목 지점 식별 및 최적화

**완료 조건**: 부하 테스트 통과 및 성능 목표 달성

---

## 📈 Phase 8: 모니터링 및 관리 도구 (예상 시간: 2일)

### 8.1 헬스체크 시스템
- [ ] TimescaleDB 연결 상태 확인
- [ ] PgBouncer 상태 확인
- [ ] 디스크 공간 모니터링
- [ ] 메모리 사용량 모니터링

**완료 조건**: 헬스체크 API 정상 동작

### 8.2 성능 모니터링
- [ ] 압축률 모니터링 API
- [ ] 쿼리 성능 통계 API
- [ ] 연결 풀 상태 API
- [ ] 대시보드 데이터 제공 API

**완료 조건**: 모니터링 대시보드에서 TimescaleDB 지표 확인 가능

### 8.3 관리 도구
- [ ] 수동 압축 실행 API
- [ ] 캐시 초기화 API
- [ ] 데이터 동기화 API
- [ ] 백업 트리거 API

**완료 조건**: 관리 API를 통한 운영 작업 가능

---

## 🚀 Phase 9: 배포 및 운영 (예상 시간: 1일)

### 9.1 프로덕션 설정
- [ ] 프로덕션용 환경변수 설정
- [ ] 로그 레벨 조정
- [ ] 보안 설정 강화
- [ ] 백업 설정

**완료 조건**: 프로덕션 환경 준비 완료

### 9.2 배포 테스트
- [ ] 스테이징 환경 배포
- [ ] 프로덕션 배포
- [ ] 롤백 테스트
- [ ] 모니터링 확인

**완료 조건**: 안정적인 배포 완료

### 9.3 문서화
- [ ] API 문서 업데이트
- [ ] 운영 가이드 작성
- [ ] 트러블슈팅 가이드 작성
- [ ] 성능 튜닝 가이드 작성

**완료 조건**: 완전한 문서화 완료

---

## ✅ 최종 검증 체크리스트

### 기능 검증
- [ ] 실시간 데이터 수집 정상 동작
- [ ] 차트 데이터 조회 정상 동작
- [ ] 수급 데이터 저장/조회 정상 동작
- [ ] 연속 집계 뷰 정상 동작
- [ ] 압축 정책 정상 동작

### 성능 검증
- [ ] API 응답시간 목표 달성
- [ ] 데이터 압축률 만족
- [ ] 메모리 사용량 적정 수준
- [ ] 디스크 사용량 효율적

### 운영 검증
- [ ] 헬스체크 정상 동작
- [ ] 모니터링 지표 수집
- [ ] 로그 수집 정상 동작
- [ ] 알림 시스템 연동

### 보안 검증
- [ ] 접근 권한 설정 확인
- [ ] 네트워크 보안 설정 확인
- [ ] 데이터 암호화 확인
- [ ] 백업 보안 확인

---

## 📋 완료 후 액션 아이템

### 즉시 수행
- [ ] 팀에 완료 보고
- [ ] 사용자 가이드 배포
- [ ] 모니터링 알림 설정
- [ ] 백업 스케줄 설정

### 향후 개선 사항
- [ ] 추가 성능 최적화 계획
- [ ] 새로운 데이터 타입 지원 계획
- [ ] 분산 처리 도입 검토
- [ ] ML/AI 연동 방안 검토

---

**⚠️ 중요 참고사항**:
1. **각 Phase 완료 후 반드시 테스트를 수행**하세요
2. **문제 발생 시 즉시 롤백 계획**을 실행하세요
3. **성능 지표를 지속적으로 모니터링**하세요
4. **보안 설정을 정기적으로 검토**하세요

---

*체크리스트 생성일: 2024년*  
*최종 수정일: 2024년*  
*담당자: AI Assistant* 