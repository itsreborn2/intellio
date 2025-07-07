// frontend/stockeasy/app/trend-following/components/SectorLeaderSection.tsx
'use client';

import React, { useEffect, useState, useRef } from 'react';
import Papa from 'papaparse';
import { CheckCircleIcon } from '@heroicons/react/24/solid';

// 신호등 색상 값 정의
const signalColorValues = {
  red: '#ef4444', // Tailwind red-500
  yellow: '#fde047', // Tailwind yellow-400
  green: '#22c55e', // Tailwind green-500
  inactive: '#e5e7eb', // Tailwind gray-200
};

// 단일 신호등 컴포넌트 (하나의 신호만 표시)
function SingleSignalLight({ signal }: { signal: string | null }) {
  // 신호에 따른 색상 결정
  let backgroundColor = signalColorValues.inactive;
  let borderColor = signalColorValues.inactive + '80';
  let shadowColor = 'rgba(229,231,235,0.5)';
  
  switch (signal?.toLowerCase()) {
    case 'red':
      backgroundColor = signalColorValues.red;
      borderColor = signalColorValues.red + '80';
      shadowColor = 'rgba(239,68,68,0.6)';
      break;
    case 'yellow':
      backgroundColor = signalColorValues.yellow;
      borderColor = signalColorValues.yellow + '80';
      shadowColor = 'rgba(253,224,71,0.5)';
      break;
    case 'green':
      backgroundColor = signalColorValues.green;
      borderColor = signalColorValues.green + '80';
      shadowColor = 'rgba(34,197,94,0.5)';
      break;
  }

  return (
    <span
      className="rounded-full border-2 inline-block mx-0.5 w-4 h-4"
      style={{
        backgroundColor, 
        borderColor,
        boxShadow: `0 0 6px 1px ${shadowColor}`
      }}
    />
  );
}

interface SectorData {
  산업: string;
  섹터: string;
  ETF명: string;
  ETF등락률: string;
  종목코드: string;
  종목명: string;
  등락률: string;
  신호등: string; // 신호등 컬럼 추가
  시가총액: string;
  거래대금: string;
  포지션: string;
  RS: string;
  RS_1M: string;
  MTT: string;
  // 문자열 키로 액세스할 수 있도록 인덱스 시그니처 추가
  [key: string]: string;
}

interface GroupedSectorData {
  [key: string]: SectorData[];
}

// CSV 파싱 결과 인터페이스 추가
interface CSVParseResult {
  headers: string[];
  rows: any[];
  errors: any[];
}

// 숫자 포맷팅 함수
function formatNumberWithCommas(value: string | number | null | undefined): string {
  if (value === null || value === undefined || String(value).trim() === '') {
    return ''; // 빈 문자열이나 null/undefined는 그대로 반환하거나 'N/A' 등으로 처리
  }
  // 숫자 외 문자 제거 (콤마 등)
  const numStr = String(value).replace(/[^0-9.-]+/g, '');
  const num = Number(numStr);
  if (isNaN(num)) {
    return String(value); // 숫자로 변환할 수 없으면 원본 문자열 반환
  }
  return num.toLocaleString('ko-KR');
}

