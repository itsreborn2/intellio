'use client';

import React, { useState, useEffect, useMemo, useCallback, useRef } from 'react';
import Papa from 'papaparse';
import { fetchCSVData } from '../utils/fetchCSVData';
import {
  createColumnHelper,
  flexRender,
  getCoreRowModel,
  useReactTable,
  getSortedRowModel,
  SortingState,
} from '@tanstack/react-table';
import { copyTableAsImage } from '../utils/tableCopyUtils'; // 테이블 복사 유틸리티 import
import { formatDateMMDD } from '../utils/dateUtils'; // 날짜 포맷 유틸리티 import

// CSV 데이터 타입 정의
interface ValuationData {
  stockCode: string;      // B열 (Index 1)
  stockName: string;      // E열 (Index 4)
  industry: string;       // F열 (Index 5)
  middleCategory: string; // D열 (Index 3) - 중분류로 변경
  marketCap: number | null;      // G열 (Index 6 - 시가총액)
  per1: number | null;           // K열 (Index 10 - PER1)
  per2: number | null;           // L열 (Index 11 - PER2)
  per3: number | null;           // M열 (Index 12 - PER3)
  per4: number | null;           // N열 (Index 13 - PER4)
  per5: number | null;           // O열 (Index 14 - PER5)
  [key: string]: string | number | null; // 인덱스 시그니처 추가
}

// 숫자에 3자리마다 콤마를 추가하는 함수
const formatNumberWithCommas = (value: string | number | null | undefined): string => {
  if (value === null || value === undefined || value === '') return '';
  
  // 문자열로 변환 후 숫자가 아닌 문자 제거
  const numStr = String(value).replace(/[^\d.-]/g, '');
  
  // 숫자로 변환 가능한지 확인
  if (isNaN(Number(numStr))) return String(value);
  
  // 3자리마다 콤마 추가
  return Number(numStr).toLocaleString('ko-KR');
};

// 시가총액을 백억 단위로 변환하는 함수
const formatMarketCapToHundredBillion = (value: string | number | null | undefined): string => {
  if (value === null || value === undefined || value === '') return '';
  
  // 문자열로 변환 후 숫자가 아닌 문자 제거
  const numStr = String(value).replace(/[^\d.-]/g, '');
  
  // 숫자로 변환 가능한지 확인
  if (isNaN(Number(numStr))) return String(value);
  
  // 억 단위를 백억 단위로 변환 (100억으로 나누기)
  const hundredBillion = Number(numStr) / 100;
  
  // 정수로 반올림
  const rounded = Math.round(hundredBillion);
  
  // 3자리마다 콤마 추가
  return rounded.toLocaleString('ko-KR');
};

// 추이 막대 그래프 컴포넌트
interface TrendBarGraphProps {
  values: (string | number | null | undefined)[];
}

const TrendBarGraph: React.FC<TrendBarGraphProps> = ({ values }) => {
  // 빈 값, undefined, null 등을 0으로 변환하여 모든 인덱스에 값 생성
  const processedValues = values.map(val => {
    if (val === undefined || val === null || val === '') return 0;
    const numVal = typeof val === 'string' ? parseFloat(val.replace(/,/g, '')) : typeof val === 'number' ? val : 0;
    return !isNaN(numVal) && numVal >= 0 ? numVal : 0;
  });
  
  // 최대값 계산 (모든 값이 0이면 maxValue도 0)
  const maxValue = Math.max(...processedValues, 0);
  
  // 모든 값이 0인 경우 간단한 표시 반환
  if (maxValue === 0) {
    return <div className="h-full w-full flex items-center justify-center text-gray-400 text-xs">0</div>;
  }
  
  // 모든 데이터 포인트 생성 (없는 값은 모두 0으로 처리되어 있음)
  const dataPoints = processedValues.map((value, index) => ({
    value,
    index
  }));
  
  // SVG 영역 계산
  const svgWidth = 100; 
  const svgHeight = 100;
  
  // 각 포인트의 SVG 좌표 계산
  const pointsData = dataPoints.map(point => {
    const barWidth = svgWidth / processedValues.length;
    const x = (point.index * barWidth) + (barWidth / 2); // 각 막대의 중앙에 위치
    const y = svgHeight - ((point.value / maxValue) * svgHeight);
    return { x, y };
  });
  
  // 포인트를 연결하는 라인 생성
  const linePoints = pointsData.map(point => `${point.x},${point.y}`).join(' ');
  
  return (
    <div className="relative h-4 w-full">
      {/* 막대 그래프 */}
      <div className="absolute inset-0 flex items-end space-x-px">
        {processedValues.map((value, index) => {
          const heightPercentage = maxValue > 0 ? (value / maxValue) * 100 : 0;
          const minHeightStyle = (value > 0 && heightPercentage < 5) ? '1px' : `${heightPercentage}%`;
          
          return (
            <div key={`bar-${index}`} className="flex-1 h-full flex items-end justify-center">
              <div
                className="w-full bg-blue-300"
                /* 추이 컬럼 막대그래프: 모서리를 6px radius로 둥글게 처리 */
                /* 위쪽(좌상단, 우상단)만 4px radius, 아래쪽은 0px */
                 style={{ height: minHeightStyle, borderTopLeftRadius: '4px', borderTopRightRadius: '4px', borderBottomLeftRadius: 0, borderBottomRightRadius: 0 }}
                title={`${value.toFixed(2)} (Max: ${maxValue.toFixed(2)})`}
              ></div>
            </div>
          );
        })}
      </div>
      
      {/* 선과 점을 위한 SVG */}
      {processedValues.length > 1 && (
        <div className="absolute inset-0 overflow-visible pointer-events-none" style={{ zIndex: 100 }}>
          <svg 
            width="100%" 
            height="100%" 
            viewBox={`0 0 ${svgWidth} ${svgHeight}`} 
            preserveAspectRatio="none"
            style={{ position: 'absolute', top: 0, left: 0 }}
          >
            {/* 선 그리기 */}
            <polyline
              points={linePoints}
              fill="none"
              stroke="#0E7490" /* 막대그래프(bg-blue-300)보다 더 진한 파란색으로 변경 */
              strokeWidth="1.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
            
            {/* 포인트 그리기 */}
            {pointsData.map((point, idx) => (
              <circle
                key={`point-${idx}`}
                cx={point.x}
                cy={point.y}
                r="1.8"
                fill="#0E7490" /* 막대그래프(bg-blue-300)보다 더 진한 파란색으로 변경 */
                stroke="white"
                strokeWidth="0.3"
              />
            ))}
          </svg>
        </div>
      )}
    </div>
  );
};

