# 주식 데이터 수집 서비스 API

## 📋 개요

키움증권 REST API를 이용하여 주식 데이터를 수집하고 제공하는 통합 서비스입니다.
종목 리스트, 실시간 가격, ETF 구성종목, 차트 데이터 등을 제공합니다.

## 🚀 주요 기능

### 1. 자동 스케줄링
- **매일 아침 7시 30분** 자동으로 전체 종목 리스트 업데이트
- **매일 아침 8시** ETF 구성종목 업데이트
- APScheduler를 사용한 안정적인 스케줄링
- 서버 재시작 시에도 자동으로 스케줄 복원

### 2. 전체 종목 조회 (ka10099 API)
- 코스피, 코스닥, ETF, ELW 등 모든 시장의 종목 조회
- 연속조회 기능으로 전체 종목 완전 수집
- 시장별 분할 조회로 안정성 확보

### 3. 실시간 데이터 수집
- 실시간 주식 가격 데이터
- 종목별 기본 정보 조회
- 차트 데이터 제공 (일봉, 분봉 등)

### 4. ETF 데이터 관리
- ETF 목록 조회
- ETF 구성종목 및 비중 정보
- pykrx를 통한 정확한 데이터 수집

### 5. 캐시 기반 고성능 조회
- Redis 캐시를 통한 빠른 응답
- 24시간 TTL로 신선한 데이터 유지
- 메모리 효율적인 데이터 관리

## 🔧 구현된 시장 유형

| 코드 | 시장명 | 설명 |
|------|--------|------|
| 0 | 코스피 | KOSPI 시장 |
| 10 | 코스닥 | KOSDAQ 시장 |
| 8 | ETF | 상장지수펀드 |
| 3 | ELW | 주식워런트증권 |
| 30 | K-OTC | 코넥스 시장 |
| 50 | 코넥스 | 코넥스 시장 |
| 5 | 신주인수권 | 신주인수권 |
| 4 | 뮤추얼펀드 | 뮤추얼펀드 |
| 6 | 리츠 | 부동산투자신탁 |
| 9 | 하이일드 | 하이일드 펀드 |

## 📡 API 사용법

### 🏢 주식 데이터 API (`/api/v1/stock`)

#### 전체 종목 리스트 조회
```bash
GET /api/v1/stock/list
```

**응답 예시:**
```json
{
  "stocks": [
    {"code": "005930", "name": "삼성전자"},
    {"code": "000660", "name": "SK하이닉스"},
    {"code": "035420", "name": "NAVER"}
  ],
  "count": 3000,
  "status": "success"
}
```

#### 종목명 검색
```bash
GET /api/v1/stock/search?keyword=삼성&limit=10
```

**응답 예시:**
```json
{
  "keyword": "삼성",
  "stocks": [
    {"code": "005930", "name": "삼성전자"},
    {"code": "028260", "name": "삼성물산"}
  ],
  "count": 2,
  "status": "success"
}
```

#### 실시간 주식 가격 조회
```bash
GET /api/v1/stock/price/{symbol}
```

**응답 예시:**
```json
{
  "symbol": "005930",
  "data": {
    "current_price": 70000,
    "change": 1000,
    "change_rate": 1.45,
    "volume": 15000000,
    "timestamp": "2024-01-15T15:30:00"
  },
  "status": "success"
}
```

#### 종목 기본정보 조회
```bash
GET /api/v1/stock/info/{symbol}
```

**응답 예시:**
```json
{
  "symbol": "005930",
  "data": {
    "name": "삼성전자",
    "market": "KOSPI",
    "sector": "반도체",
    "market_cap": 420000000000000,
    "shares_outstanding": 6000000000,
    "floating_ratio": 85.5
  },
  "status": "success"
}
```

#### 차트 데이터 조회
```bash
GET /api/v1/stock/chart/{symbol}?period=1d&interval=1m
```

**파라미터:**
- `period`: 조회 기간 (1d, 5d, 1m, 3m, 6m, 1y, 2y, 5y, 10y, ytd, max)
- `interval`: 데이터 간격 (1m, 2m, 5m, 15m, 30m, 60m, 90m, 1h, 1d, 5d, 1wk, 1mo, 3mo)

**응답 예시:**
```json
{
  "symbol": "005930",
  "period": "1d",
  "interval": "1m",
  "data": [
    {
      "timestamp": "2024-01-15T09:00:00",
      "open": 69500,
      "high": 70200,
      "low": 69300,
      "close": 70000,
      "volume": 1500000
    }
  ],
  "status": "success"
}
```

