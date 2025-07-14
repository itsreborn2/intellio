'use client'

import { useState, useEffect, useMemo, useCallback, useRef } from 'react'
import Papa from 'papaparse'
import React from 'react';
import { Sparklines, SparklinesLine, SparklinesSpots, SparklinesReferenceLine, SparklinesBars } from 'react-sparklines';
import { copyTableAsImage } from '../utils/tableCopyUtils';
import TableCopyButton from './TableCopyButton';
import { formatDateMMDD } from '../utils/dateUtils';
import { GuideTooltip } from 'intellio-common/components/ui/GuideTooltip'; // GuideTooltip 컴포넌트 임포트 경로 수정

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

// CSV 데이터를 파싱한 결과를 위한 인터페이스
interface CSVData {
  headers: string[];
  rows: Record<string, any>[];
  groupedData: GroupedData;
  errors: any[];
}

// 그룹화된 데이터를 위한 인터페이스
interface GroupedData {
  [key: string]: Record<string, any>[];
}

// ETF 데이터를 위한 인터페이스
interface ETFData {
  code: string;
  name: string;
  price: number;
  change: number;
  changePercent: number;
  volume: number;
  marketCap: number; // 시가총액
  signal: string | null; // 신호등 상태(red, yellow, green, 또는 null)
}

// 정렬 타입 정의
type SortDirection = 'asc' | 'desc' | null;

// CSV 파일 파싱 함수
function parseCSV(csvText: string): { headers: string[]; rows: Record<string, any>[]; groupedData: GroupedData; errors: any[] } {
  try {
    if (!csvText || typeof csvText !== 'string') {
      console.error('유효하지 않은 CSV 텍스트:', csvText);
      // 기본 데이터 반환
      return {
        headers: ['코드', '이름', '가격', '변동', '변동률', '거래량', '시가총액'],
        rows: [], 
        groupedData: {},
        errors: [],
      };
    }
    
    // Papa Parse 옵션
    const results = Papa.parse(csvText, {
      header: true,       // 첫 번째 행을 헤더로 사용
      skipEmptyLines: true, // 빈 줄 건너뛰기
      dynamicTyping: false,  // 문자열 그대로 유지 (수동 변환)
    });
    
    // 실제 오류가 있을 때만 로깅
    if (results.errors && results.errors.length > 0) {
      console.error('파싱 중 실제 오류 발생:', results.errors);
    }
    
    // 데이터가 없는 경우 처리
    if (!results.data || results.data.length === 0) {
      console.error('파싱된 데이터가 없습니다.');
      return {
        headers: results.meta.fields || [],
        rows: [], 
        groupedData: {},
        errors: [],
      };
    }
    
    // (불필요한 디버깅 로그 삭제)
    // // (불필요한 로그 완전 제거)
// console.log('첫 번째 파싱된 행:', results.data[0]);

    // 산업별로 그룹화
    const groupedData: GroupedData = results.data.reduce((acc: GroupedData, row: any) => {
      // 빈 객체인 경우 건너뛰기
      if (!row || Object.keys(row).length === 0) {
        return acc;
      }
      
      // 업종 필드가 B열로 변경됨 (이전에는 E열로 잘못 설정)
      let industry = row['업종'] || row['산업'];
      if (!industry) {
        // (불필요한 디버깅 로그 삭제)
        // // (불필요한 로그 완전 제거)
// console.log('업종 정보가 없는 행의 키:', Object.keys(row));
        industry = '기타'; // 업종 정보가 없는 경우 '기타'로 분류
      }
      
      // 뷰티와 음식료 카테고리를 소비재/음식료로 통합
      if (industry === '뷰티' || industry === '음식료' || industry === '소비재') {
        industry = '소비재/음식료';
      }
      
      if (!acc[industry]) {
        acc[industry] = [];
      }
      acc[industry].push(row);
      return acc;
    }, {});

    // (불필요한 디버깅 로그 삭제)
    // // (불필요한 로그 완전 제거)
// console.log('그룹화된 산업 목록:', Object.keys(groupedData));
    
    // 그룹 내에서 등락율 기준으로 정렬
    for (const industry in groupedData) {
      groupedData[industry].sort((a: any, b: any) => {
        try {
          // 등락율 필드명이 변경되었을 수 있으므로 확인
          const changeRateFieldA = a['등락율'] !== undefined ? '등락율' : (a['등락률'] !== undefined ? '등락률' : null);
          const changeRateFieldB = b['등락율'] !== undefined ? '등락율' : (b['등락률'] !== undefined ? '등락률' : null);
          
          // 필드가 없는 경우 처리
          if (changeRateFieldA === null || changeRateFieldB === null) {
            return 0;
          }
          
          const changeRateA = parseFloat((a[changeRateFieldA] || '0').replace('%', ''));
          const changeRateB = parseFloat((b[changeRateFieldB] || '0').replace('%', ''));
          
          if (isNaN(changeRateA) || isNaN(changeRateB)) {
            return 0;
          }
          
          return changeRateB - changeRateA; // 내림차순 정렬
        } catch (error) {
          console.error('정렬 중 오류:', error);
          return 0;
        }
      });
    }
    
    return {
      headers: results.meta.fields || [],
      rows: results.data as Record<string, any>[], 
      groupedData: groupedData,
      errors: results.errors,
    };
  } catch (error) {
    console.error('CSV 파싱 오류:', error);
    // 오류 발생 시 빈 데이터 반환
    return {
      headers: [],
      rows: [], 
      groupedData: {},
      errors: [error],
    };
  }
};

