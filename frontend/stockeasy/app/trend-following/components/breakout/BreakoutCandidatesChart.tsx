'use client'

import { useState, useEffect } from 'react';
import Papa from 'papaparse';
import { format } from 'date-fns';
import ChartComponentDaily from '../../../components/ChartComponentDaily';

// 캔들 데이터 타입 정의
interface CandleData {
  time: any; // string에서 any로 변경하여 유연성 확보
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

// 차트 정보 타입 정의
interface ChartInfo {
  code: string;     // 종목코드
  name: string;     // 종목명
  market: string;   // 시장 (KOSPI, KOSDAQ)
  changeRate: string; // 등락률
  rsValue: string;    // RS 값
  data: CandleData[];  // ChartComponent에 맞게 data로 이름 변경
  isLoading: boolean;
  error: string;
  breakthroughPrice?: number; // 돌파 가격
}

export default function BreakoutCandidatesChart() {
  // 차트 정보 상태 관리
  const [chartInfos, setChartInfos] = useState<ChartInfo[]>([]);
  const [updateDate, setUpdateDate] = useState<string | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [kospiIndexData, setKospiIndexData] = useState<CandleData[]>([]);
  const [kosdaqIndexData, setKosdaqIndexData] = useState<CandleData[]>([]);

  useEffect(() => {
    // 페이지 로드 시 데이터 로드
    const loadAllData = async () => {
      setLoading(true);
      setError(null);
      
      try {
        // 1. 파일 목록 가져오기
        const fileListResponse = await fetch('/requestfile/breakoutchart/watchlist/file_list.json', { cache: 'no-store' });
        
        if (!fileListResponse.ok) {
          throw new Error(`파일 목록 로드 실패: ${fileListResponse.status}`);
        }
        
        const fileList = await fileListResponse.json();
        const chartFiles = fileList.files.filter((file: string) => file !== 'file_list.json');
        
        console.log('차트 파일 목록:', chartFiles);
        
        // 2. 시장 지수 데이터 로드
        await loadMarketIndexData();

        // 3. breakout.csv에서 돌파 가격 정보 로드
        const breakthroughPriceResponse = await fetch('/requestfile/trend-following/breakout.csv', { cache: 'no-store' });
        if (!breakthroughPriceResponse.ok) {
          throw new Error(`breakout.csv 로드 실패: ${breakthroughPriceResponse.status}`);
        }
        const breakthroughCsvText = await breakthroughPriceResponse.text();
        const breakthroughCsvData = Papa.parse(breakthroughCsvText, { header: true, skipEmptyLines: true });
        const breakthroughPriceMap: { [key: string]: number } = {};
        if (breakthroughCsvData.data) {
          breakthroughCsvData.data.forEach((row: any) => {
            if (row.Code && row['Breakthrough Price']) {
              const price = parseFloat(row['Breakthrough Price']);
              if (!isNaN(price)) { // NaN이 아닐 경우에만 맵에 추가
                breakthroughPriceMap[row.Code] = price;
              } else {
                console.warn(`[BreakoutCandidatesChart] 종목코드 ${row.Code}의 Breakthrough Price 값 '${row['Breakthrough Price']}'는 유효한 숫자가 아닙니다. 이 종목의 돌파 라인은 표시되지 않습니다.`);
              }
            }
          });
        }
        console.log('돌파 가격 맵:', breakthroughPriceMap);
        
        // 4. 차트 정보 배열 초기화
        const newChartInfos: ChartInfo[] = [];
        
        // 4. 각 파일별로 차트 데이터 로드
        for (let i = 0; i < chartFiles.length; i++) {
          const fileName = chartFiles[i];
          try {
            // 파일명에서 정보 추출 (예: "003230_삼양식품.csv")
            const parts = fileName.replace('.csv', '').split('_');
            const code = parts[0];
            const name = parts[1];
            let changeRate = '0.00';
            let rsValue = '-';
            let market = '';
            
            if (parts.length > 2) {
              changeRate = parts[2] || '0.00';
              rsValue = parts[3] || '-';
            }
            
            console.log(`로딩 차트 데이터: ${fileName}`);
            
            // 차트 데이터 로드
            const response = await fetch(`/requestfile/breakoutchart/watchlist/${fileName}`, { cache: 'no-store' });
            if (!response.ok) {
              throw new Error(`차트 데이터 로드 실패: ${response.status}`);
            }
            
            const csvText = await response.text();
            
            // CSV 파싱하여 데이터와 시장구분 가져오기
            const csvData = Papa.parse(csvText, { header: true, skipEmptyLines: true });
            
            // 시장구분 추출
            let marketValue = market || 'KOSPI';  // 기본값 사용 또는 파일명에서 추출한 값
            // 최신 등락률 추출 - CSV 파일에서 가져오기
            let latestChangeRate = changeRate; // 기본값으로 파일명에서 추출한 값 사용
            // RS 값 추출 - CSV 파일에서 가져오기
            let latestRsValue = rsValue; // 기본값으로 파일명에서 추출한 값 사용
            
            if (csvData.data && csvData.data.length > 0) {
              // 시장구분은 모든 행이 동일하므로 첫 번째 행에서 가져옴
              const firstRow = csvData.data[0] as any;
              if (firstRow["시장구분"]) {
                marketValue = firstRow["시장구분"];
                console.log(`추출된 시장구분 (${fileName}):`, marketValue);
              }
              
              // 등락률과 RS는 마지막 행(최신 데이터)에서 가져옴
              const lastRow = csvData.data[csvData.data.length - 1] as any;
              // 등락률 컬럼이 있다면 마지막 행의 값을 사용
              if (lastRow["등락률"]) {
                latestChangeRate = lastRow["등락률"];
                console.log(`추출된 등락률 (마지막 행, ${fileName}):`, latestChangeRate);
              }
              // RS 컬럼이 있다면 마지막 행의 값을 사용
              if (lastRow["RS"]) {
                latestRsValue = lastRow["RS"];
                console.log(`추출된 RS (마지막 행, ${fileName}):`, latestRsValue);
              }
            }
            
            // 차트 데이터 변환
            const chartData = await loadChartData(`/requestfile/breakoutchart/watchlist/${fileName}`);
            const breakthroughPrice = breakthroughPriceMap[code]; // breakthroughPrice 변수 선언 위치 수정
            
            newChartInfos.push({
              code,
              name,
              market: marketValue,  // CSV에서 추출한 시장구분 사용
              changeRate: latestChangeRate, // CSV에서 추출한 등락률 값 사용
              rsValue: latestRsValue, // CSV에서 추출한 RS 값 사용
              data: chartData,
              isLoading: false,
              error: '',
              breakthroughPrice: breakthroughPrice // 돌파 가격 추가
            });
          } catch (err) {
            console.error(`${fileName} 차트 데이터 로드 오류:`, err);
            newChartInfos.push({
              code: '',
              name: fileName.split('_')[1] || fileName,
              market: '',
              changeRate: '',
              rsValue: '',
              data: [],
              isLoading: false,
              error: `차트 데이터를 로드하는데 실패했습니다: ${err instanceof Error ? err.message : '알 수 없는 오류'}`
            });
          }
        }
        
        setChartInfos(newChartInfos);
        
        // 업데이트 날짜 설정
        await loadUpdateDate();
      } catch (err) {
        console.error('차트 데이터 로드 오류:', err);
        setError(`데이터를 로드하는데 실패했습니다: ${err instanceof Error ? err.message : '알 수 없는 오류'}`);
      } finally {
        setLoading(false);
      }
    };
    
    loadAllData();
  }, []);

  // 시장 지수 데이터 로드 함수
  const loadMarketIndexData = async () => {
    try {
      // KOSPI 지수 데이터 로드 (2개월 데이터 사용)
      const kospiResponse = await fetch('/requestfile/market-index/kospidaily2month.csv', { cache: 'no-store' });
      
      if (!kospiResponse.ok) {
        throw new Error(`KOSPI 지수 데이터 로드 실패: ${kospiResponse.status}`);
      }
      
      const kospiCsv = await kospiResponse.text();
      
      // CSV 파싱
      Papa.parse(kospiCsv, {
        header: false,
        skipEmptyLines: true,
        complete: (results) => {
          const data = results.data
            .filter((row: any) => row.length >= 8) // KOSPI 데이터는 8개 이상의 필드가 있어야 함
            .map((row: any) => {
              // 날짜 형식 변환 (20250516 -> 2025-05-16 형태로)
              const dateStr = String(row[3]).trim();
              const formattedDate = `${dateStr.substring(0, 4)}-${dateStr.substring(4, 6)}-${dateStr.substring(6, 8)}`;
              
              return {
                time: formattedDate,
                open: parseFloat(row[4]),
                high: parseFloat(row[5]),
                low: parseFloat(row[6]),
                close: parseFloat(row[7]),
                volume: parseFloat(row[8] || '0')
              };
            })
            .sort((a: CandleData, b: CandleData) => {
              return new Date(a.time).getTime() - new Date(b.time).getTime();
            });
          
          setKospiIndexData(data);
        },
        error: (err: any) => {
          console.error('KOSPI 지수 데이터 파싱 오류:', err);
          throw new Error(`KOSPI 지수 데이터 파싱 오류: ${err.message}`);
        }
      });
      
      // KOSDAQ 지수 데이터 로드 (2개월 데이터 사용)
      const kosdaqResponse = await fetch('/requestfile/market-index/kosdaqdaily2month.csv', { cache: 'no-store' });
      
      if (!kosdaqResponse.ok) {
        throw new Error(`KOSDAQ 지수 데이터 로드 실패: ${kosdaqResponse.status}`);
      }
      
      const kosdaqCsv = await kosdaqResponse.text();
      
      // CSV 파싱
      Papa.parse(kosdaqCsv, {
        header: false,
        skipEmptyLines: true,
        complete: (results) => {
          const data = results.data
            .filter((row: any) => row.length >= 8) // KOSDAQ 데이터는 8개 이상의 필드가 있어야 함
            .map((row: any) => {
              // 날짜 형식 변환 (20250516 -> 2025-05-16 형태로)
              const dateStr = String(row[3]).trim();
              const formattedDate = `${dateStr.substring(0, 4)}-${dateStr.substring(4, 6)}-${dateStr.substring(6, 8)}`;
              
              return {
                time: formattedDate,
                open: parseFloat(row[4]),
                high: parseFloat(row[5]),
                low: parseFloat(row[6]),
                close: parseFloat(row[7]),
                volume: parseFloat(row[8] || '0')
              };
            })
            .sort((a: CandleData, b: CandleData) => {
              return new Date(a.time).getTime() - new Date(b.time).getTime();
            });
          
          setKosdaqIndexData(data);
        },
        error: (err: any) => {
          console.error('KOSDAQ 지수 데이터 파싱 오류:', err);
          throw new Error(`KOSDAQ 지수 데이터 파싱 오류: ${err.message}`);
        }
      });
    } catch (err) {
      console.error('시장 지수 데이터 로드 오류:', err);
      throw err;
    }
  };

  // 차트 데이터 로드 함수
  const loadChartData = async (filePath: string): Promise<CandleData[]> => {
    const response = await fetch(filePath, { cache: 'no-store' });
    
    if (!response.ok) {
      throw new Error(`차트 데이터 로드 실패: ${response.status}`);
    }
    
    const csvText = await response.text();
    console.log('CSV 텍스트 처음 몇 줄:', csvText.split('\n').slice(0, 3));
    
    return new Promise<CandleData[]>((resolve, reject) => {
      Papa.parse(csvText, {
        header: true,
        skipEmptyLines: true,
        complete: (results) => {
          if (results.errors && results.errors.length > 0) {
            console.error('CSV 파싱 오류:', results.errors);
            reject(new Error(`CSV 파싱 오류: ${results.errors[0].message}`));
            return;
          }
          
          console.log('파싱된 데이터 첫 열:', results.data[0]);
          
          try {
            
            const data = results.data
              .filter((row: any) => row["날짜"] && row["시가"] && row["고가"] && row["저가"] && row["종가"])
              .map((row: any) => {
                // 날짜 형식 변환
                const dateStr = String(row["날짜"]).trim();
                
                return {
                  time: dateStr,
                  open: parseFloat(row["시가"]),
                  high: parseFloat(row["고가"]),
                  low: parseFloat(row["저가"]),
                  close: parseFloat(row["종가"]),
                  volume: parseFloat(row["거래량"] || '0')
                };
              })
              .sort((a: CandleData, b: CandleData) => {
                return new Date(a.time).getTime() - new Date(b.time).getTime();
              });
            
            resolve(data);
          } catch (err) {
            reject(err);
          }
        },
        error: (err: any) => {
          reject(err);
        }
      });
    });
  };

  // 업데이트 날짜 로드 함수
  const loadUpdateDate = async () => {
    try {
      // 파일 목록 가져오기 - watchlist 폴더에서 가져오기
      const fileListResponse = await fetch('/requestfile/breakoutchart/watchlist/file_list.json', { 
        cache: 'no-store',
        method: 'HEAD'
      });
      
      if (!fileListResponse.ok) {
        console.error(`파일 목록 로드 실패: ${fileListResponse.status}`);
        return;
      }
      
      // 응답 헤더에서 Last-Modified 값 추출
      const lastModified = fileListResponse.headers.get('Last-Modified');
      
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
        
        // M/DD HH:MM 형식으로 포맷팅
        const formattedDate = `${month}/${day.toString().padStart(2, '0')} ${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}`;
        setUpdateDate(formattedDate);
      }
    } catch (error) {
      console.error('업데이트 날짜 로드 오류:', error);
      // 오류 발생 시 현재 날짜/시간 사용
      const now = new Date();
      const month = now.getMonth() + 1;
      const day = now.getDate();
      const hours = now.getHours();
      const minutes = now.getMinutes();
      
      // M/DD HH:MM 형식으로 포맷팅
      const formattedDate = `${month}/${day.toString().padStart(2, '0')} ${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}`;
      setUpdateDate(formattedDate);
    }
  };

