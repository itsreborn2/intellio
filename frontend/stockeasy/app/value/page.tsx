'use client';

import React, { useState, useEffect, useMemo, useRef } from 'react';
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

// CSV 데이터 타입 정의
interface ValuationData {
  stockCode: string;      // C열: 종목코드
  stockName: string;      // D열: 종목명
  industry: string;       // B열: 업종
  marketCap: string;      // 시가총액
  tradingVolume: string;  // 거래대금 (사용하지 않음)
  per2024E: string;       // I열: 2024(E) PER
  per2025E: string;       // J열: 2025(E) PER
  per2026E: string;       // K열: 2026(E) PER
  per2027E: string;       // L열: 2027(E) PER
  per2028E: string;       // M열: 2028(E) PER
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
                className="w-full bg-blue-300 rounded-sm"
                style={{ height: minHeightStyle }}
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

// 테이블 컬럼 정의 Helper
const columnHelper = createColumnHelper<ValuationData>();

const ValuationPage = () => {
  const [data, setData] = useState<ValuationData[]>([]);
  const [filteredData, setFilteredData] = useState<ValuationData[]>([]);
  const [loading, setLoading] = useState(true);
  const [sorting, setSorting] = useState<SortingState>([]);
  const [headers, setHeaders] = useState<string[]>([]);
  const [currentPage, setCurrentPage] = useState<number>(1);
  const [rowsPerPage, setRowsPerPage] = useState<number>(21); // 한 페이지에 표시할 행 수
  
  // 필터 상태 추가
  const [searchFilter, setSearchFilter] = useState<string>('');
  const [industryFilter, setIndustryFilter] = useState<string>('');
  const [industries, setIndustries] = useState<string[]>([]);
  
  // 선택된 종목과 업종 상태
  const [selectedStock, setSelectedStock] = useState<{code: string, name: string} | null>(null);
  const [selectedIndustry, setSelectedIndustry] = useState<string | null>(null);
  
  // 전 종목 출력 상태
  const [showAllItems, setShowAllItems] = useState(false);
  // 전종목 출력 로딩 상태 추가
  const [isAllItemsLoading, setIsAllItemsLoading] = useState(false);
  
  // 테이블 복사 기능을 위한 ref 생성
  const tableRef = useRef<HTMLDivElement>(null);
  const headerRef = useRef<HTMLDivElement>(null);

  // 컬럼 정의 - 동적으로 헤더명 사용
  // 고정 컬럼 너비 정의 (데스크탑 환경에서 가로 스크롤이 생기지 않도록 너비 조정)
  const fixedColumnWidths = {
    stockCode: 83,    // 75 -> 83으로 10% 증가
    stockName: 126,   // 140 -> 126으로 10% 감소
    industry: 161,    // 146 -> 161로 10% 더 확장
    marketCap: 72,    // 80 -> 72로 10% 더 감소
    per2024E: 75,     // 80 -> 75로 줄임
    per2025E: 75,     // 80 -> 75로 줄임
    per2026E: 75,     // 80 -> 75로 줄임
    per2027E: 75,     // 80 -> 75로 줄임
    per2028E: 75      // 80 -> 75로 줄임
  };
  
  const columns = useMemo(() => [
    columnHelper.accessor('stockCode', {
      header: () => headers[2] || '종목코드', // C열 헤더
      cell: info => {
        // 종목코드가 있을 경우 6자리로 표시 (앞에 0 채우기)
        const code = info.getValue();
        return code ? String(code).padStart(6, '0') : '';
      },
      size: fixedColumnWidths.per2024E,
      minSize: fixedColumnWidths.per2024E,
      maxSize: fixedColumnWidths.per2024E,
    }),
    columnHelper.accessor('stockName', {
      header: () => headers[3] || '종목명', // D열 헤더
      cell: info => {
        const stockName = info.getValue();
        const stockCode = info.row.original.stockCode;
        
        return (
          <div 
            className="cursor-pointer hover:bg-[#e8f4f1] hover:text-blue-700 transition-colors duration-150 w-full h-full flex items-center px-1 -mx-1"
            style={{ borderRadius: '4px' }}
            onClick={() => handleSelectStock(stockCode, stockName)}
            title={`${stockName} 선택하기`}
          >
            {stockName}
          </div>
        );
      },
      size: fixedColumnWidths.industry,
      minSize: fixedColumnWidths.industry,
      maxSize: fixedColumnWidths.industry,
    }),
    columnHelper.accessor('industry', {
      header: () => headers[1] || '업종', // B열 헤더
      cell: info => {
        const industry = info.getValue();
        
        return (
          <div 
            className="cursor-pointer hover:bg-[#e8f4f1] hover:text-blue-700 transition-colors duration-150 w-full h-full flex items-center px-1 -mx-1 overflow-hidden"
            style={{ borderRadius: '4px' }}
            onClick={() => {
              if (industry) {
                setSelectedIndustry(industry);
                setIndustryFilter(''); // 선택 후 검색어 초기화
              }
            }}
            title={`${industry} 업종 선택하기`}
          >
            {/* 업종명이 길 경우 말줄임표(...) 처리 */}
            <div className="truncate">{industry}</div>
          </div>
        );
      },
      size: fixedColumnWidths.industry,
      minSize: fixedColumnWidths.industry,
      maxSize: fixedColumnWidths.industry,
    }),
    columnHelper.accessor('marketCap', {
      header: () => '시가총액(백억)',
      cell: info => formatMarketCapToHundredBillion(info.getValue()),
      size: fixedColumnWidths.marketCap,
      minSize: fixedColumnWidths.marketCap,
      maxSize: fixedColumnWidths.marketCap,
    }),
    columnHelper.accessor('per2024E', {
      header: () => headers[8] || '2024(E) PER', // I열 헤더
      cell: info => info.getValue(),
      size: fixedColumnWidths.per2024E,
      minSize: fixedColumnWidths.per2024E,
      maxSize: fixedColumnWidths.per2024E,
    }),
    columnHelper.accessor('per2025E', {
      header: () => headers[9] || '2025(E) PER', // J열 헤더
      cell: info => info.getValue(),
      size: fixedColumnWidths.per2024E,
      minSize: fixedColumnWidths.per2024E,
      maxSize: fixedColumnWidths.per2024E,
    }),
    columnHelper.accessor('per2026E', {
      header: () => headers[10] || '2026(E) PER', // K열 헤더
      cell: info => info.getValue(),
      size: fixedColumnWidths.per2024E,
      minSize: fixedColumnWidths.per2024E,
      maxSize: fixedColumnWidths.per2024E,
    }),
    columnHelper.accessor('per2027E', {
      header: () => headers[11] || '2027(E) PER', // L열 헤더
      cell: info => info.getValue(),
      size: fixedColumnWidths.per2024E,
      minSize: fixedColumnWidths.per2024E,
      maxSize: fixedColumnWidths.per2024E,
    }),
    columnHelper.accessor('per2028E', {
      header: () => headers[12] || '2028(E) PER', // M열 헤더
      cell: info => info.getValue(),
      size: fixedColumnWidths.per2024E,
      minSize: fixedColumnWidths.per2024E,
      maxSize: fixedColumnWidths.per2024E,
    }),
    // "추이" 컬럼 추가
    columnHelper.display({
      id: 'trend',
      header: () => '추이',
      cell: info => {
        const rowData = info.row.original;
        const values = [
          rowData.per2025E,
          rowData.per2026E,
          rowData.per2027E,
          rowData.per2028E,
        ];
        return <TrendBarGraph values={values} />;
      },
      size: 130, // 추이 컬럼 너비
    }),
  ], [headers]);

  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);
        // 파일 경로 정규화를 위해 fetchCSVData 유틸리티 함수에서 경로만 가져옴
        const normalizedPath = await fetchCSVData('requestfile/value/PER.csv')
          .then(() => 'requestfile/value/PER.csv')
          .catch(() => '/requestfile/value/PER.csv'); // 오류 발생 시 절대 경로로 시도
        
