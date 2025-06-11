# 증권사 REST API 데이터 수집 시스템 설계

## 📋 목표 및 배경

### 목표
증권사의 REST API를 이용한 데이터 수집 및 백엔드/프론트엔드에 데이터 제공

### 배경
- FastAPI에 구현하기에는 다수의 worker가 구동되는 환경이라, 클래스 중복 생성됨(낭비)
- 주식종목의 데이터는 중복생성해서 저장할 이유가 없음
- Docker 내에서 컨테이너를 새로 생성하고, 그 컨테이너에서 FastAPI로 정보를 제공하는 형태(데이터 제어 단일화)
- 이 컨테이너는 FastAPI/Celery worker/프론트엔드 등 모든 요청에 응답할 수 있어야 함

## 🔍 주요 고려사항

### 데이터 저장 전략
- **수급데이터**(기관 순매수, 외국인 순매수 정보): DB에 저장
- **ETF 구성종목**: 키움 REST API 제공하지 않음. 네이버 크롤링 필요
- **차트 데이터**: 수정주가 발생 시 처리 방안 필요

## 🏗️ 시스템 아키텍처

### 1. 독립적인 데이터 수집 서비스 구축

#### 장점
- 단일 인스턴스로 API 호출 제한 관리 용이
- 메모리 효율적인 데이터 캐싱
- 실시간 데이터 스트리밍 가능

#### 고려사항
- gRPC 또는 WebSocket을 통한 내부 통신
- Redis Pub/Sub을 통한 실시간 데이터 브로드캐스팅
- 메시지 큐(RabbitMQ/Kafka) 도입 검토

### 2. 계층적 데이터 저장 구조

#### Hot Data (Redis/메모리)
- 실시간 호가/체결 데이터
- 최근 N분간의 차트 데이터
- 당일 수급 데이터

#### Warm Data (PostgreSQL)
- 일간/주간/월간 차트 데이터
- 과거 수급 데이터
- ETF 구성종목 변경 이력

#### Cold Data (S3/파일시스템)
- 장기 보관용 차트 데이터
- 백업 데이터

### 3. API 호출 제한 관리

```python
# Rate Limiting 전략
- Token Bucket 알고리즘 구현
- API별 호출 제한 관리
- 우선순위 기반 요청 큐잉
- 장애 시 Circuit Breaker 패턴
```

## 📊 데이터 정합성 및 품질 관리

### 수정주가 처리 방안
1. 원본 데이터와 수정 계수 분리 저장
2. 수정주가 이벤트 로깅
3. 실시간 재계산 vs 배치 재계산 선택
4. 변경 이력 추적 시스템

### 데이터 검증
- 거래정지/상폐 종목 처리
- 비정상 데이터 필터링
- 결측치 처리 전략
- 데이터 소스 간 교차 검증

## 🚀 확장성 고려사항

### 멀티 브로커 지원
- 추상화 레이어 구축
- 브로커별 어댑터 패턴
- 통합 데이터 모델 설계
- 브로커 장애 시 자동 전환

### 성능 최적화

#### 배치 처리
- 종목 그룹별 일괄 조회
- 시간대별 우선순위 조정

#### 캐싱 전략
- TTL 기반 캐시 무효화
- 이벤트 기반 캐시 갱신
- 계층적 캐싱 (L1: 메모리, L2: Redis)

#### 비동기 처리
- 실시간 데이터와 배치 데이터 분리
- 백그라운드 작업 큐

## 📈 모니터링 및 알림

- API 호출 횟수/성공률 추적
- 데이터 지연 시간 모니터링
- 이상 데이터 탐지
- Prometheus + Grafana 대시보드
- 장애 발생 시 Slack/이메일 알림

## 🔒 보안 고려사항

- API 키 안전한 관리 (Vault 등)
- 내부 통신 암호화
- 접근 제어 및 인증
- 감사 로그

## 💻 구현 제안

### 1. Docker 컨테이너 구성

#### 방안 1: 기존 구조와 일관성 유지 (권장)
```yaml
services:
  stock-data-collector:
    build: 
      context: .
      dockerfile: Dockerfile.stockeasy.collector.dev
    ports:
      - "8001:8001"  # gRPC
      - "8002:8002"  # WebSocket
    environment:
      - BROKER_API_KEY=${KIWOOM_API_KEY}
      - MAX_API_CALLS_PER_SECOND=10
      - PYTHONPATH=/backend
    depends_on:
      - redis
      - postgres
    volumes:
      - ./backend:/backend  # 기존 구조와 일관성 유지
    working_dir: /backend/stockeasy/collector
    command: ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]
    deploy:
      replicas: 1  # 단일 인스턴스 보장
```