  if (loading) {
    return (
      <div className="p-4">
        <div className="flex justify-between items-center">
          <h3 className="text-lg font-semibold text-gray-700 my-2">
            돌파 후보 차트
          </h3>
        </div>
        <div className="flex items-center justify-center h-40">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-4">
        <div className="flex justify-between items-center">
          <h3 className="text-lg font-semibold text-gray-700 my-2">
            돌파 후보 차트
          </h3>
        </div>
        <div className="bg-red-50 border border-red-200 rounded p-4 text-red-600 text-sm">
          {error}
        </div>
      </div>
    );
  }

  // 2개씩 차트를 묶어서 표시
  const chunkArray = (array: ChartInfo[], size: number) => {
    const chunkedArr = [];
    for (let i = 0; i < array.length; i += size) {
      chunkedArr.push(array.slice(i, i + size));
    }
    return chunkedArr;
  };

  const chunkedCharts = chunkArray(chartInfos, 2);

  return (
    <div className="p-2">
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center mt-1 mb-3">
        <h3 className="text-lg font-semibold mb-1 sm:mb-0" style={{ color: 'var(--primary-text-color, var(--primary-text-color-fallback))' }}>
          돌파 후보 차트
        </h3>
        {updateDate && <span className="text-xs sm:mr-2" style={{ fontSize: 'clamp(0.7rem, 0.7vw, 0.7rem)', color: 'var(--primary-text-color, var(--primary-text-color-fallback))' }}>updated {updateDate}</span>}
      </div>
      
      {chunkedCharts.map((chartRow, rowIndex) => (
        <div key={`row-${rowIndex}`} className="flex flex-wrap -mx-2 mb-2">
          {chartRow.map((chartInfo, colIndex) => (
            <div key={`chart-${rowIndex}-${colIndex}`} className="w-full sm:w-1/2 px-2 mb-2">
              <div className="border border-gray-200 rounded-[6px] overflow-hidden shadow-sm">
                <div className="bg-gray-50 py-1 px-2 border-b">
                  <div className="flex flex-wrap items-center justify-between">
                    <div className="flex flex-wrap items-center">
                      <span className="font-medium" style={{ fontSize: 'calc(14px)', color: 'var(--primary-text-color, var(--primary-text-color-fallback))' }}>{chartInfo.name}</span>
                      <span className="ml-2 text-xs font-medium px-2 py-0.5 rounded bg-blue-100 text-blue-800" style={{ fontSize: 'calc(14px)' }}>
                        {chartInfo.market}
                      </span>
                      {chartInfo.changeRate && (
                        <span className={`ml-2 font-medium ${Number(chartInfo.changeRate) < 0 ? 'text-blue-600' : 'text-red-600'}`} style={{ fontSize: 'calc(14px)' }}>
                          {Number(chartInfo.changeRate) < 0 ? '' : '+'}{chartInfo.changeRate}%
                        </span>
                      )}
                    </div>
                    <div className="flex items-center mt-1 sm:mt-0">
                      <span className="mr-1" style={{ fontSize: 'calc(14px)', color: 'var(--primary-text-color, var(--primary-text-color-fallback))' }}>RS</span>
                      <span className="font-medium text-blue-600" style={{ fontSize: 'calc(14px)' }}>{chartInfo.rsValue}</span>
                    </div>
                  </div>
                </div>
                <div className="h-[260px] overflow-hidden">
                  {chartInfo.error ? (
                    <div className="flex items-center justify-center h-full bg-red-50 text-red-600 text-sm p-4">
                      {chartInfo.error}
                    </div>
                  ) : chartInfo.data.length === 0 ? (
                    <div className="flex items-center justify-center h-full bg-gray-50 text-sm" style={{ color: 'var(--primary-text-color, var(--primary-text-color-fallback))' }}>
                      데이터가 없습니다
                    </div>
                  ) : (
                    <ChartComponentDaily
                      data={chartInfo.data}
                      title=""
                      subtitle=""
                      height={260}
                      width="100%"
                      showVolume={true}
                      marketType={chartInfo.market}
                      stockName={chartInfo.name}
                      showMA20={false}
                      parentComponent="BreakoutCandidatesChart"
                      breakthroughPrice={chartInfo.breakthroughPrice}
                    />
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      ))}
    </div>
  );
}
