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

  // 업데이트 날짜 로드 (High52Section과 동일한 방식)
  useEffect(() => {
    async function loadUpdateDate() {
      try {
        // High52Section과 동일한 날짜 파일 사용 또는 sector 전용 파일이 있다면 해당 파일 사용
        const response = await fetch('/requestfile/stock-data/stock_1idvb5kio0d6dchvoywe7ovwr-ez1cbpb.csv', { cache: 'no-store' });
        if (!response.ok) return;
        const csvText = await response.text();
        const parsed = parseCSV(csvText);
        if (parsed && parsed.rows.length > 0 && parsed.rows[0]['날짜']) {
          // 날짜에서 yyyy를 제거하고 MM-DD 또는 MM/DD만 표시
          let raw = parsed.rows[0]['날짜'];
          let mmdd = '';
          if (/^\d{8}$/.test(raw)) { // 20240423
            mmdd = raw.substring(4, 6) + '-' + raw.substring(6, 8);
          } else if (/^\d{4}-\d{2}-\d{2}$/.test(raw)) { // 2024-04-23
            mmdd = raw.substring(5, 7) + '-' + raw.substring(8, 10);
          } else if (/^\d{2}-\d{2}$/.test(raw)) { // 04-23
            mmdd = raw;
          } else if (/^\d{2}\/\d{2}$/.test(raw)) { // 04/23
            mmdd = raw.replace('/', '-');
          } else {
            mmdd = raw;
          }
          setUpdateDate(mmdd);
        }
      } catch (e) {}
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
    <section className="bg-white rounded-lg p-4 border border-gray-200">
      <div ref={headerContainerRef} className="flex justify-between items-center mb-4">
        <h2 className="font-semibold text-gray-700" style={{ fontSize: 'clamp(0.9rem, 1.1vw, 1.1rem)' }}>주도섹터 / 주도주</h2>
        <div className="flex items-center space-x-2">
          {updateDate && (
            <span className="text-gray-600 text-xs mr-2" style={{ fontSize: 'clamp(0.7rem, 0.7vw, 0.7rem)' }}>
              updated 16:40 {updateDate}
            </span>
          )}
          <TableCopyButton 
            tableRef={tableContainerRef} 
            headerRef={headerContainerRef} 
            tableName="주도섹터_주도주"
            updateDateText={updateDate ? `updated 16:40 ${updateDate}` : undefined}
          />
        </div>
      </div>

      <div ref={tableContainerRef} className="overflow-x-auto rounded-[6px]">
        <table className="min-w-full text-sm border border-gray-200 rounded-[6px]">
          <thead className="bg-gray-100 text-gray-700">
            <tr className="bg-gray-50">
              <th className="px-3 py-2 border-b font-semibold text-left">섹터</th>
              <th className="px-3 py-2 border-b font-semibold text-left">ETF명</th>
              <th className="px-3 py-2 border-b font-semibold text-right w-24">ETF등락률</th>
              <th className="px-3 py-2 border-b font-semibold text-left">종목명</th>
              <th className="px-3 py-2 border-b font-semibold text-right">등락률</th>
              <th className="px-3 py-2 border-b font-semibold text-center w-28">포지션</th>
              <th className="px-3 py-2 border-b font-semibold text-center">RS</th>
              <th className="px-3 py-2 border-b font-semibold text-center">RS_1M</th>
              <th className="px-3 py-2 border-b font-semibold text-center">MTT</th>
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
                              className="px-3 py-2 border-b font-semibold" 
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
