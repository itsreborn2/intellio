'use client'

import { useState, useEffect } from 'react';
import Papa from 'papaparse';
import ChartComponent from './ChartComponent'; // ChartComponent 경로 확인 필요

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

// 20malist.csv 행 데이터 타입 (CSV 헤더와 일치하도록 수정)
interface MaListItem {
  종목코드: string; // stockCode -> 종목코드
  종목명: string;   // stockName -> 종목명
  섹터: string;    // 섹터 정보 추가
  포지션: string;   // position -> 포지션
  등락률: string;   // 등락률 추가
  // 필요한 다른 컬럼들... (CSV에 있다면 추가)
}

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

  useEffect(() => {
    const loadAndFilterData = async () => {
      setIsLoadingInitial(true);
      setInitialError(null);
      setStockChartData([]); // 이전 데이터 초기화

      try {
        // 1. 20malist.csv 파일 로드
        const maListResponse = await fetch('/requestfile/20ma_list/20malist.csv');
        if (!maListResponse.ok) {
          throw new Error('20malist.csv 파일을 찾을 수 없습니다.');
        }
        const maListCsvText = await maListResponse.text();

        // 2. CSV 파싱 및 필터링
        const parsedMaList = Papa.parse<MaListItem>(maListCsvText, {
          header: true,
          skipEmptyLines: true,
        });

        if (parsedMaList.errors.length > 0) {
          throw new Error('CSV 파싱 오류 발생');
        }

        // 원본 CSV 데이터를 메모리에 저장 (포지션 정보 접근 위함)
        const allMaListData = parsedMaList.data;
        const maListMap = new Map(allMaListData.map(item => [item.종목코드, item]));

        // 2. '유지 +숫자일' 조건으로 필터링
        const positionRegex = /^유지\s*\+\d+일$/;
        const filteredStocks = allMaListData
          .filter(row => 
            row.포지션 && 
            positionRegex.test(row.포지션.trim()) && 
            row.종목코드 && 
            row.종목코드.trim() !== ''
          )
          // 등락률 기준으로 내림차순 정렬 추가
          .sort((a, b) => {
            // 등락률 문자열에서 '%' 제거하고 숫자로 변환
            const changeA = parseFloat(a.등락률.replace('%', ''));
            const changeB = parseFloat(b.등락률.replace('%', ''));
            // 숫자가 아닌 경우 0으로 처리 (오류 방지)
            return (isNaN(changeB) ? 0 : changeB) - (isNaN(changeA) ? 0 : changeA);
          });

        if (filteredStocks.length === 0) {
          console.log("'유지' 키워드를 포함하고 유효한 등락률을 가진 종목이 없습니다."); // 로그 메시지 변경
          setStockChartData([]); // 데이터 없으면 빈 배열로 초기화
          setIsLoadingInitial(false);
          return; // 필터링된 데이터 없으면 여기서 종료
        }

        // 3. 필터링된 종목 기반으로 초기 ChartInfo 생성 (포지션 정보 포함)
        // 종목코드는 항상 6자리로 맞춰서 ChartInfo에 저장
        const initialChartInfo: ChartInfo[] = filteredStocks.map(stock => ({
          code: stock.종목코드.padStart(6, '0'),
          name: stock.종목명,
          sector: stock.섹터 || 'N/A',
          position: stock.포지션 || 'N/A', // 포지션 값 추가
          chartData: [],
          isLoading: true,
          error: null,
          // 등락률 추가 (타입 변환 및 오류 처리)
          changePercent: parseFloat(stock.등락률) || 0, 
          // isAboveMA20은 position 기반으로 임시 설정 (배경색 위함)
          isAboveMA20: stock.포지션?.startsWith('유지'),
        }));
        setStockChartData(initialChartInfo);
        setIsLoadingInitial(false); // 초기 데이터 로딩 및 필터링 완료

        // 4. 각 종목의 상세 차트 데이터 비동기 로드
        const chartDataPromises = filteredStocks.map(async (stock) => {
          try {
            // 타임스탬프 추가하여 캐시 문제 방지
            const chartResponse = await fetch(`/requestfile/rs_etf/${stock.종목코드.padStart(6, '0')}.csv?t=${Date.now()}`); 
            if (!chartResponse.ok) {
              // 404 에러 등 명시적으로 처리
              throw new Error(`(${chartResponse.status}) ${stock.종목코드}.csv 파일을 찾을 수 없거나 로드할 수 없습니다.`);
            }
            const chartCsvText = await chartResponse.text();
            const chartData = parseChartData(chartCsvText);

            // MA20 계산 및 최신 상태 판단 추가
            let isAboveMA20Calculated: boolean | undefined = undefined;
            if (chartData && chartData.length >= 20) {
              const ma20Values = calculateMA(chartData, 20);
              const lastIndex = chartData.length - 1;
              const lastClose = chartData[lastIndex]?.close;
              const lastMA20 = ma20Values[lastIndex];
              // 마지막 종가와 MA20 값이 모두 유효한 숫자인 경우에만 비교
              if (typeof lastClose === 'number' && !isNaN(lastClose) && 
                  typeof lastMA20 === 'number' && !isNaN(lastMA20)) {
                isAboveMA20Calculated = lastClose >= lastMA20;
              }
            }
            
            return { 
              code: stock.종목코드.padStart(6, '0'), // 항상 6자리로 반환
              chartData, 
              error: null, 
              // 계산된 isAboveMA20 상태 추가
              isAboveMA20: isAboveMA20Calculated 
            }; 
          } catch (error) {
            console.error(`차트 데이터 로드 오류 (${stock.종목코드}):`, error);
            // 개별 차트 로드 실패 시 에러 상태 반환
            return { 
              code: stock.종목코드.padStart(6, '0'), 
              chartData: [], 
              error: error instanceof Error ? error.message : '차트 데이터 로드 실패',
              // 오류 시 상태는 undefined로 유지
              isAboveMA20: undefined 
            };
          }
        });

        // 모든 차트 데이터 로드 완료 후 상태 업데이트
        const results = await Promise.allSettled(chartDataPromises);

        setStockChartData(prevData => 
          prevData.map(prevInfo => {
            const result = results.find(r => r.status === 'fulfilled' && r.value.code === prevInfo.code);
            if (result && result.status === 'fulfilled') {
              const { chartData, error, isAboveMA20 } = result.value;
              const updatedInfo = {
                ...prevInfo,
                chartData: chartData,
                isLoading: false,
                error: error,
                // CSV position 값은 유지, 계산된 isAboveMA20 업데이트
                isAboveMA20: isAboveMA20 
              };
              return updatedInfo;
            } else {
              // 실패한 경우 또는 해당 코드를 찾지 못한 경우 처리
              const failedResult = results.find(r => r.status === 'rejected' || (r.status === 'fulfilled' && r.value.code === prevInfo.code));
              let errorMessage = '차트 데이터 처리 중 오류 발생';
              if (failedResult) {
                if (failedResult.status === 'rejected') {
                  errorMessage = failedResult.reason instanceof Error ? failedResult.reason.message : String(failedResult.reason);
                } else if (failedResult.status === 'fulfilled' && failedResult.value.error) {
                  errorMessage = failedResult.value.error;
                }
              }
              const updatedInfo = {
                ...prevInfo,
                chartData: [],
                isLoading: false,
                error: errorMessage,
                // 오류 시 isAboveMA20은 undefined로 설정
                isAboveMA20: undefined 
              };
              return updatedInfo;
            }
          })
        );

      } catch (error) {
        console.error('초기 데이터 로드 또는 필터링 오류:', error);
        setStockChartData([]); // 오류 발생 시 데이터 초기화
        setInitialError(error instanceof Error ? error.message : '데이터 로드 중 오류 발생');
      } finally {
        setIsLoadingInitial(false);
      }
    };

    loadAndFilterData();
  }, []); // 컴포넌트 마운트 시 1회 실행

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
    // 3열 그리드 및 gap 적용 (sm, md 브레이크포인트 포함)
    // -> `div`로 감싸고 제목/설명 추가
    <div>
      {/* 차트 제목 및 설명 추가 (백업에서 복원) */}
      <div className="mb-4">
        <h2 className="font-semibold whitespace-nowrap text-sm md:text-base">산업별 주도ETF 차트</h2>
        <p className="text-gray-600 mr-2 hidden sm:inline text-[11px] md:text-xs"> 
          산업별 ETF의 20일 이동평균선 위에 위치한 ETF종목들만 표시합니다.
        </p>
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
                {/* 헤더 (원본 클래스, 인라인 스타일, 배경색 함수 적용) */}
                <div 
                  className={`px-3 py-1 border flex justify-between items-baseline ${getHeaderBackgroundColor(info)}`}
                  style={{ borderRadius: '0.375rem 0.375rem 0 0' }} 
                >
                  {/* 헤더 왼쪽: 섹터, 종목명, 등락률 */}
                  {/* gap-2 -> gap-1 으로 수정하여 간격 줄임 */}
                  <div className="flex items-baseline gap-1">
                    <div className="flex items-baseline gap-1">
                      {/* 한 줄에 섹터, 종목명, 등락률 모두 표시 (줄바꿈 방지) */}
                      <div style={{ display: 'flex', alignItems: 'baseline', gap: '4px', minWidth: 0, width: '100%' }}>
                        {/* 섹터 */}
                        {info.sector && (
                          <span
                            className="px-1.5 py-0.5 rounded bg-blue-100 text-blue-800 mr-1"
                            style={{
                              fontSize: 'clamp(0.6rem, 0.7vw, 0.7rem)',
                              whiteSpace: 'nowrap',
                              overflow: 'hidden',
                              textOverflow: 'ellipsis',
                              maxWidth: '70px',
                              display: 'inline-block',
                              verticalAlign: 'bottom',
                            }}
                            title={info.sector}
                          >
                            {info.sector}
                          </span>
                        )}
                        {/* ETF 제목: 줄바꿈 방지, ... 처리, 글자 작게 */}
                        <span
                          className="font-medium"
                          style={{
                            fontSize: 'clamp(0.6rem, 0.7vw, 0.7rem)',
                            whiteSpace: 'nowrap',
                            overflow: 'hidden',
                            textOverflow: 'ellipsis',
                            maxWidth: '120px',
                            display: 'inline-block',
                            verticalAlign: 'bottom',
                          }}
                          title={info.name || info.code}
                        >
                          {info.name || info.code}
                        </span>
                        {/* 등락률 */}
                        <span
                          className={`px-1.5 py-0.5 rounded ${(info.changePercent || 0) >= 0 ? 'text-red-600' : 'text-blue-600'}`}
                          style={{ fontSize: 'clamp(0.65rem, 0.75vw, 0.75rem)' }}
                        >
                          {(info.changePercent || 0) >= 0 ? '+' : ''}{(info.changePercent || 0).toFixed(2)}%
                        </span>
                      </div>
                    </div>
                    {/* 헤더 오른쪽: 상태 텍스트 */}
                    <div className="flex items-baseline gap-1">
                      {info.isLoading ? (
                        <span className="text-xs px-1.5 py-0.5 rounded bg-gray-100 text-gray-800">
                          로딩 중...
                        </span>
                      ) : (
                        // 상태 텍스트 -> info.position 값 직접 사용
                        <span 
                          // 배경색/텍스트색은 getHeaderBackgroundColor와 별개로 position 기반 적용
                          className={`px-1.5 py-0.5 rounded ${info.position?.startsWith('유지') ? 'bg-[#D8EFE9] text-teal-800' : 'bg-gray-100 text-gray-800'}`}
                          style={{ fontSize: 'clamp(0.65rem, 0.75vw, 0.75rem)' }}
                        >
                          {/* '유지 ' 또는 '이탈 ' 제거하고 일수만 표시 */}
                          {info.position?.replace(/^(유지|이탈)\s*/, '') || 'N/A'}
                        </span>
                      )}
                    </div>
                  </div>
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
                      // subtitle에 포지션 값과 등락률 포함 ('유지'/'이탈' 제거)
                      subtitle={`${info.position?.replace(/^(유지|이탈)\s*/, '') || 'N/A'} | 등락률: ${(info.changePercent || 0) >= 0 ? '+' : ''}${(info.changePercent || 0).toFixed(2)}%`} 
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
