// 종목 타입 정의
export interface StockOption {
  value: string;
  label: string;
  display?: string; // react-mentions를 위한 표시 이름
  stockName: string; // 종목명 저장
  stockCode: string; // 종목코드 저장
}

// 메시지 타입 정의
export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: number;
  stockInfo?: {
    stockName: string;
    stockCode: string;
  };
  responseId?: string; // 분석 결과의 고유 ID
}

// 공통 props 타입
export interface CommonChatProps {
  isMobile: boolean;
  windowWidth: number;
}

// 메시지 목록 컴포넌트 props
export interface MessageListProps extends CommonChatProps {
  messages: ChatMessage[];
  isProcessing: boolean;
  elapsedTime: number;
}

// 채팅 입력 컴포넌트 props
export interface ChatInputProps extends CommonChatProps {
  selectedStock: StockOption | null;
  inputMessage: string;
  onInputChange: (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => void;
  onSendMessage: () => void;
  onStockSelect: (stock: StockOption) => void;
  isInputCentered: boolean;
  showTitle: boolean;
  stockOptions: StockOption[];
  filteredStocks: StockOption[];
  recentStocks: StockOption[];
  showStockSuggestions: boolean;
  setShowStockSuggestions: (show: boolean) => void;
  searchMode: boolean;
  setSearchMode: (mode: boolean) => void;
  isLoading: boolean;
  error: string | null;
  inputRef: React.RefObject<HTMLInputElement>;
  stockSuggestionsRef: React.RefObject<HTMLDivElement>;
  handleInputFocus: () => void;
}

// 추천 질문 컴포넌트 props
export interface SuggestedQuestionsProps extends CommonChatProps {
  onStockSelect: (stock: StockOption) => void;
  setInputMessage: (message: string) => void;
  recentStocks: StockOption[];
  setRecentStocks: (stocks: StockOption[]) => void;
} 