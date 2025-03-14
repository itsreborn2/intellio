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
  const [chartDataArray, setChartDataArray] = useState<CandleData[][]>(Array.from({length: 20}, () => []));
  const [chartLoadingArray, setChartLoadingArray] = useState<boolean[]>(Array.from({length: 20}, () => false));
  const [chartErrorArray, setChartErrorArray] = useState<string[]>(Array.from({length: 20}, () => '')); 
  const [chartMarketTypes, setChartMarketTypes] = useState<string[]>(Array.from({length: 20}, () => '')); // 빈 문자열로 초기화
  // 종목명을 저장할 상태 추가
  const [chartStockNames, setChartStockNames] = useState<string[]>(Array.from({length: 20}, () => ''));
  const [kospiIndexData, setKospiIndexData] = useState<CandleData[]>([]);
  const [kosdaqIndexData, setKosdaqIndexData] = useState<CandleData[]>([]);

  useEffect(() => {
    // 페이지 로드 시 데이터 로드
    const loadData = async () => {
      setLoading(true);
      setError(null);
      
      try {
        // 로컬 캐시 파일 경로
        const cacheFilePath = '/cache/stock-data/stock_1uyjvdmzfxarsxs0jy16fegfrqy9fs8yd.csv';
        
        // 로컬 캐시 파일 로드
        const response = await fetch(cacheFilePath);
        
        if (!response.ok) {
          throw new Error(`캐시 파일 로드 실패: ${response.status}`);
        }
        
        const csvText = await response.text();
        console.log(`RS 순위 데이터 로드 완료: ${csvText.length}자`);
        
        // CSV 파싱 및 데이터 처리
        const parsedData = parseCSV(csvText);
        console.log(`파싱 완료: ${parsedData.rows.length}개 데이터 로드됨`);
        
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
        // 캐시된 데이터 확인
        const cachedDataJSON = localStorage.getItem('stockEasyHighData');
        const cachedTimestamp = localStorage.getItem('stockEasyHighTimestamp');
        const cachedDate = localStorage.getItem('stockEasyHighDate');
        
        // 현재 시간 정보
        const now = new Date();
        const currentTime = now.getTime();
        const today = now.toISOString().split('T')[0]; // YYYY-MM-DD 형식
        
        // 캐시 유효성 확인 (오늘 이미 업데이트 되었거나, 아직 업데이트 시간이 아닌 경우)
        const isCacheValid = 
          cachedDataJSON !== null && 
          cachedTimestamp !== null && 
          cachedDate === today;
        
        // 캐시가 유효하면 캐시된 데이터 사용
        if (isCacheValid) {
          console.log('로컬 캐시에서 52주 신고가 데이터 로드 중...');
          const parsedData = JSON.parse(cachedDataJSON);
          setHighData(parsedData);
          setHighDataLoading(false);
          return;
        }
        
        // 캐시가 없거나 유효하지 않은 경우 로컬 캐시 파일에서 직접 로드
        console.log('캐시가 없거나 만료됨. 로컬 캐시 파일에서 52주 신고가 데이터 로드 중...');
        
        try {
          // 로컬 캐시 파일 경로
          const cacheFilePath = '/cache/stock-data/stock_1mbee4o9_nonpfiaexi4vin8qcn8bttxz.csv';
          const rsDataFilePath = '/cache/stock-data/stock_1uyjvdmzfxarsxs0jy16fegfrqy9fs8yd.csv';
          
          console.log('캐시 파일 경로:', cacheFilePath);
          console.log('RS 데이터 파일 경로:', rsDataFilePath);
          
          // 로컬 캐시 파일 로드
          const response = await fetch(cacheFilePath);
          
          if (!response.ok) {
            throw new Error(`캐시 파일 로드 실패: ${response.status}`);
          }
          
          const csvText = await response.text();
          console.log(`52주 신고가 데이터 로드 완료: ${csvText.length}자`);
          console.log('52주 신고가 데이터 샘플:', csvText.substring(0, 200));
          
          // RS 데이터 파일 로드
          const rsResponse = await fetch(rsDataFilePath);
          
          if (!rsResponse.ok) {
            console.error(`RS 데이터 파일 로드 실패: ${rsResponse.status} ${rsResponse.statusText}`);
            throw new Error(`RS 데이터 파일 로드 실패: ${response.status}`);
          }
          
          const rsCsvText = await rsResponse.text();
          console.log(`RS 데이터 로드 완료: ${rsCsvText.length}자`);
          console.log('RS 데이터 샘플:', rsCsvText.substring(0, 200));
          
          // CSV 파싱 및 데이터 처리
          const parsedData = parseCSV(csvText);
          const rsParsedData = parseCSV(rsCsvText);
          
          console.log(`파싱 완료: ${parsedData.rows.length}개 데이터 로드됨`);
          console.log(`RS 데이터 파싱 완료: ${rsParsedData.rows.length}개 데이터 로드됨`);
          console.log('파싱된 데이터 샘플:', JSON.stringify(parsedData.rows.slice(0, 2)));
          console.log('파싱된 RS 데이터 샘플:', JSON.stringify(rsParsedData.rows.slice(0, 2)));
          
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
          
          console.log('RS 데이터 맵 크기:', rsDataMap.size);
          console.log('RS 데이터 맵 샘플:', Array.from(rsDataMap.entries()).slice(0, 2));
          
          // 데이터 변환 - 컬럼명 매핑 (종목명 -> stockName, RS -> rs)
          const transformedData = {
            headers: parsedData.headers,
            rows: parsedData.rows.map(row => {
              // 종목명으로 RS 데이터 매핑
              const stockName = row['종목명'];
              console.log('처리 중인 종목명:', stockName);
              
              const rsData = rsDataMap.get(stockName) || { RS: '', 시가총액: '', 테마명: '' }; // 테마명 추가
              console.log('매핑된 RS 데이터:', rsData);
              
              return {
                stockName: stockName,
                rs: rsData.RS || row['거래대금'], // RS 데이터가 있으면 사용, 없으면 거래대금 사용
                시가총액: rsData.시가총액,
                테마명: rsData.테마명, // 테마명 추가
                ...row
              };
            }),
            errors: parsedData.errors
          };
          
          console.log('변환된 데이터 샘플:', JSON.stringify(transformedData.rows.slice(0, 2)));
          console.log('변환된 데이터 행 수:', transformedData.rows.length);
          
          // 데이터 캐시에 저장
          localStorage.setItem('stockEasyHighData', JSON.stringify(transformedData));
          localStorage.setItem('stockEasyHighTimestamp', String(new Date().getTime()));
          localStorage.setItem('stockEasyHighDate', new Date().toISOString().split('T')[0]); // 오늘 날짜 저장
          
          setHighData(transformedData);
        } catch (error) {
          console.error('로컬 캐시 파일 로드 실패:', error);
          throw new Error(`로컬 캐시 파일 로드 실패: ${error instanceof Error ? error.message : '알 수 없는 오류'}`);
        }
      } catch (err) {
        console.error('52주 신고가 데이터 로드 오류:', err);
        setHighDataError(`데이터를 로드하는데 실패했습니다: ${err instanceof Error ? err.message : '알 수 없는 오류'}`);
      } finally {
        setHighDataLoading(false);
      }
    };
    
    loadData();
    loadHighData();
  }, []);

  // 차트 데이터 로드 함수
  const loadAllChartData = async (rsData?: CSVData) => {
    try {
      console.log('차트 데이터 로드 시작...');
      
      // RS 랭크 데이터가 없으면 리턴
      if (!rsData || !rsData.rows || rsData.rows.length === 0) {
        console.log('RS 랭크 데이터가 없어 차트 데이터를 로드하지 않습니다.');
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
      
      // 차트 데이터 파일 경로 배열 (순서대로 매핑)
      const chartFilePaths = [
        '/cache/chart-data/1t2z88ntuzd2r3ct5oy8ic3ja09tqfaof.csv',
        '/cache/chart-data/1mhuyrpe378v1j2qmsx1sufmzkmokjv_4.csv',
        '/cache/chart-data/1wdrfq_8w9hwydadcfi7dgptwdmnxl3fk.csv',
        '/cache/chart-data/1wjdxsztimlfizel30weqzkkv4tiadhqg.csv',
        '/cache/chart-data/1zefwp0b0-8wzilvbmktyh_zyjg5cl0pw.csv',
        '/cache/chart-data/1cjeyuaoew_qler37nfiqlwgdmgeimnej.csv',
        '/cache/chart-data/12n6x15dkl1vjmzmk9ahobyiyat1unrse.csv',
        '/cache/chart-data/1i-bg0puf8rbmxekhs1toboqjxrjbwlco.csv',
        '/cache/chart-data/1apwisocpqh4r5336namsor_vdg6bbclg.csv',
        '/cache/chart-data/1st-nzj2wo3fptb6swk8glqcxyjqgx7-k.csv',
        '/cache/chart-data/1atorxqqrdjahkmginh-ajxogo7ptljpm.csv',
        '/cache/chart-data/1jctjmbiwgiihvzcppirxbnppe5gljctw.csv',
        '/cache/chart-data/11hgiohutm5yzbaguemzpxdtw4fv0wdmd.csv',
        '/cache/chart-data/1bxdtowr97lhxl8ymecl84qlbe09h6wwk.csv',
        '/cache/chart-data/1w0mug-pgv_jgsj44w3hmtfgaoq0npgos.csv',
        '/cache/chart-data/1178693zjykqgp-iesphmq8qcxgbspg0q.csv',
        '/cache/chart-data/15cqztbbinqf0f6rcir2d01bc_vc0attg.csv',
        '/cache/chart-data/1ene8lrq_9kqvootf_wil-dt9jxoqj0cd.csv',
        '/cache/chart-data/1iznpzmimg-yk2z20w2c9tjewlcdswww0.csv',
        '/cache/chart-data/1f2k3mrwuazufdx4mkl89pmg33dbfil8g.csv'
      ];
      
      // 시장 지수 데이터 파일 경로
      const kospiIndexPath = '/cache/market-index/market_1dzf65fz6elq6b5znvhuaftn10hqjbe_c.csv';
      const kosdaqIndexPath = '/cache/market-index/market_1ks9qkdzmsxv-qenv6udzzidfwgykc1qg.csv';
      
      // 시장 지수 데이터 로드
      let kospiIndexData: CandleData[] = [];
      let kosdaqIndexData: CandleData[] = [];
      
      try {
        // KOSPI 지수 데이터 로드
        const kospiResponse = await fetch(kospiIndexPath);
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
          
          console.log(`KOSPI 지수 데이터 로드 완료: ${kospiIndexData.length}개 항목`);
        }
        
        // KOSDAQ 지수 데이터 로드
        const kosdaqResponse = await fetch(kosdaqIndexPath);
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
          
          console.log(`KOSDAQ 지수 데이터 로드 완료: ${kosdaqIndexData.length}개 항목`);
        }
      } catch (error) {
        console.error('시장 지수 데이터 로드 실패:', error);
      }
      
      // 실제 데이터 로드 (최대 20개)
      const loadLimit = Math.min(20, top20Stocks.length);
      console.log(`로드할 차트 데이터 수: ${loadLimit}`);
      
      // 모든 차트 데이터를 로드하기 위한 Promise 배열 생성
      const loadPromises = [];
      
      // 각 차트 데이터 로드를 위한 Promise 생성
      for (let i = 0; i < loadLimit; i++) {
        // 임시로 종목 정보 저장 (나중에 CSV에서 가져온 정보로 덮어씌워짐)
        newStockNames[i] = top20Stocks[i]['종목명'] || `종목 ${i+1}`;
        // 종목코드로 차트 데이터 파일 경로 생성
        const stockCode = top20Stocks[i]['종목코드'] || '';
        console.log(`${i+1}번째 차트 데이터 요청 - 종목코드: ${stockCode}, 임시 종목명: ${newStockNames[i]}`);
        
        // 순서에 맞는 차트 데이터 파일 경로 사용
        const cacheFilePath = chartFilePaths[i];
        console.log(`차트 데이터 파일 경로: ${cacheFilePath}`);
        
        // 차트 데이터 로드 Promise 생성
        const loadPromise = (async (index) => {
          try {
            console.log(`${index+1}번째 차트 데이터 파일 로드 시작: ${chartFilePaths[index]}`);
            const response = await fetch(chartFilePaths[index]);
            
            if (!response.ok) {
              throw new Error(`캐시 파일 로드 실패: ${response.status}`);
            }
            
            const csvText = await response.text();
            console.log(`${index+1}번째 차트 데이터 CSV 응답 길이: ${csvText.length}`);
            
            if (csvText.length === 0) {
              throw new Error('CSV 응답이 비어 있습니다.');
            }
            
            // CSV 데이터 파싱
            const parsedData = Papa.parse(csvText, {
              header: true,
              skipEmptyLines: true,
              dynamicTyping: true,
            });
            
            // 파싱 결과 확인
            console.log(`${index+1}번째 차트 데이터 파싱 결과 - 행 수: ${parsedData.data.length}, 에러: ${parsedData.errors.length}`);
            
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
            
            // 데이터 유효성 검사 로그 추가
            console.log(`${index+1}번째 차트 데이터 변환 결과 - ${chartData.length}개 항목`);
            
            // 시장 구분 및 종목명 확인 - 타입 안전하게 처리
            if (parsedData.data.length > 0 && parsedData.data[0]) {
              const firstRow = parsedData.data[0] as Record<string, any>;
              
              // CSV 파일에서 종목명 가져오기
              if ('종목명' in firstRow) {
                const stockName = String(firstRow['종목명']);
                console.log(`${index+1}번째 차트 데이터의 종목명: ${stockName}`);
                // 종목명 정보 업데이트
                newStockNames[index] = stockName;
              } else {
                console.warn(`${index+1}번째 차트 데이터에 종목명 컬럼이 없습니다.`);
              }
              
              // CSV 파일에서 시장구분 가져오기
              if ('시장구분' in firstRow) {
                // 시장 구분 정보를 대문자로 정규화하여 저장
                const marketType = String(firstRow['시장구분']).toUpperCase();
                console.log(`${index+1}번째 차트 데이터의 시장 구분: ${marketType} (원본: ${firstRow['시장구분']})`);
                // 시장 구분 정보 업데이트
                newMarketTypes[index] = marketType;
              } else {
                console.warn(`${index+1}번째 차트 데이터에 시장구분 컬럼이 없습니다.`);
              }
            } else {
              console.warn(`${index+1}번째 차트 데이터가 비어있습니다.`);
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
      
      // 시장 지수 데이터 추가
      for (let i = 0; i < loadLimit; i++) {
        // 시장 구분 정보는 변경하지 않고 로그만 출력
        console.log(`${i+1}번째 차트(${newStockNames[i]})의 최종 시장 구분: ${newMarketTypes[i]}`);
        
        // 시장 구분에 따라 적절한 시장 지수 데이터 선택
        const marketIndexData = newMarketTypes[i] === 'KOSPI' ? kospiIndexData : kosdaqIndexData;
        console.log(`${i+1}번째 차트에 사용할 시장 지수 데이터: ${newMarketTypes[i]}, 데이터 수: ${marketIndexData.length}`);
      }
      
      // 상태 업데이트 (한 번에 모든 차트 데이터 업데이트)
      setChartDataArray(newChartDataArray);
      setChartStockNames(newStockNames);
      setChartMarketTypes(newMarketTypes);
      setChartLoadingArray(newChartLoadingArray);
      setChartErrorArray(newChartErrorArray);
      
      // 시장 지수 데이터 상태 업데이트
      setKospiIndexData(kospiIndexData);
      setKosdaqIndexData(kosdaqIndexData);
      
      console.log('모든 차트 데이터 로드 완료');
      console.log('차트 데이터 배열 상태:', newChartDataArray.map(data => data.length));
      
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
      const stockName = firstRow['종목명'] || `종목 ${index + 1}`;
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
  const formatMarketCap = (value: number | string | undefined): string => {
    if (value === undefined || value === null) return '0';
    
    // 숫자로 변환
    const numValue = typeof value === 'string' ? Number(value) : value;
    
    // 소수점 제거하고 천 단위 쉼표 추가
    return Math.floor(numValue).toLocaleString('ko-KR');
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
      const valueStr = typeof value === 'number' ? String(value) : value;
      const marketCapInBillions = Math.floor(Number(valueStr.replace(/,/g, '')) / 100000000);
      
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
    if (!highData || !highData.rows || !csvData || !csvData.rows) {
      console.log('데이터가 없습니다:', { 
        highData: highData ? `${highData.rows?.length}개 행` : '없음', 
        csvData: csvData ? `${csvData.rows?.length}개 행` : '없음' 
      });
      return [];
    }
    
    console.log('52주 신고가 데이터 행 수:', highData.rows.length);
    if (highData.rows.length > 0) {
      console.log('52주 신고가 데이터 첫 번째 행:', JSON.stringify(highData.rows[0]));
      console.log('52주 신고가 데이터 헤더:', highData.headers);
    }
    
    console.log('RS 데이터 행 수:', csvData.rows.length);
    if (csvData.rows.length > 0) {
      console.log('RS 데이터 첫 번째 행:', JSON.stringify(csvData.rows[0]));
      console.log('RS 데이터 헤더:', csvData.headers);
    }
    
    // 52주 신고가 데이터 전체를 사용하고 매칭 정보 생성
    const mappedData = highData.rows.map((highRow: any) => {
      // 종목명으로 RS 순위 데이터에서 매칭되는 항목 찾기
      const matchingRSRow = csvData.rows.find((rsRow: any) => 
        rsRow['종목명'] && highRow['종목명'] && 
        rsRow['종목명'].trim() === highRow['종목명'].trim()
      );
      
      console.log(`종목 "${highRow['종목명']}" 매칭 결과:`, matchingRSRow ? '매칭됨' : '매칭 안됨');
      
      // 매칭된 정보 합치기
      return {
        // 52주 신고가 데이터
        '종목명': highRow['종목명'],
        '종목코드': highRow['종목코드'],
        
        // RS 데이터 (숫자 형식으로 처리)
        'RS': matchingRSRow && matchingRSRow['RS'] ? Number(matchingRSRow['RS']) : 0,
        
        // 시가총액 (억 단위로 변환)
        '시가총액(억)': matchingRSRow ? Math.floor(Number(String(matchingRSRow['시가총액']).replace(/,/g, '')) / 100000000) : 0,
        
        // 거래대금 (억 단위로 변환)
        '거래대금(억)': highRow['거래대금'] ? Number(String(highRow['거래대금']).replace(/[^0-9.]/g, '')) : 0,
        
        // 테마명 추가
        '테마명': matchingRSRow && matchingRSRow['테마명'] ? matchingRSRow['테마명'] : '-',
        
        // 기타 정보
        '업종': matchingRSRow ? matchingRSRow['업종'] : '-'
      };
    });
    
    console.log('매핑된 데이터 행 수:', mappedData.length);
    if (mappedData.length > 0) {
      console.log('매핑된 데이터 첫 번째 행:', JSON.stringify(mappedData[0]));
    }
    
    // 거래대금이 0인 항목 제외 및 시가총액 2천억 이상인 종목만 필터링
    const filteredData = mappedData.filter((item) => {
      // 시가총액 필터링 - 2천억 이상만 포함 (필터링 조건 완화)
      const marketCap = Number(item['시가총액(억)'] || 0);
      return marketCap > 0; // 시가총액이 0보다 큰 종목만 포함
    });
    
    console.log('필터링된 데이터 행 수:', filteredData.length);
    
    // RS 값 기준으로 내림차순 정렬 (RS 값이 높은 순)
    return filteredData.sort((a, b) => {
      // 숫자로 변환하여 내림차순 정렬 (큰 값이 먼저 오도록)
      return Number(b['RS'] || 0) - Number(a['RS'] || 0);
    });
  }, [highData, csvData]);

  // 차트 컴포넌트 렌더링
  const renderChartComponent = (index: number) => {
    if (chartLoadingArray[index]) {
      return (
        <div className="h-80 flex items-center justify-center border border-dashed border-gray-300 rounded-md">
          <div className="flex flex-col items-center">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500 mb-2"></div>
            <span className="text-gray-500">차트 데이터 로딩 중...</span>
          </div>
        </div>
      );
    }

    if (chartErrorArray[index] && chartErrorArray[index].length > 0) {
      return (
        <div className="h-80 flex items-center justify-center border border-dashed border-gray-300 rounded-md">
          <span className="text-red-500">{chartErrorArray[index]}</span>
        </div>
      );
    }

    if (!chartDataArray[index] || chartDataArray[index].length === 0) {
      return (
        <div className="h-80 flex items-center justify-center border border-dashed border-gray-300 rounded-md">
          <span className="text-gray-400">표시할 차트 데이터가 없습니다.</span>
        </div>
      );
    }

    // 시장 구분에 따라 배경색 설정
    const marketType = chartMarketTypes[index];
    const isKospi = marketType === 'KOSPI';
    const bgColorClass = isKospi ? 'bg-blue-100 text-blue-800' : 'bg-green-100 text-green-800';

    return (
      <div className="h-80 border border-gray-200 rounded-md overflow-hidden">
        <div className="bg-gray-100 px-3 py-1 border-b border-gray-200 flex justify-between items-center">
          <div className="flex items-center">
            <span className="font-medium text-sm">{chartStockNames[index]}</span>
            <span className={`ml-2 text-xs px-1.5 py-0.5 rounded ${bgColorClass}`} data-component-name="RSRankPage">
              {marketType}
            </span>
          </div>
        </div>
        <ChartComponent 
          data={chartDataArray[index]} 
          marketType={marketType} 
          height={300}
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
                                       header === '시가총액' ? '85px' : 
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
                                          header === '시가총액' ? '85px' :
                                          header === '종목코드' ? '60px' : 
                                          header === 'RS' || header === 'RS 1W' || header === 'RS 4W' || header === 'RS 12W' || header === 'MMT' ? '45px' :
                                          header === 'RS_1M' || header === 'RS_2M' || header === 'RS_3M' ? '40px' :
                                          header === '업종' ? '220px' : '70px',
                                  fontSize: '0.875rem',
                                  maxWidth: header === '테마명' ? '220px' : 'auto',
                                  whiteSpace: 'nowrap',
                                  overflow: 'hidden',
                                  textOverflow: 'ellipsis'
                                }}
                                title={header === '테마명' ? row[header] : ''}
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
                    <div className="flex items-center justify-center h-full">
                      <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
                    </div>
                  ) : highDataError ? (
                    <div className="text-red-500">{highDataError}</div>
                  ) : (
                    (highData && highData.rows && highData.rows.length > 0) ? (
                      <div className="overflow-x-auto" style={{ overflowX: 'hidden' }}>
                        <table className="w-full bg-white border border-gray-200 table-fixed">
                          <thead>
                            <tr className="bg-gray-100">
                              <th 
                                className="py-2.5 px-3 border-b border-r text-center whitespace-nowrap cursor-pointer hover:bg-gray-200"
                                style={{ width: '100px', fontSize: '0.875rem' }}
                                onClick={() => requestSort('종목명')}
                              >
                                <div className="flex items-center justify-center">
                                  <span>종목명</span>
                                  {sortKey === '종목명' && (
                                    <span className="ml-1">
                                      {sortDirection === 'asc' ? '▲' : '▼'}
                                    </span>
                                  )}
                                </div>
                              </th>
                              <th 
                                className="py-2.5 px-3 border-b border-r text-center whitespace-nowrap cursor-pointer hover:bg-gray-200"
                                style={{ width: '45px', fontSize: '0.875rem' }}
                                onClick={() => requestSort('RS')}
                              >
                                <div className="flex items-center justify-center">
                                  <span>RS</span>
                                  {sortKey === 'RS' && (
                                    <span className="ml-1">
                                      {sortDirection === 'asc' ? '▲' : '▼'}
                                    </span>
                                  )}
                                </div>
                              </th>
                              <th 
                                className="py-2.5 px-3 border-b border-r text-center whitespace-nowrap cursor-pointer hover:bg-gray-200"
                                style={{ width: '85px', fontSize: '0.875rem' }}
                                onClick={() => requestSort('시가총액(억)')}
                              >
                                <div className="flex items-center justify-center">
                                  <span>시가총액(억)</span>
                                  {sortKey === '시가총액(억)' && (
                                    <span className="ml-1">
                                      {sortDirection === 'asc' ? '▲' : '▼'}
                                    </span>
                                  )}
                                </div>
                              </th>
                              <th 
                                className="py-2.5 px-3 border-b border-r text-center whitespace-nowrap cursor-pointer hover:bg-gray-200"
                                style={{ width: '75px', fontSize: '0.875rem' }}
                                onClick={() => requestSort('거래대금(억)')}
                              >
                                <div className="flex items-center justify-center">
                                  <span>거래대금(억)</span>
                                  {sortKey === '거래대금(억)' && (
                                    <span className="ml-1">
                                      {sortDirection === 'asc' ? '▲' : '▼'}
                                    </span>
                                  )}
                                </div>
                              </th>
                              <th 
                                className="py-2.5 px-3 border-b border-r text-center whitespace-nowrap cursor-pointer hover:bg-gray-200"
                                style={{ width: '120px', fontSize: '0.875rem' }}
                                onClick={() => requestSort('테마명')}
                              >
                                <div className="flex items-center justify-center">
                                  <span>테마명</span>
                                  {sortKey === '테마명' && (
                                    <span className="ml-1">
                                      {sortDirection === 'asc' ? '▲' : '▼'}
                                    </span>
                                  )}
                                </div>
                              </th>
                            </tr>
                          </thead>
                          <tbody>
                            {combinedHighData.slice(0, 20).map((row: any, rowIndex: number) => (
                              <tr key={rowIndex} className={rowIndex % 2 === 0 ? 'bg-gray-50' : 'bg-white'}>
                                <td 
                                  className="py-1.5 px-2 border-b border-r text-left whitespace-nowrap overflow-hidden text-ellipsis"
                                  style={{ width: '100px', fontSize: '0.875rem' }}
                                >
                                  {row['종목명']}
                                </td>
                                <td 
                                  className="py-1.5 px-2 border-b border-r text-center whitespace-nowrap overflow-hidden text-ellipsis"
                                  style={{ width: '45px', fontSize: '0.875rem' }}
                                >
                                  {row['RS']}
                                </td>
                                <td 
                                  className="py-1.5 px-2 border-b border-r text-right whitespace-nowrap overflow-hidden text-ellipsis"
                                  style={{ width: '85px', fontSize: '0.875rem' }}
                                >
                                  {formatMarketCap(row['시가총액(억)'])}
                                </td>
                                <td 
                                  className="py-1.5 px-2 border-b border-r text-right whitespace-nowrap overflow-hidden text-ellipsis"
                                  style={{ width: '75px', fontSize: '0.875rem' }}
                                >
                                  {formatMarketCap(row['거래대금(억)'])}
                                </td>
                                <td 
                                  className="py-1.5 px-2 border-b border-r text-left overflow-hidden text-ellipsis"
                                  style={{ 
                                    width: '120px', 
                                    fontSize: '0.875rem',
                                    maxWidth: '120px',
                                    whiteSpace: 'nowrap',
                                    overflow: 'hidden',
                                    textOverflow: 'ellipsis'
                                  }}
                                  title={row['테마명']}
                                >
                                  {row['테마명']}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    ) : (
                      <div className="text-gray-500">데이터가 없습니다.</div>
                    )
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
            {Array.from({length: 7}).map((_, rowIndex) => (
              <div key={rowIndex} className="flex flex-row gap-1 mb-4">
                {Array.from({length: 3}).map((_, colIndex) => {
                  const index = rowIndex * 3 + colIndex;
                  return (
                    <div key={colIndex} className="flex-1 rounded-md p-1">
                      {renderChartComponent(index)}
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
