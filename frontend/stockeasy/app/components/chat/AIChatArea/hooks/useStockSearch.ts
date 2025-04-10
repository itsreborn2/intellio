/**
 * useStockSearch.ts
 * 종목 검색 및 최근 조회 기능을 위한 커스텀 훅
 */
import { useState, useEffect, useCallback } from 'react';
import Papa from 'papaparse';
import { StockOption } from '../types';

interface UseStockSearchProps {
  maxRecentStocks?: number;
  cacheTimeout?: number;
}

/**
 * 종목 검색 및 관리를 위한 커스텀 훅
 * @param props 설정 객체 (최대 최근 종목 수, 캐시 타임아웃)
 * @returns 종목 검색 관련 상태 및 함수들
 */
export function useStockSearch({ 
  maxRecentStocks = 5, 
  cacheTimeout = 3600000 // 1시간 (밀리초)
}: UseStockSearchProps = {}) {
  // 기본 상태들
  const [stockOptions, setStockOptions] = useState<StockOption[]>([]);
  const [selectedStock, setSelectedStock] = useState<StockOption | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [lastFetchTime, setLastFetchTime] = useState<number>(0);
  const [cachedStockData, setCachedStockData] = useState<StockOption[]>([]);
  const [recentStocks, setRecentStocks] = useState<StockOption[]>([]);
  const [searchTerm, setSearchTerm] = useState<string>('');
  const [filteredStocks, setFilteredStocks] = useState<StockOption[]>([]);
  const [showStockSuggestions, setShowStockSuggestions] = useState<boolean>(false);
  const [searchMode, setSearchMode] = useState<boolean>(false);

  // 초기화 - 로컬 스토리지에서 최근 조회 종목 가져오기
  useEffect(() => {
    try {
      const savedStocks = localStorage.getItem('recentStocks');
      if (savedStocks) {
        const parsedStocks = JSON.parse(savedStocks);
        if (Array.isArray(parsedStocks) && parsedStocks.length > 0) {
          setRecentStocks(parsedStocks.slice(0, maxRecentStocks));
        }
      }
    } catch (error) {
      console.error('최근 종목 로드 실패:', error);
    }
  }, [maxRecentStocks]);

  // CSV에서 종목 목록 가져오기
  const fetchStockList = useCallback(async () => {
    // 캐시된 데이터가 있고 유효기간이 지나지 않았으면 재사용
    const now = Date.now();
    if (cachedStockData.length > 0 && (now - lastFetchTime) < cacheTimeout) {
      setStockOptions(cachedStockData);
      return;
    }

    try {
      setIsLoading(true);
      setError(null);

      // 서버 캐시 CSV 파일 경로
      const csvFilePath = '/requestfile/stock-data/stock_1idvb5kio0d6dchvoywe7ovwr-ez1cbpb.csv';

      // 서버 캐시 파일 가져오기 (항상 최신 데이터 사용)
      const response = await fetch(csvFilePath, { cache: 'no-store' });

      if (!response.ok) {
        throw new Error(`서버 캐시 파일 로드 오류: ${response.status}`);
      }

      // CSV 파일 내용 가져오기
      const csvContent = await response.text();

      // CSV 파싱
      const parsedData = Papa.parse(csvContent, {
        header: true,
        skipEmptyLines: true
      });

      // 중복 제거를 위한 Set 생성
      const uniqueStocks = new Set();

      // 종목 데이터 추출 (종목명(종목코드) 형식으로 변경)
      const stockData = parsedData.data
        .filter((row: any) => row.종목명 && row.종목코드) // 종목명과 종목코드가 있는 행만 필터링
        .filter((row: any) => {
          // 중복 제거 (같은 종목코드는 한 번만 포함)
          if (uniqueStocks.has(row.종목코드)) {
            return false;
          }
          uniqueStocks.add(row.종목코드);
          return true;
        })
        .map((row: any) => ({
          value: row.종목코드, // 값은 종목코드로 설정
          label: `${row.종목명}(${row.종목코드})`, // 라벨은 종목명(종목코드)로 설정
          display: row.종목명, // 메인 디스플레이 텍스트는 종목명만
          stockName: row.종목명, // 종목명 저장
          stockCode: row.종목코드 // 종목코드 저장
        }));

      if (stockData.length > 0) {
        console.log(`종목 데이터 ${stockData.length}개 로드 완료`);
        setStockOptions(stockData);
        setCachedStockData(stockData);
        setLastFetchTime(Date.now());
      } else {
        const errorMsg = '유효한 종목 데이터를 받지 못했습니다.';
        console.error(errorMsg);
        setError(errorMsg);
      }
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : '종목 리스트를 가져오는 중 오류가 발생했습니다.';
      console.error('종목 리스트 가져오기 오류:', error);
      setError(errorMsg);
    } finally {
      setIsLoading(false);
    }
  }, [cachedStockData, lastFetchTime, cacheTimeout]);

  // 종목 선택 처리
  const handleStockSelect = useCallback((stock: StockOption) => {
    setSelectedStock(stock);
    setSearchMode(false);
    setShowStockSuggestions(false);
    
    // 최근 조회 종목에 추가
    const updatedRecentStocks = [
      stock, 
      ...recentStocks.filter(s => s.value !== stock.value)
    ].slice(0, maxRecentStocks);
    
    setRecentStocks(updatedRecentStocks);
    
    // 로컬 스토리지에 저장
    try {
      localStorage.setItem('recentStocks', JSON.stringify(updatedRecentStocks));
    } catch (error) {
      console.error('최근 종목 저장 실패:', error);
    }
  }, [recentStocks, maxRecentStocks]);

  // 검색어 변경에 따른 필터링
  const filterStocks = useCallback((term: string) => {
    if (!term.trim()) {
      // 검색어가 없으면 최근 조회 종목 표시
      if (recentStocks.length > 0) {
        setFilteredStocks(recentStocks);
      } else {
        // 최근 조회 종목이 없으면 상위 5개 종목 표시
        setFilteredStocks(stockOptions.slice(0, 5));
      }
      return;
    }

    // 종목명이나 종목코드로 검색
    const filtered = stockOptions
      .filter(stock => {
        const stockName = stock.stockName.toLowerCase();
        const stockCode = stock.stockCode;
        const searchLower = term.toLowerCase();
        return stockName.includes(searchLower) || stockCode.includes(searchLower);
      })
      .slice(0, 10); // 최대 10개 결과만 표시

    setFilteredStocks(filtered);
  }, [stockOptions, recentStocks]);

  // 검색어 변경 핸들러
  const handleSearchTermChange = useCallback((term: string) => {
    setSearchTerm(term);
    filterStocks(term);
  }, [filterStocks]);

  // 검색 모드 설정
  const toggleSearchMode = useCallback((mode: boolean) => {
    setSearchMode(mode);
    if (mode) {
      // 검색 모드 활성화 시 기본 목록 표시
      if (recentStocks.length > 0) {
        setFilteredStocks(recentStocks);
      } else {
        setFilteredStocks(stockOptions.slice(0, 5));
      }
    }
  }, [stockOptions, recentStocks]);

  // 최근 종목 목록 초기화
  const clearRecentStocks = useCallback(() => {
    setRecentStocks([]);
    localStorage.removeItem('recentStocks');
  }, []);

  return {
    // 상태
    stockOptions,
    selectedStock,
    isLoading,
    error,
    recentStocks,
    searchTerm,
    filteredStocks,
    showStockSuggestions,
    searchMode,
    
    // 액션
    setSelectedStock,
    setSearchTerm: handleSearchTermChange,
    setShowStockSuggestions,
    setSearchMode: toggleSearchMode,
    handleStockSelect,
    fetchStockList,
    filterStocks,
    clearRecentStocks
  };
}

export default useStockSearch; 