// 행 위치 정보를 위한 인터페이스
interface RowPosition {
  bottom: number; // 행의 하단 위치 (Y 좌표)
  top: number;    // 행의 상단 위치 (Y 좌표)
  left: number;   // 행의 좌측 위치 (X 좌표)
  width: number;  // 행의 너비
}

// ETF 현재가 테이블 컴포넌트
interface ETFCurrentTableProps {
  onETFClick?: (code: string, name: string, rowPosition?: RowPosition) => void;
}

export default function ETFCurrentTable({ onETFClick }: ETFCurrentTableProps = {}) {
  // 상태 관리
  const [csvData, setCsvData] = useState<{ headers: string[]; rows: Record<string, any>[]; groupedData: GroupedData; errors: any[] }>({ headers: [], rows: [], groupedData: {}, errors: [] });
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);  
  const [sortConfig, setSortConfig] = useState<{ key: string; direction: SortDirection }>({ key: '', direction: 'asc' });
  console.log('[ETFCurrentTable] Initial sortConfig:', sortConfig);
  const [updateDate, setUpdateDate] = useState<string | null>(null); // 새로운 업데이트 날짜 상태
  // 개별 ETF 차트 데이터 관련 상태 제거됨
  const [tickerMappingInfo, setTickerMappingInfo] = useState<{
    tickerMap: {[key: string]: string},
    stockNameMap: {[key: string]: string}
  }>({ tickerMap: {}, stockNameMap: {} });

  const [maListMap, setMaListMap] = useState<Record<string, MaListData>>({}); // 종목명 -> 20malist 데이터
  
  // 테이블 복사 기능을 위한 ref 생성
  const tableRef = useRef<HTMLTableElement>(null);
  const headerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const loadData = async () => {
      setLoading(true);
      setError(null);

      try {
        // etf_table.csv만 로드하여 테이블 구성
        const response = await fetch('/requestfile/etf_sector/etf_table.csv?t=' + Date.now());
        if (!response.ok) throw new Error(`etf_table.csv 로드 실패: ${response.status}`);

        const csvText = await response.text();
        const result = Papa.parse<MaListData>(csvText, {
          header: true,
          skipEmptyLines: true,
          dynamicTyping: false,
        });

        if (result.errors.length > 0) console.error('etf_table.csv 파싱 오류:', result.errors);
        const rows = result.data;
        // 종목명 및 티커 매핑
        const maMap: Record<string, MaListData> = {};
        const tickerMap: Record<string, string> = {};

        // 저장시간 정보 처리 (첫 번째 행에서 찾기)
        if (rows.length > 0 && rows[0]['저장시간']) {
          setUpdateDate(rows[0]['저장시간']);
        } else {
          // 저장시간 정보가 없는 경우 현재 날짜와 시간 사용
          const now = new Date();
          const month = String(now.getMonth() + 1); // 앞의 0 제거
          const day = String(now.getDate()).padStart(2, '0'); // 일은 두 자리 유지
          const hours = String(now.getHours()).padStart(2, '0');
          const minutes = String(now.getMinutes()).padStart(2, '0');
          const formattedDate = `${month}/${day} ${hours}:${minutes}`;
          setUpdateDate(formattedDate);
        }

        rows.forEach(r => {
          const code = r['종목코드'].padStart(6, '0');
          const name = r['종목명'].trim();
          maMap[name] = r;
          tickerMap[code] = name;
        });
        setMaListMap(maMap);
        setTickerMappingInfo({ tickerMap, stockNameMap: tickerMap });
        
        // 산업별 그룹화
        const grouped: GroupedData = {};
        rows.forEach(r => {
          const industry = r['산업'] || '기타';
          if (!grouped[industry]) grouped[industry] = [];
          grouped[industry].push({
            '티커': r['종목코드'].padStart(6, '0'),
            '종목명': r['종목명'],
            '섹터': r['섹터'],
            '등락율': r['등락률'],
            '포지션': r['포지션'],
            '20일 이격': r['20일 이격'],
            '돌파/이탈': r['돌파/이탈'], // 수정
            '대표종목(RS)': r['대표종목(RS)'],
            '신호등': r['신호등'] // 신호등 컬럼 추가
          });
        });
        
        const processedRows = rows.map(r => ({
          ...r,
          '티커': r['종목코드'] ? String(r['종목코드']).padStart(6, '0') : undefined
        }));

        setCsvData({
          headers: ['산업','섹터','종목명','등락율','포지션','20일 이격','돌파/이탈','대표종목(RS)'],
          rows: processedRows as any[],
          groupedData: grouped, // groupedData는 이미 티커 키를 사용하고 있음
          errors: result.errors,
        });
      } catch (err: any) {
        console.error(err);
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };
    loadData();
  }, []);

  // 정렬 처리 함수
  const handleSort = (key: string) => {
    let direction: SortDirection = 'asc';
    if (sortConfig.key === key && sortConfig.direction === 'asc') {
      direction = 'desc';
    }
    setSortConfig({ key, direction });
  };

  // 정렬된 데이터 계산
  const sortedData = useMemo(() => {
    console.log('[ETFCurrentTable useMemo] sortConfig:', sortConfig);
    if (csvData && csvData.rows && csvData.rows.length > 0) {
      console.log('[ETFCurrentTable useMemo] csvData.rows[0]:', JSON.stringify(csvData.rows[0]));
    }
    if (csvData && csvData.rows && csvData.rows.length > 1) {
      console.log('[ETFCurrentTable useMemo] csvData.rows[1]:', JSON.stringify(csvData.rows[1]));
    }
    // csvData.rows가 없거나 비어있으면 빈 배열 반환
    if (!csvData || !csvData.rows || csvData.rows.length === 0) {
      return [];
    }

    // 정렬 키나 방향이 없으면 원본 순서(CSV 기본 정렬) 반환
    if (!sortConfig.key || !sortConfig.direction) {
      console.log('[ETFCurrentTable useMemo] No sortConfig, returning original csvData.rows');
      return csvData.rows;
    }

    // 모든 행을 포함하는 새로운 배열을 복사하여 정렬 (원본 데이터 변경 방지)
    const dataToSort = [...csvData.rows];

    const sortRow = (a: any, b: any) => {
      let aValue = a[sortConfig.key];
      let bValue = b[sortConfig.key];

      // 포지션 컬럼 특별 처리
      if (sortConfig.key === '포지션') {
        const extractPositionValue = (ticker: string): number => {
          console.log(`[extractPositionValue] ticker: ${ticker}`);
          const stockName = tickerMappingInfo.stockNameMap[ticker] || '';
          if (!stockName) {
            console.log(`[extractPositionValue] No stockName for ticker: ${ticker}`);
            return 0;
          }
          console.log(`[extractPositionValue] stockName: ${stockName}`);

          const maData = maListMap[stockName.trim()];
          console.log(`[extractPositionValue] maData for ${stockName.trim()}:`, maData);

          // maData 존재 및 타입, '포지션' 속성 존재 및 타입 확인
          if (!maData || typeof maData !== 'object' || !maData.hasOwnProperty('포지션')) {
            console.log(`[extractPositionValue] maData or maData['포지션'] is missing or invalid for ${stockName}`);
            return 0;
          }
          
          const positionText = maData['포지션'];
          if (typeof positionText !== 'string') {
            console.log(`[extractPositionValue] positionText is not a string for ${stockName}:`, positionText);
            return 0;
          }
          console.log(`[extractPositionValue] positionText: ${positionText}`);

          const daysMatch = positionText.match(/(\d+)/); // 숫자 부분 추출
          const days = daysMatch ? parseInt(daysMatch[1], 10) : 0;
          console.log(`[extractPositionValue] daysMatch: ${daysMatch}, days: ${days}`);

          if (isNaN(days)) {
            console.log(`[extractPositionValue] days is NaN for ${positionText}`);
            return 0; // 숫자로 변환할 수 없으면 0
          }

          let calculatedValue = 0;
          if (positionText.includes('유지')) {
            calculatedValue = days; // '유지 X일' -> X
          } else if (positionText.includes('이탈')) {
            calculatedValue = -days; // '이탈 Y일' -> -Y
          }
          console.log(`[extractPositionValue] calculatedValue for ${positionText}: ${calculatedValue}`);
          return calculatedValue; // '신규' 또는 기타 텍스트는 0으로 처리
        };
        const aPositionValue = extractPositionValue(a['티커']);
        const bPositionValue = extractPositionValue(b['티커']);
        console.log(`[sortRow - 포지션] aValue: ${aPositionValue}, bValue: ${bPositionValue}, direction: ${sortConfig.direction}`);
        if (aPositionValue < bPositionValue) return sortConfig.direction === 'asc' ? -1 : 1;
        if (aPositionValue > bPositionValue) return sortConfig.direction === 'asc' ? 1 : -1;
        return 0;
      } 
      // 등락률 컬럼 처리 (maListMap에서 데이터 가져와서 숫자로 변환)
      else if (sortConfig.key === '등락율' || sortConfig.key === '20일 이격') {
        const extractChangeRateValue = (rowItem: Record<string, any>): number => {
          const changeRateStr = rowItem['등락률']?.toString().replace('%', '');
          return parseFloat(changeRateStr) || 0;
        };

        const extractDisparityValue = (rowItem: Record<string, any>): number => {
          const disparityStr = rowItem['20일 이격']?.toString().replace('%', '');
          return parseFloat(disparityStr) || 0;
        };
        const aValue = sortConfig.key === '등락율' ? extractChangeRateValue(a) : extractDisparityValue(a);
        const bValue = sortConfig.key === '등락율' ? extractChangeRateValue(b) : extractDisparityValue(b);
        
        // 숫자로 변환된 값을 사용하여 비교 후 바로 결과 반환
        if (aValue < bValue) return sortConfig.direction === 'asc' ? -1 : 1;
        if (aValue > bValue) return sortConfig.direction === 'asc' ? 1 : -1;
        return 0;
      }
      // 그 외 숫자 형태의 문자열을 숫자로 변환 (시가총액, 거래량 등)
      else if (['가격', '시가총액', '거래량'].includes(sortConfig.key)) {
        aValue = parseFloat(String(aValue).replace(/,/g, ''));
        bValue = parseFloat(String(bValue).replace(/,/g, ''));
      }
      // 일반 문자열 비교 또는 이미 숫자인 경우
      else if (typeof aValue === 'string' && typeof bValue === 'string') {
        // 문자열 직접 비교
      } else if (typeof aValue === 'number' && typeof bValue === 'number'){
        // 숫자 직접 비교
      } else {
        // 혼합 타입이거나 예상치 못한 타입의 경우, 기본 비교 시도 또는 에러 처리
        // 여기서는 문자열로 변환하여 비교
        aValue = String(aValue);
        bValue = String(bValue);
      }

      if (aValue < bValue) return sortConfig.direction === 'asc' ? -1 : 1;
      if (aValue > bValue) return sortConfig.direction === 'asc' ? 1 : -1;
      return 0;
    };

    return dataToSort.sort(sortRow);
  }, [csvData.rows, sortConfig, maListMap, tickerMappingInfo.stockNameMap]);

  // 테이블 본문 렌더링 로직을 수정합니다.
  // 이전에는 industryGroups를 순회했지만, 이제 평탄화된 sortedData (배열)를 직접 사용합니다.
  // allRows를 생성하는 로직도 평탄화된 sortedData를 사용하도록 변경합니다.


  // 날짜 컬럼을 제외한 헤더 필터링
  const filteredHeaders = useMemo(() => {
    // 표시하지 않을 컬럼 목록
    const excludedColumns = ['날짜', '시가', '종가', '고가', '저가', '거래량', '전일종가'];
    return csvData.headers.filter(header => !excludedColumns.includes(header));
  }, [csvData.headers]);
  
  // 코스피/코스닥 데이터 추출
  const marketData = useMemo(() => {
    // groupedData에서 코스피와 코스닥 데이터 찾기
    const kospiRow = csvData.groupedData && csvData.groupedData['마켓'] ? 
      csvData.groupedData['마켓'].find((row: Record<string, any>) => row['티커'] === '069500') : null;
    const kosdaqRow = csvData.groupedData && csvData.groupedData['마켓'] ? 
      csvData.groupedData['마켓'].find((row: Record<string, any>) => row['티커'] === '229200') : null;

    return {
      kospi: {
        changeRate: kospiRow ? kospiRow['등락율'] : '0.00%'
      },
      kosdaq: {
        changeRate: kosdaqRow ? kosdaqRow['등락율'] : '0.00%'
      }
    };
  }, [csvData.groupedData]);
  
  // 변동률에 따른 색상 클래스 반환 함수
  const getChangeColorClass = (change: number) => {
    if (change > 0) return 'text-red-400';
    if (change < 0) return 'text-blue-400';
    return '';
  };

  // 변동률에 따른 색상 코드 반환 함수
  const getChangeColorCode = (change: number) => {
    if (change > 0) return '#EF4444';
    if (change < 0) return '#3B82F6';
    return '#4B5563';
  };

  // 변동률에 따른 배경 색상 코드 반환 함수
  const getChangeBgColorCode = (change: number) => {
    if (change > 0) return '#FEE2E2';
    if (change < 0) return '#DBEAFE';
    return '#F3F4F6';
  };

  const getIndustryChangeRate = useCallback((industry: string): string => {
    for (const stockName in maListMap) {
      const row = maListMap[stockName];
      // 타입 가드 추가: row 객체 및 필요한 속성이 존재하는지 확인
      if (row && typeof row === 'object' && '산업' in row && row['산업'] && typeof row['산업'] === 'string' && '산업 등락률' in row) {
        // 산업명 비교 시, 공백을 제거하고 대소문자 구분 없이 비교합니다.
        if (row['산업'].replace(/\s/g, '').toLowerCase() === industry.replace(/\s/g, '').toLowerCase()) {
          // 일치하는 행을 찾으면 해당 행의 '산업 등락률' 값을 반환합니다.
          // 값이 없거나 빈 문자열이면 '-'를 반환합니다.
          return typeof row['산업 등락률'] === 'string' ? row['산업 등락률'] || '-' : '-';
        }
      }
    }
    // 일치하는 산업명을 찾지 못한 경우 '-'를 반환합니다.
    return '-';
  }, [maListMap]); // maListMap이 변경될 때만 함수를 재생성합니다.



  // 변동률에 따른 색상 클래스 반환 함수 (평균용 -> 산업 등락률용으로 재사용)
  const getAverageColorClass = (change: string) => {
    const numValue = parseFloat(change.replace('%', ''));
    if (numValue > 0) return 'text-red-400';
    if (numValue < 0) return 'text-blue-400';
    return 'text-gray-500';
  };

  // 포지션 상태 텍스트 가져오기
  const getPositionStatusText = (stockName: string): string => {
    const maData = maListMap[stockName?.trim()];
    if (!maData || !maData['포지션']) {
      return '-';
    }

    return maData['포지션'];
  };

  // 포지션 뱃지 렌더링 함수
  const renderPositionBadge = (stockName: string) => {
    const maData = maListMap[stockName?.trim()];
    const positionText = (maData && maData['포지션']) ? maData['포지션'] : '-'; // 포지션 텍스트 가져오기, 없으면 '-'

    // 이전 조건부 스타일 클래스 적용
    let containerClasses = 'flex items-center justify-center w-20 h-6'; // 기본 컨테이너 클래스
    const textClasses = 'text-xs font-medium'; // 기본 텍스트 클래스

    if (positionText === '-') {
      // 기본값 또는 데이터 없는 경우 스타일 (이전 로직에 맞춰 회색 계열 사용)
      containerClasses += ' bg-gray-200 text-gray-700 border border-gray-200 shadow-sm'; 
    } else if (positionText.includes('유지')) {
      // '유지' 포함 시 녹색 스타일 (이전 스타일)
      containerClasses += ' bg-green-100 text-green-800';
    } else {
      // '이탈' 포함 시 또는 기타 경우 회색 스타일 (이전 스타일)
      containerClasses += ' bg-gray-200 text-gray-700 border border-gray-200 shadow-sm';
    }

    return (
      <div className={containerClasses} style={{ borderRadius: '4px' }}>
        <span className={textClasses}>
          {positionText}
        </span>
      </div>
    );
  };

  // 테이블 이미지 복사 함수
  const handleCopyTableAsImage = async () => {
    try {
      const currentDate = new Date();
      const formattedDate = `${currentDate.getFullYear()}-${String(currentDate.getMonth() + 1).padStart(2, '0')}-${String(currentDate.getDate()).padStart(2, '0')}`;
      
      await copyTableAsImage(
        tableRef,
        headerRef,
        'ETF 현재가 테이블',
        {
          copyrightText: ' intellio.kr',
          watermark: {
            text: 'intellio.kr',
            opacity: 0.1,
            fontSize: '24px',
            color: '#000000'
          },
          scale: 2,
          backgroundColor: '#ffffff',
          footerStyle: {
            fontSize: '8px',
            color: '#999999',
            marginTop: '8px',
            textAlign: 'center'
          }
        },
        formattedDate
      );
    } catch (error) {
      console.error('테이블 이미지 복사 중 오류 발생:', error);
      alert('테이블 이미지 복사에 실패했습니다.');
    }
  };

  // 로딩 중 표시
  if (loading) {
    return (
      <div className="bg-white rounded-md shadow p-4 h-80 flex items-center justify-center">
        <div className="text-gray-500">데이터 로딩 중...</div>
      </div>
    );
  }
  
  // 오류 표시
  if (error) {
    return (
      <div className="bg-white rounded-md shadow p-4 h-80 flex items-center justify-center">
        <div className="text-red-500">{error}</div>
      </div>
    );
  }
  
  // 데이터가 없는 경우
  if (!csvData.groupedData) {
    return (
      <div className="bg-white rounded-md shadow p-4 h-80 flex items-center justify-center">
        <div className="text-gray-500">데이터가 없습니다.</div>
      </div>
    );
  }
  
  

  // 산업 그룹 순서 하드코딩 제거: csv 원본 순서대로 렌더링
