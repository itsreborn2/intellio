// 52주 신고가 주요 종목 섹션 (rs-rank/page.tsx 테이블과 100% 동일하게 구현)
// 주의: 주석, 컬럼, 캔들, 데이터 파싱, 스타일 등 모두 rs-rank와 완벽히 동일하게 복사 적용
// 수정 시 반드시 rs-rank/page.tsx와 동기화 필요

'use client'

import { useEffect, useState, useRef } from 'react';
import Papa from 'papaparse';
// import TableCopyButton from '../../components/TableCopyButton';
import { CandleMini } from 'intellio-common/components/ui/CandleMini';
import { CheckCircleIcon } from '@heroicons/react/24/solid';

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
  const [highSortKey, setHighSortKey] = useState<string>('등락률');
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

  // 업데이트 날짜 로드
  useEffect(() => {
    async function loadUpdateDate() {
      try {
        // stock_1mbee4o9_nonpfiaexi4vin8qcn8bttxz.csv 파일에서 마지막 수정 날짜 가져오기
        const response = await fetch(cacheFilePath, { cache: 'no-store' });
        
        if (!response.ok) {
          console.error(`데이터 파일 로드 실패: ${response.status}`);
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
          console.warn('파일의 Last-Modified 헤더를 찾을 수 없어 현재 시간을 사용합니다.');
        }
      } catch (e) {
        console.error('업데이트 날짜 로드 실패:', e);
      }
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
  return (
    <section className="bg-white rounded border border-gray-100 px-2 md:px-4 py-2 md:py-3">
        <div className="flex justify-between items-center mb-2">
          {/* 제목 (52주 신고/신저가 주요종목) */}
          <div className="font-semibold flex items-center mb-1" style={{ fontSize: '18px', color: 'var(--primary-text-color, var(--primary-text-color-fallback))' }}>52주 신고/신저가 주요종목</div>
          <div className="flex items-center space-x-2">
            {updateDate && (
              <span className="text-xs mr-2" style={{ fontSize: 'clamp(0.7rem, 0.7vw, 0.7rem)', color: 'var(--text-muted-color, var(--text-muted-color-fallback))' }}>
                updated {updateDate}
              </span>
            )}
            {/* 복사 버튼 숨김 처리
            <TableCopyButton 
              tableRef={highTableRef} 
              headerRef={highHeaderRef} 
              tableName="52주 신고가 주요 종목"
              updateDateText={updateDate ? `updated ${updateDate}` : undefined}
            />
            */}
          </div>
        </div>
        <div className="overflow-x-auto rounded-[6px]" ref={highTableRef}>
          {highData && highData.rows.length > 0 ? (
            <table className="min-w-full text-sm border border-gray-200 rounded-[6px]">
              <thead className="bg-gray-100">
                <tr>
                  <th className="px-3 py-2 border-b font-medium text-left" style={{ color: 'var(--text-muted-color, var(--text-muted-color-fallback))' }}>종목명</th>
                  <th className="px-3 py-2 border-b font-medium text-left" style={{ color: 'var(--text-muted-color, var(--text-muted-color-fallback))' }}>업종명</th>
                  <th className="px-3 py-2 border-b font-medium text-right cursor-pointer" style={{ color: 'var(--text-muted-color, var(--text-muted-color-fallback))' }} onClick={() => handleHighSort('등락률')}>등락률{highSortKey === '등락률' && <span className="ml-1">{highSortDirection === 'asc' ? '↑' : '↓'}</span>}</th>
                  <th className="px-3 py-2 border-b font-medium text-center" style={{ color: 'var(--text-muted-color, var(--text-muted-color-fallback))' }}>당일 캔캔들</th>
                  <th className="px-3 py-2 border-b font-medium text-right cursor-pointer" style={{ width: '120px', color: 'var(--text-muted-color, var(--text-muted-color-fallback))' }} onClick={() => handleHighSort('시가총액')}>시가총액(억){highSortKey === '시가총액' && <span className="ml-1">{highSortDirection === 'asc' ? '↑' : '↓'}</span>}</th>
                  <th className="px-3 py-2 border-b font-medium text-right cursor-pointer" style={{ color: 'var(--text-muted-color, var(--text-muted-color-fallback))' }} onClick={() => handleHighSort('거래대금')}>거래대금(억){highSortKey === '거래대금' && <span className="ml-1">{highSortDirection === 'asc' ? '↑' : '↓'}</span>}</th>
                  <th className="px-3 py-2 border-b font-medium text-center cursor-pointer" style={{ color: 'var(--text-muted-color, var(--text-muted-color-fallback))' }} onClick={() => handleHighSort('RS')}>RS{highSortKey === 'RS' && <span className="ml-1">{highSortDirection === 'asc' ? '↑' : '↓'}</span>}</th>
                  <th className="px-3 py-2 border-b font-medium text-center cursor-pointer" style={{ color: 'var(--text-muted-color, var(--text-muted-color-fallback))' }} onClick={() => handleHighSort('MTT')}>MTT{highSortKey === 'MTT' && <span className="ml-1">{highSortDirection === 'asc' ? '↑' : '↓'}</span>}</th>
                </tr>
              </thead>
              <tbody>
                {getSortedHighData(highData.rows).map((row: any, rowIndex: number) => (
                  <tr key={rowIndex} className={`${rowIndex % 2 === 0 ? 'bg-gray-50' : 'bg-white'} hover:bg-gray-50 transition-colors`}>
                    <td className="px-3 py-2 border-b text-left">{row['종목명']}</td>
                    <td className="px-3 py-2 border-b text-left">{row['업종명']}</td>
                    <td className="px-3 py-2 border-b text-right"><span className={`${Number(row['등락률']) > 5 ? 'text-red-500' : Number(row['등락률']) < 0 ? 'text-blue-500' : ''}`}>{(Number(row['등락률']) > 0 ? '+' : '') + (Number(row['등락률']) || 0).toFixed(2)}%</span></td>
                    <td className="px-3 py-2 border-b text-center"><div className="flex items-center justify-center"><CandleMini open={Number(row['시가'])} high={Number(row['고가'])} low={Number(row['저가'])} close={Number(row['종가'])} width={28} height={44} /></div></td>
                    <td className="px-3 py-2 border-b text-right" style={{ width: '120px' }}>{formatMarketCap(row['시가총액'])}</td>
                    <td className="px-3 py-2 border-b text-right">{formatMarketCap(row['거래대금'])}</td>
                    <td className="px-3 py-2 border-b text-center">{row['RS']}</td>
                    <td className="px-3 py-2 border-b text-center">
                      {row['MTT'] === 'y' ? (
                        <CheckCircleIcon className="h-5 w-5 text-green-500 mx-auto" />
                      ) : null}
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
    </section>
  );
}
