# 기술적 분석 에이전트 API 가이드

## 📋 개요

기술적 분석 에이전트는 주식의 기술적 지표, 차트 패턴, 매매 신호를 분석하여 투자자에게 도움이 되는 정보를 제공합니다.

## 🔧 사용법

### 기본 사용법

기술적 분석 에이전트는 다음과 같은 키워드를 포함한 질문에 자동으로 활성화됩니다:

#### 기술적 지표 관련 키워드
- `RSI`, `상대강도`, `MACD`, `볼린저밴드`, `볼린저`, `이동평균`, `이동평균선`
- `스토캐스틱`, `기술적지표`, `기술적 지표`, `지표분석`, `지표 분석`

#### 차트 패턴 관련 키워드  
- `차트`, `패턴`, `지지선`, `지지`, `저항선`, `저항`, `추세`, `상승세`, `하락세`
- `횡보`, `돌파`, `삼각형`, `머리어깨`, `컵앤핸들`

#### 매매 신호 관련 키워드
- `매수신호`, `매수 신호`, `매도신호`, `매도 신호`, `골든크로스`, `데드크로스`
- `매매신호`, `매매 신호`, `투자신호`, `투자 신호`

### 질문 예시

```
"삼성전자의 RSI와 MACD를 분석해주세요"
"SK하이닉스의 차트 패턴과 지지선을 알려주세요"  
"NAVER의 기술적 지표 기반 매매 신호를 분석해주세요"
"현대차의 볼린저밴드와 이동평균선 분석 부탁드립니다"
```

## 📊 분석 결과 형식

### TechnicalAnalysisResult 구조

```python
{
    "stock_code": "005930",
    "stock_name": "삼성전자",
    "analysis_date": "2024-01-01T12:00:00",
    "current_price": 71500.0,
    "chart_patterns": {
        "support_levels": [70000, 68000],
        "resistance_levels": [75000, 77000],
        "trend_direction": "상승",
        "trend_strength": "보통",
        "patterns": ["상승삼각형"],
        "breakout_signals": [
            {
                "type": "저항선_돌파",
                "level": 75000,
                "current_price": 76000,
                "volume_confirmation": true
            }
        ]
    },
    "technical_indicators": {
        "sma_20": 72000.0,
        "sma_60": 70000.0,
        "ema_12": 71800.0,
        "ema_26": 71200.0,
        "rsi": 65.5,
        "macd": 1.2,
        "macd_signal": 1.0,
        "macd_histogram": 0.2,
        "bollinger_upper": 75000.0,
        "bollinger_middle": 72000.0,
        "bollinger_lower": 69000.0,
        "stochastic_k": 70.0,
        "stochastic_d": 68.0
    },
    "trading_signals": {
        "overall_signal": "매수",
        "confidence": 0.75,
        "signals": [
            {
                "indicator": "MACD",
                "signal": "매수",
                "strength": 0.8,
                "value": 1.2,
                "reason": "상승교차"
            },
            {
                "indicator": "RSI",
                "signal": "중립",
                "strength": 0.3,
                "value": 65.5,
                "reason": "중립"
            }
        ],
        "entry_points": [71500],
        "exit_points": [],
        "stop_loss": 67925.0,
        "target_price": 78650.0
    },
    "market_sentiment": {
        "volume_trend": "증가",
        "price_volume_relation": "긍정적",
        "foreign_flow": null,
        "institution_flow": null
    },
    "summary": "현재 삼성전자는 MACD 상승교차와 함께 상승삼각형 패턴을 형성하고 있어 긍정적인 기술적 신호를 보이고 있습니다...",
    "recommendations": [
        "강력한 매수 신호가 확인되었습니다.",
        "분할 매수/매도를 통해 리스크를 관리하세요.",
        "손절선을 미리 설정하고 감정적 거래를 피하세요."
    ]
}
```

## 📈 기술적 지표 설명

### RSI (Relative Strength Index)
- **범위**: 0-100
- **해석**: 
  - 70 이상: 과매수 (매도 신호)
  - 30 이하: 과매도 (매수 신호)
  - 30-70: 중립

### MACD (Moving Average Convergence Divergence)
- **구성**: MACD Line, Signal Line, Histogram
- **해석**:
  - MACD > Signal: 상승 추세
  - MACD < Signal: 하락 추세
  - 골든크로스/데드크로스: 추세 전환 신호

