'use client'

import { useState, useEffect, useMemo, useRef } from 'react'
import ChartComponent from './ChartComponent'
import { fetchCSVData } from '../utils/fetchCSVData'
import Papa from 'papaparse'

// 차트 데이터 타입 정의
interface CandleData {
  time: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

// ETF 정보 타입 정의
interface ETFInfo {
  name: string;
  code: string;
  chartData: CandleData[];
  isLoading: boolean;
  error: string;
  isAboveMA20: boolean;  // null 타입 제거
  durationDays: number;  // null 타입 제거
  changePercent: number;
}

// 산업 차트 컴포넌트
export default function IndustryCharts() {
  // ETF 정보 상태
  const [etfInfoList, setEtfInfoList] = useState<ETFInfo[]>([]);
  const [stockPriceData, setStockPriceData] = useState<{[key: string]: number[]}>({});
  const [chartDataMap, setChartDataMap] = useState<Record<string, CandleData[]>>({});
  const [selectedStocksChartMap, setSelectedStocksChartMap] = useState<Record<string, CandleData[]>>({});
  const [processedStocks, setProcessedStocks] = useState<string[]>([]);
  const [selectedStockCodes, setSelectedStockCodes] = useState<string[]>([]);
  
  // 차트 컨테이너 ref 추가
  const chartRefs = useRef<{[key: string]: HTMLDivElement | null}>({});
  
  // 산업-ETF 매핑 데이터
  const industryETFMapping = [
    { name: '반도체', code: '091160' },
    { name: '반도체 전공정', code: '475300' },
    { name: '반도체 후공정', code: '475310' },
    { name: '2차전지', code: '364980' },
    { name: '전력기기', code: '487240' },
    { name: '에너지', code: '433500' },
    { name: '태양광/ESS', code: '457990' },
    { name: '2차전지 소부장', code: '455860' },
    { name: '조선', code: '466920' },
    { name: '운송', code: '140710' },
    { name: '자동차', code: '091180' },
    { name: '자동차 소부장', code: '464600' },
    { name: '로봇', code: '445290' },
    { name: '바이오', code: '463050' },
    { name: '바이오(코스닥)', code: '227540' },
    { name: '의료기기', code: '464610' },
    { name: '인터넷', code: '365000' },
    { name: '엔터', code: '475050' },
    { name: '여행레저', code: '228800' },
    { name: '게임', code: '364990' },
    { name: '방산/우주', code: '463250' },
    { name: '철강', code: '139240' },
    { name: '석유', code: '139250' },
    { name: '은행', code: '091170' },
    { name: '증권', code: '102970' },
    { name: '보험', code: '140700' },
    { name: '화장품', code: '479850' },
    { name: '음식료', code: '438900' }
  ];
  
  useEffect(() => {
    // 초기 ETF 정보 설정
    const initialETFInfoList = industryETFMapping.map(item => ({
      name: item.name,
      code: item.code,
      chartData: [],
      isLoading: true,
      error: '',
      isAboveMA20: false, // 기본값 false
      durationDays: 0, // 기본값 0
      changePercent: 0
    }));
    
    setEtfInfoList(initialETFInfoList);
    
    // 모든 ETF 데이터 로드
    loadAllETFData();
  }, []);
  
  // 모든 ETF 데이터 로드 함수
  const loadAllETFData = async () => {
    try {
      // 모든 ETF 코드 추출
      const etfCodes = industryETFMapping.map(item => item.code);
      
      // 각 ETF별 차트 데이터 로드
      await Promise.all(
        etfCodes.map((code, index) => loadETFChartData(code, index))
      );
      
      // 모든 ETF의 종가 데이터 로드 (20일선 계산용)
      await loadAllPriceData(etfCodes);
      
      // 20일선 계산 및 정렬
      calculateMA20AndSort();
    } catch (error) {
      console.error('ETF 데이터 로드 오류:', error);
    }
  };
  
  // ETF 차트 데이터 로드 함수
  const loadETFChartData = async (code: string, index: number) => {
    try {
      // 로딩 상태 설정
      setEtfInfoList(prev => {
        const newList = [...prev];
        newList[index] = { ...newList[index], isLoading: true, error: '' };
        return newList;
      });

      const csvFilePath = `/rs_etf/${code}.csv`;
      const response = await fetch(csvFilePath);
      
      if (!response.ok) {
        throw new Error(`CSV 파일을 찾을 수 없음: ${csvFilePath}`);
      }
      
      const csvText = await response.text();
      const chartData = parseChartData(csvText);
      
      // 차트 데이터 저장
      chartDataMap[code] = chartData;
      
      // 등락율 계산
      const changePercent = calculateChangePercent(code);
      
      // 상태 업데이트
      setEtfInfoList(prev => {
        const newList = [...prev];
        newList[index] = {
          ...newList[index],
          chartData,  // chartData 설정
          isLoading: false,
          error: '',
          changePercent
        };
        return newList;
      });
      
      return chartData;
    } catch (error) {
      console.error(`ETF 데이터 로드 오류 (${code}):`, error);
      
      // 오류 상태 업데이트
      setEtfInfoList(prev => {
        const newList = [...prev];
        newList[index] = {
          ...newList[index],
          chartData: [], // 빈 배열로 초기화
          isLoading: false,
          error: error instanceof Error ? error.message : '알 수 없는 오류',
          changePercent: 0
        };
        return newList;
      });
      
      return [];
    }
  };
  
  // 모든 ETF의 종가 데이터 로드 (20일선 계산용)
  const loadAllPriceData = async (tickers: string[]) => {
    const priceData: {[key: string]: number[]} = {};
    
    await Promise.all(
      tickers.map(async (ticker) => {
        try {
          const response = await fetch(`/rs_etf/${ticker}.csv`);
          if (response.ok) {
            const csvText = await response.text();
            const result = Papa.parse(csvText, { header: true });
            
            // 종가 데이터 추출
            const closePrices = result.data
              .filter((row: any) => row['종가'] && !isNaN(parseFloat(row['종가'])))
              .map((row: any) => parseFloat(row['종가']));
            
            if (closePrices.length > 0) {
              priceData[ticker] = closePrices;
            }
          }
        } catch (error) {
          console.error(`${ticker} 종가 데이터 로드 오류:`, error);
        }
      })
    );
    
    setStockPriceData(priceData);
    return priceData;
  };
  
  // 20일선 계산 및 정렬
  const calculateMA20AndSort = () => {
    setEtfInfoList(prev => {
      const newList = [...prev].map(etf => {
        // 20일선 위/아래 여부 및 유지 기간 계산
        const { isAboveMA20, durationDays } = calculate20DayMAStatus(etf.code);
        
        return {
          ...etf,
          isAboveMA20,
          durationDays
        };
      });
      
      // 정렬: 20일선 위에 있는 종목을 유지 기간 내림차순으로, 아래에 있는 종목을 20일선과의 근접도 순으로
      return newList.sort((a, b) => {
        // 둘 다 20일선 위에 있는 경우 -> 유지 기간 내림차순
        if (a.isAboveMA20 === true && b.isAboveMA20 === true) {
          return (b.durationDays || 0) - (a.durationDays || 0);
        }
        
        // 둘 다 20일선 아래에 있는 경우 -> 20일선과의 근접도 오름차순
        if (a.isAboveMA20 === false && b.isAboveMA20 === false) {
          return calculateMA20Proximity(a.code) - calculateMA20Proximity(b.code);
        }
        
        // 하나는 위, 하나는 아래에 있는 경우 -> 위에 있는 것이 우선
        return a.isAboveMA20 === true ? -1 : 1;
      });
    });
  };
  
  // 20일선 상태 계산
  const calculate20DayMAStatus = (ticker: string): { isAboveMA20: boolean; durationDays: number } => {
    try {
      const chartData = chartDataMap[ticker];
      if (!chartData || chartData.length < 20) {
        return { isAboveMA20: false, durationDays: 0 };
      }

      // 최근 20일 종가 데이터
      const recentData = chartData.slice(-20);
      const currentPrice = recentData[recentData.length - 1].close;
      const ma20 = recentData.reduce((sum, data) => sum + data.close, 0) / 20;
      const isAboveMA = currentPrice > ma20;

      // 연속일수 계산
      let durationDays = 1;
      for (let i = chartData.length - 2; i >= 0; i--) {
        const price = chartData[i].close;
        const prevMA20 = chartData.slice(Math.max(0, i - 19), i + 1).reduce((sum, data) => sum + data.close, 0) / Math.min(20, i + 1);
        
        if ((price > prevMA20) !== isAboveMA) {
          break;
        }
        durationDays++;
      }

      return { isAboveMA20: isAboveMA, durationDays };
    } catch (error) {
      console.error(`20일선 상태 계산 오류 (${ticker}):`, error);
      return { isAboveMA20: false, durationDays: 0 };
    }
  };
  
  // 20일선과의 근접도 계산 (낮을수록 더 가까움)
  const calculateMA20Proximity = (ticker: string): number => {
    if (!ticker || !stockPriceData[ticker] || stockPriceData[ticker].length < 20) {
      return Number.MAX_SAFE_INTEGER; // 데이터가 없으면 가장 낮은 우선순위
    }
    
    try {
      // 최근 데이터 추출
      const recentData = stockPriceData[ticker];
      
      // 현재가 (가장 최근 데이터)
      const currentPrice = recentData[recentData.length - 1];
      
      // 20일 이동평균 계산
      const ma20 = recentData.slice(-20).reduce((acc, val) => acc + val, 0) / 20;
      
      // 현재가와 20일 이동평균선의 차이 (절대값)
      return Math.abs((currentPrice - ma20) / ma20 * 100);
    } catch (error) {
      console.error(`20일선 근접도 계산 오류 (${ticker}):`, error);
      return Number.MAX_SAFE_INTEGER;
    }
  };
  
  // 등락율 계산
  const calculateChangePercent = (ticker: string): number => {
    try {
      // 이미 로드된 차트 데이터 사용
      const chartData = chartDataMap[ticker];
      if (!chartData || chartData.length === 0) {
        console.error(`차트 데이터가 비어있음: ${ticker}`);
        return 0;
      }
      
      // 가장 최근 데이터 가져오기
      const latestData = chartData[chartData.length - 1];
      
      // 시가와 종가로 등락율 계산
      const openPrice = latestData.open;
      const closePrice = latestData.close;
      
      // 시가가 0이거나 유효하지 않은 경우 0 반환
      if (openPrice === 0 || !openPrice || isNaN(openPrice)) {
        console.warn(`유효하지 않은 시가 (${ticker}): ${openPrice}`);
        return 0;
      }
      
      // 등락률 계산 및 소수점 제한 (무한대 값 방지)
      const changePercent = ((closePrice - openPrice) / openPrice) * 100;
      
      // 무한대 값 체크
      if (!isFinite(changePercent)) {
        console.warn(`무한대 등락률 감지 (${ticker}): ${changePercent}`);
        return 0;
      }
      
      return changePercent;
    } catch (error) {
      console.error(`등락율 계산 오류 (${ticker}):`, error);
      return 0;
    }
  };
  
  // CSV 데이터를 차트 데이터로 파싱하는 함수
  const parseChartData = (csvText: string): CandleData[] => {
    try {
      // CSV 파싱 (간단한 구현, 실제로는 더 복잡할 수 있음)
      const lines = csvText.trim().split('\n');
      const headers = lines[0].split(',');
      
      // 헤더 인덱스 찾기
      const dateIndex = headers.findIndex(h => h.includes('날짜') || h.includes('Date'));
      const openIndex = headers.findIndex(h => h.includes('시가') || h.includes('Open'));
      const highIndex = headers.findIndex(h => h.includes('고가') || h.includes('High'));
      const lowIndex = headers.findIndex(h => h.includes('저가') || h.includes('Low'));
      const closeIndex = headers.findIndex(h => h.includes('종가') || h.includes('Close'));
      const volumeIndex = headers.findIndex(h => h.includes('거래량') || h.includes('Volume'));
      
      // 데이터 변환
      const chartData: CandleData[] = [];
      
      for (let i = 1; i < lines.length; i++) {
        const values = lines[i].split(',');
        
        if (values.length >= Math.max(dateIndex, openIndex, highIndex, lowIndex, closeIndex, volumeIndex) + 1) {
          chartData.push({
            time: values[dateIndex],
            open: parseFloat(values[openIndex]),
            high: parseFloat(values[highIndex]),
            low: parseFloat(values[lowIndex]),
            close: parseFloat(values[closeIndex]),
            volume: parseFloat(values[volumeIndex])
          });
        }
      }
      
      return chartData;
    } catch (error) {
      console.error('차트 데이터 파싱 오류:', error);
      return generateSampleChartData();
    }
  };
  
  // 샘플 차트 데이터 생성 함수
  const generateSampleChartData = (): CandleData[] => {
    const data: CandleData[] = [];
    const today = new Date();
    
    // 최근 60일 데이터 생성
    for (let i = 60; i >= 0; i--) {
      const date = new Date(today);
      date.setDate(today.getDate() - i);
      
      // 주말 제외
      if (date.getDay() === 0 || date.getDay() === 6) continue;
      
      const formattedDate = date.toISOString().split('T')[0]; // YYYY-MM-DD 형식
      
      // 이전 종가 또는 초기값
      const prevClose = data.length > 0 ? data[data.length - 1].close : 10000;
      
      // 가격 변동 (-3% ~ +3%)
      const changePercent = (Math.random() * 6) - 3;
      const close = Math.round(prevClose * (1 + changePercent / 100));
      
      // 일중 변동폭
      const dayRange = close * 0.02; // 2% 범위
      const high = Math.round(close + (Math.random() * dayRange));
      const low = Math.round(close - (Math.random() * dayRange));
      const open = Math.round(low + (Math.random() * (high - low)));
      
      // 거래량 (100,000 ~ 1,000,000)
      const volume = Math.round(100000 + Math.random() * 900000);
      
      data.push({
        time: formattedDate,
        open,
        high,
        low,
        close,
        volume
      });
    }
    
    return data;
  };
  
  // 헤더 배경색 결정 함수
  const getHeaderBackgroundColor = (etf: ETFInfo): string => {
    if (etf.isAboveMA20 === true) {
      return 'bg-green-100 border-green-200'; // 20일선 위에 있는 경우 (유지)
    } else if (etf.isAboveMA20 === false) {
      return 'bg-yellow-100 border-yellow-200'; // 20일선 아래에 있는 경우 (이탈)
    }
    return 'bg-gray-100 border-gray-200'; // 상태를 알 수 없는 경우
  };
  
  // 상태 텍스트 가져오기
  const getStatusText = (etf: ETFInfo) => {
    if (etf.isLoading) return '상태 확인 중';
    return `${etf.isAboveMA20 ? '유지' : '이탈'} +${etf.durationDays}일`;
  };
  
  // 정렬된 ETF 목록 계산
  const sortedETFInfoList = useMemo(() => {
    return [...etfInfoList];
  }, [etfInfoList]);
  
  return (
    <div className="p-4">
      {/* 차트 제목 및 설명 추가 */}
      <div className="mb-4">
        <h2 className="text-xl font-bold mb-2">산업별 주도ETF 차트</h2>
        <p className="text-sm text-gray-600">
          각 산업별 ETF의 20일 이동평균선 기준 상태와 등락률을 확인할 수 있습니다. 
          녹색 배경은 20일선 위에 있는 ETF, 노란색 배경은 20일선 아래에 있는 ETF를 나타냅니다.
          각 ETF는 등락률 기준으로 내림차순 정렬되어 있습니다.
        </p>
      </div>
      
      <div className="grid grid-cols-1 md:grid-cols-4 gap-2">
        {[...etfInfoList]
          .sort((a, b) => b.changePercent - a.changePercent)
          .map((etf, index) => (
          <div key={index} className="flex-1 rounded-md p-1">
            <div>
              <div className={`px-3 py-1 border flex justify-between items-center ${getHeaderBackgroundColor(etf)}`} style={{ borderRadius: '0.375rem 0.375rem 0 0' }}>
                <div className="flex items-center gap-2">
                  <span className="font-medium text-sm">{etf.name}</span>
                  <span className={`text-xs px-1.5 py-0.5 rounded ${etf.changePercent >= 0 ? 'text-red-600' : 'text-blue-600'}`}>
                    {etf.changePercent >= 0 ? '+' : ''}{etf.changePercent.toFixed(2)}%
                  </span>
                </div>
                <div className="flex items-center gap-1">
                  {etf.isLoading ? (
                    <span className="text-xs px-1.5 py-0.5 rounded bg-gray-100 text-gray-800">
                      로딩 중...
                    </span>
                  ) : (
                    <span className={`text-xs px-1.5 py-0.5 rounded ${etf.isAboveMA20 ? 'bg-green-100 text-green-800' : 'bg-yellow-100 text-yellow-800'}`}>
                      {getStatusText(etf)}
                    </span>
                  )}
                </div>
              </div>
              
              <div className="border border-t-0 border-gray-200" style={{ borderRadius: '0 0 0.375rem 0.375rem', overflow: 'hidden' }}>
                <div ref={(el) => { chartRefs.current[etf.code] = el; }}>
                  <ChartComponent
                    data={etf.chartData}
                    height={300}
                    width="100%"
                    showVolume={true}
                    showMA20={true}
                    title={`${etf.name} (${etf.code})`}
                    subtitle={`${getStatusText(etf)} | 등락률: ${etf.changePercent >= 0 ? '+' : ''}${etf.changePercent.toFixed(2)}%`}
                    parentComponent="IndustryCharts"
                  />
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
