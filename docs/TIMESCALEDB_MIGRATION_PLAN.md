# TimescaleDB 마이그레이션 계획

## 📋 프로젝트 개요

### 목표
기존 PostgreSQL + PgBouncer 구조를 유지하면서, 주식 데이터 수집을 위한 TimescaleDB 마이크로아키텍처 추가

### 배경
- 주식 차트, 수급데이터, 실시간 가격 등 시계열 데이터의 효율적 처리 필요
- 기존 애플리케이션 DB와 분리하여 성능 최적화
- 마이크로서비스 아키텍처로 독립적인 확장 가능

## 🏗️ 아키텍처 설계

### 현재 구조
```
┌─────────────────┐    ┌──────────────┐    ┌──────────────┐
│   FastAPI       │───▶│  PgBouncer   │───▶│ PostgreSQL   │
│   Celery        │    │   :6432      │    │   :5432      │
│   Other Services│    │              │    │              │
└─────────────────┘    └──────────────┘    └──────────────┘
```

### 목표 구조 (이중 PgBouncer)
```
┌─────────────────┐    ┌──────────────┐    ┌──────────────┐
│   FastAPI       │───▶│  PgBouncer   │───▶│ PostgreSQL   │
│   Celery        │    │   :6432      │    │   :5432      │
│   Other Services│    │              │    │ (기존 데이터) │
└─────────────────┘    └──────────────┘    └──────────────┘
          │
          │
┌─────────────────┐    ┌──────────────┐    ┌──────────────┐
│ Stock Collector │───▶│PgBouncer-TS  │───▶│ TimescaleDB  │
│                 │    │   :6433      │    │   :5433      │
│                 │    │(session mode)│    │(주식 데이터)  │
└─────────────────┘    └──────────────┘    └──────────────┘
```

## 🎯 데이터 분류 및 저장 전략

### TimescaleDB에 저장할 데이터 (시계열)
- **주가 차트 데이터**: OHLCV, 1분봉/5분봉/일봉
- **실시간 가격 데이터**: 현재가, 호가, 체결
- **수급 데이터**: 기관/외국인/개인 순매수
- **거래량 분석**: 시간대별 거래량, 거래대금

### PostgreSQL에 유지할 데이터 (관계형)
- **종목 기본정보**: 종목코드, 종목명, 시장구분
- **기업 정보**: 업종, 상장일, 액면가
- **ETF 구성종목**: ETF별 편입종목 및 비중
- **사용자 데이터**: 관심종목, 포트폴리오

## 🔧 기술 스택

### TimescaleDB 선택 이유
- **PostgreSQL 완전 호환**: 기존 지식과 도구 활용
- **시계열 + 관계형**: 하나의 DB에서 모든 데이터 타입 지원
- **자동 파티셔닝**: 시간 기반 자동 분할로 성능 최적화
- **압축 기능**: 오래된 데이터 자동 압축
- **연속 집계**: 실시간 집계 뷰 (분봉 → 일봉)

### PgBouncer 설정 전략
- **기존 PgBouncer**: Transaction 모드 유지 (기존 앱용)
- **TimescaleDB PgBouncer**: Session 모드 (TimescaleDB 기능 완전 활용)

## 📊 데이터 모델 설계

### TimescaleDB 하이퍼테이블
```sql
-- 주가 데이터 (1분봉)
CREATE TABLE stock_prices (
    time TIMESTAMPTZ NOT NULL,
    symbol VARCHAR(10) NOT NULL,
    open NUMERIC(12,2),
    high NUMERIC(12,2),
    low NUMERIC(12,2),
    close NUMERIC(12,2),
    volume BIGINT,
    trading_value BIGINT
);

SELECT create_hypertable('stock_prices', 'time', chunk_time_interval => INTERVAL '1 day');

-- 수급 데이터
CREATE TABLE supply_demand (
    date TIMESTAMPTZ NOT NULL,
    symbol VARCHAR(10) NOT NULL,
    institution_amount BIGINT,
    foreign_amount BIGINT,
    individual_amount BIGINT
);

SELECT create_hypertable('supply_demand', 'date', chunk_time_interval => INTERVAL '7 days');

-- 실시간 데이터
CREATE TABLE realtime_prices (
    time TIMESTAMPTZ NOT NULL,
    symbol VARCHAR(10) NOT NULL,
    price NUMERIC(12,2),
    volume BIGINT,
    bid_price NUMERIC(12,2),
    ask_price NUMERIC(12,2),
    bid_volume BIGINT,
    ask_volume BIGINT
);

SELECT create_hypertable('realtime_prices', 'time', chunk_time_interval => INTERVAL '1 hour');
```

### 연속 집계 (자동 일봉 생성)
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

### 압축 정책
```sql
-- 30일 이상 데이터 압축
ALTER TABLE stock_prices SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'symbol'
);

SELECT add_compression_policy('stock_prices', INTERVAL '30 days');
```

## 🐳 Docker 구성

