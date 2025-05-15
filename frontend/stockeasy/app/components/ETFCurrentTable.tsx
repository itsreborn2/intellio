'use client'

import { useState, useEffect, useMemo, useCallback, useRef } from 'react'
import Papa from 'papaparse'
import React from 'react';
import { Sparklines, SparklinesLine, SparklinesSpots, SparklinesReferenceLine, SparklinesBars } from 'react-sparklines';
import { copyTableAsImage } from '../utils/tableCopyUtils';
import TableCopyButton from './TableCopyButton';
import { formatDateMMDD } from '../utils/dateUtils';
import { GuideTooltip } from 'intellio-common/components/ui/GuideTooltip'; // GuideTooltip 컴포넌트 임포트 경로 수정

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

// ETF 현재가 테이블 컴포넌트
export default function ETFCurrentTable() {
  // 상태 관리
  const [csvData, setCsvData] = useState<{ headers: string[]; rows: Record<string, any>[]; groupedData: GroupedData; errors: any[] }>({ headers: [], rows: [], groupedData: {}, errors: [] });
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);  
  const [sortKey, setSortKey] = useState<string>('산업');  // 정렬 상태 - 기본값으로 산업 컬럼 오름차순 설정
  const [sortDirection, setSortDirection] = useState<SortDirection>('asc');
  const [updateDate, setUpdateDate] = useState<string | null>(null); // 새로운 업데이트 날짜 상태
  // 개별 ETF 차트 데이터 관련 상태 제거됨
  const [tickerMappingInfo, setTickerMappingInfo] = useState<{
    tickerMap: {[key: string]: string},
    stockNameMap: {[key: string]: string}
  }>({ tickerMap: {}, stockNameMap: {} });

  const [maListMap, setMaListMap] = useState<Record<string, MaListData>>({}); // 종목명 -> 20malist 데이터
  
  // 테이블 복사 기능을 위한 ref 생성
  const tableRef = useRef<HTMLDivElement>(null);
  const headerRef = useRef<HTMLDivElement>(null);

  // 개별 ETF 차트 데이터 관련 티커 목록 및 매핑 테이블 제거됨
  
  // 개별 ETF 차트 데이터 로딩 관련 함수들(loadPriceData, loadAllPriceData, normalizeTicker) 제거됨
  
  // 업데이트 날짜와 시간을 파일 수정 정보로부터 로드하는 함수
  const loadUpdateDate = async () => {
    try {
      // GET 요청으로 etf_table.csv 파일의 수정 날짜를 가져옴
      // 캐시를 방지하기 위해 타임스탬프 추가
      const etfFilePath = '/requestfile/etf_sector/etf_table.csv?t=' + Date.now();
      
      const response = await fetch(etfFilePath, { 
        method: 'GET',
        cache: 'no-store',
        headers: {
          'Pragma': 'no-cache',
          'Cache-Control': 'no-cache'
        }
      });
      
      if (!response.ok) {
        throw new Error(`ETF 테이블 파일 접근 실패: ${response.status}`);
      }
      
      // 응답 헤더에서 Last-Modified 정보 추출
      const lastModified = response.headers.get('Last-Modified');
      
      if (lastModified) {
        // Last-Modified 날짜를 Date 객체로 변환
        const modifiedDate = new Date(lastModified);
        
        // 날짜 형식 변환 (M/DD 형식 - 예: 5/10)
        const month = String(modifiedDate.getMonth() + 1); // 앞의 0 제거
        const day = String(modifiedDate.getDate()).padStart(2, '0'); // 일은 두 자리 유지
        
        // 시간 형식 변환 (HH:MM 형식 - 예: 14:30)
        const hours = String(modifiedDate.getHours()).padStart(2, '0');
        const minutes = String(modifiedDate.getMinutes()).padStart(2, '0');
        
        // 날짜와 시간을 포함한 형식으로 변환 (M/DD HH:MM)
        const formattedDate = `${month}/${day} ${hours}:${minutes}`;
        
        // 업데이트 날짜 설정
        setUpdateDate(formattedDate);
      } else {
        console.error('ETFCurrentTable: 파일의 수정 날짜 정보를 가져올 수 없습니다.');
        
        // 파일의 수정 날짜를 가져올 수 없는 경우 현재 날짜와 시간 사용
        const now = new Date();
        const month = String(now.getMonth() + 1); // 앞의 0 제거
        const day = String(now.getDate()).padStart(2, '0'); // 일은 두 자리 유지
        const hours = String(now.getHours()).padStart(2, '0');
        const minutes = String(now.getMinutes()).padStart(2, '0');
        const formattedDate = `${month}/${day} ${hours}:${minutes}`;
        setUpdateDate(formattedDate);
      }
    } catch (err) {
      console.error('ETFCurrentTable: 업데이트 날짜 로드 중 오류 발생:', err);
      // 오류 발생 시 현재 날짜와 시간 사용
      const now = new Date();
      const month = String(now.getMonth() + 1); // 앞의 0 제거
      const day = String(now.getDate()).padStart(2, '0'); // 일은 두 자리 유지
      const hours = String(now.getHours()).padStart(2, '0');
      const minutes = String(now.getMinutes()).padStart(2, '0');
      const formattedDate = `${month}/${day} ${hours}:${minutes}`;
      setUpdateDate(formattedDate);
    }
  };

  useEffect(() => {
    const loadData = async () => {
      setLoading(true);
      setError(null);
      
      await loadUpdateDate(); // 새로운 업데이트 날짜 로드 함수 호출

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
            '대표종목(RS)': r['대표종목(RS)']
          });
        });
        setCsvData({
          headers: ['산업','섹터','종목명','등락율','포지션','20일 이격','돌파/이탈','대표종목(RS)'],
          rows: rows as any[],
          groupedData: grouped,
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
    // (불필요한 로그 완전 제거)
// console.log(`정렬 시도: 컴럼 = ${key}, 현재 정렬키 = ${sortKey}, 현재 방향 = ${sortDirection}`);
    
    if (sortKey === key) {
      // 같은 컴럼을 다시 클릭한 경우, 오름차순과 내림차순만 반복하도록 수정
      const newDirection = sortDirection === 'asc' ? 'desc' : 'asc';
      // (불필요한 로그 완전 제거)
// console.log(`같은 컴럼 클릭: 정렬 방향 변경 ${sortDirection} -> ${newDirection}`);
      setSortDirection(newDirection);
    } else {
      // 다른 컴럼을 클릭한 경우, 해당 컴럼으로 오름차순 정렬
      // (불필요한 로그 완전 제거)
// console.log(`새 컴럼 클릭: 정렬키 변경 ${sortKey} -> ${key}, 방향 = asc`);
      setSortKey(key);
      setSortDirection('asc');
    }
  };
  
  // 정렬된 데이터 계산
  const sortedData = useMemo(() => {
    if (!sortKey || !sortDirection || !csvData.groupedData) {
      return csvData.groupedData;
    }
    
    // 마켓 행 반드시 복사하여 사용
    const marketGroup = [...(csvData.groupedData['마켓'] || [])];
    
    // 1. 마켓을 포함한 모든 산업 그룹들의 데이터를 복사
    const allIndustries: GroupedData = {};
    for (const industry in csvData.groupedData) {
      allIndustries[industry] = [...csvData.groupedData[industry]];
    }
    
    // 2. 단순한 행 정렬 함수 정의
    const sortRow = (a: any, b: any) => {
      let aValue = a[sortKey];
      let bValue = b[sortKey];
      
      // 포지션 컴럼은 특별 처리
      if (sortKey === '포지션') {
        // 포지션 값은 데이터에 직접 존재하지 않음
        // 티커를 사용하여 포지션 값을 가져와야 함
        const aTicker = a['티커'];
        const bTicker = b['티커'];
        
        // (불필요한 로그 완전 제거)
// console.log('포지션 정렬을 위한 티커:', aTicker, bTicker);
        
        // 포지션 값 추출 - maListMap에서 포지션 정보 가져오기
        const extractPositionValue = (ticker: string): number => {
          // 티커로 종목명 찾기
          const stockName = tickerMappingInfo.stockNameMap[ticker] || '';
          if (!stockName) return 0;
          
          // maListMap에서 포지션 정보 가져오기
          const maData = maListMap[stockName.trim()];
          if (!maData || !maData['포지션']) return 0;
          
          // 포지션 텍스트에 따라 값 할당
          const positionText = maData['포지션'];
          
          if (positionText.includes('유지')) {
            return 1; // 유지는 양수 값
          } else if (positionText.includes('이탈')) {
            return -1; // 이탈은 음수 값
          }
          
          return 0; // 기타 경우
        };
        
        const aPositionValue = extractPositionValue(aTicker);
        const bPositionValue = extractPositionValue(bTicker);
        
        // (불필요한 로그 완전 제거)
// console.log(`비교: ${aPositionValue} vs ${bPositionValue}, 정렬방향: ${sortDirection}`);
        
        if (aPositionValue < bPositionValue) return sortDirection === 'asc' ? -1 : 1;
        if (aPositionValue > bPositionValue) return sortDirection === 'asc' ? 1 : -1;
        return 0;
      }
      // 숫자 문자열을 숫자로 변환 (일반 컴럼)
      else if (!isNaN(parseFloat(aValue)) && !isNaN(parseFloat(bValue))) {
        aValue = parseFloat(aValue);
        bValue = parseFloat(bValue);
      }
      
      if (aValue < bValue) return sortDirection === 'asc' ? -1 : 1;
      if (aValue > bValue) return sortDirection === 'asc' ? 1 : -1;
      return 0;
    };
    
    // 3. 산업 그룹을 등락률 평균 기준으로 정렬 (직접 계산)
    // 산업 컴럼 외 다른 컴럼을 정렬할 때는 산업그룹 순서는 유지하고 그룹 내부만 정렬
    if (sortKey === '산업') {
      // 산업 컴럼을 클릭했을 때는 산업 그룹을 정렬

      const industryAverages: Record<string, number> = {};
      
      // 각 산업의 등락률 평균값 계산
      for (const industry in allIndustries) {
        // 마켓을 제외한 산업만 평균 계산 (마켓은 항상 최상단에 고정)
        if (industry !== '마켓') {
          // 해당 산업의 모든 항목에 대해 등락률 평균 계산
          let sum = 0;
          let count = 0;
          
          allIndustries[industry].forEach((item: any) => {
            const changeRate = item['등락율']; // '등락율' 기준으로 평균 계산
            if (changeRate) {
              const numValue = parseFloat(changeRate.replace('%', ''));
              if (!isNaN(numValue)) {
                sum += numValue;
                count++;
              }
            }
          });
          
          // 산업 평균 등락률 계산
          industryAverages[industry] = count > 0 ? sum / count : 0;
        }
      }
      
      // 마켓을 제외한 산업 그룹만 정렬
      const sortedIndustries = Object.keys(allIndustries)
        .filter(industry => industry !== '마켓')
        .sort((a, b) => {
          const aAvg = industryAverages[a];
          const bAvg = industryAverages[b];
          
          // sortDirection에 따라 산업 그룹 정렬 방향 변경
          if (aAvg < bAvg) return sortDirection === 'asc' ? 1 : -1; 
          if (aAvg > bAvg) return sortDirection === 'asc' ? -1 : 1;
          return 0;
        });
      
      // 정렬된 산업 순서대로 새 데이터 객체 생성 (마켓은 최상단 고정)
      const sortedGroupedData: GroupedData = { '마켓': marketGroup };
      
      // 정렬된 산업 순서대로 그룹 추가
      sortedIndustries.forEach(industry => {
        sortedGroupedData[industry] = allIndustries[industry];
      });
      
      return sortedGroupedData;
    } else {
      // 다른 컴럼을 클릭했을 때는 그룹 순서는 유지하고 그룹 내부만 정렬
      
      // 1. 산업 그룹 내부 정렬
      for (const industry in allIndustries) {
        allIndustries[industry].sort(sortRow);
      }
      
      // 2. 마켓 그룹은 최상단에 고정
      const sortedGroupedData: GroupedData = { '마켓': allIndustries['마켓'] };
      
      // 3. 기존 산업 순서를 유지하면서 그룹 내부만 정렬된 데이터 추가
      Object.keys(csvData.groupedData)
        .filter(industry => industry !== '마켓')
        .forEach(industry => {
          sortedGroupedData[industry] = allIndustries[industry];
        });
      
      return sortedGroupedData;
    }
  }, [csvData.groupedData, sortKey, sortDirection]);

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
            <h2 className="text-sm md:text-base font-semibold text-gray-700 cursor-help"> {/* 도움말 커서 추가 */}
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
            <div className="text-gray-600 text-xs mr-2 js-remove-for-capture" style={{ fontSize: 'clamp(0.7rem, 0.7vw, 0.7rem)' }}>
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

      <div ref={tableRef} className="overflow-x-auto scrollbar-thin scrollbar-thumb-gray-300 scrollbar-track-transparent">
        <table className="min-w-full bg-white border border-gray-200 table-fixed">
          <thead>
            <tr className="bg-gray-100">
              {/* 기존 thead 내용 유지 */}
              <th
                key="산업"
                scope="col"
                className="px-4 py-3 text-center text-xs md:text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer border border-gray-200"
                style={{
                  width: '60px',
                  height: '35px'
                }}
                onClick={() => handleSort('산업')}
              >
                <div className="flex justify-center items-center">
                  산업
                  {sortKey === '산업' && (
                    <span className="ml-1">
                      {sortDirection === 'asc' ? '↑' : sortDirection === 'desc' ? '↓' : ''}
                    </span>
                  )}
                </div>
              </th>
              <th
                key="섹터"
                scope="col"
                className="px-4 py-3 text-center text-xs md:text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer border border-gray-200"
                style={{
                  width: '60px',
                  height: '35px'
                }}
                onClick={() => handleSort('섹터')}
              >
                <div className="flex justify-center items-center">
                  섹터
                  {sortKey === '섹터' && (
                    <span className="ml-1">
                      {sortDirection === 'asc' ? '↑' : sortDirection === 'desc' ? '↓' : ''}
                    </span>
                  )}
                </div>
              </th>
              <th
                key="종목명"
                scope="col"
                className="px-4 py-3 text-center text-xs md:text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer border border-gray-200"
                style={{
                  width: '140px',
                  height: '35px'
                }}
                onClick={() => handleSort('종목명')}
              >
                <div className="flex justify-center items-center">
                  ETF 종목명
                  {sortKey === '종목명' && (
                    <span className="ml-1">
                      {sortDirection === 'asc' ? '↑' : sortDirection === 'desc' ? '↓' : ''}
                    </span>
                  )}
                </div>
              </th>
              {filteredHeaders.filter(header => header === '등락율').map((header) => (
                <th
                  key={header}
                  scope="col"
                  className="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer border border-gray-200"
                  style={{
                    width: '65px', 
                    height: '35px'
                  }}
                  onClick={() => handleSort(header)} // 정렬 함수에는 데이터 키 "등락율" 전달
                >
                  <div className="flex justify-center items-center">
                    등락률 {/* 표시 텍스트만 변경 */}
                    {sortKey === header && (
                      <span className="ml-1">
                        {sortDirection === 'asc' ? '↑' : sortDirection === 'desc' ? '↓' : ''}
                      </span>
                    )}
                  </div>
                </th>
              ))}
              <th
                key="포지션"
                scope="col"
                // className 수정: cursor-help 추가
                className="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider cursor-help border border-gray-200" // cursor-help 추가
                style={{
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
                    {sortKey === '포지션' && (
                      <span className="ml-1">
                        {sortDirection === 'asc' ? '↑' : sortDirection === 'desc' ? '↓' : ''}
                      </span>
                    )}
                  </div>
                </GuideTooltip>
              </th>
              {['20일 이격', '돌파/이탈', '대표종목(RS)'].map((header) => (
                <th
                  key={header}
                  scope="col"
                  // className 수정: font-medium, text-gray-500, uppercase, tracking-wider 추가
                  className={`px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider border border-gray-200 ${header === '20일 이격' || header === '돌파/이탈' || header === '대표종목(RS)' ? 'cursor-help' : ''} hidden md:table-cell`} // 스타일 클래스 추가 및 cursor-help 유지
                  style={{
                    width: header === '20일 이격' ? '65px' : header === '돌파/이탈' ? '70px' : header === '대표종목(RS)' ? '380px' : '80px',
                    height: '35px'
                  }}
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
                      <div className="flex justify-center items-center">{header}</div>
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
            {(() => {
              // 산업별로 데이터를 그룹화하고 각 산업의 첫 번째 행 인덱스를 저장
              const industryGroups: { [industry: string]: { rows: Record<string, any>[], firstRowIndex: number } } = {};
              let allRows: { industry: string, row: Record<string, any> }[] = [];
              
              // sortedData의 키를 직접 사용하여 정렬된 순서대로 데이터 추가
              // 마켓은 항상 먼저 표시하고, 나머지는 sortedData의 키 순서대로 추가
              const industriesToRender = Object.keys(sortedData);
              
              // 마켓을 먼저 추가
              if (industriesToRender.includes('마켓')) {
                const industry = '마켓';
                industryGroups[industry] = { 
                  rows: sortedData[industry], 
                  firstRowIndex: allRows.length 
                };
                
                sortedData[industry].forEach(row => {
                  allRows.push({ industry, row });
                });
              }
              
              // 나머지 산업 그룹들을 sortedData 순서대로 추가
              industriesToRender.forEach(industry => {
                if (industry !== '마켓' && sortedData[industry]) {
                  industryGroups[industry] = { 
                    rows: sortedData[industry], 
                    firstRowIndex: allRows.length 
                  };
                  
                  sortedData[industry].forEach(row => {
                    allRows.push({ industry, row });
                  });
                }
              });
              
              // 각 행 렌더링
              return allRows.map((item, rowIndex) => {
                const { industry, row } = item;
                const isFirstRowOfIndustry = industryGroups[industry].firstRowIndex === rowIndex;
                const rowCount = industryGroups[industry].rows.length;
                
                // 산업이 바뀔 때 더 두꺼운 상단 테두리 적용
                const borderTopClass = isFirstRowOfIndustry ? 'border-t-2 border-t-gray-300' : '';
                
                return (
                  <tr key={`${industry}-${rowIndex}`} className={`hover:bg-gray-100 ${borderTopClass}`}>
                    {isFirstRowOfIndustry && (
                      <td
                        rowSpan={rowCount}
                        className="px-2 py-1 whitespace-nowrap text-xs border border-gray-200 align-middle"
                        style={{ width: '60px' }}
                      >
                        <div className="flex flex-col items-start">
                          <span className="text-xs px-1 sm:px-2 py-0.5 sm:py-1 bg-white text-gray-700 border border-gray-200 shadow-sm inline-block" style={{ borderRadius: '4px' }}>
                            {industry === '소비재/음식료' ? '소비재/음식료' : industry}
                          </span>
                          <span className={`mt-1 text-xs font-medium ${getAverageColorClass(getIndustryChangeRate(industry))}`} style={{ paddingLeft: '2px', width: '100%' }}>
                            {getIndustryChangeRate(industry)}
                          </span>
                        </div>
                      </td>
                    )}
                    <td 
                      className={`px-4 py-1 whitespace-nowrap text-xs border border-gray-200 ${isFirstRowOfIndustry ? 'border-t-2 border-t-gray-300' : ''}`} 
                      style={{ width: '60px', height: '16px' }}
                    >
                      {row['섹터']}
                    </td>
                    <td className={`px-4 py-1 whitespace-nowrap text-xs border border-gray-200 ${isFirstRowOfIndustry ? 'border-t-2 border-t-gray-300' : ''}`} style={{ width: '140px', height: '16px' }}>
                      {row['종목명'] || tickerMappingInfo.stockNameMap[row['티커']] || ''}
                    </td>
                    {filteredHeaders.filter(header => header === '등락율').map((header) => {
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
                      
                      return (
                        <td
                          key={header}
                          className={`px-4 py-1 whitespace-nowrap text-xs border border-gray-200 text-right tabular-nums ${isFirstRowOfIndustry ? 'border-t-2 border-t-gray-300' : ''}`}
                          style={{ width: '60px', height: '16px' }}
                        >
                          <span className={textColorClass}>{changeRateText || '-'}</span>
                        </td>
                      );
                    })}
                    <td className={`px-4 py-1 whitespace-nowrap text-xs border border-gray-200 ${isFirstRowOfIndustry ? 'border-t-2 border-t-gray-300' : ''}`} style={{ width: '78px', height: '16px' }}>
                      {/* 포지션 상태 표시 */}
                      <div className="flex items-center justify-center">
                        {renderPositionBadge(row['종목명'])}
                      </div>
                    </td>
                    {['20일 이격', '돌파/이탈', '대표종목(RS)'].map((header) => (
                      <td
                        key={header}
                        className={`px-4 py-1 ${header === '대표종목(RS)' ? 'whitespace-normal break-words' : 'whitespace-nowrap'} text-xs border border-gray-200 ${isFirstRowOfIndustry ? 'border-t-2 border-t-gray-300' : ''} hidden md:table-cell`}
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
                            let textColor = 'text-black'; // 항상 검정색으로 표시
                            
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
                            return <div className={`text-center tabular-nums ${textColor}`}>{displayDate}</div>;
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
                                        {name}(<span className={rsValue >= 90 ? 'font-bold' : ''}>{rsValueStr}</span>)
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
              });
            })()}
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
}
