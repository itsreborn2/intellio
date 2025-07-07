"""
기술적 분석 에이전트 프롬프트 템플릿

이 모듈은 기술적 분석 결과를 해석하고 매매 신호를 설명하기 위해
기술적 분석 에이전트에서 사용하는 프롬프트 템플릿을 정의합니다.
"""

# 기술적 분석 결과 해석 프롬프트
TECHNICAL_ANALYSIS_INTERPRETATION_PROMPT = """
당신은 전문 기술적 분석가입니다. 다음 기술적 분석 결과를 바탕으로 현재 {stock_name}의 기술적 상황을 종합적으로 해석해주세요.

기술적 지표:
- RSI: {rsi}
- MACD: {macd}
- MACD Signal: {macd_signal}
- 볼린저 밴드 상단: {bollinger_upper}
- 볼린저 밴드 하단: {bollinger_lower}
- 20일 이동평균: {sma_20}
- 60일 이동평균: {sma_60}

차트 패턴 분석:
- 추세 방향: {trend_direction}
- 추세 강도: {trend_strength}
- 주요 패턴: {patterns}

매매 신호:
- 종합 신호: {overall_signal}
- 신뢰도: {confidence}%

다음 사항을 포함하여 3-5문장으로 현재 기술적 상황을 종합 해석해주세요:
1. 현재 기술적 상태 (과매수/과매도, 추세 상황)
2. 주요 기술적 지표들의 신호 일치성
3. 투자자에게 주는 시사점
4. 주의해야 할 리스크 요인

한국 주식 시장 맥락에서 실무적이고 구체적인 해석을 제공해주세요.
"""

# 매매 신호 설명 프롬프트
TRADING_SIGNALS_EXPLANATION_PROMPT = """
당신은 개인 투자자를 위한 기술적 분석 전문가입니다. 다음 매매 신호 분석 결과를 일반 투자자가 이해하기 쉽게 설명해주세요.

종목: {stock_name}
현재가: {current_price:,}원

매매 신호 분석:
- 종합 신호: {overall_signal}
- 신뢰도: {confidence}%
- 개별 신호들: {individual_signals}

{price_targets}

다음을 포함하여 명확하고 실용적인 설명을 제공해주세요:
1. 현재 매매 신호의 의미와 근거
2. 신뢰도 수준에 대한 해석
3. 구체적인 투자 전략 제안
4. 리스크 관리 방안

전문 용어는 쉽게 풀어서 설명하고, 실제 투자 의사결정에 도움이 되는 조언을 제공해주세요.
"""

# 기술적 지표 상세 설명 프롬프트
TECHNICAL_INDICATORS_DETAIL_PROMPT = """
당신은 기술적 분석 교육 전문가입니다. {stock_name}의 현재 기술적 지표들을 분석하여 각 지표의 의미와 투자 시사점을 설명해주세요.

현재 기술적 지표:
{technical_indicators}

각 지표에 대해 다음을 설명해주세요:
1. 현재 수치의 의미 (정상/과매수/과매도 등)
2. 다른 지표들과의 상호 관계
3. 단기/중기 투자 관점에서의 시사점
4. 해당 지표 기반 매매 타이밍 제안

초보자도 이해할 수 있도록 쉽고 명확하게 설명하되, 정확한 분석을 제공해주세요.
"""

# 차트 패턴 분석 프롬프트
CHART_PATTERN_ANALYSIS_PROMPT = """
당신은 차트 패턴 분석 전문가입니다. {stock_name}에서 발견된 차트 패턴을 분석하여 향후 주가 움직임에 대한 통찰을 제공해주세요.

차트 패턴 정보:
- 지지선: {support_levels}
- 저항선: {resistance_levels}
- 감지된 패턴: {detected_patterns}
- 돌파 신호: {breakout_signals}

다음을 포함하여 패턴 분석을 제공해주세요:
1. 발견된 패턴의 의미와 일반적인 특징
2. 현재 주가 위치의 기술적 의미
3. 주요 지지/저항 수준과 돌파 시나리오
4. 패턴 완성 시 예상 목표가 또는 조정폭
5. 패턴 실패 시 대응 방안

실제 매매에 활용할 수 있는 구체적이고 실무적인 분석을 제공해주세요.
"""