#### 방안 2: 독립적인 구조 (선택사항)
```yaml
services:
  stock-data-collector:
    build: ./backend/stockeasy/collector
    ports:
      - "8001:8001"  # gRPC
      - "8002:8002"  # WebSocket
    environment:
      - BROKER_API_KEY=${KIWOOM_API_KEY}
      - MAX_API_CALLS_PER_SECOND=10
    depends_on:
      - redis
      - postgres
    volumes:
      - ./backend/stockeasy:/app
      - ./backend/common:/app/common  # 공통 모듈 접근
    deploy:
      replicas: 1  # 단일 인스턴스 보장
```

#### 방안 3: 하이브리드 접근 (최적화)
```yaml
services:
  stock-data-collector:
    build: 
      context: .
      dockerfile: Dockerfile.stockeasy.collector.dev
    ports:
      - "8001:8001"
      - "8002:8002"
    environment:
      - BROKER_API_KEY=${KIWOOM_API_KEY}
      - MAX_API_CALLS_PER_SECOND=10
    depends_on:
      - redis
      - postgres
    volumes:
      - ./backend:/backend:ro  # 읽기 전용으로 전체 마운트
      - collector_data:/app/data  # 수집 데이터용 별도 볼륨
    working_dir: /backend/stockeasy/collector
    deploy:
      replicas: 1
```

### 2. 데이터 모델 설계

#### 실시간 데이터 (Redis)
```json
{
    "stock:005930:realtime": {
        "price": 71000,
        "volume": 1234567,
        "timestamp": "2024-01-01T09:00:00",
        "ttl": 300
    }
}
```

#### 차트 데이터 (PostgreSQL)
```python
class StockPrice(Base):
    __tablename__ = "stock_prices"
    
    id = Column(Integer, primary_key=True)
    symbol = Column(String, index=True)
    date = Column(Date, index=True)
    open = Column(Numeric)
    high = Column(Numeric)
    low = Column(Numeric)
    close = Column(Numeric)
    volume = Column(BigInteger)
    adj_factor = Column(Numeric, default=1.0)  # 수정계수
    
    __table_args__ = (
        UniqueConstraint('symbol', 'date', name='uq_symbol_date'),
        Index('idx_symbol_date', 'symbol', 'date'),
    )
```

### 3. ETF 구성종목 크롤링

```python
# Celery 태스크로 구현
@celery_app.task
def update_etf_components():
    """매일 정해진 시간에 ETF 구성종목 업데이트"""
    etf_list = ["KODEX 200", "TIGER 200", ...]
    for etf in etf_list:
        components = crawl_naver_etf(etf)
        save_to_db(components)
        invalidate_cache(f"etf:{etf}")
```

### 4. 통신 프로토콜

```python
# gRPC 서비스 정의
service StockDataService {
    rpc GetRealtimePrice(StockRequest) returns (PriceResponse);
    rpc SubscribePriceStream(StockRequest) returns (stream PriceUpdate);
    rpc GetHistoricalData(HistoricalRequest) returns (HistoricalResponse);
}
```

## 🎯 단계별 구현 계획

### Phase 1: 기본 인프라 구축
- 독립 컨테이너 설정
- Redis/PostgreSQL 연동
- 기본 API 래퍼 구현

### Phase 2: 실시간 데이터 수집
- WebSocket 서버 구현
- 실시간 데이터 스트리밍
- 캐싱 레이어 구축

### Phase 3: 배치 데이터 처리
- 일간 데이터 수집
- ETF 크롤링
- 수정주가 처리

### Phase 4: 최적화 및 모니터링
- 성능 튜닝
- 모니터링 대시보드
- 알림 시스템

## 📝 추가 검토 사항

### 기술적 결정 필요
1. **메시지 큐 선택**: Redis Pub/Sub vs RabbitMQ vs Apache Kafka
2. **통신 프로토콜**: gRPC vs WebSocket vs HTTP/2
3. **캐싱 전략**: 메모리 vs Redis vs 하이브리드
4. **데이터 압축**: 저장 공간 최적화 방안

### 비즈니스 로직 고려
1. **거래 시간 처리**: 장 시작/종료 시간, 휴일 처리
2. **종목 관리**: 신규 상장/상폐 종목 자동 감지
3. **데이터 품질**: 이상치 탐지 및 보정 알고리즘
4. **백업 전략**: 데이터 손실 방지 및 복구 계획

### 운영 고려사항
1. **로그 관리**: 구조화된 로깅 및 로그 레벨 관리
2. **배포 전략**: 무중단 배포 및 롤백 계획
3. **스케일링**: 수평/수직 확장 전략
4. **비용 최적화**: 클라우드 리소스 사용량 모니터링

---

*문서 작성일: 2024년*  
*최종 수정일: 2024년* 