// frontend/stockeasy/app/trend-following/components/NewSectorOut.tsx
'use client';

import React, { useEffect, useState, useRef } from 'react';
import Papa from 'papaparse';
import { CheckCircleIcon } from '@heroicons/react/24/solid';
// import { TableCopyButton } from '@/app/components/TableCopyButton';

interface SectorData {
  섹터: string;
  '산업 등락률': string;
  종목명: string;
  등락률: string;
  포지션: string;
  신호등: string;
  '20일 이격': string;
  '돌파/이탈': string;
  '대표종목(RS)': string;

  // 문자열 키로 액세스할 수 있도록 인덱스 시그니처 추가
  [key: string]: string;
}

// 신호등 색상 값 정의
const signalColorValues = {
  red: '#ef4444', // 빨강
  yellow: '#fde047', // 노랑
  green: '#22c55e', // 초록
  inactive: '#e5e7eb', // 비활성
};

// 신호등 컴포넌트
function SingleSignalLight({ signal }: { signal: string | null }) {
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

interface GroupedSectorData {
  [key: string]: SectorData[];
}

// CSV 파싱 결과 인터페이스 추가
interface CSVParseResult {
  headers: string[];
  rows: any[];
  errors: any[];
}

export default function NewSectorOut() {
  const [data, setData] = useState<GroupedSectorData>({});
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [updateDate, setUpdateDate] = useState<string>(''); // '저장시간'을 저장할 상태
  const tableContainerRef = useRef<HTMLDivElement>(null);
  const headerContainerRef = useRef<HTMLDivElement>(null);

  // CSV 파싱 함수
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
      try {
        const response = await fetch('/requestfile/trend-following/newsectorout.csv', { cache: 'no-store' });
        const csvText = await response.text();
        
        Papa.parse(csvText, {
          header: true,
          skipEmptyLines: true,
          complete: (results) => {
            const parsedData = results.data as SectorData[];
            // 데이터 정렬 로직 (예시: 섹터 이름으로 정렬)
            const sortedData = parsedData.sort((a, b) => a.섹터.localeCompare(b.섹터));
            
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
            if (results.data.length > 0 && (results.data[0] as SectorData).저장시간) {
              const firstRowWithTime = results.data[0] as SectorData;
              // '05/21 16:00' 형식에서 'MM/DD HH:mm' 부분만 추출
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
                setUpdateDate(`${month.toString().padStart(2, '0')}/${day.toString().padStart(2, '0')} ${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}`);
                updatedTimeSet = true;
              } else {
                // CSV 저장시간도 없고, Last-Modified 헤더도 없는 경우 현재 시간 사용
                const now = new Date();
                const month = now.getMonth() + 1;
                const day = now.getDate();
                const hours = now.getHours();
                const minutes = now.getMinutes();
                const formattedDate = `${month.toString().padStart(2, '0')}/${day.toString().padStart(2, '0')} ${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}`;
                setUpdateDate(formattedDate);
                console.warn('newsectorout.csv 파일의 저장시간 및 Last-Modified 헤더를 찾을 수 없어 현재 시간을 사용합니다.');
              }
            }
            setLoading(false);
          },
          error: (err: Error) => {
            console.error('CSV 파싱 중 에러 발생: ', err);
            setError('CSV 파일을 파싱하는 중 오류가 발생했습니다.');
            setUpdateDate(''); // 오류 발생 시 날짜 초기화
            setLoading(false);
          }
        });
      } catch (e: any) {
        console.error('데이터 패칭 중 에러 발생: ', e);
        setError('데이터를 가져오는 중 오류가 발생했습니다.');
        setData({}); // 오류 발생 시 데이터 초기화
        setUpdateDate(''); // 오류 발생 시 날짜 초기화
        setLoading(false);
      }
    }

    fetchData();
  }, []);

  if (loading) {
    return (
      <section className="mb-6">
        <h2 className="text-sm font-semibold mb-2">신규 이탈 섹터</h2>
        <div className="min-h-[200px] flex items-center justify-center">
          <div className="animate-pulse text-gray-500">데이터 로딩 중...</div>
        </div>
      </section>
    );
  }

  if (error) {
    return (
      <section className="mb-6">
        <h2 className="text-sm font-semibold mb-2">신규 이탈 섹터</h2>
        <div className="min-h-[200px] flex items-center justify-center">
          <div className="text-red-500">{error}</div>
        </div>
      </section>
    );
  }

  // 데이터가 없으면 섹션 자체를 숨김
  if (Object.keys(data).length === 0) {
    return null;
  }

  return (
    <section className="bg-white rounded border border-gray-100 px-2 md:px-4 py-2 md:py-3">
      <div ref={headerContainerRef} className="flex justify-between items-center mb-2">
        <div className="font-semibold flex items-center mb-1 text-base md:text-lg" style={{ color: 'var(--primary-text-color, var(--primary-text-color-fallback))' }}>신규 이탈 섹터</div>
        <div className="flex items-center space-x-2">
          {updateDate && (
            <span className="text-xs mr-2" style={{ fontSize: 'clamp(0.7rem, 0.7vw, 0.7rem)', color: 'var(--text-muted-color, var(--text-muted-color-fallback))' }}>
              updated {updateDate}
            </span>
          )}
          {/* 복사 버튼 숨김 처리
          {Object.keys(data).length > 0 && (
            <TableCopyButton 
              tableRef={tableContainerRef} 
              headerRef={headerContainerRef}
              tableName="신규 이탈 섹터" 
              options={{
                copyrightText: "© intellio.kr",
                scale: 4
              }}
              updateDateText={updateDate ? `updated ${updateDate}` : undefined}
            />
          )}
          */}
        </div>
      </div>
      <div ref={tableContainerRef} className="overflow-x-auto rounded-[6px]">
        <table className="min-w-full text-sm border border-gray-200 rounded-[6px]">
          <thead className="bg-gray-100">
            <tr>
              <th className="text-xs sm:text-sm px-2 py-1 md:px-3 md:py-2 border-b text-left font-medium w-[122px]" style={{ color: 'var(--text-muted-color, var(--text-muted-color-fallback))' }}>섹터</th>
              <th className="text-xs sm:text-sm px-2 py-1 md:px-3 md:py-2 border-b text-right font-medium hidden md:table-cell" style={{ color: 'var(--text-muted-color, var(--text-muted-color-fallback))' }}>등락률</th>
              <th className="text-xs sm:text-sm px-2 py-1 md:px-3 md:py-2 border-b text-left font-medium w-[90px]" style={{ color: 'var(--text-muted-color, var(--text-muted-color-fallback))' }}>종목명</th>
              <th className="text-xs sm:text-sm px-2 py-1 md:px-3 md:py-2 border-b text-right font-medium" style={{ color: 'var(--text-muted-color, var(--text-muted-color-fallback))' }}>등락률</th>
              <th className="text-xs sm:text-sm px-2 py-1 md:px-3 md:py-2 border-b text-center font-medium hidden md:table-cell" style={{ color: 'var(--text-muted-color, var(--text-muted-color-fallback))' }}>포지션</th>
              <th className="text-xs sm:text-sm px-2 py-1 md:px-3 md:py-2 border-b text-center font-medium hidden md:table-cell w-[65px]" style={{ color: 'var(--text-muted-color, var(--text-muted-color-fallback))' }}>신호</th>
              <th className="text-xs sm:text-sm px-2 py-1 md:px-3 md:py-2 border-b text-center font-medium hidden md:table-cell" style={{ color: 'var(--text-muted-color, var(--text-muted-color-fallback))' }}>20일 이격</th>
              <th className="text-xs sm:text-sm px-2 py-1 md:px-3 md:py-2 border-b text-center font-medium" style={{ color: 'var(--text-muted-color, var(--text-muted-color-fallback))' }}>대표종목(RS)</th>

            </tr>
          </thead>
          <tbody className="bg-white">
            {Object.entries(data).map(([sector, sectorStocks]) => {
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
                            className="text-xs sm:text-sm px-2 py-1 md:px-3 md:py-2 border-b w-[122px] align-middle"
                            rowSpan={sectorStocks.length}
                          >
                            {sector}
                          </td>
                        )}
                        <td className="text-xs sm:text-sm px-2 py-1 md:px-3 md:py-2 border-b text-right w-24 hidden md:table-cell">
                          <span className={`${parseFloat(stock["산업 등락률"]) > 0 ? 'text-red-500' : parseFloat(stock["산업 등락률"]) < 0 ? 'text-blue-500' : ''}`}>
                            {stock["산업 등락률"]}%
                          </span>
                        </td>
                        <td className="text-xs sm:text-sm px-2 py-1 md:px-3 md:py-2 border-b w-[90px] truncate" title={stock["종목명"]}>{stock["종목명"]}</td>
                        <td className="text-xs sm:text-sm px-2 py-1 md:px-3 md:py-2 border-b text-right">
                          <span className={`${parseFloat(stock["등락률"]) > 0 ? 'text-red-500' : parseFloat(stock["등락률"]) < 0 ? 'text-blue-500' : ''}`}>
                            {stock["등락률"]}%
                          </span>
                        </td>
                        <td className="text-xs sm:text-sm px-2 py-1 md:px-3 md:py-2 border-b text-center w-28 hidden md:table-cell">
                          <div className="mx-auto flex items-center justify-center w-20 h-6 bg-red-100 text-red-800 rounded-[4px]">
                            <span className="text-xs font-medium">
                              {stock["포지션"]}
                            </span>
                          </div>
                        </td>
                        <td className="text-xs sm:text-sm px-2 py-1 md:px-3 md:py-2 border-b text-center w-[65px] hidden md:table-cell">
                          {stock["신호등"] ? <SingleSignalLight signal={stock["신호등"]} /> : null}
                        </td>
                        <td className="text-xs sm:text-sm px-2 py-1 md:px-3 md:py-2 border-b text-center hidden md:table-cell">{stock["20일 이격"]}%
                        </td>
                        <td className="text-xs sm:text-sm px-2 py-1 md:px-3 md:py-2 border-b w-[330px] max-w-[330px]">
                          <div className="whitespace-normal text-xs overflow-hidden">
                            {stock["대표종목(RS)"].split(', ').map((item, index) => {
                              const match = item.match(/(.+)\((\d+)\)/);
                              if (match) {
                                const [, name, rsValue] = match;
                                const rsNumber = parseInt(rsValue, 10);
                                if (rsNumber >= 90) {
                                  return <span key={index} className="font-bold">{name}({rsValue}){index < stock["대표종목(RS)"].split(', ').length - 1 ? ', ' : ''}</span>;
                                }
                              }
                              return <span key={index}>{item}{index < stock["대표종목(RS)"].split(', ').length - 1 ? ', ' : ''}</span>;
                            })}
                          </div>
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
