'use client';

import React from 'react';
import { createChart, ColorType, LineStyle, CandlestickSeries, HistogramSeries, LineSeries, AreaSeries, Time } from 'lightweight-charts';

// PriceChart 컴포넌트 - Lightweight Charts를 사용한 주가차트
const PriceChart: React.FC<{
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
    if (!chartContainerRef.current || !data.candle_data || data.candle_data.length === 0) {
      return;
    }
    
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
        scaleMargins: {
          top: 0.1,
          bottom: 0.1,
        },
      },
      timeScale: {
        borderColor: '#cccccc',
        timeVisible: true,
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
    const seriesRefs: Array<{ series: any; name: string; color: string; type: 'candle' | 'indicator' | 'volume' | 'ma' }> = [];
    
    // 캔들스틱 시리즈 추가 - 한국 스타일 (상승: 빨간색, 하락: 파란색)
    const candlestickSeries = chart.addSeries(CandlestickSeries, {
      upColor: '#F87171',
      downColor: '#60A5FA',
      borderUpColor: '#F87171',
      borderDownColor: '#60A5FA',
      wickUpColor: '#F87171',
      wickDownColor: '#60A5FA',
      priceFormat: {
        type: 'custom',
        minMove: 1,
        formatter: (price: number) => {
          // 주가를 정수형으로 표시 (원 단위)
          return Math.round(price).toLocaleString('ko-KR');
        }
      },
      //title: '주가',
    });
    
    // 주가 스케일 설정 - 거래량이 있으면 상단 70% 영역 사용
    if (data.volume_data && data.volume_data.length > 0) {
      chart.priceScale('right').applyOptions({
        scaleMargins: {
          top: 0.1,
          bottom: 0.3, // 하단 30%는 거래량을 위해 여백 확보
        },
      });
    }
    
    // 캔들 데이터 설정
    const candleData = data.candle_data.map((item: any) => ({
      time: item.time as Time,
      open: item.open,
      high: item.high,
      low: item.low,
      close: item.close,
      price_change_percent: item.price_change_percent, // 등락율 정보 추가
    }));
    
    candlestickSeries.setData(candleData);
    
    // 캔들스틱 시리즈 참조 저장
    seriesRefs.push({
      series: candlestickSeries,
      name: '캔들스틱',
      color: '#ef5350',
      type: 'candle'
    });
    
    // 거래량 데이터 처리 - volume_data가 있으면 사용하고, 없으면 candle_data에서 추출
    let volumeDataToUse = data.volume_data;
    
    // volume_data가 없지만 candle_data에 volume 정보가 있는 경우 추출
    if ((!volumeDataToUse || volumeDataToUse.length === 0) && data.candle_data && data.candle_data.length > 0) {
      // candle_data에서 volume 정보만 추출하여 volume_data 형태로 변환
      volumeDataToUse = data.candle_data
        .filter((candle: any) => candle.volume !== undefined && candle.volume > 0)
        .map((candle: any) => ({
          time: candle.time,
          value: candle.volume,
        }));
    }
    
    // 거래량 데이터가 있으면 추가
    if (volumeDataToUse && volumeDataToUse.length > 0) {
      const volumeSeries = chart.addSeries(HistogramSeries, {
        color: '#26a69a',
        priceFormat: {
          type: 'volume',
        },
        priceScaleId: 'volume',
        //title: '거래량',
      });
      
      // 거래량 스케일 설정 - 하단 30% 영역 사용
      chart.priceScale('volume').applyOptions({
        scaleMargins: {
          top: 0.7, // 상단 70% 지점부터 시작
          bottom: 0,
        },
        borderColor: '#cccccc',
        textColor: '#666',
        entireTextOnly: false,
        ticksVisible: true,
        borderVisible: true,
      });
      
              // 거래량 데이터 처리 - 전일 대비 증감으로 색상 결정
        const volumeData = volumeDataToUse.map((item: any, index: number) => {
          let volumeColor = '#F8717180'; // 기본 상승 색상 (반투명)
          
          // 전일 거래량과 비교하여 색상 결정
          if (index > 0 && volumeDataToUse[index - 1]) {
            const prevVolume = volumeDataToUse[index - 1].value;
            const currentVolume = item.value;
            
            // 전일 대비 거래량 증가: 빨간색, 감소: 파란색 (반투명)
            volumeColor = currentVolume >= prevVolume ? '#F8717180' : '#60A5FA80';
          } else if (item.color) {
            // 별도로 색상이 지정된 경우 사용 (반투명 처리)
            volumeColor = item.color + '80';
          }
        
        return {
          time: item.time as Time,
          value: item.value,
          color: volumeColor,
        };
      });
      
      volumeSeries.setData(volumeData);
      
      // 거래량 시리즈 참조 저장 (대표 색상으로 표시)
      seriesRefs.push({
        series: volumeSeries,
        name: '거래량',
        color: '#26a69a',
        type: 'volume'
      });
    }
    
    // 이동평균선 추가
    if (data.moving_averages && data.moving_averages.length > 0) {
      const maSeries = chart.addSeries(LineSeries, {
        color: '#ff6b35',
        lineWidth: 2,
      });
      
      const maData = data.moving_averages.map((item: any) => ({
        time: item.time as Time,
        value: item.value
      }));
      
      maSeries.setData(maData);
      
      // 이동평균선 시리즈 참조 저장
      seriesRefs.push({
        series: maSeries,
        name: '이동평균선',
        color: '#ff6b35',
        type: 'ma'
      });
    }
    
    // 지지선 추가
    if (data.support_lines && data.support_lines.length > 0) {
      data.support_lines.forEach((line: any) => {
        // 캔들스틱 시리즈에 직접 프라이스 라인 추가 (중복 방지)
        if (candlestickSeries && line.show_label) {
          candlestickSeries.createPriceLine({
            price: line.price,
            color: line.color || '#2196f3',
            lineWidth: line.line_width || 2,
            lineStyle: line.line_style === 'solid' ? LineStyle.Solid :
                      line.line_style === 'dotted' ? LineStyle.Dotted :
                      LineStyle.Dashed,
            axisLabelVisible: false, // 오른쪽 Y축 라벨 제거
            title: line.label,
          });
        }
      });
    }
    
    // 저항선 추가
    if (data.resistance_lines && data.resistance_lines.length > 0) {
      data.resistance_lines.forEach((line: any) => {
        // 캔들스틱 시리즈에 직접 프라이스 라인 추가 (중복 방지)
        if (candlestickSeries && line.show_label) {
          candlestickSeries.createPriceLine({
            price: line.price,
            color: line.color || '#ef5350',
            lineWidth: line.line_width || 2,
            lineStyle: line.line_style === 'solid' ? LineStyle.Solid :
                      line.line_style === 'dotted' ? LineStyle.Dotted :
                      LineStyle.Dashed,
            axisLabelVisible: false, // 오른쪽 Y축 라벨 제거
            title: line.label,
          });
        }
      });
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
            // 지표, 거래량, 이동평균선 데이터
            const value = dataPoint.value !== undefined ? dataPoint.value : dataPoint;
            let displayValue: string;
            
            if (type === 'volume') {
              // 거래량은 천 단위로 표시
              displayValue = typeof value === 'number' ? 
                (value >= 1000000 ? (value / 1000000).toFixed(1) + 'M' :
                 value >= 1000 ? (value / 1000).toFixed(0) + 'K' :
                 value.toString()) : value.toString();
            } else {
              // 일반 지표는 소수점 2자리로 표시
              displayValue = typeof value === 'number' ? value.toFixed(2) : value.toString();
            }
            
            indicators.push({
              name,
              value: displayValue,
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
    const legendItems = [];
    
    // 캔들스틱 범례
    if (data.candle_data && data.candle_data.length > 0) {
      legendItems.push({
        name: '주가',
        color: '#26a69a',
        type: 'candle'
      });
    }
    
    // 거래량 범례 - volume_data가 있거나 candle_data에 volume이 있는 경우
    const hasVolumeData = (data.volume_data && data.volume_data.length > 0) || 
                         (data.candle_data && data.candle_data.length > 0 && 
                          data.candle_data.some((candle: any) => candle.volume !== undefined && candle.volume > 0));
    
    if (hasVolumeData) {
      legendItems.push({
        name: '거래량',
        color: '#666',
        type: 'bar'
      });
    }
    
    // 이동평균선 범례
    if (data.moving_averages && data.moving_averages.length > 0) {
      legendItems.push({
        name: '이동평균선',
        color: '#ff6b35',
        type: 'line'
      });
    }
    
                // 지지선 범례 - 실제 라인 색상과 일치
    if (data.support_lines && data.support_lines.length > 0) {
      const supportLineColor = data.support_lines[0]?.color || '#2196f3';
      legendItems.push({
        name: '지지선',
        color: supportLineColor,
        type: 'line'
      });
    }
    
    // 저항선 범례 - 실제 라인 색상과 일치
    if (data.resistance_lines && data.resistance_lines.length > 0) {
      const resistanceLineColor = data.resistance_lines[0]?.color || '#ef5350';
      legendItems.push({
        name: '저항선',
        color: resistanceLineColor,
        type: 'line'
      });
    }
    
    if (legendItems.length === 0) return null;
    
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
        {legendItems.map((item, index) => (
          <div key={`legend-${index}`} style={{
            display: 'flex',
            alignItems: 'center',
            gap: '5px',
          }}>
            <div style={{
              width: item.type === 'candle' ? '8px' : '12px',
              height: item.type === 'candle' ? '12px' : item.type === 'bar' ? '8px' : '2px',
              backgroundColor: item.color,
              borderRadius: item.type === 'candle' ? '1px' : '1px',
              border: item.type === 'candle' ? `1px solid ${item.color}` : 'none',
            }} />
            <span style={{ color: '#333' }}>{item.name}</span>
          </div>
        ))}
      </div>
    );
  };
  
  return (
    <div style={{ width: '100%' }}>
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
                    { label: '종가', value: crosshairData.candle.close, color: '#1e293b' }
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
                      }}>{value.toLocaleString()}</div>
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
                      }}>{indicator.value}</span>
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

export default PriceChart; 