### 볼린저 밴드 (Bollinger Bands)
- **구성**: 상단선, 중간선(20일 이평), 하단선
- **해석**:
  - 상단선 근처: 과매수 구간
  - 하단선 근처: 과매도 구간
  - 밴드 확장/수축: 변동성 변화

### 이동평균선 (Moving Average)
- **SMA**: 단순이동평균
- **EMA**: 지수이동평균
- **해석**:
  - 주가 > 이평선: 상승 추세
  - 주가 < 이평선: 하락 추세
  - 골든크로스(단기>장기): 매수 신호

## 🎯 매매 신호 해석

### 종합 신호 유형
- **강력매수**: 여러 지표가 강한 매수 신호
- **매수**: 일반적인 매수 신호
- **중립**: 뚜렷한 방향성 없음
- **매도**: 일반적인 매도 신호
- **강력매도**: 여러 지표가 강한 매도 신호

### 신뢰도 수준
- **0.8 이상**: 높은 신뢰도
- **0.6-0.8**: 중간 신뢰도
- **0.6 미만**: 낮은 신뢰도

## 🔄 데이터 수집 소스

기술적 분석 에이전트는 다음 API를 통해 데이터를 수집합니다:

### stock-data-collector API 엔드포인트

1. **주가 데이터**: `/api/v1/stock/chart/{stock_code}`
   - 1년간 일봉 데이터 수집
   - OHLCV (시가, 고가, 저가, 종가, 거래량) 정보

2. **수급 데이터**: `/api/v1/stock/supply-demand/{stock_code}`
   - 30일간 수급 데이터 수집
   - 외국인, 기관 매매 동향

3. **시장지수**: `/api/v1/market/indices`
   - 코스피, 코스닥 등 주요 지수
   - 시장 전반 상황 파악

## ⚠️ 주의사항

### 데이터 제한
- 실시간 데이터가 아닌 일정 시간 지연된 데이터 사용
- stock-data-collector 서비스 의존성
- 분석 결과는 참고용이며 투자 결정의 유일한 근거가 되어서는 안됨

### 리스크 요인
- 기술적 분석의 한계성 (과거 데이터 기반)
- 급변하는 시장 상황에서의 지표 실효성
- 다른 분석 방법과의 종합적 검토 필요

## 🛠️ 에러 처리

### 일반적인 오류 상황
1. **종목코드 누락**: "종목코드가 필요합니다"
2. **API 연결 실패**: "주가 데이터를 가져올 수 없습니다"
3. **데이터 부족**: 제한된 분석 결과 제공
4. **계산 오류**: 기본값으로 대체하여 분석 계속

### Graceful Degradation
- API 호출 실패 시에도 기본적인 분석 제공
- 일부 지표 계산 실패 시 나머지 지표로 분석
- 타임아웃 발생 시 부분 결과 반환

## 🔧 개발자 가이드

### 에이전트 확장 방법

1. **새로운 기술적 지표 추가**:
   ```python
   def _calculate_new_indicator(self, df: pd.DataFrame) -> float:
       # 새로운 지표 계산 로직
       return calculated_value
   ```

2. **차트 패턴 인식 추가**:
   ```python
   def _identify_new_pattern(self, df: pd.DataFrame) -> List[str]:
       # 새로운 패턴 인식 로직
       return detected_patterns
   ```

3. **매매 신호 로직 개선**:
   ```python
   def _generate_enhanced_signals(self, indicators: dict) -> dict:
       # 개선된 신호 생성 로직
       return trading_signals
   ```

### 테스트 방법

1. **단위 테스트**: 개별 지표 계산 함수 검증
2. **통합 테스트**: 전체 분석 워크플로우 검증
3. **성능 테스트**: 응답 시간 및 메모리 사용량 측정

## 📞 문의 및 지원

기술적 분석 에이전트 관련 문의사항이나 개선 요청은 개발팀에 문의하시기 바랍니다.

---

*이 문서는 기술적 분석 에이전트의 효과적인 활용을 위한 가이드입니다. 실제 투자 시에는 다양한 분석 방법을 종합적으로 고려하시기 바랍니다.* 