# 기술적 분석 에이전트 추가 명세서

## 1. 개요

### 1.1 목적
기존의 멀티 에이전트 시스템에 기술적 분석 기능을 추가하여 종합적인 주식 분석 서비스를 제공합니다. 기본적 분석(펀더멘털), 재무 분석과 함께 기술적 분석을 통해 보다 완성도 높은 투자 의사결정 지원 정보를 제공합니다.

### 1.2 범위
- 기술적 분석 에이전트 신규 개발
- 기존 멀티 에이전트 시스템과의 통합
- stock-data-collector 컨테이너와의 REST API 연동
- 질문 분석 및 오케스트레이터 로직 확장

## 2. 시스템 아키텍처

### 2.1 전체 구조
```
사용자 질문 → Question Analyzer → Orchestrator → Parallel Search Agent
                     ↓                    ↓              ↓
            기술적분석 필요성 판단    실행계획 수립    기술적분석 에이전트 실행
                                                           ↓
                                                stock-data-collector
                                                  (REST API 호출)
```

### 2.2 컴포넌트 관계도
- **Question Analyzer**: 질문 패턴 분석 및 기술적 분석 필요성 판단
- **Orchestrator**: 기술적 분석 에이전트 포함 실행 계획 수립
- **Parallel Search Agent**: 기술적 분석 에이전트 병렬 실행
- **Technical Analysis Agent**: 기술적 분석 수행 (신규)
- **stock-data-collector**: 주가 및 시장 데이터 제공

## 3. 기능 명세

### 3.1 Question Analyzer 확장

#### 3.1.1 질문 패턴 분석
- 기술적 분석 관련 키워드 감지
  - 차트 패턴: "차트", "패턴", "지지선", "저항선", "삼각형", "머리어깨" 등
  - 기술적 지표: "RS(상대강도)", "RSI", "MACD", "볼린저밴드", "이동평균선", "스토캐스틱" 등
  - 매매 신호: "매수신호", "매도신호", "골든크로스", "데드크로스" 등
  - 가격 움직임: "추세", "상승세", "하락세", "횡보", "돌파" 등

#### 3.1.2 DataRequirements 모델 확장
```python
class DataRequirements(BaseModel):
    # 기존 필드들...
    technical_analysis_needed: bool = Field(False, description="기술적 분석 데이터 필요 여부")
```

#### 3.1.3 목차 생성 로직 확장
- 기술적 분석이 필요한 경우 동적 목차에 기술적 분석 섹션 추가
- 섹션 예시:
  - "기술적 분석"
  - "차트 패턴 분석"
  - "기술적 지표 분석"
  - "매매 신호 분석"

### 3.2 Orchestrator 확장

#### 3.2.1 실행 계획 수정
- `data_requirements.technical_analysis_needed` 확인
- 기술적 분석 에이전트를 실행 순서에 포함
- 우선순위 설정 (일반적으로 다른 분석 에이전트와 동일한 레벨)

#### 3.2.2 에이전트 설정 추가
```python
available_agents = {
    # 기존 에이전트들...
    "technical_analyzer": "기술적 분석 에이전트"
}
```

### 3.3 Parallel Search Agent 확장

#### 3.3.1 에이전트 목록 추가
```python
search_agent_names = [
    # 기존 에이전트들...
    "technical_analyzer"
]
```

#### 3.3.2 실행 조건 추가
- `data_requirements.technical_analysis_needed` 확인하여 실행 여부 결정

### 3.4 Agent Registry 확장

#### 3.4.1 에이전트 클래스 등록
```python
agent_classes = {
    # 기존 에이전트들...
    "technical_analyzer": TechnicalAnalyzerAgent
}
```

### 3.5 Stock Analysis Graph 확장

#### 3.5.1 노드 추가
- 기술적 분석 에이전트를 그래프 노드로 추가
- 병렬 검색 프로세스에 포함

## 4. Technical Analysis Agent 상세 명세

### 4.1 주요 기능
1. **차트 패턴 분석**
   - 지지선/저항선 식별
   - 추세선 분석
   - 차트 패턴 인식 (삼각형, 머리어깨, 컵앤핸들 등)

2. **기술적 지표 계산 및 분석**
   - 이동평균선 (SMA, EMA)
   - RS (상대강도, 지수대비)
   - MACD
   - 볼린저 밴드

