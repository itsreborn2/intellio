/**
 * StockSelectorContext.tsx
 * 종목 선택 상태 관리를 위한 컨텍스트 API
 */
import React, { createContext, useContext, useReducer, ReactNode, useMemo, useEffect, useState, useCallback, useRef } from 'react';
import { StockOption, StockSearchState, StockSearchAction } from '../types';
import Papa from 'papaparse';

// 로컬 스토리지 키 상수 정의
const LOCAL_STORAGE_RECENT_STOCKS_KEY = 'stockeasy_recent_stocks';

// 초기 상태 정의
const initialState: StockSearchState = {
  searchTerm: '',
  filteredStocks: [],
  recentStocks: [],
  showStockSuggestions: false,
  isLoading: false,
  error: null,
  searchMode: true, // 새로고침 시 처음부터 '종목명 또는 종목코드 검색' 표시하도록 설정
  stockOptions: [] // 종목 목록 추가
};

// 리듀서 함수 정의
function stockSearchReducer(state: StockSearchState, action: StockSearchAction): StockSearchState {
  switch (action.type) {
    case 'SET_SEARCH_TERM': {
      // 상태 업데이트만 하고 filteredStocks에는 영향 주지 않음
      return {
        ...state,
        searchTerm: action.payload
      };
    }
    
    case 'SET_FILTERED_STOCKS': {
      // 검색어 상태에 따른 필터링 결과 처리 로직 강화
      // 1. 검색어가 있는 경우: 필터링 결과 적용 (검색 결과가 우선)
      if (state.searchTerm.trim()) {
        return {
          ...state,
          filteredStocks: action.payload
        };
      }
      
      // 2. 검색어가 없고 최근 종목이 있는 경우: 최근 종목 표시
      if (!state.searchTerm.trim() && state.recentStocks.length > 0) {
        return {
          ...state,
          filteredStocks: action.payload.length > 0 ? action.payload : state.recentStocks
        };
      }
      
      // 3. 그 외의 경우: 제공된 필터링 결과 적용
      return {
        ...state,
        filteredStocks: action.payload
      };
    }
    
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
      
      // 검색어가 없고, 새로운 종목이 추가된 경우에만 filteredStocks를 갱신
      // 검색어가 있는 경우에는 검색 결과를 유지
      if (!state.searchTerm.trim()) {
        return {
          ...state,
          recentStocks: updatedRecentStocks,
          filteredStocks: state.searchTerm.trim() ? state.filteredStocks : updatedRecentStocks
        };
      }
      
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
  
  // 데이터 로드 중복 방지를 위한 ref
  const isLoadingRef = useRef(false);
  const hasLoggedRef = useRef(false);
  
  // 종목 목록 가져오기 함수 (useCallback으로 안정화)
  const fetchStockList = useCallback(async () => {
    // 이미 로드 중이면 중복 호출 방지
    if (isLoadingRef.current) {
      return;
    }
    
    // 이미 데이터가 있으면 다시 로드하지 않음
    if (state.stockOptions.length > 0) {
      return;
    }

    // 마지막 로드 시간 확인 (1시간 내에 다시 로드하지 않음)
    const now = Date.now();
    const oneHour = 60 * 60 * 1000;
    if (lastFetchTime > 0 && now - lastFetchTime < oneHour) {
      if (cachedStockData.length > 0) {
        dispatch({ type: 'SET_STOCK_OPTIONS', payload: cachedStockData });
        return;
      }
    }

    try {
      // 로드 시작 플래그 설정
      isLoadingRef.current = true;
      dispatch({ type: 'SET_LOADING', payload: true });
      dispatch({ type: 'SET_ERROR', payload: null }); // 요청 시작 시 오류 상태 초기화

      let stockData: any[] = [];
      let dataSource = '';

      try {
        // 1차 시도: Stock Data 컨테이너 API에서 종목 리스트 가져오기
        const apiBaseUrl = process.env.NEXT_PUBLIC_API_STOCK_DATA_URL;
        const apiUrl = `${apiBaseUrl}/api/v1/stock/list_for_stockai?gzip_enabled=true`;
        
        const response = await fetch(apiUrl, { 
          headers: {
            'Accept': 'application/json',
            'Content-Type': 'application/json'
          }
        });

        if (response.ok) {
          // API 응답 데이터 가져오기
          const apiData = await response.json();
          
          // API 응답에서 종목 리스트 추출 (응답 구조에 따라 조정 필요)
          const stockList = apiData.data || apiData.stocks || apiData;

          // API 응답 구조 확인 및 데이터 추출
          let rawStockList: any[] = [];
          
          if (apiData.data && Array.isArray(apiData.data) && apiData.headers) {
            // 압축된 형태의 응답 처리: headers와 data 배열
            const headers = apiData.headers; // ["code", "name", "market"]
            const codeIndex = headers.indexOf('code');
            const nameIndex = headers.indexOf('name');
            const marketIndex = headers.indexOf('market');
            
            if (codeIndex !== -1 && nameIndex !== -1) {
              rawStockList = apiData.data.map((row: any[]) => ({
                종목코드: row[codeIndex],
                종목명: row[nameIndex],
                market: marketIndex !== -1 ? row[marketIndex] : ''
              }));
            } else {
              throw new Error('API 응답의 헤더 구조가 예상과 다릅니다.');
            }
          } else if (apiData.stocks && Array.isArray(apiData.stocks)) {
            // 일반 형태의 응답 처리
            rawStockList = apiData.stocks.map((stock: any) => ({
              종목코드: stock.code,
              종목명: stock.name,
              market: stock.market || ''
            }));
          } else if (Array.isArray(apiData)) {
            // 배열 형태의 직접 응답
            rawStockList = apiData.map((stock: any) => ({
              종목코드: stock.code || stock.종목코드,
              종목명: stock.name || stock.종목명,
              market: stock.market || ''
            }));
          } else {
            throw new Error('API 응답 형식을 인식할 수 없습니다.');
          }

          if (rawStockList.length > 0) {
            // 중복 제거를 위한 Set 생성
            const uniqueStocks = new Set();

            // 종목 데이터 변환 (기존 구조 유지)
            stockData = rawStockList
              .filter((stock: any) => stock.종목명 && stock.종목코드) // 종목명과 종목코드가 있는 항목만 필터링
              .filter((stock: any) => {
                // 중복 제거 (같은 종목코드는 한 번만 포함)
                if (uniqueStocks.has(stock.종목코드)) {
                  return false;
                }
                uniqueStocks.add(stock.종목코드);
                return true;
              })
              .map((stock: any) => ({
                value: stock.종목코드, // 값은 종목코드로 설정
                label: `${stock.종목명}(${stock.종목코드})`, // 라벨은 종목명(종목코드)로 설정
                display: stock.종목명, // 메인 디스플레이 텍스트는 종목명만 (react-mentions용)
                stockName: stock.종목명, // 종목명 저장
                stockCode: stock.종목코드 // 종목코드 저장
              }));

            dataSource = 'API';
            console.log(`종목 리스트 API 로드 완료: ${stockData.length}개 종목`);
          } else {
            throw new Error('API 응답에서 유효한 종목 데이터를 찾을 수 없습니다.');
          }
        } else {
          throw new Error(`Stock Data API 요청 오류: ${response.status}`);
        }
      } catch (apiError) {
        console.warn('API에서 종목 리스트 로드 실패, CSV 파일로 fallback 시도:', apiError);
        
        try {
          // 2차 시도: CSV 파일에서 종목 리스트 가져오기 (fallback)
          const csvFilePath = '/requestfile/stock-data/stock_1idvb5kio0d6dchvoywe7ovwr-ez1cbpb.csv';
          
          const csvResponse = await fetch(csvFilePath, { cache: 'no-store' });

          if (!csvResponse.ok) {
            throw new Error(`CSV 파일 로드 오류: ${csvResponse.status}`);
          }

          // CSV 파일 내용 가져오기
          const csvContent = await csvResponse.text();

          // CSV 파싱
          const parsedData = Papa.parse(csvContent, {
            header: true,
            skipEmptyLines: true
          });

          // 중복 제거를 위한 Set 생성
          const uniqueStocks = new Set();

          // 종목 데이터 추출 (종목명(종목코드) 형식으로 변경)
          stockData = parsedData.data
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

          dataSource = 'CSV';
          console.log(`종목 리스트 CSV 로드 완료 (fallback): ${stockData.length}개 종목`);
        } catch (csvError) {
          throw new Error(`API 및 CSV 파일 모두에서 종목 리스트 로드 실패: ${csvError}`);
        }
      }

      if (stockData.length > 0) {
        // 한 번만 로그 출력 (세션당)
        if (!hasLoggedRef.current) {
          console.log(`종목 리스트 로드 완료 (${dataSource}): ${stockData.length}개 종목`);
          hasLoggedRef.current = true;
        }
        dispatch({ type: 'SET_STOCK_OPTIONS', payload: stockData });
        setCachedStockData(stockData);
        setLastFetchTime(Date.now());
      } else {
        const errorMsg = '유효한 종목 데이터를 받지 못했습니다.';
        dispatch({ type: 'SET_ERROR', payload: errorMsg });
      }
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : '종목 리스트를 가져오는 중 오류가 발생했습니다.';
      dispatch({ type: 'SET_ERROR', payload: errorMsg });
    } finally {
      isLoadingRef.current = false;
      dispatch({ type: 'SET_LOADING', payload: false });
    }
  }, [state.stockOptions.length, cachedStockData, lastFetchTime]); // 종속성을 명확히 지정

  // 컴포넌트 마운트 시 상태 초기화
  useEffect(() => {
    setIsMounted(true);
    
    // 로컬 스토리지에서 최근 조회 종목 가져오기
    try {
      const savedStocks = localStorage.getItem(LOCAL_STORAGE_RECENT_STOCKS_KEY);
      if (savedStocks) {
        const parsedStocks = JSON.parse(savedStocks);
        if (Array.isArray(parsedStocks) && parsedStocks.length > 0) {
          dispatch({ type: 'SET_RECENT_STOCKS', payload: parsedStocks.slice(0, 5) });
        }
      }
    } catch (error) {
    }
  }, []);

  // 컴포넌트 마운트 시 종목 리스트 가져오기 (최초 한 번만)
  useEffect(() => {
    // 마운트 되었을 때, 한번만 실행되도록 정적 변수 사용
    if (typeof (StockSelectorProvider as any).hasInitialized === 'undefined') {
      (StockSelectorProvider as any).hasInitialized = false;
    }

    if (isMounted && !(StockSelectorProvider as any).hasInitialized) {
      (StockSelectorProvider as any).hasInitialized = true;
      
      if (state.stockOptions.length === 0 && cachedStockData.length === 0) {
        fetchStockList();
      } else if (cachedStockData.length > 0 && state.stockOptions.length === 0) {
        // 캐시된 데이터가 있으면 사용
        dispatch({ type: 'SET_STOCK_OPTIONS', payload: cachedStockData });
      }
    }
  }, [isMounted]); // fetchStockList 의존성 제거
  
  // 편의 함수들 메모이제이션
  const contextValue = useMemo(() => ({
    state,
    dispatch,
    setSearchTerm: (term: string) => {
      dispatch({ type: 'SET_SEARCH_TERM', payload: term });
    },
    setFilteredStocks: (stocks: StockOption[]) => {
      dispatch({ type: 'SET_FILTERED_STOCKS', payload: stocks });
    },
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
    addRecentStock: (stock: StockOption) => {
      // 최근 종목에 추가
      const updatedRecentStocks = [
        stock, 
        ...state.recentStocks.filter(s => s.value !== stock.value)
      ].slice(0, 5); // 최대 5개 항목
      
      dispatch({ type: 'ADD_RECENT_STOCK', payload: stock });
      
      // 로컬 스토리지에 저장
      try {
        localStorage.setItem(LOCAL_STORAGE_RECENT_STOCKS_KEY, JSON.stringify(updatedRecentStocks));
      } catch (error) {
      }
    },
    clearRecentStocks: () => {
      dispatch({ type: 'CLEAR_RECENT_STOCKS' });
      // 로컬 스토리지에서도 삭제
      localStorage.removeItem(LOCAL_STORAGE_RECENT_STOCKS_KEY);
    },
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