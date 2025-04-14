'use client'

import { Suspense, useState, useEffect, useMemo, useCallback, useRef } from 'react'
import { useRouter, useSearchParams } from 'next/navigation';
import Papa from 'papaparse';
import { format, subDays } from 'date-fns';
import { formatDateMMDD } from '../utils/dateUtils';
import ChartComponent from '../components/ChartComponent'
import { fetchCSVData } from '../utils/fetchCSVData'
import html2canvas from 'html2canvas';
import TableCopyButton from '../components/TableCopyButton';

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
  // 상태 관리
  const [csvData, setCsvData] = useState<CSVData>({ headers: [], rows: [], errors: [] });
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [currentPage, setCurrentPage] = useState<number>(1);
  const [sortKey, setSortKey] = useState<string>('RS');
  const [sortDirection, setSortDirection] = useState<SortDirection>('desc');
  const rsTableRef = useRef<HTMLDivElement>(null);
  const rsHeaderRef = useRef<HTMLDivElement>(null);
  const highTableRef = useRef<HTMLDivElement>(null);
  const highHeaderRef = useRef<HTMLDivElement>(null);
  
  // 52주 신고가 데이터 관련 상태
  const [highData, setHighData] = useState<CSVData>({ headers: [], rows: [], errors: [] });
  const [highDataLoading, setHighDataLoading] = useState<boolean>(true);
  const [highDataError, setHighDataError] = useState<string | null>(null);
  const [highSortKey, setHighSortKey] = useState<string>('RS');
  const [highSortDirection, setHighSortDirection] = useState<SortDirection>('desc');
  
  // 업데이트 날짜 상태 추가
  const [updateDate, setUpdateDate] = useState<string | null>(null); 
  
  // 차트 데이터 관련 상태 - 20개의 차트를 위한 상태 배열로 변경
  const [chartDataArray, setChartDataArray] = useState<CandleData[][]>(Array.from({length: 20}, () => []));
  const [chartLoadingArray, setChartLoadingArray] = useState<boolean[]>(Array.from({length: 20}, () => false));
  const [chartErrorArray, setChartErrorArray] = useState<string[]>(Array.from({length: 20}, () => '')); 
  const [chartMarketTypes, setChartMarketTypes] = useState<string[]>(Array.from({length: 20}, () => '')); // 빈 문자열로 초기화
  // 종목명을 저장할 상태 추가
  const [chartStockNames, setChartStockNames] = useState<string[]>(Array.from({length: 20}, () => ''));
  // RS 값을 저장할 상태 추가
  const [chartRsValues, setChartRsValues] = useState<string[]>(Array.from({length: 20}, () => ''));
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
          const rsDataFilePath = '/requestfile/stock-data/stock_1uyjvdmzfxarsxs0jy16fegfrqy9fs8yd.csv';
          
          // 로컬 캐시 파일 로드
          const response = await fetch(cacheFilePath, { cache: 'no-store' });
          
          if (!response.ok) {
            throw new Error(`캐시 파일 로드 실패: ${response.status}`);
          }
          
          const csvText = await response.text();
          
          // RS 데이터 파일 로드
          const rsResponse = await fetch(rsDataFilePath, { cache: 'no-store' });
          
          if (!rsResponse.ok) {
            console.error(`RS 데이터 파일 로드 실패: ${response.status}`);
            throw new Error(`RS 데이터 파일 로드 실패: ${response.status}`);
          }
          
          const rsCsvText = await rsResponse.text();
          
          // CSV 파싱 및 데이터 처리
          const parsedData = parseCSV(csvText);
          const rsParsedData = parseCSV(rsCsvText);
          
          // RS 데이터를 종목명으로 매핑하여 빠르게 검색할 수 있도록 Map 생성
          const rsDataMap = new Map();
          rsParsedData.rows.forEach(row => {
            if (row['종목명']) {
              // 시가총액을 억 단위로 변환
              let marketCapBillion = 0;
              if (row['시가총액']) {
                const marketCap = String(row['시가총액']).replace(/,/g, '');
                marketCapBillion = Math.floor(Number(marketCap) / 100000000); // 억 단위로 변환
              }
              
              rsDataMap.set(row['종목명'], {
                RS: row['RS'] || '',
                시가총액: marketCapBillion,
                테마명: row['테마명'] || ''
              });
            }
          });
          
          // 데이터 변환 - 컬럼명 매핑 (종목명 -> stockName, RS -> rs)
          const transformedData = {
            headers: parsedData.headers,
            rows: parsedData.rows.map(row => {
              // 종목명으로 RS 데이터 매핑
              const stockName = row['종목명'];
              
              const rsData = rsDataMap.get(stockName) || { RS: '', 시가총액: '', 테마명: '' }; // 테마명 추가
              
              return {
                stockName: stockName,
                rs: rsData.RS || row['거래대금'], // RS 데이터가 있으면 사용, 없으면 거래대금 사용
                시가총액: rsData.시가총액,
                ...row
              };
            }),
            errors: parsedData.errors
          };
          
          setHighData(transformedData);
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
        // 로컬 캐시 파일에서 직접 로드
        const cacheFilePath = '/requestfile/stock-data/stock_1idvb5kio0d6dchvoywe7ovwr-ez1cbpb.csv';
        
        // 로컬 캐시 파일 로드
        const response = await fetch(cacheFilePath, { cache: 'no-store' });
        
        if (!response.ok) {
          throw new Error(`캐시 파일 로드 실패: ${response.status}`);
        }
        
        const csvText = await response.text();
        
        // CSV 파싱 및 데이터 처리
        const parsedData = parseCSV(csvText);
        
        if (parsedData && parsedData.rows.length > 0) {
          const dateString = parsedData.rows[0]['날짜']; // 첫 번째 행의 '날짜' 컬럼 값 사용
          if (dateString) {
            const formatted = formatDateMMDD(dateString);
            if (formatted) {
              setUpdateDate(formatted);
            } else {
              console.error('Failed to format update date from CSV.');
               // setError('Failed to format update date from CSV.'); // 필요시 에러 상태 업데이트
            }
          } else {
            console.error('Date column "날짜" not found or empty in date CSV.');
            // setError('Date column "날짜" not found or empty in date CSV.');
          }
        } else {
          console.error('Failed to parse or empty date CSV.');
          // setError('Failed to parse or empty date CSV.');
        }
      } catch (err) {
        console.error('Failed to load update date:', err);
        // setError(err instanceof Error ? err.message : String(err)); // 필요시 에러 상태 업데이트
      }
    };
    
    loadData();
    loadHighData();
    loadUpdateDate();
    // loadStockPriceData();
  }, []);

  // 차트 데이터 로드 함수
  const loadAllChartData = async (rsData?: CSVData) => {
    try {
      // RS 랭크 데이터가 없으면 리턴
      if (!rsData || !rsData.rows || rsData.rows.length === 0) {
        return;
      }
      
      // 상위 20개 종목 추출
      const top20Stocks = rsData.rows.slice(0, 20);
      
      // 차트 데이터 배열 초기화
      const newChartDataArray: CandleData[][] = Array.from({length: 20}, () => []);
      const newStockNames: string[] = Array.from({length: 20}, () => '');
      const newMarketTypes: string[] = Array.from({length: 20}, () => ''); // 빈 문자열로 초기화
      const newChartLoadingArray: boolean[] = Array.from({length: 20}, () => true);
      const newChartErrorArray: string[] = Array.from({length: 20}, () => '');
      const newRsValues: string[] = Array.from({length: 20}, () => '');
      
      // RS 값 설정 (종목 데이터에서 가져옴)
      top20Stocks.forEach((stock, index) => {
        if (index < 20) {
          newRsValues[index] = stock.RS ? String(stock.RS) : '';
          newStockNames[index] = stock.종목명 || '';
        }
      });
      
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
        '/requestfile/chart-data/20.csv'
      ];
      
      // 시장 지수 데이터 파일 경로
      const kospiIndexPath = '/requestfile/market-index/1dzf65fz6elq6b5znvhuaftn10hqjbe_c.csv';
      const kosdaqIndexPath = '/requestfile/market-index/1ks9qkdzmsxv-qenv6udzzidfwgykc1qg.csv';
      
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
                open: parseFloat(row['시가'] || 0),
                high: parseFloat(row['고가'] || 0),
                low: parseFloat(row['저가'] || 0),
                close: parseFloat(row['종가'] || 0),
                volume: parseFloat(row['거래량'] || 0),
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
                open: parseFloat(row['시가'] || 0),
                high: parseFloat(row['고가'] || 0),
                low: parseFloat(row['저가'] || 0),
                close: parseFloat(row['종가'] || 0),
                volume: parseFloat(row['거래량'] || 0),
              };
            });
        }
      } catch (error) {
        console.error('시장 지수 데이터 로드 오류:', error);
      }
      
      // 실제 데이터 로드 (최대 20개)
      const loadLimit = Math.min(20, top20Stocks.length);
      
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
      setChartLoadingArray(Array.from({length: 20}, () => false));
      setChartErrorArray(Array.from({length: 20}, () => `데이터 로드 실패: ${error instanceof Error ? error.message : '알 수 없는 오류'}`));
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
          if (!isValid) {
            console.warn(`유효하지 않은 데이터 행:`, row);
          }
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
  const formatMarketCap = (value: any): string => {
    if (!value) return '0';
    
    // 숫자가 아니면 그대로 반환
    if (isNaN(Number(value))) return String(value);
    
    // 숫자로 변환
    const valueStr = typeof value === 'number' ? String(value) : value;
    let marketCapValue = Number(valueStr.replace(/[^0-9.]/g, ''));
    
    // 10억 이상인 경우 억 단위로 변환 (1,000,000,000 이상)
    if (marketCapValue >= 100000000) {
      marketCapValue = marketCapValue / 100000000; // 억 단위로 변환
    }
    
    // 소수점 제거하고 천 단위 구분 쉼표(,) 추가
    return Math.floor(marketCapValue).toLocaleString('ko-KR');
  };

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

  // 현재 페이지에 표시할 데이터 계산
  const currentPageData = useMemo(() => {
    if (!csvData || !csvData.rows) {
      return [];
    }
    
    // 시가총액 2천억 이상 필터링 적용
    const filteredByMarketCap = csvData.rows.filter((row: any) => {
      const marketCap = Number(row['시가총액'] || 0);
      const isAboveThreshold = marketCap >= 200000000000; // 2천억 이상
      
      return isAboveThreshold;
    });
    
    // 정렬된 데이터 가져오기
    const sortedData = sortDirection 
      ? sortData(filteredByMarketCap, sortKey, sortDirection)
      : filteredByMarketCap;
    
    const startIndex = (currentPage - 1) * 20;
    return sortedData.slice(startIndex, startIndex + 20);
  }, [csvData, currentPage, sortKey, sortDirection]);

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
      const valueStr = typeof value === 'number' ? String(value) : value;
      let marketCapValue = Number(valueStr.replace(/[^0-9.]/g, ''));
      
      // 10억 이상인 경우 억 단위로 변환 (1,000,000,000 이상)
      if (marketCapValue >= 100000000) {
        marketCapValue = marketCapValue / 100000000; // 억 단위로 변환
      }
      
      // 소수점 제거하고 천 단위 구분 쉼표(,) 추가
      return Math.floor(marketCapValue).toLocaleString('ko-KR');
    }
    
    // 거래대금 컬럼인 경우 억 단위로 포맷팅
    if (header === '거래대금') {
      // 숫자가 아니면 그대로 반환
      if (isNaN(Number(value))) return value;
      
      // 숫자로 변환 후 억 단위로 나누고 소수점 없이 표시
      const valueStr = typeof value === 'number' ? String(value) : value;
      const tradeAmountInBillions = Number(valueStr.replace(/[^0-9.]/g, ''));
      
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
                <span className="text-xs text-gray-500 mr-1" style={{ fontSize: 'clamp(0.55rem, 0.65vw, 0.65rem)' }}>RS</span>
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
                <span className="text-xs text-gray-500 mr-1" style={{ fontSize: 'clamp(0.55rem, 0.65vw, 0.65rem)' }}>RS</span>
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
                <span className="text-xs text-gray-500 mr-1" style={{ fontSize: 'clamp(0.55rem, 0.65vw, 0.65rem)' }}>RS</span>
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
              <span className="text-xs text-gray-500 mr-1" style={{ fontSize: 'clamp(0.55rem, 0.65vw, 0.65rem)' }}>RS</span>
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

  // 시장 지수 데이터 로드 함수
  const loadMarketIndexData = async () => {
    try {
      // 시장 지수 데이터 로드 (코스피, 코스닥)
      const kospiIndexPath = '/requestfile/market-index/1dzf65fz6elq6b5znvhuaftn10hqjbe_c.csv';
      const kosdaqIndexPath = '/requestfile/market-index/1ks9qkdzmsxv-qenv6udzzidfwgykc1qg.csv';
      
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
                open: parseFloat(row['시가'] || 0),
                high: parseFloat(row['고가'] || 0),
                low: parseFloat(row['저가'] || 0),
                close: parseFloat(row['종가'] || 0),
                volume: parseFloat(row['거래량'] || 0),
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
                open: parseFloat(row['시가'] || 0),
                high: parseFloat(row['고가'] || 0),
                low: parseFloat(row['저가'] || 0),
                close: parseFloat(row['종가'] || 0),
                volume: parseFloat(row['거래량'] || 0),
              };
            });
        }
      } catch (error) {
        console.error('시장 지수 데이터 로드 오류:', error);
      }
      
      // 상태 업데이트
      setKospiIndexData(kospiIndexData);
      setKosdaqIndexData(kosdaqIndexData);
    } catch (error) {
      console.error('시장 지수 데이터 로드 오류:', error);
    }
  };

  return (
    <div className="flex-1 p-0 sm:p-2 md:p-4 overflow-auto w-full">
      {/* 메인 콘텐츠 영역 - 모바일 최적화 */}
      <div className="w-full max-w-[1280px] mx-auto">
        {/* 테이블 섹션 컨테이너 */}
        <div className="bg-white rounded-md shadow p-2 md:p-4 flex-1 flex flex-col overflow-hidden">
          {/* RS 순위 테이블 & 52주 신고/신저가 */}
          <div className="bg-white rounded-md shadow">
            <div className="p-2 md:p-4"> 
              <Suspense fallback={<div className="h-80 flex items-center justify-center">로딩 중...</div>}>
                {/* RS 순위 및 52주 신고/신저가 테이블 영역 */}
                <div className="flex flex-col gap-6">
                  
                  {/* RS 순위 테이블 섹션 */}
                  <div className="flex-1">
                    <div ref={rsHeaderRef} className="flex justify-between items-center mb-2">
                      <h2 className="text-sm md:text-base font-semibold text-gray-700">RS 순위</h2>
                      <div className="flex items-center space-x-2">
                        {/* 업데이트 날짜 표시 */}
                        {updateDate && (
                          <span className="text-gray-600 text-xs mr-2" style={{ fontSize: 'clamp(0.7rem, 0.7vw, 0.7rem)' }}>
                            updated 16:30 {updateDate}
                          </span>
                        )}
                        <TableCopyButton 
                          tableRef={rsTableRef} 
                          headerRef={rsHeaderRef} 
                          tableName="RS 순위 TOP 200" 
                          updateDateText={updateDate ? `updated 16:30 ${updateDate}` : undefined}
                        />
                      </div>
                    </div>
                    <div className="relative">
                      <div className="flex-1 overflow-x-auto scrollbar-thin scrollbar-thumb-gray-300 scrollbar-track-transparent" ref={rsTableRef}>
                        <table className="w-full bg-white border border-gray-200 table-fixed">
                          <thead>
                            <tr className="bg-gray-100">
                              {(() => {
                                // 표시할 헤더 순서 정의
                                const desiredOrder = ['종목코드', '종목명', '업종', 'RS', 'RS_1M', 'RS_2M', 'RS_3M', 'MTT', '시가총액'];
                                // '테마명' 제외하고 원하는 순서대로 정렬
                                const orderedHeaders = csvData.headers
                                  .filter(header => header !== '테마명')
                                  .sort((a, b) => desiredOrder.indexOf(a) - desiredOrder.indexOf(b));

                                return orderedHeaders.map((header, index) => (
                                  <th 
                                    key={header}
                                    className={`px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer border border-gray-200 text-xs
                                      ${header === '업종' ? 'text-center' : ''} // 업종 헤더 가운데 정렬
                                      ${
                                      // 모바일 화면에서 숨길 컬럼들
                                      (header === '업종' || header === 'RS_2M' || header === 'RS_3M' || header === '시가총액' || header === '종목코드') ? 'hidden md:table-cell' : 
                                      ''
                                    }`}
                                    style={{
                                      width: header === 'RS' || header === 'RS_1M' || header === 'RS_2M' || header === 'RS_3M' || header === 'MTT' ? '70px' :
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
                                      <span>{formatHeaderName(header)}</span>
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
                                  const desiredOrder = ['종목코드', '종목명', '업종', 'RS', 'RS_1M', 'RS_2M', 'RS_3M', 'MTT', '시가총액'];
                                  const orderedHeaders = csvData.headers
                                    .filter(header => header !== '테마명')
                                    .sort((a, b) => desiredOrder.indexOf(a) - desiredOrder.indexOf(b));

                                  return orderedHeaders.map((header, colIndex) => (
                                    <td 
                                      key={header}
                                      className={`py-1 px-1 sm:py-1.5 sm:px-2 border-b border-r ${getCellAlignment(header)} whitespace-nowrap overflow-hidden text-ellipsis text-xs
                                        ${
                                        // 모바일 화면에서 숨길 컬럼들
                                        (header === '업종' || header === 'RS_2M' || header === 'RS_3M' || header === '시가총액' || header === '종목코드') ? 'hidden md:table-cell' : 
                                        ''
                                      }`}
                                      style={{ 
                                        height: '35px', // 높이 적용
                                      }}
                                      title={header === '업종' ? row[header] : ''} // 업종 셀에 툴팁 추가
                                    >
                                      {formatCellValue(header, row[header])}
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
                  
                  {/* 52주 신고/신저가 테이블 섹션 */}
                  <div className="flex-1">
                    <div ref={highHeaderRef} className="flex justify-between items-center mb-2">
                      <h2 className="text-sm md:text-base font-semibold text-gray-700">52주 주요 종목</h2>
                      <div className="flex items-center space-x-2">
                        {/* 업데이트 날짜 표시 */}
                        {updateDate && (
                          <span className="text-gray-600 text-xs mr-2" style={{ fontSize: 'clamp(0.7rem, 0.7vw, 0.7rem)' }}>
                            updated 16:30 {updateDate}
                          </span>
                        )}
                        <TableCopyButton 
                          tableRef={highTableRef} 
                          headerRef={highHeaderRef} 
                          tableName="52주 신고/신저가"
                          updateDateText={updateDate ? `updated 16:30 ${updateDate}` : undefined}
                        />
                      </div>
                    </div>
                    <div className="relative">
                      <div className="flex-1 overflow-x-auto overflow-y-auto max-h-[630px] scrollbar-thin scrollbar-thumb-gray-300 scrollbar-track-transparent" ref={highTableRef}>
                        {/* 데이터 유무 확인 */}
                        {highData && highData.rows.length > 0 ? (
                          <table className="w-full bg-white border border-gray-200 table-fixed">
                            <thead>
                              <tr className="bg-gray-100">
                                <th 
                                  className="px-0.5 sm:px-1 md:px-2 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer border border-gray-200 text-center text-xs"
                                  style={{ width: '90px', height: '35px' }}
                                  onClick={() => handleHighSort('종목명')}
                                >
                                  <div className="flex items-center justify-center">
                                    <span>종목명</span>
                                    {highSortKey === '종목명' && (
                                      <span className="ml-1">
                                        {highSortDirection === 'asc' ? '↑' : '↓'}
                                      </span>
                                    )}
                                  </div>
                                </th>
                                <th 
                                  className="px-0.5 sm:px-1 md:px-2 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer border border-gray-200 text-center text-xs"
                                  style={{ width: '45px', height: '35px' }}
                                  onClick={() => handleHighSort('RS')}
                                >
                                  <div className="flex items-center justify-center">
                                    <span>RS</span>
                                    {highSortKey === 'RS' && (
                                      <span className="ml-1">
                                        {highSortDirection === 'asc' ? '↑' : '↓'}
                                      </span>
                                    )}
                                  </div>
                                </th>
                                <th 
                                  className="px-0.5 sm:px-1 md:px-2 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer border border-gray-200 text-center text-xs"
                                  style={{ width: '55px', height: '35px' }} // 너비 늘림 (예: 55px -> 60px)
                                  onClick={() => handleHighSort('등락률')}
                                >
                                  <div className="flex items-center justify-center">
                                    <span>등락률</span>
                                    {highSortKey === '등락률' && (
                                      <span className="ml-1">
                                        {highSortDirection === 'asc' ? '↑' : '↓'}
                                      </span>
                                    )}
                                  </div>
                                </th>
                                <th 
                                  className="px-0.5 sm:px-1 md:px-2 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer border border-gray-200 text-center text-xs"
                                  style={{ width: '60px', height: '35px' }}
                                  onClick={() => handleHighSort('시가총액')}
                                >
                                  <div className="flex items-center justify-center">
                                    <span>시가총액</span>
                                    {highSortKey === '시가총액' && (
                                      <span className="ml-1">
                                        {highSortDirection === 'asc' ? '↑' : '↓'}
                                      </span>
                                    )}
                                  </div>
                                </th>
                                <th 
                                  className="px-0.5 sm:px-1 md:px-2 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer border border-gray-200 text-center text-xs"
                                  style={{ width: '60px', height: '35px' }}
                                  onClick={() => handleHighSort('거래대금')}
                                >
                                  <div className="flex items-center justify-center">
                                    <span>거래대금</span>
                                    {highSortKey === '거래대금' && (
                                      <span className="ml-1">
                                        {highSortDirection === 'asc' ? '↑' : '↓'}
                                      </span>
                                    )}
                                  </div>
                                </th>
                              </tr>
                            </thead>
                            <tbody>
                              {/* .slice(0, 20) 제거 */}
                              {sortedHighData.map((row: any, rowIndex: number) => (
                                <tr key={rowIndex} className={rowIndex % 2 === 0 ? 'bg-gray-50' : 'bg-white'}>
                                  <td 
                                    className="py-1 sm:py-1.5 px-0.5 sm:px-1 md:px-2 border-b border-r text-left whitespace-nowrap overflow-hidden text-ellipsis text-xs" 
                                    style={{ height: '35px' }}
                                  >
                                    {row['종목명']}
                                  </td>
                                  <td 
                                    className="py-1 sm:py-1.5 px-0.5 sm:px-1 md:px-2 border-b border-r text-center whitespace-nowrap overflow-hidden text-ellipsis text-xs"
                                    style={{ height: '35px' }}
                                  >
                                    {row['RS']}
                                  </td>
                                  <td 
                                    className={`py-1 sm:py-1.5 px-0.5 sm:px-1 md:px-2 border-b border-r text-center whitespace-nowrap overflow-hidden text-ellipsis text-xs ${
                                      // 등락률 값에 따라 색상 클래스 적용
                                      (Number(row['등락률']) || 0) > 0 ? 'text-red-500' : (Number(row['등락률']) || 0) < 0 ? 'text-blue-500' : ''
                                    }`}
                                    style={{ height: '35px' }}
                                  >
                                    {/* RS 값을 숫자로 변환하고 toFixed 적용, 변환 실패 시 0으로 처리 */}
                                    {(Number(row['등락률']) > 0 ? '+' : '') + (Number(row['등락률']) || 0).toFixed(2)}%
                                  </td>
                                  <td 
                                    className="py-1 sm:py-1.5 px-0.5 sm:px-1 md:px-2 border-b border-r text-right whitespace-nowrap overflow-hidden text-ellipsis text-xs"
                                    style={{ height: '35px' }}
                                  >
                                    {/* CSV에서 직접 가져온 시가총액 값을 formatMarketCap 함수로 포맷팅하여 표시 */} 
                                    {formatMarketCap(row['시가총액'])}
                                  </td>
                                  <td 
                                    className="py-1 sm:py-1.5 px-0.5 sm:px-1 md:px-2 border-b border-r text-right whitespace-nowrap overflow-hidden text-ellipsis text-xs"
                                    style={{ height: '35px' }}
                                  >
                                    {/* 거래대금 값을 숫자로 변환하고 '억' 단위 추가, 변환 실패 시 0으로 처리 */}
                                    {(Number(row['거래대금']) || 0).toLocaleString()}억
                                  </td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        ) : (
                          <p className="text-gray-700 text-center py-4" style={{ fontSize: 'clamp(0.7rem, 0.8vw, 0.8rem)' }}>
                            52주 신고/신저가를 갱신한 주요 종목이 없습니다.<br />시장 환경이 좋지 않은 상태를 의미합니다.
                          </p>
                        )}
                      </div>
                    </div>
                  </div>
                  
                </div>
              </Suspense>
            </div>
          </div>
        </div>

        {/* 차트 섹션 컨테이너 - 별도의 영역으로 분리 */}
        <div className="bg-white rounded-md shadow p-2 md:p-4 flex-1 flex flex-col overflow-hidden">
          <div className="bg-white rounded-md shadow flex-1 flex flex-col overflow-hidden">
            {/* 하단 섹션: RS상위 시장 비교차트 */}
            <div>
              <div className="p-2 md:p-4">
                <Suspense fallback={<div className="h-80 flex items-center justify-center">로딩 중...</div>}>
                  <div className="mb-3">
                    <h2 className="text-sm md:text-base font-semibold">RS상위 시장 비교차트</h2>
                  </div>
                  <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                    {Array.from({length: 20}).map((_, index) => (
                      <div key={index} className="rounded-md">
                        {renderChartComponent(index)}
                      </div>
                    ))}
                  </div>
                </Suspense>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
