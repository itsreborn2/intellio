'use client'

import { Suspense, useState, useEffect, useMemo, useCallback, useRef } from 'react'
import { useRouter, useSearchParams } from 'next/navigation';
import Papa from 'papaparse';
import { format, subDays, parse, isValid } from 'date-fns'; // parse, isValid 추가
import { formatDateMMDD } from '../utils/dateUtils';
import ChartComponent from '../components/ChartComponent'
import { fetchCSVData } from '../utils/fetchCSVData'
import html2canvas from 'html2canvas';
import TableCopyButton from '../components/TableCopyButton';
// RS 컬럼 툴팁용 GuideTooltip 컴포넌트 import
import { GuideTooltip } from 'intellio-common/components/ui/GuideTooltip';
import { CheckIcon } from '@heroicons/react/24/solid'; // CheckIcon import 추가
import { CheckCircleIcon } from '@heroicons/react/24/solid'; // CheckCircleIcon 추가
import MTTtopchart from './MTTtopchart'; // MTT 상위 차트 컴포넌트 추가

// CSV 파일을 파싱하는 함수 (PapaParse 사용)
const parseCSV = (csvText: string): CSVData => {
  // 중요 로그만 유지
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
  
  // 중요 오류 로그만 유지
  if (results.errors && results.errors.length > 0) {
    console.error('CSV 파싱 오류:', results.errors);
  }
  
  return {
    headers: results.meta.fields || [],
    rows: results.data || [],
    errors: results.errors || [],
  };
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
  // --- RS 테이블 캡처 상태 변수 ---
  // 이미지 복사(캡처) 중일 때 true, 아닐 때 false
  // 캡처 중에는 종목명/종목코드 검색 입력 박스를 숨긴다.
  const [isRsTableCapturing, setIsRsTableCapturing] = useState(false);
  // 종목명/종목코드 검색 상태 및 선택 상태 추가 (밸류에이션 페이지와 동일하게)
  const [searchFilter, setSearchFilter] = useState('');
  const [selectedStock, setSelectedStock] = useState<{ code: string; name: string } | null>(null);

  // 종목명/종목코드 검색 핸들러 (밸류에이션 페이지와 동일하게)
  const handleSearchKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      // 검색어가 있고, 필터링된 결과가 1개인 경우
      const filtered = csvData.rows.filter(row => {
        const stockName = row['종목명'] || '';
        const stockCode = row['종목코드'] || '';
        return (
          stockName.includes(searchFilter) ||
          stockCode.includes(searchFilter)
        );
      });
      if (searchFilter.trim() && filtered.length === 1) {
        setSelectedStock({ code: filtered[0]['종목코드'], name: filtered[0]['종목명'] });
      }
    }
  };
  // 선택 해제 핸들러
  const handleClearSelectedStock = () => {
    setSelectedStock(null);
    setSearchFilter('');
  };

  // 상태 관리
  const [csvData, setCsvData] = useState<CSVData>({ headers: [], rows: [], errors: [] });
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [currentPage, setCurrentPage] = useState<number>(1);
  const [sortKey, setSortKey] = useState<string>('RS');
  const [sortDirection, setSortDirection] = useState<SortDirection>('desc');
  const [chartTab, setChartTab] = useState<'rs' | 'mtt'>('rs');
  const rsTableRef = useRef<HTMLDivElement>(null);
  const rsHeaderRef = useRef<HTMLDivElement>(null);
  const highTableRef = useRef<HTMLDivElement>(null);
  const highHeaderRef = useRef<HTMLDivElement>(null);
  
  // 52주 신고가 데이터 관련 상태
  const [highData, setHighData] = useState<CSVData>({ headers: [], rows: [], errors: [] });
  const [highDataLoading, setHighDataLoading] = useState<boolean>(true);
  const [highDataError, setHighDataError] = useState<string | null>(null);
  // 52주 신고가 테이블의 기본 정렬 기준을 '등락률'로 설정 (기존: 'RS')
  const [highSortKey, setHighSortKey] = useState<string>('등락률');
  const [highSortDirection, setHighSortDirection] = useState<SortDirection>('desc');
  
  // 업데이트 날짜 상태 추가
  const [updateDate, setUpdateDate] = useState<string | null>(null); 
  
  // 차트 데이터 관련 상태 - 21개의 차트를 위한 상태 배열로 변경
  const [chartDataArray, setChartDataArray] = useState<CandleData[][]>(Array.from({length: 21}, () => []));
  const [chartLoadingArray, setChartLoadingArray] = useState<boolean[]>(Array.from({length: 21}, () => false));
  const [chartErrorArray, setChartErrorArray] = useState<string[]>(Array.from({length: 21}, () => '')); 
  const [chartMarketTypes, setChartMarketTypes] = useState<string[]>(Array.from({length: 21}, () => '')); // 빈 문자열로 초기화
  // 종목명을 저장할 상태 추가
  const [chartStockNames, setChartStockNames] = useState<string[]>(Array.from({length: 21}, () => ''));
  // RS 값을 저장할 상태 추가
  const [chartRsValues, setChartRsValues] = useState<string[]>(Array.from({length: 21}, () => ''));
  const [kospiIndexData, setKospiIndexData] = useState<CandleData[]>([]);
  const [kosdaqIndexData, setKosdaqIndexData] = useState<CandleData[]>([]);
  
  useEffect(() => {
    // 페이지 로드 시 데이터 로드
    const loadData = async () => {
      setLoading(true);
      setError(null);
      
      try {
        // 로컬 캐시 파일 경로
        const cacheFilePath = '/requestfile/stock-data/stock_1uyjvdmzfxarsxs0jy16fegfrqy9fs8yd.csv';
        
        // 로컬 캐시 파일 로드
        const response = await fetch(cacheFilePath, { cache: 'no-store' });
        
        if (!response.ok) {
          throw new Error(`캐시 파일 로드 실패: ${response.status}`);
        }
        
        const csvText = await response.text();
        
        // CSV 파싱 및 데이터 처리
        const parsedData = parseCSV(csvText);
        
        setCsvData(parsedData);
        
        // RS 순위 데이터 로드 후 차트 데이터 로드
        await loadAllChartData(parsedData);
      } catch (err) {
        console.error('RS 순위 데이터 로드 오류:', err);
        setError(`데이터를 로드하는데 실패했습니다: ${err instanceof Error ? err.message : '알 수 없는 오류'}`);
      } finally {
        setLoading(false);
      }
    };
    
    const loadHighData = async () => {
      setHighDataLoading(true);
      setHighDataError(null);
      
      try {
        // 로컬 캐시 파일에서 직접 로드
        try {
          // 로컬 캐시 파일 경로
          const cacheFilePath = '/requestfile/stock-data/stock_1mbee4o9_nonpfiaexi4vin8qcn8bttxz.csv';
          // const rsDataFilePath = '/requestfile/stock-data/stock_1uyjvdmzfxarsxs0jy16fegfrqy9fs8yd.csv'; // RS 데이터 파일 로드 로직 제거
          
          // 로컬 캐시 파일 로드
          const response = await fetch(cacheFilePath, { cache: 'no-store' });
          
          if (!response.ok) {
            throw new Error(`캐시 파일 로드 실패: ${response.status}`);
          }
          
          const csvText = await response.text();
          
          // RS 데이터 파일 로드 로직 제거
          // const rsResponse = await fetch(rsDataFilePath, { cache: 'no-store' });
          // 
          // if (!rsResponse.ok) {
          //   console.error(`RS 데이터 파일 로드 실패: ${response.status}`);
          //   throw new Error(`RS 데이터 파일 로드 실패: ${response.status}`);
          // }
          // 
          // const rsCsvText = await rsResponse.text();
          
          // CSV 파싱 및 데이터 처리
          const parsedData = parseCSV(csvText);
          // const rsParsedData = parseCSV(rsCsvText); // RS 데이터 파싱 로직 제거
          
          // RS 데이터를 종목명으로 매핑하여 빠르게 검색할 수 있도록 Map 생성 로직 제거
          // const rsDataMap = new Map();
          // rsParsedData.rows.forEach(row => {
          //   if (row['종목명']) {
          //     // 시가총액을 억 단위로 변환 로직 제거
          //     // let marketCapBillion = 0;
          //     // if (row['시가총액']) {
          //     //   const marketCap = String(row['시가총액']).replace(/,/g, '');
          //     //   marketCapBillion = Math.floor(Number(marketCap) / 100000000); // 억 단위로 변환
          //     // }
          //     
          //     rsDataMap.set(row['종목명'], {
          //       RS: row['RS'] || '',
          //       시가총액: row['시가총액'], // 시가총액 직접 사용
          //       테마명: row['테마명'] || ''
          //     });
          //   }
          // });
          
          // 데이터 변환 로직 제거 - stock_1mbee4o9_nonpfiaexi4vin8qcn8bttxz.csv 파일의 데이터를 그대로 사용
          // const transformedData = {
          //   headers: parsedData.headers,
          //   rows: parsedData.rows.map(row => {
          //     // 종목명으로 RS 데이터 매핑 로직 제거
          //     // const stockName = row['종목명'];
          //     // 
          //     // const rsData = rsDataMap.get(stockName) || { RS: '', 시가총액: '', 테마명: '' }; // 테마명 추가
          //     // 
          //     return {
          //       // stockName: stockName, // 필요시 종목명 컬럼명 변경 가능
          //       // rs: rsData.RS || row['거래대금'], // RS 데이터가 있으면 사용, 없으면 거래대금 사용
          //       // 시가총액: rsData.시가총액,
          //       ...row
          //     };
          //   }),
          //   errors: parsedData.errors
          // };
          
          setHighData(parsedData); // parsedData를 직접 사용
        } catch (error) {
          console.error('서버 캐시 파일 로드 실패:', error);
          throw new Error(`서버 캐시 파일 로드 실패: ${error instanceof Error ? error.message : '알 수 없는 오류'}`);
        }
      } catch (err) {
        console.error('52주 신고가 데이터 로드 오류:', err);
        setHighDataError(`데이터를 로드하는데 실패했습니다: ${err instanceof Error ? err.message : '알 수 없는 오류'}`);
      } finally {
        setHighDataLoading(false);
      }
    };
    
    const loadStockPriceData = async () => {
      try {
        // 종목 가격 데이터 파일 경로
        const stockPriceDataPath = '/requestfile/stock-data/stock_1idvb5kio0d6dchvoywe7ovwr-ez1cbpb.csv';
        
        // 파일 로드
        const response = await fetch(stockPriceDataPath, { cache: 'no-store' });
        
        if (!response.ok) {
          console.error(`종목 가격 데이터 파일 로드 실패: ${response.status}`);
          return;
        }
        
        // CSV 텍스트 가져오기
        const csvText = await response.text();
        
        // CSV 파싱
        const parsedData = parseCSV(csvText);
        
        if (!parsedData || !parsedData.rows || parsedData.rows.length === 0) {
          console.error('종목 가격 데이터가 없습니다.');
          return;
        }
        
        // 종목코드를 키로 하는 시가/종가 정보 객체 생성
        const priceDataMap: Record<string, { open: number, close: number }> = {};
        
        // 각 행을 순회하며 종목코드를 키로 하는 시가/종가 정보 추출
        parsedData.rows.forEach((row: any) => {
          if (row['종목코드'] && row['시가'] && row['종가']) {
            const stockCode = String(row['종목코드']).trim();
            const openPrice = parseFloat(String(row['시가']).replace(/,/g, ''));
            const closePrice = parseFloat(String(row['종가']).replace(/,/g, ''));
            
            if (!isNaN(openPrice) && !isNaN(closePrice)) {
              priceDataMap[stockCode] = {
                open: openPrice,
                close: closePrice
              };
            }
          }
        });
        
        // 상태 업데이트
        // setStockPriceData(priceDataMap);
      } catch (error) {
        console.error('종목 가격 데이터 로드 오류:', error);
      }
    };
    
    const loadUpdateDate = async () => {
      try {
        // 주식 데이터 CSV 파일에서 마지막 수정 날짜 가져오기
        const cacheFilePath = '/requestfile/stock-data/stock_1uyjvdmzfxarsxs0jy16fegfrqy9fs8yd.csv';
        
        // 헤더만 가져와서 Last-Modified 확인
        const response = await fetch(cacheFilePath, { cache: 'no-store' });
        
        if (!response.ok) {
          throw new Error(`주식 데이터 파일 로드 실패: ${response.status}`);
        }
        
        // 응답 헤더에서 Last-Modified 값 추출
        const lastModified = response.headers.get('Last-Modified');
        
        if (lastModified) {
          // Last-Modified 헤더에서 날짜와 시간 추출하여 포맷팅
          const modifiedDate = new Date(lastModified);
          const month = modifiedDate.getMonth() + 1; // getMonth()는 0부터 시작하므로 1 더함
          const day = modifiedDate.getDate();
          const hours = modifiedDate.getHours();
          const minutes = modifiedDate.getMinutes();
          
          // M/DD HH:MM 형식으로 포맷팅
          const formattedDate = `${month}/${day.toString().padStart(2, '0')} ${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}`;
          setUpdateDate(formattedDate);
        } else {
          // Last-Modified 헤더가 없는 경우 현재 날짜/시간 사용
          const now = new Date();
          const month = now.getMonth() + 1;
          const day = now.getDate();
          const hours = now.getHours();
          const minutes = now.getMinutes();
          
          const formattedDate = `${month}/${day.toString().padStart(2, '0')} ${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}`;
          setUpdateDate(formattedDate);
          console.warn('주식 데이터 파일의 Last-Modified 헤더를 찾을 수 없어 현재 시간을 사용합니다.');
        }
      } catch (err) {
        console.error('업데이트 날짜 로드 실패:', err);
        // 오류 발생 시 현재 날짜/시간을 사용
        const now = new Date();
        const month = now.getMonth() + 1;
        const day = now.getDate();
        const hours = now.getHours();
        const minutes = now.getMinutes();
        
        const formattedDate = `${month}/${day.toString().padStart(2, '0')} ${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}`;
        setUpdateDate(formattedDate);
      }
    };
    
    // Helper function to parse various date string formats
    const parseDateString = (dateInput: unknown): Date | null => {
      if (typeof dateInput !== 'string') {
        // console.warn(`parseDateString received non-string input: ${String(dateInput)} (type: ${typeof dateInput})`);
        return null;
      }
      const dateString = dateInput.trim();
      if (!dateString) {
        // console.warn('parseDateString received empty string after trim.');
        return null;
      }

      const formats = [
        'yyyyMMdd',   // Numeric string like 20230515
        'yyyy-MM-dd', // ISO
        'yyyy.MM.dd', // Dotted
        'yyyy/MM/dd', // Slashed
        'MM/dd/yyyy', // US
        'M/d/yyyy',   // US short (e.g., 5/1/2024)
        'dd/MM/yyyy', // EU
        'd/M/yyyy',   // EU short
      ];

      for (const fmt of formats) {
        const parsed = parse(dateString, fmt, new Date());
        if (isValid(parsed)) {
          return parsed;
        }
      }

      if (/^\d{8}$/.test(dateString)) {
        const year = parseInt(dateString.substring(0, 4), 10);
        const month = parseInt(dateString.substring(4, 6), 10) - 1; // JS months are 0-indexed
        const day = parseInt(dateString.substring(6, 8), 10);
        if (year > 1900 && year < 2100 && month >= 0 && month <= 11 && day >= 1 && day <= 31) {
            const manualDate = new Date(Date.UTC(year, month, day));
            if (isValid(manualDate) && 
                manualDate.getUTCFullYear() === year &&
                manualDate.getUTCMonth() === month &&
                manualDate.getUTCDate() === day) {
              return manualDate;
            }
        }
      }
      
      if (dateString.includes('-') || dateString.includes('/') || dateString.includes(':') || dateString.includes('.')) {
        const directParsed = new Date(dateString);
        if (isValid(directParsed) && dateString.length > 4) { // Avoid single numbers like "2024"
             return directParsed;
        }
      }
      
      console.warn(`[parseDateString] Failed to parse date: '${dateString}' (Original input: '${String(dateInput)}')`);
      return null;
    };

    const loadMarketIndexData = async () => {
      try {
        // KOSPI 주간 데이터 로드
        const kospiResponse = await fetch('/requestfile/market-index/kospiwk.csv', { cache: 'no-store' });
        if (!kospiResponse.ok) {
          throw new Error(`KOSPI 데이터 로드 실패: ${kospiResponse.status}`);
        }
        const kospiCsvText = await kospiResponse.text();
        const kospiParsedData = parseCSV(kospiCsvText);
        // 데이터 형식 변환 (CandleData)
        const kospiFormattedData = kospiParsedData.rows.reduce((acc, row) => {
          const rawDateValue = row['날짜'] || row['일자'] || row['Date']; // 다양한 컬럼명 처리
          const parsedDate = parseDateString(rawDateValue);

          if (parsedDate) { // parseDateString returns valid Date or null
            acc.push({
              time: format(parsedDate, 'yyyy-MM-dd'), // 날짜 형식 통일
              open: parseFloat(row['시가']),
              high: parseFloat(row['고가']),
              low: parseFloat(row['저가']),
              close: parseFloat(row['종가']),
              volume: parseFloat(row['거래량'])
            });
          } else {
            if (rawDateValue !== undefined && rawDateValue !== null && String(rawDateValue).trim() !== '') {
              // parseDateString will log the specific parsing failure
              // console.warn(`KOSPI: Row skipped due to unparseable date. Input: '${String(rawDateValue)}'`);
            }
          }
          return acc;
        }, [] as CandleData[]).sort((a: CandleData, b: CandleData) => new Date(a.time).getTime() - new Date(b.time).getTime()); // 타입 명시
        setKospiIndexData(kospiFormattedData);

        // KOSDAQ 주간 데이터 로드
        const kosdaqResponse = await fetch('/requestfile/market-index/kosdaqwk.csv', { cache: 'no-store' });
        if (!kosdaqResponse.ok) {
          throw new Error(`KOSDAQ 데이터 로드 실패: ${kosdaqResponse.status}`);
        }
        const kosdaqCsvText = await kosdaqResponse.text();
        const kosdaqParsedData = parseCSV(kosdaqCsvText);
        // 데이터 형식 변환 (CandleData)
        const kosdaqFormattedData = kosdaqParsedData.rows.reduce((acc, row) => {
          const rawDateValue = row['날짜'] || row['일자'] || row['Date']; // 다양한 컬럼명 처리
          const parsedDate = parseDateString(rawDateValue);
          
          if (parsedDate) { // parseDateString returns valid Date or null
            acc.push({
              time: format(parsedDate, 'yyyy-MM-dd'),
              open: parseFloat(row['시가']),
              high: parseFloat(row['고가']),
              low: parseFloat(row['저가']),
              close: parseFloat(row['종가']),
              volume: parseFloat(row['거래량'])
            });
          } else {
            if (rawDateValue !== undefined && rawDateValue !== null && String(rawDateValue).trim() !== '') {
              // parseDateString will log the specific parsing failure
              // console.warn(`KOSDAQ: Row skipped due to unparseable date. Input: '${String(rawDateValue)}'`);
            }
          }
          return acc;
        }, [] as CandleData[]).sort((a: CandleData, b: CandleData) => new Date(a.time).getTime() - new Date(b.time).getTime()); // 타입 명시
        setKosdaqIndexData(kosdaqFormattedData);

      } catch (err) {
        console.error('시장 지수 데이터 로드 오류:', err);
        // 필요에 따라 사용자에게 오류 메시지를 표시할 수 있습니다.
      }
    };

    loadData();
    loadHighData();
    loadUpdateDate();
    loadMarketIndexData(); // 시장 지수 데이터 로드 함수 호출
    // loadStockPriceData();
  }, []);

  // 차트 데이터 로드 함수
  const loadAllChartData = async (rsData?: CSVData) => {
    try {
      // RS 랭크 데이터가 없으면 리턴
      if (!rsData || !rsData.rows || rsData.rows.length === 0) {
        return;
      }
      
      // 상위 21개 종목 추출
      const topStocks = rsData.rows.slice(0, 21);
      
      // 차트 데이터 배열 초기화
      const newChartDataArray: CandleData[][] = Array.from({length: 21}, () => []);
      let newStockNames: string[] = Array.from({length: 21}, () => ''); // const에서 let으로 변경
      let newMarketTypes: string[] = Array.from({length: 21}, () => ''); // const에서 let으로 변경
      const newChartLoadingArray: boolean[] = Array.from({length: 21}, () => true);
      const newChartErrorArray: string[] = Array.from({length: 21}, () => '');
      const newRsValues: string[] = Array.from({length: 21}, () => '');
      
      // RS 값 설정 (종목 데이터에서 가져옴) -> 각 차트 파일에서 가져오도록 변경하므로 이 부분은 주석 처리 또는 삭제
      // topStocks.forEach((stock, index) => {
      //   if (index < 21) {
      //     newRsValues[index] = stock.RS ? String(stock.RS) : ''; 
      //     newStockNames[index] = stock.종목명 || '';
      //   }
      // });
      newStockNames = topStocks.map(stock => stock.종목명 || ''); // 종목명은 계속 rsData에서 가져옴
      newMarketTypes = topStocks.map(stock => stock.시장구분 || ''); // 시장구분도 rsData에서 가져옴

      // 차트 데이터 파일 경로 배열 (순서대로 매핑)
      const chartFilePaths = [
        '/requestfile/chart-data/1.csv',
        '/requestfile/chart-data/2.csv',
        '/requestfile/chart-data/3.csv',
        '/requestfile/chart-data/4.csv',
        '/requestfile/chart-data/5.csv',
        '/requestfile/chart-data/6.csv',
        '/requestfile/chart-data/7.csv',
        '/requestfile/chart-data/8.csv',
        '/requestfile/chart-data/9.csv',
        '/requestfile/chart-data/10.csv',
        '/requestfile/chart-data/11.csv',
        '/requestfile/chart-data/12.csv',
        '/requestfile/chart-data/13.csv',
        '/requestfile/chart-data/14.csv',
        '/requestfile/chart-data/15.csv',
        '/requestfile/chart-data/16.csv',
        '/requestfile/chart-data/17.csv',
        '/requestfile/chart-data/18.csv',
        '/requestfile/chart-data/19.csv',
        '/requestfile/chart-data/20.csv',
        '/requestfile/chart-data/21.csv' // 21번째 파일 추가
      ];
      
      // 시장 지수 데이터 파일 경로
      const kospiIndexPath = '/requestfile/market-index/kospiwk.csv'; // KOSPI 주간 데이터 파일로 변경
      const kosdaqIndexPath = '/requestfile/market-index/kosdaqwk.csv'; // KOSDAQ 주간 데이터 파일로 변경
      
      // 시장 지수 데이터 로드
      let kospiIndexData: CandleData[] = [];
      let kosdaqIndexData: CandleData[] = [];
      
      try {
        // KOSPI 지수 데이터 로드
        let kospiResponse = await fetch(kospiIndexPath, { cache: 'no-store' });
        
        // 파일이 없으면 오류 메시지 표시
        if (!kospiResponse.ok) {
          throw new Error(`코스피 지수 데이터 파일을 찾을 수 없습니다.`);
        }
        
        if (kospiResponse.ok) {
          const kospiCsvText = await kospiResponse.text();
          const kospiParsedData = Papa.parse(kospiCsvText, {
            header: true,
            skipEmptyLines: true,
            dynamicTyping: true,
          });
          
          kospiIndexData = kospiParsedData.data
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
                open: parseFloat(row['시가']),
                high: parseFloat(row['고가']),
                low: parseFloat(row['저가']),
                close: parseFloat(row['종가']),
                volume: parseFloat(row['거래량'])
              };
            });
        }
        
        // KOSDAQ 지수 데이터 로드
        let kosdaqResponse = await fetch(kosdaqIndexPath, { cache: 'no-store' });
        
        // 파일이 없으면 오류 메시지 표시
        if (!kosdaqResponse.ok) {
          throw new Error(`코스닥 지수 데이터 파일을 찾을 수 없습니다.`);
        }
        
        if (kosdaqResponse.ok) {
          const kosdaqCsvText = await kosdaqResponse.text();
          const kosdaqParsedData = Papa.parse(kosdaqCsvText, {
            header: true,
            skipEmptyLines: true,
            dynamicTyping: true,
          });
          
          kosdaqIndexData = kosdaqParsedData.data
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
                open: parseFloat(row['시가']),
                high: parseFloat(row['고가']),
                low: parseFloat(row['저가']),
                close: parseFloat(row['종가']),
                volume: parseFloat(row['거래량'])
              };
            });
        }
      } catch (error) {
        console.error('시장 지수 데이터 로드 오류:', error);
      }
      
      // 실제 데이터 로드 (최대 21개)
      const loadLimit = Math.min(21, topStocks.length);
      
      // 모든 차트 데이터를 로드하기 위한 Promise 배열 생성
      const loadPromises = [];
      
      // 각 차트 데이터 로드를 위한 Promise 생성
      for (let i = 0; i < loadLimit; i++) {
        // 순서에 맞는 차트 데이터 파일 경로 사용
        const cacheFilePath = chartFilePaths[i];
        
        // 차트 데이터 로드 Promise 생성
        const loadPromise = (async (index) => {
          try {
            const response = await fetch(chartFilePaths[index], { cache: 'no-store' });
            
            if (!response.ok) {
              newChartErrorArray[index] = `차트 데이터 파일을 찾을 수 없습니다.`;
              newChartLoadingArray[index] = false;
              return;
            }
            
            const csvText = await response.text();
            
            if (csvText.length === 0) {
              throw new Error('CSV 응답이 비어 있습니다.');
            }
            
            // CSV 데이터 파싱
            const parsedData = Papa.parse(csvText, {
              header: true,
              skipEmptyLines: true,
              dynamicTyping: true,
            });
            
            // RS 값 추출: parsedData의 마지막 행에서 RS 값을 가져옴
            if (parsedData.data && parsedData.data.length > 0) {
              const lastRow: any = parsedData.data[parsedData.data.length - 1];
              if (lastRow && typeof lastRow.RS !== 'undefined') {
                newRsValues[index] = String(lastRow.RS);
              } else {
                newRsValues[index] = ''; // RS 값이 없는 경우 빈 문자열
              }
            } else {
              newRsValues[index] = ''; // 데이터가 없는 경우 빈 문자열
            }
            
            // 차트 데이터 형식으로 변환
            const chartData: CandleData[] = parsedData.data
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
                  open: parseFloat(row['시가'] || 0),
                  high: parseFloat(row['고가'] || 0),
                  low: parseFloat(row['저가'] || 0),
                  close: parseFloat(row['종가'] || 0),
                  volume: parseFloat(row['거래량'] || 0),
                };
              });
            
            // 시장 구분 및 종목명 확인 - 타입 안전하게 처리
            if (parsedData.data.length > 0 && parsedData.data[0]) {
              const firstRow = parsedData.data[0] as Record<string, any>;
              
              // CSV 파일에서 종목명 가져오기
              if ('종목명' in firstRow) {
                const stockName = String(firstRow['종목명']);
                // 종목명 정보 업데이트
                newStockNames[index] = stockName;
              }
              
              // CSV 파일에서 시장구분 가져오기
              if ('시장구분' in firstRow) {
                // 시장 구분 정보를 대문자로 정규화하여 저장
                const marketType = String(firstRow['시장구분']).toUpperCase();
                // 시장 구분 정보 업데이트
                newMarketTypes[index] = marketType;
              }
            }
            
            // 데이터 저장
            newChartDataArray[index] = chartData;
            return { index, success: true, marketType: newMarketTypes[index] };
          } catch (error) {
            console.error(`${index+1}번째 차트 데이터 파일 로드 실패: ${error instanceof Error ? error.message : '알 수 없는 오류'}`);
            newChartErrorArray[index] = `데이터 로드 실패: ${error instanceof Error ? error.message : '알 수 없는 오류'}`;
            newChartDataArray[index] = [];
            return { index, success: false, marketType: newMarketTypes[index] };
          }
        })(i);
        
        loadPromises.push(loadPromise);
      }
      
      // 모든 차트 데이터 로드 완료 대기
      await Promise.all(loadPromises);
      
      // 로딩 상태 업데이트
      for (let i = 0; i < loadLimit; i++) {
        newChartLoadingArray[i] = false;
      }
      
      // 상태 업데이트 (한 번에 모든 차트 데이터 업데이트)
      setChartDataArray(newChartDataArray);
      setChartStockNames(newStockNames);
      setChartMarketTypes(newMarketTypes);
      setChartRsValues(newRsValues);
      setChartLoadingArray(newChartLoadingArray);
      setChartErrorArray(newChartErrorArray);
      
      // 시장 지수 데이터 상태 업데이트
      setKospiIndexData(kospiIndexData);
      setKosdaqIndexData(kosdaqIndexData);
      
    } catch (error) {
      console.error('차트 데이터 로드 오류:', error);
      setChartLoadingArray(Array.from({length: 21}, () => false)); // 크기 21로 변경
      setChartErrorArray(Array.from({length: 21}, () => `데이터 로드 실패: ${error instanceof Error ? error.message : '알 수 없는 오류'}`)); // 크기 21로 변경
    }
  };

  // CSV 파싱 최적화 함수 - 한 번의 파싱으로 모든 필요한 정보 추출
  const parseCSVOptimized = (csvText: string, index: number): { chartData: CandleData[], stockName: string, marketType: string } => {
    try {
      // CSV 파싱
      const parsedData = Papa.parse(csvText, {
        header: true,
        skipEmptyLines: true,
        dynamicTyping: true,
      });
      
      // 첫 번째 행에서 종목명과 시장 정보 추출
      const firstRow = parsedData.data[0] as Record<string, any>;
      
      // CSV 파일에서 종목명 가져오기
      const stockName = firstRow['종목명'] || `종목 ${index + 1}`;
      
      // CSV 파일에서 시장구분 가져오기
      const marketType = firstRow['시장'] || 'KOSPI';
      
      // 차트 데이터 형식으로 변환
      const chartData: CandleData[] = parsedData.data
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
            open: parseFloat(row['시가'] || 0),
            high: parseFloat(row['고가'] || 0),
            low: parseFloat(row['저가'] || 0),
            close: parseFloat(row['종가'] || 0),
            volume: parseFloat(row['거래량'] || 0),
          };
        });
      
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

  // 52주 신고가 테이블 정렬 함수
  const handleHighSort = useCallback((key: string) => {
    setHighSortKey(key);
    setHighSortDirection(prev => 
      key === highSortKey ? (prev === 'asc' ? 'desc' : 'asc') : 'desc'
    );
  }, [highSortKey]);

  // 셀의 정렬 방향을 결정하는 함수
  const getCellAlignment = (header: string) => {
    // RS 관련 수치들은 가운데 정렬
    if (header.startsWith('RS') || ['MTT'].includes(header)) {
      return 'text-center';
    }
    
    // 종목코드는 가운데 정렬
    if (header === '종목코드') {
      return 'text-center';
    }
    
    // 시가총액 컬럼은 우측 정렬
    if (header === '시가총액') {
      return 'text-right';
    }
    
    // 다른 숫자 컬럼은 우측 정렬
    if (['RS_Rank', 'RS_Rank_Prev', 'RS_Rank_Change'].includes(header)) {
      return 'text-right';
    }
    
    // 기본값은 좌측 정렬
    return 'text-left';
  };

  // 시가총액을 억 단위로 포맷팅하는 함수 제거
  // const formatMarketCap = (value: any): string => {
  //   if (!value) return '0';
  //   
  //   // 숫자가 아니면 그대로 반환
  //   if (isNaN(Number(value))) return String(value);
  //   
  //   // 숫자로 변환
  //   const valueStr = typeof value === 'number' ? String(value) : value;
  //   let marketCapValue = Number(valueStr.replace(/[^0-9.]/g, ''));
  //   
  //   // 10억 이상인 경우 억 단위로 변환 (1,000,000,000 이상)
  //   if (marketCapValue >= 100000000) {
  //     marketCapValue = marketCapValue / 100000000; // 억 단위로 변환
  //   }
  //   
  //   // 소수점 제거하고 천 단위 구분 쉼표(,) 추가
  //   return Math.floor(marketCapValue).toLocaleString('ko-KR');
  // };

  // 등락률 계산 함수 제거
  // const calculatePriceChange = (openPrice: number, closePrice: number): number => {
  //   if (!openPrice || openPrice === 0) return 0;
  //   return ((closePrice - openPrice) / openPrice) * 100;
  // };

  // 등락률 포맷팅 함수 제거
  // const formatPriceChange = (change: number): string => {
  //   if (change === 0) return '0.00%';
  //   return change > 0 ? `+${change.toFixed(2)}%` : `${change.toFixed(2)}%`;
  // };

  // 등락률에 따른 색상 결정 함수 제거
  // const getPriceChangeColor = (change: number): string => {
  //   if (change >= 5) return 'text-red-500'; // 5% 이상 상승은 빨간색
  //   if (change < 0) return 'text-blue-400'; // 하락은 파란색
  //   return 'text-gray-900'; // 그 외는 검정색
  // };

  // [검색 및 필터] selectedStock, searchFilter, 시가총액 2천억 이상 필터 제거
  const filteredData = useMemo(() => {
    if (!csvData || !csvData.rows) return [];
    // 1. 선택된 종목이 있으면 해당 종목만 반환
    if (selectedStock) {
      return csvData.rows.filter(row =>
        row['종목코드'] === selectedStock.code &&
        row['종목명'] === selectedStock.name
      );
    }
    // 2. 검색어가 있으면 종목명/종목코드 부분 일치(대소문자 무시)
    let result = csvData.rows;
    if (searchFilter.trim()) {
      const keyword = searchFilter.trim().toLowerCase();
      result = result.filter(row =>
        (row['종목명'] && String(row['종목명']).toLowerCase().includes(keyword)) ||
        (row['종목코드'] && String(row['종목코드']).toLowerCase().includes(keyword))
      );
    }
    // 3. 시가총액 2천억 미만인 종목 필터링
    // result = result.filter(row => Number(row['시가총액'] || 0) >= 200000000000);
    return result;
  }, [csvData, selectedStock, searchFilter]);

  // [페이지네이션+정렬] 실제 테이블에 표시할 데이터 (filteredData 기준)
  const currentPageData = useMemo(() => {
    const sortedData = sortDirection 
      ? sortData(filteredData, sortKey, sortDirection)
      : filteredData;
    const startIndex = (currentPage - 1) * 20;
    return sortedData.slice(startIndex, startIndex + 20);
  }, [filteredData, currentPage, sortKey, sortDirection]);

  // [페이지네이션] 총 페이지 수 계산 (filteredData 기준)
  const totalPages = useMemo(() => {
    return Math.ceil(filteredData.length / 20);
  }, [filteredData]);

  // 52주 신고가 데이터 정렬
  const sortedHighData = useMemo(() => {
    if (!highSortKey || highSortDirection === null) {
      return [...highData.rows];
    }
    
    return [...highData.rows].sort((a, b) => {
      let aValue = a[highSortKey];
      let bValue = b[highSortKey];
      
      // 등락률 컬럼의 경우 숫자로 변환하여 비교
      if (highSortKey === '등락률') {
        aValue = parseFloat(aValue.replace('%', '')) || 0;
        bValue = parseFloat(bValue.replace('%', '')) || 0;
      }
      // 시가총액 컬럼의 경우 숫자로 변환하여 비교
      else if (highSortKey === '시가총액') {
        aValue = parseFloat(aValue.replace(/,/g, '')) || 0;
        bValue = parseFloat(bValue.replace(/,/g, '')) || 0;
      }
      // 거래대금 컬럼의 경우 숫자로 변환하여 비교
      else if (highSortKey === '거래대금') {
        aValue = parseFloat(aValue.replace(/,/g, '')) || 0;
        bValue = parseFloat(bValue.replace(/,/g, '')) || 0;
      }
      
      if (aValue < bValue) return highSortDirection === 'asc' ? -1 : 1;
      if (aValue > bValue) return highSortDirection === 'asc' ? 1 : -1;
      return 0;
    });
  }, [highData.rows, highSortKey, highSortDirection]);

  // 표시할 테이블 컬럼 정의
  const DESIRED_COLUMNS = ['종목코드', '종목명', '업종', 'RS', 'RS_1M', 'RS_3M', 'RS_6M', 'MTT', '시가총액'];

  // 페이지 변경 핸들러
  const handlePageChange = useCallback((page: number) => {
    setCurrentPage(page);
  }, []);

  // 헤더 이름을 변환하는 함수
  const formatHeaderName = (header: string) => {
    // 시가총액 헤더를 시가총액(억)으로 변경하지 않음 (원본 헤더명 사용)
    // if (header === '시가총액') {
    //   return '시가총액(억)';
    // }
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
    
    // 시가총액 컬럼은 천 단위 구분 기호(콤마) 추가
    if (header === '시가총액') {
      if (!value || isNaN(Number(value.replace(/,/g, '')))) return value || ''; // 숫자 아니거나 빈 값이면 그대로 반환
      return Number(value.replace(/,/g, '')).toLocaleString('ko-KR');
    }
    
    // 거래대금 컬럼인 경우 억 단위로 포맷팅
    if (header === '거래대금') {
      // 숫자가 아니면 그대로 반환
      if (isNaN(Number(value))) return value;
      
      // 숫자로 변환 후 억 단위로 나누고 소수점 없이 표시
      const valueStr = typeof value === 'number' ? String(value) : value;
      let tradeAmountInBillions = Number(valueStr.replace(/[^0-9.]/g, ''));
      
      // 천 단위 구분 쉼표(,) 추가
      return Math.floor(tradeAmountInBillions).toLocaleString('ko-KR');
    }
    
    // 종목코드가 아닌 숫자인 경우에만 천 단위 구분 쉼표(,) 추가
    if (!isNaN(Number(value)) && value !== '') {
      return Number(value).toLocaleString('ko-KR');
    }
    
    // 다른 컬럼은 그대로 표시
    return value || '';
  };

  // 52주 신고/신저가 및 RS 순위 데이터 매칭하여 보여줄 데이터 생성
  const combinedHighData = useMemo(() => {
    if (!highData || highData.rows.length === 0) {
      return [];
    }

    return highData.rows.map((highRow) => {
      // 등락률 계산 로직 제거
      // const stockName = highRow['종목명'];
      // const priceInfo = stockPriceData[stockName]; // 등락률 계산을 위해 유지

      // 등락률 계산 로직 제거
      // const priceChange = priceInfo ? calculatePriceChange(priceInfo.open, priceInfo.close) : 0;

      return {
        ...highRow,
        // '등락률' 키에 CSV의 실제 '등락률' 컬럼 값을 할당
        '등락률': highRow['등락률'], 
        // 시가총액은 CSV에서 직접 가져옵니다. 렌더링 시 포맷팅합니다.
        '시가총액': highRow['시가총액'], 
        // '거래대금' 키에 CSV의 '거래대금' 컬럼 값을 할당
        '거래대금': highRow['거래대금'],
      };
    })
    // 시가총액이 2천억 미만인 종목 필터링
    .filter(item => {
      const marketCapString = item['시가총액'];
      // 시가총액 값을 숫자로 변환 (실패 시 0)
      const marketCapValue = Number(marketCapString) || 0;
      // 2천억 이상인 경우만 true 반환
      return marketCapValue >= 200000000000;
    })
    // RS 값 기준으로 내림차순 정렬 (높은 값이 먼저 오도록)
    .sort((a, b) => {
      // RS 값을 숫자로 변환 (변환 실패 시 0으로 처리)
      const rsA = Number(a['RS']) || 0;
      const rsB = Number(b['RS']) || 0;
      // 내림차순 정렬 (큰 값이 먼저 오도록)
      return rsB - rsA;
    });
  // 의존성 배열에서 stockPriceData, calculatePriceChange 제거
  }, [highData]); 

  // 차트 컴포넌트 렌더링
  const renderChartComponent = (index: number) => {
    if (chartLoadingArray[index]) {
      return (
        <div>
          <div className="bg-gray-100 px-3 py-1 border border-gray-200 flex justify-between items-center" style={{ borderRadius: '0.375rem 0.375rem 0 0' }}>
            <div className="flex items-center">
              <span className="font-medium text-xs text-xs" style={{ fontSize: 'clamp(0.65rem, 0.75vw, 0.75rem)' }}>{chartStockNames[index] || '로딩 중...'}</span>
              <span className={`ml-2 text-xs px-1.5 py-0.5 rounded bg-gray-300 text-gray-700`}>
                {chartMarketTypes[index] || '...'}
              </span>
            </div>
            {chartRsValues[index] && (
              <div className="flex items-center">
                <span className="text-xs text-gray-500 mr-1" style={{ fontSize: 'clamp(0.65rem, 0.75vw, 0.75rem)' }}>RS</span>
                <span className="font-medium text-xs text-blue-600" style={{ fontSize: 'clamp(0.65rem, 0.75vw, 0.75rem)' }}>{chartRsValues[index]}</span>
              </div>
            )}
          </div>
          <div className="h-72 flex items-center justify-center border border-gray-200 border-t-0" style={{ borderRadius: '0 0 0.375rem 0.375rem' }}>
            <div className="flex flex-col items-center">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500 mb-2"></div>
              <span className="text-gray-500" style={{ fontSize: 'clamp(0.55rem, 0.65vw, 0.65rem)' }}>차트 데이터 로딩 중...</span>
            </div>
          </div>
        </div>
      );
    }

    if (chartErrorArray[index] && chartErrorArray[index].length > 0) {
      return (
        <div>
          <div className="bg-gray-100 px-3 py-1 border border-gray-200 flex justify-between items-center" style={{ borderRadius: '0.375rem 0.375rem 0 0' }}>
            <div className="flex items-center">
              <span className="font-medium text-xs text-xs" style={{ fontSize: 'clamp(0.65rem, 0.75vw, 0.75rem)' }}>{chartStockNames[index] || '오류'}</span>
              <span className={`ml-2 text-xs px-1.5 py-0.5 rounded bg-red-100 text-red-800`}>
                오류
              </span>
            </div>
            {chartRsValues[index] && (
              <div className="flex items-center">
                <span className="text-xs text-gray-500 mr-1" style={{ fontSize: 'clamp(0.65rem, 0.75vw, 0.75rem)' }}>RS</span>
                <span className="font-medium text-xs text-blue-600" style={{ fontSize: 'clamp(0.65rem, 0.75vw, 0.75rem)' }}>{chartRsValues[index]}</span>
              </div>
            )}
          </div>
          <div className="h-72 flex items-center justify-center border border-gray-200 border-t-0" style={{ borderRadius: '0 0 0.375rem 0.375rem' }}>
            <span className="text-red-500" style={{ fontSize: 'clamp(0.6rem, 0.7vw, 0.7rem)' }}>{chartErrorArray[index]}</span>
          </div>
        </div>
      );
    }

    if (!chartDataArray[index] || chartDataArray[index].length === 0) {
      return (
        <div>
          <div className="bg-gray-100 px-3 py-1 border border-gray-200 flex justify-between items-center" style={{ borderRadius: '0.375rem 0.375rem 0 0' }}>
            <div className="flex items-center">
              <span className="font-medium text-xs text-xs" style={{ fontSize: 'clamp(0.65rem, 0.75vw, 0.75rem)' }}>{chartStockNames[index] || '데이터 없음'}</span>
              <span className={`ml-2 text-xs px-1.5 py-0.5 rounded bg-gray-300 text-gray-700`}>
                {chartMarketTypes[index] || '...'}
              </span>
            </div>
            {chartRsValues[index] && (
              <div className="flex items-center">
                <span className="text-xs text-gray-500 mr-1" style={{ fontSize: 'clamp(0.65rem, 0.75vw, 0.75rem)' }}>RS</span>
                <span className="font-medium text-xs text-blue-600" style={{ fontSize: 'clamp(0.65rem, 0.75vw, 0.75rem)' }}>{chartRsValues[index]}</span>
              </div>
            )}
          </div>
          <div className="h-72 flex items-center justify-center border border-gray-200 border-t-0" style={{ borderRadius: '0 0 0.375rem 0.375rem' }}>
            <div className="flex flex-col items-center">
              <span className="text-gray-400" style={{ fontSize: 'clamp(0.55rem, 0.65vw, 0.65rem)' }}>표시할 차트 데이터가 없습니다.</span>
            </div>
          </div>
        </div>
      );
    }

    // 시장 구분에 따라 배경색 설정
    const marketType = chartMarketTypes[index];
    const bgColorClass = 'bg-gray-200 text-gray-700'; // 회색 버튼 스타일로 고정

    return (
      <div>
        <div className="bg-gray-100 px-3 py-1 border border-gray-200 flex justify-between items-center" style={{ borderRadius: '0.375rem 0.375rem 0 0' }}>
          <div className="flex items-center">
            <span className="font-medium text-xs text-xs" style={{ fontSize: 'clamp(0.65rem, 0.75vw, 0.75rem)' }}>{chartStockNames[index]}</span>
            <span 
              className={`ml-2 px-1.5 py-0.5 rounded ${bgColorClass}`}
              style={{ fontSize: 'clamp(0.6rem, 0.7vw, 0.7rem)' }}
            >
              {marketType}
            </span>
          </div>
          {chartRsValues[index] && (
            <div className="flex items-center">
              <span className="text-xs text-gray-500 mr-1" style={{ fontSize: 'clamp(0.65rem, 0.75vw, 0.75rem)' }}>RS</span>
              <span className="font-medium text-xs text-blue-600" style={{ fontSize: 'clamp(0.65rem, 0.75vw, 0.75rem)' }}>{chartRsValues[index]}</span>
            </div>
          )}
        </div>
        <ChartComponent 
          data={chartDataArray[index]} 
          marketType={marketType} 
          height={280}
        />
      </div>
    );
  };

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
    <div className="flex-1 p-0 sm:p-2 md:p-4 overflow-auto w-full">
      {/* 메인 콘텐츠 영역 - 모바일 최적화 */}
      <div className="w-full max-w-[1280px] mx-auto">
        {/* 테이블 섹션 컨테이너 */}
        <div className="bg-white rounded-md shadow p-2 md:p-4 flex-1 flex flex-col overflow-hidden mb-6">
          {/* RS 순위 테이블 & 52주 신고/신저가 */}
          <div className="bg-white rounded-md shadow">
            <div className="p-2 md:p-4"> 
              <Suspense fallback={<div className="h-80 flex items-center justify-center">로딩 중...</div>}>
                {/* RS 순위 및 52주 신고/신저가 테이블 영역 */}
                <div className="flex flex-col gap-6">
                  
                  {/* RS 순위 테이블 섹션 */}
                  <div className="flex-1">
                    <div ref={rsHeaderRef} className="flex justify-between items-center mb-2">
                      <GuideTooltip
  title="RS (Relative Strength)란?"
  description={`RS는 '상대강도'를 의미하며, 특정 종목의 주가 수익률이 시장 전체(예: 코스피, 코스닥 지수)의 수익률과 비교하여 얼마나 강한지 또는 약한지를 나타내는 지표입니다.\n시가총액 2천억 미만은 제외된 리스트입니다.`}
  side="top"
  width={360}
  collisionPadding={{ left: 260 }}
