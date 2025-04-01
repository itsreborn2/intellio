'use client';

import React, { useState, useEffect, useMemo, useRef } from 'react';
import Papa from 'papaparse';
import {
  createColumnHelper,
  flexRender,
  getCoreRowModel,
  useReactTable,
  getSortedRowModel,
  SortingState,
} from '@tanstack/react-table';
import Sidebar from '../components/Sidebar'; // 사이드바 컴포넌트 import
import TableCopyButton from '../components/TableCopyButton'; // 테이블 복사 버튼 import
import { copyTableAsImage } from '../utils/tableCopyUtils'; // 테이블 복사 유틸리티 import

// CSV 데이터 타입 정의
interface ValuationData {
  stockName: string; // B열: 종목명
  marketCap: string; // C열: 시가총액
  per2023: string; // G열: 2023 PER
  perTrailing4Q: string; // H열: 직전 4분기 PER
  per2024E: string; // I열: 2024(E) PER
  per2025E: string; // J열: 2025(E) PER
  per2026E: string; // K열: 2026(E) PER
}

// 테이블 컬럼 정의 Helper
const columnHelper = createColumnHelper<ValuationData>();

// 컬럼 정의
const columns = [
  columnHelper.accessor('stockName', {
    header: '종목명',
    cell: info => info.getValue(),
    size: 150, // ETF 페이지 참고하여 너비 설정
  }),
  columnHelper.accessor('marketCap', {
    header: '시가총액',
    cell: info => info.getValue(),
    size: 100,
  }),
  columnHelper.accessor('per2023', {
    header: '2023 PER',
    cell: info => info.getValue(),
    size: 80,
  }),
  columnHelper.accessor('perTrailing4Q', {
    header: '직전 4분기 PER',
    cell: info => info.getValue(),
    size: 100,
  }),
  columnHelper.accessor('per2024E', {
    header: '2024(E) PER',
    cell: info => info.getValue(),
    size: 100,
  }),
  columnHelper.accessor('per2025E', {
    header: '2025(E) PER',
    cell: info => info.getValue(),
    size: 100,
  }),
  columnHelper.accessor('per2026E', {
    header: '2026(E) PER',
    cell: info => info.getValue(),
    size: 100,
  }),
];

