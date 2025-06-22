'use client';

import React from 'react';
import { createChart, ColorType, LineStyle, CandlestickSeries, HistogramSeries, LineSeries, AreaSeries, Time } from 'lightweight-charts';

// 차트 색상 테마 정의
const CHART_COLORS = [
  '#4285F4', '#34A853', '#FBBC05', '#EA4335', 
  '#8C9EFF', '#1DE9B6', '#FFAB40', '#FF5252',
  '#7C4DFF', '#00E5FF', '#EEFF41', '#FF4081'
];

// 지표별 색상을 반환하는 함수
function getIndicatorColor(indicatorName: string): string {
  const colorMap: { [key: string]: string } = {
    'rsi': '#ff6b6b',
    'macd': '#4ecdc4',
    'macd_signal': '#45b7d1',
    'macd_histogram': '#f9ca24',
    'sma_20': '#6c5ce7',
    'sma_60': '#a29bfe',
    'ema_12': '#fd79a8',
    'ema_26': '#fdcb6e',
    'bollinger_upper': '#00b894',
    'bollinger_middle': '#00cec9',
    'bollinger_lower': '#55a3ff',
    'adx': '#e17055',
    'adx_plus_di': '#00b894',
    'adx_minus_di': '#d63031',
    'supertrend': '#74b9ff',
    'adr': '#fd79a8',
    'stochastic_k': '#a29bfe',
    'stochastic_d': '#6c5ce7'
  };
  
  return colorMap[indicatorName] || '#74b9ff';
}

// 지표 타입을 반환하는 함수
function getIndicatorType(indicatorName: string): string {
  const typeMap: { [key: string]: string } = {
    'macd_histogram': 'histogram',
    'volume': 'histogram'
  };
  
  return typeMap[indicatorName] || 'line';
}

