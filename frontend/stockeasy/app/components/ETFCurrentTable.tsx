'use client'

import { useState, useEffect, useMemo, useCallback, useRef } from 'react'
import Papa from 'papaparse'
import React from 'react';
import { Sparklines, SparklinesLine, SparklinesSpots, SparklinesReferenceLine, SparklinesBars } from 'react-sparklines';
import { copyTableAsImage } from '../utils/tableCopyUtils';
import TableCopyButton from './TableCopyButton';
import { formatDateMMDD } from '../utils/dateUtils';

// CSV 데이터를 파싱한 결과를 위한 인터페이스
interface CSVData {
  headers: string[];
  rows: Record<string, any>[];
  groupedData: GroupedData;
  errors: any[];
}

// 그룹화된 데이터를 위한 인터페이스
interface GroupedData {
  [key: string]: Record<string, any>[];
}

// ETF 데이터를 위한 인터페이스
interface ETFData {
  code: string;
  name: string;
  price: number;
  change: number;
  changePercent: number;
  volume: number;
  marketCap: number; // 시가총액
}

// 스파크라인 차트를 위한 인터페이스
interface StockPriceData {
  [ticker: string]: { date: string; price: number }[];
}

// 정렬 타입 정의
type SortDirection = 'asc' | 'desc' | null;

// ETF 파일 정보
const ETF_FILES = {
  currentPrice: {
    fileId: '1u46PGtK4RY4vUOBIXzvrFsk_mUsxznbA',
    fileName: 'today_price_etf.csv',
    path: '/requestfile/today_price_etf'
  },
  stockList: {
    path: '/requestfile/etf_stocklist/etf_stocklist.csv'
  }
};

// CSV 파일 파싱 함수
function parseCSV(csvText: string): { headers: string[]; rows: Record<string, any>[]; groupedData: GroupedData; errors: any[] } {
  try {
    if (!csvText || typeof csvText !== 'string') {
      console.error('유효하지 않은 CSV 텍스트:', csvText);
      // 기본 데이터 반환
      return {
        headers: ['코드', '이름', '가격', '변동', '변동률', '거래량', '시가총액'],
        rows: [], 
        groupedData: {},
        errors: [],
      };
    }
    
    // CSV 텍스트의 처음 500자 로깅 (디버깅용)
    console.log('CSV 텍스트 샘플:', csvText.substring(0, 500));
    
    // Papa Parse 옵션
    const results = Papa.parse(csvText, {
      header: true,       // 첫 번째 행을 헤더로 사용
      skipEmptyLines: true, // 빈 줄 건너뛰기
      dynamicTyping: false,  // 문자열 그대로 유지 (수동 변환)
    });
    
    console.log('파싱 결과 헤더:', results.meta.fields);
    // 오류 로깅 방식 변경 - 실제 오류가 있을 때만 로깅
    if (results.errors && results.errors.length > 0) {
      console.error('파싱 중 실제 오류 발생:', results.errors);
    } else {
      console.log('CSV 파싱 성공, 오류 없음');
    }
    
    // 데이터가 없는 경우 처리
    if (!results.data || results.data.length === 0) {
      console.error('파싱된 데이터가 없습니다.');
      return {
        headers: results.meta.fields || [],
        rows: [], 
        groupedData: {},
        errors: [],
      };
    }
    
    // 첫 번째 행 로깅 (디버깅용)
    console.log('첫 번째 파싱된 행:', results.data[0]);

    // 산업별로 그룹화
    const groupedData: GroupedData = results.data.reduce((acc: GroupedData, row: any) => {
      // 빈 객체인 경우 건너뛰기
      if (!row || Object.keys(row).length === 0) {
        return acc;
      }
      
      // 업종 필드가 B열로 변경됨 (이전에는 E열로 잘못 설정)
      let industry = row['업종'] || row['산업'];
      if (!industry) {
        // 모든 키 출력 (디버깅용)
        console.log('업종 정보가 없는 행의 키:', Object.keys(row));
        industry = '기타'; // 업종 정보가 없는 경우 '기타'로 분류
      }
      
      // 뷰티와 음식료 카테고리를 소비재/음식료로 통합
      if (industry === '뷰티' || industry === '음식료' || industry === '소비재') {
        industry = '소비재/음식료';
      }
      
      if (!acc[industry]) {
        acc[industry] = [];
      }
      acc[industry].push(row);
      return acc;
    }, {});

    // 그룹화된 데이터 확인 (디버깅용)
    console.log('그룹화된 산업 목록:', Object.keys(groupedData));
    
    // 그룹 내에서 등락율 기준으로 정렬
    for (const industry in groupedData) {
      groupedData[industry].sort((a: any, b: any) => {
        try {
          // 등락율 필드명이 변경되었을 수 있으므로 확인
          const changeRateFieldA = a['등락율'] !== undefined ? '등락율' : (a['등락률'] !== undefined ? '등락률' : null);
          const changeRateFieldB = b['등락율'] !== undefined ? '등락율' : (b['등락률'] !== undefined ? '등락률' : null);
          
          // 필드가 없는 경우 처리
          if (changeRateFieldA === null || changeRateFieldB === null) {
            return 0;
          }
          
          const changeRateA = parseFloat((a[changeRateFieldA] || '0').replace('%', ''));
          const changeRateB = parseFloat((b[changeRateFieldB] || '0').replace('%', ''));
          
          if (isNaN(changeRateA) || isNaN(changeRateB)) {
            return 0;
          }
          
          return changeRateB - changeRateA; // 내림차순 정렬
        } catch (error) {
          console.error('정렬 중 오류:', error);
          return 0;
        }
      });
    }
    
    return {
      headers: results.meta.fields || [],
      rows: results.data as Record<string, any>[], 
      groupedData: groupedData,
      errors: results.errors,
    };
  } catch (error) {
    console.error('CSV 파싱 오류:', error);
    // 오류 발생 시 빈 데이터 반환
    return {
      headers: [],
      rows: [], 
      groupedData: {},
      errors: [error],
    };
  }
};