// Helper function to parse numeric CSV values
const parseNumericValue = (value: string | undefined): number | null => {
  if (value === undefined || value === null || value.trim() === '' || value.trim() === '-') {
    return null; // Handle undefined, null, empty strings, and '-' as null
  }
  const cleanedValue = value.replace(/,/g, ''); // Remove commas
  const num = parseFloat(cleanedValue);
  return isNaN(num) ? null : num; // Return number or null if parsing failed
};

// 테이블 컬럼 정의 Helper
const columnHelper = createColumnHelper<ValuationData>();

const ValuationPage = () => {
  const [data, setData] = useState<ValuationData[]>([]);
  const [filteredData, setFilteredData] = useState<ValuationData[]>([]);
  const [sortedData, setSortedData] = useState<ValuationData[]>([]); // 정렬된 데이터 상태 추가
  const [csvHeaders, setCsvHeaders] = useState<string[]>([]); // CSV 헤더 상태 추가
  const [loading, setLoading] = useState(true);
  const [searchFilter, setSearchFilter] = useState('');
  const [industryFilter, setIndustryFilter] = useState('');
  const [industries, setIndustries] = useState<string[]>([]);
  // [중분류] 입력값 상태
  const [middleCategoryFilter, setMiddleCategoryFilter] = useState('');
  // [중분류] 목록 상태
  const [middleCategories, setMiddleCategories] = useState<string[]>([]);
  // [중분류] 선택된 값 상태
  const [selectedMiddleCategory, setSelectedMiddleCategory] = useState<string | null>(null);

  // 선택된 종목과 업종 상태
  const [selectedStock, setSelectedStock] = useState<{code: string, name: string} | null>(null);
  const [selectedIndustry, setSelectedIndustry] = useState<string | null>(null);
  
  // 전 종목 출력 상태
  const [showAllItems, setShowAllItems] = useState(false);
  // 전종목 출력 로딩 상태 추가
  const [isAllItemsLoading, setIsAllItemsLoading] = useState(false);
  
  // 페이지네이션 및 정렬 상태
  const [sorting, setSorting] = useState<SortingState>([]);
  const [currentPage, setCurrentPage] = useState<number>(1);
  const [rowsPerPage, setRowsPerPage] = useState<number>(21);
  
  // 테이블 복사 기능을 위한 ref 생성
  const tableRef = useRef<HTMLDivElement>(null);
  const headerRef = useRef<HTMLDivElement>(null);

  // 화면 크기에 따라 표시할 행 수를 업데이트하는 함수
  const tableContainerRef = useRef<HTMLDivElement>(null);
  const updateRowsPerPage = useCallback(() => {
    if (tableContainerRef.current) {
      const containerHeight = tableContainerRef.current.offsetHeight;
      // 헤더(60px), 페이지네이션(50px), 기타 여백(20px) 제외
      const availableHeight = containerHeight - 130;
      const rowHeight = 35; // 각 행의 높이 (패딩 포함)
      const calculatedRows = Math.max(5, Math.floor(availableHeight / rowHeight)); // 최소 5개 행 보장
      setRowsPerPage(calculatedRows);
    } else {
      // 기본값 설정 (컨테이너 참조가 아직 없을 때)
      setRowsPerPage(21); // 기본값으로 21 설정
    }
  }, []);

  // 현재 페이지 데이터 계산
  const currentPageData = useMemo(() => {
    if (showAllItems) {
      return sortedData;
    }
    const startIndex = (currentPage - 1) * rowsPerPage;
    return sortedData.slice(startIndex, startIndex + rowsPerPage);
  }, [sortedData, currentPage, rowsPerPage, showAllItems]);

  // 총 페이지 수 계산
  const totalPages = useMemo(() => {
    if (showAllItems) {
      return 1;
    }
    return Math.ceil(sortedData.length / rowsPerPage);
  }, [sortedData, rowsPerPage, showAllItems]);

  // 컬럼 정의 - 동적으로 헤더명 사용
  // 고정 컬럼 너비 정의 (데스크탑 환경에서 가로 스크롤이 생기지 않도록 너비 조정)
  const fixedColumnWidths = {
    stockCode: 83,    // 75 -> 83으로 10% 증가
    stockName: 146,   // 126 -> 146으로 증가 (20 증가)
    industry: 100,    // 120 -> 100으로 감소 (20 감소)
    middleCategory: 120, // 161 -> 120으로 줄여서 스크롤 방지
    marketCap: 75,    // 80 -> 72로 10% 더 감소
    per1: 60,         // 75 -> 60으로 더 줄임
    per2: 60,         // 75 -> 60으로 더 줄임
    per3: 60,         // 75 -> 60으로 더 줄임
    per4: 60,         // 75 -> 60으로 더 줄임
    per5: 60,         // 75 -> 60으로 더 줄임
  };
  
  const columns = useMemo(() => [
    columnHelper.accessor('stockCode', {
      header: () => csvHeaders[4] || '종목코드', // CSV 헤더 사용 (Index 4)
      cell: info => {
        // 종목코드가 항상 6자리로 표시되도록 수정
        const code = info.getValue();
        return code ? String(code).padStart(6, '0') : '';
      },
      size: fixedColumnWidths.stockCode,
      minSize: fixedColumnWidths.stockCode,
      maxSize: fixedColumnWidths.stockCode,
    }),
    columnHelper.accessor('stockName', {
      header: () => csvHeaders[5] || '종목명', // CSV 헤더 사용 (Index 5)
      cell: info => {
        const stockName = info.getValue();
        const stockCode = info.row.original.stockCode;
        
        return (
          <div 
            className="cursor-pointer hover:bg-[#e8f4f1] hover:text-blue-700 transition-colors duration-150 w-full h-full flex items-center px-1 -mx-1 truncate" // truncate 클래스 추가
            style={{ borderRadius: '4px' }}
            onClick={() => handleSelectStock(stockCode, stockName)}
            title={`${stockName} 선택하기`}
          >
            {stockName}
          </div>
        );
      },
      size: fixedColumnWidths.stockName,
      minSize: fixedColumnWidths.stockName,
      maxSize: fixedColumnWidths.stockName,
    }),
    columnHelper.accessor('industry', {
      header: () => csvHeaders[1] || '업종', // CSV 헤더 사용 (Index 1)
      cell: info => {
        const industry = info.getValue();
        
        return (
          <div 
            className="cursor-pointer hover:bg-[#e8f4f1] hover:text-blue-700 transition-colors duration-150 w-full h-full flex items-center px-1 -mx-1 truncate" // truncate 클래스 추가
            style={{ borderRadius: '4px' }}
            onClick={() => {
              if (industry) {
                setSelectedIndustry(industry);
                setIndustryFilter(''); // 선택 후 검색어 초기화
              }
            }}
            title={`${industry} 업종 선택하기`}
          >
            {industry}
          </div>
        );
      },
      size: fixedColumnWidths.industry,
      minSize: fixedColumnWidths.industry,
      maxSize: fixedColumnWidths.industry,
    }),
    columnHelper.accessor('middleCategory', {
      header: () => csvHeaders[3] || '중분류', // CSV 헤더 사용 (Index 3)
      cell: info => <div className="truncate">{info.getValue()}</div>, // truncate 클래스 추가
      size: fixedColumnWidths.middleCategory,
      minSize: fixedColumnWidths.middleCategory,
      maxSize: fixedColumnWidths.middleCategory,
    }),
    columnHelper.accessor('marketCap', {
      header: () => <div style={{ textAlign: 'center' }}>시가총액(억)</div>, // 헤더명 고정
      cell: info => {
        const value = info.getValue();
        if (value === null) return <div style={{ textAlign: 'right' }}></div>;
        if (value === 0) return <div style={{ textAlign: 'right' }}>0.00</div>;
        // 정수 콤마 포맷
        const displayValue = value > 0 ? value.toLocaleString('en-US', { maximumFractionDigits: 0 }) : value.toLocaleString('en-US', { maximumFractionDigits: 0 });
        return <div style={{ textAlign: 'right' }}>{displayValue}</div>;
      },
      size: fixedColumnWidths.marketCap,
      minSize: fixedColumnWidths.marketCap,
      maxSize: fixedColumnWidths.marketCap,
    }),
    // --- PER 컬럼 수정 시작 ---
    columnHelper.accessor('per1', { // 필드명 변경
      header: () => csvHeaders[10] || 'PER1', // CSV 헤더 사용 (Index 10)
      cell: info => {
        const value = info.getValue();
        if (value === null) return <div style={{ textAlign: 'right' }}></div>;
        if (value === 0) return <div style={{ textAlign: 'right' }}>0.00</div>;
        const displayValue = value.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
        return <div style={{ textAlign: 'right' }}>{displayValue}</div>;
      },
      size: fixedColumnWidths.per1, // 사이즈 키는 유지
      minSize: fixedColumnWidths.per1,
      maxSize: fixedColumnWidths.per1,
      enableSorting: true, // 정렬 활성화
    }),
    columnHelper.accessor('per2', { // 필드명 변경
      header: () => csvHeaders[11] || 'PER2', // CSV 헤더 사용 (Index 11)
      cell: info => {
        const value = info.getValue();
        if (value === null) return <div style={{ textAlign: 'right' }}></div>;
        if (value === 0) return <div style={{ textAlign: 'right' }}>0.00</div>;
        const displayValue = value.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
        return <div style={{ textAlign: 'right' }}>{displayValue}</div>;
      },
      size: fixedColumnWidths.per2, // 사이즈 키는 유지
      minSize: fixedColumnWidths.per2,
      maxSize: fixedColumnWidths.per2,
      enableSorting: true, // 정렬 활성화
    }),
    columnHelper.accessor('per3', { // 필드명 변경
      header: () => csvHeaders[12] || 'PER3', // CSV 헤더 사용 (Index 12)
      cell: info => {
        const value = info.getValue();
        if (value === null) return <div style={{ textAlign: 'right' }}></div>;
        if (value === 0) return <div style={{ textAlign: 'right' }}>0.00</div>;
        const displayValue = value.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
        return <div style={{ textAlign: 'right' }}>{displayValue}</div>;
      },
      size: fixedColumnWidths.per3, // 사이즈 키는 유지
      minSize: fixedColumnWidths.per3,
      maxSize: fixedColumnWidths.per3,
      enableSorting: true, // 정렬 활성화
    }),
    columnHelper.accessor('per4', { // 필드명 변경
      header: () => csvHeaders[13] || 'PER4', // CSV 헤더 사용 (Index 13)
      cell: info => {
        const value = info.getValue();
        if (value === null) return <div style={{ textAlign: 'right' }}></div>;
        if (value === 0) return <div style={{ textAlign: 'right' }}>0.00</div>;
        const displayValue = value.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
        return <div style={{ textAlign: 'right' }}>{displayValue}</div>;
      },
      size: fixedColumnWidths.per4, // 사이즈 키는 유지
      minSize: fixedColumnWidths.per4,
      maxSize: fixedColumnWidths.per4,
      enableSorting: true, // 정렬 활성화
    }),
    columnHelper.accessor('per5', { // 필드명 변경
      header: () => csvHeaders[14] || 'PER5', // CSV 헤더 사용 (Index 14)
      cell: info => {
        const value = info.getValue();
        if (value === null) return <div style={{ textAlign: 'right' }}></div>;
        if (value === 0) return <div style={{ textAlign: 'right' }}>0.00</div>;
        const displayValue = value.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
        return <div style={{ textAlign: 'right' }}>{displayValue}</div>;
      },
      size: fixedColumnWidths.per5, // 사이즈 키는 유지
      minSize: fixedColumnWidths.per5,
      maxSize: fixedColumnWidths.per5,
      enableSorting: true, // 정렬 활성화
    }),
    // --- PER 컬럼 수정 끝 ---
    
    // 추이 컬럼 추가
    columnHelper.display({
      id: 'trend',
      header: () => '추이',
      cell: ({ row }) => {
        const trendValues = ['per1', 'per3', 'per4', 'per5'].map(
          (colId) => typeof row.original[colId as keyof ValuationData] === 'number' ? row.original[colId as keyof ValuationData] : 0
        );
        return <TrendBarGraph values={trendValues} />;
      },
      size: 200, // 추이 컬럼 너비 증가
      minSize: 150,
      maxSize: 300,
    }),
  ], [selectedStock, selectedIndustry, csvHeaders]); // csvHeaders 의존성 추가

  // 날짜 데이터 로드 useEffect
  const [updateDate, setUpdateDate] = useState<string | null>(null); // 업데이트 날짜 상태 추가
  const [loadingDate, setLoadingDate] = useState<boolean>(true); // 날짜 로딩 상태 추가
  const [errorDate, setErrorDate] = useState<string | null>(null); // 날짜 로딩 오류 상태 추가

  useEffect(() => {
    const loadUpdateDate = async () => {
      setLoadingDate(true);
      setErrorDate(null);
      try {
        // fetch 경로를 사용자의 원래 요청대로 today_price_etf.csv로 되돌림
        const response = await fetch('/requestfile/today_price_etf/today_price_etf.csv'); 
        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`);
        }
        const csvText = await response.text();
        
        // PapaParse를 사용하여 CSV 파싱
        Papa.parse(csvText, {
          header: true,
          skipEmptyLines: true,
          complete: (results) => {
            if (results.errors.length > 0) {
              console.error('CSV 파싱 오류:', results.errors);
              setErrorDate('날짜 데이터 파싱 중 오류가 발생했습니다.');
              return;
            }
            
            const parsedData = results.data as Record<string, string>[];
            
            if (parsedData && parsedData.length > 0) {
              const dateString = parsedData[0]['날짜']; // 첫 번째 행의 '날짜' 컬럼 값
              if (dateString) {
                const formattedDate = formatDateMMDD(dateString); // MM/DD 형식으로 변환
                if (formattedDate) {
                  setUpdateDate(formattedDate); // 상태 업데이트
                } else {
                  setErrorDate('날짜 형식이 올바르지 않습니다.');
                }
              } else {
                setErrorDate('CSV에서 날짜 정보를 찾을 수 없습니다.');
              }
            } else {
              setErrorDate('날짜 데이터가 비어있습니다.');
            }
          },
          error: (error: any) => {
            console.error('CSV 파싱 중 심각한 오류:', error);
            setErrorDate('날짜 데이터 파싱 중 심각한 오류가 발생했습니다.');
          }
        });
      } catch (err: unknown) {
        console.error('날짜 데이터 로딩 오류:', err);
        setErrorDate('날짜 데이터를 불러오는 데 실패했습니다.');
        if (err instanceof Error) {
          setErrorDate(`날짜 데이터를 불러오는 데 실패했습니다: ${err.message}`);
        } else {
          setErrorDate('알 수 없는 오류로 날짜 데이터를 불러오는 데 실패했습니다.');
        }
      } finally {
        setLoadingDate(false);
      }
    };

    loadUpdateDate();
  }, []); // 컴포넌트 마운트 시 한 번만 실행

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      const csvUrl = '/requestfile/value/per.csv'; // 실제 CSV 파일 경로
      try {
        const response = await fetch(csvUrl);
        if (!response.ok) { // 응답 상태 확인
          throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        // --- EUC-KR 인코딩 처리 수정 ---
        // 응답을 ArrayBuffer로 받아 UTF-8로 디코딩
        const buffer = await response.arrayBuffer();
        const decoder = new TextDecoder('utf-8');
        const csvText = decoder.decode(buffer);
        // --- EUC-KR 인코딩 처리 수정 끝 ---
        
        // PapaParse 설정: 헤더 사용 안함
        Papa.parse(csvText, {
          header: false, // 헤더 사용 안함
          skipEmptyLines: true,
          encoding: 'UTF-8', // 인코딩 추가
          complete: (results) => {
            // 첫 번째 행을 헤더로 저장
            const headers = results.data[0] as string[] || [];
            setCsvHeaders(headers);
            
            // 첫 번째 행은 헤더 정보이므로 건너뜀 (데이터는 두 번째 행부터 시작)
            // ValuationData 타입 적용 및 숫자 변환 로직 추가
            const parsedData: ValuationData[] = (results.data as string[][]).slice(1).map((row) => ({
              stockCode: (row[4] || '').padStart(6, '0'), // 종목코드가 항상 6자리로 표시되도록 수정
              stockName: row[5] || '', // E열
              industry: row[1] || '', // B열
              middleCategory: row[3] || '', // D열 - 중분류로 변경
              marketCap: parseNumericValue(row[6]), // G열 - parseNumericValue 적용
              per1: parseNumericValue(row[10]), // K열 - parseNumericValue 적용
              per2: parseNumericValue(row[11]), // L열 - parseNumericValue 적용
              per3: parseNumericValue(row[12]), // M열 - parseNumericValue 적용
              per4: parseNumericValue(row[13]), // N열 - parseNumericValue 적용
              per5: parseNumericValue(row[14]), // O열 - parseNumericValue 적용
            }));

            // 업종 목록 추출 (중복 제거 및 정렬)
            const uniqueIndustries = Array.from(new Set(parsedData.map(item => item.industry))).sort();
            setIndustries(uniqueIndustries);
            // [중분류] 목록 추출 (중복 제거 및 정렬)
            const uniqueMiddleCategories = Array.from(new Set(parsedData.map(item => item.middleCategory))).sort();
            setMiddleCategories(uniqueMiddleCategories);

            setData(parsedData);
            setFilteredData(parsedData); // 초기 필터링 데이터 설정
            setLoading(false);
          },
          error: (error: any) => {
            console.error("Error parsing CSV:", error);
            setLoading(false);
          }
        });
      } catch (error: unknown) {
        console.error("Error fetching or decoding CSV data:", error); // 에러 메시지 수정
        setLoading(false);
      }
    };

    fetchData();
    
    // 화면 크기 변경 감지
    updateRowsPerPage(); // 초기 로드 시 행 수 계산
    window.addEventListener('resize', updateRowsPerPage);

    // 컴포넌트 언마운트 시 이벤트 리스너 제거
    return () => {
      window.removeEventListener('resize', updateRowsPerPage);
    };
  }, [updateRowsPerPage]); // updateRowsPerPage를 의존성 배열에 추가

  // 정렬 로직 구현 - 모든 데이터 기준으로 정렬
  useEffect(() => {
    if (sorting.length > 0) {
      const sorted = [...filteredData].sort((a, b) => {
        for (const { id, desc } of sorting) {
          const multiplier = desc ? -1 : 1;
          const aValue = a[id as keyof ValuationData];
          const bValue = b[id as keyof ValuationData];

          // 숫자 컬럼인지 확인 (타입이 number인 경우)
          if (typeof aValue === 'number' || typeof bValue === 'number' || aValue === null || bValue === null) {
            // null 값 처리: null은 가장 작은 값으로 간주
            const aNum = aValue === null ? -Infinity : Number(aValue);
            const bNum = bValue === null ? -Infinity : Number(bValue);
            
            if (aNum < bNum) return -1 * multiplier;
            if (aNum > bNum) return 1 * multiplier;

          } else {
            // 문자열 비교 (업종, 종목명, 종목코드 등 - null/undefined 안전 처리)
            const aStr = String(aValue || '').toLowerCase(); 
            const bStr = String(bValue || '').toLowerCase();
            if (aStr < bStr) return -1 * multiplier;
            if (aStr > bStr) return 1 * multiplier;
          }
        }
        return 0;
      });
      setSortedData(sorted);
    } else {
      setSortedData(filteredData); // 정렬 조건이 없으면 필터링된 데이터 사용
    }
  }, [sorting, filteredData]); // 의존성 배열에 filteredData 추가

  // 필터 적용 효과
  useEffect(() => {
    // 필터링 로직 (종목명/코드, 업종, 중분류 순서로 적용)
    let result = [...data];
    
    // 종목명 또는 종목코드 필터 적용
    if (selectedStock) {
      // 선택된 종목이 있는 경우 (종목코드로만 매칭)
      result = result.filter(item => 
        item.stockCode === selectedStock.code
      );
    } else if (searchFilter) {
      // 검색어가 있는 경우
      const searchTerm = searchFilter.toLowerCase();
      result = result.filter(item => 
        (item.stockName && item.stockName.toLowerCase().includes(searchTerm)) || 
        (item.stockCode && item.stockCode.toLowerCase().includes(searchTerm))
      );
    }
    
    // 업종 필터 적용
    if (selectedIndustry) {
      // 선택된 업종이 있는 경우
      result = result.filter(item => 
        item.industry === selectedIndustry
      );
    } else if (industryFilter) {
      // 업종 검색어가 있는 경우
      result = result.filter(item => 
        item.industry.toLowerCase().includes(industryFilter.toLowerCase())
      );
    }
    
    // [중분류] 필터 적용
    if (selectedMiddleCategory) {
      // 선택된 중분류가 있는 경우
      result = result.filter(item => item.middleCategory === selectedMiddleCategory);
    } else if (middleCategoryFilter) {
      // 중분류 검색어가 있는 경우
      result = result.filter(item => item.middleCategory.toLowerCase().includes(middleCategoryFilter.toLowerCase()));
    }

    setFilteredData(result);
    setCurrentPage(1); // 필터 변경 시 첫 페이지로 이동
  }, [data, searchFilter, industryFilter, selectedStock, selectedIndustry, middleCategoryFilter, selectedMiddleCategory]);

  // 종목 선택 기능
  const handleSelectStock = (stockCode: string, stockName: string) => {
    setSelectedStock({
      code: stockCode,
      name: stockName
    });
    setSearchFilter(''); // 선택 후 검색어 초기화
  };

  // 업종 선택 기능
  useEffect(() => {
    if (industryFilter.trim()) {
      // 정확히 일치하는 업종 찾기
      const foundIndustry = industries.find(industry => 
        industry.toLowerCase().includes(industryFilter.toLowerCase())
      );
      
      if (foundIndustry) {
        setSelectedIndustry(foundIndustry);
        setIndustryFilter(''); // 선택 후 검색어 초기화
      }
    }
  }, [industryFilter, industries]);

  // [중분류] 선택 기능
  useEffect(() => {
    if (middleCategoryFilter.trim()) {
      // 정확히 일치하는 중분류 찾기
      const foundMiddleCategory = middleCategories.find(category => 
        category.toLowerCase().includes(middleCategoryFilter.toLowerCase())
      );
      
      if (foundMiddleCategory) {
        setSelectedMiddleCategory(foundMiddleCategory);
        setMiddleCategoryFilter(''); // 선택 후 검색어 초기화
      }
    }
  }, [middleCategoryFilter, middleCategories]);

  // 선택된 종목 해제 핸들러
  const handleClearSelectedStock = () => {
    setSelectedStock(null);
    setSearchFilter('');
  };
  
  // 선택된 업종 해제 핸들러
  const handleClearSelectedIndustry = () => {
    setSelectedIndustry(null);
    setIndustryFilter('');
  };
  
  // [중분류] 선택 해제 핸들러
  const handleClearSelectedMiddleCategory = () => {
    setSelectedMiddleCategory(null);
    setMiddleCategoryFilter('');
  };

  // 컬럼 너비 상태 추가 - 고정 너비 사용
  const [columnSizes, setColumnSizes] = useState<Record<string, number>>(() => {
    // 초기 컬럼 너비 설정
    const initialSizes: Record<string, number> = {};
    Object.keys(fixedColumnWidths).forEach(columnId => {
      initialSizes[columnId] = fixedColumnWidths[columnId as keyof typeof fixedColumnWidths];
    });
    return initialSizes;
  });

  // 페이지네이션 및 정렬을 위한 테이블 인스턴스 생성
  const table = useReactTable({
    data: showAllItems ? sortedData : currentPageData, // 전 종목 출력 여부에 따라 데이터 소스 변경
    columns,
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    // debugTable: true, // 디버깅 필요시 활성화
    state: {
      sorting,
      columnSizing: columnSizes,
    },
    columnResizeMode: 'onChange',
    enableColumnResizing: false, // 컬럼 크기 조정 비활성화
    defaultColumn: {
      minSize: 50,
      size: 150,
      maxSize: 300,
    },
  });

  // 컬럼 너비 가져오는 함수
  const getColumnWidth = (columnId: string) => {
    // 고정된 너비 값 반환
    const fixedWidth = fixedColumnWidths[columnId as keyof typeof fixedColumnWidths];
    return fixedWidth || columnSizes[columnId] || 150; // 기본값 150px
  };

  // 검색어 입력 시 엔터키 처리 함수
  const handleSearchKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    // 엔터키 입력 시
    if (e.key === 'Enter') {
      // 검색어가 있고, 필터링된 결과가 1개인 경우
      if (searchFilter.trim() && filteredData.length === 1) {
        // 해당 종목 선택
        handleSelectStock(filteredData[0].stockCode, filteredData[0].stockName);
      }
    }
  };

  // 전종목 출력 처리 함수
  const handleShowAllItems = async () => {
    try {
      // 이미 로딩 중이면 중복 실행 방지
      if (isAllItemsLoading) return;
      
      // 전종목 출력 중이면 바로 끄기
      if (showAllItems) {
        setShowAllItems(false);
        return;
      }
      
      // 버튼 상태 즉시 변경 (UI 반응성 향상)
      setShowAllItems(true);
      
      // 전종목 출력 전환 로딩 상태 활성화
      setIsAllItemsLoading(true);
      
      // 비동기 작업 시뮬레이션 (실제로는 데이터 로딩/필터링에 시간이 걸림)
      // setTimeout으로 비동기 작업을 시뮬레이션하지만, 
      // 실제로는 다음 이벤트 루프에서 무거운 데이터 처리가 일어나므로 UI가 업데이트됨
      await new Promise(resolve => setTimeout(resolve, 50));
      
      // 로딩 상태 비활성화
      setIsAllItemsLoading(false);
    } catch (error: unknown) {
      console.error('전종목 출력 처리 중 오류:', error);
      setIsAllItemsLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex-1 p-0 sm:p-2 md:p-4 overflow-hidden ml-0 md:ml-16 w-full flex flex-col">
        <div className="max-w-[1280px] mx-auto w-full flex-1 flex flex-col overflow-hidden"> {/* overflow-hidden 추가 */}
          <div className="flex items-center justify-center h-screen">
            <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-gray-900"></div>
            <span className="ml-3 text-gray-700">데이터 로딩 중...</span>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 p-0 sm:p-2 md:p-4 overflow-auto w-full">
      {/* 메인 콘텐츠 영역 - 모바일 최적화 */}
      <div className="w-full max-w-[1280px] mx-auto"> 
        {/* 테이블 섹션 컨테이너 (rs-rank 페이지와 유사하게) */}
        <div className="mb-2 md:mb-4">
          {/* 내부 컨테이너 (하단 마진 제거) */}
          <div className="bg-white rounded-md shadow p-2 md:p-4">
            {/* 내부 패딩 조정: 하단 패딩(pb) 제거 */}
            <div className="bg-white rounded border border-gray-100 p-2 md:p-4 h-auto"> 
              {/* 제목과 날짜를 그룹화하는 div */}
              <div className="flex flex-col sm:flex-row items-start sm:items-center mb-3">
                <h2 className="font-semibold whitespace-nowrap" style={{ fontSize: 'clamp(0.9rem, 0.5vw + 0.85rem, 1rem)' }}>밸류에이션</h2>
              </div>
              
              {/* 필터 섹션 */}
              <div className="flex flex-wrap items-center gap-2 sm:gap-4 mb-2 md:mb-4">
                {/* 종목명/종목코드 검색 필터 */}
                <div className="flex items-center">
                  <label htmlFor="searchFilter" className="text-[10px] sm:text-xs font-medium text-gray-700 mr-1 sm:mr-2 whitespace-nowrap">
                    종목명/종목코드
                  </label>
                  {selectedStock ? (
                    <button
                      onClick={handleClearSelectedStock}
                      className="px-2 sm:px-3 py-1 bg-[#D8EFE9] text-gray-700 rounded text-[10px] sm:text-xs hover:bg-[#c5e0da] focus:outline-none flex items-center"
                      style={{ height: '35px', borderRadius: '4px' }}
                    >
                      <span>{selectedStock.name} ({selectedStock.code})</span>
                      <span className="ml-1">×</span>
                    </button>
                  ) : (
                    <div className="flex items-center">
                      <input
                        id="searchFilter"
                        type="text"
                        value={searchFilter}
                        onChange={(e) => setSearchFilter(e.target.value)}
                        onKeyDown={handleSearchKeyDown}
                        placeholder="종목명/종목코드 입력"
                        className="px-2 sm:px-3 border border-gray-300 text-[10px] sm:text-xs focus:outline-none focus:ring-2 focus:ring-[#D8EFE9] focus:border-transparent"
                        style={{ 
                          width: 'clamp(120px, 15vw, 180px)',
                          height: '35px',
                          borderRadius: '4px'
                        }}
                      />
                    </div>
                  )}
                </div>
                
                {/* 업종 선택 필터 */}
                <div className="flex flex-row items-center ml-1 sm:ml-2">
                  <label htmlFor="industryFilter" className="text-[10px] sm:text-xs font-medium text-gray-700 mr-1 sm:mr-2 whitespace-nowrap">
                    업종
                  </label>
                  {selectedIndustry ? (
                    <button
                      onClick={handleClearSelectedIndustry}
                      className="px-2 sm:px-3 py-1 bg-[#D8EFE9] text-gray-700 rounded text-[10px] sm:text-xs hover:bg-[#c5e0da] focus:outline-none flex items-center"
                      style={{ height: '35px', borderRadius: '4px' }}
                    >
                      <span>{selectedIndustry}</span>
                      <span className="ml-1">×</span>
                    </button>
                  ) : (
                    <div className="flex items-center">
                      <input
                        list="industryOptions"
                        id="industryFilter"
                        value={industryFilter}
                        onChange={(e) => setIndustryFilter(e.target.value)}
                        placeholder="업종 선택 또는 입력..."
                        autoComplete="off" // 브라우저 자동완성(검색 기록) 비활성화
                        className="px-2 sm:px-3 border border-gray-300 text-[10px] sm:text-xs focus:outline-none focus:ring-2 focus:ring-[#D8EFE9] focus:border-transparent"
                        style={{ 
                          width: 'clamp(100px, 12vw, 150px)',
                          height: '35px',
                          borderRadius: '4px'
                        }}
                      />
                      <datalist id="industryOptions">
                        <option value="">전체 업종</option>
                        {industries.map((industry, index) => (
                          <option key={index} value={industry}>
                            {industry}
                          </option>
                        ))}
                      </datalist>
                    </div>
                  )}
                </div>
                
                {/* [중분류] 선택 필터 */}
                <div className="flex flex-row items-center ml-1 sm:ml-2">
                  <label htmlFor="middleCategoryFilter" className="text-[10px] sm:text-xs font-medium text-gray-700 mr-1 sm:mr-2 whitespace-nowrap">
                    중분류
                  </label>
                  {selectedMiddleCategory ? (
                    <button
                      onClick={handleClearSelectedMiddleCategory}
                      className="px-2 sm:px-3 py-1 bg-[#D8EFE9] text-gray-700 rounded text-[10px] sm:text-xs hover:bg-[#c5e0da] focus:outline-none flex items-center"
                      style={{ height: '35px', borderRadius: '4px' }}
                    >
                      <span>{selectedMiddleCategory}</span>
                      <span className="ml-1">×</span>
                    </button>
                  ) : (
                    <div className="flex items-center">
                      <input
                        list="middleCategoryOptions"
                        id="middleCategoryFilter"
                        value={middleCategoryFilter}
                        onChange={(e) => setMiddleCategoryFilter(e.target.value)}
                        placeholder="중분류 선택 또는 입력..."
                        autoComplete="off" // 브라우저 자동완성(검색 기록) 비활성화
                        className="px-2 sm:px-3 border border-gray-300 text-[10px] sm:text-xs focus:outline-none focus:ring-2 focus:ring-[#D8EFE9] focus:border-transparent"
                        style={{ 
                          width: 'clamp(100px, 12vw, 150px)',
                          height: '35px',
                          borderRadius: '4px'
                        }}
                      />
                      <datalist id="middleCategoryOptions">
                        <option value="">전체 중분류</option>
                        {middleCategories.map((category, index) => (
                          <option key={index} value={category}>
                            {category}
                          </option>
                        ))}
                      </datalist>
                    </div>
                  )}
                </div>
                
                {/* 필터 초기화 버튼 */}
                <div className="flex items-center ml-1 sm:ml-2">
                  <button
                    onClick={() => {
                      setSearchFilter('');
                      setIndustryFilter('');
                      setSelectedStock(null);
                      setSelectedIndustry(null);
                      setMiddleCategoryFilter('');
                      setSelectedMiddleCategory(null);
                    }}
                    className="px-2 sm:px-3 bg-gray-200 text-gray-700 text-[10px] sm:text-xs hover:bg-gray-300 focus:outline-none"
                    style={{ 
                      height: '35px',
                      borderRadius: '4px'
                    }}
                  >
                    초기화
                  </button>
                </div>
                
                {/* 전 종목 출력 버튼 */}
                <div className="flex items-center ml-1 sm:ml-2">
                  <label className="flex items-center cursor-pointer">
                    <input
                      type="checkbox"
                      checked={showAllItems}
                      onChange={handleShowAllItems}
                      className="sr-only"
                    />
                    <div className={`w-9 h-5 flex items-center rounded-full p-1 duration-300 ease-in-out ${showAllItems ? 'bg-[#D8EFE9]' : 'bg-gray-300'}`}>
                      <div className={`bg-white w-4 h-4 rounded-full shadow-md transform duration-300 ease-in-out ${showAllItems ? 'translate-x-4' : ''}`}></div>
                    </div>
                    <span className="ml-2 text-[10px] sm:text-xs text-gray-700">전 종목 출력</span>
                  </label>
                  {/* 로딩 스피너 추가 */}
                  {isAllItemsLoading && (
                    <div className="ml-2 animate-spin h-4 w-4">
                      <svg className="h-4 w-4 text-blue-500" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                      </svg>
                    </div>
                  )}
                </div>
                
                {/* 업데이트 날짜 표시 영역 추가 - ml-auto 적용, self-end 추가 */}
                <div className="text-gray-600 text-xs ml-auto self-end" style={{ fontSize: 'clamp(0.7rem, 0.7vw, 0.7rem)' }}>
                  {loadingDate ? (
                    <span>날짜 로딩 중...</span>
                  ) : errorDate ? (
                    <span className="text-red-500">{errorDate}</span>
                  ) : updateDate ? (
                    <span>updated 17:00 {updateDate}</span>
                  ) : (
                    <span>날짜 정보 없음</span> // 로딩 완료 후에도 날짜가 없을 경우
                  )}
                </div>
              </div>
              
              {/* 전종목 출력 로딩 상태 표시 */}
              {showAllItems && isAllItemsLoading && (
                <div className="flex items-center justify-center h-screen">
                  <div className="text-xl">전 종목 데이터를 불러오는 중...</div>
                </div>
              )}
              
              {/* 테이블 */}
              {!isAllItemsLoading && (
                <div 
                  // 테이블 래퍼에 가로 스크롤 추가하고 부모 너비 따르도록 w-full 추가
                  className="table-container overflow-x-auto w-full" 
                  ref={tableRef}
                >
                  <table className="w-full min-w-[860px] border border-gray-200">
                    <thead className="bg-gray-100">
                      <tr>
                        {table.getHeaderGroups().map(headerGroup => (
                          headerGroup.headers.map(header => (
                            <th
                              key={header.id}
                              scope="col"
                              /* 모바일 좌우 패딩 px-0.5 -> px-1로 변경 */
                              className={`px-1 md:px-2 py-2 text-center text-[9px] sm:text-[10px] md:text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer border border-gray-200 ${
                                // 모바일에서 특정 컬럼 숨김 처리
                                header.id === 'stockCode' || header.id === 'marketCap' ? 'hidden sm:table-cell' : ''
                              }`}
                              style={{ 
                                width: `${getColumnWidth(header.id)}px`,
                                height: '35px',
                                minWidth: `${getColumnWidth(header.id)}px`,
                                maxWidth: `${getColumnWidth(header.id)}px`
                              }}
                              onClick={header.column.getToggleSortingHandler()}
                            >
                              <div className="flex justify-center items-center">
                                {flexRender(
                                  header.column.columnDef.header,
                                  header.getContext()
                                )}
                                {header.column.getIsSorted() ? (
                                  header.column.getIsSorted() === 'asc' ? (
                                    <span className="ml-1">↑</span>
                                  ) : (
                                    <span className="ml-1">↓</span>
                                  )
                                ) : null}
                              </div>
                            </th>
                          ))
                        ))}
                      </tr>
                    </thead>
                    <tbody className="bg-white">
                      {table.getRowModel().rows.map((row, rowIndex) => (
                        <tr key={row.id} className={rowIndex % 2 === 0 ? 'bg-gray-50' : 'bg-white'}>
                          {row.getVisibleCells().map(cell => (
                            <td
                              key={cell.id}
                              /* 모바일 좌우 패딩 px-0.5 -> px-1로 변경 */
                              className={`px-1 md:px-2 py-1 whitespace-nowrap text-[9px] sm:text-[10px] md:text-xs border border-gray-200 ${
                                // 컬럼별 정렬 방식 적용
                                cell.column.id === 'stockCode' ? 'text-center' :
                                cell.column.id === 'stockName' || cell.column.id === 'industry' || cell.column.id === 'middleCategory' ? 'text-left' :
                                'text-right'
                              } ${
                                // 모바일에서 특정 컬럼 숨김 처리
                                cell.column.id === 'stockCode' || cell.column.id === 'marketCap' ? 'hidden sm:table-cell' : ''
                              }`}
                              style={{ 
                                width: `${getColumnWidth(cell.column.id)}px`,
                                height: '35px',
                                minWidth: `${getColumnWidth(cell.column.id)}px`,
                                maxWidth: `${getColumnWidth(cell.column.id)}px`
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
              )}
              
              {/* 페이지네이션 추가 */}
              {!showAllItems && (
                <div className="mt-4 flex justify-center"> {/* RS 순위 페이지와 동일하게 상단 여백 mt-4로 변경하고 하단 여백 제거 */}
                  <div className="flex items-center space-x-1">
                    <button
                      className="px-2 py-1 bg-gray-200 rounded hover:bg-gray-300 text-sm"
                      style={{ fontSize: 'clamp(0.65rem, 0.7vw, 0.7rem)' }}
                      onClick={() => setCurrentPage(1)}
                      disabled={currentPage === 1}
                    >
                      <span className="hidden sm:inline">처음</span>
                      <span className="sm:hidden">«</span>
                    </button>
                    <button
                      className="px-2 py-1 bg-gray-200 rounded hover:bg-gray-300 text-sm"
                      style={{ fontSize: 'clamp(0.65rem, 0.7vw, 0.7rem)' }}
                      onClick={() => setCurrentPage(currentPage - 1)}
                      disabled={currentPage === 1}
                    >
                      <span className="hidden sm:inline">이전</span>
                      <span className="sm:hidden">‹</span>
                    </button>
                    
                    {/* 페이지 번호 버튼 - 모바일에서는 줄이고 PC에서는 더 많이 표시 */}
                    {Array.from({ length: totalPages }).map((_, index) => {
                      const pageNumber = index + 1;
                      // 모바일에서는 현재 페이지 주변 1개만 표시, PC에서는 2개 표시
                      const visibleOnMobile = Math.abs(pageNumber - currentPage) <= 1;
                      const visibleOnDesktop = Math.abs(pageNumber - currentPage) <= 2;
                      
                      if (visibleOnDesktop) {
                        return (
                          <button
                            key={index}
                            className={`w-8 py-1 flex justify-center ${
                              pageNumber === currentPage
                                ? 'bg-[#D8EFE9] text-gray-700 rounded'
                                : 'bg-gray-200 rounded hover:bg-gray-300'
                            } text-sm ${!visibleOnMobile ? 'hidden sm:inline-block' : ''}`}
                            style={{ fontSize: 'clamp(0.65rem, 0.7vw, 0.7rem)' }}
                            onClick={() => setCurrentPage(pageNumber)}
                          >
                            {pageNumber}
                          </button>
                        );
                      }
                      return null;
                    })}
                    
                    <button
                      className="px-2 py-1 bg-gray-200 rounded hover:bg-gray-300 text-sm"
                      style={{ fontSize: 'clamp(0.65rem, 0.7vw, 0.7rem)' }}
                      onClick={() => setCurrentPage(currentPage + 1)}
                      disabled={currentPage === totalPages}
                    >
                      <span className="hidden sm:inline">다음</span>
                      <span className="sm:hidden">›</span>
                    </button>
                    <button
                      className="px-2 py-1 bg-gray-200 rounded hover:bg-gray-300 text-sm"
                      style={{ fontSize: 'clamp(0.65rem, 0.7vw, 0.7rem)' }}
                      onClick={() => setCurrentPage(totalPages)}
                      disabled={currentPage === totalPages}
                    >
                      <span className="hidden sm:inline">마지막</span>
                      <span className="sm:hidden">»</span>
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ValuationPage;