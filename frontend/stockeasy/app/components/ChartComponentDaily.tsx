'use client';
/**
 * ChartComponentDaily.tsx
 * 일봉 데이터 표시에 최적화된 캔들스틱 차트 컴포넌트
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
  subtitle?: string;
  height?: number;
  width?: string;
  showVolume?: boolean;
  marketType?: string; // 시장 구분 (KOSDAQ 또는 KOSPI)
  stockName?: string; // 종목명 추가
  showMA20?: boolean; // 20일 이동평균선 표시 여부
  parentComponent?: string; // 부모 컴포넌트 식별자 추가
  breakthroughPrice?: number; // 돌파 가격
}

/**
 * 일봉 데이터에 최적화된 캔들스틱 차트 컴포넌트
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
 * @param breakthroughPrice - 돌파 가격 (기본값: undefined)
 */
const ChartComponentDaily: React.FC<ChartProps> = ({ 
  data, 
  title, 
  subtitle,
  height = 400, 
  width = '100%',
  showVolume = true,
  marketType,
  stockName,
  showMA20 = true,
  parentComponent,
  breakthroughPrice,
}) => {
  console.log(`[ChartComponentDaily] 종목: ${stockName}, 수신된 breakthroughPrice: ${breakthroughPrice}, 타입: ${typeof breakthroughPrice}`);
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<any>(null);
  const candlestickSeriesRef = useRef<any>(null);
  const volumeSeriesRef = useRef<any>(null);
  const lineSeriesRef = useRef<any>(null); // 시장 지수 라인 시리즈 ref
  const ma20SeriesRef = useRef<any>(null); // 20일 이동평균선 시리즈 ref
  const [marketIndexData, setMarketIndexData] = useState<LineData<Time>[]>([]);
  const [isLoadingMarketIndex, setIsLoadingMarketIndex] = useState<boolean>(false);
  const [marketIndexLoaded, setMarketIndexLoaded] = useState<boolean>(false);
  const [marketIndexError, setMarketIndexError] = useState<string | null>(null);

  // 실제로 20일선을 표시할지 여부 결정
  const shouldShowMA20 = showMA20 && parentComponent !== undefined;

  // 시장 지수 데이터 가져오는 함수
  const fetchMarketIndexData = useCallback(async () => {
    if (!marketType) {
      console.log('marketType이 정의되지 않아 시장 지수 데이터를 가져오지 않습니다.');
      return;
    }

    console.log(`[${marketType}] 시장 지수 데이터 가져오기 시작...`);
    setIsLoadingMarketIndex(true);
    setMarketIndexError(null);
    setMarketIndexLoaded(false); // 데이터 로드 시작 시 false로 설정

    const normalizedMarketType = marketType.toUpperCase();
    
    // ChartComponentDaily는 주로 일별 2개월 데이터를 사용합니다.
    // parentComponent prop에 따라 다른 경로를 사용해야 하는 경우 아래 로직을 확장할 수 있습니다.
    // const useDaily2Month = parentComponent === 'SpecificComponent' ? false : true;
    const useDaily2Month = true; // 현재 ChartComponentDaily는 항상 2개월치 일봉을 사용한다고 가정합니다.

    let marketIndexPath = '';
    if (useDaily2Month) {
      marketIndexPath = normalizedMarketType === 'KOSPI'
        ? '/requestfile/market-index/kospidaily2month.csv'
        : '/requestfile/market-index/kosdaqdaily2month.csv';
    } else {
      // 필요시 다른 기간의 데이터 경로 설정 (예: 전체 기간 데이터)
      marketIndexPath = normalizedMarketType === 'KOSPI'
        ? '/requestfile/market-index/kospi.csv' // 가상의 전체 KOSPI 데이터 경로
        : '/requestfile/market-index/kosdaq.csv'; // 가상의 전체 KOSDAQ 데이터 경로
    }

    console.log(`[${marketType}] 시장 지수 데이터 요청 경로: ${marketIndexPath}`);

    try {
      const cacheBustingTimestamp = new Date().getTime();
      const response = await fetch(`${marketIndexPath}?t=${cacheBustingTimestamp}`, { cache: 'no-store' });

      if (!response.ok) {
        const errorText = await response.text();
        console.error(`[${marketType}] 시장 지수 데이터 (${marketIndexPath}) 로드 실패: ${response.status} ${response.statusText}`, errorText);
        throw new Error(`시장 지수 데이터 로드 실패: ${response.status} ${response.statusText}`);
      }

      const csvText = await response.text();
      // console.log(`[${marketType}] CSV 데이터 수신 완료 (첫 200자):`, csvText.substring(0, 200));

      Papa.parse(csvText, {
        header: true,        // 첫 번째 줄을 헤더로 사용
        skipEmptyLines: true, // 빈 줄은 건너뜀
        dynamicTyping: false, // 모든 값을 문자열로 받아 수동으로 파싱 (날짜/숫자 형식 보존)
        complete: (results) => {
          // console.log(`[${marketType}] CSV 파싱 결과 (메타데이터):`, results.meta);
          if (results.errors.length > 0) {
            results.errors.forEach(err => console.error(`[${marketType}] CSV 파싱 오류: ${err.message}, 행: ${err.row}, 코드: ${err.code}`, err));
            setMarketIndexError('시장 지수 데이터 파싱 중 오류가 발생했습니다. 자세한 내용은 콘솔을 확인하세요.');
            setIsLoadingMarketIndex(false);
            return;
          }
          if (!results.data || results.data.length === 0) {
            console.warn(`[${marketType}] CSV 파싱 후 데이터가 비어있습니다.`);
            setMarketIndexData([]);
            setMarketIndexLoaded(true);
            setIsLoadingMarketIndex(false);
            return;
          }

          try {
            const processedData = results.data
              .map((row: any, rowIndex: number) => {
                // CSV 헤더 이름의 다양성을 고려 (예: '날짜', 'Date', '일자' 등)
                const dateValue = row['날짜'] || row['Date'] || row['일자'];
                // CSV 헤더 이름의 다양성을 고려 (예: '종가', 'Close', '기준가' 등)
                const closeValue = row['종가'] || row['Close'] || row['기준가'];

                if (!dateValue) {
                  // console.warn(`[${marketType}] ${rowIndex}번째 행에 날짜 데이터가 없습니다.`, row);
                  return null;
                }
                if (closeValue === undefined || closeValue === null || closeValue === '') {
                  // console.warn(`[${marketType}] ${rowIndex}번째 행에 종가 데이터가 없거나 비어있습니다.`, row);
                  return null;
                }

                let numericValue: number;
                if (typeof closeValue === 'string') {
                  const cleanedString = closeValue.replace(/,/g, ''); // 쉼표 제거
                  numericValue = parseFloat(cleanedString);
                } else if (typeof closeValue === 'number') {
                  numericValue = closeValue;
                } else {
                  console.warn(`[${marketType}] ${rowIndex}번째 행의 종가(${closeValue})가 숫자나 문자열이 아닙니다.`, typeof closeValue);
                  return null;
                }

                // 날짜 유효성 검사 (YYYY-MM-DD 형식)
                if (!/\d{4}-\d{2}-\d{2}/.test(dateValue)) {
                  console.warn(`[${marketType}] ${rowIndex}번째 행의 날짜(${dateValue}) 형식이 'YYYY-MM-DD'가 아닙니다.`);
                  return null;
                }
                const timeAsDate = new Date(dateValue);
                if (isNaN(timeAsDate.getTime())) {
                  console.warn(`[${marketType}] ${rowIndex}번째 행의 날짜(${dateValue})를 Date 객체로 변환할 수 없습니다.`);
                  return null;
                }

                if (isNaN(numericValue)) {
                  // console.warn(`[${marketType}] ${rowIndex}번째 행의 종가(${closeValue})를 숫자로 변환할 수 없습니다.`);
                  return null;
                }

                return { time: dateValue as Time, value: numericValue }; // 'YYYY-MM-DD' 형식 유지
              })
              .filter(item => item !== null && item.value > 0) // null 값 및 0 이하 값 제거
              .sort((a, b) => new Date(a!.time as string).getTime() - new Date(b!.time as string).getTime()); // 시간 오름차순 정렬
            
            console.log(`[${marketType}] 최종 처리된 시장 지수 데이터 개수: ${processedData.length}. (샘플 3개: ${JSON.stringify(processedData.slice(0,3))})`);
            setMarketIndexData(processedData as LineData<Time>[]);
            setMarketIndexLoaded(true);
          } catch (processingError) {
            console.error(`[${marketType}] 파싱된 데이터 처리 중 오류:`, processingError);
            setMarketIndexError(`파싱된 시장 지수 데이터 처리 중 오류가 발생했습니다: ${processingError instanceof Error ? processingError.message : String(processingError)}`);
          }
        },
        error: (error: Error) => {
          console.error(`[${marketType}] CSV 파싱 중 심각한 오류 발생:`, error);
          setMarketIndexError(`시장 지수 데이터 파싱 중 심각한 오류가 발생했습니다: ${error.message}`);
        }
      });
    } catch (fetchError) {
      console.error(`[${marketType}] 시장 지수 데이터 가져오기 또는 처리 중 오류:`, fetchError);
      setMarketIndexError(`시장 지수 데이터를 가져오는 중 오류가 발생했습니다: ${fetchError instanceof Error ? fetchError.message : String(fetchError)}`);
    } finally {
      setIsLoadingMarketIndex(false);
      console.log(`[${marketType}] 시장 지수 데이터 가져오기 완료 (로딩 상태: ${isLoadingMarketIndex}, 로드됨: ${marketIndexLoaded})`);
    }
  }, [marketType]); // parentComponent는 현재 경로 결정에 직접 사용되지 않으므로 의존성 배열에서 제외 가능


  // 차트 생성 및 데이터 설정 useEffect
  useEffect(() => {
    if (!data || data.length === 0 || !chartContainerRef.current) {
      return undefined;
    }
    
    let cleanupFunction = () => {};
    
    // 자동 리사이즈 핸들러 함수 정의 (try 블록 밖으로 이동)
    const handleResize = () => {
      if (chartRef.current && chartContainerRef.current) {
        chartRef.current.applyOptions({
          width: chartContainerRef.current.clientWidth,
        });
      }
    };
    
    try {
      // 시장 구분 정규화
      const normalizedMarketType = marketType ? marketType.toUpperCase() : 'KOSPI';

      // 1. 데이터 가공 및 검증
      const validData = data
        .filter(item => 
          item && 
          item.time && 
          item.open !== undefined && 
          item.high !== undefined && 
          item.low !== undefined && 
          item.close !== undefined && 
          !isNaN(item.open) && 
          !isNaN(item.high) && 
          !isNaN(item.low) && 
          !isNaN(item.close)
        )
        .sort((a, b) => {
          const timeA = typeof a.time === 'string' ? new Date(a.time).getTime() : Number(a.time) * 1000;
          const timeB = typeof b.time === 'string' ? new Date(b.time).getTime() : Number(b.time) * 1000;
          return timeA - timeB;
        })
        .map(item => {
          // 타임스킬프 변환: 문자열 형식의 날짜는 UNIX 타임스킬프(초)로 변환
          let timeValue: Time;
          
          if (typeof item.time === 'string') {
            // 날짜 문자열을 UNIX 타임스킬프(초)로 변환
            timeValue = Math.floor(new Date(item.time).getTime() / 1000) as Time;
          } else {
            // 이미 숫자 타입인 경우 그대로 사용
            timeValue = item.time;
          }
          
          return {
            time: timeValue,
            open: item.open,
            high: item.high,
            low: item.low,
            close: item.close,
            volume: item.volume
          };
        });
      
      // 2. 거래량 데이터 분리 (필요한 경우)
      const volumeData = showVolume 
        ? validData
          .filter(item => item.volume !== undefined && !isNaN(Number(item.volume)))
          .map(item => {
            // 캔들 색상과 일치하는 거래량 막대 색상 설정
            let barColor = 'rgba(156, 163, 175, 0.8)'; // 기본(동일) 색상: Tailwind Gray 400
            if (item.close > item.open) {
              barColor = 'rgba(248, 113, 113, 0.8)'; // 상승 시: Tailwind Red 400 (#F87171)
            } else if (item.close < item.open) {
              barColor = 'rgba(96, 165, 250, 0.8)'; // 하락 시: Tailwind Blue 400 (#60A5FA)
            }
            
            return {
              time: item.time,
              value: Number(item.volume),
              color: barColor
            };
          })
        : [];
      
      // 3. 차트 설정 옵션
      const chartOptions: DeepPartial<ChartOptions> = {
        width: chartContainerRef.current.clientWidth,
        height,
        layout: {
          background: { type: ColorType.Solid, color: 'white' },
          textColor: '#333',
          fontFamily: 'Pretendard, -apple-system, BlinkMacSystemFont, system-ui, Roboto, sans-serif',
          fontSize: 12,
        },
        grid: {
          vertLines: { visible: false },
          horzLines: { color: 'rgba(197, 203, 206, 0.3)' },
        },
        crosshair: {
          mode: CrosshairMode.Normal,
          vertLine: {
            color: '#758696',
            width: 1,
            style: LineStyle.LargeDashed,
            labelBackgroundColor: '#758696',
          },
          horzLine: {
            color: '#758696',
            width: 1,
            style: LineStyle.LargeDashed,
            labelBackgroundColor: '#758696',
          },
        },
        rightPriceScale: {
          borderColor: 'rgba(197, 203, 206, 0.8)',
          entireTextOnly: true,
        },
        timeScale: {
          borderColor: 'rgba(197, 203, 206, 0.8)',
          timeVisible: true,
          secondsVisible: false,
          // 일봉 차트에 최적화된 설정 - 주봉처럼 보이지 않도록 간격 좁힘
          rightOffset: 3,
          barSpacing: 3,  // 더 좁은 간격으로 설정 (기존 10)
          minBarSpacing: 2,  // 최소 간격도 좁게 설정 (기존 5)
          fixLeftEdge: true,
          fixRightEdge: true,
          rightBarStaysOnScroll: true,
          borderVisible: true,
          visible: true,
          ticksVisible: true,
          tickMarkFormatter: (time: Time, tickMarkType: TickMarkType, locale: string) => {
            const date = new Date(Number(time) * 1000);
            const year = date.getFullYear();
            const month = (date.getMonth() + 1).toString().padStart(2, '0');
            const day = date.getDate().toString().padStart(2, '0');
            
            // 일봉 차트에 맞게 더 상세한 날짜 표시
            if (tickMarkType === TickMarkType.Year) {
              return `${year}`;
            } else if (tickMarkType === TickMarkType.Month) {
              return `${month}월`;
            } else if (tickMarkType === TickMarkType.DayOfMonth) {
              return `${month}.${day}`;
            }
            
            // 기본적으로 더 상세한 날짜 표시
            return `${month}.${day}`;
          },
        },
        localization: {
          locale: 'ko-KR',
          priceFormatter: (price: number) => {
            return Math.round(price).toLocaleString('ko-KR');
          },
          timeFormatter: (originalTime: number) => {
            const date = new Date(originalTime * 1000); // lightweight-charts는 초 단위 timestamp를 사용
            const year = date.getFullYear().toString().slice(-2); // 'yy'
            const month = (date.getMonth() + 1).toString().padStart(2, '0'); // 'mm'
            const day = date.getDate().toString().padStart(2, '0'); // 'dd'
            return `${year}년 ${month}월 ${day}일`;
          },
        },
      };

      const chart = createChart(chartContainerRef.current, chartOptions);
      chartRef.current = chart;
      
      const candleSeries = chart.addSeries(CandlestickSeries, {
        priceFormat: {
          type: 'price',
          precision: 0, // 소수점 제거
          minMove: 1,   // 최소 가격 변동 단위
        },
        // 한국식 캔들 색상 설정 (상승 시 빨간색, 하락 시 파란색)
        upColor: '#F87171',       // 상승 시 Tailwind Red 400
        downColor: '#60A5FA',     // 하락 시 Tailwind Blue 400
        borderUpColor: '#F87171', // 상승 시 테두리 색상
        borderDownColor: '#60A5FA', // 하락 시 테두리 색상
        wickUpColor: '#F87171',   // 상승 시 꼬리 색상
        wickDownColor: '#60A5FA'  // 하락 시 꼬리 색상
      });
      candlestickSeriesRef.current = candleSeries;
      
      // 캔들 데이터 설정
      candleSeries.setData(validData);
      
      // 거래량 차트 추가 (showVolume이 true인 경우)
      if (showVolume && volumeData.length > 0) {
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
        
        volumeSeries.setData(volumeData);
      }
      
      // 시장 지수 데이터가 있고, marketType이 정의된 경우에만 라인 시리즈 추가
      // BreakoutSustainChart에서는 시장 지수 라인을 표시하지 않음
      if (marketType && marketIndexData && marketIndexData.length > 0 && parentComponent !== 'BreakoutSustainChart' && parentComponent !== 'BreakoutFailChart' && parentComponent !== 'BreakoutCandidatesChart') {
        console.log(`시장 지수 데이터 처리 시작 - 총 ${marketIndexData.length}개 항목`);
        
        // 시장 지수를 표시할 단위 파스텔 계열 색상 설정
        // KOSPI와 KOSDAQ 모두 동일한 색상으로 통일 (파스텔 계열 파란색)
        const indexColor = '#14B8A6';
        
        // 선 차트 추가 - 더 두꺼운 선과 더 뿜리한 색상으로 설정
        const lineSeries = chart.addSeries(LineSeries, {
          color: indexColor,
          lineWidth: 2,
          lineStyle: LineStyle.Solid,
          priceScaleId: 'market-index',  // 별도의 스케일 ID 사용
          title: '', // 라벨 제거
          lastValueVisible: false, // 마지막 값 라벨 숨김
          priceLineVisible: false, // 가격 라인 숨김
        });
        lineSeriesRef.current = lineSeries;
        
        // 시장 지수 데이터 처리 시작
        console.log('원본 시장 지수 데이터 (상위 3개):', JSON.stringify(marketIndexData.slice(0, 3)));

        const startTimestamp = Math.floor(new Date('2025-04-01').getTime() / 1000);
        const endTimestamp = Math.floor(new Date('2025-05-20').getTime() / 1000);
        console.log(`데이터 필터링 기간: ${new Date(startTimestamp * 1000).toLocaleDateString()} ~ ${new Date(endTimestamp * 1000).toLocaleDateString()}`);

        const processedMarketData = marketIndexData.map(item => {
          let timestamp: number | undefined;
          if (typeof item.time === 'string') {
            const date = new Date(item.time);
            if (!isNaN(date.getTime())) {
              timestamp = date.getTime() / 1000;
            } else {
              console.warn('잘못된 날짜 문자열 형식의 시장 지수 데이터:', item.time);
            }
          } else if (typeof item.time === 'number') {
            timestamp = item.time; // 이미 초 단위 타임스탬프라고 가정
          } else {
            console.warn('알 수 없는 시간 형식의 시장 지수 데이터:', item);
          }

          let value: number | undefined;
          // marketIndexData의 value는 fetchMarketIndexData에서 이미 number로 변환되었어야 합니다.
          // 따라서 string 타입 체크 및 .replace() 호출은 불필요하며 오류의 원인이 될 수 있습니다.
          if (typeof item.value === 'number') {
            value = item.value;
          } else {
            // 이 블록은 item.value가 number가 아닌 예외적인 경우를 처리합니다.
            // 예를 들어, fetchMarketIndexData에서 파싱에 실패하여 item.value가 undefined로 설정되었을 수 있습니다.
            // 또는 예상치 못한 타입의 데이터가 marketIndexData에 포함된 경우입니다.
            console.warn(`[ChartComponentDaily useEffect] marketIndexData item.value가 숫자 타입이 아닙니다. item:`, item);
            // value를 undefined로 설정하여 이후 filter에서 제외되도록 합니다.
            value = undefined; 
          }

          if (timestamp !== undefined && value !== undefined) {
            return { time: timestamp as Time, value };
          }
          return null;
        }).filter(item => {
          if (item === null) return false;
          const RtnTimestamp = typeof item.time === 'number' ? item.time : new Date(String(item.time)).getTime() / 1000;
          return RtnTimestamp >= startTimestamp && RtnTimestamp <= endTimestamp;
        }) as LineData<Time>[];

        if (processedMarketData.length > 0) {
          console.log('처리 및 필터링된 시장 지수 데이터 (상위 3개):', JSON.stringify(processedMarketData.slice(0, 3)));
          console.log(`처리 및 필터링된 시장 지수 데이터 총 개수: ${processedMarketData.length}`);

          chart.priceScale('market-index').applyOptions({
            visible: true,
            autoScale: true,
            mode: 0, // Normal
            invertScale: false,
            alignLabels: true,
            borderVisible: true,
            borderColor: indexColor,
            entireTextOnly: false,
            scaleMargins: { top: 0.1, bottom: 0.25 }, // 하단 마진 약간 조정
          });
          console.log('시장 지수 priceScale(\'market-index\') 옵션 적용 완료');

          lineSeries.setData(processedMarketData);
          console.log('라인 시리즈에 시장 지수 데이터 설정 완료.');
          const seriesData = lineSeries.data();
          console.log(`시리즈에 설정된 실제 데이터 개수: ${seriesData.length}`);
          if (seriesData.length > 0) {
            console.log('시리즈 데이터 샘플 (상위 3개):', JSON.stringify(seriesData.slice(0, 3)));
          }
        } else {
          console.log('시장 지수 데이터가 없거나 marketType이 정의되지 않았거나 BreakoutSustainChart, BreakoutFailChart 또는 BreakoutCandidatesChart에서 호출되어 라인 시리즈를 추가하지 않습니다.');
          // 시장 지수 데이터가 없을 경우 또는 BreakoutSustainChart일 경우 가격 스케일 숨김
          chart.priceScale('market-index').applyOptions({ visible: false });
        }
      }
      
      // 돌파 가격 라인 추가
      if (breakthroughPrice !== undefined && candlestickSeriesRef.current) {
        console.log(`[ChartComponentDaily] 종목: ${stockName}, 돌파 가격(${breakthroughPrice}) 라인 생성 시도.`);
        candlestickSeriesRef.current.createPriceLine({
          price: breakthroughPrice,
          color: 'rgba(0, 150, 136, 0.7)', // KOSDAQ 지수 색상 (청록색/초록색 계열)
          lineWidth: 2, // 선 굵기 2로 변경
          lineStyle: LineStyle.Dashed,
          axisLabelVisible: true,
          title: '', // 라인 위의 '돌파' 텍스트 라벨 제거 (가격은 계속 표시됨)
        });
      } else {
        if (breakthroughPrice === undefined) {
          console.log(`[ChartComponentDaily] 종목: ${stockName}, breakthroughPrice가 undefined이므로 돌파 라인을 생성하지 않습니다.`);
        }
        if (!candlestickSeriesRef.current) {
          console.log(`[ChartComponentDaily] 종목: ${stockName}, candlestickSeries가 없으므로 돌파 라인을 생성하지 않습니다.`);
        }
      }

      // 20일 이동평균선 추가 (shouldShowMA20이 true인 경우)
      if (shouldShowMA20 && validData.length > 0) {
        const ma20Data = calculateMA20(validData);
        
        const ma20Series = chart.addSeries(LineSeries, {
          color: 'rgba(255, 153, 0, 0.8)',
          lineWidth: 1,
          lineStyle: LineStyle.Solid,
          priceScaleId: 'right',
          lastValueVisible: false,
          priceLineVisible: false,
        });
        ma20SeriesRef.current = ma20Series;
        
        ma20Series.setData(ma20Data);
        
        // MA20 레전드 생성
        const container = chartContainerRef.current;
        const ma20Legend = document.createElement('div');
        ma20Legend.className = 'ma20-legend';
        ma20Legend.style.position = 'absolute';
        ma20Legend.style.top = '5px';
        ma20Legend.style.right = '10px';
        ma20Legend.style.zIndex = '2';
        ma20Legend.style.fontSize = '12px';
        ma20Legend.style.color = 'rgba(255, 153, 0, 0.8)';
        ma20Legend.style.fontWeight = 'bold';
        ma20Legend.innerText = 'MA20';
        
        container.appendChild(ma20Legend);
      }
      
      // 모든 데이터가 로드된 후 차트 내용을 화면에 맞춤
      chart.timeScale().fitContent();

      // 자동 리사이즈 이벤트 리스너 등록
      window.addEventListener('resize', handleResize);
      
      // 이벤트 리스너 및 정리 함수 선언
      cleanupFunction = () => {
        window.removeEventListener('resize', handleResize);
        if (chartRef.current) {
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
  }, [data, height, showVolume, marketType, marketIndexData, shouldShowMA20, parentComponent]);
  
  // 시장 지수 데이터 로드 useEffect
  useEffect(() => {
    // BreakoutSustainChart에서는 시장 지수 데이터를 로드하지 않음
    if (marketType && !marketIndexLoaded && !isLoadingMarketIndex && parentComponent !== 'BreakoutSustainChart' && parentComponent !== 'BreakoutFailChart' && parentComponent !== 'BreakoutCandidatesChart') {
      fetchMarketIndexData();
    }
  }, [marketType, marketIndexLoaded, isLoadingMarketIndex, fetchMarketIndexData, parentComponent]);

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
      {breakthroughPrice !== undefined && !isNaN(breakthroughPrice) && (
        <div
          style={{
            position: 'absolute',
            top: title ? (subtitle ? '45px' : '25px') : (subtitle ? '25px' : '5px'), // title, subtitle 유무에 따라 위치 조정
            left: '10px',
            color: 'rgba(0, 150, 136, 1)', // 돌파 라인 색상 (투명도 없음)
            fontSize: 'clamp(0.65rem, 0.8vw, 0.8rem)',
            fontWeight: '700', // 텍스트를 더 진하게 (bold)
            zIndex: 10,
            pointerEvents: 'none',
          }}
        >
          돌파
        </div>
      )}
    </div>
  );
};

export default ChartComponentDaily;
