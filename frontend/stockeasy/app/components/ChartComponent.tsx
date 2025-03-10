'use client';
/**
 * ChartComponent.tsx
 * lightweight-charts 라이브러리를 사용한 캔들스틱 차트 컴포넌트
 * lightweight-charts v5.0.3 API 사용
 */
import React, { useEffect, useRef, useState, useCallback } from 'react';
import { 
  createChart, 
  CandlestickSeries, 
  HistogramSeries,
  LineSeries,
  ColorType,
  Time,
  CrosshairMode,
  DeepPartial,
  ChartOptions,
  CandlestickData,
  HistogramData,
  LineData,
  TickMarkType
} from 'lightweight-charts';

// 캔들 데이터 인터페이스 정의
interface CandleData {
  time: Time; // 'YYYY-MM-DD' 형식 또는 타임스탬프
  open: number;
  high: number;
  low: number;
  close: number;
  volume?: number;
}

// 내부 처리용 확장 캔들 데이터 인터페이스
interface ExtendedCandleData {
  time: Time;
  open: number;
  high: number;
  low: number;
  close: number;
  volume?: number; // 볼륨 정보는 선택적
}

// 차트 컴포넌트 props 인터페이스
interface ChartProps {
  data: CandleData[];
  title?: string;
  height?: number;
  width?: string;
  showVolume?: boolean;
  marketType?: string; // 시장 구분 (KOSDAQ 또는 KOSPI)
  stockName?: string; // 종목명 추가
}

/**
 * 캔들스틱 차트 컴포넌트
 * @param data - 차트에 표시할 캔들 데이터 배열
 * @param title - 차트 제목 (선택 사항)
 * @param height - 차트 높이 (기본값: 400px)
 * @param width - 차트 너비 (기본값: '100%')
 * @param showVolume - 거래량 차트 표시 여부 (기본값: true)
 * @param marketType - 시장 구분 (기본값: undefined)
 * @param stockName - 종목명 (기본값: undefined)
 */
