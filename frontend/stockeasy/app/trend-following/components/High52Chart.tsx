'use client'

import { useState, useEffect } from 'react';
import Papa from 'papaparse';
import { format } from 'date-fns';
import ChartComponent from '../../components/ChartComponent';

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
}

export default function High52Chart() {
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
        const fileListResponse = await fetch('/requestfile/52wkhighchart/file_list.json', { cache: 'no-store' });
        
        if (!fileListResponse.ok) {
          throw new Error(`파일 목록 로드 실패: ${fileListResponse.status}`);
        }
        
        const fileList = await fileListResponse.json();
        const chartFiles = fileList.files.filter((file: string) => file !== 'file_list.json');
        
        console.log('차트 파일 목록:', chartFiles);
        
        // 2. 시장 지수 데이터 로드
        await loadMarketIndexData();
        
        // 3. 차트 정보 배열 초기화
        const newChartInfos: ChartInfo[] = [];
        
        // 4. 각 파일별로 차트 데이터 로드
        for (let i = 0; i < chartFiles.length; i++) {
          const fileName = chartFiles[i];
          try {
            // 파일명에서 정보 추출 (예: "003230_삼양식품_KOSPI_19.07_97.csv")
            const parts = fileName.replace('.csv', '').split('_');
            const code = parts[0];
            const name = parts[1];
            const market = parts[2];
            const changeRate = parts[3];
            const rsValue = parts[4];
            
            console.log(`로딩 차트 데이터: ${fileName}`);
            
            // 차트 데이터 로드
            const chartData = await loadChartData(`/requestfile/52wkhighchart/${fileName}`);
            
            newChartInfos.push({
              code,
              name,
              market,
              changeRate,
              rsValue,
              data: chartData, // ChartComponent에 맞게 data로 이름 변경
              isLoading: false,
              error: ''
            });
          } catch (err) {
            console.error(`${fileName} 차트 데이터 로드 오류:`, err);
            newChartInfos.push({
              code: '',
              name: fileName.split('_')[1] || fileName,
              market: '',
              changeRate: '',
              rsValue: '',
              data: [], // ChartComponent에 맞게 data로 이름 변경
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
      // KOSPI 주간 데이터 로드
      const kospiResponse = await fetch('/requestfile/market-index/kospiwk.csv', { cache: 'no-store' });
      if (!kospiResponse.ok) {
        throw new Error(`KOSPI 데이터 로드 실패: ${kospiResponse.status}`);
      }
      const kospiCsvText = await kospiResponse.text();
      
      // Papa.parse 직접 사용
      const kospiParsedData = Papa.parse(kospiCsvText, {
        header: true,
        skipEmptyLines: true,
        dynamicTyping: true,
      });
      
      // 데이터 형식 변환 (CandleData)
      const kospiFormattedData = kospiParsedData.data
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
            // 다른 형식이면 그대로 사용
            formattedTime = timeStr;
          }
          
          return {
            time: formattedTime,
            open: Number(row['시가']),
            high: Number(row['고가']),
            low: Number(row['저가']),
            close: Number(row['종가']),
            volume: Number(row['거래량'] || 0)
          };
        })
        .sort((a: any, b: any) => new Date(a.time).getTime() - new Date(b.time).getTime());
        
      setKospiIndexData(kospiFormattedData);

      // KOSDAQ 주간 데이터 로드 (동일한 방식 적용)
      const kosdaqResponse = await fetch('/requestfile/market-index/kosdaqwk.csv', { cache: 'no-store' });
      if (!kosdaqResponse.ok) {
        throw new Error(`KOSDAQ 데이터 로드 실패: ${kosdaqResponse.status}`);
      }
      const kosdaqCsvText = await kosdaqResponse.text();
      
      // Papa.parse 직접 사용
      const kosdaqParsedData = Papa.parse(kosdaqCsvText, {
        header: true,
        skipEmptyLines: true,
        dynamicTyping: true,
      });
      
      // 데이터 형식 변환 (CandleData)
      const kosdaqFormattedData = kosdaqParsedData.data
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
            // 다른 형식이면 그대로 사용
            formattedTime = timeStr;
          }
          
          return {
            time: formattedTime,
            open: Number(row['시가']),
            high: Number(row['고가']),
            low: Number(row['저가']),
            close: Number(row['종가']),
            volume: Number(row['거래량'] || 0)
          };
        })
        .sort((a: any, b: any) => new Date(a.time).getTime() - new Date(b.time).getTime());
        
      setKosdaqIndexData(kosdaqFormattedData);
      
      console.log('시장 지수 데이터 로드 완료', {
        kospi: kospiFormattedData.length,
        kosdaq: kosdaqFormattedData.length
      });
    } catch (err) {
      console.error('시장 지수 데이터 로드 오류:', err);
    }
  };
  
  // 차트 데이터 로드 함수
  const loadChartData = async (filePath: string): Promise<CandleData[]> => {
    console.log(`차트 데이터 로드 시작: ${filePath}`);
    const response = await fetch(filePath, { cache: 'no-store' });
    
    if (!response.ok) {
      console.error(`차트 데이터 로드 실패 (${response.status}): ${filePath}`);
      throw new Error(`차트 데이터 로드 실패 (${response.status}): ${filePath}`);
    }
    
    const csvText = await response.text();
    console.log(`차트 데이터 텍스트 로드 완료: ${filePath}`);
    
    // Papa.parse 직접 사용
    const parsedData = Papa.parse(csvText, {
      header: true,
      skipEmptyLines: true,
      dynamicTyping: true,
    });
    
    console.log(`차트 데이터 파싱 완료: ${filePath}`, { rowCount: parsedData.data.length });
    
    // CSV 데이터를 CandleData 형식으로 변환
    const formattedData = parsedData.data
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
          // 다른 형식이면 그대로 사용
          try {
            formattedTime = format(new Date(timeStr), 'yyyy-MM-dd');
          } catch (e) {
            console.error(`날짜 변환 오류: ${timeStr}`, e);
            formattedTime = timeStr;
          }
        }
        
        return {
          time: formattedTime,
          open: Number(row['시가']),
          high: Number(row['고가']),
          low: Number(row['저가']),
          close: Number(row['종가']),
          volume: Number(row['거래량'] || 0)
        };
      })
      .sort((a: any, b: any) => new Date(a.time).getTime() - new Date(b.time).getTime());
      
    console.log(`차트 데이터 변환 완료: ${filePath}`, { formattedRowCount: formattedData.length });
    return formattedData;
  };
  
  // 업데이트 날짜 로드 함수
  const loadUpdateDate = async () => {
    try {
      // 파일 목록 JSON에서 마지막 수정 날짜 가져오기
      const response = await fetch('/requestfile/52wkhighchart/file_list.json', { cache: 'no-store' });
      
      if (!response.ok) {
        throw new Error(`파일 목록 로드 실패: ${response.status}`);
      }
      
      // 응답 헤더에서 Last-Modified 값 추출
      const lastModified = response.headers.get('Last-Modified');
      
      if (lastModified) {
        // Last-Modified 헤더에서 날짜와 시간 추출하여 포맷팅
        const modifiedDate = new Date(lastModified);
        const month = modifiedDate.getMonth() + 1;
        const day = modifiedDate.getDate();
        const hours = modifiedDate.getHours();
        const minutes = modifiedDate.getMinutes();
        
        // M/DD HH:MM 형식으로 포맷팅 (rs-rank/page.tsx와 동일한 형식)
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

  if (loading) {
    return (
      <div className="p-4">
        <div className="flex justify-between items-center">
          <h3 className="text-lg font-semibold my-2" style={{ color: 'var(--primary-text-color, var(--primary-text-color-fallback))' }}>
            52주 신고가 차트 {updateDate && <span className="text-xs ml-2" style={{ color: 'var(--text-muted-color, var(--text-muted-color-fallback))' }}>(업데이트: {updateDate})</span>}
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
          <h3 className="text-lg font-semibold my-2" style={{ color: 'var(--primary-text-color, var(--primary-text-color-fallback))' }}>
            52주 신고가 차트
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
          52주 신고가 차트
        </h3>
        {updateDate && <span className="text-xs sm:mr-2" style={{ fontSize: 'clamp(0.7rem, 0.7vw, 0.7rem)', color: 'var(--text-muted-color, var(--text-muted-color-fallback))' }}>updated {updateDate}</span>}
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
                      <span className="ml-2 text-xs font-medium px-2 py-0.5 rounded bg-blue-100" style={{ fontSize: 'calc(14px)', color: 'var(--blue-600, #2563eb)' }}>
                        {chartInfo.market}
                      </span>
                      <span className="ml-2 font-medium" style={{ fontSize: 'calc(14px)', color: 'var(--red-500, #ef4444)' }}>
                        +{chartInfo.changeRate}%
                      </span>
                    </div>
                    <div className="flex items-center mt-1 sm:mt-0">
                      <span className="mr-1" style={{ fontSize: 'calc(14px)', color: 'var(--text-muted-color, var(--text-muted-color-fallback))' }}>RS</span>
                      <span className="font-medium" style={{ fontSize: 'calc(14px)', color: 'var(--blue-500, #3b82f6)' }}>{chartInfo.rsValue}</span>
                    </div>
                  </div>
                </div>
                <div className="h-[260px] overflow-hidden">
                  {chartInfo.error ? (
                    <div className="flex items-center justify-center h-full bg-red-50 text-red-600 text-sm p-4">
                      {chartInfo.error}
                    </div>
                  ) : chartInfo.data.length === 0 ? (
                    <div className="flex items-center justify-center h-full bg-gray-50 text-gray-500 text-sm">
                      데이터가 없습니다
                    </div>
                  ) : (
                    <ChartComponent
                      data={chartInfo.data}
                      title=""
                      subtitle=""
                      height={260}
                      width="100%"
                      showVolume={false}
                      marketType={chartInfo.market}
                      stockName={chartInfo.name}
                      showMA20={false}
                      parentComponent="High52Chart"
                      kospiIndexData={kospiIndexData}
                      kosdaqIndexData={kosdaqIndexData}
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
