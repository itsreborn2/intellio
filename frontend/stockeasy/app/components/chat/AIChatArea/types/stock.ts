// AIChatArea의 종목 관련 타입 정의

/**
 * 종목 옵션 타입 정의
 */
export interface StockOption {
  value: string;
  label: string;
  display?: string; // react-mentions를 위한 표시 이름
  stockName: string; // 종목명 저장
  stockCode: string; // 종목코드 저장
}

/**
 * 종목 검색 관련 상태 인터페이스
 */
export interface StockSearchState {
  searchTerm: string;
  filteredStocks: StockOption[];
  recentStocks: StockOption[];
  showStockSuggestions: boolean;
  isLoading: boolean;
  error: string | null;
  searchMode: boolean;
  stockOptions: StockOption[]; // 전체 종목 목록 추가
}

/**
 * 종목 검색 컨텍스트 액션 타입
 */
export type StockSearchAction =
  | { type: 'SET_SEARCH_TERM'; payload: string }
  | { type: 'SET_FILTERED_STOCKS'; payload: StockOption[] }
  | { type: 'SET_RECENT_STOCKS'; payload: StockOption[] }
  | { type: 'SHOW_SUGGESTIONS'; payload: boolean }
  | { type: 'SET_LOADING'; payload: boolean }
  | { type: 'SET_ERROR'; payload: string | null }
  | { type: 'SET_SEARCH_MODE'; payload: boolean }
  | { type: 'ADD_RECENT_STOCK'; payload: StockOption }
  | { type: 'CLEAR_RECENT_STOCKS' }
  | { type: 'SET_STOCK_OPTIONS'; payload: StockOption[] }; 