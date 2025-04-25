// 52주 신고가 주요 종목 섹션 (rs-rank/page.tsx 테이블과 100% 동일하게 구현)
// 주의: 주석, 컬럼, 캔들, 데이터 파싱, 스타일 등 모두 rs-rank와 완벽히 동일하게 복사 적용
// 수정 시 반드시 rs-rank/page.tsx와 동기화 필요

'use client'

import { useEffect, useState, useRef } from 'react';
import Papa from 'papaparse';
import TableCopyButton from '../../components/TableCopyButton';
import { CandleMini } from 'intellio-common/components/ui/CandleMini';

// CSV 파싱 결과 타입
interface CSVData {
  headers: string[];
  rows: any[];
  errors: any[];
}

// 시가총액 억 단위 포맷 함수 (rs-rank와 동일)
function formatMarketCap(value: any): string {
  if (!value) return '0';
  if (isNaN(Number(value))) return String(value);
  const valueStr = typeof value === 'number' ? String(value) : value;
  let marketCapValue = Number(valueStr.replace(/[^0-9.]/g, ''));
  if (marketCapValue >= 100000000) {
    marketCapValue = marketCapValue / 100000000;
  }
  return Math.floor(marketCapValue).toLocaleString('ko-KR');
}

// 52주 신고가 주요 종목 섹션 컴포넌트
export default function High52Section() {
  // 데이터 상태
  const [highData, setHighData] = useState<CSVData | null>(null);
  const [highSortKey, setHighSortKey] = useState<string>('RS');
  const [highSortDirection, setHighSortDirection] = useState<'asc' | 'desc'>('desc');
  const [updateDate, setUpdateDate] = useState<string>('');
  const highTableRef = useRef<HTMLDivElement>(null);
  const highHeaderRef = useRef<HTMLDivElement>(null);

  // CSV 파일 경로 (rs-rank와 동일)
  const cacheFilePath = '/requestfile/stock-data/stock_1mbee4o9_nonpfiaexi4vin8qcn8bttxz.csv';

  // CSV 파싱 함수 (rs-rank와 동일)
  function parseCSV(csvText: string): CSVData {
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

  // 데이터 로드
  useEffect(() => {
    async function loadHighData() {
      try {
        const response = await fetch(cacheFilePath, { cache: 'no-store' });
        if (!response.ok) throw new Error('데이터 파일 로드 실패');
        const csvText = await response.text();
        setHighData(parseCSV(csvText));
      } catch (e) {
        setHighData({ headers: [], rows: [], errors: [] });
      }
    }
    loadHighData();
  }, []);

  // 업데이트 날짜 로드 (rs-rank와 동일)
  useEffect(() => {
    async function loadUpdateDate() {
      try {
        const response = await fetch('/requestfile/stock-data/stock_1idvb5kio0d6dchvoywe7ovwr-ez1cbpb.csv', { cache: 'no-store' });
        if (!response.ok) return;
        const csvText = await response.text();
        const parsed = parseCSV(csvText);
        if (parsed && parsed.rows.length > 0 && parsed.rows[0]['날짜']) {
          // 날짜에서 yyyy를 제거하고 MM-DD 또는 MM/DD만 표시
          // 예: 2024-04-23 -> 04-23, 20240423 -> 04-23
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

  // 정렬
  function handleHighSort(key: string) {
    let direction: 'asc' | 'desc' = 'asc';
    if (highSortKey === key) {
      direction = highSortDirection === 'asc' ? 'desc' : 'asc';
    }
    setHighSortKey(key);
    setHighSortDirection(direction);
  }
  function getSortedHighData(rows: any[]) {
    if (!highSortKey) return rows;
    return [...rows].sort((a, b) => {
      const aVal = a[highSortKey];
      const bVal = b[highSortKey];
      if (!isNaN(Number(aVal)) && !isNaN(Number(bVal))) {
        return highSortDirection === 'asc' ? Number(aVal) - Number(bVal) : Number(bVal) - Number(aVal);
      }
      if (aVal < bVal) return highSortDirection === 'asc' ? -1 : 1;
      if (aVal > bVal) return highSortDirection === 'asc' ? 1 : -1;
      return 0;
    });
  }

  // 렌더링
  // 섹션 전체에 radius 6px 적용 (테이블과 통일)
  return (
    <div className="bg-white rounded-[6px] shadow p-2 md:p-4" ref={highHeaderRef}>
      <div className="flex justify-between items-center mb-2">
        {/* 제목 폰트 사이즈 18px 고정 (모든 해상도) */}
        {/* 제목 폰트 사이즈 18px 고정 (모든 해상도, 상단 여백 없음, 하단만 mb-4) */}
        <h2 className="font-semibold text-gray-700 mb-4" style={{ fontSize: '18px' }}>52주 신고가 주요 종목</h2>
        <div className="flex items-center space-x-2">
          {updateDate && (
            <span className="text-gray-600 text-xs mr-2" style={{ fontSize: 'clamp(0.7rem, 0.7vw, 0.7rem)' }}>
              updated 16:40 {updateDate}
            </span>
          )}
          <TableCopyButton 
            tableRef={highTableRef} 
            headerRef={highHeaderRef} 
            tableName="52주 신고가 주요 종목"
            updateDateText={updateDate ? `updated 16:40 ${updateDate}` : undefined}
          />
        </div>
      </div>
      <div className="relative">
        <div className="flex-1 overflow-x-auto" ref={highTableRef}>
          {highData && highData.rows.length > 0 ? (
            <table className="w-full bg-white border border-gray-200 table-fixed rounded-[6px]">
              <thead>
                <tr className="bg-gray-100">
                  <th className="px-0.5 sm:px-1 md:px-2 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer border border-gray-200 text-center text-xs" style={{ width: '90px', height: '35px' }} onClick={() => handleHighSort('종목명')}>
                    <div className="flex items-center justify-center">
                      <span>종목명</span>
                      {highSortKey === '종목명' && (<span className="ml-1">{highSortDirection === 'asc' ? '↑' : '↓'}</span>)}
                    </div>
                  </th>
                  <th className="px-0.5 sm:px-1 md:px-2 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer border border-gray-200 text-center text-xs" style={{ width: '45px', height: '35px' }} onClick={() => handleHighSort('RS')}>
                    <div className="flex items-center justify-center">
                      <span>RS</span>
                      {highSortKey === 'RS' && (<span className="ml-1">{highSortDirection === 'asc' ? '↑' : '↓'}</span>)}
                    </div>
                  </th>
                  <th className="px-0.5 sm:px-1 md:px-2 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer border border-gray-200 text-center text-xs" style={{ width: '55px', height: '35px' }} onClick={() => handleHighSort('등락률')}>
                    <div className="flex items-center justify-center">
                      <span>등락률</span>
                      {highSortKey === '등락률' && (<span className="ml-1">{highSortDirection === 'asc' ? '↑' : '↓'}</span>)}
                    </div>
                  </th>
                  {/* 당일 캔들 컬럼 헤더 */}
                  <th className="px-0.5 sm:px-1 md:px-2 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider border border-gray-200 text-center text-xs" style={{ width: '90px', height: '35px' }}>
                    <div className="flex items-center justify-center"><span>당일 캔들</span></div>
                  </th>
                  <th className="hidden sm:table-cell px-0.5 sm:px-1 md:px-2 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider border border-gray-200 text-center text-xs" style={{ width: '70px', height: '35px' }}>
                    <div className="flex items-center justify-center"><span>종가(원)</span></div>
                  </th>
                  <th className="px-0.5 sm:px-1 md:px-2 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer border border-gray-200 text-center text-xs" style={{ width: '60px', height: '35px' }} onClick={() => handleHighSort('시가총액')}>
                    <div className="flex items-center justify-center">
                      <span>시가총액(억)</span>
                      {highSortKey === '시가총액' && (<span className="ml-1">{highSortDirection === 'asc' ? '↑' : '↓'}</span>)}
                    </div>
                  </th>
                  <th className="px-0.5 sm:px-1 md:px-2 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer border border-gray-200 text-center text-xs" style={{ width: '60px', height: '35px' }} onClick={() => handleHighSort('거래대금')}>
                    <div className="flex items-center justify-center">
                      <span>거래대금(억)</span>
                      {highSortKey === '거래대금' && (<span className="ml-1">{highSortDirection === 'asc' ? '↑' : '↓'}</span>)}
                    </div>
                  </th>
                </tr>
              </thead>
              <tbody>
                {getSortedHighData(highData.rows).map((row: any, rowIndex: number) => (
                  <tr key={rowIndex} className={rowIndex % 2 === 0 ? 'bg-gray-50' : 'bg-white'}>
                    <td className="py-1 sm:py-1.5 px-0.5 sm:px-1 md:px-2 border-b border-r text-left whitespace-nowrap overflow-hidden text-ellipsis text-xs" style={{ height: '35px' }}>{row['종목명']}</td>
                    <td className="py-1 sm:py-1.5 px-0.5 sm:px-1 md:px-2 border-b border-r text-center whitespace-nowrap overflow-hidden text-ellipsis text-xs" style={{ height: '35px' }}>{row['RS']}</td>
                    <td className={`py-1 sm:py-1.5 px-0.5 sm:px-1 md:px-2 border-b border-r text-center whitespace-nowrap overflow-hidden text-ellipsis text-xs ${
                      (Number(row['등락률']) >= 5)
                        ? 'text-red-500'
                        : (Number(row['등락률']) <= -2)
                          ? 'text-blue-500'
                          : ''
                    }`} style={{ height: '35px' }}>
                      {(Number(row['등락률']) > 0 ? '+' : '') + (Number(row['등락률']) || 0).toFixed(2)}%
                    </td>
                    {/* 당일 캔들(시가/고가/저가/종가) */}
                    <td className="py-1 sm:py-1.5 px-0.5 sm:px-1 md:px-2 border-b border-r text-center whitespace-nowrap overflow-hidden text-ellipsis text-xs" style={{ height: '35px' }}>
                      <div className="flex items-center justify-center w-full h-full">
                        <CandleMini 
                          open={Number(row['시가'])}
                          high={Number(row['고가'])}
                          low={Number(row['저가'])}
                          close={Number(row['종가'])}
                          width={28}
                          height={44}
                        />
                      </div>
                    </td>
                    <td className="hidden sm:table-cell py-1 sm:py-1.5 px-0.5 sm:px-1 md:px-2 border-b border-r text-right whitespace-nowrap overflow-hidden text-ellipsis text-xs" style={{ height: '35px' }}>
                      {row['종가'] && !isNaN(Number(row['종가'])) ? Number(row['종가']).toLocaleString('ko-KR') : (row['종가'] || '')}
                    </td>
                    <td className="py-1 sm:py-1.5 px-0.5 sm:px-1 md:px-2 border-b border-r text-right whitespace-nowrap overflow-hidden text-ellipsis text-xs" style={{ height: '35px' }}>
                      {formatMarketCap(row['시가총액'])}
                    </td>
                    <td className="py-1 sm:py-1.5 px-0.5 sm:px-1 md:px-2 border-b border-r text-right whitespace-nowrap overflow-hidden text-ellipsis text-xs" style={{ height: '35px' }}>
                      {(Number(row['거래대금']) || 0).toLocaleString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <p className="text-gray-700 text-center py-4" style={{ fontSize: 'clamp(0.7rem, 0.8vw, 0.8rem)' }}>
              52주 신고/신저가를 갱신한 주요 종목이 없습니다.<br />시장 환경이 좋지 않은 상태를 의미합니다.
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
