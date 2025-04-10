/**
 * StockSelectorContext.tsx
 * 종목 선택 상태 관리를 위한 컨텍스트 API
 */
import React, { createContext, useContext, useReducer, ReactNode, useMemo, useEffect, useState } from 'react';
import { StockOption, StockSearchState, StockSearchAction } from '../types';
import Papa from 'papaparse';

// 초기 상태 정의
const initialState: StockSearchState = {
  searchTerm: '',
  filteredStocks: [],
  recentStocks: [],
  showStockSuggestions: false,
  isLoading: false,
  error: null,
  searchMode: false,
  stockOptions: [] // 종목 목록 추가
};

// 리듀서 함수 정의
function stockSearchReducer(state: StockSearchState, action: StockSearchAction): StockSearchState {
  switch (action.type) {
    case 'SET_SEARCH_TERM':
      return {
        ...state,
        searchTerm: action.payload
      };
    case 'SET_FILTERED_STOCKS':
      return {
        ...state,
        filteredStocks: action.payload
      };
    case 'SET_RECENT_STOCKS':
      return {
        ...state,
        recentStocks: action.payload
      };
    case 'SHOW_SUGGESTIONS':
      return {
        ...state,
        showStockSuggestions: action.payload
      };
    case 'SET_LOADING':
      return {
        ...state,
        isLoading: action.payload
      };
    case 'SET_ERROR':
      return {
        ...state,
        error: action.payload
      };
    case 'SET_SEARCH_MODE':
      return {
        ...state,
        searchMode: action.payload
      };
    case 'ADD_RECENT_STOCK': {
      const updatedRecentStocks = [
        action.payload,
        ...state.recentStocks.filter(stock => stock.value !== action.payload.value)
      ].slice(0, 5); // 최대 5개 항목
      
      return {
        ...state,
        recentStocks: updatedRecentStocks
      };
    }
    case 'CLEAR_RECENT_STOCKS':
      return {
        ...state,
        recentStocks: []
      };
    case 'SET_STOCK_OPTIONS':
      return {
        ...state,
        stockOptions: action.payload
      };
    default:
      return state;
  }
}

// 컨텍스트 타입 정의
type StockSelectorContextType = {
  state: StockSearchState;
  dispatch: React.Dispatch<StockSearchAction>;
  // 편의 함수들
  setSearchTerm: (term: string) => void;
  setFilteredStocks: (stocks: StockOption[]) => void;
  setRecentStocks: (stocks: StockOption[]) => void;
  showSuggestions: (show: boolean) => void;
  setLoading: (isLoading: boolean) => void;
  setError: (error: string | null) => void;
  setSearchMode: (isSearchMode: boolean) => void;
  addRecentStock: (stock: StockOption) => void;
  clearRecentStocks: () => void;
  setStockOptions: (stocks: StockOption[]) => void;
  fetchStockList: () => Promise<void>;
};

// 컨텍스트 생성
const StockSelectorContext = createContext<StockSelectorContextType | undefined>(undefined);

// 프로바이더 컴포넌트
export function StockSelectorProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(stockSearchReducer, initialState);
  const [isMounted, setIsMounted] = useState(false);
  const [cachedStockData, setCachedStockData] = useState<StockOption[]>([]);
  const [lastFetchTime, setLastFetchTime] = useState<number>(0);
  
  // 종목 목록 가져오기 함수
  const fetchStockList = async () => {
    try {
      dispatch({ type: 'SET_LOADING', payload: true });
      dispatch({ type: 'SET_ERROR', payload: null }); // 요청 시작 시 오류 상태 초기화

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

      console.log('파싱된 데이터 샘플:', parsedData.data.slice(0, 3));

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
          display: row.종목명, // 메인 디스플레이 텍스트는 종목명만 (react-mentions용)
          stockName: row.종목명, // 종목명 저장
          stockCode: row.종목코드 // 종목코드 저장
        }));

      if (stockData.length > 0) {
        console.log(`종목 데이터 ${stockData.length}개 로드 완료`);
        dispatch({ type: 'SET_STOCK_OPTIONS', payload: stockData });
        setCachedStockData(stockData);
        setLastFetchTime(Date.now());
      } else {
        const errorMsg = '유효한 종목 데이터를 받지 못했습니다.';
        console.error(errorMsg);
        dispatch({ type: 'SET_ERROR', payload: errorMsg });
      }

      dispatch({ type: 'SET_LOADING', payload: false });
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : '종목 리스트를 가져오는 중 오류가 발생했습니다.';
      console.error('종목 리스트 가져오기 오류:', error);
      dispatch({ type: 'SET_ERROR', payload: errorMsg });
      dispatch({ type: 'SET_LOADING', payload: false });
    }
  };

  // 컴포넌트 마운트 시 종목 리스트 가져오기
  useEffect(() => {
    setIsMounted(true);
  }, []);

  useEffect(() => {
    if (isMounted) {
      fetchStockList();
    }
  }, [isMounted]);
  
  // 편의 함수들 메모이제이션
  const contextValue = useMemo(() => ({
    state,
    dispatch,
    setSearchTerm: (term: string) => 
      dispatch({ type: 'SET_SEARCH_TERM', payload: term }),
    setFilteredStocks: (stocks: StockOption[]) => 
      dispatch({ type: 'SET_FILTERED_STOCKS', payload: stocks }),
    setRecentStocks: (stocks: StockOption[]) => 
      dispatch({ type: 'SET_RECENT_STOCKS', payload: stocks }),
    showSuggestions: (show: boolean) => 
      dispatch({ type: 'SHOW_SUGGESTIONS', payload: show }),
    setLoading: (isLoading: boolean) => 
      dispatch({ type: 'SET_LOADING', payload: isLoading }),
    setError: (error: string | null) => 
      dispatch({ type: 'SET_ERROR', payload: error }),
    setSearchMode: (isSearchMode: boolean) => 
      dispatch({ type: 'SET_SEARCH_MODE', payload: isSearchMode }),
    addRecentStock: (stock: StockOption) => 
      dispatch({ type: 'ADD_RECENT_STOCK', payload: stock }),
    clearRecentStocks: () => 
      dispatch({ type: 'CLEAR_RECENT_STOCKS' }),
    setStockOptions: (stocks: StockOption[]) => 
      dispatch({ type: 'SET_STOCK_OPTIONS', payload: stocks }),
    fetchStockList // 종목 목록 가져오기 함수 추가
  }), [state, dispatch, isMounted]);
  
  return (
    <StockSelectorContext.Provider value={contextValue}>
      {children}
    </StockSelectorContext.Provider>
  );
}

// 커스텀 훅
export function useStockSelector() {
  const context = useContext(StockSelectorContext);
  if (context === undefined) {
    throw new Error('useStockSelector must be used within a StockSelectorProvider');
  }
  return context;
}

export default StockSelectorContext; 