#### 수동 종목 리스트 새로고침
```bash
POST /api/v1/stock/list/refresh
```

### 📊 ETF 데이터 API (`/api/v1/etf`)

#### ETF 목록 조회
```bash
GET /api/v1/etf/list
```

**응답 예시:**
```json
{
  "etfs": [
    {"code": "069500", "name": "KODEX 200"},
    {"code": "114800", "name": "KODEX 인버스"},
    {"code": "233740", "name": "KODEX 코스닥150"}
  ],
  "count": 300,
  "status": "success"
}
```

#### ETF 구성종목 조회
```bash
GET /api/v1/etf/components/{etf_code}
```

**응답 예시:**
```json
{
  "etf_code": "069500",
  "components": [
    {
      "code": "005930",
      "name": "삼성전자",
      "weight": 31.2,
      "shares": 15000000
    },
    {
      "code": "000660",
      "name": "SK하이닉스",
      "weight": 4.8,
      "shares": 2500000
    }
  ],
  "count": 200,
  "status": "success"
}
```

#### ETF 구성종목 갱신
```bash
POST /api/v1/etf/components/{etf_code}/refresh
```

#### 모든 ETF 구성종목 일괄 갱신
```bash
POST /api/v1/etf/components/refresh-all
```

**응답 예시:**
```json
{
  "message": "모든 ETF 구성종목 갱신 완료",
  "results": {
    "069500": 200,
    "114800": 150,
    "233740": 180
  },
  "total_etfs": 3,
  "total_components": 530,
  "status": "success"
}
```

### 📈 시장 데이터 API (`/api/v1/market`)

#### 시장 상태 조회
```bash
GET /api/v1/market/status
```

**응답 예시:**
```json
{
  "market_status": {
    "kospi": {
      "is_open": true,
      "session": "regular_trading",
      "next_session_time": "2024-01-15T15:30:00"
    },
    "kosdaq": {
      "is_open": true,
      "session": "regular_trading",
      "next_session_time": "2024-01-15T15:30:00"
    }
  },
  "status": "success"
}
```

#### 주요 지수 조회
```bash
GET /api/v1/market/indices
```

**응답 예시:**
```json
{
  "indices": {
    "KOSPI": {
      "value": 2580.15,
      "change": 15.2,
      "change_rate": 0.59
    },
    "KOSDAQ": {
      "value": 850.30,
      "change": -8.5,
      "change_rate": -0.99
    }
  },
  "status": "success"
}
```

## 🔧 관리자 기능 (`/api/v1/admin`)

### 스케줄러 관리

#### 스케줄러 시작
```bash
POST /api/v1/admin/scheduler/start
```

#### 스케줄러 중지
```bash
POST /api/v1/admin/scheduler/stop
```

#### 스케줄러 상태 조회
```bash
GET /api/v1/admin/scheduler/stats
```

**응답 예시:**
```json
{
  "scheduler_stats": {
    "is_running": true,
    "total_jobs": 4,
    "pending_jobs": 2,
    "next_run_time": "2024-01-16T07:30:00"
  },
  "status": "success"
}
```

#### 즉시 종목 리스트 업데이트 실행
```bash
POST /api/v1/admin/scheduler/trigger/stocks
```

#### 즉시 ETF 구성종목 업데이트 실행
```bash
POST /api/v1/admin/scheduler/trigger/etf
```

### 실시간 데이터 수집 관리

#### 실시간 데이터 수집 시작
```bash
POST /api/v1/admin/start-collection
```

#### 실시간 데이터 수집 중지
```bash
POST /api/v1/admin/stop-collection
```

### 통계 및 모니터링

#### 전체 수집 통계
```bash
GET /api/v1/admin/stats
```

**응답 예시:**
```json
{
  "stats": {
    "total_stocks": 3000,
    "total_etfs": 300,
    "api_calls_today": 15000,
    "cache_hit_rate": 85.2,
    "uptime": "2 days, 15:30:22"
  },
  "status": "success"
}
```

#### 키움 API 통계
```bash
GET /api/v1/admin/kiwoom/stats
```

#### ETF 크롤러 통계
```bash
GET /api/v1/admin/etf/stats
```

### 데이터 관리

#### 종목 코드-이름 매핑 업데이트
```bash
POST /api/v1/admin/update-symbols
```

#### 캐시 강제 갱신
```bash
POST /api/v1/admin/cache/refresh
```

## 📊 스케줄 목록