const ChartComponent: React.FC<ChartProps> = ({ 
  data, 
  title, 
  height = 400, 
  width = '100%',
  showVolume = true,
  marketType,
  stockName
}) => {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<any>(null);
  const candlestickSeriesRef = useRef<any>(null);
  const volumeSeriesRef = useRef<any>(null);
  const lineSeriesRef = useRef<any>(null); // 시장 지수 라인 시리즈 ref
  const [marketIndexData, setMarketIndexData] = useState<LineData<Time>[]>([]);
  const [isLoadingMarketIndex, setIsLoadingMarketIndex] = useState<boolean>(false);
  const [marketIndexError, setMarketIndexError] = useState<string | null>(null);
  const [marketIndexLoaded, setMarketIndexLoaded] = useState<boolean>(false);

  // 시장 지수 데이터 가져오는 함수
  const fetchMarketIndexData = useCallback(async () => {
    if (!marketType) {
      console.log('시장 구분 정보가 없어 시장 지수 데이터를 가져오지 않습니다.');
      return;
    }
    
    try {
      setIsLoadingMarketIndex(true);
      setMarketIndexError(null);
      
      console.log(`시장 지수 데이터 가져오기: ${marketType}`);
      
      // 시장 지수 API 호출
      const response = await fetch('/api/market-index', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ marketType }),
      });
      
      if (!response.ok) {
        const errorText = await response.text();
        console.error(`시장 지수 데이터 가져오기 실패: ${response.status} ${errorText}`);
        setMarketIndexError(`API 응답 오류: ${response.status}`);
        setMarketIndexData([]);
        return;
      }
      
      const result = await response.json();
      console.log(`시장 지수 데이터 수신 성공: ${result.data?.length || 0}개 데이터 포인트`);
      
      // 경고 메시지 처리
      if (result.warning) {
        console.warn(`시장 지수 데이터 경고: ${result.warning}`);
        setMarketIndexError(result.warning);
      }
      
      if (!result.data || result.data.length === 0) {
        console.warn(`시장 지수 데이터가 비어 있습니다: ${marketType}`);
        setMarketIndexError(`${marketType} 시장 지수 데이터를 찾을 수 없습니다.`);
        setMarketIndexData([]);
        return;
      }
      
      // 캔들 데이터와 시장 지수 데이터의 날짜 형식을 일치시키기 위한 처리
      const formattedMarketData = result.data.map((item: { date: string; close: number }) => {
        // 날짜 형식 처리 (YYYY-MM-DD, YYYY/MM/DD 등 다양한 형식 지원)
        let timeValue: Time = item.date;
        
        // 날짜 형식 정규화 (하이픈과 슬래시 처리)
        if (typeof item.date === 'string') {
          // 슬래시를 하이픈으로 변환
          timeValue = item.date.replace(/\//g, '-');
        }
        
        return {
          time: timeValue,
          value: item.close
        } as LineData<Time>;
      });
      
      if (formattedMarketData.length === 0) {
        console.warn(`시장 지수 데이터 형식 변환 후 데이터가 비어 있습니다: ${marketType}`);
        setMarketIndexError(`${marketType} 시장 지수 데이터 형식이 올바르지 않습니다.`);
        setMarketIndexData([]);
        return;
      }
      
      setMarketIndexData(formattedMarketData);
      setMarketIndexLoaded(true);
      console.log(`시장 지수 데이터 형식 변환 완료. 첫번째 항목:`, formattedMarketData[0]);
    } catch (error) {
      console.error('시장 지수 데이터 가져오기 오류:', error);
      setMarketIndexError(error instanceof Error ? error.message : '알 수 없는 오류');
      setMarketIndexData([]);
    } finally {
      setIsLoadingMarketIndex(false);
    }
  }, [marketType]);

  // 시장 지수 데이터 가져오기
  useEffect(() => {
    if (marketType) {
      fetchMarketIndexData();
    }
  }, [marketType, fetchMarketIndexData]);

  useEffect(() => {
    // 차트 컨테이너나 데이터가 없으면 실행하지 않음
    if (!chartContainerRef.current || !data || data.length === 0) {
      return;
    }
    
    // 이벤트 리스너 및 정리 함수 선언
    let cleanupFunction = () => {};
    const handleResize = () => {
      if (chartContainerRef.current && chartRef.current) {
        try {
          chartRef.current.applyOptions({ 
            width: chartContainerRef.current.clientWidth 
          });
        } catch (error) {
          console.error('차트 리사이징 오류:', error);
        }
      }
    };
    
    // 기존 차트 정리
    if (chartRef.current) {
      chartRef.current.remove();
      chartRef.current = null;
      candlestickSeriesRef.current = null;
      volumeSeriesRef.current = null;
      lineSeriesRef.current = null;
    }
    
    console.log('차트 생성 시작...');
    
    try {
      // 데이터 유효성 로깅
      console.log(`ChartComponent: 데이터 수신 완료 (${data.length}개 항목)`);
      console.log('첫 번째 데이터 항목:', data[0]);
      
      // 캔들 데이터 필터링 및 정렬
      const validData = data.filter((item: any) => item && (item.time !== undefined && item.time !== null));
      console.log('유효한 데이터 개수:', validData.length);
      
      const usedTimestamps = new Set<number>();
      let timestampOffset = 0;
      const secondsInDay = 24 * 60 * 60; // 하루를 초 단위로 표현
      
      const candleData = validData
        .map((item: any, index: number) => {
          let timestamp: Time;
          let originalTimestamp: number = 0;
          
          if (typeof item.time === 'string') {
            if (/^\d{4}-\d{2}-\d{2}$/.test(item.time)) {
              const [year, month, day] = item.time.split('-').map(Number);
              if (year >= 1900 && year <= 2100 && month >= 1 && month <= 12 && day >= 1 && day <= 31) {
                originalTimestamp = Math.floor(new Date(Date.UTC(year, month - 1, day)).getTime() / 1000);
              } else {
                console.error(`유효하지 않은 날짜 범위: ${item.time}`);
                originalTimestamp = secondsInDay * index;
              }
            } 
            else if (/^\d{4}\/\d{2}\/\d{2}$/.test(item.time)) {
              const [year, month, day] = item.time.split('/').map(Number);
              if (year >= 1900 && year <= 2100 && month >= 1 && month <= 12 && day >= 1 && day <= 31) {
                originalTimestamp = Math.floor(new Date(Date.UTC(year, month - 1, day)).getTime() / 1000);
              } else {
                console.error(`유효하지 않은 날짜 범위: ${item.time}`);
                originalTimestamp = secondsInDay * index;
              }
            }
            else if (/^\d{8}$/.test(item.time)) {
              const year = parseInt(item.time.substring(0, 4));
              const month = parseInt(item.time.substring(4, 6));
              const day = parseInt(item.time.substring(6, 8));
              if (year >= 1900 && year <= 2100 && month >= 1 && month <= 12 && day >= 1 && day <= 31) {
                originalTimestamp = Math.floor(new Date(Date.UTC(year, month - 1, day)).getTime() / 1000);
              } else {
                console.error(`유효하지 않은 날짜 범위: ${item.time}`);
                originalTimestamp = secondsInDay * index;
              }
            }
            else {
              console.error(`지원하지 않는 날짜 형식: ${item.time}, 인덱스 기반 타임스탬프 생성`);
              originalTimestamp = secondsInDay * index;
            }
          } else if (typeof item.time === 'number') {
            originalTimestamp = item.time;
            if (originalTimestamp <= 0) {
              console.warn(`유효하지 않은 타임스탬프: ${originalTimestamp}, 인덱스 기반 타임스탬프로 대체`);
              originalTimestamp = secondsInDay * index;
            }
          } else {
            console.error(`지원하지 않는 날짜 타입: ${typeof item.time}, 인덱스 기반 타임스탬프 생성`);
            originalTimestamp = secondsInDay * index;
          }
          
          if (originalTimestamp <= 0) {
            originalTimestamp = secondsInDay * (index + 1); // 최소한 1일부터 시작
          }
          
          if (usedTimestamps.has(originalTimestamp)) {
            timestampOffset++;
            timestamp = (originalTimestamp + timestampOffset) as Time;
            console.warn(`중복된 타임스탬프 감지: ${originalTimestamp}, 조정된 타임스탬프: ${timestamp}`);
          } else {
            timestamp = originalTimestamp as Time;
            usedTimestamps.add(originalTimestamp);
          }
          
          if (Number(timestamp) <= 0) {
            console.error(`유효하지 않은 타임스탬프(${timestamp})가 생성되었습니다. 기본값으로 대체합니다.`);
            timestamp = (secondsInDay * (index + 1)) as Time;
          }
          
          let open = typeof item.open === 'number' ? item.open : 0;
          let high = typeof item.high === 'number' ? item.high : 0;
          let low = typeof item.low === 'number' ? item.low : 0;
          let close = typeof item.close === 'number' ? item.close : 0;
          
          if (isNaN(open)) open = 0;
          if (isNaN(high)) high = 0;
          if (isNaN(low)) low = 0;
          if (isNaN(close)) close = 0;
          
          if (open <= 0) open = close > 0 ? close : 100;
          if (close <= 0) close = open > 0 ? open : 100;
          if (high <= 0) high = Math.max(open, close, 100);
          if (low <= 0) low = Math.min(open > 0 ? open : 100, close > 0 ? close : 100);
          
          if (high < Math.max(open, close)) high = Math.max(open, close);
          if (low > Math.min(open, close)) low = Math.min(open, close);
          
          return {
            time: timestamp,
            open: open,
            high: high,
            low: low,
            close: close,
          };
        })
        .filter((item): item is CandlestickData<Time> => {
          return item !== undefined && Number(item.time) > 0;
        })
        .sort((a: any, b: any) => {
          return a.time - b.time;
        });
      
      const finalTimestamps = new Set<number>();
      const uniqueCandleData = candleData.filter((item, index) => {
        if (index === 0) {
          finalTimestamps.add(Number(item.time));
          return true;
        }
        
        const time = Number(item.time);
        if (finalTimestamps.has(time)) {
          console.warn(`최종 검사에서 중복 타임스탬프 발견: ${time} (인덱스: ${index})`);
          return false;
        }
        
        finalTimestamps.add(time);
        return true;
      });
      
      console.log(`유효한 캔들 데이터 ${uniqueCandleData.length}개 생성 (중복 제거 후)`);
      if (uniqueCandleData.length > 0) {
        console.log('첫 번째 캔들 데이터:', uniqueCandleData[0]);
        if (uniqueCandleData.length > 1) {
          console.log('두 번째 캔들 데이터:', uniqueCandleData[1]);
        }
        if (uniqueCandleData.length > 2) {
          console.log('세 번째 캔들 데이터:', uniqueCandleData[2]);
        }
      } else {
        console.error('유효한 캔들 데이터가 없습니다!');
      }
      
      const chartOptions: DeepPartial<ChartOptions> = {
        width: chartContainerRef.current?.clientWidth,
        height: height,
        layout: {
          background: { 
            type: ColorType.Solid, 
            color: '#ffffff' 
          },
          textColor: '#333',
        },
        grid: {
          vertLines: {
            color: 'rgba(197, 203, 206, 0.5)',
          },
          horzLines: {
            color: 'rgba(197, 203, 206, 0.5)',
          },
        },
        crosshair: {
          mode: CrosshairMode.Normal,
        },
        rightPriceScale: {
          borderColor: 'rgba(197, 203, 206, 0.8)',
        },
        timeScale: {
          borderColor: 'rgba(197, 203, 206, 0.8)',
          timeVisible: true,
          secondsVisible: false,
          tickMarkFormatter: (time: Time, tickMarkType: any, locale: string) => {
            const date = new Date(Number(time) * 1000);
            const month = (date.getMonth() + 1).toString().padStart(2, '0');
            const day = date.getDate().toString().padStart(2, '0');
            return `${month}-${day}`;
          },
        },
        localization: {
          priceFormatter: (price: number) => {
            return price.toLocaleString('ko-KR');
          },
        },
      };

      const chart = createChart(chartContainerRef.current, chartOptions);
      chartRef.current = chart;
      
      const candleSeries = chart.addSeries(CandlestickSeries, {
        priceFormat: {
          type: 'price',
          precision: 0, // 소수점 제거
          minMove: 1, // 최소 이동 단위
        }
      });
      candlestickSeriesRef.current = candleSeries;

      if (uniqueCandleData.length > 0) {
        console.log('캔들 차트 데이터 설정 중...');
        candleSeries.setData(uniqueCandleData);
      } else {
        console.error('캔들 데이터가 비어있습니다.');
        candleSeries.setData([
          { time: '2023-01-01' as Time, open: 100, high: 105, low: 95, close: 101 },
          { time: '2023-01-02' as Time, open: 101, high: 106, low: 100, close: 102 },
          { time: '2023-01-03' as Time, open: 102, high: 107, low: 101, close: 103 },
        ]);
      }

      if (showVolume) {
        console.log('볼륨 데이터 생성 중...');
        
        const volumeData = uniqueCandleData.map((candle: any) => {
          let volume = 0;
          
          try {
            const candleTimeStr = typeof candle.time === 'number' ? 
              new Date(candle.time * 1000).toISOString().split('T')[0] : String(candle.time);
            
            console.log(`볼륨 데이터 찾는 중 - 캔들 시간: ${candleTimeStr}, 타입: ${typeof candle.time}`);
            
            const originalItem = data.find((item: any) => {
              const itemTimeStr = typeof item.time === 'string' ? item.time : 
                (typeof item.time === 'number' ? 
                  new Date(item.time * 1000).toISOString().split('T')[0] : null);
              
              if (itemTimeStr && candleTimeStr) {
                const normalizedItemTime = itemTimeStr.replace(/\//g, '-').replace(/(\d{4})(\d{2})(\d{2})/, '$1-$2-$3');
                const normalizedCandleTime = candleTimeStr.replace(/\//g, '-').replace(/(\d{4})(\d{2})(\d{2})/, '$1-$2-$3');
                
                return normalizedItemTime === normalizedCandleTime;
              }
              return false;
            });
            
            if (originalItem) {
              console.log('매칭된 원본 데이터 항목 찾음:', originalItem);
              
              const itemAsAny = originalItem as any;
              const volumeField = itemAsAny.volume || itemAsAny.Volume || 
                                  itemAsAny.VOLUME || itemAsAny['거래량'] || null;
              
              if (volumeField !== null && volumeField !== undefined) {
                if (typeof volumeField === 'number') {
                  volume = volumeField;
                } else if (typeof volumeField === 'string') {
                  try {
                    volume = parseFloat(volumeField.replace(/,/g, '').replace(/[^\d.-]/g, ''));
                  } catch (error) {
                    console.warn('볼륨 문자열 변환 오류:', error);
                    volume = 0;
                  }
                }
              } else {
                console.warn('항목에 볼륨 필드가 없습니다:', originalItem);
              }
            } else {
              if (candle.volume !== undefined) {
                if (typeof candle.volume === 'number') {
                  volume = candle.volume;
                } else if (typeof candle.volume === 'string') {
                  try {
                    volume = parseFloat(candle.volume.replace(/,/g, '').replace(/[^\d.-]/g, ''));
                  } catch (error) {
                    console.warn('캔들 데이터 볼륨 변환 오류:', error);
                    volume = 0;
                  }
                  console.log(`캔들 데이터 자체의 볼륨 사용: ${volume}`);
                }
              } else {
                console.warn(`${candleTimeStr} 에 해당하는 볼륨 데이터를 찾을 수 없음`);
              }
            }
          } catch (matchingError) {
            console.error('볼륨 데이터 매칭 오류:', matchingError);
          }
          
          if (isNaN(volume) || volume < 0) {
            console.warn(`유효하지 않은 거래량 감지: ${volume}, 0으로 설정`);
            volume = 0;
          }
          
          const color = (candle.close >= candle.open) ? '#26a69a' : '#ef5350';
          
          if (volume > 0) {
            console.log(`볼륨 데이터 생성 성공: 시간=${candle.time}, 볼륨=${volume}`);
          }
          
          return {
            time: candle.time, 
            value: volume,
            color: color
          } as HistogramData<Time>;
        });
        
        console.log(`유효한 볼륨 데이터 ${volumeData.length}개 생성`);
        if (volumeData.length > 0) {
          console.log('볼륨 데이터 샘플:', volumeData.slice(0, 3));
        }
        
        const volumeSeries = chart.addSeries(HistogramSeries, {
          color: '#26a69a',
          priceFormat: {
            type: 'volume',
            precision: 0, // 소수점 제거
          },
          priceScaleId: 'volume',
          lastValueVisible: true,        // 마지막 값 표시
          priceLineVisible: false,       // 가격선 숨김
          baseLineVisible: false,        // 기준선 숨김
        });
        volumeSeriesRef.current = volumeSeries;

        chart.priceScale('volume').applyOptions({
          visible: true,
          borderVisible: true,
          borderColor: '#eeeeee',        // 경계선 색상
          scaleMargins: {
            top: 0.8, // 위에서 80% 위치에서 시작
            bottom: 0,
          },
          entireTextOnly: true,          // 텍스트 전체 표시
        });

        if (volumeData.length > 0) {
          console.log('볼륨 차트 데이터 설정 중...');
          try {
            const hasNonZeroVolume = volumeData.some(item => item.value > 0);
            if (!hasNonZeroVolume) {
              console.warn('모든 볼륨 데이터가 0입니다. 차트에 표시되지 않을 수 있습니다.');
              
              if (uniqueCandleData.length > 0) {
                console.log('샘플 볼륨 데이터를 생성합니다.');
                const sampleVolumeData = uniqueCandleData.map((candle, index) => {
                  const sampleVolume = Math.round((candle.close || 100) * (1 + Math.random() * 4)) * 100;
                  return {
                    time: candle.time,
                    value: sampleVolume,
                    color: (candle.close >= candle.open) ? '#26a69a' : '#ef5350'
                  } as HistogramData<Time>;
                });
                
                console.log('생성된 샘플 볼륨 데이터:', sampleVolumeData.slice(0, 3));
                
                volumeSeries.setData(sampleVolumeData);
                console.log('샘플 볼륨 데이터 설정 완료');
              }
            } else {
              volumeSeries.setData(volumeData);
              console.log('볼륨 차트 데이터 설정 완료');
            }
          } catch (error) {
            console.error('볼륨 데이터 설정 오류:', error);
          }
        } else {
          console.error('볼륨 데이터가 비어있습니다.');
        }
      }

      if (marketType && marketIndexData.length > 0) {
        console.log(`시장 지수 라인 시리즈 추가: ${marketType}, 데이터 ${marketIndexData.length}개`);
        
        // 시장 지수 차트에도 localization 옵션 적용
        chart.applyOptions({
          localization: {
            priceFormatter: (price: number) => {
              return price.toLocaleString('ko-KR');
            },
          },
        });
        
        // 시장 구분에 따라 색상 설정
        const marketColor = marketType === 'KOSPI' ? '#2962FF' : '#00C853'; // KOSPI는 파란색, KOSDAQ은 녹색
        
        const marketIndexSeries = chart.addSeries(LineSeries, {
          color: marketColor, // 시장 구분에 따른 색상 적용
          lineWidth: 2,
          crosshairMarkerVisible: true,
          lastValueVisible: true,
          priceLineVisible: true,
          priceScaleId: 'market-index',
          title: marketType,
          priceFormat: {
            type: 'price',
            precision: 0, // 소수점 제거
            minMove: 1, // 최소 이동 단위
          }
        });
        
        chart.priceScale('market-index').applyOptions({
          visible: true,
          borderVisible: true,
          borderColor: marketColor, // 시장 구분에 따른 색상 적용
          scaleMargins: {
            top: 0.1,
            bottom: showVolume ? 0.2 : 0,
          },
          entireTextOnly: true,
          ticksVisible: true,
        });

        marketIndexSeries.setData(marketIndexData);
        lineSeriesRef.current = marketIndexSeries;
        
        chartContainerRef.current.style.position = 'relative';
        
        console.log('시장 지수 라인 시리즈 추가 완료');
      }

      try {
        chart.timeScale().fitContent();
      } catch (error) {
        console.error('차트 크기 조정 오류:', error);
      }

      window.addEventListener('resize', handleResize);

      cleanupFunction = () => {
        window.removeEventListener('resize', handleResize);
        if (chartRef.current) {
          console.log('차트 정리 중...');
          chartRef.current.remove();
          chartRef.current = null;
          candlestickSeriesRef.current = null;
          volumeSeriesRef.current = null;
          lineSeriesRef.current = null;
        }
      };
    } catch (error) {
      console.error('차트 생성 중 오류 발생:', error);
      cleanupFunction = () => {
        window.removeEventListener('resize', handleResize);
        if (chartRef.current) {
          chartRef.current.remove();
          chartRef.current = null;
        }
      };
    }
    
    return cleanupFunction;
  }, [data, height, showVolume, marketType, marketIndexData]);

  return (
    <div className="chart-container">
      {/* title 표시 부분 제거 - 중복 표시 문제 해결 */}
      {/* 종목명과 시장 구분을 함께 표시 */}
      <div className="flex items-center justify-between mb-2">
        {stockName && (
          <h4 className="text-base font-semibold text-black">{stockName}</h4>
        )}
        {marketType && (
          <span className={`text-xs font-medium px-2 py-1 rounded ${marketType === 'KOSPI' ? 'bg-blue-100 text-blue-800' : 'bg-green-100 text-green-800'}`}>
            {marketType}
          </span>
        )}
      </div>
      {/* 시장 지수 관련 텍스트 제거 */}
      <div
        ref={chartContainerRef}
        style={{ 
          height: `${height}px`, 
          width, 
          border: '1px solid #e2e8f0', 
          borderRadius: '0.375rem',
          overflow: 'hidden' 
        }}
      />
    </div>
  );
};

export default ChartComponent;