const ValuationPage = () => {
  const [data, setData] = useState<ValuationData[]>([]);
  const [loading, setLoading] = useState(true);
  const [sorting, setSorting] = useState<SortingState>([]);
  
  // 테이블 복사 기능을 위한 ref 생성
  const tableRef = useRef<HTMLDivElement>(null);
  const headerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);
        const response = await fetch('/requestfile/value/PER.csv');
        
        // --- CSV 인코딩 처리 시작 ---
        const buffer = await response.arrayBuffer();
        // EUC-KR 또는 CP949로 시도, 깨진 문자에 따라 변경 필요
        const decoder = new TextDecoder('euc-kr'); 
        const decodedCsv = decoder.decode(buffer);
        // --- CSV 인코딩 처리 끝 ---

        Papa.parse<string[]>(decodedCsv, {
          complete: (results) => {
            // 3번째 행(인덱스 2)부터 데이터 추출
            const parsedData = results.data.slice(2).map(row => ({
              stockName: row[1] || '', // B열
              marketCap: row[2] || '', // C열
              per2023: row[6] || '', // G열
              perTrailing4Q: row[7] || '', // H열
              per2024E: row[8] || '', // I열
              per2025E: row[9] || '', // J열
              per2026E: row[10] || '', // K열
            })).filter(item => item.stockName); // 종목명이 있는 데이터만 필터링
            setData(parsedData);
            setLoading(false);
          },
          error: (error: any) => { // error 파라미터에 : any 타입 명시
            console.error('Error parsing CSV:', error);
            setLoading(false);
          },
          skipEmptyLines: true,
        });
      } catch (error: any) { // error 파라미터에 : any 타입 명시
        console.error('Error fetching CSV:', error);
        setLoading(false);
      }
    };

    fetchData();
  }, []);

  const table = useReactTable({
    data,
    columns,
    state: {
      sorting,
    },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    // debugTable: true, // 디버깅 필요시 활성화
  });

  if (loading) {
    return <div className="p-4">Loading...</div>;
  }

  return (
    <div className="flex"> {/* flex 컨테이너 추가 */}
      {/* 사이드바 */}
      <Sidebar />
      
      {/* 메인 콘텐츠 영역 - 모바일 최적화 */}
      <div className="flex-1 p-0 sm:p-2 md:p-4 overflow-auto ml-0 md:ml-16 w-full">
        {/* Inner container for width limit and centering */}
        <div className="max-w-6xl mx-auto">
          <div className="mb-2 md:mb-4"> {/* 바깥쪽 div: etf-sector와 동일한 하단 여백 */}
            {/* 안쪽 div: etf-sector 스타일(배경, 라운딩, 그림자, 패딩) 적용 + 기존 overflow, border 유지 */}
            <div className="bg-white rounded-md shadow p-2 md:p-4 overflow-x-auto border border-gray-200">
              {/* 제목 및 설명 영역 - ETF 페이지와 동일한 스타일 */}
              <div ref={headerRef} className="flex justify-between items-center mb-3">
                <div>
                  <h1 className="font-semibold text-gray-800" style={{ fontSize: 'clamp(0.75rem, 0.9vw, 0.9rem)' }}>벨류에이션 (PER 기반)</h1>
                  <p className="text-xs text-gray-500 mt-1">
                    기업별 PER 벨류에이션 데이터입니다. 2023-2026년 예상 PER 기준으로 정렬할 수 있습니다.
                  </p>
                </div>
                <div>
                  <TableCopyButton
                    tableRef={tableRef}
                    headerRef={headerRef}
                    tableName="벨류에이션_PER"
                    options={{
                      copyrightText: " StockEasy",
                      scale: 2
                    }}
                  />
                </div>
              </div>
              
              {/* 테이블 영역 */}
              <div ref={tableRef} className="overflow-x-auto">
                <table className="min-w-full border border-gray-200 table-fixed">
                <thead className="bg-gray-100">
                  {table.getHeaderGroups().map(headerGroup => (
                    <tr key={headerGroup.id}>
                      {headerGroup.headers.map(header => (
                        <th
                          key={header.id}
                          scope="col"
                          className="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer border border-gray-200"
                          style={{ 
                            width: `${header.getSize()}px`,
                            height: '35px',
                            fontSize: 'clamp(0.6rem, 0.7vw, 0.7rem)'
                          }}
                          onClick={header.column.getToggleSortingHandler()}
                        >
                          <div className="flex justify-center items-center">
                            {flexRender(
                              header.column.columnDef.header,
                              header.getContext()
                            )}
                            {/* 정렬 아이콘 */}
                            {header.column.getIsSorted() && (
                              <span className="ml-1">
                                {header.column.getIsSorted() === 'asc' ? '↑' : '↓'}
                              </span>
                            )}
                          </div>
                        </th>
                      ))}
                    </tr>
                  ))}
                </thead>
                <tbody className="bg-white">
                  {table.getRowModel().rows.map((row, rowIndex) => (
                    <tr key={row.id} className="hover:bg-gray-50">
                      {row.getVisibleCells().map(cell => (
                        <td
                          key={cell.id}
                          className="px-4 py-1 whitespace-nowrap text-xs border border-gray-200 text-center"
                          style={{ 
                            width: `${cell.column.getSize()}px`,
                            height: '16px',
                            fontSize: 'clamp(0.6rem, 0.7vw, 0.7rem)'
                          }}
                        >
                          {flexRender(cell.column.columnDef.cell, cell.getContext())}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ValuationPage;