| 작업명 | 실행 시간 | 설명 |
|--------|-----------|------|
| 일일 종목 리스트 업데이트 | 매일 07:30 | 전체 종목 리스트 갱신 |
| 일일 ETF 구성종목 업데이트 | 매일 08:00 | ETF 구성종목 정보 갱신 |
| 시간별 캐시 정리 | 매시간 정각 | 만료된 캐시 정리 |
| 주간 전체 캐시 새로고침 | 토요일 18:00 | 전체 캐시 강제 갱신 |

## 🛠️ 기술 스택

- **FastAPI**: REST API 서버
- **APScheduler**: 스케줄링 엔진
- **Redis**: 캐시 저장소
- **aiohttp**: 비동기 HTTP 클라이언트
- **Pydantic**: 데이터 검증
- **pykrx**: 한국 주식 데이터 수집
- **SQLAlchemy**: ORM (데이터베이스 연동)

## 🔐 환경 변수

```env
# 키움 API 설정
KIWOOM_API_KEY=your_api_key
KIWOOM_SECRET=your_secret_key
KIWOOM_APP_KEY=your_app_key

# API 호출 제한
MAX_API_CALLS_PER_SECOND=10
MAX_API_CALLS_PER_MINUTE=600
MAX_API_CALLS_PER_HOUR=10000

# 캐시 설정
CACHE_TTL_REALTIME=60
CACHE_TTL_DAILY=3600
CACHE_TTL_ETF=86400

# Redis 설정
REDIS_URL=redis://redis:6379/0

# 데이터베이스 설정
DATABASE_URL=postgresql://user:password@postgres:5432/stockeasy
```

## 📈 성능 최적화

### API 호출 제한 관리
- 초당 최대 10회 호출 제한
- 비동기 세마포어로 동시성 제어
- 연속조회 간 적절한 지연 시간 설정

### 캐시 전략
- 24시간 TTL로 일일 업데이트 보장
- 메모리 효율적인 JSON 직렬화
- 네임스페이스 분리로 관리 용이성 확보

### 오류 처리
- 시장별 독립적인 오류 처리
- 부분 실패 시에도 수집 가능한 데이터 보존
- 상세한 로깅으로 디버깅 지원

## 🔍 모니터링

### 로그 확인
```bash
# 컨테이너 로그 조회
docker logs stock-data-collector

# 스케줄러 작업 로그 확인
grep "스케줄 작업" /backend/logs/collector.log
```

### 통계 조회
```bash
# 전체 수집 통계
GET /api/v1/admin/stats

# 키움 API 통계
GET /api/v1/admin/kiwoom/stats

# 스케줄러 통계
GET /api/v1/admin/scheduler/stats
```

## 🚨 주의사항

1. **API 키 보안**: 키움 API 키는 환경 변수로 안전하게 관리
2. **호출 제한**: 키움 API 호출 제한을 준수하여 계정 제재 방지
3. **네트워크 안정성**: 장시간 네트워크 연결 유지 필요
4. **Redis 메모리**: 전체 종목 데이터로 인한 Redis 메모리 사용량 모니터링
5. **실시간 수집**: 실시간 데이터 수집 시 시스템 리소스 모니터링 필요

## 🔧 문제 해결

### 종목 리스트가 업데이트되지 않는 경우
1. 스케줄러 상태 확인: `GET /api/v1/admin/scheduler/stats`
2. 키움 API 연결 상태 확인: `GET /api/v1/admin/kiwoom/stats`
3. 수동 업데이트 실행: `POST /api/v1/admin/scheduler/trigger/stocks`

### API 호출 실패 시
1. API 키 유효성 확인
2. 네트워크 연결 상태 확인
3. 호출 제한 초과 여부 확인

### ETF 구성종목 업데이트 실패 시
1. pykrx 라이브러리 상태 확인
2. 네트워크 연결 상태 확인
3. 수동 갱신 실행: `POST /api/v1/etf/components/refresh-all`

## 📚 개발 참고사항

### 키움 API 문서
- API ID: ka10099 (주식기본정보조회)
- 연속조회 지원: cont-yn, next-key 헤더 사용
- 시장구분 코드: mrkt_tp 파라미터

### 확장 가능성
- 다른 증권사 API 추가 지원
- 실시간 종목 정보 업데이트
- 종목별 상세 정보 수집
- 히스토리 데이터 관리
- 뉴스 및 공시 정보 수집

### API 버전 관리
- 현재 버전: v1
- API 버전별 하위 호환성 보장
- 새로운 기능은 신규 버전에서 제공

---

**작성일**: 2024년  
**버전**: 1.0.0  
**담당**: Backend Development Team 