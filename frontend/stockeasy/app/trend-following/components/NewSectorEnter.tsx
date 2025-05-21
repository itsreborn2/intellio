// frontend/stockeasy/app/trend-following/components/NewSectorEnter.tsx
'use client';

import React, { useEffect, useState, useRef } from 'react';
import Papa from 'papaparse';
import { CheckCircleIcon } from '@heroicons/react/24/solid';
// import { TableCopyButton } from '@/app/components/TableCopyButton';

interface SectorData {
  산업: string;
  섹터: string;
  '산업 등락률': string;
  종목명: string;
  등락률: string;
  포지션: string;
  '20일 이격': string;
  '돌파/이탈': string;
  '대표종목(RS)': string;
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

export default function NewSectorEnter() {
  const [data, setData] = useState<GroupedSectorData>({});
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [updateDate, setUpdateDate] = useState<string>('');

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
      setLoading(true);
      try {
        const response = await fetch('/requestfile/trend-following/newsectorenter.csv');
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
              return parseFloat(b["산업 등락률"]) - parseFloat(a["산업 등락률"]);
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
            setLoading(false);
          },
          error: (err: Error) => {
            console.error('Papa Parse 오류:', err);
            setError('CSV 데이터를 불러오는 중 오류가 발생했습니다.');
            setLoading(false);
          }
        });
      } catch (err) {
        console.error('데이터 가져오기 오류:', err);
        setError('데이터를 가져오는 중 오류가 발생했습니다.');
        setLoading(false);
      }
    }

    fetchData();
  }, []);

  // 업데이트 날짜 로드
  useEffect(() => {
    async function loadUpdateDate() {
      try {
        // newsectorenter.csv 파일에서 마지막 수정 날짜 가져오기
        const cacheFilePath = '/requestfile/trend-following/newsectorenter.csv';
        
        // 헤더만 가져와서 Last-Modified 확인
        const response = await fetch(cacheFilePath, { cache: 'no-store' });
        
        if (!response.ok) {
          console.error(`newsectorenter.csv 파일 로드 실패: ${response.status}`);
          return;
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
          console.warn('newsectorenter.csv 파일의 Last-Modified 헤더를 찾을 수 없어 현재 시간을 사용합니다.');
        }
      } catch (error) {
        console.error('데이터 업데이트 날짜 로드 실패:', error);
      }
    }
    
    loadUpdateDate();
  }, []);

  if (loading) {
    return (
      <section className="mb-6">
        <h2 className="text-sm font-semibold mb-2">신규 관심 섹터</h2>
        <div className="min-h-[200px] flex items-center justify-center">
          <div className="animate-pulse text-gray-500">데이터 로딩 중...</div>
        </div>
      </section>
    );
  }

  if (error) {
    return (
      <section className="mb-6">
        <h2 className="text-sm font-semibold mb-2">신규 관심 섹터</h2>
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
        <div className="font-semibold flex items-center mb-1" style={{ fontSize: '18px', color: 'var(--primary-text-color, var(--primary-text-color-fallback))' }}>신규 관심 섹터</div>
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
              tableName="신규 관심 섹터" 
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
              <th className="px-3 py-2 border-b text-left font-medium w-[135px]" style={{ color: 'var(--text-muted-color, var(--text-muted-color-fallback))' }}>산업</th>
              <th className="px-3 py-2 border-b text-left font-medium w-[115px]" style={{ color: 'var(--text-muted-color, var(--text-muted-color-fallback))' }}>섹터</th>
              <th className="px-3 py-2 border-b text-right font-medium" style={{ color: 'var(--text-muted-color, var(--text-muted-color-fallback))' }}>등락률</th>
              <th className="px-3 py-2 border-b text-left font-medium" style={{ color: 'var(--text-muted-color, var(--text-muted-color-fallback))' }}>종목명</th>
              <th className="px-3 py-2 border-b text-right font-medium" style={{ color: 'var(--text-muted-color, var(--text-muted-color-fallback))' }}>등락률</th>
              <th className="px-3 py-2 border-b text-center font-medium" style={{ color: 'var(--text-muted-color, var(--text-muted-color-fallback))' }}>포지션</th>
              <th className="px-3 py-2 border-b text-center font-medium" style={{ color: 'var(--text-muted-color, var(--text-muted-color-fallback))' }}>20일 이격</th>
              <th className="px-3 py-2 border-b text-center font-medium" style={{ color: 'var(--text-muted-color, var(--text-muted-color-fallback))' }}>돌파/이탈</th>
              <th className="px-3 py-2 border-b text-center font-medium w-[250px] max-w-[250px]" style={{ color: 'var(--text-muted-color, var(--text-muted-color-fallback))' }}>대표종목(RS)</th>
            </tr>
          </thead>
          <tbody className="bg-white">
            {Object.entries(data).map(([sector, sectorStocks]) => {
              // 산업별 그룹화
              const industryGroups: { [key: string]: SectorData[] } = {};
              
              sectorStocks.forEach(stock => {
                if (!industryGroups[stock.산업]) {
                  industryGroups[stock.산업] = [];
                }
                industryGroups[stock.산업].push(stock);
              });
              
              let isFirstRow = true;
              
              return (
                <React.Fragment key={sector}>
                  {Object.keys(industryGroups).map((industry, industryIndex) => {
                    const stocks = industryGroups[industry];
                    const industryRowSpan = stocks.length;
                    
                    return stocks.map((stock, stockIndex) => {
                      const showSector = isFirstRow && stockIndex === 0;
                      const showIndustry = stockIndex === 0;
                      
                      if (stockIndex === 0 && industryIndex === 0) {
                        isFirstRow = false;
                      }
                      
                      return (
                        <tr 
                          key={`${sector}-${industry}-${stockIndex}`}
                          className="hover:bg-gray-50 transition-colors"
                        >
                          {showSector && (
                            <td 
                              className="px-3 py-2 border-b w-[135px]" 
                              rowSpan={sectorStocks.length}
                            >
                              {sector}
                            </td>
                          )}
                          {showIndustry && (
                            <td 
                              className="px-3 py-2 border-b w-[115px]" 
                              rowSpan={industryRowSpan}
                            >
                              {industry}
                            </td>
                          )}
                          <td className="px-3 py-2 border-b text-right w-24">
                            <span className={`${parseFloat(stock["산업 등락률"]) > 0 ? 'text-red-500' : parseFloat(stock["산업 등락률"]) < 0 ? 'text-blue-500' : ''}`}>
                              {stock["산업 등락률"]}%
                            </span>
                          </td>
                          <td className="px-3 py-2 border-b">{stock["종목명"]}</td>
                          <td className="px-3 py-2 border-b text-right">
                            <span className={`${parseFloat(stock["등락률"]) > 0 ? 'text-red-500' : parseFloat(stock["등락률"]) < 0 ? 'text-blue-500' : ''}`}>
                              {stock["등락률"]}%
                            </span>
                          </td>
                          <td className="px-3 py-2 border-b text-center w-28">
                            <div className="mx-auto flex items-center justify-center w-20 h-6 bg-green-100 text-green-800 rounded-[4px]">
                              <span className="text-xs font-medium">
                                {stock["포지션"]}
                              </span>
                            </div>
                          </td>
                          <td className="px-3 py-2 border-b text-center">{stock["20일 이격"]}%</td>
                          <td className="px-3 py-2 border-b text-center">{stock["돌파/이탈"]}</td>
                          <td className="px-3 py-2 border-b w-[250px] max-w-[250px]">
                            <div className="whitespace-normal text-xs overflow-hidden">
                              {stock["대표종목(RS)"].split(', ').map((item, index) => {
                                // 정규표현식을 사용하여 종목명과 괄호 안의 값 추출
                                const match = item.match(/(.+)\((\d+)\)/);
                                if (match) {
                                  const [, name, rsValue] = match;
                                  const rsNumber = parseInt(rsValue, 10);
                                  // RS 값이 90 이상인 경우 굵게 표시
                                  if (rsNumber >= 90) {
                                    return <span key={index} className="font-bold">{name}({rsValue}){index < stock["대표종목(RS)"].split(', ').length - 1 ? ', ' : ''}</span>;
                                  }
                                }
                                // 그 외의 경우 일반 텍스트로 표시
                                return <span key={index}>{item}{index < stock["대표종목(RS)"].split(', ').length - 1 ? ', ' : ''}</span>;
                              })}
                            </div>
                          </td>
                        </tr>
                      );
                    });
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
