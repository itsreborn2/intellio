'use client'

import { useState, useEffect, useRef } from 'react';
import Papa from 'papaparse';
import ChartComponent from './ChartComponent'; // ChartComponent 경로 확인 필요
import { ChartCopyButton } from './ChartCopyButton';
import { GuideTooltip } from 'intellio-common/components/ui/GuideTooltip'; // GuideTooltip 추가
import { formatDateMMDD } from '../utils/dateUtils'; // formatDateMMDD import 추가

// 차트 데이터 타입 정의
interface CandleData {
  time: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

// 표시할 각 차트 정보 타입 정의
interface ChartInfo {
  code: string;
  name?: string; // 종목명 (선택적)
  sector?: string; // 섹터 정보 추가
  position?: string; // CSV '포지션' 컬럼 값
  chartData: CandleData[];
  isLoading: boolean;
  error: string | null;
  // 원본 상태 표시 위한 속성 추가 (기본값 설정)
  isAboveMA20?: boolean; 
  durationDays?: number; 
  changePercent?: number;
}

// etf_table.csv 행 데이터 타입 (CSV 헤더와 일치하도록 수정)
interface EtfTableRow {
  산업: string;
  섹터: string;
  '산업 등락률': string;
  종목코드: string;
  종목명: string;
  등락률: string;
  포지션: string;
  '20일 이격': string;
  '돌파/이탈': string;
  '대표종목(RS)': string;
} // etf_table.csv 헤더 기준

// CSV 차트 데이터 행 타입 (파싱 시 사용)
interface CsvChartRow {
  날짜: string;
  시가: string;
  고가: string;
  저가: string;
  종가: string;
  거래량: string; // 'Volume' 또는 실제 CSV 헤더에 맞게 수정
}

// 유효한 차트 데이터인지 확인하는 함수
function isValidChartRow(row: any): row is CsvChartRow {
  return row &&
         typeof row.날짜 === 'string' && row.날짜.trim() !== '' &&
         typeof row.시가 === 'string' && !isNaN(parseFloat(row.시가)) &&
         typeof row.고가 === 'string' && !isNaN(parseFloat(row.고가)) &&
         typeof row.저가 === 'string' && !isNaN(parseFloat(row.저가)) &&
         typeof row.종가 === 'string' && !isNaN(parseFloat(row.종가)) &&
         typeof row.거래량 === 'string' && !isNaN(parseFloat(row.거래량));
}

// CSV 텍스트를 CandleData 배열로 파싱하는 함수
const parseChartData = (csvText: string): CandleData[] => {
  const parsed = Papa.parse<CsvChartRow>(csvText, {
    header: true,
    skipEmptyLines: true,
  });

  return parsed.data
    .filter(isValidChartRow) // 유효한 데이터만 필터링
    .map(row => ({
      time: row.날짜.replace(/(\d{4})(\d{2})(\d{2})/, '$1-$2-$3'), // YYYYMMDD -> YYYY-MM-DD 형식으로 변환 가정
      open: parseFloat(row.시가),
      high: parseFloat(row.고가),
      low: parseFloat(row.저가),
      close: parseFloat(row.종가),
      volume: parseFloat(row.거래량),
    }))
     // 시간 순서대로 정렬 (오름차순: 과거 -> 현재)
    .sort((a, b) => new Date(a.time).getTime() - new Date(b.time).getTime());
};

// 헤더 배경색 결정 함수 (백업에서 복원, info.position 기반으로 수정)
const getHeaderBackgroundColor = (info: ChartInfo): string => {
  // 로딩 중, 오류 시 기본 회색
  if (info.isLoading || info.error) {
    return 'bg-gray-50'; 
  }
  // position 값에 '유지' 포함 시 연녹색, 아니면 회색
  return info.position?.startsWith('유지') ? 'bg-[#EEF8F5]' : 'bg-gray-50'; 
};

/**
 * 단순 이동 평균(SMA)을 계산하는 함수
 * @param data 캔들 데이터 배열 (종가 'close' 포함 가정)
 * @param period 이동 평균 기간 (예: 20)
 * @returns 이동 평균값 배열 (계산 불가능한 초기값은 null)
 */
const calculateMA = (data: CandleData[], period: number): (number | null)[] => {
  if (!data || data.length < period) {
    // 데이터가 부족하면 모든 기간에 대해 null 반환
    return Array(data?.length || 0).fill(null);
  }

  const movingAverages: (number | null)[] = [];
  // 초기 period-1 개는 계산 불가하므로 null 추가
  for (let i = 0; i < period - 1; i++) {
    movingAverages.push(null);
  }

  // 나머지 기간에 대해 이동 평균 계산
  for (let i = period - 1; i < data.length; i++) {
    let sum = 0;
    let validDataPoints = 0;
    for (let j = 0; j < period; j++) {
       // data[i-j] 및 data[i-j].close 접근 유효성 및 타입 확인
       const closePrice = data[i-j]?.close;
       if (typeof closePrice === 'number' && !isNaN(closePrice)) {
           sum += closePrice;
           validDataPoints++;
       }
    }
    // 유효한 데이터 포인트가 period 개수만큼 있을 때만 계산
    if (validDataPoints === period) {
        movingAverages.push(sum / period);
    } else {
        movingAverages.push(null); // 유효하지 않으면 null
    }
  }

  return movingAverages;
};

// 산업 차트 컴포넌트
export default function IndustryCharts() {
  const [stockChartData, setStockChartData] = useState<ChartInfo[]>([]);
  const [isLoadingInitial, setIsLoadingInitial] = useState<boolean>(true); // 초기 필터링 및 로딩 상태
  const [initialError, setInitialError] = useState<string | null>(null); // 초기 데이터 로드 에러
  // 캡처(복사) 중 여부 상태
  const [isCapturing, setIsCapturing] = useState(false);
  // 차트 전체 컨테이너 ref (제목+차트 전체 캡처용)
  const chartsContainerRef = useRef<HTMLDivElement>(null);
  // updated 날짜 (예시: 오늘 날짜)
  const [updateDate, setUpdateDate] = useState<string | null>(null); // 타입을 string | null로 변경
  
  // 업데이트 날짜를 로드하는 함수 추가
  const loadUpdateDate = async () => {
    try {
      // 파일 경로 정의 - ETFCurrentTable과 동일한 파일 참조
      const cacheFilePath = '/requestfile/etf_sector/etf_table.csv?t=' + Date.now();
      
      // 파일 정보와 내용 가져오기
      const response = await fetch(cacheFilePath, { cache: 'no-store' });
      if (!response.ok) {
        throw new Error(`파일 로드 실패: ${response.status}`);
      }
      
      // 헤더에서 last-modified 날짜 가져오기
      const lastModified = response.headers.get('last-modified');
      const modifiedDate = lastModified ? new Date(lastModified) : null;
      
      // CSV 텍스트 파싱
      const csvText = await response.text();
      const parsedResult = Papa.parse(csvText, {
        header: true,
        skipEmptyLines: true,
      });

      // 날짜 및 시간 포맷팅
      if (modifiedDate && !isNaN(modifiedDate.getTime())) {
        // 마지막 수정 날짜/시간이 유효하면 사용
        const month = String(modifiedDate.getMonth() + 1);
        const day = String(modifiedDate.getDate()).padStart(2, '0');
        const hours = String(modifiedDate.getHours()).padStart(2, '0');
        const minutes = String(modifiedDate.getMinutes()).padStart(2, '0');
        
        // M/DD HH:MM 형식으로 설정
        setUpdateDate(`${month}/${day} ${hours}:${minutes}`);
      } else if (parsedResult.data && parsedResult.data.length > 0) {
        // 마지막 수정 날짜를 가져올 수 없으면 CSV의 첫 번째 행의 날짜 사용
        const firstRow = parsedResult.data[0] as Record<string, string>; 
        const dateString = firstRow['날짜']; 
        if (dateString) {
          const date = new Date(dateString);
          if (!isNaN(date.getTime())) {
            const month = String(date.getMonth() + 1);
            const day = String(date.getDate()).padStart(2, '0');
            // 현재 시간 사용 (파일 날짜만 있고 시간이 없는 경우)
            const now = new Date();
            const hours = String(now.getHours()).padStart(2, '0');
            const minutes = String(now.getMinutes()).padStart(2, '0');
            
            setUpdateDate(`${month}/${day} ${hours}:${minutes}`);
          } else {
            console.error('IndustryCharts: 날짜 파싱 실패:', dateString);
            setFallbackDate();
          }
        } else {
          console.error('IndustryCharts: CSV 파일에 "날짜" 컬럼이 없거나 비어있습니다.');
          setFallbackDate();
        }
      } else {
        console.error('IndustryCharts: 날짜 CSV 파싱에 실패했거나 데이터가 없습니다.');
        setFallbackDate();
      }
    } catch (err) {
      console.error('IndustryCharts: 업데이트 날짜 로드 중 오류 발생:', err);
      setFallbackDate();
    }
  };
  
  // 폴백 날짜 설정 함수 (오류 발생 시 현재 날짜/시간 사용)
  const setFallbackDate = () => {
    const now = new Date();
    const month = String(now.getMonth() + 1);
    const day = String(now.getDate()).padStart(2, '0');
    const hours = String(now.getHours()).padStart(2, '0');
    const minutes = String(now.getMinutes()).padStart(2, '0');
    setUpdateDate(`${month}/${day} ${hours}:${minutes}`);
  };

  useEffect(() => {
    const loadFileListAndData = async () => {
      setIsLoadingInitial(true);
      setInitialError(null);
      setStockChartData([]);

      try {
        const listRes = await fetch('/requestfile/etf_industry/file_list.json');
        if (!listRes.ok) throw new Error('file_list.json 파일을 찾을 수 없습니다.');
        const { files }: { files: string[] } = await listRes.json();

        // 파일명에서 코드, 종목명, 등락률, 섹터, 유지일 추출
        const initialInfos: ChartInfo[] = files.map(filename => {
          const [code, name, changeStr, sector, durationStr] = filename.split('_');
          const durationDays = parseInt(durationStr.replace('.csv', ''), 10);
          const changePercent = parseFloat(changeStr);
          return {
            code,
            name,
            sector,
            chartData: [],
            isLoading: true,
            error: null,
            changePercent,
            durationDays,
            position: `유지 ${durationDays}일` // 유지일을 position 속성에 할당
          };
        });
        setStockChartData(initialInfos);

        // 각 CSV 파일 로드
        const dataPromises = files.map(async filename => {
          try {
            const res = await fetch(`/requestfile/etf_industry/${filename}?t=${Date.now()}`);
            if (!res.ok) throw new Error(`${filename} 로드 실패`);
            const text = await res.text();
            const data = parseChartData(text);
            return { filename, data };
          } catch (e) {
            console.error(e);
            return { filename, data: [] as CandleData[] };
          }
        });
        const results = await Promise.all(dataPromises);

        setStockChartData(prev =>
          prev.map(info => {
            const match = results.find(r => r.filename.startsWith(`${info.code}_`));
            return match
              ? { ...info, chartData: match.data, isLoading: false }
              : info;
          })
        );
      } catch (e: any) {
        setInitialError(e.message || '데이터 로드 중 오류 발생');
      } finally {
        setIsLoadingInitial(false);
      }
    };
    loadFileListAndData();
    loadUpdateDate(); // 업데이트 날짜 로드 함수 호출
  }, []);

  // 로딩 및 에러 상태 표시
  if (isLoadingInitial) {
    return <div className="p-4 text-center">필터링 및 초기 데이터 로딩 중...</div>;
  }

  if (initialError) {
    return <div className="p-4 text-center text-red-600">오류: {initialError}</div>;
  }

  if (stockChartData.length === 0) {
    return <div className="p-4 text-center">표시할 차트 데이터가 없습니다. ('position' 컬럼에 '유지' 포함 확인)</div>; // 안내 메시지 변경
  }

  // 차트 렌더링 (원본 디자인 완전 복제)
  return (
    // 제목+복사버튼+updated 영역과 전체 차트 그리드를 하나의 ref로 감쌈
    <div ref={chartsContainerRef}>
      {/* 제목+복사버튼+updated 영역 */}
      {/* 제목+updated+복사버튼만 flex-row, 설명은 아래에 분리 */}
      {/* 제목(좌) / updated+복사버튼(우)로 분리, flex justify-between */}
      <div className="mb-2 flex flex-row items-center justify-between w-full"> {/* mb-1 -> mb-2 */}
        {/* 제목 영역을 GuideTooltip으로 감쌈 */}
        <GuideTooltip
          title="산업별 주도 ETF 차트"
          description={`각 산업을 대표하는 ETF 중 20일 이동평균선 위에 위치한 종목만을 선별하여 보여줍니다. 이를 통해 현재 상승 추세에 있는 주도 산업 및 ETF를 쉽게 파악할 수 있습니다.\n\n*차트 헤더 안내:*\n차트 제목 우측의 숫자는 해당 ETF가 *20일 이동평균선 위에서 연속으로 머무른 기간(일수)*을 나타냅니다.\n(이 차트에는 20일선 아래 종목은 표시되지 않습니다.)\n유지 기간(숫자)이 길수록 해당 ETF의 상승 추세가 견조함을 의미할 수 있습니다.`}
          side="bottom" // 제목 아래에 표시되도록 side 조정
          width="min(90vw, 450px)" // 너비 조정 (내용이 길어서 조금 늘림)
          collisionPadding={{ top: 10, left: 260, right: 10, bottom: 10 }} // 왼쪽 여백 260px 추가
        >
          {/* 기존 h2 태그를 Tooltip의 자식으로 이동하고 스타일 추가 */}
          <h2 className="font-semibold whitespace-nowrap text-sm md:text-base cursor-help"> 
            산업별 주도ETF 차트
          </h2>
        </GuideTooltip>

        <div className="flex flex-row items-center ml-auto">
          {/* updated: 평소에는 버튼 왼쪽, 캡처 중에는 오른쪽 끝 */}
          {!isCapturing && updateDate && (
            <div
              className="text-gray-600 text-xs mr-2 js-remove-for-capture"
              style={{ fontSize: 'clamp(0.7rem, 0.7vw, 0.7rem)' }}
            >
              updated {updateDate}
            </div>
          )}
          {/* 모바일에서 숨기기 위한 div 추가 */}
          <div className="hidden"> {/* md:block 클래스 제거, hidden만 남김 */}
            <ChartCopyButton
              chartRef={chartsContainerRef}
              chartName="산업별 주도ETF 차트 전체"
              onStartCapture={() => setIsCapturing(true)}
              onEndCapture={() => setIsCapturing(false)}
              updateDateText={updateDate || ''} // updateDate가 null이면 빈 문자열 전달
            />
          </div>
          {isCapturing && updateDate && (
            <div
              className="text-gray-600 text-xs ml-2 js-remove-for-capture"
              style={{ fontSize: 'clamp(0.7rem, 0.7vw, 0.7rem)' }}
            >
              updated {updateDate}
            </div>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-2 md:gap-4">
        {[...stockChartData] // 복사본 사용
          // 데이터 로딩 완료된 항목만 필터링 및 정렬
          .filter(info => !info.isLoading && info.changePercent !== undefined)
          .sort((a, b) => (b.changePercent || 0) - (a.changePercent || 0))
          .map((info, index) => ( // key를 index 대신 info.code 사용 고려
            // 개별 차트 아이템 래퍼 (둥근 모서리, 패딩)
            <div key={info.code} className="flex-1 rounded-md p-1"> 
              <div> {/* 내부 래퍼 */} 
                {/* 헤더 - 반응형 레이아웃으로 개선 */}
                <div 
                  className={`px-3 py-1 border flex justify-between items-center flex-wrap ${getHeaderBackgroundColor(info)}`}
                  style={{ borderRadius: '0.375rem 0.375rem 0 0' }} 
                >
                  {/* 헤더 왼쪽: 섹터, 종목명, 등락률 - 구조 단순화 및 반응형 개선 */}
                  <div className="flex items-center flex-1 min-w-0 overflow-hidden mr-2">
                    {/* 섹터 */}
                    {info.sector && (
                      <span
                        className="px-1.5 py-0.5 rounded bg-blue-100 text-blue-800 mr-1 shrink"
                        style={{
                          fontSize: 'clamp(0.65rem, 0.75vw, 0.75rem)', // 수정된 부분
                          whiteSpace: 'nowrap',
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          minWidth: '40px',
                          maxWidth: '120px',
                          display: 'inline-block',
                          verticalAlign: 'middle',
                          textAlign: 'center',
                          width: 'auto',
                        }}
                        title={info.sector}
                      >
                        {info.sector}
                      </span>
                    )}
                    
                    {/* 종목명 */}
                    <span
                      className="font-medium shrink mr-1"
                      style={{
                        fontSize: 'clamp(0.65rem, 0.75vw, 0.75rem)', // 수정된 부분
                        whiteSpace: 'nowrap',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        minWidth: '60px',
                        maxWidth: '200px',
                        display: 'inline-block',
                        verticalAlign: 'middle',
                      }}
                      title={info.name || info.code}
                    >
                      {info.name || info.code}
                    </span>
                    
                    {/* 등락률 - shrink-0으로 항상 필요한 너비 유지 */}
                    <span
                      className={`px-1.5 py-0.5 rounded shrink-0 ${(info.changePercent || 0) >= 0 ? 'text-red-600' : 'text-blue-600'}`}
                      style={{ fontSize: 'clamp(0.65rem, 0.75vw, 0.75rem)' }}
                    >
                      {(info.changePercent || 0) >= 0 ? '+' : ''}{(info.changePercent || 0).toFixed(2)}%
                    </span>
                  </div>
                  
                  {/* 헤더 오른쪽: 상태 텍스트 - shrink-0으로 항상 필요한 너비만 유지 */}
                  {info.isLoading ? (
                    <span className="px-1.5 py-0.5 rounded bg-gray-100 text-gray-800 shrink-0" 
                          style={{ fontSize: 'clamp(0.65rem, 0.75vw, 0.75rem)' }}>
                      로딩 중...
                    </span>
                  ) : (
                    <span 
                      className={`px-1.5 py-0.5 rounded shrink-0 ${info.durationDays ? 'bg-[#D8EFE9] text-teal-800' : 'bg-gray-100 text-gray-800'}`}
                      style={{ fontSize: 'clamp(0.65rem, 0.75vw, 0.75rem)' }}
                    >
                      {info.durationDays ? `${info.durationDays > 0 ? '+' : ''}${info.durationDays}일` : 'N/A'}
                    </span>
                  )}
                </div>
                
                {/* 차트 컴포넌트 컨테이너 (원본 클래스, 인라인 스타일) */}
                <div 
                  className="border border-t-0 border-gray-200" 
                  style={{ borderRadius: '0 0 0.375rem 0.375rem', overflow: 'hidden' }}
                >
                  {/* ChartComponent (원본 props 적용) */} 
                  {info.isLoading ? (
                    <div className="text-center py-10 text-gray-500 text-xs h-[300px] flex items-center justify-center">차트 로딩 중...</div>
                  ) : info.error ? (
                    <div className="text-center py-10 text-red-500 text-xs h-[300px] flex items-center justify-center">오류: {info.error}</div>
                  ) : info.chartData.length > 0 ? (
                    <ChartComponent 
                      data={info.chartData} 
                      height={300} 
                      width="100%" 
                      showVolume={true} 
                      showMA20={true} 
                      title={`${info.name} (${info.code})`} 
                      // subtitle에 유지일과 등락률 포함
                      subtitle={`${info.durationDays ? `${info.durationDays}일` : 'N/A'} | 등락률: ${(info.changePercent || 0) >= 0 ? '+' : ''}${(info.changePercent || 0).toFixed(2)}%`} 
                      parentComponent="IndustryCharts"
                    />
                  ) : (
                    <div className="text-center py-10 text-gray-500 text-xs h-[300px] flex items-center justify-center">차트 데이터 없음</div>
                  )}
                </div>
              </div>
            </div>
          ))}
      </div>
    </div>
  );
}
