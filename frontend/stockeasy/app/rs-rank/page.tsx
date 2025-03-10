'use client'

import { Suspense, useState, useEffect, useMemo, useCallback } from 'react'
import Sidebar from '../components/Sidebar'
import Papa from 'papaparse'
import ChartComponent from '../components/ChartComponent'
import { fetchCSVData } from '../utils/fetchCSVData'

// CSV 파일을 파싱하는 함수 (PapaParse 사용)
const parseCSV = (csvText: string): CSVData => {
  console.log('CSV 파싱 시작...');
  console.log('CSV 원본 데이터 길이:', csvText.length);
  console.log('CSV 원본 데이터 처음 부분:', csvText.substring(0, 500));
  
  try {
    if (!csvText || typeof csvText !== 'string') {
      console.error('유효하지 않은 CSV 텍스트:', csvText);
      // 기본 데이터 반환
      return {
        headers: ['날짜', '시가', '고가', '저가', '종가', '거래량'],
        rows: [],
        errors: [],
      };
    }
    
    // Papa Parse 옵션
    const results = Papa.parse(csvText, {
      header: true,       // 첫 번째 행을 헤더로 사용
      skipEmptyLines: true, // 빈 줄 건너뛰기
      dynamicTyping: false,  // 문자열 그대로 유지 (수동 변환)
    });
    
    console.log('파싱 결과 오류:', results.errors);
    console.log('파싱된 데이터 행 수:', results.data.length);
    
    // 컬럼 이름 확인 및 데이터 구조 디버깅
    if (results.data.length > 0) {
      const firstRow = results.data[0] as Record<string, any>;
      console.log('컬럼 확인:');
      for (const key in firstRow) {
        console.log(`- '${key}': ${firstRow[key]}`);
      }
      
      // 첫 번째 행 전체 데이터 출력
      console.log('첫 번째 행 전체 데이터:', JSON.stringify(firstRow));
      
      // 두 번째 행 데이터 (있는 경우)
      if (results.data.length > 1) {
        const secondRow = results.data[1] as Record<string, any>;
        console.log('두 번째 행 전체 데이터:', JSON.stringify(secondRow));
      }
    }
    
    return {
      headers: results.meta.fields || [],
      rows: results.data || [],
      errors: results.errors || [],
    };
  } catch (error) {
    console.error('CSV 파싱 오류:', error);
    // 오류 발생 시 빈 데이터 반환
    return {
      headers: ['날짜', '시가', '고가', '저가', '종가', '거래량'],
      rows: [],
      errors: [],
    };
  }
};

// 정렬 타입 정의
type SortDirection = 'asc' | 'desc' | null;

// CSV 데이터를 파싱한 결과를 위한 인터페이스
interface CSVData {
  headers: string[];
  rows: any[];
  errors: any[]; // 파싱 오류 정보 추가
}