// TechnicalIndicatorChart 컴포넌트 - Lightweight Charts를 사용한 기술적 지표 차트
const TechnicalIndicatorChart: React.FC<{
  data: any;
  height: number;
  isMobile: boolean;
}> = ({ data, height, isMobile }) => {
  const chartContainerRef = React.useRef<HTMLDivElement>(null);
  const chartRef = React.useRef<any>(null);
  const [crosshairData, setCrosshairData] = React.useState<{
    time: string;
    candle?: { open: number; high: number; low: number; close: number; price_change_percent?: number };
    indicators: { name: string; value: number | string; color: string }[];
    mouseX: number;
    mouseY: number;
  } | null>(null);
  
  React.useEffect(() => {
    console.log('[TechnicalIndicatorChart] useEffect 시작, 데이터 검증:', {
      hasContainer: !!chartContainerRef.current,
      hasDates: !!data.dates,
      datesLength: data.dates?.length || 0,
      hasIndicators: !!data.indicators,
      indicatorsLength: data.indicators?.length || 0,
      hasCandleData: !!data.candle_data,
      candleDataLength: data.candle_data?.length || 0,
      fullData: data
    });

    if (!chartContainerRef.current) {
      console.warn('[TechnicalIndicatorChart] 차트 컨테이너 ref가 없습니다.');
      return;
    }

    if (!data.dates || data.dates.length === 0) {
      console.warn('[TechnicalIndicatorChart] dates 데이터가 없거나 비어있습니다.');
      return;
    }

    // 캔들 데이터가 없으면 차트를 그릴 수 없음
    if (!data.candle_data || data.candle_data.length === 0) {
      console.warn('[TechnicalIndicatorChart] candle_data가 없거나 비어있습니다.');
      return;
    }
    
    // indicators는 선택사항으로 처리 (없어도 캔들차트는 표시)
    const indicatorsList = data.indicators || [];
    console.log('[TechnicalIndicatorChart] 렌더링 시작 - 캔들데이터:', data.candle_data.length, '지표:', indicatorsList.length);
    
    // 차트 생성
    const chart = createChart(chartContainerRef.current, {
      width: chartContainerRef.current.clientWidth,
      height: height,
      layout: {
        background: { color: '#ffffff' },
        textColor: '#333333',
      },
      grid: {
        vertLines: {
          color: '#e1e1e1',
        },
        horzLines: {
          color: '#e1e1e1',
        },
      },
      rightPriceScale: {
        borderColor: '#cccccc',
        visible: true,
      },
      leftPriceScale: {
        borderColor: '#cccccc',
        visible: true,
      },
      timeScale: {
        borderColor: '#cccccc',
        timeVisible: false,
        secondsVisible: false,
      },
      crosshair: {
        mode: 1, // Normal crosshair mode
        vertLine: {
          width: 1,
          color: '#999999',
          style: 2, // LightweightCharts.LineStyle.Dashed
        },
        horzLine: {
          width: 1,
          color: '#999999',
          style: 2, // LightweightCharts.LineStyle.Dashed
        },
      },
      localization: {
        timeFormatter: (time: any) => {
          // yyyy-mm-dd 형식으로 변환
          if (typeof time === 'string') {
            return time; // 이미 문자열 형태면 그대로 반환
          }
          const date = new Date(time * 1000);
          const year = date.getFullYear();
          const month = String(date.getMonth() + 1).padStart(2, '0');
          const day = String(date.getDate()).padStart(2, '0');
          return `${year}-${month}-${day}`;
        },
      },
    });
    
    chartRef.current = chart;
    
    // 시리즈 참조들을 저장할 배열
    const seriesRefs: Array<{ series: any; name: string; color: string; type: 'candle' | 'indicator' }> = [];
    
    // 선 스타일 변환 함수
    const getLineStyle = (lineStyle: string): LineStyle => {
      switch (lineStyle) {
        case 'dashed':
          return LineStyle.Dashed;
        case 'dotted':
          return LineStyle.Dotted;
        default:
          return LineStyle.Solid;
      }
    };
    
    // Y축 설정
    const primaryAxisConfig = data.y_axis_configs?.primary || {
      title: "Primary",
      position: "left",
      color: "#3b82f6"
    };

    const secondaryAxisConfig = data.y_axis_configs?.secondary || {
      title: "Secondary", 
      position: "right",
      color: "#8b5cf6"
    };

    const hiddenAxisConfig = data.y_axis_configs?.hidden || null;
    
    // 캔들 데이터가 있는 경우 캔들스틱 시리즈 추가 - 한국 스타일
    if (data.candle_data && data.candle_data.length > 0) {
      console.log('[TechnicalIndicatorChart] 캔들 데이터 생성 시작:', data.candle_data.length, '개');
      
      try {
        const candlestickSeries = chart.addSeries(CandlestickSeries, {
          upColor: '#F87171',
          downColor: '#60A5FA', 
          borderUpColor: '#F87171',
          borderDownColor: '#60A5FA',
          wickUpColor: '#F87171',
          wickDownColor: '#60A5FA',
          priceScaleId: 'right', // 오른쪽 스케일 사용
          priceFormat: {
            type: 'custom',
            minMove: 1,
            formatter: (price: number) => {
              // 주가를 정수형으로 표시 (원 단위)
              return Math.round(price).toLocaleString('ko-KR');
            }
          }
        });
        
        // 캔들 데이터 변환 및 검증
        const candleData = data.candle_data.map((item: any, index: number) => {
          // 시간 데이터 정규화 (YYYY-MM-DD 형식)
          let timeValue: string;
          if (typeof item.time === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(item.time)) {
            timeValue = item.time;
          } else {
            // 날짜 변환 시도
            const date = new Date(item.time);
            if (!isNaN(date.getTime())) {
              const year = date.getFullYear();
              const month = String(date.getMonth() + 1).padStart(2, '0');
              const day = String(date.getDate()).padStart(2, '0');
              timeValue = `${year}-${month}-${day}`;
            } else {
              console.warn(`[TechnicalIndicatorChart] 유효하지 않은 시간 데이터 (인덱스 ${index}):`, item.time);
              timeValue = '2024-01-01'; // 기본값
            }
          }
          
          // OHLC 데이터 검증
          const open = Number(item.open) || 0;
          const high = Number(item.high) || 0;
          const low = Number(item.low) || 0;
          const close = Number(item.close) || 0;
          
          if (high < low || high < Math.max(open, close) || low > Math.min(open, close)) {
            console.warn(`[TechnicalIndicatorChart] 비정상적인 OHLC 데이터 (인덱스 ${index}):`, {
              time: timeValue, open, high, low, close
            });
          }
          
          return {
            time: timeValue as Time,
            open: open,
            high: high,
            low: low,
            close: close,
          };
        });
        
        console.log('[TechnicalIndicatorChart] 변환된 캔들 데이터 샘플:', candleData.slice(0, 3));
        
        candlestickSeries.setData(candleData);
        
        // 캔들스틱 시리즈 참조 저장
        seriesRefs.push({
          series: candlestickSeries,
          name: '캔들스틱',
          color: '#F87171',
          type: 'candle'
        });
        
        console.log('[TechnicalIndicatorChart] 캔들스틱 시리즈 생성 완료');
        
      } catch (error) {
        console.error('[TechnicalIndicatorChart] 캔들스틱 시리즈 생성 중 오류:', error);
      }
    } else {
      console.warn('[TechnicalIndicatorChart] 캔들 데이터가 없습니다:', {
        hasCandleData: !!data.candle_data,
        candleDataLength: data.candle_data?.length || 0
      });
    }

    // 지표별 시리즈 생성
    console.log('=== TechnicalIndicatorChart 분석 시작 ===');
    console.log('전체 데이터:', data);
    console.log('지표 목록:', indicatorsList);
    
    indicatorsList.forEach((indicator: any, index: number) => {
      const color = indicator.color || CHART_COLORS[index % CHART_COLORS.length];
      const lineStyle = getLineStyle(indicator.line_style);
      
      // 슈퍼트렌드 지표인지 확인
      const isSupertrend = indicator.name && (
        indicator.name.toLowerCase().includes('supertrend') || 
        indicator.name.includes('슈퍼트렌드')
      );
      
      console.log(`지표 ${index + 1} 분석:`, {
        name: indicator.name,
        isSupertrend,
        hasDirections: !!indicator.directions,
        directionsLength: indicator.directions?.length,
        directions: indicator.directions,
        dataLength: indicator.data?.length
      });
      
      // 스케일 ID 결정: 슈퍼트렌드는 캔들 데이터와 동일한 스케일 사용
      let priceScaleId;
      if (isSupertrend && data.candle_data && data.candle_data.length > 0) {
        priceScaleId = 'right'; // 캔들 데이터와 동일한 스케일 사용 (오른쪽)
      } else if (indicator.y_axis_id === 'hidden') {
        priceScaleId = 'hidden'; // 범용 hidden 축 사용
      } else {
        priceScaleId = indicator.y_axis_id === 'secondary' ? 'right' : 'left'; // secondary는 오른쪽, primary는 왼쪽
      }
      
      // 시계열 데이터 생성 - 슈퍼트렌드의 경우 항상 실제 값 사용
      let seriesData;
      if (isSupertrend) {
        // 슈퍼트렌드는 실제 가격 값을 사용 (data 필드에 이미 실제 값이 들어있음)
        seriesData = data.dates.map((date: string, idx: number) => ({
          time: date as Time,
          value: indicator.data[idx] || 0, // 백엔드에서 이미 실제 값으로 설정됨
        }));
      } else {
        seriesData = data.dates.map((date: string, idx: number) => ({
          time: date as Time,
          value: indicator.data[idx] || 0,
        }));
      }
      
      // 차트 타입에 따라 시리즈 생성
      if (indicator.chart_type === 'bar') {
        const histogramSeries = chart.addSeries(HistogramSeries, {
          color: color,
          priceFormat: {
            type: 'price',
            precision: 2,
            minMove: 0.01,
          },
          priceScaleId: priceScaleId,
        });
        
        // 막대 차트용 데이터 형식으로 변환
        const histogramData = seriesData.map((item: any) => ({
          time: item.time,
          value: item.value,
          color: color,
        }));
        
        histogramSeries.setData(histogramData);
        
      } else if (indicator.chart_type === 'area') {
        const areaSeries = chart.addSeries(AreaSeries, {
          topColor: color,
          bottomColor: `${color}20`, // 투명도 적용
          lineColor: color,
          lineWidth: 2,
          lineStyle: lineStyle,
          priceFormat: {
            type: 'price',
            precision: 2,
            minMove: 0.01,
          },
          priceScaleId: priceScaleId,
        });
        
        areaSeries.setData(seriesData);
        
      } else {
        // 기본값: line
        // 슈퍼트렌드의 경우 방향에 따라 구간별 색상 변경
        if (isSupertrend && indicator.directions && indicator.directions.length > 0) {
          // 방향 변화 지점을 찾아서 구간별로 시리즈 생성
          const segments: Array<{data: any[], direction: number}> = [];
          let currentSegment: any[] = [];
          let currentDirection = indicator.directions[0];
          
          seriesData.forEach((point: any, idx: number) => {
            const direction = indicator.directions[idx];
            
            // 방향이 바뀌는 지점
            if (direction !== currentDirection && currentSegment.length > 0) {
              // 이전 구간을 저장 (연결점 포함)
              segments.push({
                data: [...currentSegment, point], // 연결을 위해 현재 포인트도 포함
                direction: currentDirection
              });
              
              // 새 구간 시작 (연결점으로 현재 포인트부터 시작)
              currentSegment = [point];
              currentDirection = direction;
            } else {
              currentSegment.push(point);
            }
          });
          
          // 마지막 구간 저장
          if (currentSegment.length > 0) {
            segments.push({
              data: currentSegment,
              direction: currentDirection
            });
          }
          
          // 각 구간별로 시리즈 생성
          segments.forEach((segment, segmentIdx) => {
            const segmentColor = segment.direction === 1 ? '#34A853' : '#ef5350'; // 상승: 초록색, 하락: 빨간색
            const segmentName = segment.direction === 1 ? '상승' : '하락';
            
            if (segment.data.length > 1) { // 최소 2개 포인트가 있어야 선을 그릴 수 있음
              const segmentSeries = chart.addSeries(LineSeries, {
                color: segmentColor,
                lineWidth: 3, // 슈퍼트렌드는 좀 더 굵게
                lineStyle: lineStyle,
                priceFormat: {
                  type: 'price',
                  precision: 2,
                  minMove: 0.01,
                },
                priceScaleId: priceScaleId,
                title: segmentIdx === 0 ? indicator.name : '', // 첫 번째 구간에만 이름 표시
                lastValueVisible: false, // 마지막 값 표시 숨김
                priceLineVisible: false, // 프라이스 라인 표시 숨김
              });
              
              segmentSeries.setData(segment.data);
              
              // 첫 번째 구간만 참조로 저장 (전체 지표를 대표)
              if (segmentIdx === 0) {
                seriesRefs.push({
                  series: segmentSeries,
                  name: indicator.name,
                  color: color,
                  type: 'indicator'
                });
              }

            } else {
              console.log(`❌ 구간 ${segmentIdx + 1} 스킵 (데이터 부족: ${segment.data.length}개)`);
            }
          });
          console.log('🟢 슈퍼트렌드 방향별 색상 적용 완료!');
        } else {
          // 일반 지표는 기존 방식으로 처리
          console.log(`🔴 일반 지표 처리: ${indicator.name}`);
          
          // +DI, -DI 지표인지 확인하여 선 굵기 설정
          const isDIIndicator = indicator.name && (
            indicator.name.includes('+DI') || 
            indicator.name.includes('-DI') ||
            indicator.name.includes('상승방향지수') ||
            indicator.name.includes('하락방향지수')
          );
          
          const lineSeriesOptions: any = {
            color: color,
            lineWidth: isDIIndicator ? 1 : 2, // +DI, -DI는 굵기 1, 나머지는 굵기 2
            lineStyle: lineStyle,
            priceFormat: {
              type: 'price',
              precision: 2,
              minMove: 0.01,
            },
            priceScaleId: priceScaleId,
          };
          
          // 슈퍼트렌드가 아닌 일반 지표는 부가 정보 표시 숨김
          if (!isSupertrend) {
            lineSeriesOptions.lastValueVisible = false; // 마지막 값 표시 숨김
            lineSeriesOptions.priceLineVisible = false; // 프라이스 라인 표시 숨김
          }
          
          const lineSeries = chart.addSeries(LineSeries, lineSeriesOptions);
          
          lineSeries.setData(seriesData);
          
          // 일반 지표 시리즈 참조 저장
          seriesRefs.push({
            series: lineSeries,
            name: indicator.name,
            color: color,
            type: 'indicator'
          });
          console.log(`✅ 일반 지표 시리즈 생성 완료: ${indicator.name}`);
        }
      }
    });
    
    // Y축 스케일 설정
    if (data.y_axis_configs) {
      if (primaryAxisConfig.title) {
        chart.priceScale('left').applyOptions({
          borderColor: primaryAxisConfig.color,
          scaleMargins: {
            top: data.candle_data && data.candle_data.length > 0 ? 0.6 : 0.1, // 캔들이 있으면 지표들을 위한 공간
            bottom: 0.1,
          },
          visible: primaryAxisConfig.display !== false, // display가 false면 축 숨김
        });
      }
      
      if (secondaryAxisConfig.title) {
        chart.priceScale('right').applyOptions({
          borderColor: secondaryAxisConfig.color,
          scaleMargins: {
            top: 0.1, // 캔들을 위한 적절한 여백
            bottom: data.candle_data && data.candle_data.length > 0 ? 0.4 : 0.1, // 다른 지표들을 위한 공간 확보
          },
          visible: secondaryAxisConfig.display !== false, // display가 false면 축 숨김
        });
      }

      // 범용 hidden 축 설정
      if (hiddenAxisConfig) {
        chart.priceScale('hidden').applyOptions({
          borderColor: hiddenAxisConfig.color || '#2196f3',
          visible: false, // 항상 숨김
          scaleMargins: {
            top: 0.25,    // 상단 패딩 증가 (10% → 20%)
            bottom: 0.25, // 하단 패딩 증가 (10% → 20%)
          },
        });
      }
    }
    
    // 마우스 이벤트를 위한 차트 컨테이너에 이벤트 리스너 추가
    let currentMouseX = 0;
    let currentMouseY = 0;
    
    const handleMouseMove = (event: MouseEvent) => {
      const rect = chartContainerRef.current?.getBoundingClientRect();
      if (rect) {
        currentMouseX = event.clientX - rect.left;
        currentMouseY = event.clientY - rect.top;
      }
    };
    
    chartContainerRef.current.addEventListener('mousemove', handleMouseMove);
    
    // 크로스헤어 이벤트 리스너 추가
    chart.subscribeCrosshairMove((param: any) => {
      if (!param.time) {
        setCrosshairData(null);
        return;
      }
      
      const indicators: { name: string; value: number | string; color: string }[] = [];
      let candleData: { open: number; high: number; low: number; close: number; price_change_percent?: number } | undefined;
      
      // 모든 시리즈에서 해당 시점의 데이터 수집
      seriesRefs.forEach(({ series, name, color, type }) => {
        const dataPoint = param.seriesData?.get(series);
        if (dataPoint) {
          if (type === 'candle') {
            candleData = {
              open: dataPoint.open,
              high: dataPoint.high,
              low: dataPoint.low,
              close: dataPoint.close,
              price_change_percent: dataPoint.price_change_percent
            };
          } else {
            // 지표 데이터
            const value = dataPoint.value !== undefined ? dataPoint.value : dataPoint;
            indicators.push({
              name,
              value: typeof value === 'number' ? value.toFixed(2) : String(value),
              color
            });
          }
        }
      });
      
      // 시간 포맷팅
      const timeStr = typeof param.time === 'string' ? param.time : 
                     new Date(param.time * 1000).toISOString().split('T')[0];
      
      setCrosshairData({
        time: timeStr,
        candle: candleData,
        indicators,
        mouseX: currentMouseX,
        mouseY: currentMouseY
      });
    });
    
    // 리사이즈 핸들러
    const handleResize = () => {
      if (chartContainerRef.current && chartRef.current) {
        chartRef.current.applyOptions({
          width: chartContainerRef.current.clientWidth,
        });
      }
    };
    
    window.addEventListener('resize', handleResize);
    
    // 정리
    return () => {
      window.removeEventListener('resize', handleResize);
      if (chartContainerRef.current) {
        chartContainerRef.current.removeEventListener('mousemove', handleMouseMove);
      }
      if (chartRef.current) {
        chartRef.current.remove();
      }
    };
  }, [data, height]);
  
  // 범례 정보 표시용 컴포넌트
  const renderLegend = () => {
    return (
      <div style={{
        display: 'flex',
        flexWrap: 'wrap',
        justifyContent: 'center',
        alignItems: 'center',
        gap: '15px',
        marginTop: '10px',
        padding: '8px',
        fontSize: '0.75em',
        fontWeight: 500,
      }}>
        {/* 캔들 범례 - 한국 스타일 */}
        {data.candle_data && data.candle_data.length > 0 && (
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: '5px',
          }}>
            <div style={{
              width: '8px',
              height: '12px',
              backgroundColor: '#ef5350',
              borderRadius: '1px',
              border: '1px solid #ef5350',
            }} />
            <span style={{ color: '#333' }}>주가</span>
          </div>
        )}
        
        {/* 지표 범례 */}
        {data.indicators && data.indicators.map((indicator: any, index: number) => {
          const color = indicator.color || CHART_COLORS[index % CHART_COLORS.length];
          
          // 슈퍼트렌드 지표인지 확인
          const isSupertrend = indicator.name && (
            indicator.name.toLowerCase().includes('supertrend') || 
            indicator.name.includes('슈퍼트렌드')
          );
          
          return (
            <div key={`legend-${index}`} style={{
              display: 'flex',
              alignItems: 'center',
              gap: '5px',
            }}>
              {isSupertrend ? (
                // 슈퍼트렌드의 경우 녹색+빨간색 반반 표시
                <div style={{
                  width: '12px',
                  height: '2px',
                  borderRadius: '1px',
                  display: 'flex',
                  overflow: 'hidden',
                }}>
                  <div style={{
                    width: '50%',
                    height: '100%',
                    backgroundColor: '#34A853', // 상승 녹색
                  }} />
                  <div style={{
                    width: '50%',
                    height: '100%',
                    backgroundColor: '#ef5350', // 하락 빨간색
                  }} />
                </div>
              ) : (
                // 일반 지표는 기존 방식
                <div style={{
                  width: '12px',
                  height: '2px',
                  backgroundColor: color,
                  borderRadius: '1px',
                }} />
              )}
              <span style={{ color: '#333' }}>{indicator.name}</span>
            </div>
          );
        })}
      </div>
    );
  };
  
  // 데이터가 유효하지 않은 경우 에러 메시지 표시 (indicators는 선택사항으로 변경)
  if (!data || !data.dates || data.dates.length === 0 || !data.candle_data || data.candle_data.length === 0) {
    return (
      <div style={{ 
        width: '100%', 
        height: `${height}px`,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        backgroundColor: '#f8f9fa',
        border: '2px dashed #dee2e6',
        borderRadius: '8px',
        color: '#6c757d'
      }}>
        <div style={{ textAlign: 'center' }}>
          <div style={{ fontSize: '1.2em', marginBottom: '0.5em' }}>📊</div>
          <div>차트 데이터를 처리하는 중입니다...</div>
          <div style={{ fontSize: '0.8em', marginTop: '0.5em', color: '#999' }}>
            날짜: {data?.dates?.length || 0}개 | 캔들: {data?.candle_data?.length || 0}개 | 지표: {data?.indicators?.length || 0}개
          </div>
        </div>
      </div>
    );
  }

  return (
    <div style={{ width: '100%' }}>
      {/* Y축 라벨 */}
      {data.y_axis_configs && (
        <div style={{
          display: 'flex',
          justifyContent: 'space-between',
          marginBottom: '5px',
          fontSize: '0.75em',
          fontWeight: 'bold',
          color: '#666',
        }}>
          {data.y_axis_configs.primary?.title && data.y_axis_configs.primary?.display !== false && (
            <span style={{ color: data.y_axis_configs.primary.color }}>
              {data.y_axis_configs.primary.title}
            </span>
          )}
          {data.y_axis_configs.secondary?.title && data.y_axis_configs.secondary?.display !== false && (
            <span style={{ color: data.y_axis_configs.secondary.color }}>
              {data.y_axis_configs.secondary.title}
            </span>
          )}
          {/* hidden 축은 라벨을 표시하지 않음 (visible: false이므로) */}
        </div>
      )}
      
      {/* 차트 영역 */}
      <div 
        ref={chartContainerRef} 
        style={{ 
          width: '100%', 
          height: `${height}px`,
          position: 'relative'
        }}
      >
        {/* 크로스헤어 데이터 표시 - 마우스 팝업 */}
        {crosshairData && (() => {
          // 팝업 위치 계산 (화면 경계를 벗어나지 않도록 조정)
          const popupWidth = 300; // 예상 팝업 너비
          const popupHeight = 80; // 예상 팝업 높이
          
          let left = crosshairData.mouseX + 15; // 마우스 오른쪽에 표시
          let top = crosshairData.mouseY - 40; // 마우스 위쪽에 표시
          
          // 오른쪽 경계 체크
          if (left + popupWidth > chartContainerRef.current?.clientWidth!) {
            left = crosshairData.mouseX - popupWidth - 15; // 마우스 왼쪽에 표시
          }
          
          // 위쪽 경계 체크
          if (top < 0) {
            top = crosshairData.mouseY + 15; // 마우스 아래쪽에 표시
          }
          
          // 아래쪽 경계 체크
          if (top + popupHeight > chartContainerRef.current?.clientHeight!) {
            top = chartContainerRef.current?.clientHeight! - popupHeight - 10;
          }
          
          return (
            <div style={{
              position: 'absolute',
              left: `${left}px`,
              top: `${top}px`,
              zIndex: 1000,
              background: 'linear-gradient(135deg, rgba(255, 255, 255, 0.98), rgba(248, 250, 252, 0.98))',
              backdropFilter: 'blur(12px)',
              border: '1px solid rgba(226, 232, 240, 0.6)',
              borderRadius: '10px',
              padding: '10px 14px',
              fontSize: '0.85em',
              fontFamily: 'system-ui, -apple-system, sans-serif',
              boxShadow: '0 8px 32px rgba(0, 0, 0, 0.12)',
              display: 'flex',
              flexDirection: 'column',
              gap: '6px',
              minWidth: '200px',
              maxWidth: '300px',
              lineHeight: '1.3',
              transition: 'all 0.15s ease',
              pointerEvents: 'none', // 마우스 이벤트 무시
            }}>
              {/* 시간 표시 */}
              <div style={{ 
                fontSize: '0.9em',
                fontWeight: '600',
                color: '#1e293b',
                marginBottom: '4px',
                textAlign: 'center'
              }}>
                📅 {crosshairData.time}
              </div>
              
              {/* 캔들 데이터 표시 */}
              {crosshairData.candle && (
                <div style={{ 
                  display: 'grid',
                  gridTemplateColumns: 'repeat(4, 1fr)',
                  gap: '8px',
                  padding: '6px',
                  backgroundColor: 'rgba(248, 113, 113, 0.08)',
                  borderRadius: '6px',
                  border: '1px solid rgba(248, 113, 113, 0.2)'
                }}>
                  {[
                    { label: '시가', value: crosshairData.candle.open, color: '#64748b' },
                    { label: '고가', value: crosshairData.candle.high, color: '#dc2626' },
                    { label: '저가', value: crosshairData.candle.low, color: '#2563eb' },
                    { label: '종가', value: crosshairData.candle.close, color: '#1e293b' },
                    ...(crosshairData.candle.price_change_percent !== undefined ? 
                      [{ label: '등락율', value: crosshairData.candle.price_change_percent, color: '#64748b' }] : [])
                  ].map(({ label, value, color }, idx) => (
                    <div key={idx} style={{ textAlign: 'center' }}>
                      <div style={{ 
                        fontSize: '0.75em', 
                        color: '#64748b',
                        fontWeight: '500',
                        marginBottom: '2px'
                      }}>{label}</div>
                      <div style={{ 
                        color: color,
                        fontWeight: '600',
                        fontSize: '0.85em'
                      }}>{value?.toLocaleString() || '0'}</div>
                    </div>
                  ))}
                </div>
              )}
              
              {/* 지표 데이터 표시 */}
              {crosshairData.indicators.length > 0 && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                  {crosshairData.indicators.map((indicator, index) => (
                    <div key={index} style={{ 
                      display: 'flex', 
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      padding: '3px 6px',
                      backgroundColor: 'rgba(99, 102, 241, 0.06)',
                      borderRadius: '4px'
                    }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                        <div style={{
                          width: '6px',
                          height: '6px',
                          borderRadius: '50%',
                          backgroundColor: indicator.color,
                        }} />
                        <span style={{ 
                          color: '#475569',
                          fontSize: '0.8em',
                          fontWeight: '500'
                        }}>{indicator.name}</span>
                      </div>
                      <span style={{ 
                        color: '#1e293b',
                        fontWeight: '600',
                        fontSize: '0.85em'
                      }}>{String(indicator.value)}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          );
        })()}
      </div>
      
      {/* 범례 */}
      {renderLegend()}
    </div>
  );
};

export default TechnicalIndicatorChart; 