export default function SectorLeaderSection() {
  const [data, setData] = useState<GroupedSectorData>({});
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [updateDate, setUpdateDate] = useState<string>('');

  const tableContainerRef = useRef<HTMLDivElement>(null);
  const headerContainerRef = useRef<HTMLDivElement>(null);

  // CSV 파싱 함수 (High52Section과 동일)
  function parseCSV(csvText: string): CSVParseResult {
    if (!csvText || typeof csvText !== 'string') {
      return { headers: [], rows: [], errors: [] };
    }
    const results = Papa.parse(csvText, {
      header: true,
      skipEmptyLines: true,
      dynamicTyping: false,
    });
    return {
      headers: results.meta.fields || [],
      rows: results.data || [],
      errors: results.errors || [],
    };
  }

  useEffect(() => {
    async function fetchData() {
      setLoading(true);
      try {
        const response = await fetch('/requestfile/trend-following/trend-following-sector.csv', { cache: 'no-store' });
        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`);
        }
        const csvText = await response.text();
        
        Papa.parse<SectorData>(csvText, {
          header: true,
          skipEmptyLines: true,
          complete: (results) => {
            if (results.errors.length > 0) {
              console.error('CSV 파싱 오류:', results.errors);
              setError('CSV 파일을 파싱하는 중 오류가 발생했습니다.');
              setLoading(false);
              return;
            }
            const sortedData = results.data.sort((a, b) => {
              return parseFloat(b["ETF등락률"]) - parseFloat(a["ETF등락률"]);
            });
            
            const grouped: GroupedSectorData = {};
            sortedData.forEach(row => {
              const sector = row["섹터"];
              if (!grouped[sector]) {
                grouped[sector] = [];
              }
              grouped[sector].push(row);
            });
            setData(grouped);

            // 업데이트 시간 설정 로직
            let updatedTimeSet = false;
            if (results.data.length > 0 && results.data[0].저장시간) {
              const firstRowWithTime = results.data[0] as SectorData;
              const match = firstRowWithTime.저장시간.match(/(\d{2}\/\d{2}\s\d{2}:\d{2})/);
              if (match && match[1]) {
                setUpdateDate(match[1]);
                updatedTimeSet = true;
              }
            }

            if (!updatedTimeSet) {
              const lastModifiedHeader = response.headers.get('Last-Modified');
              if (lastModifiedHeader) {
                const date = new Date(lastModifiedHeader);
                const month = date.getMonth() + 1;
                const day = date.getDate();
                const hours = date.getHours();
                const minutes = date.getMinutes();
                setUpdateDate(`${month}/${day.toString().padStart(2, '0')} ${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}`);
                updatedTimeSet = true;
              } else {
                // CSV 저장시간도 없고, Last-Modified 헤더도 없는 경우 현재 시간 사용
                const now = new Date();
                const month = now.getMonth() + 1;
                const day = now.getDate();
                const hours = now.getHours();
                const minutes = now.getMinutes();
                const formattedDate = `${month}/${day.toString().padStart(2, '0')} ${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}`;
                setUpdateDate(formattedDate);
                console.warn('trend-following-sector.csv 파일의 저장시간 및 Last-Modified 헤더를 찾을 수 없어 현재 시간을 사용합니다.');
                updatedTimeSet = true;
              }
            }
            setLoading(false);
          },
          error: (err: Error) => {
            console.error('CSV 파싱 중 에러 발생: ', err);
            setError('CSV 파일을 파싱하는 중 오류가 발생했습니다.');
            setUpdateDate('');
            setLoading(false);
          }
        });
      } catch (e: any) {
        console.error('데이터 패칭 중 에러 발생: ', e);
        setError('데이터를 가져오는 중 오류가 발생했습니다.');
        setData({});
        setUpdateDate('');
        setLoading(false);
      }
    }

    fetchData();
  }, []);

  // loading, error, data 상태에 따른 UI 렌더링은 여기부터 시작됩니다.
  if (loading) {
    return <div className="p-4 text-center">데이터를 불러오는 중입니다...</div>;
  }

  if (error) {
    return <div className="p-4 text-center text-red-500">오류: {error}</div>;
  }

  if (Object.keys(data).length === 0) {
    return <div className="p-4 text-center">표시할 데이터가 없습니다.</div>;
  }

  return (
    <section className="bg-white rounded border border-gray-100 px-2 md:px-4 py-2 md:py-3">
      <div ref={headerContainerRef} className="flex justify-between items-center mb-3">
        <h2 className="text-base md:text-lg font-semibold" style={{ color: 'var(--primary-text-color, var(--primary-text-color-fallback))' }}>
          주도 섹터 및 주도주 현황
        </h2>
        <div className="flex items-center space-x-2">
          {updateDate && (
            <span className="text-xs mr-2 js-remove-for-capture" style={{ fontSize: 'clamp(0.7rem, 0.7vw, 0.7rem)', color: 'var(--text-muted-color, var(--text-muted-color-fallback))' }}>
              updated {updateDate}
            </span>
          )}
        </div>
      </div>

      <div ref={tableContainerRef} className="overflow-x-auto rounded-[6px]">
        <table className="min-w-full text-sm border border-gray-200 rounded-[6px]">
          <thead className="bg-gray-100">
            <tr>
              <th className="text-xs sm:text-sm px-2 py-1 md:px-3 md:py-2 border-b font-medium text-left w-[80px]" style={{ color: 'var(--text-muted-color, var(--text-muted-color-fallback))' }}>섹터</th>
              <th className="text-xs sm:text-sm px-2 py-1 md:px-3 md:py-2 border-b font-medium text-left w-[100px]" style={{ color: 'var(--text-muted-color, var(--text-muted-color-fallback))' }}>종목명</th>
              <th className="text-xs sm:text-sm px-2 py-1 md:px-3 md:py-2 border-b font-medium text-right w-[60px]" style={{ color: 'var(--text-muted-color, var(--text-muted-color-fallback))' }}>등락률</th>
              <th className="text-xs sm:text-sm px-2 py-1 md:px-3 md:py-2 border-b font-medium text-right w-[80px] hidden md:table-cell" style={{ color: 'var(--text-muted-color, var(--text-muted-color-fallback))' }}>시가총액(억)</th>
              <th className="text-xs sm:text-sm px-2 py-1 md:px-3 md:py-2 border-b font-medium text-right w-[80px] hidden md:table-cell" style={{ color: 'var(--text-muted-color, var(--text-muted-color-fallback))' }}>거래대금(억)</th>
              <th className="text-xs sm:text-sm px-2 py-1 md:px-3 md:py-2 border-b font-medium text-center w-[60px]" style={{ color: 'var(--text-muted-color, var(--text-muted-color-fallback))' }}>포지션</th>
              <th className="text-xs sm:text-sm px-2 py-1 md:px-3 md:py-2 border-b font-medium text-center w-[65px]" style={{ color: 'var(--text-muted-color, var(--text-muted-color-fallback))' }}>신호</th>
              <th className="text-xs sm:text-sm px-2 py-1 md:px-3 md:py-2 border-b font-medium text-center w-[60px]" style={{ color: 'var(--text-muted-color, var(--text-muted-color-fallback))' }}>RS</th>
              <th className="text-xs sm:text-sm px-2 py-1 md:px-3 md:py-2 border-b font-medium text-center w-[60px] hidden md:table-cell" style={{ color: 'var(--text-muted-color, var(--text-muted-color-fallback))' }}>RS_1M</th>
              <th className="text-xs sm:text-sm px-2 py-1 md:px-3 md:py-2 border-b font-medium text-center w-[60px]" style={{ color: 'var(--text-muted-color, var(--text-muted-color-fallback))' }}>MTT</th>
            </tr>
          </thead>
          <tbody>
            {Object.keys(data).map(sector => {
              const sectorStocks = data[sector];
              
              return (
                <React.Fragment key={sector}>
                  {sectorStocks.map((stock, stockIndex) => {
                    const showSector = stockIndex === 0;
                    
                    return (
                      <tr 
                        key={`${sector}-${stockIndex}`}
                        className="hover:bg-gray-50 transition-colors"
                      >
                        {showSector && (
                          <td 
                            className="text-xs sm:text-sm px-2 py-1 md:px-3 md:py-2 border-b w-[80px] align-middle" 
                            rowSpan={sectorStocks.length}
                          >
                            {sector}
                          </td>
                        )}
                          <td className="text-xs sm:text-sm px-2 py-1 md:px-3 md:py-2 border-b w-[100px]">{stock["종목명"]}</td>
                          <td className="text-xs sm:text-sm px-2 py-1 md:px-3 md:py-2 border-b text-right w-[60px]">
                            <span className={`${parseFloat(stock["등락률"]) > 0 ? 'text-red-500' : parseFloat(stock["등락률"]) < 0 ? 'text-blue-500' : ''}`}>
                              {stock["등락률"]}%
                            </span>
                          </td>
                          <td className="text-xs sm:text-sm px-2 py-1 md:px-3 md:py-2 border-b text-right w-[60px] hidden md:table-cell">{formatNumberWithCommas(stock["시가총액"]) }</td>
                          <td className="text-xs sm:text-sm px-2 py-1 md:px-3 md:py-2 border-b text-right w-[60px] hidden md:table-cell">{formatNumberWithCommas(stock["거래대금"]) }</td>
                          <td className="text-xs sm:text-sm px-2 py-1 md:px-3 md:py-2 border-b text-center w-[60px]">
                            <div className="mx-auto flex items-center justify-center w-20 h-6 bg-green-100 text-green-800 rounded-[4px]">
                              <span className="text-xs font-medium">
                                {stock["포지션"].includes('유지') 
                                  ? stock["포지션"] 
                                  : `유지 ${stock["포지션"]}`}
                              </span>
                            </div>
                          </td>
                          <td className="text-xs sm:text-sm px-2 py-1 md:px-3 md:py-2 border-b text-center w-[65px]">
                            {stock["신호등"] ? <SingleSignalLight signal={stock["신호등"]} /> : null}
                          </td>
                          <td className="text-xs sm:text-sm px-2 py-1 md:px-3 md:py-2 border-b text-center w-[60px]">{stock["RS"]}</td>
                          <td className="text-xs sm:text-sm px-2 py-1 md:px-3 md:py-2 border-b text-center w-[60px] hidden md:table-cell">{stock["RS_1M"]}</td>
                          <td className="text-xs sm:text-sm px-2 py-1 md:px-3 md:py-2 border-b text-center w-[60px]">
                            {stock["MTT"] === 'y' ? (
                              <CheckCircleIcon className="h-4 w-4 text-green-500 mx-auto" />
                            ) : (
                              null
                            )}
                          </td>
                        </tr>
                      );
                    })}
                </React.Fragment>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}