### 컨테이너 추가
```yaml
services:
  # 기존 서비스들 유지...
  
  # TimescaleDB 추가
  timescaledb:
    image: timescale/timescaledb:latest-pg15
    environment:
      POSTGRES_DB: stockeasy_collector
      POSTGRES_USER: collector_user
      POSTGRES_PASSWORD: ${COLLECTOR_DB_PASSWORD}
    ports:
      - "5433:5432"
    volumes:
      - timescale_data:/var/lib/postgresql/data
      - ./backend/stockeasy/collector/database/init:/docker-entrypoint-initdb.d
    command: >
      postgres 
      -c shared_preload_libraries=timescaledb
      -c max_connections=200
      -c shared_buffers=256MB
      -c effective_cache_size=1GB
    networks:
      - app-network

  # TimescaleDB용 PgBouncer
  pgbouncer-timescale:
    image: edoburu/pgbouncer:latest
    environment:
      - DB_USER=collector_user
      - DB_PASSWORD=${COLLECTOR_DB_PASSWORD}
      - DB_HOST=timescaledb
      - DB_NAME=stockeasy_collector
      - POOL_MODE=session
      - MAX_CLIENT_CONN=100
      - DEFAULT_POOL_SIZE=20
      - ADMIN_USERS=collector_user
      - LISTEN_PORT=6432
      - AUTH_TYPE=scram-sha-256
    ports:
      - "6433:6432"
    depends_on:
      - timescaledb
    networks:
      - app-network

volumes:
  timescale_data:
```

## 🔧 애플리케이션 설정

### 환경변수 추가
```bash
# .env.development
TIMESCALE_HOST=pgbouncer-timescale
TIMESCALE_PORT=6432
TIMESCALE_USER=collector_user
TIMESCALE_PASSWORD=your_strong_password
TIMESCALE_DB=stockeasy_collector
COLLECTOR_DB_PASSWORD=your_strong_password
```

### 데이터베이스 연결 설정
```python
# backend/stockeasy/collector/core/config.py
class Settings(BaseSettings):
    # TimescaleDB 설정
    TIMESCALE_HOST: str = Field(default="pgbouncer-timescale")
    TIMESCALE_PORT: int = Field(default=6432)
    TIMESCALE_USER: str = Field(default="collector_user")
    TIMESCALE_PASSWORD: str = Field(...)
    TIMESCALE_DB: str = Field(default="stockeasy_collector")
    
    @property
    def TIMESCALE_DATABASE_URL(self) -> str:
        return f"postgresql+psycopg2://{self.TIMESCALE_USER}:{self.TIMESCALE_PASSWORD}@{self.TIMESCALE_HOST}:{self.TIMESCALE_PORT}/{self.TIMESCALE_DB}"
```

## 📈 성능 최적화 방안

### 1. 배치 삽입
```python
async def bulk_insert_prices(self, prices: List[StockPriceCreate]):
    """대량 데이터 배치 삽입"""
    query = """
    INSERT INTO stock_prices (time, symbol, open, high, low, close, volume)
    VALUES (:time, :symbol, :open, :high, :low, :close, :volume)
    ON CONFLICT (time, symbol) DO UPDATE SET
        open = EXCLUDED.open,
        high = EXCLUDED.high,
        low = EXCLUDED.low,
        close = EXCLUDED.close,
        volume = EXCLUDED.volume
    """
    await self.session.execute(query, [p.dict() for p in prices])
```

### 2. 인덱스 최적화
```sql
-- 심볼별 시간 인덱스
CREATE INDEX idx_stock_prices_symbol_time ON stock_prices (symbol, time DESC);

-- 시간 범위 쿼리용 인덱스
CREATE INDEX idx_supply_demand_date_symbol ON supply_demand (date, symbol);
```

### 3. 캐싱 전략
- **실시간 데이터**: Redis (TTL 1분)
- **일간 데이터**: 메모리 캐시 (TTL 1시간)
- **과거 데이터**: DB 쿼리 (압축된 데이터)

## 🔍 모니터링 및 알림

### 성능 메트릭
- **압축률 모니터링**: 저장 공간 효율성
- **쿼리 성능**: 평균 응답 시간
- **연결 풀 상태**: PgBouncer 통계
- **메모리 사용량**: TimescaleDB 메모리 최적화

### 대시보드 구성
```python
async def get_timescale_stats():
    """TimescaleDB 성능 통계"""
    return {
        "chunk_count": await get_chunk_count(),
        "compression_ratio": await get_compression_stats(),
        "query_performance": await get_slow_queries(),
        "connection_stats": await get_pgbouncer_stats()
    }
```

## 🔒 보안 고려사항

### 접근 제어
- **네트워크 분리**: TimescaleDB는 내부 네트워크만 접근
- **사용자 권한**: 최소 권한 원칙
- **암호화**: 전송 중 데이터 암호화

### 백업 전략
- **Point-in-time Recovery**: 연속 백업
- **크로스 리전 백업**: 재해 복구
- **자동화된 복원 테스트**: 백업 유효성 검증

## 🚀 마이그레이션 전략

### 단계적 마이그레이션
1. **Phase 1**: TimescaleDB 환경 구축
2. **Phase 2**: 병렬 데이터 수집 (기존 + 새 구조)
3. **Phase 3**: 점진적 트래픽 이전
4. **Phase 4**: 기존 구조 정리

### 롤백 계획
- **데이터 동기화**: 이중 쓰기로 안전성 확보
- **즉시 롤백**: 기존 구조로 신속 복원
- **모니터링**: 성능 비교 및 이상 감지

## 📝 운영 가이드

### 일상 운영
- **로그 모니터링**: 오류 및 성능 이슈 추적
- **용량 관리**: 압축 정책 및 보관 주기
- **성능 튜닝**: 쿼리 최적화 및 인덱스 관리

### 장애 대응
- **연결 장애**: PgBouncer 재시작
- **메모리 부족**: 메모리 설정 조정
- **디스크 공간**: 압축 정책 강화

---

*문서 작성일: 2024년*  
*버전: 1.0*  
*작성자: AI Assistant* 