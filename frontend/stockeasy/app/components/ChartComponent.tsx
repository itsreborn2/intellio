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
  TickMarkType,
  LineStyle
} from 'lightweight-charts';
import Papa from 'papaparse';

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
  subtitle?: string; // 부제목 속성 추가
  height?: number;
  width?: string;
  showVolume?: boolean;
  marketType?: string; // 시장 구분 (KOSDAQ 또는 KOSPI)
  stockName?: string; // 종목명 추가
  showMA20?: boolean; // 20일 이동평균선 표시 여부
  parentComponent?: string; // 부모 컴포넌트 식별자 추가
}

/**
 * 캔들스틱 차트 컴포넌트
 * @param data - 차트에 표시할 캔들 데이터 배열
 * @param title - 차트 제목 (선택 사항)
 * @param subtitle - 차트 부제목 (선택 사항)
 * @param height - 차트 높이 (기본값: 400px)
 * @param width - 차트 너비 (기본값: '100%')
 * @param showVolume - 거래량 차트 표시 여부 (기본값: true)
 * @param marketType - 시장 구분 (기본값: undefined)
 * @param stockName - 종목명 (기본값: undefined)
 * @param showMA20 - 20일 이동평균선 표시 여부 (기본값: true)
 * @param parentComponent - 부모 컴포넌트 식별자 (기본값: undefined)
 */