const orderedIndustries = Object.keys(sortedData);

  // (불필요한 디버깅용 변수 및 코드 완전 삭제)
  // industryCounts, totalETFs, allTickers 등은 실제 렌더링/기능에 사용되지 않으므로 제거

  return (
    <div>
      <div ref={headerRef} className="flex justify-start items-center mb-2">
        <GuideTooltip
          title="ETF 주요섹터"
          description={`산업 및 주요 섹터별로 분류하여 엄선한 ETF 목록입니다.\n이 목록을 통해 현재 강세인 산업과 그 안의 주요 섹터, 그리고 해당 섹터를 이끄는 대표 종목까지 한눈에 파악하실 수 있습니다.\n시장을 주도하는 섹터 중심의 투자 기회를 발견하는 데 도움을 드립니다.`}
          side="top"
          width="min(90vw, 360px)" // 너비를 반응형으로 수정
          collisionPadding={{ left: 260 }} // 왼쪽 여백 추가
        >
          <span className="inline-flex items-center"> {/* Tooltip 트리거 영역 확장을 위한 span */}
            <h2 className="text-sm md:text-base font-semibold cursor-help" style={{ color: 'var(--primary-text-color, var(--primary-text-color-fallback))' }}> {/* 도움말 커서 추가 */}
              ETF 주요섹터
            </h2>
          </span>
        </GuideTooltip>
        <div className="flex items-center space-x-2 ml-auto">
          {/* 기존 업데이트 시간 표시 부분 수정 */}
          {/* 
          <div className="text-gray-600 text-xs mr-2" style={{ fontSize: 'clamp(0.7rem, 0.7vw, 0.7rem)' }}>
            {updateTime}
          </div>
          */}
          {/* 업데이트 날짜/시간 표시 */} 
          {updateDate && (
            <div className="text-xs mr-2 js-remove-for-capture" style={{ fontSize: 'clamp(0.7rem, 0.7vw, 0.7rem)', color: 'var(--text-muted-color, var(--text-muted-color-fallback))' }}>
              updated {updateDate}
            </div>
          )}
          <div className="hidden md:block">
            <TableCopyButton
              tableRef={tableRef}
              headerRef={headerRef}
              tableName="ETF 현황"
              updateDateText={updateDate ? `updated ${updateDate}` : undefined}
            />
          </div>
        </div>
      </div>

      <div className="overflow-x-auto scrollbar-thin scrollbar-thumb-gray-300 scrollbar-track-transparent">
        <table ref={tableRef} className="min-w-full bg-white border border-gray-200 table-fixed">
          <thead>
            <tr className="bg-gray-100">
              {/* 기존 thead 내용 유지 */}

              <th
                key="섹터"
                scope="col"
                className="px-4 py-3 text-center text-xs md:text-xs font-medium uppercase tracking-wider cursor-pointer border border-gray-200"
                style={{
                  color: 'var(--text-muted-color, var(--text-muted-color-fallback))',
                  width: '60px',
                  height: '35px'
                }}
                onClick={() => handleSort('섹터')}
              >
                <div className="flex justify-center items-center">
                  섹터
                  {sortConfig.key === '섹터' && (
                    <span className="ml-1">
                      {sortConfig.direction === 'asc' ? '↑' : sortConfig.direction === 'desc' ? '↓' : ''}
                    </span>
                  )}
                </div>
              </th>
              <th
                key="종목명"
                scope="col"
                className="px-4 py-3 text-center text-xs md:text-xs font-medium uppercase tracking-wider cursor-pointer border border-gray-200"
                style={{
                  color: 'var(--text-muted-color, var(--text-muted-color-fallback))',
                  width: '140px',
                  height: '35px'
                }}
                onClick={() => handleSort('종목명')}
              >
                <div className="flex justify-center items-center">
                  ETF 종목명
                  {sortConfig.key === '종목명' && (
                    <span className="ml-1">
                      {sortConfig.direction === 'asc' ? '↑' : sortConfig.direction === 'desc' ? '↓' : ''}
                    </span>
                  )}
                </div>
              </th>
              {filteredHeaders.filter(header => header === '등락율').map((header) => (
                <th
                  key={header}
                  scope="col"
                  className="px-4 py-3 text-center text-xs font-medium uppercase tracking-wider cursor-pointer border border-gray-200"
                  style={{
                    color: 'var(--text-muted-color, var(--text-muted-color-fallback))',
                    width: '65px', 
                    height: '35px'
                  }}
                  onClick={() => handleSort(header)} // 정렬 함수에는 데이터 키 "등락율" 전달
                >
                  <div className="flex justify-center items-center">
                    등락률 {/* 표시 텍스트만 변경 */}
                    {sortConfig.key === header && (
                      <span className="ml-1">
                        {sortConfig.direction === 'asc' ? '↑' : sortConfig.direction === 'desc' ? '↓' : ''}
                      </span>
                    )}
                  </div>
                </th>
              ))}
              <th
                key="포지션"
                scope="col"
                // className 수정: cursor-help 추가
                className="px-4 py-3 text-center text-xs font-medium uppercase tracking-wider cursor-help border border-gray-200" // cursor-help 추가, text-gray-500 제거
                style={{
                  color: 'var(--text-muted-color, var(--text-muted-color-fallback))',
                  width: '78px',
                  height: '35px'
                }}
                // onClick은 Tooltip 트리거 내부 요소가 아닌 th 자체에 두어 클릭 영역 유지
                onClick={() => handleSort('포지션')}
              >
                <GuideTooltip
                  title="포지션이란?"
                  description="해당 ETF가 20일 이동평균선 위에서 유지된 기간을 나타냅니다. 이 기간이 길수록 해당 섹터가 강한 상승 추세에 있음을 시사합니다."
                  side="top"
                  width="min(90vw, 360px)" // 반응형 너비
                  collisionPadding={{ left: 260 }} // 왼쪽 여백
                >
                  {/* 기존 div 내용을 Tooltip의 자식으로 이동 */}
                  <div className="flex justify-center items-center">
                    포지션
                    {sortConfig.key === '포지션' && (
                      <span className="ml-1">
                        {sortConfig.direction === 'asc' ? '↑' : sortConfig.direction === 'desc' ? '↓' : ''}
                      </span>
                    )}
                  </div>
                </GuideTooltip>
              </th>
              {/* 신호등 헤더 추가 */}
              <th
                key="신호"
                scope="col"
                className="px-4 py-3 text-center text-xs font-medium uppercase tracking-wider cursor-help border border-gray-200"
                style={{
                  color: 'var(--text-muted-color, var(--text-muted-color-fallback))',
                  width: '60px',
                  height: '35px'
                }}
              >
                <GuideTooltip
                  title="신호 지표란?"
                  description="신호 색상으로 현재 ETF의 시장 상태를 표시합니다. 파란색은 매수를 해도 좋은 상태, 노란색은 매수에 주의해야하는 상태, 빨간색은 매수를 하면 안되는 상태를 의미합니다."
                  side="top"
                  width="min(90vw, 360px)" // 반응형 너비
                  collisionPadding={{ left: 260 }} // 왼쪽 여백
                >
                  <div className="flex justify-center items-center">
                    신호
                  </div>
                </GuideTooltip>
              </th>
              {['20일 이격', '돌파/이탈', '대표종목(RS)'].map((header) => (
                <th
                  key={header}
                  scope="col"
                  // className 수정: font-medium, text-gray-500, uppercase, tracking-wider 추가
                  className={`px-4 py-3 text-center text-xs font-medium uppercase tracking-wider border border-gray-200 ${header === '20일 이격' ? 'cursor-pointer' : header === '돌파/이탈' || header === '대표종목(RS)' ? 'cursor-help' : ''} hidden md:table-cell`} // 20일 이격은 cursor-pointer로 변경, 나머지는 cursor-help 유지
                  style={{
                    color: 'var(--text-muted-color, var(--text-muted-color-fallback))',
                    width: header === '20일 이격' ? '65px' : header === '돌파/이탈' ? '70px' : header === '대표종목(RS)' ? '380px' : '80px',
                    height: '35px'
                  }}
                  onClick={header === '20일 이격' ? () => handleSort(header) : undefined} // 20일 이격 컬럼에만 정렬 기능 추가
                >
                  {/* '20일 이격' 헤더일 경우 GuideTooltip으로 감싸기 */}
                  {header === '20일 이격' ? (
                    <GuideTooltip
                      title="20일 이격이란?"
                      description="현재가와 *20일 이동평균선 간의 차이(이격률)*를 보여줍니다. 20일선 위에 위치하면 양수(+), 아래에 위치하면 음수(-)로 표시됩니다. 섹터의 단기 위치를 참고하는데 도움이 됩니다."
                      side="top"
                      width="min(90vw, 360px)" // 반응형 너비
                      collisionPadding={{ left: 260 }} // 왼쪽 여백
                    >
                      <div className="flex justify-center items-center">
                        {header}
                        {sortConfig.key === header && (
                          <span className="ml-1">
                            {sortConfig.direction === 'asc' ? '↑' : sortConfig.direction === 'desc' ? '↓' : ''}
                          </span>
                        )}
                      </div>
                    </GuideTooltip>
                  ) : /* '돌파/이탈' 헤더일 경우 GuideTooltip으로 감싸기 */
                  header === '돌파/이탈' ? (
                    <GuideTooltip
                      title="돌파/이탈이란?"
                      // description에서 마크다운 처리 (템플릿 리터럴 사용)
                      description={`가장 최근에 **20일 이동평균선을 위로 돌파(붉은색)**하거나 아래로 이탈(푸른색)한 날짜를 표시합니다. 기간을 확인하여 추세의 지속 여부를 판단합니다.`}
                      side="top"
                      width="min(90vw, 360px)" // 반응형 너비
                      collisionPadding={{ left: 260 }} // 왼쪽 여백
                    >
                      <div className="flex justify-center items-center">
                        <>돌파/<br />이탈</> {/* 툴팁 내부 텍스트 */}
                      </div>
                    </GuideTooltip>
                  ) : /* '대표종목(RS)' 헤더일 경우 GuideTooltip으로 감싸기 */
                  header === '대표종목(RS)' ? (
                    <GuideTooltip
                      title="대표 종목 (RS)이란?"
                      description="각 섹터를 대표하는 주요 종목과 해당 종목의 상대강도(RS) 값을 함께 보여주어 섹터 내 주도주를 쉽게 확인할 수 있습니다."
                      side="top"
                      width="min(90vw, 360px)" // 반응형 너비
                      collisionPadding={{ left: 260 }} // 왼쪽 여백
                    >
                      <div className="flex justify-center items-center">{header}</div>
                    </GuideTooltip>
                  ) : (
                    // '20일 이격' 및 '돌파/이탈' 외 헤더는 그대로 유지
                    <div className="flex justify-center items-center">{header}</div>
                  )}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="bg-white">
            {(sortedData as Record<string, any>[]).map((row: Record<string, any>, rowIndex: number) => {
              // 각 행에 대한 고유 키 생성 시, row에 고유 ID가 있다면 그것을 사용하는 것이 좋습니다.
              // 여기서는 rowIndex를 사용하지만, 데이터에 '티커'와 같이 고유 식별자가 있다면 활용하세요.
              // 예: const rowKey = row['티커'] ? `${row['티커']}-${rowIndex}` : `row-${rowIndex}`;
              const rowKey = `row-${rowIndex}`; // 임시로 rowIndex 사용, 실제 데이터 기반 키 권장
              
              // 스타일링 위한 클래스 (이전 로직에서는 industry에 따라 borderTopClass를 다르게 설정 가능했으나, 이제 모든 행 동일)
              const borderTopClass = ''; // 필요에 따라 조건부 스타일링 추가 가능

              return (
                <tr key={rowKey} className={`hover:bg-gray-100 ${borderTopClass}`}>

                    <td 
                      className="px-2 py-1 whitespace-nowrap text-xs border border-gray-200" 
                      style={{ width: '60px', height: '16px' }}
                    >
                      <div className="flex flex-col items-start">
                        <span className="text-xs px-1 sm:px-2 py-0.5 sm:py-1 bg-white text-gray-700 border border-gray-200 shadow-sm inline-block" style={{ borderRadius: '4px' }}>
                          {row['섹터']}
                        </span>
                      </div>
                    </td>
                    <td 
                      className="px-4 py-1 whitespace-nowrap text-xs border border-gray-200 cursor-pointer hover:bg-gray-50" 
                      style={{ width: '140px', height: '16px' }}
                      onClick={(event) => {
                        const etfName = row['종목명'] || tickerMappingInfo.stockNameMap[row['티커']] || '';
                        const etfCode = row['티커'] || '';
                        if (onETFClick && etfName && etfCode) {
                          // 클릭한 요소의 위치 정보 계산
                          const clickedElement = event.currentTarget as HTMLElement;
                          const rect = clickedElement.getBoundingClientRect();
                          const rowPosition = {
                            bottom: rect.bottom + window.scrollY,
                            top: rect.top + window.scrollY,
                            left: rect.left + window.scrollX,
                            width: clickedElement.closest('tr')?.offsetWidth || 0
                          };
                          
                          onETFClick(etfCode, etfName, rowPosition);
                        }
                      }}
                      title="차트 보기"
                    >
                      {row['종목명'] || tickerMappingInfo.stockNameMap[row['티커']] || ''}
                    </td>
                    {/* 등락률 셀 렌더링 */}
                    <td className="px-4 py-1 whitespace-nowrap text-xs border border-gray-200 text-right tabular-nums" style={{ width: '60px', height: '16px' }}>
                      {(() => {
                        const stockName = row['종목명'] as string;
                        const maData = maListMap[stockName?.trim()];
                        const changeRateText = maData ? maData['등락률'] : '-';
                      
                        let textColorClass = 'text-gray-500'; // 기본값
                        if (changeRateText && changeRateText !== '-') {
                          // '%' 기호 제거 및 숫자로 변환 시도
                          const changeRateValue = parseFloat(changeRateText.replace('%', ''));
                          if (!isNaN(changeRateValue)) {
                            textColorClass = changeRateValue > 0 ? 'text-red-500' : changeRateValue < 0 ? 'text-blue-500' : 'text-gray-500';
                          }
                        }
                      
                        return <span className={textColorClass}>{changeRateText || '-'}</span>;
                      })()} 
                    </td>
                    <td className="px-4 py-1 whitespace-nowrap text-xs border border-gray-200" style={{ width: '78px', height: '16px' }}>
                      {/* 포지션 상태 표시 */}
                      <div className="flex items-center justify-center">
                        {renderPositionBadge(row['종목명'])}
                      </div>
                    </td>
                    {/* 신호등 컬럼 추가 */}
                    <td className="px-4 py-1 whitespace-nowrap text-xs border border-gray-200" style={{ width: '60px', height: '16px' }}>
                      <div className="flex items-center justify-center">
                        <SingleSignalLight signal={row['신호등'] || null} />
                      </div>
                    </td>
                    {['20일 이격', '돌파/이탈', '대표종목(RS)'].map((header) => (
                      <td
                        key={header}
                        className={`px-4 py-1 ${header === '대표종목(RS)' ? 'whitespace-normal break-words' : 'whitespace-nowrap'} text-xs border border-gray-200 hidden md:table-cell`}
                        style={{
                          width: header === '20일 이격' ? '60px' : header === '돌파/이탈' ? '80px' : header === '대표종목(RS)' ? '400px' : '80px',
                          height: '16px'
                        }}
                      >
                        {(() => {
                          if (header === '20일 이격') {
                            // maListMap에서 20일 이격 데이터 가져오기
                            const stockName = row['종목명'] as string;
                            const maData = maListMap[stockName?.trim()];
                            // 타입 가드 추가: maData 객체 및 '20일 이격' 속성 존재 및 타입 확인
                            const maPositionText = (maData && typeof maData === 'object' && '20일 이격' in maData && typeof maData['20일 이격'] === 'string')
                              ? maData['20일 이격']
                              : '-';
                            
                            let textColor = 'text-gray-500'; // 기본값
                            const numVal = Number(maPositionText?.replace(/[^\d.-]/g, ''));
                            if (!isNaN(numVal)) {
                              if (numVal > 0) textColor = 'text-red-500';
                              else if (numVal < 0) textColor = 'text-blue-500';
                              else textColor = 'text-gray-500';
                            }
                            return <div className={`text-right tabular-nums ${textColor}`}>{maPositionText}</div>;
                          } else if (header === '돌파/이탈') {
                            // maListMap에서 변동일 데이터 가져와서 포맷팅하기
                            const stockName = row['종목명'] as string;
                            const maData = maListMap[stockName.trim()];
                            let displayDate = '-';
                            // let textColor = 'text-black'; // 더 이상 사용되지 않음
                            
                            if (maData && maData['돌파/이탈']) {
                              const rawDate = maData['돌파/이탈'];
                              if (/^\d{4}-\d{2}-\d{2}$/.test(rawDate)) {
                                // YYYY-MM-DD -> MM-DD
                                displayDate = rawDate.substring(5);
                              } else {
                                // MM-DD 등 포맷 그대로 사용
                                displayDate = rawDate;
                              }
                            }
                            return <div className="text-center tabular-nums" style={{ color: 'var(--primary-text-color, var(--primary-text-color-fallback))' }}>{displayDate}</div>;
                          } else if (header === '대표종목(RS)') {
                            // 대표종목(RS) 데이터 표시 (20malist.csv 기반)
                            const stockName = row['종목명'] as string;
                            const maData = maListMap[stockName?.trim()];
                            // 타입 가드 추가: maData 객체 및 '대표종목(RS)' 속성 존재 및 타입 확인
                            const representativeStocksRS = (maData && typeof maData === 'object' && '대표종목(RS)' in maData && typeof maData['대표종목(RS)'] === 'string')
                              ? maData['대표종목(RS)']
                              : null;

                            if (!representativeStocksRS) {
                              return '-'; // 20malist.csv에 해당 종목 데이터 없음
                            }

                            // 문자열 파싱: "종목명1(RS1), 종목명2(RS2)"에서 ASCII/comma 및 전각 콤마 지원
                            const items = representativeStocksRS.split(/[,，]/).map((item: string) => item.trim()).filter((item: string) => item);

                            if (items.length === 0) {
                              return '-'; // 문자열이 비어 있거나 형식이 잘못됨
                            }

                            return (
                              <div className="flex flex-wrap items-center gap-1">
                                {items.map((itemString: string, index: number) => {
                                  // 정규식을 사용하여 이름과 RS 값 추출 (예: "삼성전자(91)", "삼성전자(91.0)", "삼성전자( 91 )")
                                  // 괄호 안에 소수점, 공백도 허용
                                  const trimmedItem = itemString.trim();
                                  const match = trimmedItem.match(/^(.+?)\s*\(\s*(\d+)\s*\)$/);
                                  if (match) {
                                    const name = match[1].trim();
                                    const rsValueStr = match[2];
                                    const rsValue = parseInt(rsValueStr, 10);
                                    return (
                                      <span key={index} className="text-xs mr-1">
                                        {rsValue >= 90 ? (
                                          <>
                                            <span className="font-bold">{name}</span>(<span className="font-bold">{rsValueStr}</span>)
                                          </>
                                        ) : (
                                          <>
                                            {name}({rsValueStr})
                                          </>
                                        )}
                                      </span>
                                    );
                                  }
                                  // 형식 불일치 시 원본 문자열 표시 (오류 표시용)
                                  return <span key={index} className="text-xs text-red-500">?{itemString as string}?</span>;
                                })}
                              </div>
                            );
                          }
                        })()}
                      </td>
                    ))}
                  </tr>
                );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

interface MaListData {
  종목코드: string;
  종목명: string;
  섹터: string;
  산업: string;
  대표종목: string;
  등락률: string; // 또는 number
  '돌파/이탈': string; // YYYY-MM-DD 형식
  포지션: string;
  '20일 이격': string; // 또는 number
  '대표종목(RS)': string;
  '신호등'?: string; // 선택적 속성(존재할 수도, 안할 수도 있음)
  '저장시간'?: string; // CSV 파일에 포함된 저장 시간 정보 (MM/DD HH:MM 형식)
}

// ...
