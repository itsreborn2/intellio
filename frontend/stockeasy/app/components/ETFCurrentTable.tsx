'use client'

import { useState, useEffect, useMemo, useCallback, useRef } from 'react'
import Papa from 'papaparse'
import React from 'react';
import { Sparklines, SparklinesLine, SparklinesSpots, SparklinesReferenceLine, SparklinesBars } from 'react-sparklines';
import { copyTableAsImage } from '../utils/tableCopyUtils';
import TableCopyButton from './TableCopyButton';
import { formatDateMMDD } from '../utils/dateUtils';

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

// ETF 파일 정보
const ETF_FILES = {
  currentPrice: {
    fileId: '1u46PGtK4RY4vUOBIXzvrFsk_mUsxznbA',
    fileName: 'today_price_etf.csv',
    path: '/requestfile/today_price_etf'
  }
};

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
  // 개별 ETF 차트 데이터 관련 상태 제거됨
  const [tickerMappingInfo, setTickerMappingInfo] = useState<{
    tickerMap: {[key: string]: string},
    stockNameMap: {[key: string]: string}
  }>({ tickerMap: {}, stockNameMap: {} });

  const [updateDate, setUpdateDate] = useState<string | null>(null); // Add state for update date
  const [maListMap, setMaListMap] = useState<Record<string, MaListData>>({}); // 종목명 -> 20malist 데이터
  
  // 테이블 복사 기능을 위한 ref 생성
  const tableRef = useRef<HTMLDivElement>(null);
  const headerRef = useRef<HTMLDivElement>(null);

  // 개별 ETF 차트 데이터 관련 티커 목록 및 매핑 테이블 제거됨
  
  // 개별 ETF 차트 데이터 로딩 관련 함수들(loadPriceData, loadAllPriceData, normalizeTicker) 제거됨
  
  useEffect(() => {
    // 페이지 로드 시 데이터 로드
    const loadData = async () => {
      setLoading(true);
      setError(null);
      
      try {
        // ETF 현재가 데이터 파일 경로 - 구글 드라이브 동기화 시스템과 일치
        const filePath = `${ETF_FILES.currentPrice.path}/${ETF_FILES.currentPrice.fileName}?t=${Date.now()}`;
        
        // (불필요한 로그 완전 제거)
// console.log('파일 경로:', filePath);
        
        // 로컬 캐시 파일 로드 - 직접 fetch 사용
        const response = await fetch(filePath);
        
        if (!response.ok) {
          throw new Error(`캐시 파일 로드 실패: ${response.status}`);
        }
        
        const csvText = await response.text();
        
        // CSV 텍스트 로깅 (디버깅용)
        // (불필요한 로그 완전 제거)
// console.log('CSV 파일 로드 완료, 크기:', csvText.length);
        if (csvText.length > 0) {
          // (불필요한 로그 완전 제거)
// console.log('CSV 첫 줄:', csvText.split('\n')[0]);
        } else {
          console.error('CSV 텍스트가 비어 있습니다!');
          setError('CSV 파일이 비어 있습니다.');
          setLoading(false);
          return;
        }
        
        // CSV 파싱 및 데이터 처리
        const parsedData = parseCSV(csvText);
        
        // 파싱된 데이터 확인
        if (!parsedData.groupedData || Object.keys(parsedData.groupedData).length === 0) {
          console.error('그룹화된 데이터가 없습니다.');
          setError('데이터를 그룹화할 수 없습니다. CSV 형식을 확인해주세요.');
          setLoading(false);
          return;
        }
        
        setCsvData(parsedData);
        
        // 모든 ETF 티커 추출
        const tickers: string[] = [];
        Object.values(parsedData.groupedData).forEach(group => {
          group.forEach(item => {
            if (item['티커']) {
              tickers.push(item['티커']);
            }
          });
        });
        
        // 티커별 종가 데이터 로드 부분 제거됨 - 개별 ETF 차트 데이터 로딩 관련 코드
        
        // 종목명 매핑 정보만 생성
        const stockNameMap: {[key: string]: string} = {};
        
        // 티커에서 종목명 매핑 생성
        tickers.forEach(ticker => {
          const matchingRow = parsedData.rows.find((row: Record<string, any>) =>
            row['티커'] === ticker ||
            row['티커']?.padStart(6, '0') === ticker.padStart(6, '0')
          );
          if (matchingRow) {
            stockNameMap[ticker] = matchingRow['종목명'] || '';
          }
        });
        
        setTickerMappingInfo({ tickerMap: {}, stockNameMap });
        
        // ETF 대표종목 데이터 로드 부분 제거됨 - 사용되지 않는 etf_stocklist.csv 파일
        
        // 20malist.csv 데이터 로드
        const maListResponse = await fetch('/requestfile/20ma_list/20malist.csv?t=' + Date.now());
        if (maListResponse.ok) {
          const maListCsvText = await maListResponse.text();
          const maListParsedResult = Papa.parse<MaListData>(maListCsvText, {
            header: true,
            skipEmptyLines: true,
            dynamicTyping: false, // 필요에 따라 true로 변경하여 타입 자동 변환
          });

          if (maListParsedResult.errors.length > 0) {
            console.error('20malist.csv Parsing Errors:', maListParsedResult.errors);
            // 에러 처리 (예: 사용자에게 알림)
          }

          // 종목명을 키로 하는 맵 생성
          const map: Record<string, MaListData> = {};
          for (const row of maListParsedResult.data) {
            if (row.종목명) { // 종목명이 있는 경우에만 추가
              map[row.종목명.trim()] = row; // 혹시 모를 공백 제거
            }
          }
          setMaListMap(map);
        }
        
        // 날짜 추출 및 상태 업데이트 (CSV 첫 행의 '날짜' 컬럼 사용)
        if (parsedData.rows && parsedData.rows.length > 0) {
          const dateString = parsedData.rows[0]['날짜']; 
          if (dateString) {
            const formattedDate = formatDateMMDD(dateString);
            if (formattedDate) {
              setUpdateDate(formattedDate);
            } else {
              // (불필요한 경고 로그 완전 제거)
// console.warn('날짜 형식을 변환할 수 없습니다:', dateString);
            }
          } else {
            // (불필요한 경고 로그 완전 제거)
// console.warn('CSV 데이터에 날짜 정보가 없습니다.');
          }
        }
        
      } catch (err) {
        console.error('데이터 로드 오류:', err);
        setError(`데이터 로드 중 오류가 발생했습니다: ${err instanceof Error ? err.message : String(err)}`);
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

  // 산업별 등락률(20malist.csv 기반) 반환 함수
  // maListMap에서 산업명을 찾아 해당 산업의 '산업 등락률' 값을 반환합니다.
  const getIndustryChangeRate = useCallback((industry: string): string => {
    // maListMap의 값들(MaListData 객체들)을 순회하며 산업명이 일치하는 첫 번째 행을 찾습니다.
    for (const stockName in maListMap) {
      const row = maListMap[stockName];
      // 타입 가드 추가: row 객체 및 필요한 속성이 존재하는지 확인
      if (row && typeof row === 'object' && '산업' in row && row['산업'] && typeof row['산업'] === 'string' && '산업 등락률' in row) {
        // 산업명 비교 시, 공백을 제거하고 대소문자 구분 없이 비교합니다.
        // maListMap의 '산업' 필드와 테이블의 industry 이름이 일치하는지 확인합니다.
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
      containerClasses += ' bg-gray-200 text-gray-700'; 
    } else if (positionText.includes('유지')) {
      // '유지' 포함 시 녹색 스타일 (이전 스타일)
      containerClasses += ' bg-green-100 text-green-800';
    } else {
      // '이탈' 포함 시 또는 기타 경우 회색 스타일 (이전 스타일)
      containerClasses += ' bg-gray-200 text-gray-700';
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
  
  // 산업 그룹 순서 정의
  const industryOrder = [
    '마켓',
    '반도체',
    '2차전지',
    '철강',
    '조선',
    '자동차',
    '에너지',
    '화학',
    '바이오',
    '제약',
    '헬스케어',
    '의료',
    '금융',
    '은행',
    '증권',
    '보험',
    '여행',
    '항공',
    '호텔',
    '레저',
    '엔터',
    '게임',
    '미디어',
    '통신',
    '인터넷',
    '소프트웨어',
    '유통',
    '소비재/음식료',
    '필수소비재',
    '전력기기',
    '인프라',
    '부동산',
    '친환경',
    '수소',
    '원자력',
    '메타버스',
    '로보틱스',
    '우주항공',
    '농업',
    '기타'
  ];

  // 모든 산업 그룹을 포함하도록 보장 (Set을 Array로 변환)
  const allIndustries = Array.from(new Set([...industryOrder, ...Object.keys(sortedData)]));
  
  // industryOrder의 순서를 유지하면서 누락된 산업 그룹을 추가
  const orderedIndustries = [...industryOrder].filter(industry => industry !== '기타');
  allIndustries.forEach(industry => {
    if (!orderedIndustries.includes(industry) && industry !== '기타') {
      orderedIndustries.push(industry);
    }
  });
  
  // '기타' 섹터를 항상 마지막에 추가
  if (allIndustries.includes('기타')) {
    orderedIndustries.push('기타');
  }

  // (불필요한 디버깅용 변수 및 코드 완전 삭제)
  // industryCounts, totalETFs, allTickers 등은 실제 렌더링/기능에 사용되지 않으므로 제거

  return (
    <div>
      <div ref={headerRef} className="flex justify-start items-center mb-2">
        <h2 className="text-sm md:text-base font-semibold text-gray-700">ETF 주요섹터</h2>
        <div className="flex items-center space-x-2 ml-auto">
          {/* 업데이트 날짜 표시 */}
          {updateDate && (
            <span className="text-gray-600 text-xs mr-2" style={{ fontSize: 'clamp(0.7rem, 0.7vw, 0.7rem)' }}>
              updated 16:30 {updateDate}
            </span>
          )}
          {/* 테이블 복사 버튼 */}
          <TableCopyButton
            tableRef={tableRef}
            headerRef={headerRef}
            tableName="ETF 현황"
            updateDateText={updateDate ? `updated 16:30 ${updateDate}` : undefined}
            // className="p-1 text-xs" // 필요시 버튼 스타일 조정
          />
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
                    width: '60px', // 너비 복원
                    height: '35px'
                  }}
                  onClick={() => handleSort(header)}
                >
                  <div className="flex justify-center items-center">
                    {header}
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
                className="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer border border-gray-200"
                style={{
                  width: '78px',
                  height: '35px'
                }}
                onClick={() => handleSort('포지션')}
              >
                <div className="flex justify-center items-center">
                  포지션
                  {sortKey === '포지션' && (
                    <span className="ml-1">
                      {sortDirection === 'asc' ? '↑' : sortDirection === 'desc' ? '↓' : ''}
                    </span>
                  )}
                </div>
              </th>
              {['20일 이격', '돌파/이탈', '대표종목(RS)'].map((header) => (
                <th
                  key={header}
                  scope="col"
                  className={`px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider border border-gray-200 hidden md:table-cell`}
                  style={{
                    width: header === '20일 이격' ? '80px' : header === '돌파/이탈' ? '80px' : header === '대표종목(RS)' ? '380px' : '80px',
                    height: '35px'
                  }}
                >
                  <div className="flex justify-center items-center">
                    {header === '돌파/이탈' ? <>돌파/<br />이탈</> : header}
                  </div>
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
                        className={`px-4 py-1 whitespace-nowrap text-xs border border-gray-200 ${isFirstRowOfIndustry ? 'border-t-2 border-t-gray-300' : ''} hidden md:table-cell`}
                        style={{
                          width: header === '20일 이격' ? '80px' : header === '돌파/이탈' ? '80px' : header === '대표종목(RS)' ? '380px' : '80px',
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
                            if (maPositionText?.startsWith('+')) {
                              textColor = 'text-red-500';
                            } else if (maPositionText?.startsWith('-')) {
                              textColor = 'text-blue-500';
                            }
                            return <div className={`text-right tabular-nums ${textColor}`}>{maPositionText}</div>;
                          } else if (header === '돌파/이탈') {
                            // maListMap에서 변동일 데이터 가져와서 포맷팅하기
                            const stockName = row['종목명'] as string;
                            const maData = maListMap[stockName?.trim()];
                            let displayDate = '-';
                            let textColor = 'text-gray-500'; // 기본값
                            
                            if (maData && maData['변동일']) {
                              try {
                                // YYYY-MM-DD 형식에서 MM-DD 추출
                                displayDate = maData['변동일'].substring(5);
                                
                                // 포지션 텍스트 기준으로 색상 결정
                                if (maData['포지션']?.includes('유지')) {
                                  textColor = 'text-red-500'; // 돌파 유지
                                } else if (maData['포지션']?.includes('이탈')) {
                                  textColor = 'text-blue-500'; // 이탈 유지
                                }
                                
                              } catch (e) {
                                console.error(`Error formatting date ${maData['변동일']}:`, e);
                                // 날짜 형식이 예상과 다를 경우 오류 로깅 및 '-' 표시
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

                            // 문자열 파싱: "종목명1(RS1), 종목명2(RS2), ..."
                            const items = representativeStocksRS.split(',').map((item: string) => item.trim()).filter((item: string) => item);

                            if (items.length === 0) {
                              return '-'; // 문자열이 비어 있거나 형식이 잘못됨
                            }

                            return (
                              <div className="flex flex-wrap items-center gap-1">
                                {items.map((itemString: string, index: number) => {
                                  // 정규식을 사용하여 이름과 RS 값 추출 (예: "삼성전자(34)")
                                  const match = itemString.match(/(.+)\s*\((\d+)\)/);
                                  if (match && match.length === 3) {
                                    const name = match[1].trim();
                                    const rsValue = parseInt(match[2], 10);
                                    const isBold = rsValue >= 90;

                                    return (
                                      <div key={index} className="flex items-center">
                                        <span className="text-xs">{name}</span>
                                        <span className={`text-xs ${isBold ? 'font-bold' : ''}`}>
                                          ({rsValue})
                                        </span>
                                      </div>
                                    );
                                  }
                                  // 형식 불일치 시 원본 문자열 표시 (오류 표시용)
                                  // 타입 명시적 지정으로 린트 오류 방지
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
  대표종목: string;
  등락률: string; // 또는 number
  변동일: string; // YYYY-MM-DD 형식
  포지션: string;
  '20일 이격': string; // 또는 number
}