// ETF 현재가 테이블 컴포넌트
export default function ETFCurrentTable() {
  // 상태 관리
  const [csvData, setCsvData] = useState<{ headers: string[]; rows: Record<string, any>[]; groupedData: GroupedData; errors: any[] }>({ headers: [], rows: [], groupedData: {}, errors: [] });
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);  
  const [sortKey, setSortKey] = useState<string>('산업');  // 정렬 상태 - 기본값으로 산업 컬럼 오름차순 설정
  const [sortDirection, setSortDirection] = useState<SortDirection>('asc');
  const [stockPriceData, setStockPriceData] = useState<StockPriceData>({});
  const [tickerMappingInfo, setTickerMappingInfo] = useState<{
    tickerMap: {[key: string]: string},
    stockNameMap: {[key: string]: string}
  }>({ tickerMap: {}, stockNameMap: {} });
  const [etfStockList, setEtfStockList] = useState<{[key: string]: Array<{name: string, rs: string}>}>({});
  const [updateDate, setUpdateDate] = useState<string | null>(null); // Add state for update date
  
  // 테이블 복사 기능을 위한 ref 생성
  const tableRef = useRef<HTMLDivElement>(null);
  const headerRef = useRef<HTMLDivElement>(null);

  // 사용 가능한 티커 목록 (rs_etf 폴더에 있는 파일 이름)
  const availableTickers = [
    '069500', '091160', '091170', '091180', '098560', '102970', '139220', 
    '139240', '139250', '139270', '140700', '140710', '157490', '227540', 
    '228790', '228800', '228810', '229200', '261070', '364980', 
    '364990', '365000', '433500', '438900', '445290', '449450', '455860', 
    '457990', '460280', '463050', '463250', '464600', '464610', '466920', 
    '475050', '475300', '475310', '479850', '483020', '487240'
  ];
  
  // 티커 매핑 테이블 (today_price_etf 티커 -> rs_etf 파일 이름)
  const tickerMappingTable: {[key: string]: string} = {
    // 코스피/코스닥 ETF
    '069500': '069500', // KODEX 200
    '229200': '229200', // KODEX 코스닥150
    '091180': '091180', // KODEX 자동차
    '140710': '140710', // KODEX 운송
    '227540': '227540', // TIGER 200 헬스케어
    '261070': '261070', // TIGER 코스닥150바이오테크
    '139240': '139240', // TIGER 200 철강소재
    
    // 산업/테마 ETF
    '433500': '433500', // ACE 원자력테마딥서치
    '457990': '457990', // PLUS 태양광&ESS
    '460280': '460280', // KIWOOM Fn유전자혁신기술
    '463050': '463050', // TIMEFOLIO K바이오액티브
    '463250': '463250', // TIGER 우주방산
    '464600': '464600', // SOL 자동차소부장Fn
    '464610': '464610', // SOL 의료기기소부장Fn
    '466920': '466920', // SOL 조선TOP3플러스
    '483020': '483020', // KIWOOM 의료AI
    '487240': '487240', // KODEX AI전력핵심설비
    '449450': '449450', // PLUS K방산
    
    // 추가 매핑
    '098560': '098560', // 키움글로벌클라우드플러스
    '102970': '102970', // 신한BNPP코리아우량회사채
    '139220': '139220', // 솔라엣지테크놀로지
    '139250': '139250', // 미래에셋맵스아시아퍼시픽
    '139270': '139270', // 미래에셋맵스미국블루칩
    '140700': '140700', // 미래에셋맵스브라질
    '157490': '157490', // 미래에셋맵스인디아
    '228790': '228790', // 스마트베타유니버스
    '228800': '228800', // 스마트베타모멘텀
    '228810': '228810', // 스마트베타퀄리티
    '364980': '364980', // 미래에셋글로벌리츠
    '364990': '364990', // 미래에셋글로벌헬스케어
    '365000': '365000', // 미래에셋글로벌인컴
    '438900': '438900', // 한화글로벌메타버스
    '445290': '445290', // 한화글로벌헬스케어
    '455860': '455860', // 미래에셋글로벌테크
    '475050': '475050', // 미래에셋글로벌클린에너지
    '475300': '475300', // 미래에셋글로벌인프라
    '475310': '475310', // 미래에셋글로벌리츠부동산
    '479850': '479850'  // 미래에셋글로벌테크놀로지
  };
  
  // 종가 데이터 로드 함수
  const loadPriceData = async (ticker: string): Promise<{ date: string; price: number }[]> => {
    try {
      // 티커가 없으면 빈 배열 반환
      if (!ticker || ticker === 'N/A') {
        console.error(`유효하지 않은 티커: ${ticker}`);
        return [];
      }
      
      // CSV 파일 로드
      const response = await fetch(`/requestfile/rs_etf/${ticker}.csv?t=${Date.now()}`);
      if (!response.ok) {
        console.error(`${ticker} CSV 파일을 불러오는데 실패했습니다: ${response.status}`);
        return [];
      }
      
      const csvText = await response.text();
      const result = Papa.parse(csvText, { header: true });
      
      // 종가 데이터 추출 (CSV 파일은 이미 날짜순으로 정렬되어 있음 - 과거에서 현재로)
      const closePrices = result.data
        .filter((row: any) => row['종가'] && !isNaN(parseFloat(row['종가'])) && row['날짜'])
        .map((row: any) => ({ 
          date: row['날짜'], // YYYY-MM-DD 형식
          price: parseFloat(row['종가']) 
        }));
      
      // 날짜 기준으로 정렬 (과거 -> 현재)
      closePrices.sort((a, b) => {
        const dateA = new Date(a.date);
        const dateB = new Date(b.date);
        return dateA.getTime() - dateB.getTime();
      });
      
      return closePrices;
    } catch (error) {
      console.error(`${ticker} 종가 데이터 로드 중 오류 발생:`, error);
      return [];
    }
  };
  
  // 모든 티커에 대한 종가 데이터 로드
  const loadAllPriceData = async (tickers: string[]) => {
    const priceData: StockPriceData = {};
    const tickerMap: {[key: string]: string} = {}; // 원본 티커와 정규화된 티커 매핑
    const stockNameMap: {[key: string]: string} = {}; // 티커와 종목명 매핑
    
    // 유효한 티커만 필터링
    const validTickers = tickers.filter(ticker => ticker && ticker.trim().length > 0);
    
    // 티커별 데이터 로드 (순차적으로 처리하여 종목명 매칭 로직이 제대로 작동하도록 함)
    for (const ticker of validTickers) {
      try {
        // 티커와 함께 종목명도 가져오기 (있는 경우)
        // 원본 데이터에서 해당 티커의 종목명 찾기
        let stockName = '';  // 기본값을 빈 문자열로 초기화
        
        // 티커 변형 생성 (원본, 앞에 0 추가, 앞의 0 제거)
        const tickerVariations = [
          ticker,
          ticker.padStart(6, '0'),
          ticker.replace(/^0+/, '')
        ];
        
        // groupedData의 모든 산업을 순회하며 해당 티커 찾기
        let found = false;
        for (const industry in csvData.groupedData) {
          const industryData = csvData.groupedData[industry];
          for (const sector in industryData) {
            const sectorData = industryData[sector];
            
            // 모든 티커 변형에 대해 검색
            for (const tickerVariant of tickerVariations) {
              const matchingRow = sectorData.find((row: Record<string, any>) => 
                row['티커'] === tickerVariant || 
                row['티커']?.padStart(6, '0') === tickerVariant.padStart(6, '0')
              );
              
              if (matchingRow) {
                stockName = matchingRow['종목명'] || '';
                stockNameMap[ticker] = stockName; // 종목명 저장
                found = true;
                break;
              }
            }
            if (found) break;
          }
          if (found) break;
        }
        
        // 티커 정규화
        const normalizedTicker = await normalizeTicker(ticker, stockName);
        if(normalizedTicker !== null) {
          tickerMap[ticker] = normalizedTicker;
        } else {
          tickerMap[ticker] = 'N/A';
        }
        
        if (normalizedTicker) {
          const prices = await loadPriceData(normalizedTicker);
          if (prices && prices.length > 0) {
            priceData[ticker] = prices; // 원래 티커 값을 키로 사용
          } else {
          }
        } else {
        }
      } catch (error) {
        console.error(`${ticker} 처리 중 오류:`, error);
      }
    }
    
    return { priceData, tickerMap, stockNameMap };
  };
  
  // 티커 정규화 함수
  const normalizeTicker = async (ticker: string, stockName?: string): Promise<string | null> => {
    if (!ticker) return null;
    
    // 공백 제거
    const cleaned = ticker.trim();
    
    // 원본 티커와 앞에 0을 추가한 버전 모두 시도
    const variations = [
      cleaned,                           // 원본
      cleaned.padStart(6, '0'),          // 6자리로 패딩 (069500 형식)
      cleaned.replace(/^0+/, '')         // 앞의 0 제거 (69500 -> 69500)
    ];
    
    // console.log(`티커 변형 시도: ${variations.join(', ')}`);
    
    // 1. 티커 매핑 테이블에서 매핑된 티커를 찾음
    for (const variant of variations) {
      if (tickerMappingTable[variant]) {
        const mappedTicker = tickerMappingTable[variant];
        return mappedTicker;
      }
    }
    
    // 2. 정확히 일치하는 티커가 있는지 확인
    for (const variant of variations) {
      if (availableTickers.includes(variant)) {
        return variant;
      }
    }
    
    // 3. 종목명을 사용하여 매핑 시도 (stockName이 제공된 경우)
    if (stockName) {
      // 종목명에서 공통 부분을 추출 (예: "KODEX", "TIGER" 등)
      const stockNameParts = stockName.split(' ');
      if (stockNameParts.length > 0) {
        const prefix = stockNameParts[0]; // "KODEX", "TIGER" 등
        
        // 해당 접두사를 가진 티커 찾기
        for (const availableTicker of availableTickers) {
          // 해당 티커의 CSV 파일을 로드하여 종목명 확인
          try {
            const response = await fetch(`/requestfile/rs_etf/${availableTicker}.csv?t=${Date.now()}`);
            if (response.ok) {
              const csvText = await response.text();
              const result = Papa.parse(csvText, { header: true });
              
              if (result.data && result.data.length > 0) {
                const firstRow = result.data[0] as Record<string, unknown>;
                const csvStockName = firstRow['종목명'] as string;
                
                if (csvStockName && csvStockName.includes(prefix)) {
                  return availableTicker;
                }
              }
            }
          } catch (error) {
            console.error(`종목명 매칭 시도 중 오류:`, error);
          }
        }
      }
    }
    
    // 매칭되는 티커가 없음
    return null;
  };
  
  // 20일선 돌파/이탈 이벤트 계산
  const calculate20DayCrossover = (ticker: string): { date: string; type: 'cross_above' | 'cross_below' } | null => {
    if (!ticker || !stockPriceData[ticker] || stockPriceData[ticker].length < 20) {
      return null;
    }
    
    // 최근 데이터 추출 (가능한 많은 데이터 사용)
    const recentData = stockPriceData[ticker];
    const events = [];
    
    // 각 날짜에 대해 20일 이동평균선 계산 및 돌파/이탈 확인
    // 최소 20일 데이터가 있어야 시작
    for (let i = 19; i < recentData.length; i++) {
      try {
        // i번째 날짜의 20일 이동평균 계산
        const ma20 = recentData.slice(i - 19, i + 1).reduce((acc, val) => acc + val.price, 0) / 20;
        
        // 가격 데이터 (종가 기준)
        const currPrice = recentData[i].price;
        
        // 실제 데이터의 날짜 사용
        const dateString = recentData[i].date;
        
        // 이전 데이터가 있는 경우에만 돌파/이탈 확인
        if (i > 19) {
          const prevMa20 = recentData.slice(i - 20, i).reduce((acc, val) => acc + val.price, 0) / 20;
          const prevPrice = recentData[i - 1].price;
          
          // 가격이 20일선 아래에서 위로 돌파 (종가 기준)
          if (prevPrice < prevMa20 && currPrice > ma20) {
            events.push({
              date: dateString,
              type: 'cross_above' as const,
              index: i
            });
          }
          // 가격이 20일선 위에서 아래로 이탈 (종가 기준)
          else if (prevPrice > prevMa20 && currPrice < ma20) {
            events.push({
              date: dateString,
              type: 'cross_below' as const,
              index: i
            });
          }
        }
        
        // 첫 번째 데이터 포인트에 대한 특별 처리 (이전 데이터가 없는 경우)
        // 첫 번째 데이터 포인트의 위치에 따라 초기 이벤트 설정
        if (i === 19 && events.length === 0) {
          if (currPrice > ma20) {
            events.push({
              date: dateString,
              type: 'cross_above' as const,
              index: i
            });
          } else if (currPrice < ma20) {
            events.push({
              date: dateString,
              type: 'cross_below' as const,
              index: i
            });
          }
        }
      } catch (error) {
        console.error(`Error calculating MA for ticker ${ticker} at index ${i}:`, error);
      }
    }
    
    // 이벤트가 없으면 현재 상태에 따라 기본 이벤트 생성
    if (events.length === 0) {
      try {
        const lastIndex = recentData.length - 1;
        if (lastIndex >= 19) {
          const lastPrice = recentData[lastIndex].price;
          const lastMA20 = recentData.slice(lastIndex - 19, lastIndex + 1).reduce((acc, val) => acc + val.price, 0) / 20;
          
          // 실제 데이터의 날짜 사용
          const dateString = recentData[lastIndex].date;
          
          if (lastPrice > lastMA20) {
            return {
              date: dateString,
              type: 'cross_above'
            };
          } else {
            return {
              date: dateString,
              type: 'cross_below'
            };
          }
        }
      } catch (error) {
        console.error(`Error creating default event for ticker ${ticker}:`, error);
      }
      return null;
    }
    
    // 모든 이벤트 로깅
    // if (events.length > 0) {
    //   console.log(`${ticker} 감지된 모든 이벤트:`, events.map(e => `${e.date} (${e.type})`).join(', '));
    // }
    
    // 현재 상태에 따라 가장 최근의 유의미한 이벤트 반환
    const lastIndex = recentData.length - 1;
    const lastPrice = recentData[lastIndex].price;
    const lastMA20 = recentData.slice(lastIndex - 19, lastIndex + 1).reduce((acc, val) => acc + val.price, 0) / 20;
    const isAboveMA = lastPrice > lastMA20;
    
    if (isAboveMA) {
      // 현재 20일선 위에 있으면, 가장 최근 돌파 이벤트 찾기
      const lastCrossAbove = events.filter(e => e.type === 'cross_above')
                                  .sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime())[0];
      if (lastCrossAbove) {
        return {
          date: lastCrossAbove.date,
          type: lastCrossAbove.type
        };
      }
    } else {
      // 현재 20일선 아래에 있으면, 가장 최근 이탈 이벤트 찾기
      const lastCrossBelow = events.filter(e => e.type === 'cross_below')
                                  .sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime())[0];
      if (lastCrossBelow) {
        return {
          date: lastCrossBelow.date,
          type: lastCrossBelow.type
        };
      }
    }
    
    // 현재 상태와 일치하는 이벤트가 없으면 가장 최근 이벤트 반환
    const lastEvent = events.sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime())[0];
    return {
      date: lastEvent.date,
      type: lastEvent.type
    };
  };

  // 종목별 20일 이동평균선 위치 계산
  const calculate20DayMAPosition = (ticker: string): string => {
    if (!ticker || !stockPriceData[ticker] || stockPriceData[ticker].length < 20) {
      return '-';
    }
    
    // 최근 20일 데이터 추출
    const recentData = stockPriceData[ticker].slice(-20);
    
    // 20일 이동평균 계산
    const sum = recentData.reduce((acc, val) => acc + val.price, 0);
    const ma20 = sum / recentData.length;
    
    // 현재가 (가장 최근 데이터)
    const currentPrice = stockPriceData[ticker][stockPriceData[ticker].length - 1].price;
    
    // 현재가와 20일 이동평균선 비교
    const diffPercent = ((currentPrice - ma20) / ma20 * 100).toFixed(1);
    
    // 위치 표시 (위, 아래 또는 일치)
    if (currentPrice > ma20) {
      return `+${diffPercent}%`;
    } else if (currentPrice < ma20) {
      return `${diffPercent}%`;
    } else {
      return '0%';
    }
  };

  // 돌파/이탈 유지 기간 계산 (캔들 기준)
  const calculatePositionDuration = (ticker: string): number | null => {
    if (!ticker || !stockPriceData[ticker] || stockPriceData[ticker].length < 20) {
      return null;
    }
    
    // 현재가와 20일 이동평균선 데이터 가져오기
    const priceData = stockPriceData[ticker];
    if (!priceData || priceData.length < 20) {
      return null;
    }
    
    const currentPrice = priceData[priceData.length - 1].price;
    const ma20 = priceData.slice(-20).reduce((acc, val) => acc + val.price, 0) / 20;
    
    // 현재 상태 (20일선 위 또는 아래)
    const isAboveMA = currentPrice > ma20;
    
    // 연속일수 계산 (IndustryCharts 방식)
    let durationDays = 1;
    for (let i = priceData.length - 2; i >= 0; i--) {
      // 이전 가격과 이전 20일 이동평균선 계산
      const price = priceData[i].price;
      
      // 이전 20일 이동평균선 계산 (데이터가 20개 미만일 수 있으므로 처리)
      const prevMA20 = priceData
        .slice(Math.max(0, i - 19), i + 1)
        .reduce((acc, val) => acc + val.price, 0) / Math.min(20, i + 1);
      
      // 이전 상태가 현재 상태와 다르면 중단
      if ((price > prevMA20) !== isAboveMA) {
        break;
      }
      
      // 같은 상태면 일수 증가
      durationDays++;
    }
    
    return durationDays;
  };

  // 날짜 형식 변환 함수 (YYYY-MM-DD -> MM-DD)
  const formatDateToMMDD = (dateString: string): string => {
    if (!dateString) return '';
    
    const parts = dateString.split('-');
    if (parts.length !== 3) return dateString;
    
    return `${parts[1]}-${parts[2]}`;
  };

  // 표시용 날짜 형식 변환 함수 (컴포넌트에서 사용)
  const formatDisplayDate = (dateString: string, type: 'cross_above' | 'cross_below'): string => {
    const mmdd = formatDateToMMDD(dateString);
    const typeText = type === 'cross_above' ? '돌파' : '이탈';
    return `${mmdd} ${typeText}`;
  };

  useEffect(() => {
    // 페이지 로드 시 데이터 로드
    const loadData = async () => {
      setLoading(true);
      setError(null);
      
      try {
        // ETF 현재가 데이터 파일 경로 - 구글 드라이브 동기화 시스템과 일치
        const filePath = `${ETF_FILES.currentPrice.path}/${ETF_FILES.currentPrice.fileName}?t=${Date.now()}`;
        
        console.log('파일 경로:', filePath);
        
        // 로컬 캐시 파일 로드 - 직접 fetch 사용
        const response = await fetch(filePath);
        
        if (!response.ok) {
          throw new Error(`캐시 파일 로드 실패: ${response.status}`);
        }
        
        const csvText = await response.text();
        
        // CSV 텍스트 로깅 (디버깅용)
        console.log('CSV 파일 로드 완료, 크기:', csvText.length);
        if (csvText.length > 0) {
          console.log('CSV 첫 줄:', csvText.split('\n')[0]);
        } else {
          console.error('CSV 텍스트가 비어 있습니다!');
          setError('CSV 파일이 비어 있습니다.');
          setLoading(false);
          return;
        }
        
        // CSV 파싱 및 데이터 처리
        const parsedData = parseCSV(csvText);
        
        // 파싱된 데이터 확인
        if (!parsedData.groupedData || Object.keys(parsedData.groupedData).length === 0) {
          console.error('그룹화된 데이터가 없습니다.');
          setError('데이터를 그룹화할 수 없습니다. CSV 형식을 확인해주세요.');
          setLoading(false);
          return;
        }
        
        setCsvData(parsedData);
        
        // 모든 ETF 티커 추출
        const tickers: string[] = [];
        Object.values(parsedData.groupedData).forEach(group => {
          group.forEach(item => {
            if (item['티커']) {
              tickers.push(item['티커']);
            }
          });
        });
        
        // 티커별 종가 데이터 로드
        const { priceData, tickerMap, stockNameMap } = await loadAllPriceData(tickers);
        
        setStockPriceData(priceData);
        setTickerMappingInfo({ tickerMap, stockNameMap });
        
        // ETF 대표종목 데이터 로드
        const stockListResponse = await fetch(ETF_FILES.stockList.path);
        if (stockListResponse.ok) {
          const stockListText = await stockListResponse.text();
          const stockListResult = Papa.parse(stockListText, { header: true });
          
          // ETF 티커별 대표종목 매핑 생성
          const stockListMap: {[key: string]: Array<{name: string, rs: string}>} = {};
          stockListResult.data.forEach((row: any) => {
            if (row['티커']) {
              // 티커 변형 생성 (원본, 앞에 0 추가, 앞의 0 제거)
              const tickerVariations = [
                row['티커'],
                row['티커'].padStart(6, '0'),
                row['티커'].replace(/^0+/, '')
              ];
              
              const stockList = [
                {name: row['대표 구성 종목 1'] || '', rs: row['대표 구성 종목 1rs'] || ''},
                {name: row['대표 구성 종목 2'] || '', rs: row['대표 구성 종목 2rs'] || ''},
                {name: row['대표 구성 종목 3'] || '', rs: row['대표 구성 종목 3rs'] || ''},
                {name: row['대표 구성 종목 4'] || '', rs: row['대표 구성 종목 4rs'] || ''}
              ].filter(item => item.name); // 빈 문자열 제거
              
              // 모든 티커 변형에 대해 매핑 추가
              tickerVariations.forEach(variant => {
                if (variant) {
                  stockListMap[variant] = stockList;
                }
              });
            }
          });
          
          setEtfStockList(stockListMap);
        }
        
        // 날짜 추출 및 상태 업데이트 (CSV 첫 행의 '날짜' 컬럼 사용)
        if (parsedData.rows && parsedData.rows.length > 0) {
          const dateString = parsedData.rows[0]['날짜']; 
          if (dateString) {
            const formattedDate = formatDateMMDD(dateString);
            if (formattedDate) {
              setUpdateDate(formattedDate);
            } else {
              console.warn('날짜 형식을 변환할 수 없습니다:', dateString);
            }
          } else {
            console.warn('CSV 데이터에 날짜 정보가 없습니다.');
          }
        }
        
      } catch (err) {
        console.error('데이터 로드 오류:', err);
        setError(`데이터 로드 중 오류가 발생했습니다: ${err instanceof Error ? err.message : String(err)}`);
      } finally {
        setLoading(false);
      }
    };
    
    loadData();
  }, []);

  // 정렬 처리 함수
  const handleSort = (key: string) => {
    console.log(`정렬 시도: 컴럼 = ${key}, 현재 정렬키 = ${sortKey}, 현재 방향 = ${sortDirection}`);
    
    if (sortKey === key) {
      // 같은 컴럼을 다시 클릭한 경우, 오름차순과 내림차순만 반복하도록 수정
      const newDirection = sortDirection === 'asc' ? 'desc' : 'asc';
      console.log(`같은 컴럼 클릭: 정렬 방향 변경 ${sortDirection} -> ${newDirection}`);
      setSortDirection(newDirection);
    } else {
      // 다른 컴럼을 클릭한 경우, 해당 컴럼으로 오름차순 정렬
      console.log(`새 컴럼 클릭: 정렬키 변경 ${sortKey} -> ${key}, 방향 = asc`);
      setSortKey(key);
      setSortDirection('asc');
    }
  };
  
  // 정렬된 데이터 계산
  const sortedData = useMemo(() => {
    if (!sortKey || !sortDirection || !csvData.groupedData) {
      return csvData.groupedData;
    }
    
    // 마켓 행 반드시 복사하여 사용
    const marketGroup = [...(csvData.groupedData['마켓'] || [])];
    
    // 1. 마켓을 포함한 모든 산업 그룹들의 데이터를 복사
    const allIndustries: GroupedData = {};
    for (const industry in csvData.groupedData) {
      allIndustries[industry] = [...csvData.groupedData[industry]];
    }
    
    // 2. 단순한 행 정렬 함수 정의
    const sortRow = (a: any, b: any) => {
      let aValue = a[sortKey];
      let bValue = b[sortKey];
      
      // 포지션 컴럼은 특별 처리
      if (sortKey === '포지션') {
        // 포지션 값은 데이터에 직접 존재하지 않음
        // 티커를 사용하여 포지션 값을 가져와야 함
        const aTicker = a['티커'];
        const bTicker = b['티커'];
        
        console.log('포지션 정렬을 위한 티커:', aTicker, bTicker);
        
        // 포지션 값 추출 및 처리 - getPositionStatusText 함수 대신 직접 구현
        const extractPositionValue = (ticker: string): number => {
          if (!ticker || !stockPriceData[ticker] || stockPriceData[ticker].length < 20) return 0;
          
          // 현재가와 20일 이동평균선 데이터 가져오기
          const priceData = stockPriceData[ticker];
          if (!priceData || priceData.length < 20) {
            return 0;
          }
          
          const currentPrice = priceData[priceData.length - 1].price;
          const ma20 = priceData.slice(-20).reduce((acc, val) => acc + val.price, 0) / 20;
          
          // 현재 상태 (20일선 위 또는 아래)
          const isAboveMA = currentPrice > ma20;
          
          // 유지 기간 계산 - 직접 구현
          let duration = 0;
          try {
            if (!priceData || priceData.length < 2) return isAboveMA ? 1 : -1;
            
            // 역순으로 데이터 확인
            const reversedData = [...priceData].reverse();
            const ma20Values = [];
            
            // 20일 이동평균 계산
            for (let i = 0; i < reversedData.length - 19; i++) {
              const slice = reversedData.slice(i, i + 20);
              const ma = slice.reduce((sum, item) => sum + item.price, 0) / 20;
              ma20Values.push({
                price: reversedData[i].price,
                ma20: ma,
                date: reversedData[i].date,
                isAbove: reversedData[i].price > ma
              });
            }
            
            // 현재 상태
            const currentStatus = ma20Values[0].isAbove;
            
            // 연속 유지 기간 계산
            duration = 1; // 현재 일자 포함
            for (let i = 1; i < ma20Values.length; i++) {
              if (ma20Values[i].isAbove === currentStatus) {
                duration++;
              } else {
                break;
              }
            }
            
            // 이탈이면 음수로 처리
            if (!currentStatus) {
              duration = -duration;
            }
          } catch (error) {
            console.error('포지션 기간 계산 오류:', error);
            duration = isAboveMA ? 1 : -1; // 오류 발생 시 기본값
          }
          
          console.log(`티커 ${ticker}의 포지션 값:`, duration);
          return duration;
        };
        
        const aPositionValue = extractPositionValue(aTicker);
        const bPositionValue = extractPositionValue(bTicker);
        
        console.log(`비교: ${aPositionValue} vs ${bPositionValue}, 정렬방향: ${sortDirection}`);
        
        if (aPositionValue < bPositionValue) return sortDirection === 'asc' ? -1 : 1;
        if (aPositionValue > bPositionValue) return sortDirection === 'asc' ? 1 : -1;
        return 0;
      }
      // 숫자 문자열을 숫자로 변환 (일반 컴럼)
      else if (!isNaN(parseFloat(aValue)) && !isNaN(parseFloat(bValue))) {
        aValue = parseFloat(aValue);
        bValue = parseFloat(bValue);
      }
      
      if (aValue < bValue) return sortDirection === 'asc' ? -1 : 1;
      if (aValue > bValue) return sortDirection === 'asc' ? 1 : -1;
      return 0;
    };
    
    // 3. 산업 그룹을 등락률 평균 기준으로 정렬 (직접 계산)
    // 산업 컴럼 외 다른 컴럼을 정렬할 때는 산업그룹 순서는 유지하고 그룹 내부만 정렬
    if (sortKey === '산업') {
      // 산업 컴럼을 클릭했을 때는 산업 그룹을 정렬

      const industryAverages: Record<string, number> = {};
      
      // 각 산업의 등락률 평균값 계산
      for (const industry in allIndustries) {
        // 마켓을 제외한 산업만 평균 계산 (마켓은 항상 최상단에 고정)
        if (industry !== '마켓') {
          // 해당 산업의 모든 항목에 대해 등락률 평균 계산
          let sum = 0;
          let count = 0;
          
          allIndustries[industry].forEach((item: any) => {
            const changeRate = item['등락율']; // '등락율' 기준으로 평균 계산
            if (changeRate) {
              const numValue = parseFloat(changeRate.replace('%', ''));
              if (!isNaN(numValue)) {
                sum += numValue;
                count++;
              }
            }
          });
          
          // 산업 평균 등락률 계산
          industryAverages[industry] = count > 0 ? sum / count : 0;
        }
      }
      
      // 마켓을 제외한 산업 그룹만 정렬
      const sortedIndustries = Object.keys(allIndustries)
        .filter(industry => industry !== '마켓')
        .sort((a, b) => {
          const aAvg = industryAverages[a];
          const bAvg = industryAverages[b];
          
          // sortDirection에 따라 산업 그룹 정렬 방향 변경
          if (aAvg < bAvg) return sortDirection === 'asc' ? 1 : -1; 
          if (aAvg > bAvg) return sortDirection === 'asc' ? -1 : 1;
          return 0;
        });
      
      // 정렬된 산업 순서대로 새 데이터 객체 생성 (마켓은 최상단 고정)
      const sortedGroupedData: GroupedData = { '마켓': marketGroup };
      
      // 정렬된 산업 순서대로 그룹 추가
      sortedIndustries.forEach(industry => {
        sortedGroupedData[industry] = allIndustries[industry];
      });
      
      return sortedGroupedData;
    } else {
      // 다른 컴럼을 클릭했을 때는 그룹 순서는 유지하고 그룹 내부만 정렬
      
      // 1. 산업 그룹 내부 정렬
      for (const industry in allIndustries) {
        allIndustries[industry].sort(sortRow);
      }
      
      // 2. 마켓 그룹은 최상단에 고정
      const sortedGroupedData: GroupedData = { '마켓': allIndustries['마켓'] };
      
      // 3. 기존 산업 순서를 유지하면서 그룹 내부만 정렬된 데이터 추가
      Object.keys(csvData.groupedData)
        .filter(industry => industry !== '마켓')
        .forEach(industry => {
          sortedGroupedData[industry] = allIndustries[industry];
        });
      
      return sortedGroupedData;
    }
  }, [csvData.groupedData, sortKey, sortDirection]);

  // 날짜 컬럼을 제외한 헤더 필터링
  const filteredHeaders = useMemo(() => {
    // 표시하지 않을 컬럼 목록
    const excludedColumns = ['날짜', '시가', '종가', '고가', '저가', '거래량', '전일종가'];
    return csvData.headers.filter(header => !excludedColumns.includes(header));
  }, [csvData.headers]);
  
  // 코스피/코스닥 데이터 추출
  const marketData = useMemo(() => {
    // groupedData에서 코스피와 코스닥 데이터 찾기
    const kospiRow = csvData.groupedData && csvData.groupedData['마켓'] ? 
      csvData.groupedData['마켓'].find((row: Record<string, any>) => row['티커'] === '069500') : null;
    const kosdaqRow = csvData.groupedData && csvData.groupedData['마켓'] ? 
      csvData.groupedData['마켓'].find((row: Record<string, any>) => row['티커'] === '229200') : null;

    return {
      kospi: {
        changeRate: kospiRow ? kospiRow['등락율'] : '0.00%'
      },
      kosdaq: {
        changeRate: kosdaqRow ? kosdaqRow['등락율'] : '0.00%'
      }
    };
  }, [csvData.groupedData]);
  
  // 변동률에 따른 색상 클래스 반환 함수
  const getChangeColorClass = (change: number) => {
    if (change > 0) return 'text-red-400';
    if (change < 0) return 'text-blue-400';
    return '';
  };

  // 변동률에 따른 색상 코드 반환 함수
  const getChangeColorCode = (change: number) => {
    if (change > 0) return '#EF4444';
    if (change < 0) return '#3B82F6';
    return '#4B5563';
  };

  // 변동률에 따른 배경 색상 코드 반환 함수
  const getChangeBgColorCode = (change: number) => {
    if (change > 0) return '#FEE2E2';
    if (change < 0) return '#DBEAFE';
    return '#F3F4F6';
  };

  // 산업별 평균 등락률 계산
  const calculateIndustryAverage = useCallback((industry: string, data: Record<string, any[]>) => {
    if (!data[industry] || data[industry].length === 0) return '0.00%';
    
    let sum = 0;
    let count = 0;
    
    data[industry].forEach((item) => {
      const changeRate = item['등락율'];
      if (changeRate) {
        const numValue = parseFloat(changeRate.replace('%', ''));
        if (!isNaN(numValue)) {
          sum += numValue;
          count++;
        }
      }
    });
    
    if (count === 0) return '0.00%';
    const average = sum / count;
    return average.toFixed(2) + '%';
  }, []);

  // 변동률에 따른 색상 클래스 반환 함수 (평균용)
  const getAverageColorClass = (change: string) => {
    const numValue = parseFloat(change.replace('%', ''));
    if (numValue > 0) return 'text-red-400';
    if (numValue < 0) return 'text-blue-400';
    return 'text-gray-500';
  };

  // 돌파/이탈 일 컬럼 렌더링 함수
  const renderCrossover = (ticker: string) => {
    const crossover = calculate20DayCrossover(ticker);
    
    if (!crossover) {
      return <span className="text-gray-400">-</span>;
    }
    
    // 날짜 형식 변환 (YYYY-MM-DD -> MM-DD)
    const formattedDate = formatDisplayDate(crossover.date, crossover.type);
    
    return (
      <div className="flex items-center justify-center">
        <span 
          className={`text-xs font-medium ${
            crossover.type === 'cross_above' 
              ? 'text-red-400' 
              : 'text-blue-400'
          }`}
          style={{ fontSize: 'clamp(0.6rem, 0.7vw, 0.7rem)' }}
        >
          {formattedDate}
        </span>
      </div>
    );
  };

  // 포지션 상태 텍스트 가져오기
  const getPositionStatusText = (ticker: string): string => {
    if (!ticker || !stockPriceData[ticker] || stockPriceData[ticker].length < 20) return '-';
    
    // 현재가와 20일 이동평균선 데이터 가져오기
    const priceData = stockPriceData[ticker];
    if (!priceData || priceData.length < 20) {
      return '-';
    }
    
    const currentPrice = priceData[priceData.length - 1].price;
    const ma20 = priceData.slice(-20).reduce((acc, val) => acc + val.price, 0) / 20;
    
    // 현재 상태 (20일선 위 또는 아래)
    const isAboveMA = currentPrice > ma20;
    
    // 유지 기간 계산
    const duration = calculatePositionDuration(ticker);
    const durationText = duration !== null ? `+${duration}일` : '';
    
    return isAboveMA ? `유지 ${durationText}` : `이탈 ${durationText}`;
  };

  // 테이블 이미지 복사 함수
  const handleCopyTableAsImage = async () => {
    try {
      const currentDate = new Date();
      const formattedDate = `${currentDate.getFullYear()}-${String(currentDate.getMonth() + 1).padStart(2, '0')}-${String(currentDate.getDate()).padStart(2, '0')}`;
      
      await copyTableAsImage(
        tableRef,
        headerRef,
        'ETF 현재가 테이블',
        {
          copyrightText: '© intellio.kr',
          watermark: {
            text: 'intellio.kr',
            opacity: 0.1,
            fontSize: '24px',
            color: '#000000'
          },
          scale: 2,
          backgroundColor: '#ffffff',
          footerStyle: {
            fontSize: '8px',
            color: '#999999',
            marginTop: '8px',
            textAlign: 'center'
          }
        },
        formattedDate
      );
    } catch (error) {
      console.error('테이블 이미지 복사 중 오류 발생:', error);
      alert('테이블 이미지 복사에 실패했습니다.');
    }
  };

  // 로딩 중 표시
  if (loading) {
    return (
      <div className="bg-white rounded-md shadow p-4 h-80 flex items-center justify-center">
        <div className="text-gray-500">데이터 로딩 중...</div>
      </div>
    );
  }
  
  // 오류 표시
  if (error) {
    return (
      <div className="bg-white rounded-md shadow p-4 h-80 flex items-center justify-center">
        <div className="text-red-500">{error}</div>
      </div>
    );
  }
  
  // 데이터가 없는 경우
  if (!csvData.groupedData) {
    return (
      <div className="bg-white rounded-md shadow p-4 h-80 flex items-center justify-center">
        <div className="text-gray-500">데이터가 없습니다.</div>
      </div>
    );
  }
  
  // 산업 그룹 순서 정의
  const industryOrder = [
    '마켓',
    '반도체',
    '2차전지',
    '철강',
    '조선',
    '자동차',
    '에너지',
    '화학',
    '바이오',
    '제약',
    '헬스케어',
    '의료',
    '금융',
    '은행',
    '증권',
    '보험',
    '여행',
    '항공',
    '호텔',
    '레저',
    '엔터',
    '게임',
    '미디어',
    '통신',
    '인터넷',
    '소프트웨어',
    '유통',
    '소비재/음식료',
    '필수소비재',
    '전력기기',
    '인프라',
    '부동산',
    '친환경',
    '수소',
    '원자력',
    '메타버스',
    '로보틱스',
    '우주항공',
    '농업',
    '기타'
  ];

  // 모든 산업 그룹을 포함하도록 보장 (Set을 Array로 변환)
  const allIndustries = Array.from(new Set([...industryOrder, ...Object.keys(sortedData)]));
  
  // industryOrder의 순서를 유지하면서 누락된 산업 그룹을 추가
  const orderedIndustries = [...industryOrder].filter(industry => industry !== '기타');
  allIndustries.forEach(industry => {
    if (!orderedIndustries.includes(industry) && industry !== '기타') {
      orderedIndustries.push(industry);
    }
  });
  
  // '기타' 섹터를 항상 마지막에 추가
  if (allIndustries.includes('기타')) {
    orderedIndustries.push('기타');
  }

  // 디버깅: 각 산업 그룹별 종목 수 확인
  const industryCounts: Record<string, number> = {};
  Object.keys(sortedData).forEach(industry => {
    industryCounts[industry] = sortedData[industry].length;
  });

  // 전체 종목 수 확인
  const totalETFs = Object.values(sortedData).reduce((acc: number, curr: any[]) => acc + curr.length, 0);

  // 모든 티커 목록 확인
  const allTickers: string[] = [];
  Object.values(sortedData).forEach((industryData: any[]) => {
    industryData.forEach((item: any) => {
      if (item.티커) {
        allTickers.push(item.티커);
      }
    });
  });

  return (
    <div>
      <div ref={headerRef} className="flex justify-between items-center mb-3">
        {/* 좌측 그룹: 제목 */}
        <div className="flex items-center">
          <h2 className="font-semibold whitespace-nowrap mr-2" style={{ fontSize: 'clamp(0.75rem, 0.9vw, 0.9rem)' }}>ETF 현재가</h2>
        </div>
        {/* 우측 그룹: 업데이트 시간 + 복사 버튼 */}
        <div className="flex items-center">
          {/* 업데이트 시간 추가 */}
          {updateDate && (
            <span className="text-gray-600 text-xs mr-2" style={{ fontSize: 'clamp(0.7rem, 0.7vw, 0.7rem)' }}>
              updated 16:30 {updateDate}
            </span>
          )}
          {/* 복사 버튼 */}
          {/* <TableCopyButton 
            tableRef={tableRef} 
            headerRef={headerRef}
            tableName="ETF 현재가"
            buttonText="이미지 저장"
            updateDateText={updateDate ? `updated 16:30 ${updateDate}` : undefined}
            data-component-name="TableCopyButton"
          /> */}
        </div>
      </div>
      
      <div id="etf-current-table" className="overflow-x-auto" ref={tableRef}>
        <div ref={headerRef} className="hidden">
          <h2 className="text-lg font-semibold">ETF 현재가 테이블</h2>
          <p className="text-sm text-gray-500">{new Date().toISOString().split('T')[0]}</p>
        </div>
        <table className="min-w-full border border-gray-200 table-fixed">
          <thead className="bg-gray-100">
            <tr>
              <th
                key="산업"
                scope="col"
                className="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer border border-gray-200"
                style={{
                  width: '60px',
                  height: '35px',
                  fontSize: 'clamp(0.6rem, 0.7vw, 0.7rem)'
                }}
                onClick={() => handleSort('산업')}
              >
                <div className="flex justify-center items-center">
                  산업
                  {sortKey === '산업' && (
                    <span className="ml-1">
                      {sortDirection === 'asc' ? '↑' : sortDirection === 'desc' ? '↓' : ''}
                    </span>
                  )}
                </div>
              </th>
              <th
                key="섹터"
                scope="col"
                className="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer border border-gray-200"
                style={{
                  width: '60px',
                  height: '35px',
                  fontSize: 'clamp(0.6rem, 0.7vw, 0.7rem)'
                }}
                onClick={() => handleSort('섹터')}
              >
                <div className="flex justify-center items-center">
                  섹터
                  {sortKey === '섹터' && (
                    <span className="ml-1">
                      {sortDirection === 'asc' ? '↑' : sortDirection === 'desc' ? '↓' : ''}
                    </span>
                  )}
                </div>
              </th>
              <th
                key="종목명"
                scope="col"
                className="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer border border-gray-200"
                style={{
                  width: '140px',
                  height: '35px',
                  fontSize: 'clamp(0.6rem, 0.7vw, 0.7rem)'
                }}
                onClick={() => handleSort('종목명')}
              >
                <div className="flex justify-center items-center">
                  ETF 종목명
                  {sortKey === '종목명' && (
                    <span className="ml-1">
                      {sortDirection === 'asc' ? '↑' : sortDirection === 'desc' ? '↓' : ''}
                    </span>
                  )}
                </div>
              </th>
              {filteredHeaders.filter(header => header === '등락율').map((header) => (
                <th
                  key={header}
                  scope="col"
                  className="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer border border-gray-200"
                  style={{
                    width: '38px',
                    height: '35px',
                    fontSize: 'clamp(0.6rem, 0.7vw, 0.7rem)'
                  }}
                  onClick={() => handleSort(header)}
                >
                  <div className="flex justify-center items-center">
                    {header}
                    {sortKey === header && (
                      <span className="ml-1">
                        {sortDirection === 'asc' ? '↑' : sortDirection === 'desc' ? '↓' : ''}
                      </span>
                    )}
                  </div>
                </th>
              ))}
              <th
                key="포지션"
                scope="col"
                className="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer border border-gray-200"
                style={{
                  width: '78px',
                  height: '35px',
                  fontSize: 'clamp(0.6rem, 0.7vw, 0.7rem)'
                }}
                onClick={() => handleSort('포지션')}
              >
                <div className="flex justify-center items-center">
                  포지션
                  {sortKey === '포지션' && (
                    <span className="ml-1">
                      {sortDirection === 'asc' ? '↑' : sortDirection === 'desc' ? '↓' : ''}
                    </span>
                  )}
                </div>
              </th>
              {['20일선 이격', '돌파/이탈', '대표종목(RS)'].map((header) => (
                <th
                  key={header}
                  scope="col"
                  className={`px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider border border-gray-200 hidden md:table-cell`}
                  style={{
                    width: header === '20일선 이격' ? '80px' : header === '돌파/이탈' ? '80px' : header === '대표종목(RS)' ? '380px' : '80px',
                    height: '35px',
                    fontSize: 'clamp(0.6rem, 0.7vw, 0.7rem)'
                  }}
                >
                  <div className="flex justify-center items-center">
                    {header}
                  </div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="bg-white">
            {(() => {
              // 산업별로 데이터를 그룹화하고 각 산업의 첫 번째 행 인덱스를 저장
              const industryGroups: { [industry: string]: { rows: Record<string, any>[], firstRowIndex: number } } = {};
              let allRows: { industry: string, row: Record<string, any> }[] = [];
              
              // sortedData의 키를 직접 사용하여 정렬된 순서대로 데이터 추가
              // 마켓은 항상 먼저 표시하고, 나머지는 sortedData의 키 순서대로 추가
              const industriesToRender = Object.keys(sortedData);
              
              // 마켓을 먼저 추가
              if (industriesToRender.includes('마켓')) {
                const industry = '마켓';
                industryGroups[industry] = { 
                  rows: sortedData[industry], 
                  firstRowIndex: allRows.length 
                };
                
                sortedData[industry].forEach(row => {
                  allRows.push({ industry, row });
                });
              }
              
              // 나머지 산업 그룹들을 sortedData 순서대로 추가
              industriesToRender.forEach(industry => {
                if (industry !== '마켓' && sortedData[industry]) {
                  industryGroups[industry] = { 
                    rows: sortedData[industry], 
                    firstRowIndex: allRows.length 
                  };
                  
                  sortedData[industry].forEach(row => {
                    allRows.push({ industry, row });
                  });
                }
              });
              
              // 각 행 렌더링
              return allRows.map((item, rowIndex) => {
                const { industry, row } = item;
                const isFirstRowOfIndustry = industryGroups[industry].firstRowIndex === rowIndex;
                const rowCount = industryGroups[industry].rows.length;
                
                // 산업이 바뀔 때 더 두꺼운 상단 테두리 적용
                const borderTopClass = isFirstRowOfIndustry ? 'border-t-2 border-t-gray-300' : '';
                
                return (
                  <tr key={`${industry}-${rowIndex}`} className={`hover:bg-gray-100 ${borderTopClass}`}>
                    {isFirstRowOfIndustry && (
                      <td
                        rowSpan={rowCount}
                        className="px-2 py-1 whitespace-nowrap text-xs border border-gray-200 align-middle"
                        style={{ width: '60px', fontSize: 'clamp(0.6rem, 0.7vw, 0.7rem)' }}
                      >
                        <div className="flex flex-col items-start">
                          <span className="text-xs px-1 sm:px-2 py-0.5 sm:py-1 bg-white text-gray-700 border border-gray-200 shadow-sm inline-block" style={{ fontSize: 'clamp(0.6rem, 0.7vw, 0.7rem)', borderRadius: '4px' }}>
                            {industry === '소비재/음식료' ? '소비재/음식료' : industry}
                          </span>
                          <span className={`mt-1 text-xs font-medium ${getAverageColorClass(calculateIndustryAverage(industry, sortedData))}`} style={{ fontSize: 'clamp(0.6rem, 0.7vw, 0.7rem)', paddingLeft: '2px', width: '100%' }}>
                            {calculateIndustryAverage(industry, sortedData)}
                          </span>
                        </div>
                      </td>
                    )}
                    <td 
                      className={`px-4 py-1 whitespace-nowrap text-xs border border-gray-200 ${isFirstRowOfIndustry ? 'border-t-2 border-t-gray-300' : ''}`} 
                      style={{ width: '60px', height: '16px', fontSize: 'clamp(0.6rem, 0.7vw, 0.7rem)' }}
                    >
                      {row['섹터']}
                    </td>
                    <td className={`px-4 py-1 whitespace-nowrap text-xs border border-gray-200 ${isFirstRowOfIndustry ? 'border-t-2 border-t-gray-300' : ''}`} style={{ width: '140px', height: '16px', fontSize: 'clamp(0.6rem, 0.7vw, 0.7rem)' }}>
                      {row['종목명'] || tickerMappingInfo.stockNameMap[row['티커']] || ''}
                    </td>
                    {filteredHeaders.filter(header => header === '등락율').map((header) => {
                      const isChangeColumn = header === '등락율' || header === '전일대비';
                      const isTickerColumn = false; // 티커 컬럼은 이 필터에 포함되지 않으므로 항상 false
                      const value = row[header];
                      const numericValue = isChangeColumn ? parseFloat(value) : null;
                      const colorClass = isChangeColumn
                        ? numericValue! > 0 ? 'text-red-400' : numericValue! < 0 ? 'text-blue-400' : 'text-gray-600'
                        : '';
                      
                      return (
                        <td
                          key={header}
                          className={`px-4 py-1 whitespace-nowrap text-xs ${colorClass} border border-gray-200 ${isChangeColumn || isTickerColumn ? 'text-center' : ''} ${isFirstRowOfIndustry ? 'border-t-2 border-t-gray-300' : ''}`}
                          style={{ 
                            width: '38px', 
                            height: '16px',
                            fontSize: 'clamp(0.6rem, 0.7vw, 0.7rem)'
                          }}
                        >
                          {isChangeColumn && numericValue! > 0 ? '+' : ''}
                          {value}
                        </td>
                      );
                    })}
                    <td className={`px-4 py-1 whitespace-nowrap text-xs border border-gray-200 ${isFirstRowOfIndustry ? 'border-t-2 border-t-gray-300' : ''}`} style={{ width: '78px', height: '16px', fontSize: 'clamp(0.6rem, 0.7vw, 0.7rem)' }}>
                      {/* 포지션 상태 표시 */}
                      <div className="flex items-center justify-center">
                        <div className={`flex items-center justify-center w-20 h-6 ${getPositionStatusText(row['티커']).startsWith('유지') ? 'bg-green-100 text-green-800' : 'bg-gray-200 text-gray-700'} `} style={{ borderRadius: '4px' }}>
                          <span className="text-xs font-medium" style={{ fontSize: 'clamp(0.6rem, 0.7vw, 0.7rem)' }}>
                            {getPositionStatusText(row['티커'])}
                          </span>
                        </div>
                      </div>
                    </td>
                    {['20일선 이격', '돌파/이탈', '대표종목'].map((header) => (
                      <td
                        key={header}
                        className={`px-4 py-1 whitespace-nowrap text-xs border border-gray-200 ${isFirstRowOfIndustry ? 'border-t-2 border-t-gray-300' : ''} hidden md:table-cell`}
                        style={{ 
                          width: header === '20일선 이격' ? '80px' : header === '돌파/이탈' ? '80px' : header === '대표종목' ? '380px' : '80px', 
                          height: '16px',
                          fontSize: 'clamp(0.6rem, 0.7vw, 0.7rem)'
                        }}
                      >
                        {(() => {
                          if (header === '20일선 이격') {
                            // 20일선 위치 데이터 표시
                            const ticker = row['티커'];
                            if (!ticker) return '-';
                            
                            const position = calculate20DayMAPosition(ticker);
                            const positionValue = parseFloat(position);
                            
                            // 색상 결정
                            let colorClass = 'text-gray-600';
                            if (!isNaN(positionValue)) {
                              if (positionValue > 0) {
                                colorClass = 'text-red-400';
                              } else if (positionValue < 0) {
                                colorClass = 'text-blue-400';
                              }
                            }
                            
                            return (
                              <div className="flex items-center justify-center h-full">
                                <span className={`text-xs font-medium ${colorClass}`} style={{ fontSize: 'clamp(0.6rem, 0.7vw, 0.7rem)' }}>
                                  {position}
                                </span>
                              </div>
                            );
                          } else if (header === '돌파/이탈') {
                            // 돌파/이탈 데이터 표시
                            return (
                              <div className="flex items-center justify-center h-full">
                                {renderCrossover(row['티커'])}
                              </div>
                            );
                          } else if (header === '대표종목') {
                            // 대표종목 데이터 표시
                            const ticker = row['티커'];
                            if (!ticker) return '-';
                            
                            // 티커 변형 생성 (원본, 앞에 0 추가, 앞의 0 제거)
                            const tickerVariations = [
                              ticker,
                              ticker.padStart(6, '0'),
                              ticker.replace(/^0+/, '')
                            ];
                            
                            // 모든 티커 변형에 대해 대표종목 검색
                            let stockList = null;
                            for (const variant of tickerVariations) {
                              if (etfStockList[variant] && etfStockList[variant].length > 0) {
                                stockList = etfStockList[variant];
                                break;
                              }
                            }
                            
                            // 대표종목이 없으면 '-' 반환
                            if (!stockList || stockList.length === 0) {
                              return '-';
                            }
                            
                            // 모든 대표종목 표시
                            return (
                              <div className="flex flex-wrap items-center gap-1">
                                {stockList.map((item, index) => (
                                  <div key={index} className="flex items-center">
                                    <span className="text-xs" style={{ fontSize: 'clamp(0.6rem, 0.7vw, 0.7rem)' }}>{item.name}</span>
                                    {item.rs && (
                                      <span className={`text-xs ${parseInt(item.rs) >= 90 ? 'font-bold' : ''}`} data-component-name="ETFCurrentTable"
                                            style={{ fontSize: 'clamp(0.6rem, 0.7vw, 0.7rem)' }}>
                                        ({item.rs})
                                      </span>
                                    )}
                                  </div>
                                ))}
                              </div>
                            );
                          }
                        })()}
                      </td>
                    ))}
                  </tr>
                );
              });
            })()}
          </tbody>
        </table>
      </div>
    </div>
  );
}