// 차트 데이터 타입 정의
interface CandleData {
  time: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

// RS순위 페이지 컴포넌트
export default function RSRankPage() {
  // 상태 관리
  const [csvData, setCsvData] = useState<CSVData>({ headers: [], rows: [], errors: [] });
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [currentPage, setCurrentPage] = useState<number>(1);
  const [sortKey, setSortKey] = useState<string>('');
  const [sortDirection, setSortDirection] = useState<SortDirection>(null);
  
  // 52주 신고가 데이터 관련 상태
  const [highData, setHighData] = useState<CSVData>({ headers: [], rows: [], errors: [] });
  const [highDataLoading, setHighDataLoading] = useState<boolean>(true);
  const [highDataError, setHighDataError] = useState<string | null>(null);
  
  // 차트 데이터 관련 상태 - 20개의 차트를 위한 상태 배열로 변경
  const [chartDataArray, setChartDataArray] = useState<CandleData[][]>(Array(20).fill([]));
  const [chartLoadingArray, setChartLoadingArray] = useState<boolean[]>(Array(20).fill(true));
  const [chartErrorArray, setChartErrorArray] = useState<string[]>(Array(20).fill('')); 
  const [chartMarketTypes, setChartMarketTypes] = useState<string[]>(Array(20).fill('KOSDAQ'));
  // 종목명을 저장할 상태 추가
  const [chartStockNames, setChartStockNames] = useState<string[]>(Array(20).fill(''));

  // Google Drive 파일 ID 배열 - 제공된 파일 ID로 설정
  const fileIds = [
    '1T2Z88ntuzd2R3cT5oy8Ic3JA09tqFAOf',  // 1.csv
    '1MHUyRPe378V1J2qmSx1sUfMzkMokJv_4',  // 2.csv
    '1WDrfq_8W9HwYdaDcfI7DgpTwdmNxL3Fk',  // 3.csv
    '1wjdXsZtImLFizEl30WeqZkkv4TiaDHqG',  // 4.csv
    '1zEfWp0b0-8WZILvbmKtyh_zYJg5cl0PW',  // 5.csv
    '1CJEyUAoew_QLer37NfiqLwGdMGeiMNEJ',  // 6.csv
    '12n6X15dKl1VjMZMk9AHObYIyat1UNrSE',  // 7.csv
    '1i-bg0pUF8rbMxEkHs1TObOQJXrjbwLcO',  // 8.csv
    '1apwIsOcpqH4R5336nAMsOr_vDG6BBClG',  // 9.csv
    '1st-nzJ2wo3FPtb6SwK8glQcXyJqGx7-k',  // 10.csv
    '1ATorXqqRdjAhKmGINH-AJxOgO7ptLjPm',  // 11.csv
    '1JcTJmbiWGIihVzCppiRxbnppE5GLjCTW',  // 12.csv
    '11hGioHutm5YZBAGUeMzpXDTw4FV0wdmD',  // 13.csv
    '1BxdTOwr97lhxl8YMECl84QLBe09h6wwk',  // 14.csv
    '1W0MuG-PGv_jGSJ44w3hmTFgAoQ0NPgOS',  // 15.csv
    '1178693ZjYkqgP-ieSPhmQ8qCxgbsPG0q',  // 16.csv
    '15CQZTBbinqf0f6rCir2D01bC_VC0aTtG',  // 17.csv
    '1ENe8LRQ_9kQvoOTF_wIL-dT9jXoqJ0Cd',  // 18.csv
    '1IzNpZmIMG-Yk2Z20W2C9TjEWlcdSwWW0',  // 19.csv
    '1f2K3mrwuaZUfDX4Mkl89pmG33DbFiL8G'   // 20.csv
  ];
  
  useEffect(() => {
    const fetchCSVData = async () => {
      setLoading(true);
      setError(null);
      
      try {
        // 캐시된 데이터 확인
        const cachedDataJSON = localStorage.getItem('stockEasyData');
        const cachedTimestamp = localStorage.getItem('stockEasyTimestamp');
        const currentTime = new Date().getTime();
        
        // 캐시 유효 시간 (24시간 = 86400000 밀리초)
        const CACHE_TTL = 24 * 60 * 60 * 1000; // 24시간
        
        // 캐시 유효성 확인 (24시간 이내에 캐시된 데이터인지)
        const isCacheValid = cachedDataJSON !== null && cachedTimestamp !== null && 
                          (currentTime - Number(cachedTimestamp)) < CACHE_TTL;
        
        // 캐시가 유효하면 캐시된 데이터 사용
        if (isCacheValid) {
          console.log('로컬 캐시에서 데이터 로드 중...');
          const parsedData = JSON.parse(cachedDataJSON);
          setCsvData(parsedData);
          setLoading(false);
          console.log(`캐시에서 ${parsedData.rows.length}개 데이터 로드 완료`);
          return;
        }
        
        console.log('캐시가 없거나 만료됨. Google Drive에서 데이터 가져오는 중...');
        // Google Drive 파일 ID (RS 랭크 데이터)
        const fileId = '1UYJVdMZFXarsxs0jy16fEGfRqY9Fs8YD'; // 원래 RS 랭크 데이터 파일 ID로 복원
        
        // API를 통해 Google Drive 파일 가져오기
        const response = await fetch('/api/stocks', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ fileId }),
        });
        
        if (!response.ok) {
          throw new Error('데이터를 가져오는데 실패했습니다.');
        }
        
        const csvText = await response.text();
        
        // CSV 파싱 및 데이터 처리
        const parsedData = parseCSV(csvText);
        console.log(`파싱 완료: ${parsedData.rows.length}개 데이터 로드됨`);
        console.log('파싱된 헤더:', parsedData.headers);
        
        // 데이터 필터링 및 처리 - 시가총액 2천억 이상만 저장
        const filteredData = parsedData.rows.filter((row: any) => {
          // 시가총액 필드가 있는 경우에만 필터링 적용
          if ('시가총액' in row) {
            const marketCap = Number(row['시가총액'] || 0);
            return marketCap >= 200000000000; // 2천억 이상 필터링
          }
          return true; // 시가총액 필드가 없는 경우 모든 데이터 포함
        });
        
        const processedData = {
          headers: parsedData.headers,
          rows: filteredData,
          errors: parsedData.errors,
        };
        
        // localStorage에 데이터 저장 - 타임스탬프는 현재 시간(밀리초)으로 저장
        localStorage.setItem('stockEasyData', JSON.stringify(processedData));
        localStorage.setItem('stockEasyTimestamp', String(currentTime));
        localStorage.setItem('stockEasyLastUpdate', String(currentTime));
        
        setCsvData(processedData);
        setLoading(false);
        console.log(`필터링 후 ${filteredData.length}개 데이터 캐시 저장 완료`);
      } catch (err) {
        console.error('CSV 데이터 로딩 오류:', err);
        setError('데이터를 불러오는 중 오류가 발생했습니다.');
        setLoading(false);
      }
    };
    
