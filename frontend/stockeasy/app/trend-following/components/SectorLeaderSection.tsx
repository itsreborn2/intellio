// frontend/stockeasy/app/trend-following/components/SectorLeaderSection.tsx
'use client';

import React, { useEffect, useState, useRef } from 'react';
import Papa from 'papaparse';
import { CheckCircleIcon } from '@heroicons/react/24/solid';
import { TableCopyButton } from '@/app/components/TableCopyButton';

interface SectorData {
  산업: string;
  섹터: string;
  ETF명: string;
  ETF등락률: string;
  종목코드: string;
  종목명: string;
  등락률: string;
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
        const response = await fetch('/requestfile/trend-following/trend-following-sector.csv');
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
        // trend-following-sector.csv 파일에서 마지막 수정 날짜 가져오기
        const cacheFilePath = '/requestfile/trend-following/trend-following-sector.csv';
        
        // 헤더만 가져와서 Last-Modified 확인
        const response = await fetch(cacheFilePath, { cache: 'no-store' });
        
        if (!response.ok) {
          console.error(`trend-following-sector.csv 파일 로드 실패: ${response.status}`);
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
          console.warn('trend-following-sector.csv 파일의 Last-Modified 헤더를 찾을 수 없어 현재 시간을 사용합니다.');
        }
      } catch (e) {
        console.error('업데이트 날짜 로드 실패:', e);
      }
    }
    loadUpdateDate();
  }, []);

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
      <div ref={headerContainerRef} className="flex justify-between items-center mb-2">
        <div className="font-semibold flex items-center mb-1" style={{ fontSize: '18px', color: 'var(--primary-text-color, var(--primary-text-color-fallback))' }}>주도섹터 / 주도주</div>
        <div className="flex items-center space-x-2">
          {updateDate && (
            <span className="text-xs mr-2" style={{ fontSize: 'clamp(0.7rem, 0.7vw, 0.7rem)', color: 'var(--text-muted-color, var(--text-muted-color-fallback))' }}>
              updated {updateDate}
            </span>
          )}
          {/* 복사 버튼 숨김 처리
          <TableCopyButton 
            tableRef={tableContainerRef} 
            headerRef={headerContainerRef} 
            tableName="주도섹터_주도주"
            updateDateText={updateDate ? `updated ${updateDate}` : undefined}
          />
          */}
        </div>
      </div>

      <div ref={tableContainerRef} className="overflow-x-auto rounded-[6px]">
        <table className="min-w-full text-sm border border-gray-200 rounded-[6px]">
          <thead className="bg-gray-100">
            <tr>
              <th className="px-3 py-2 border-b font-medium text-left" style={{ color: 'var(--text-muted-color, var(--text-muted-color-fallback))' }}>섹터</th>
              <th className="px-3 py-2 border-b font-medium text-left" style={{ color: 'var(--text-muted-color, var(--text-muted-color-fallback))' }}>ETF명</th>
              <th className="px-3 py-2 border-b font-medium text-right w-24" style={{ color: 'var(--text-muted-color, var(--text-muted-color-fallback))' }}>ETF등락률</th>
              <th className="px-3 py-2 border-b font-medium text-left" style={{ color: 'var(--text-muted-color, var(--text-muted-color-fallback))' }}>종목명</th>
              <th className="px-3 py-2 border-b font-medium text-right" style={{ color: 'var(--text-muted-color, var(--text-muted-color-fallback))' }}>등락률</th>
              <th className="px-3 py-2 border-b font-medium text-center w-28" style={{ color: 'var(--text-muted-color, var(--text-muted-color-fallback))' }}>포지션</th>
              <th className="px-3 py-2 border-b font-medium text-center" style={{ color: 'var(--text-muted-color, var(--text-muted-color-fallback))' }}>RS</th>
              <th className="px-3 py-2 border-b font-medium text-center" style={{ color: 'var(--text-muted-color, var(--text-muted-color-fallback))' }}>RS_1M</th>
              <th className="px-3 py-2 border-b font-medium text-center" style={{ color: 'var(--text-muted-color, var(--text-muted-color-fallback))' }}>MTT</th>
            </tr>
          </thead>
          <tbody>
            {Object.keys(data).map((sector) => {
              const sectorStocks = data[sector];
              const etfGroups: { [etfName: string]: SectorData[] } = {};
              
              sectorStocks.forEach(stock => {
                if (!etfGroups[stock.ETF명]) {
                  etfGroups[stock.ETF명] = [];
                }
                etfGroups[stock.ETF명].push(stock);
              });
              
              let isFirstRow = true;
              
              return (
                <React.Fragment key={sector}>
                  {Object.keys(etfGroups).map((etfName, etfIndex) => {
                    const stocks = etfGroups[etfName];
                    const etfRowSpan = stocks.length;
                    
                    return stocks.map((stock, stockIndex) => {
                      const showSector = isFirstRow && stockIndex === 0;
                      const showEtf = stockIndex === 0;
                      
                      if (stockIndex === 0 && etfIndex === 0) {
                        isFirstRow = false;
                      }
                      
                      return (
                        <tr 
                          key={`${sector}-${etfName}-${stockIndex}`}
                          className="hover:bg-gray-50 transition-colors"
                        >
                          {showSector && (
                            <td 
                              className="px-3 py-2 border-b" 
                              rowSpan={sectorStocks.length}
                            >
                              {sector}
                            </td>
                          )}
                          {showEtf && (
                            <td 
                              className="px-3 py-2 border-b" 
                              rowSpan={etfRowSpan}
                            >
                              {etfName}
                            </td>
                          )}
                          <td className="px-3 py-2 border-b text-right w-24">
                            <span className={`${parseFloat(stock["ETF등락률"]) > 0 ? 'text-red-500' : parseFloat(stock["ETF등락률"]) < 0 ? 'text-blue-500' : ''}`}>
                              {stock["ETF등락률"]}%
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
                                {stock["포지션"].includes('유지') 
                                  ? stock["포지션"] 
                                  : `유지 ${stock["포지션"]}`}
                              </span>
                            </div>
                          </td>
                          <td className="px-3 py-2 border-b text-center">{stock["RS"]}</td>
                          <td className="px-3 py-2 border-b text-center">{stock["RS_1M"]}</td>
                          <td className="px-3 py-2 border-b text-center">
                            {stock["MTT"] === 'y' ? (
                              <CheckCircleIcon className="h-5 w-5 text-green-500 mx-auto" />
                            ) : (
                              null
                            )}
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