        // --- CSV 인코딩 처리 시작 ---
        // 한글 인코딩 문제로 인해 EUC-KR 인코딩 처리가 반드시 필요함
        // 원본 파일이 EUC-KR로 인코딩되어 있어 TextDecoder를 사용해야 함
        console.log('파일 경로:', normalizedPath); // 디버깅용 로그
        const response = await fetch(normalizedPath);
        const buffer = await response.arrayBuffer();
        const decoder = new TextDecoder('euc-kr'); 
        const decodedCsv = decoder.decode(buffer);
        // --- CSV 인코딩 처리 끝 ---

        Papa.parse<string[]>(decodedCsv, {
          complete: (results) => {
            // a행은 헤더, c행부터 데이터 시작 (인덱스로는 0부터 시작하므로 c행은 인덱스 2)
            const headers = results.data[0] || []; // a행의 헤더 가져오기
            setHeaders(headers);
            const parsedData = results.data.slice(2).map(row => ({
              stockCode: row[2] || '', // C열: 종목코드
              stockName: row[3] || '', // D열: 종목명
              industry: row[1] || '', // B열: 업종
              marketCap: row[4] || '', // 시가총액
              tradingVolume: row[5] || '', // 거래대금 (사용하지 않음)
              per2024E: row[8] || '', // I열
              per2025E: row[9] || '', // J열
              per2026E: row[10] || '', // K열
              per2027E: row[11] || '', // L열
              per2028E: row[12] || '', // M열
            })).filter(item => item.stockName); // 종목명이 있는 데이터만 필터링
            
            setData(parsedData);
            setFilteredData(parsedData); // 초기 필터링된 데이터는 전체 데이터와 동일
            
            // 업종 목록 추출
            const uniqueIndustries = Array.from(new Set(parsedData.map(item => item.industry)))
              .filter(Boolean) // 빈 값 제거
              .sort(); // 알파벳 순 정렬
            setIndustries(uniqueIndustries);
            
            // 화면 크기에 따라 동적으로 행 수 조정
            updateRowsPerPage();
            
            setLoading(false);
          },
          error: (error: any) => { 
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
    
    // 화면 크기 변경 시 행 수 업데이트
    window.addEventListener('resize', updateRowsPerPage);
    return () => {
      window.removeEventListener('resize', updateRowsPerPage);
    };
  }, []);
  
  // 필터 적용 효과
  useEffect(() => {
    // 필터링 로직
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
    
    setFilteredData(result);
    setCurrentPage(1); // 필터 변경 시 첫 페이지로 이동
  }, [data, searchFilter, industryFilter, selectedStock, selectedIndustry]);

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
  
  // 화면 크기에 따라 표시할 행 수 계산
  const updateRowsPerPage = () => {
    try {
      // 사용자 요청에 따라 고정 행 수 21개로 설정
      const fixedRows = 21;
      
      setRowsPerPage(fixedRows);
    } catch (error) {
      console.error('행 수 계산 오류:', error);
      // 오류 발생 시 기본값 설정
      setRowsPerPage(21);
    }
  };
  
  // 현재 페이지 데이터 계산
  const currentPageData = useMemo(() => {
    if (showAllItems) {
      return filteredData;
    }
    const startIndex = (currentPage - 1) * rowsPerPage;
    return filteredData.slice(startIndex, startIndex + rowsPerPage);
  }, [filteredData, currentPage, rowsPerPage, showAllItems]);

  // 총 페이지 수 계산
  const totalPages = useMemo(() => {
    if (showAllItems) {
      return 1;
    }
    return Math.ceil(filteredData.length / rowsPerPage);
  }, [filteredData, rowsPerPage, showAllItems]);

  // 컬럼 너비 상태 추가 - 고정 너비 사용
  const [columnSizes, setColumnSizes] = useState<Record<string, number>>(() => {
    // 초기 컬럼 너비 설정
    const initialSizes: Record<string, number> = {};
    Object.keys(fixedColumnWidths).forEach(columnId => {
      initialSizes[columnId] = fixedColumnWidths[columnId as keyof typeof fixedColumnWidths];
    });
    return initialSizes;
  });

  const table = useReactTable({
    data: showAllItems ? filteredData : currentPageData, // 전 종목 출력 여부에 따라 데이터 소스 변경
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
    } catch (error) {
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
              {/* 테이블 헤더 영역 */}
              <div ref={headerRef} className="flex flex-col sm:flex-row justify-between items-start sm:items-center mb-3"> {/* 제목 영역 + mb-3 */}
                {/* text-lg 클래스 제거하여 RS 순위 제목과 크기 맞춤 */}
                <h2 className="font-semibold whitespace-nowrap" style={{ fontSize: 'clamp(0.75rem, 0.9vw, 0.9rem)' }}>밸류에이션</h2>
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
                
                {/* 필터 초기화 버튼 */}
                <div className="flex items-center ml-1 sm:ml-2">
                  <button
                    onClick={() => {
                      setSearchFilter('');
                      setIndustryFilter('');
                      setSelectedStock(null);
                      setSelectedIndustry(null);
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
              </div>
              
              {/* 전 종목 출력 로딩 상태 표시 */}
              {showAllItems && isAllItemsLoading && (
                <div className="flex items-center justify-center h-screen">
                  <div className="text-xl">전 종목 데이터를 불러오는 중...</div>
                </div>
              )}
              
              {/* 테이블 */}
              {!isAllItemsLoading && (
                <div 
                  // 테이블 래퍼에 가로 스크롤 추가하여 반응형 지원
                  // 모바일에서만 overflow-x-auto 적용, 데스크탑에서는 스크롤 없음
                  className="table-container overflow-x-auto sm:overflow-visible" 
                  ref={tableRef}
                >
                  <div className="w-full sm:w-auto">
                    <table className="w-full border border-gray-200">
                      <thead className="bg-gray-100">
                        <tr>
                          {table.getHeaderGroups().map(headerGroup => (
                            headerGroup.headers.map(header => (
                              <th
                                key={header.id}
                                scope="col"
                                className={`px-0.5 sm:px-1 md:px-2 py-2 text-center text-[9px] sm:text-[10px] md:text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer border border-gray-200 ${
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
                                className={`px-0.5 sm:px-1 md:px-2 py-1 whitespace-nowrap text-[9px] sm:text-[10px] md:text-xs border border-gray-200 ${
                                  // 컬럼별 정렬 방식 적용
                                  cell.column.id === 'stockCode' ? 'text-center' :
                                  cell.column.id === 'stockName' || cell.column.id === 'industry' ? 'text-left' :
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