def format_technical_analysis_prompt(template: str, **kwargs) -> str:
    """
    기술적 분석 프롬프트를 포맷팅합니다.
    
    Args:
        template: 프롬프트 템플릿
        **kwargs: 템플릿에 삽입할 변수들
        
    Returns:
        포맷팅된 프롬프트 문자열
    """
    try:
        return template.format(**kwargs)
    except KeyError as e:
        # 누락된 변수가 있는 경우 기본값으로 대체
        default_kwargs = {
            'stock_name': '분석 종목',
            'current_price': 0,
            'rsi': 'N/A',
            'macd': 'N/A',
            'macd_signal': 'N/A',
            'bollinger_upper': 'N/A',
            'bollinger_lower': 'N/A',
            'sma_20': 'N/A',
            'sma_60': 'N/A',
            'trend_direction': '불명확',
            'trend_strength': '약함',
            'patterns': '감지된 패턴 없음',
            'overall_signal': '중립',
            'confidence': 0,
            'individual_signals': '신호 없음',
            'price_targets': '',
            'technical_indicators': '지표 정보 없음',
            'support_levels': [],
            'resistance_levels': [],
            'detected_patterns': [],
            'breakout_signals': []
        }
        default_kwargs.update(kwargs)
        return template.format(**default_kwargs)

def create_price_targets_text(stop_loss: float = None, target_price: float = None) -> str:
    """
    목표가와 손절가 정보를 텍스트로 변환합니다.
    
    Args:
        stop_loss: 손절가
        target_price: 목표가
        
    Returns:
        가격 목표 텍스트
    """
    if not stop_loss and not target_price:
        return "목표가 및 손절가: 현재 신호 기준으로 설정되지 않음"
    
    result = []
    if target_price:
        result.append(f"목표가: {target_price:,.0f}원")
    if stop_loss:
        result.append(f"손절가: {stop_loss:,.0f}원")
    
    return "\n".join(result)

def format_individual_signals(signals: list) -> str:
    """
    개별 신호들을 포맷팅하여 텍스트로 변환합니다.
    
    Args:
        signals: 개별 신호 리스트
        
    Returns:
        포맷팅된 신호 텍스트
    """
    if not signals:
        return "감지된 개별 신호 없음"
    
    formatted_signals = []
    for signal in signals:
        indicator = signal.get('indicator', 'Unknown')
        signal_type = signal.get('signal', 'Unknown')
        strength = signal.get('strength', 0)
        reason = signal.get('reason', '')
        
        formatted_signals.append(
            f"- {indicator}: {signal_type} (강도: {strength:.1f}) - {reason}"
        )
    
    return "\n".join(formatted_signals)

def format_technical_indicators_text(indicators: dict) -> str:
    """
    기술적 지표 딕셔너리를 텍스트로 포맷팅합니다.
    
    Args:
        indicators: 기술적 지표 딕셔너리
        
    Returns:
        포맷팅된 지표 텍스트
    """
    if not indicators:
        return "기술적 지표 정보 없음"
    
    formatted_indicators = []
    
    # RSI
    if indicators.get('rsi') is not None:
        rsi = indicators['rsi']
        rsi_status = "과매수" if rsi > 70 else "과매도" if rsi < 30 else "중립"
        formatted_indicators.append(f"RSI: {rsi:.1f} ({rsi_status})")
    
    # MACD
    if indicators.get('macd') is not None:
        macd = indicators['macd']
        macd_signal = indicators.get('macd_signal', 0)
        macd_trend = "상승" if macd > macd_signal else "하락"
        formatted_indicators.append(f"MACD: {macd:.3f} ({macd_trend} 추세)")
    
    # 볼린저 밴드
    if indicators.get('bollinger_upper') is not None:
        formatted_indicators.append(
            f"볼린저 밴드: 상단 {indicators['bollinger_upper']:,.0f}원, "
            f"하단 {indicators['bollinger_lower']:,.0f}원"
        )
    
    # 이동평균선
    if indicators.get('sma_20') is not None:
        formatted_indicators.append(f"20일 이평: {indicators['sma_20']:,.0f}원")
    if indicators.get('sma_60') is not None:
        formatted_indicators.append(f"60일 이평: {indicators['sma_60']:,.0f}원")
    
    return "\n".join(formatted_indicators) 