>
  <h2 className="text-sm md:text-base font-semibold cursor-help" style={{ color: 'var(--primary-text-color, var(--primary-text-color-fallback))' }}>
    RS 순위
  </h2>
</GuideTooltip>
                      <div className="flex items-center space-x-2">
   {/* 종목명/종목코드 검색 input - 밸류에이션과 동일한 디자인 */}
   {/* 이미지 복사(캡처) 중에는 입력 박스를 숨긴다 */}
   {!isRsTableCapturing && (
    <div className="flex items-center">
      <label htmlFor="rsSearchFilter" className="text-[10px] sm:text-xs font-medium mr-1 sm:mr-2 whitespace-nowrap" style={{ color: 'oklch(0.5 0.03 257.287)' }}>
        종목명/종목코드
      </label>
      {selectedStock ? (
        <button
          onClick={handleClearSelectedStock}
          className="px-2 sm:px-3 py-1 bg-[#D8EFE9] text-gray-700 rounded text-[10px] sm:text-xs hover:bg-[#c5e0da] focus:outline-none flex items-center"
          style={{
            height: '35px',
            borderRadius: '4px',
            width: 'clamp(120px, 15vw, 180px)',
            minWidth: 120,
            maxWidth: 180,
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap'
          }}
        >
          <span className="truncate">{selectedStock.name} ({selectedStock.code})</span>
          <span className="ml-1">×</span>
        </button>
      ) : (
        <div className="flex items-center">
          <input
            id="rsSearchFilter"
            type="text"
            value={searchFilter}
            onChange={e => setSearchFilter(e.target.value)}
            onKeyDown={handleSearchKeyDown}
            placeholder="종목명/종목코드 입력"
            className="px-2 sm:px-3 border border-gray-300 text-[10px] sm:text-xs focus:outline-none focus:ring-2 focus:ring-[#D8EFE9] focus:border-transparent truncate"
            style={{
              width: 'clamp(120px, 15vw, 180px)',
              minWidth: 120,
              maxWidth: 180,
              height: '35px',
              borderRadius: '4px',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap'
            }}
          />
        </div>
      )}
    </div>
   )}
  {/* 업데이트 날짜 표시 */}
  {updateDate && (
    <span className="text-xs mr-2" style={{ fontSize: 'clamp(0.7rem, 0.7vw, 0.7rem)', color: 'var(--text-muted-color, var(--text-muted-color-fallback))' }}>
      updated {updateDate}
    </span>
  )}
  <div className="hidden md:block">
    {/*
      TableCopyButton(이미지 복사 버튼) 임시 숨김
      <TableCopyButton 
        tableRef={rsTableRef} 
        headerRef={rsHeaderRef} 
        tableName="RS 순위 TOP 200" 
        updateDateText={updateDate ? `updated ${updateDate}` : undefined}
        // --- 복사(캡처) 시작/종료 시 입력 박스 숨김/표시를 위한 핸들러 연결 ---
        onStartCapture={() => setIsRsTableCapturing(true)}
        onEndCapture={() => setIsRsTableCapturing(false)}
      />
    */}
  </div>