    fetchCSVData();
  }, []);

  // 52주 신고가 데이터 불러오기
  useEffect(() => {
    const fetchHighData = async () => {
      setHighDataLoading(true);
      setHighDataError(null);
      
      try {
        // 캐시된 데이터 확인
        const cachedDataJSON = localStorage.getItem('stockEasyHighData');
        const cachedTimestamp = localStorage.getItem('stockEasyHighTimestamp');
        const currentTime = new Date().getTime();
        
        // 캐시 유효 시간 (24시간 = 86400000 밀리초)
        const CACHE_TTL = 24 * 60 * 60 * 1000; // 24시간
        
        // 캐시 유효성 확인 (24시간 이내에 캐시된 데이터인지)
        const isCacheValid = cachedDataJSON !== null && cachedTimestamp !== null && 
                          (currentTime - Number(cachedTimestamp)) < CACHE_TTL;
        
        // 캐시가 유효하면 캐시된 데이터 사용
        if (isCacheValid) {
          console.log('로컬 캐시에서 52주 신고가 데이터 로드 중...');
          const parsedData = JSON.parse(cachedDataJSON);
          setHighData(parsedData);
          setHighDataLoading(false);
          console.log(`캐시에서 ${parsedData.rows.length}개 52주 신고가 데이터 로드 완료`);
          return;
        }
        
        console.log('캐시가 없거나 만료됨. Google Drive에서 52주 신고가 데이터 가져오는 중...');
        // Google Drive 파일 ID (52주 신고가 데이터)
        const fileId = '1mbee4O9_NoNpfIAExI4viN8qcN8BtTXz'; // 원래 52주 신고가 데이터 파일 ID로 복원
        
        // API를 통해 Google Drive 파일 가져오기
        const response = await fetch('/api/stocks', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ fileId }),
        });
        
        if (!response.ok) {
          throw new Error('52주 신고가 데이터를 가져오는데 실패했습니다.');
        }
        
        const csvText = await response.text();
        
        // CSV 파싱 및 데이터 처리
        const parsedData = parseCSV(csvText);
        
        // 데이터 필터링 및 처리 - 시가총액 2천억 이상만 저장
        const filteredData = parsedData.rows.filter((row: any) => {
          // 시가총액 필드가 있는 경우에만 필터링 적용
          if ('시가총액' in row) {
            const marketCap = Number(row['시가총액'] || 0);
            return marketCap >= 200000000000; // 2천억 이상 필터링
          }
          return true; // 시가총액 필드가 없는 경우 모든 데이터 포함
        });
        
        const processedData = {
          headers: parsedData.headers,
          rows: filteredData,
          errors: parsedData.errors,
        };
        
        // 데이터 캐시에 저장
        localStorage.setItem('stockEasyHighData', JSON.stringify(processedData));
        localStorage.setItem('stockEasyHighTimestamp', String(currentTime));
        localStorage.setItem('stockEasyHighLastUpdate', String(currentTime));
        
        setHighData(processedData);
        console.log(`Google Drive에서 ${processedData.rows.length}개 52주 신고가 데이터 로드 완료`);
      } catch (err) {
        console.error('52주 신고가 데이터 가져오기 오류:', err);
        setHighDataError(`데이터를 불러오는데 실패했습니다: ${err instanceof Error ? err.message : '알 수 없는 오류'}`);
      } finally {
        setHighDataLoading(false);
      }
    };
    
    fetchHighData();
  }, []);

  // 차트 데이터 로드 함수
  const loadAllChartData = async () => {
    try {
      console.log('차트 데이터 로드 시작');
      
      // 캐시된 데이터 확인
      const cachedChartDataJSON = localStorage.getItem('stockEasyChartData');
      const cachedChartStockNames = localStorage.getItem('stockEasyChartStockNames');
      const cachedChartMarketTypes = localStorage.getItem('stockEasyChartMarketTypes');
      const cachedChartTimestamp = localStorage.getItem('stockEasyChartTimestamp');
      const currentDate = new Date().toISOString().split('T')[0]; // 현재 날짜 (YYYY-MM-DD 형식)
      const currentTime = new Date().getTime();
      
      // 캐시 유효 시간 (24시간 = 86400000 밀리초)
      const CACHE_TTL = 24 * 60 * 60 * 1000; // 24시간
      
      // 캐시 유효성 확인 (24시간 이내에 캐시된 데이터인지)
      const isCacheValid = cachedChartDataJSON !== null && 
                           cachedChartTimestamp !== null && 
                           cachedChartStockNames !== null && 
                           cachedChartMarketTypes !== null && 
                           parseInt(cachedChartTimestamp) >= currentTime - CACHE_TTL;
      
      if (isCacheValid) {
        try {
          console.log('캐시된 차트 데이터 확인 중...');
          
          // 캐시된 데이터 파싱
          const parsedChartData = JSON.parse(cachedChartDataJSON);
          const parsedStockNames = JSON.parse(cachedChartStockNames);
          const parsedMarketTypes = JSON.parse(cachedChartMarketTypes);
          
          // 데이터 유효성 검사
          if (Array.isArray(parsedChartData) && parsedChartData.length === 20 &&
              Array.isArray(parsedStockNames) && parsedStockNames.length === 20 &&
              Array.isArray(parsedMarketTypes) && parsedMarketTypes.length === 20) {
            
            // 캐시된 데이터 설정
            setChartDataArray(parsedChartData);
            setChartStockNames(parsedStockNames);
            setChartMarketTypes(parsedMarketTypes);
            setChartLoadingArray(Array(20).fill(false));
            console.log('캐시된 차트 데이터 로드 완료');
            return; // 캐시된 데이터를 사용했으므로 함수 종료
          } else {
            console.warn('캐시된 차트 데이터 형식이 올바르지 않습니다. 새로운 데이터를 로드합니다.');
          }
        } catch (error) {
          console.error('캐시된 차트 데이터 파싱 오류:', error);
          // 캐시 파싱 오류 시 계속 진행하여 새로운 데이터 로드
        }
      } else {
        console.log('캐시가 없거나 유효하지 않음. 새로운 차트 데이터를 로드합니다.');
        console.log(`캐시 상태: 데이터=${!!cachedChartDataJSON}, 타임스탬프=${cachedChartTimestamp}, 현재날짜=${currentDate}`);
      }
      
      // 캐시가 없거나 유효하지 않은 경우 새로운 데이터 로드
      console.log('새로운 차트 데이터 로드 시작');
      
      // 차트 데이터, 종목명, 시장 구분을 저장할 배열
      const newChartDataArray: CandleData[][] = Array(20).fill(null).map(() => []);
      const newStockNames: string[] = Array(20).fill('').map((_, i) => '');
      const newMarketTypes: string[] = Array(20).fill('');
      
      // 로딩 상태 배열 복사
      const newChartLoadingArray = [...chartLoadingArray];
      const newChartErrorArray = [...chartErrorArray];
      
      // 시장 구분 데이터를 미리 로드하기 위한 맵 생성
      const marketTypeMap: Record<string, string> = {};
      
      // 병렬 로드를 위한 Promise 배열
      const loadPromises = fileIds.map((fileId: string, index: number) => {
        return (async () => {
          try {
            // 종목명 설정 - CSV 데이터에서 추출
            const response = await fetch('/api/chart-data', {
              method: 'POST',
              headers: {
                'Content-Type': 'application/json',
              },
              body: JSON.stringify({ 
                fileId: fileId.trim() // 파일 ID 공백 제거
              }),
            });
            
            if (!response.ok) {
              throw new Error(`API 응답 오류: ${response.status} ${response.statusText}`);
            }
            
            const result = await response.json();
            const csvText = result.data;
            
            console.log(`차트 ${index + 1} 데이터 로드 완료: ${csvText.length}자`);
            
            // CSV 파싱 최적화 - 한 번의 파싱으로 모든 필요한 정보 추출
            const { chartData, stockName, marketType } = parseCSVOptimized(csvText, index);
            
            // 추출한 데이터 저장
            newChartDataArray[index] = chartData;
            newStockNames[index] = stockName;
            newMarketTypes[index] = marketType;
            
            // 시장 구분 맵에 저장
            if (stockName) {
              marketTypeMap[stockName] = marketType;
            }
            
            // 로딩 상태 업데이트
            newChartLoadingArray[index] = false;
            
            console.log(`차트 ${index + 1} 데이터 처리 완료: ${chartData.length}개 데이터 포인트`);
          } catch (error) {
            console.error(`차트 ${index + 1} 데이터 로드 오류:`, error);
            newChartErrorArray[index] = error instanceof Error ? error.message : String(error);
            newChartLoadingArray[index] = false;
          }
        })();
      });
      
      // 모든 Promise 완료 대기
      await Promise.all(loadPromises);
      
      // 상태 업데이트
      setChartDataArray(newChartDataArray);
      setChartStockNames(newStockNames);
      setChartMarketTypes(newMarketTypes);
      setChartLoadingArray(newChartLoadingArray);
      setChartErrorArray(newChartErrorArray);
      
      // 시장 구분 데이터 캐싱
      localStorage.setItem('stockEasyMarketTypeMap', JSON.stringify(marketTypeMap));
      
      // 차트 데이터 캐싱
      localStorage.setItem('stockEasyChartData', JSON.stringify(newChartDataArray));
      localStorage.setItem('stockEasyChartStockNames', JSON.stringify(newStockNames));
      localStorage.setItem('stockEasyChartMarketTypes', JSON.stringify(newMarketTypes));
      localStorage.setItem('stockEasyChartTimestamp', currentTime.toString());
      
      console.log('모든 차트 데이터 로드 및 캐싱 완료');
    } catch (error) {
      console.error('차트 데이터 로드 중 오류 발생:', error);
    }
  };
  
  // 차트 데이터 로드 함수 호출을 위한 useEffect 추가
  useEffect(() => {
    // 모든 차트 로딩 상태 초기화
    setChartLoadingArray(Array(20).fill(true));
    setChartErrorArray(Array(20).fill('')); 
    
    loadAllChartData();
  }, []);

  // CSV 파싱 최적화 함수 - 한 번의 파싱으로 모든 필요한 정보 추출
  const parseCSVOptimized = (csvText: string, index: number): { chartData: CandleData[], stockName: string, marketType: string } => {
    try {
      // 헤더 행 추출을 위한 첫 번째 파싱
      const firstLineEnd = csvText.indexOf('\n');
      if (firstLineEnd === -1) {
        console.error(`차트 ${index + 1} CSV 형식 오류: 줄바꿈 문자를 찾을 수 없습니다.`);
        return { chartData: [], stockName: `종목 ${index + 1}`, marketType: 'KOSPI' };
      }
      
      const headerLine = csvText.substring(0, firstLineEnd);
      const headers = headerLine.split(',').map(h => h.trim());
      
      // 필요한 컬럼 인덱스 찾기
      const stockNameIndex = headers.findIndex(h => h === '종목명');
      const marketTypeIndex = headers.findIndex(h => h === '시장구분');
      const dateIndex = headers.findIndex(h => h === '일자');
      const openIndex = headers.findIndex(h => h === '시가');
      const highIndex = headers.findIndex(h => h === '고가');
      const lowIndex = headers.findIndex(h => h === '저가');
      const closeIndex = headers.findIndex(h => h === '종가');
      const volumeIndex = headers.findIndex(h => h === '거래량');
      
      // 전체 데이터 파싱
      const results = Papa.parse(csvText, {
        header: true,
        skipEmptyLines: true,
        dynamicTyping: true,
      });
      
      // 종목명과 시장구분 추출
      let stockName = `종목 ${index + 1}`;
      let marketType = 'KOSPI';
      
      if (results.data.length > 0) {
        const firstRow = results.data[0] as any;
        
        if (stockNameIndex !== -1 && firstRow[headers[stockNameIndex]]) {
          stockName = firstRow[headers[stockNameIndex]].toString();
        }
        
        if (marketTypeIndex !== -1 && firstRow[headers[marketTypeIndex]]) {
          marketType = firstRow[headers[marketTypeIndex]].toString();
        }
      }
      
      // 차트 데이터 변환
      const chartData: CandleData[] = results.data
        .filter(row => row && typeof row === 'object')
        .map((row: any) => {
          const dateKey = headers[dateIndex];
          const openKey = headers[openIndex];
          const highKey = headers[highIndex];
          const lowKey = headers[lowIndex];
          const closeKey = headers[closeIndex];
          const volumeKey = headers[volumeIndex];
          
          return {
            time: row[dateKey]?.toString() || '',
            open: parseFloat(row[openKey]) || 0,
            high: parseFloat(row[highKey]) || 0,
            low: parseFloat(row[lowKey]) || 0,
            close: parseFloat(row[closeKey]) || 0,
            volume: parseFloat(row[volumeKey]) || 0,
          };
        })
        .filter(item => item.time && !isNaN(item.open) && !isNaN(item.high) && !isNaN(item.low) && !isNaN(item.close));
      
      return { chartData, stockName, marketType };
    } catch (error) {
      console.error(`차트 ${index + 1} 데이터 파싱 오류:`, error);
      return { chartData: [], stockName: `종목 ${index + 1}`, marketType: 'KOSPI' };
    }
  };

  // 데이터 정렬 함수
  const sortData = (data: any[], key: string, direction: SortDirection) => {
    if (!direction) return [...data];
    
    return [...data].sort((a, b) => {
      // 숫자로 변환 가능한 경우 숫자 정렬
      if (!isNaN(Number(a[key])) && !isNaN(Number(b[key]))) {
        return direction === 'asc' 
          ? Number(a[key]) - Number(b[key])
          : Number(b[key]) - Number(a[key]);
      }
      
      // 문자열 정렬
      if (a[key] < b[key]) return direction === 'asc' ? -1 : 1;
      if (a[key] > b[key]) return direction === 'asc' ? 1 : -1;
      return 0;
    });
  };

  // 정렬 요청 핸들러
  const requestSort = (key: string) => {
    let direction: SortDirection = 'asc';
    if (sortKey === key) {
      if (sortDirection === 'asc') direction = 'desc';
      else if (sortDirection === 'desc') direction = null;
      else direction = 'asc';
    }
    setSortKey(key);
    setSortDirection(direction);
  };

  // 셀의 정렬 방향을 결정하는 함수
  const getCellAlignment = (header: string) => {
    // RS 관련 수치들은 가운데 정렬
    if (header.startsWith('RS') || ['MMT'].includes(header)) {
      return 'text-center';
    }
    
    // 종목코드는 가운데 정렬
    if (header === '종목코드') {
      return 'text-center';
    }
    
    // 시가총액 컬럼은 우측 정렬
    if (header === '시가총액' || header === '시가총액(억)') {
      return 'text-right';
    }
    
    // 다른 숫자 컬럼은 우측 정렬
    if (['RS_Rank', 'RS_Rank_Prev', 'RS_Rank_Change'].includes(header)) {
      return 'text-right';
    }
    
    // 기본값은 좌측 정렬
    return 'text-left';
  };

  // 시가총액을 억 단위로 포맷팅하는 함수
  const formatMarketCap = (value: string) => {
    // 숫자가 아니면 그대로 반환
    if (isNaN(Number(value))) return value;
    
    // 숫자로 변환 후 억 단위로 나누고 소수점 없이 표시
    const marketCapInBillions = Math.round(Number(value) / 100000000);
    
    // 천 단위 구분 쉼표(,) 추가하고 '억' 단위 추가
    return marketCapInBillions.toLocaleString('ko-KR') + '억';
  };

  // 현재 페이지에 표시할 데이터 계산
  const currentPageData = useMemo(() => {
    if (!csvData || !csvData.rows) {
      return [];
    }
    
    // 시가총액 2천억 이상 필터링 적용
    const filteredByMarketCap = csvData.rows.filter((row: any) => {
      const marketCap = Number(row['시가총액'] || 0);
      const isAboveThreshold = marketCap >= 200000000000; // 2천억 이상
      
      // 디버깅을 위한 로그 추가
      if (!isAboveThreshold && marketCap > 0) {
        console.log(`필터링: 시가총액 2천억 미만 종목 제외 - ${row['종목명']} (${marketCap.toLocaleString('ko-KR')}원)`);
      }
      
      return isAboveThreshold;
    });
    
    console.log(`원본 데이터: ${csvData.rows.length}개, 시가총액 2천억 이상 필터링 후: ${filteredByMarketCap.length}개`);
    
    // 정렬된 데이터 가져오기
    const sortedData = sortDirection 
      ? sortData(filteredByMarketCap, sortKey, sortDirection)
      : filteredByMarketCap;
    
    const startIndex = (currentPage - 1) * 20;
    return sortedData.slice(startIndex, startIndex + 20);
  }, [csvData, currentPage, sortKey, sortDirection]);

  // 총 페이지 수 계산 - 필터링된 데이터 기준으로 계산
  const totalPages = useMemo(() => {
    if (!csvData || !csvData.rows) return 0;
    
    // 시가총액 2천억 이상 필터링 적용
    const filteredCount = csvData.rows.filter((row: any) => {
      const marketCap = Number(row['시가총액'] || 0);
      return marketCap >= 200000000000; // 2천억 이상
    }).length;
    
    return Math.ceil(filteredCount / 20);
  }, [csvData]);

  // 페이지 변경 핸들러
  const handlePageChange = useCallback((page: number) => {
    setCurrentPage(page);
  }, []);

  // 헤더 이름을 변환하는 함수
  const formatHeaderName = (header: string) => {
    // 시가총액 헤더를 시가총액(억)으로 변경
    if (header === '시가총액') {
      return '시가총액(억)';
    }
    return header;
  };

  // 테이블 셀 값을 포맷팅하는 함수
  const formatCellValue = (header: string, value: string) => {
    // 종목코드인 경우 6자리로 포맷팅 (앞에 0 채우기)
    if (header === '종목코드') {
      // 숫자가 아니면 그대로 반환
      if (isNaN(Number(value))) return value;
      
      // 6자리로 포맷팅 (앞에 0 채우기)
      return value.padStart(6, '0');
    }
    
    // 시가총액 컬럼인 경우 억 단위로 포맷팅
    if (header === '시가총액' || header === '시가총액(억)') {
      // 숫자가 아니면 그대로 반환
      if (isNaN(Number(value))) return value;
      
      // 숫자로 변환 후 억 단위로 나누고 소수점 없이 표시
      const marketCapInBillions = Math.round(Number(value) / 100000000);
      
      // 천 단위 구분 쉼표(,) 추가
      return marketCapInBillions.toLocaleString('ko-KR');
    }
    
    // 종목코드가 아닌 숫자인 경우에만 천 단위 구분 쉼표(,) 추가
    if (!isNaN(Number(value)) && value !== '') {
      return Number(value).toLocaleString('ko-KR');
    }
    
    // 다른 컬럼은 그대로 표시
    return value || '';
  };

  // 52주 신고가 및 RS 순위 데이터 매칭하여 보여줄 데이터 생성
  const combinedHighData = useMemo(() => {
    if (!highData.rows || !csvData.rows) return [];
    
    // 52주 신고가 데이터 전체를 사용하고 매칭 정보 생성
    const mappedData = highData.rows.map((highRow: any) => {
      // 종목코드로 RS 순위 데이터에서 매칭되는 항목 찾기
      // 종목코드 형식을 맞추기 위해 문자열로 변환하여 비교
      const matchingRSRow = csvData.rows.find((rsRow: any) => 
        String(rsRow['종목코드']).trim() === String(highRow['종목코드']).trim()
      );
      
      // 매칭된 정보 합치기
      return {
        // 52주 신고가 데이터에서 가져오기
        '종목코드': highRow['종목코드'],
        '종목명': highRow['종목명'],
        '거래대금': highRow['거래대금'] || '0',
        
        // RS 순위 데이터에서 가져오기 (매칭된 경우만)
        'RS': matchingRSRow ? matchingRSRow['RS'] : '-',
        '시가총액': matchingRSRow ? matchingRSRow['시가총액'] : '0',
        '업종': matchingRSRow ? matchingRSRow['업종'] : '-'
      };
    });
    
    // 거래대금이 0인 항목 제외 및 시가총액 2천억 이상인 종목만 필터링
    const filteredData = mappedData.filter((item) => {
      // 거래대금이 0인 항목 제외
      if (item['거래대금'] === '0') return false;
      
      // 시가총액 필터링 - 2천억 이상만 포함
      const marketCap = Number(item['시가총액'] || 0);
      return marketCap >= 200000000000; // 2천억 이상 필터링
    });
    
    // RS 값 기준으로 내림차순 정렬 (RS 값이 높은 순)
    return filteredData.sort((a, b) => {
      // RS 값이 '-'인 경우 가장 낮은 순위로 처리
      if (a['RS'] === '-') return 1;
      if (b['RS'] === '-') return -1;
      
      // 숫자로 변환하여 내림차순 정렬 (큰 값이 먼저 오도록)
      return Number(b['RS']) - Number(a['RS']);
    });
  }, [highData.rows, csvData.rows]);

  // 페이지 로드 시 스크롤 위치를 최상단으로 설정하는 useEffect 추가
  useEffect(() => {
    // 페이지 로드 시 스크롤 위치를 최상단(0, 0)으로 설정
    window.scrollTo(0, 0);
    
    // 스크롤 이벤트 리스너 추가 - 페이지 로드 직후 스크롤이 발생하는 것을 방지
    const preventInitialScroll = () => {
      window.scrollTo(0, 0);
    };
    
    // 여러 이벤트에 리스너 등록
    window.addEventListener('load', preventInitialScroll);
    window.addEventListener('DOMContentLoaded', preventInitialScroll);
    
    // 100ms 후에도 한 번 더 스크롤 위치 조정 (비동기 로딩 콘텐츠 대응)
    const timeoutId = setTimeout(() => {
      window.scrollTo(0, 0);
    }, 100);
    
    // 클린업 함수
    return () => {
      window.removeEventListener('load', preventInitialScroll);
      window.removeEventListener('DOMContentLoaded', preventInitialScroll);
      clearTimeout(timeoutId);
    };
  }, []);

  return (
    <div className="flex h-screen bg-gray-100">
      {/* 사이드바 */}
      <Suspense fallback={<div>로딩 중...</div>}>
        <Sidebar />
      </Suspense>
      
      {/* 메인 콘텐츠 - 왼쪽 여백을 추가하여 고정된 사이드바와 겹치지 않도록 함 */}
      <div className="flex-1 p-3 ml-[59px] flex flex-col">
        {/* 상단 헤더 - 브랜드 표시 */}
        <div className="flex justify-between items-center mb-1">
          <div className="flex items-center">
            <h1 className="text-lg font-bold">StockEasy</h1>
          </div>
          <div className="text-xs text-gray-600">(주)인텔리오</div>
        </div>
        
        {/* 상단 여백 추가 - 여백 조정 */}
        <div className="mb-2"></div>
        
        {/* 7:3 비율의 레이아웃 구성 */}
        <div className="flex flex-1 gap-1 flex-col">
          {/* 상단 영역 - 테이블 및 우측 정보 */}
          <div className="flex gap-1">
            {/* 메인 테이블 영역 (70%) */}
            <div className="w-[70%] bg-white rounded-lg shadow p-4">
              {loading ? (
                <div className="text-center py-4">데이터를 불러오는 중입니다...</div>
              ) : error ? (
                <div className="text-red-500 text-center py-4">{error}</div>
              ) : csvData ? (
                <div className="flex flex-col h-full">
                  <div className="flex justify-between items-center mb-3">
                    <h2 className="text-lg font-semibold">RS순위</h2>
                    <span className="text-xs text-gray-600">RS는 특정 주식이 시장 또는 비교 대상에 비해 상대적으로 강한 움직임을 보이는지 수치화한 지표입니다.</span>
                  </div>
                  <div 
                    className="overflow-x-auto"
                    style={{ overflowX: 'hidden' }}
                  >
                    <table className="w-full bg-white border border-gray-200 table-fixed">
                      <thead>
                        <tr className="bg-gray-100">
                          {csvData.headers.map((header, index) => (
                            <th 
                              key={index} 
                              className="py-2.5 px-3 border-b border-r text-center whitespace-nowrap cursor-pointer hover:bg-gray-200"
                              style={{ 
                                width: header === '종목명' ? '100px' : 
                                       header === '테마명' ? '220px' :
                                       header === '시가총액' ? '60px' : 
                                       header === '종목코드' ? '60px' : 
                                       header === 'RS' || header === 'RS 1W' || header === 'RS 4W' || header === 'RS 12W' || header === 'MMT' ? '45px' :
                                       header === 'RS_1M' || header === 'RS_2M' || header === 'RS_3M' ? '40px' :
                                       header === '업종' ? '220px' : '70px',
                                fontSize: '0.875rem'
                              }}
                              onClick={() => requestSort(header)}
                            >
                              <div className="flex items-center justify-center">
                                <span>{formatHeaderName(header)}</span>
                                {sortKey === header && (
                                  <span className="ml-1">
                                    {sortDirection === 'asc' ? '▲' : '▼'}
                                  </span>
                                )}
                              </div>
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {currentPageData.map((row, rowIndex) => (
                          <tr key={rowIndex} className={rowIndex % 2 === 0 ? 'bg-gray-50' : 'bg-white'}>
                            {csvData.headers.map((header, colIndex) => (
                              <td 
                                key={colIndex} 
                                className={`py-1.5 px-2 border-b border-r ${getCellAlignment(header)} whitespace-nowrap overflow-hidden text-ellipsis`}
                                style={{ 
                                  width: header === '종목명' ? '100px' : 
                                          header === '테마명' ? '220px' :
                                          header === '시가총액' ? '60px' :
                                          header === '종목코드' ? '60px' : 
                                          header === 'RS' || header === 'RS 1W' || header === 'RS 4W' || header === 'RS 12W' || header === 'MMT' ? '45px' :
                                          header === 'RS_1M' || header === 'RS_2M' || header === 'RS_3M' ? '40px' :
                                          header === '업종' ? '220px' : '70px',
                                  fontSize: '0.875rem'
                                }}
                              >
                                {formatCellValue(header, row[header])}
                              </td>
                            ))}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  
                  {/* 페이지네이션 */}
                  <div className="flex flex-col items-center pt-4 pb-0 mt-0 mb-0">
                    <nav className="flex items-center justify-center">
                      <button
                        onClick={() => handlePageChange(1)}
                        disabled={currentPage === 1}
                        className={`px-1.5 py-0.5 mx-0.5 rounded text-sm ${
                          currentPage === 1 ? 'bg-gray-200 text-gray-500' : 'bg-blue-500 text-white hover:bg-blue-600'
                        }`}
                      >
                        {'<<'}
                      </button>
                      <button
                        onClick={() => handlePageChange(currentPage - 1)}
                        disabled={currentPage === 1}
                        className={`px-2 py-0.5 mx-0.5 rounded text-sm ${
                          currentPage === 1 ? 'bg-gray-200 text-gray-500' : 'bg-blue-500 text-white hover:bg-blue-600'
                        }`}
                      >
                        이전
                      </button>
                      <div className="px-3 text-sm">
                        {currentPage} / {totalPages}
                      </div>
                      <button
                        onClick={() => handlePageChange(currentPage + 1)}
                        disabled={currentPage === totalPages}
                        className={`px-2 py-0.5 mx-0.5 rounded text-sm ${
                          currentPage === totalPages ? 'bg-gray-200 text-gray-500' : 'bg-blue-500 text-white hover:bg-blue-600'
                        }`}
                      >
                        다음
                      </button>
                      <button
                        onClick={() => handlePageChange(totalPages)}
                        disabled={currentPage === totalPages}
                        className={`px-1.5 py-0.5 mx-0.5 rounded text-sm ${
                          currentPage === totalPages ? 'bg-gray-200 text-gray-500' : 'bg-blue-500 text-white hover:bg-blue-600'
                        }`}
                      >
                        {'>>'}
                      </button>
                    </nav>
                  </div>
                </div>
              ) : (
                <p className="text-gray-700">데이터가 없습니다.</p>
              )}
            </div>
            
            {/* 우측 영역 - 52주 신고가 섹션 */}
            <div className="w-[30%] bg-white rounded-lg shadow p-4">
              {/* 금주 52주 신고가 정보 영역 */}
              <div className="flex flex-col">
                <div className="flex justify-between items-center mb-3">
                  <h2 className="text-lg font-semibold">52주 신고가</h2>
                  <span className="text-xs text-gray-600">당일 52주 신고가중 RS값이 높은 순서대로 리스트업합니다.</span>
                </div>
                <div className="flex-1" style={{ overflowX: 'hidden' }}>
                  {/* 신고가 데이터 테이블 */}
                  {highDataLoading ? (
                    <div className="flex-1 flex items-center justify-center">
                      <span className="text-gray-400">데이터를 불러오는 중입니다...</span>
                    </div>
                  ) : highDataError ? (
                    <div className="flex-1 flex items-center justify-center">
                      <span className="text-red-500">{highDataError}</span>
                    </div>
                  ) : highData && csvData ? (
                    <table className="w-full bg-white border border-gray-200 table-fixed">
                      <thead>
                        <tr className="bg-gray-100">
                          <th className="py-2.5 px-0 border-b border-r cursor-pointer hover:bg-gray-200" style={{width: '60px', fontSize: '0.875rem', textAlign: 'center'}}>종목코드</th>
                          <th className="py-2.5 px-0 border-b border-r cursor-pointer hover:bg-gray-200" style={{width: '100px', fontSize: '0.875rem', textAlign: 'center'}}>종목명</th>
                          <th className="py-2.5 px-0 border-b border-r cursor-pointer hover:bg-gray-200" style={{width: '45px', fontSize: '0.875rem', textAlign: 'center'}}>RS</th>
                          <th className="py-2.5 px-0 border-b border-r cursor-pointer hover:bg-gray-200" style={{width: '60px', fontSize: '0.875rem', textAlign: 'center'}}>시가총액</th>
                          <th className="py-2.5 px-0 border-b border-r cursor-pointer hover:bg-gray-200" style={{width: '60px', fontSize: '0.875rem', textAlign: 'center'}}>거래대금</th>
                          <th className="py-2.5 px-0 border-b border-r cursor-pointer hover:bg-gray-200" style={{width: '120px', fontSize: '0.875rem', textAlign: 'center'}}>업종</th>
                        </tr>
                      </thead>
                      <tbody>
                        {/* 매칭된 데이터 표시 - 최대 20개만 표시 */}
                        {combinedHighData.slice(0, 20).map((row: any, rowIndex: number) => (
                          <tr key={rowIndex} className={rowIndex % 2 === 0 ? 'bg-gray-50' : 'bg-white'}>
                            <td className="py-1.5 px-2 border-b border-r text-center whitespace-nowrap" style={{width: '60px', fontSize: '0.875rem'}}>{row['종목코드']}</td>
                            <td className="py-1.5 px-2 border-b border-r whitespace-nowrap overflow-hidden text-ellipsis" style={{width: '100px', fontSize: '0.875rem'}}>{row['종목명']}</td>
                            <td className="py-1.5 px-2 border-b border-r text-center whitespace-nowrap" style={{width: '45px', fontSize: '0.875rem'}}>{row['RS']}</td>
                            <td className="py-1.5 px-2 border-b border-r text-right whitespace-nowrap" style={{width: '60px', fontSize: '0.875rem'}}>{formatCellValue('시가총액', row['시가총액'])}</td>
                            <td className="py-1.5 px-2 border-b border-r text-right whitespace-nowrap" style={{width: '60px', fontSize: '0.875rem'}}>{formatCellValue('거래대금', row['거래대금'])}</td>
                            <td className="py-1.5 px-2 border-b border-r text-center break-words" style={{width: '120px', fontSize: '0.8rem'}}>{row['업종']}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  ) : (
                    <div className="flex-1 flex items-center justify-center">
                      <span className="text-gray-400">데이터가 없습니다.</span>
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>
          
          {/* RS상위 시장 비교차트 영역 */}
          <div className="bg-white rounded-lg shadow p-4 mt-1">
            <div className="flex justify-between items-center mb-3">
              <h2 className="text-lg font-semibold">RS상위 시장 비교차트</h2>
              <span className="text-xs text-gray-600">RS상위와 시가총액 순서로 해당 종목이 속한 시장 지수를 비교합니다.</span>
            </div>
            
            {/* 7줄에 3개의 차트를 가로로 배치 */}
            {Array(7).fill(0).map((_, rowIndex) => (
              <div key={rowIndex} className="flex flex-row gap-1 mb-4">
                {Array(3).fill(0).map((_, colIndex) => {
                  const index = rowIndex * 3 + colIndex;
                  return (
                    <div key={colIndex} className="flex-1 rounded-md p-1">
                      {chartLoadingArray[index] ? (
                        <div className="h-80 flex items-center justify-center border border-dashed border-gray-300 rounded-md">
                          <span className="text-gray-400">차트 데이터를 불러오는 중입니다...</span>
                        </div>
                      ) : chartErrorArray[index] ? (
                        <div className="h-80 flex items-center justify-center border border-dashed border-gray-300 rounded-md">
                          <span className="text-red-500">{chartErrorArray[index]}</span>
                        </div>
                      ) : chartDataArray[index]?.length > 0 ? (
                        <ChartComponent 
                          data={chartDataArray[index]} 
                          height={320}
                          showVolume={true}
                          marketType={chartMarketTypes[index]}
                          stockName={chartStockNames[index]}
                          title={`${chartStockNames[index]} (${chartMarketTypes[index]})`}
                        />
                      ) : (
                        <div className="h-80 flex items-center justify-center border border-dashed border-gray-300 rounded-md">
                          <span className="text-gray-400">표시할 차트 데이터가 없습니다.</span>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