3. **매매 신호 생성**
   - 골든크로스/데드크로스
   - 지표 기반 과매수/과매도 신호
   - 돌파 신호

4. **시장 정서 분석**
   - 거래량 분석

5. **수급 분석**
   - 수급 데이터 분석

### 4.2 데이터 요청 명세

#### 4.2.1 REST API 엔드포인트
- 베이스 URL: `http://stock-data-collector:8001`
- 주요 엔드포인트:
  - `/api/v1/stock-price/{stock_code}`: 주가 데이터
  - `/api/v1/supply-demand/{stock_code}`: 수급 데이터
  - `/api/v1/market-index`: 시장지수 데이터

#### 4.2.2 데이터 형식
```python
# 주가 데이터 요청 예시
{
    "stock_code": "005930",
    "period": "1y",  # 1d, 1w, 1m, 3m, 6m, 1y
    "interval": "1d"  # 1m, 5m, 15m, 30m, 1h, 1d
}

# 응답 형식
{
    "stock_code": "005930",
    "data": [
        {
            "date": "2024-01-01",
            "open": 71000,
            "high": 72000,
            "low": 70000,
            "close": 71500,
            "volume": 1000000,
            "adj_close": 71500
        }
    ]
}
```

### 4.3 분석 결과 형식

#### 4.3.1 기술적 분석 결과 구조
```python
{
    "technical_analysis": {
        "chart_patterns": {
            "support_levels": [70000, 68000],
            "resistance_levels": [75000, 77000],
            "trend_direction": "상승",
            "patterns": ["상승삼각형"]
        },
        "technical_indicators": {
            "rsi": {"value": 65.5, "signal": "중립"},
            "macd": {"value": 1.2, "signal": "매수"},
            "bollinger_bands": {
                "upper": 75000,
                "middle": 72000,
                "lower": 69000,
                "position": "중간대"
            }
        },
        "trading_signals": {
            "overall_signal": "매수",
            "confidence": 0.75,
            "signals": [
                {"indicator": "MACD", "signal": "매수", "strength": 0.8},
                {"indicator": "RSI", "signal": "중립", "strength": 0.5}
            ]
        },
        "market_sentiment": {
            "volume_trend": "증가",
            "price_volume_relation": "긍정적"
        }
    }
}
```

## 5. 통합 및 데이터 흐름

### 5.1 데이터 흐름도
```
1. 사용자 질문 입력
2. Question Analyzer에서 기술적 분석 필요성 판단
3. Orchestrator에서 실행 계획 수립
4. Parallel Search Agent에서 기술적 분석 에이전트 실행
5. Technical Analysis Agent에서 stock-data-collector API 호출
6. 기술적 분석 수행 및 결과 반환
7. Knowledge Integrator에서 다른 분석 결과와 통합
8. 최종 응답 생성
```

### 5.2 에러 처리
- stock-data-collector API 호출 실패 시 graceful degradation
- 데이터 부족 시 제한된 분석 결과 제공
- 타임아웃 설정 및 재시도 로직

## 6. 성능 및 제약사항

### 6.1 성능 요구사항
- API 호출 응답시간: 5초 이내
- 전체 분석 완료시간: 30초 이내
- 동시 처리 가능한 요청 수: 10개

### 6.2 제약사항
- stock-data-collector 서비스 의존성
- 실시간 데이터의 지연 가능성
- 기술적 분석의 주관적 해석 한계

## 7. 보안 및 고려사항

### 7.1 보안
- 내부 네트워크 통신 (컨테이너 간)
- API 호출 시 적절한 타임아웃 설정

### 7.2 확장성
- 새로운 기술적 지표 추가 용이성
- 분석 알고리즘 개선 가능성
- 실시간 분석 기능 추가 가능성

## 8. 테스트 계획

### 8.1 단위 테스트
- 각 기술적 지표 계산 로직
- API 호출 및 데이터 파싱
- 에러 처리 로직

### 8.2 통합 테스트
- 전체 워크플로우 테스트
- 다른 에이전트와의 연동 테스트
- stock-data-collector와의 API 연동 테스트

### 8.3 성능 테스트
- 응답시간 측정
- 동시 요청 처리 테스트
- 메모리 사용량 모니터링 