</div>
                    </div>
                    <div className="relative">
                      <div className="flex-1 overflow-x-auto scrollbar-thin scrollbar-thumb-gray-300 scrollbar-track-transparent" ref={rsTableRef}>
                        <table className="w-full bg-white border border-gray-200 table-fixed">
                          <thead>
                            <tr className="bg-gray-100">
                              {(() => {
                                // 표시할 헤더 순서 정의
                                const desiredOrder = ['종목코드', '종목명', '업종', 'RS', 'RS_1M', 'RS_3M', 'RS_6M', 'MTT', '시가총액'];
                                // '테마명' 제외하고 원하는 순서대로 정렬
                                const orderedHeaders = DESIRED_COLUMNS;

                                return orderedHeaders.map((header, index) => (
                                  <th 
                                    key={header}
                                    className={`px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer border border-gray-200 text-xs
                                      ${header === '업종' ? 'text-center' : ''} // 업종 헤더 가운데 정렬
                                      ${
                                      // 모바일 화면에서 숨길 컬럼들
                                      (header === '업종' || header === 'RS_3M' || header === 'RS_6M' || header === '시가총액' || header === '종목코드') ? 'hidden md:table-cell' : 
                                      ''
                                    }`}
                                    style={{
                                      width: header === 'RS' || header === 'RS_1M' || header === 'RS_3M' || header === 'RS_6M' || header === 'MTT' ? '70px' :
                                             header === '시가총액' || header === '거래대금' ? '110px' :
                                             header === '종목명' ? '200px' :
                                             header === '종목코드' ? '90px' :
                                             header === '업종' ? '150' : // 업종 너비 자동
                                             'auto',
                                      minWidth: header === '업종' ? '100px' : undefined, // 업종 최소 너비
                                      // maxWidth: header === '업종' ? '200px' : undefined, // 필요시 최대 너비 설정
                                      height: '35px', // 높이 적용
                                    }}
                                    onClick={() => requestSort(header)}
                                  >
                                    <div className={`flex items-center ${header === '업종' ? 'justify-center' : 'justify-center'}`}> {/* 헤더 텍스트 정렬 */} 
                                      {header === 'RS' ? (
  // RS 컬럼에만 툴팁 적용 (아이콘 없이 텍스트 전체에 마우스 오버)
  <GuideTooltip
    title="RS란?"
    description={`RS (상대강도, Relative Strength)\n1년 동안의 주가 변화를 평가합니다.\n최근 1분기, 2분기, 3분기, 4분기 전의 종가를 각각 비교하여 점수를 산출합니다.\n\n실제 생활 예시\n1년 동안 네 번의 건강검진을 받는다고 생각해보세요.\n최근 건강검진(3개월 전) 결과가 이전보다 좋아졌다면, 이 부분을 두 배로 평가합니다(최근 변화가 중요하니까요).\n그 외에도 3개월 단위로 건강이 얼마나 좋아졌는지 각각 평가해서 모두 합산합니다.\n즉, 최근 변화에 더 큰 비중을 두고, 1년간의 건강 변화 전체를 종합적으로 판단하는 방식입니다.`}
    side="top"
    width={340}
    collisionPadding={{ left: 260 }}
  >
    <span
      className="flex items-center justify-center w-full h-full px-2 py-1 rounded hover:bg-neutral-200/60 transition cursor-help text-center"
      style={{ color: 'oklch(0.372 0.044 257.287)', minWidth: 36 }}
    >
      {formatHeaderName(header)}
    </span>
  </GuideTooltip>
) : header === 'RS_1M' ? (
  // RS_1M 컬럼에도 동일한 방식으로 툴팁 적용
  <GuideTooltip
    title="RS_1M (1개월 상대강도)"
    description={`RS_1M (1개월 상대강도)\n코드 로직\n최근 1개월(21거래일) 동안의 주가 변화를 평가합니다.\n\n실제 생활 예시\n한 달 전과 지금의 몸무게를 비교하는 것과 같습니다.\n예를 들어, 한 달 전에 70kg이었고 지금 72kg이라면, 72/70 = 1.028, 즉 2.8% 증가한 셈입니다.`}
    side="top"
    width={340}
    collisionPadding={{ left: 260 }}
  >
    <span
      className="flex items-center justify-center w-full h-full px-2 py-1 rounded hover:bg-neutral-200/60 transition cursor-help text-center"
      style={{ color: 'oklch(0.372 0.044 257.287)', minWidth: 36 }}
    >
      {formatHeaderName(header)}
    </span>
  </GuideTooltip>
) : header === 'RS_3M' ? (
  // RS_3M 컬럼에도 동일한 방식으로 툴팁 적용
  <GuideTooltip
    title="RS_3M (3개월 상대강도)"
    description={`RS_3M (3개월 상대강도)\n코드 로직\n최근 3개월(63거래일, 1분기) 동안의 주가 변화를 평가합니다.\n\n실제 생활 예시\n3개월 전과 지금의 체력(예: 100m 달리기 기록)을 비교하는 것과 같습니다.\n3개월 전보다 빨라졌다면, 점수가 1보다 크고, 느려졌다면 1보다 작게 나옵니다.`}
    side="top"
    width={340}
    collisionPadding={{ left: 260 }}
  >
    <span
      className="flex items-center justify-center w-full h-full px-2 py-1 rounded hover:bg-neutral-200/60 transition cursor-help text-center"
      style={{ color: 'oklch(0.372 0.044 257.287)', minWidth: 36 }}
    >
      {formatHeaderName(header)}
    </span>
  </GuideTooltip>
) : header === 'RS_6M' ? (
  // RS_6M 컬럼에도 동일한 방식으로 툴팁 적용
  <GuideTooltip
    title="RS_6M (6개월 상대강도)"
    description={`RS_6M (6개월 상대강도)\n코드 로직\n최근 6개월(126거래일) 동안의 주가 변화를 평가합니다.\n\n실제 생활 예시\n6개월 전과 지금의 저축액을 비교하는 것과 같습니다.\n6개월 전에 100만 원이었고 지금 120만 원이라면, 120/100 = 1.2, 즉 20% 늘어난 것입니다.`}
    side="top"
    width={340}
    collisionPadding={{ left: 260 }}
  >
    <span
      className="flex items-center justify-center w-full h-full px-2 py-1 rounded hover:bg-neutral-200/60 transition cursor-help text-center"
      style={{ color: 'oklch(0.372 0.044 257.287)', minWidth: 36 }}
    >
      {formatHeaderName(header)}
    </span>
  </GuideTooltip>
) : header === 'MTT' ? (
  // MTT 컬럼에도 동일한 방식으로 툴팁 적용
  <GuideTooltip
    title="MTT란?"
    description={`MTT는 윌리엄 오닐의 CAN SLIM 전략에서 \"추세(Trend)\"를 반영한 지표입니다.\n단순히 RS(상대강도) 점수가 높은 종목 중에서, 여러 이동평균선(5일, 20일, 60일, 120일 등) 위에 주가가 모두 위치한, 즉 상승 추세가 뚜렷한 종목만을 선별합니다.\n이 조건을 만족하는 종목만 RS 점수를 인정받아 MTT 점수가 부여되고, 그렇지 않으면 0점이 됩니다.\n\n비유:\n공부(성적, RS)는 잘하지만, 생활습관(규칙적인 운동, 이동평균선 위 주가)이 좋은 학생만 상(MTT 점수)을 받는 것과 같습니다.`}
    side="top"
    width={340}
    collisionPadding={{ left: 260 }}
  >
    <span
      className="flex items-center justify-center w-full h-full px-2 py-1 rounded hover:bg-neutral-200/60 transition cursor-help text-center"
      style={{ color: 'oklch(0.372 0.044 257.287)', minWidth: 36 }}
    >
      {formatHeaderName(header)}
    </span>
  </GuideTooltip>
) : (
  <span style={{ color: 'oklch(0.372 0.044 257.287)' }}>{formatHeaderName(header)}</span>
)}
                                      {sortKey === header && (
                                        <span className="ml-1">
                                          {sortDirection === 'asc' ? '▲' : '▼'}
                                        </span>
                                      )}
                                    </div>
                                  </th>
                                ))
                              })()}
                            </tr>
                          </thead>
                          <tbody>
                            {currentPageData.map((row, rowIndex) => (
                              <tr key={rowIndex} className={rowIndex % 2 === 0 ? 'bg-gray-50' : 'bg-white'}>
                                {(() => {
                                  // 헤더와 동일한 순서로 셀 렌더링
                                  const desiredOrder = ['종목코드', '종목명', '업종', 'RS', 'RS_1M', 'RS_3M', 'RS_6M', 'MTT', '시가총액'];
                                  const orderedHeaders = DESIRED_COLUMNS;

                                  return orderedHeaders.map((header, colIndex) => (
                                    <td 
                                      key={header}
                                      className={`py-1 px-1 sm:py-1.5 sm:px-2 border-b border-r ${getCellAlignment(header)} whitespace-nowrap overflow-hidden text-ellipsis text-xs
                                        ${
                                        // 모바일 화면에서 숨길 컬럼들 (종목명, RS, RS_1M, MTT는 항상 표시)
                                        (header === '업종' || header === 'RS_3M' || header === 'RS_6M' || header === '시가총액' || header === '종목코드') ? 'hidden md:table-cell' : 
                                        ''
                                      }`}
                                      style={{ 
                                        height: '35px', // 높이 적용
                                      }}
                                      title={header === '업종' ? row[header] : ''} // 업종 셀에 툴팁 추가
                                    >
                                      {header === 'MTT' ? (
                                        String(row[header]).toLowerCase() === 'y' ? (
                                          <div className="flex items-center justify-center h-full w-full">
                                            <CheckCircleIcon className="h-5 w-5 text-green-500" />
                                          </div>
                                        ) : null
                                      ) : formatCellValue(header, row[header])}
                                    </td>
                                  ))
                                })()}
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                      
                      {/* 페이지네이션 */}
                      <div className="mt-4 flex justify-center">
                        <div className="flex items-center space-x-1">
                          <button
                            // h-8, flex, items-center 제거하고 py-1 추가하여 이전 높이로 복원
                            className="px-2 py-1 bg-gray-200 rounded hover:bg-gray-300 text-sm text-xs"
                            style={{ 
                              fontSize: 'clamp(0.65rem, 0.7vw, 0.7rem)',
                            }}
                            onClick={() => setCurrentPage(1)}
                            disabled={currentPage === 1}
                          >
                            <span className="hidden sm:inline">처음</span>
                            <span className="sm:hidden">«</span>
                          </button>
                          <button
                            // h-8, flex, items-center 제거하고 py-1 추가하여 이전 높이로 복원
                            className="px-2 py-1 bg-gray-200 rounded hover:bg-gray-300 text-sm text-xs"
                            style={{ 
                              fontSize: 'clamp(0.65rem, 0.7vw, 0.7rem)',
                            }}
                            onClick={() => setCurrentPage(currentPage - 1)}
                            disabled={currentPage === 1}
                          >
                            <span className="hidden sm:inline">이전</span>
                            <span className="sm:hidden">‹</span>
                          </button>
                          
                          {/* 페이지 번호 버튼 - 모바일에서는 줄이고 PC에서는 더 많이 표시 */}
                          {Array.from({ length: totalPages }).map((_, index) => {
                            const pageNumber = index + 1;
                            // 모바일에서는 현재 페이지 주변 1개만 표시, PC에서는 2개 표시
                            const visibleOnMobile = Math.abs(pageNumber - currentPage) <= 1;
                            const visibleOnDesktop = Math.abs(pageNumber - currentPage) <= 2;
                            
                            if (visibleOnDesktop) {
                              return (
                                <button
                                  key={index}
                                  // w-8 고정 너비 및 중앙 정렬은 유지, h-8 제거하고 py-1 추가하여 높이 복원
                                  className={`w-8 py-1 flex justify-center ${
                                    pageNumber === currentPage
                                      ? 'bg-[#D8EFE9] text-gray-700 rounded'
                                      : 'bg-gray-200 rounded hover:bg-gray-300'
                                  } text-sm text-xs ${!visibleOnMobile ? 'hidden sm:inline-block' : ''}`}
                                  style={{ 
                                    fontSize: 'clamp(0.65rem, 0.7vw, 0.7rem)',
                                  }}
                                  onClick={() => setCurrentPage(pageNumber)}
                                >
                                  {pageNumber}
                                </button>
                              );
                            }
                            return null;
                          })}
                          
                          <button
                            // h-8, flex, items-center 제거하고 py-1 추가하여 이전 높이로 복원
                            className="px-3 py-1 bg-gray-200 rounded hover:bg-gray-300 text-sm text-xs"
                            style={{ 
                              fontSize: 'clamp(0.65rem, 0.7vw, 0.7rem)',
                            }}
                            onClick={() => setCurrentPage(currentPage + 1)}
                            disabled={currentPage === totalPages}
                          >
                            <span className="hidden sm:inline">다음</span>
                            <span className="sm:hidden">›</span>
                          </button>
                          <button
                            // h-8, flex, items-center 제거하고 py-1 추가하여 이전 높이로 복원
                            className="px-2 py-1 bg-gray-200 rounded hover:bg-gray-300 text-sm text-xs"
                            style={{ 
                              fontSize: 'clamp(0.65rem, 0.7vw, 0.7rem)',
                            }}
                            onClick={() => setCurrentPage(totalPages)}
                            disabled={currentPage === totalPages}
                          >
                            <span className="hidden sm:inline">마지막</span>
                            <span className="sm:hidden">»</span>
                          </button>
                        </div>
                      </div>
                    </div>
                  </div>

                  
                </div>
              </Suspense>
            </div>
          </div>
        </div>

        {/* 차트 섹션 탭 메뉴 - 컨테이너 외부로 배치 */}
        <div className="border-b border-gray-200">
          <div className="flex w-max space-x-0">
            <button
              className={`px-4 py-2 text-sm font-medium rounded-tl-[6px] border-t border-l border-r border-gray-200 ${chartTab === 'rs' ? 'bg-white font-extrabold text-base' : 'hover:bg-gray-100 border-b'}`}
              onClick={() => setChartTab('rs')}
              style={{ 
                color: chartTab === 'rs' ? 'var(--primary-text-color, var(--primary-text-color-fallback))' : 'var(--text-muted-color, var(--text-muted-color-fallback))',
                fontWeight: chartTab === 'rs' ? 700 : 400
              }}
            >
              RS상위 차트
            </button>
            <button
              className={`px-4 py-2 text-sm font-medium rounded-tr-[6px] border-t border-r border-gray-200 ${chartTab === 'mtt' ? 'bg-white font-extrabold text-base' : 'hover:bg-gray-100 border-b'}`}
              onClick={() => setChartTab('mtt')}
              style={{ 
                color: chartTab === 'mtt' ? 'var(--primary-text-color, var(--primary-text-color-fallback))' : 'var(--text-muted-color, var(--text-muted-color-fallback))',
                fontWeight: chartTab === 'mtt' ? 700 : 400
              }}
            >
              MTT 상위 차트
            </button>
          </div>
        </div>
        
        {/* RS상위 차트 탭 컨텐츠 */}
        {chartTab === 'rs' && (
          <div className="bg-white rounded-md shadow p-2 md:p-4 flex-1 flex flex-col overflow-hidden">
            <div className="p-2 md:p-4">
              <Suspense fallback={<div className="h-80 flex items-center justify-center">로딩 중...</div>}>
                <div className="mb-3 flex justify-between items-center">
                  <GuideTooltip
                    title="RS상위 시장 비교차트"
                    description={`RS 상위 21개 종목의 차트를 해당 종목이 속한 시장 지수(KOSPI, KOSDAQ)와 함께, 주봉 기준으로 52주간의 가격 변화를 비교합니다.`}
                    side="top"
                    width={360}
                    collisionPadding={{ left: 260 }}
                  >
                    <span className="inline-flex items-center">
                      <h2 className="text-sm md:text-base font-semibold cursor-help" style={{ color: 'var(--primary-text-color, var(--primary-text-color-fallback))' }} data-state="closed">
                        RS상위 시장 비교차트
                      </h2>
                    </span>
                  </GuideTooltip>
                  {/* 업데이트 날짜 표시 */}
                  {updateDate && (
                    <span className="text-xs mr-2" style={{ fontSize: 'clamp(0.7rem, 0.7vw, 0.7rem)', color: 'var(--text-muted-color, var(--text-muted-color-fallback))' }}>
                      updated {updateDate}
                    </span>
                  )}
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                  {Array.from({length: 21}).map((_, index) => (
                    <div key={index} className="rounded-md">
                      {renderChartComponent(index)}
                    </div>
                  ))}
                </div>
              </Suspense>
            </div>
          </div>
        )}
        
        {/* MTT 상위 차트 탭 컨텐츠 */}
        {chartTab === 'mtt' && (
          <div className="bg-white rounded-md shadow p-2 md:p-4 flex-1 flex flex-col overflow-hidden">
            <div className="p-2 md:p-4">
              <Suspense fallback={<div className="h-80 flex items-center justify-center">로딩 중...</div>}>
                <div className="mb-3 flex justify-between items-center">
                  <GuideTooltip
                    title="MTT상위 시장 비교차트"
                    description={`MTT 상위 종목의 차트를 해당 종목이 속한 시장 지수(KOSPI, KOSDAQ)와 함께, 주봉 기준으로 52주간의 가격 변화를 비교합니다.`}
                    side="top"
                    width={360}
                    collisionPadding={{ left: 260 }}
                  >
                    <span className="inline-flex items-center">
                      <h2 className="text-sm md:text-base font-semibold cursor-help" style={{ color: 'var(--primary-text-color, var(--primary-text-color-fallback))' }} data-state="closed">
                        MTT상위 시장 비교차트
                      </h2>
                    </span>
                  </GuideTooltip>
                  {/* 업데이트 날짜 표시 */}
                  {updateDate && (
                    <span className="text-xs mr-2" style={{ fontSize: 'clamp(0.7rem, 0.7vw, 0.7rem)', color: 'var(--text-muted-color, var(--text-muted-color-fallback))' }}>
                      updated {updateDate}
                    </span>
                  )}
                </div>
                {/* MTT 상위 차트 컴포넌트 렌더링 */}
                <MTTtopchart />
              </Suspense>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