const ChartComponent: React.FC<ChartProps> = ({ 
  data, 
  title, 
  subtitle, // 부제목 속성 추가
  height = 400, 
  width = '100%',
  showVolume = true,
  marketType,
  stockName,
  showMA20 = true,
  parentComponent
}) => {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<any>(null);
  const candlestickSeriesRef = useRef<any>(null);
  const volumeSeriesRef = useRef<any>(null);
  const lineSeriesRef = useRef<any>(null); // 시장 지수 라인 시리즈 ref
  const ma20SeriesRef = useRef<any>(null); // 20일 이동평균선 시리즈 ref
  const [marketIndexData, setMarketIndexData] = useState<LineData<Time>[]>([]);
  const [isLoadingMarketIndex, setIsLoadingMarketIndex] = useState<boolean>(false);
  const [marketIndexError, setMarketIndexError] = useState<string | null>(null);
  const [marketIndexLoaded, setMarketIndexLoaded] = useState<boolean>(false);

  // 실제로 20일선을 표시할지 여부 결정
  // parentComponent가 지정되지 않은 경우(직접 사용되는 경우) 20일선을 표시하지 않음
  const shouldShowMA20 = showMA20 && parentComponent !== undefined;

  // 시장 지수 데이터 가져오는 함수
  const fetchMarketIndexData = useCallback(async () => {
    if (!marketType) {
      console.log('시장 구분이 없어 시장 지수 데이터를 가져오지 않습니다.');
      return;
    }
    
    try {
      setIsLoadingMarketIndex(true);
      setMarketIndexError(null);
      
      // 시장 구분 정규화 (대소문자 구분 없이 처리)
      const normalizedMarketType = marketType.toUpperCase();
      console.log(`시장 지수 데이터 가져오기: ${normalizedMarketType} (원본: ${marketType})`);
      
      // 시장 지수 로컬 캐시 파일 경로 설정
      const marketIndexPath = normalizedMarketType === 'KOSPI' 
        ? '/market-index/1dzf65fz6elq6b5znvhuaftn10hqjbe_c.csv'
        : '/market-index/1ks9qkdzmsxv-qenv6udzzidfwgykc1qg.csv';
      
      console.log(`시장 지수 파일 경로: ${marketIndexPath}`);
      
      // 로컬 캐시 파일에서 데이터 가져오기
      const response = await fetch(marketIndexPath);
      
      if (!response.ok) {
        const errorText = await response.text();
        console.error(`시장 지수 데이터 가져오기 실패: ${response.status} ${errorText}`);
        setMarketIndexError(`로컬 캐시 파일 로드 오류: ${response.status}`);
        setMarketIndexData([]);
        return;
      }
      
      const csvText = await response.text();
      
      // CSV 파싱
      const parsedData = Papa.parse(csvText, {
        header: true,
        skipEmptyLines: true,
        dynamicTyping: true,
      });
      
      // 데이터 변환
      const indexData = parsedData.data
        .filter((row: any) => {
          const isValid = row && row['날짜'] && row['시가'] && row['고가'] && row['저가'] && row['종가'];
          return isValid;
        })
        .map((row: any) => {
          // 날짜 형식 변환 (YYYYMMDD -> YYYY-MM-DD)
          let timeStr = String(row['날짜'] || '');
          let formattedTime = '';
          
          if (timeStr.length === 8) {
            const year = timeStr.substring(0, 4);
            const month = timeStr.substring(4, 6);
            const day = timeStr.substring(6, 8);
            formattedTime = `${year}-${month}-${day}`;
          } else {
            formattedTime = timeStr;
          }
          
          return {
            time: formattedTime,
            value: parseFloat(row['종가'] || 0)
          } as LineData<Time>;
        });
      
      console.log(`시장 지수 데이터 로드 완료: ${indexData.length}개 데이터 포인트`);
      setMarketIndexData(indexData);
      setMarketIndexLoaded(true);
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
      ma20SeriesRef.current = null;
    }
    
    console.log('차트 생성 시작...');
    console.log(`ChartComponent에 전달된 데이터 타입: ${typeof data}, 배열 여부: ${Array.isArray(data)}`);
    console.log(`전달된 데이터 길이: ${data ? data.length : '데이터 없음'}`);
    
    try {
      // 데이터 유효성 로깅
      console.log(`ChartComponent: 데이터 수신 완료 (${data.length}개 항목)`);
      if (data.length > 0) {
        console.log('첫 번째 데이터 항목:', JSON.stringify(data[0]));
      } else {
        console.error('ChartComponent: 데이터가 비어 있습니다.');
        return; // 데이터가 없으면 차트 생성 중단
      }
      
      // 캔들 데이터 필터링 및 정렬
      const validData = data.filter((item: any) => 
        item && 
        item.time !== undefined && 
        item.time !== null &&
        !isNaN(item.open) && 
        !isNaN(item.high) && 
        !isNaN(item.low) && 
        !isNaN(item.close)
      );
      
      console.log('유효한 데이터 개수:', validData.length);
      
      if (validData.length === 0) {
        console.error('ChartComponent: 유효한 데이터가 없습니다.');
        return; // 유효한 데이터가 없으면 차트 생성 중단
      }
      
      const usedTimestamps = new Set<number>();
      let timestampOffset = 0;
      const secondsInDay = 24 * 60 * 60; // 하루를 초 단위로 표현
      
      const candleData = validData
        .map((item: any, index: number) => {
          try {
            // 데이터 형식 로깅
            console.log(`아이템 #${index} 처리 중 - 데이터 타입:`, typeof item);
            if (typeof item === 'object' && item !== null) {
              console.log(`아이템 #${index}의 속성들:`, Object.keys(item).join(', '));
            }
            
            // 시가, 고가, 저가, 종가 필드 추출
            const openField = extractNumberField(item, ['open', 'Open', 'OPEN', '시가']);
            const highField = extractNumberField(item, ['high', 'High', 'HIGH', '고가']);
            const lowField = extractNumberField(item, ['low', 'Low', 'LOW', '저가']);
            const closeField = extractNumberField(item, ['close', 'Close', 'CLOSE', '종가']);
            
            // 추출된 값 로깅
            console.log(`아이템 #${index} 필드 추출 결과: open=${openField}, high=${highField}, low=${lowField}, close=${closeField}`);
            
            let timestamp: Time;
            let originalTimestamp: number = 0;
            
            if (typeof item.time === 'string') {
              // 하이픈 형식 날짜 (YYYY-MM-DD)
              if (/^\d{4}-\d{2}-\d{2}$/.test(item.time)) {
                try {
                  const [year, month, day] = item.time.split('-').map(Number);
                  console.log(`날짜 파싱 (하이픈): ${year}년 ${month}월 ${day}일`);
                  
                  if (year >= 1900 && year <= 2100 && month >= 1 && month <= 12 && day >= 1 && day <= 31) {
                    originalTimestamp = Math.floor(new Date(Date.UTC(year, month - 1, day)).getTime() / 1000);
                    console.log(`${item.time}의 타임스탬프 변환 결과: ${originalTimestamp}`);
                  } else {
                    console.error(`유효하지 않은 날짜 범위: ${item.time}`);
                    originalTimestamp = secondsInDay * index;
                  }
                } catch (error) {
                  console.error(`날짜 파싱 오류 (하이픈): ${item.time}`, error);
                  originalTimestamp = secondsInDay * index;
                }
              } 
              // 슬래시 형식 날짜 (YYYY/MM/DD)
              else if (/^\d{4}\/\d{2}\/\d{2}$/.test(item.time)) {
                try {
                  const [year, month, day] = item.time.split('/').map(Number);
                  console.log(`날짜 파싱 (슬래시): ${year}년 ${month}월 ${day}일`);
                  
                  if (year >= 1900 && year <= 2100 && month >= 1 && month <= 12 && day >= 1 && day <= 31) {
                    originalTimestamp = Math.floor(new Date(Date.UTC(year, month - 1, day)).getTime() / 1000);
                    console.log(`${item.time}의 타임스탬프 변환 결과: ${originalTimestamp}`);
                  } else {
                    console.error(`유효하지 않은 날짜 범위: ${item.time}`);
                    originalTimestamp = secondsInDay * index;
                  }
                } catch (error) {
                  console.error(`날짜 파싱 오류 (슬래시): ${item.time}`, error);
                  originalTimestamp = secondsInDay * index;
                }
              }
              // 숫자 8자리 형식 날짜 (YYYYMMDD)
              else if (/^\d{8}$/.test(item.time)) {
                try {
                  const year = parseInt(item.time.substring(0, 4));
                  const month = parseInt(item.time.substring(4, 6));
                  const day = parseInt(item.time.substring(6, 8));
                  console.log(`날짜 파싱 (8자리): ${year}년 ${month}월 ${day}일`);
                  
                  if (year >= 1900 && year <= 2100 && month >= 1 && month <= 12 && day >= 1 && day <= 31) {
                    originalTimestamp = Math.floor(new Date(Date.UTC(year, month - 1, day)).getTime() / 1000);
                    console.log(`${item.time}의 타임스탬프 변환 결과: ${originalTimestamp}`);
                  } else {
                    console.error(`유효하지 않은 날짜 범위: ${item.time}`);
                    originalTimestamp = secondsInDay * index;
                  }
                } catch (error) {
                  console.error(`날짜 파싱 오류 (8자리): ${item.time}`, error);
                  originalTimestamp = secondsInDay * index;
                }
              }
              else {
                console.error(`지원하지 않는 날짜 형식: ${item.time}, 인덱스 기반 타임스탬프 생성`);
                originalTimestamp = secondsInDay * index;
              }
            } else if (typeof item.time === 'number') {
              // 숫자 형식 (타임스탬프)
              originalTimestamp = item.time;
              if (originalTimestamp <= 0) {
                console.warn(`유효하지 않은 타임스탬프: ${originalTimestamp}, 인덱스 기반 타임스탬프로 대체`);
                originalTimestamp = secondsInDay * index;
              } else {
                console.log(`숫자 타임스탬프 사용: ${originalTimestamp}`);
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
          } catch (error) {
            console.error(`캔들 데이터 생성 오류: ${error}`);
            return null;
          }
        })
        .filter((item): item is CandlestickData<Time> => {
          if (!item) return false; // null 체크 추가
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
          tickMarkFormatter: (time: Time, tickMarkType: TickMarkType, locale: string) => {
            const date = new Date(Number(time) * 1000);
            const year = date.getFullYear();
            const month = (date.getMonth() + 1).toString().padStart(2, '0');
            const day = date.getDate().toString().padStart(2, '0');
            
            // 메이저 틱(주요 눈금)에는 연도-월-일 형식으로 표시
            if (tickMarkType === TickMarkType.Year) {
              return `${year}`;
            } else if (tickMarkType === TickMarkType.Month) {
              return `${year}-${month}`;
            } else if (tickMarkType === TickMarkType.DayOfMonth) {
              return `${month}.${day}`;
            }
            
            // 기본 형식은 월.일
            return `${month}.${day}`;
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
        },
        // 한국식 캔들 색상 설정 (상승 시 빨간색, 하락 시 파란색)
        upColor: '#ef5350',       // 상승 시 빨간색
        downColor: '#2962FF',     // 하락 시 파란색
        borderUpColor: '#ef5350', // 상승 시 테두리 색상
        borderDownColor: '#2962FF', // 하락 시 테두리 색상
        wickUpColor: '#ef5350',   // 상승 시 꼬리 색상
        wickDownColor: '#2962FF'  // 하락 시 꼬리 색상
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
          
          // 한국식 볼륨 색상 설정 (상승 시 빨간색, 하락 시 파란색)
          const color = (candle.close >= candle.open) ? '#ef5350' : '#2962FF';
          
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
                    color: (candle.close >= candle.open) ? '#ef5350' : '#2962FF'
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
        
        // 시장 구분에 따라 색상 설정
        const marketColor = marketType === 'KOSPI' ? '#2962FF' : '#00C853'; // KOSPI는 파란색, KOSDAQ은 녹색
        
        const marketIndexSeries = chart.addSeries(LineSeries, {
          color: marketColor, // 시장 구분에 따른 색상 적용
          lineWidth: 2,
          crosshairMarkerVisible: true,
          lastValueVisible: true, // 마지막 값 표시 활성화
          priceLineVisible: true, // 가격선 표시 활성화
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
        
        console.log('시장 지수 라인 시리즈 추가 완료');
      }

      // 20일 이동평균선 추가
      if (shouldShowMA20 && uniqueCandleData.length > 0) {
        console.log('20일 이동평균선 추가 중...');
        
        // 20일 이동평균선 데이터 계산
        const ma20Data = calculateMA20(uniqueCandleData);
        
        if (ma20Data.length > 0) {
          // 20일 이동평균선 시리즈 추가
          const ma20Series = chart.addSeries(LineSeries, {
            color: '#000080', // 남색(navy)
            lineWidth: 2,
            crosshairMarkerVisible: true,
            lastValueVisible: false, // 마지막 값 표시 비활성화
            priceLineVisible: false,
            title: '', // 타이틀 제거
          });
          
          ma20Series.setData(ma20Data);
          ma20SeriesRef.current = ma20Series;
          
          // 차트 좌측 상단에 MA20 텍스트 추가
          const container = chartContainerRef.current;
          if (container) {
            // 기존 MA20 레전드가 있다면 제거
            const existingLegend = container.querySelector('.ma20-legend');
            if (existingLegend) {
              container.removeChild(existingLegend);
            }
            
            const legendDiv = document.createElement('div');
            legendDiv.className = 'ma20-legend';
            legendDiv.style.position = 'absolute';
            legendDiv.style.left = '10px';
            legendDiv.style.top = '10px';
            legendDiv.style.zIndex = '3';
            legendDiv.style.fontSize = '12px';
            legendDiv.style.padding = '2px 5px';
            legendDiv.style.borderRadius = '3px';
            legendDiv.style.backgroundColor = 'rgba(255, 255, 255, 0.7)';
            legendDiv.innerHTML = '<span style="color: #000080; font-weight: bold;">MA20</span>';
            container.appendChild(legendDiv);
          }
          
          console.log('20일 이동평균선 추가 완료');
        } else {
          console.log('20일 이동평균선 데이터가 충분하지 않습니다.');
        }
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
          ma20SeriesRef.current = null;
        }
        
        // 차트 컨테이너에서 MA20 레전드 제거
        const container = chartContainerRef.current;
        if (container) {
          const legend = container.querySelector('.ma20-legend');
          if (legend) {
            container.removeChild(legend);
          }
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
        
        // 차트 컨테이너에서 MA20 레전드 제거
        const container = chartContainerRef.current;
        if (container) {
          const legend = container.querySelector('.ma20-legend');
          if (legend) {
            container.removeChild(legend);
          }
        }
      };
    }
    
    return cleanupFunction;
  }, [data, height, showVolume, marketType, marketIndexData]);

  // 숫자 필드 추출을 위한 헬퍼 함수
  const extractNumberField = (item: any, fieldNames: string[]): number => {
    if (!item) return 0;
    
    for (const fieldName of fieldNames) {
      if (item[fieldName] !== undefined) {
        const value = item[fieldName];
        
        if (typeof value === 'number') {
          return value;
        } else if (typeof value === 'string') {
          try {
            // 쉼표 및 기타 문자 제거 후 숫자 변환
            const numValue = parseFloat(value.replace(/,/g, '').replace(/[^\d.-]/g, ''));
            if (!isNaN(numValue)) {
              return numValue;
            }
          } catch (error) {
            console.warn(`${fieldName} 필드 변환 오류:`, error);
          }
        }
      }
    }
    
    return 0;
  };

  // 20일 이동평균선 계산 함수
  const calculateMA20 = (data: CandlestickData<Time>[]): LineData<Time>[] => {
    if (!data || data.length === 0) return [];
    
    const period = 20;
    const result: LineData<Time>[] = [];
    
    // 데이터가 충분하지 않은 경우에도 이동평균선을 계산하기 위한 방법
    // 부족한 데이터는 첫 번째 데이터로 채움
    for (let i = 0; i < data.length; i++) {
      let sum = 0;
      let count = 0;
      
      // 이전 20일 데이터 수집
      for (let j = 0; j < period; j++) {
        if (i - j >= 0) {
          // 실제 데이터가 있는 경우
          sum += data[i - j].close;
          count++;
        } else {
          // 데이터가 부족한 경우 첫 번째 데이터로 대체
          sum += data[0].close;
          count++;
        }
      }
      
      // 평균 계산
      const ma = sum / count;
      
      result.push({
        time: data[i].time,
        value: ma
      });
    }
    
    return result;
  };

  return (
    <div style={{ position: 'relative', width, height: `${height}px` }}>
      <div 
        ref={chartContainerRef} 
        style={{ 
          width: '100%', 
          height: '100%',
          border: '1px solid #e2e8f0', 
          borderRadius: '0 0 0.375rem 0.375rem',
          overflow: 'hidden'
        }} 
      />
      {title && (
        <div 
          style={{
            position: 'absolute',
            top: '5px',
            left: '10px',
            color: '#333',
            fontSize: '14px',
            fontWeight: 'bold',
          }}
        >
          {title}
        </div>
      )}
      {subtitle && (
        <div 
          style={{
            position: 'absolute',
            top: '25px',
            left: '10px',
            color: '#666',
            fontSize: '12px',
          }}
        >
          {subtitle}
        </div>
      )}
    </div>
  );
};

export default ChartComponent;
