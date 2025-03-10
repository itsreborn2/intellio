'use client'

import { Suspense, useState, useEffect, useMemo, useRef } from 'react'
import Select from 'react-select'
import Papa from 'papaparse'
import { MentionsInput, Mention } from 'react-mentions'

// 종목 타입 정의
interface StockOption {
  value: string;
  label: string;
  display?: string; // react-mentions를 위한 표시 이름
  stockName: string; // 종목명 저장
  stockCode: string; // 종목코드 저장
}

// 메시지 타입 정의
interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: number;
  stockInfo?: {
    stockName: string;
    stockCode: string;
  };
}

// 컨텐츠 컴포넌트
function AIChatAreaContent() {
  // 종목 리스트 상태
  const [stockOptions, setStockOptions] = useState<StockOption[]>([]);
  const [selectedStock, setSelectedStock] = useState<StockOption | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [inputMessage, setInputMessage] = useState<string>('');
  const [isMounted, setIsMounted] = useState<boolean>(false); // 클라이언트 사이드 렌더링 확인용 상태
  const [error, setError] = useState<string | null>(null); // 오류 메시지 상태 추가
  const [lastFetchTime, setLastFetchTime] = useState<number>(0);
  const [cachedStockData, setCachedStockData] = useState<StockOption[]>([]);
  const [showStockSuggestions, setShowStockSuggestions] = useState<boolean>(false); // 종목 추천 표시 여부
  const [searchTerm, setSearchTerm] = useState<string>(''); // 종목 검색어 상태 추가
  const [filteredStocks, setFilteredStocks] = useState<StockOption[]>([]); // 필터링된 종목 목록
  const [recentStocks, setRecentStocks] = useState<StockOption[]>([]); // 최근 조회한 종목 목록
  const [messages, setMessages] = useState<ChatMessage[]>([]); // 채팅 메시지 목록
  const [isProcessing, setIsProcessing] = useState<boolean>(false); // 메시지 처리 중 상태
  
  const inputRef = useRef<HTMLInputElement>(null); // 입력 필드 참조
  const searchInputRef = useRef<HTMLInputElement>(null); // 검색 입력 필드 참조
  const stockSuggestionsRef = useRef<HTMLDivElement>(null); // 종목 추천 컨테이너 참조
  const messagesEndRef = useRef<HTMLDivElement>(null); // 메시지 영역 끝 참조
  
  const CACHE_DURATION = 3600000; // 캐시 유효 시간 (1시간 = 3600000ms)
  const MAX_RECENT_STOCKS = 5; // 최근 조회 종목 최대 개수

  // 클라이언트 사이드 렌더링 확인
  useEffect(() => {
    setIsMounted(true);
    
    // 로컬 스토리지에서 최근 조회 종목 불러오기
    try {
      const recentStocksStr = localStorage.getItem('recentStocks');
      if (recentStocksStr) {
        const savedRecentStocks = JSON.parse(recentStocksStr);
        if (Array.isArray(savedRecentStocks)) {
          setRecentStocks(savedRecentStocks);
        }
      }
    } catch (error) {
      console.warn('최근 조회 종목 불러오기 실패:', error);
    }
    
    // 외부 클릭 이벤트 리스너 추가
    const handleClickOutside = (event: MouseEvent) => {
      if (
        stockSuggestionsRef.current && 
        !stockSuggestionsRef.current.contains(event.target as Node) &&
        inputRef.current && 
        !inputRef.current.contains(event.target as Node)
      ) {
        setShowStockSuggestions(false);
      }
    };
    
    document.addEventListener('mousedown', handleClickOutside);
    
    // 컴포넌트 언마운트 시 이벤트 리스너 제거
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, []);

  // CSV 파일에서 종목 리스트 가져오기
  useEffect(() => {
    // 클라이언트 사이드에서만 실행
    if (!isMounted) return;

    const fetchStockList = async () => {
      try {
        // 캐시가 유효한지 확인 (캐시된 데이터가 있고, 캐시 유효 시간이 지나지 않았는지)
        const currentTime = Date.now();
        if (cachedStockData.length > 0 && (currentTime - lastFetchTime) < CACHE_DURATION) {
          console.log('캐시된 종목 데이터 사용:', cachedStockData.length);
          setStockOptions(cachedStockData);
          return;
        }

        setIsLoading(true);
        setError(null); // 요청 시작 시 오류 상태 초기화
        
        // 구글 드라이브 파일 ID
        const fileId = '1idVB5kIo0d6dChvOyWE7OvWr-eZ1cbpB';
        
        // API 라우트를 통해 구글 드라이브에서 종목 리스트 가져오기
        const response = await fetch('/api/stocks', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ fileId }),
        });
        
        if (!response.ok) {
          throw new Error(`API 응답 오류: ${response.status}`);
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
          setStockOptions(stockData);
          
          // 캐시 업데이트
          setCachedStockData(stockData);
          setLastFetchTime(currentTime);
          
          // 로컬 스토리지에도 캐싱 (페이지 새로고침 시에도 유지)
          try {
            localStorage.setItem('cachedStockData', JSON.stringify(stockData));
            localStorage.setItem('lastFetchTime', currentTime.toString());
          } catch (storageError) {
            console.warn('로컬 스토리지 저장 실패:', storageError);
          }
        } else {
          const errorMsg = '유효한 종목 데이터를 받지 못했습니다.';
          console.error(errorMsg);
          setError(errorMsg);
        }
        
        setIsLoading(false);
      } catch (error) {
        const errorMsg = error instanceof Error ? error.message : '종목 리스트를 가져오는 중 오류가 발생했습니다.';
        console.error('종목 리스트 가져오기 오류:', error);
        setError(errorMsg);
        setIsLoading(false);
      }
    };

    // 로컬 스토리지에서 캐시된 데이터 불러오기 시도
    try {
      const cachedDataStr = localStorage.getItem('cachedStockData');
      const cachedTimeStr = localStorage.getItem('lastFetchTime');
      
      if (cachedDataStr && cachedTimeStr) {
        const cachedData = JSON.parse(cachedDataStr);
        const cachedTime = parseInt(cachedTimeStr, 10);
        
        if (Array.isArray(cachedData) && cachedData.length > 0) {
          console.log('로컬 스토리지에서 캐시된 종목 데이터 불러옴:', cachedData.length);
          setCachedStockData(cachedData);
          setLastFetchTime(cachedTime);
          
          // 캐시가 유효한지 확인
          const currentTime = Date.now();
          if ((currentTime - cachedTime) < CACHE_DURATION) {
            console.log('유효한 캐시 사용');
            setStockOptions(cachedData);
            setIsLoading(false);
            return;
          } else {
            console.log('캐시 만료됨, 새로운 데이터 가져오기');
          }
        }
      }
    } catch (storageError) {
      console.warn('로컬 스토리지 읽기 실패:', storageError);
    }

    fetchStockList();
  }, [isMounted]); // 의존성 배열에서 cachedStockData와 lastFetchTime 제거

  // 메시지 전송 처리
  const handleSendMessage = async () => {
    if (!inputMessage.trim() && !selectedStock) return;
    
    // 사용자 메시지 생성
    const userMessageContent = selectedStock 
      ? `${selectedStock.stockName}(${selectedStock.stockCode}) 종목에 대해 ${inputMessage}` 
      : inputMessage;
    
    const userMessage: ChatMessage = {
      id: `user-${Date.now()}`,
      role: 'user',
      content: userMessageContent,
      timestamp: Date.now(),
      stockInfo: selectedStock ? {
        stockName: selectedStock.stockName,
        stockCode: selectedStock.stockCode
      } : undefined
    };
    
    // 메시지 목록에 사용자 메시지 추가
    setMessages(prevMessages => [...prevMessages, userMessage]);
    
    // 입력 필드 초기화
    setInputMessage('');
    setSelectedStock(null);
    
    // 메시지 처리 중 상태로 변경
    setIsProcessing(true);
    
    try {
      // 백엔드 API 호출
      const response = await fetch('/api/aichatarea', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          message: inputMessage,
          stockInfo: selectedStock ? {
            stockName: selectedStock.stockName,
            stockCode: selectedStock.stockCode
          } : null
        }),
      });
      
      if (!response.ok) {
        throw new Error(`API 응답 오류: ${response.status}`);
      }
      
      const responseData = await response.json();
      
      // 응답 메시지 생성
      const assistantMessage: ChatMessage = {
        id: `assistant-${Date.now()}`,
        role: 'assistant',
        content: responseData.content || '죄송합니다. 응답을 생성하는 중 오류가 발생했습니다.',
        timestamp: Date.now()
      };
      
      // 메시지 목록에 응답 메시지 추가
      setMessages(prevMessages => [...prevMessages, assistantMessage]);
    } catch (error) {
      console.error('메시지 전송 오류:', error);
      
      // 오류 메시지 생성
      const errorMessage: ChatMessage = {
        id: `error-${Date.now()}`,
        role: 'assistant',
        content: '죄송합니다. 서버와 통신 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.',
        timestamp: Date.now()
      };
      
      // 메시지 목록에 오류 메시지 추가
      setMessages(prevMessages => [...prevMessages, errorMessage]);
    } finally {
      // 메시지 처리 완료 상태로 변경
      setIsProcessing(false);
    }
  };
  
  // 메시지 영역 자동 스크롤
  useEffect(() => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages]);
  
  // 로컬 스토리지에서 메시지 불러오기
  useEffect(() => {
    if (!isMounted) return;
    
    try {
      const savedMessages = localStorage.getItem('chatMessages');
      if (savedMessages) {
        const parsedMessages = JSON.parse(savedMessages);
        if (Array.isArray(parsedMessages)) {
          setMessages(parsedMessages);
        }
      }
    } catch (error) {
      console.warn('메시지 불러오기 실패:', error);
    }
  }, [isMounted]);
  
  // 메시지 저장
  useEffect(() => {
    if (!isMounted || messages.length === 0) return;
    
    try {
      localStorage.setItem('chatMessages', JSON.stringify(messages));
    } catch (error) {
      console.warn('메시지 저장 실패:', error);
    }
  }, [messages, isMounted]);

  // 컴포넌트가 마운트되었을 때 초기 메시지 설정
  useEffect(() => {
    if (!isMounted) return;
    
    // 예시 메시지 추가 (개발용)
    if (messages.length === 0) {
      const initialMessages: ChatMessage[] = [
        {
          id: `user-${Date.now()-2000}`,
          role: 'user',
          content: '올해 실적 전망이 어떻게 돼?',
          timestamp: Date.now()-2000,
          stockInfo: {
            stockName: '삼성전자',
            stockCode: '005930'
          }
        },
        {
          id: `assistant-${Date.now()-1000}`,
          role: 'assistant',
          content: `삼성전자의 올해 실적 전망은 전반적으로 긍정적입니다. 주요 내용을 요약해 드리겠습니다:

1. **메모리 반도체 부문 호조**
   - HBM(High Bandwidth Memory) 수요 급증으로 메모리 가격 상승세가 유지될 전망
   - AI 서버용 고부가가치 메모리 비중 확대로 ASP 상승 및 수익성 개선 기대
   - 하반기 서버 및 모바일 시장 회복으로 메모리 부문 매출 성장 가속화

2. **파운드리 사업 경쟁력 강화**
   - 3나노 이하 첨단 공정 확대로 시장 점유율 상승 기대
   - NVIDIA와의 협력 강화로 AI 반도체 시장 입지 확대

3. **숫자로 보는 전망**
   - 매출액: 전년 대비 약 12% 증가 예상
   - 영업이익: 전년 대비 25~30% 성장 전망
   - 특히 반도체 부문 영업이익률 15% 이상으로 회복 기대

4. **위험 요소**
   - 글로벌 경쟁 심화 및 기술 변화 가속화
   - 무역 분쟁 및 보호무역주의 강화로 인한 불확실성
   - 원자재 및 부품 가격 변동성에 따른 수익성 영향

종합적으로 반도체 수요 증가와 AI 시장 확대에 따른 수혜가 예상되며, 특히 HBM 메모리와 파운드리 사업 확장이 실적 개선의 핵심 동력이 될 것으로 분석됩니다.

더 구체적인 세부 사업 부문별 전망이 필요하시면 추가로 질문해 주세요.`,
          timestamp: Date.now()-1000
        }
      ];
      
      setMessages(initialMessages);
    }
  }, [isMounted, messages.length]);

  // 입력 필드 포커스 시 종목 추천 목록 표시
  const handleInputFocus = () => {
    setShowStockSuggestions(true);
    // 초기 검색 결과는 전체 목록의 첫 5개
    setFilteredStocks(stockOptions.slice(0, 5));
  };

  // 종목 선택 처리
  const handleStockSelect = (stock: StockOption) => {
    setSelectedStock(stock);
    setShowStockSuggestions(false);
    setSearchTerm(''); // 검색어 초기화
    
    // 최근 조회 종목에 추가
    updateRecentStocks(stock);
    
    // 종목 선택 후 입력 필드에 포커스 유지
    if (inputRef.current) {
      inputRef.current.focus();
    }
  };

  // 최근 조회 종목 업데이트
  const updateRecentStocks = (stock: StockOption) => {
    // 이미 있는 종목이면 제거 (중복 방지)
    const filteredRecent = recentStocks.filter(item => item.value !== stock.value);
    
    // 새 종목을 맨 앞에 추가
    const newRecentStocks = [stock, ...filteredRecent].slice(0, MAX_RECENT_STOCKS);
    setRecentStocks(newRecentStocks);
    
    // 로컬 스토리지에 저장
    try {
      localStorage.setItem('recentStocks', JSON.stringify(newRecentStocks));
    } catch (error) {
      console.warn('최근 조회 종목 저장 실패:', error);
    }
  };

  // 입력 필드 변경 처리
  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const inputValue = e.target.value;
    setInputMessage(inputValue);
    // 자동 종목 매칭 로직 제거
  };

  // 종목 검색 입력 처리
  const handleSearchInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const searchValue = e.target.value;
    setSearchTerm(searchValue);
    
    // 검색어에 따라 종목 필터링
    if (searchValue.trim()) {
      const filtered = stockOptions.filter(stock => {
        const stockName = stock.stockName || stock.display || stock.label.split('(')[0];
        return (
          stockName.toLowerCase().includes(searchValue.toLowerCase()) ||
          stock.value.toLowerCase().includes(searchValue.toLowerCase()) ||
          stock.label.toLowerCase().includes(searchValue.toLowerCase())
        );
      });
      setFilteredStocks(filtered.slice(0, 20)); // 최대 20개까지 표시
    } else {
      setFilteredStocks(stockOptions.slice(0, 5)); // 검색어 없을 때는 첫 5개만
    }
  };

  // 검색 입력 필드에서 엔터키 처리
  const handleSearchInputKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      // 검색 결과가 있으면 첫 번째 종목 선택
      if (filteredStocks.length > 0) {
        handleStockSelect(filteredStocks[0]);
      }
    }
  };

  // 검색 입력 필드 클릭 시 전체 선택
  const handleSearchInputClick = () => {
    if (searchInputRef.current) {
      searchInputRef.current.select();
    }
  };

  // 스타일 정의
  const aiChatAreaStyle: React.CSSProperties = {
    display: 'flex',
    flexDirection: 'column',
    height: '100%',
    width: '100%',
    maxWidth: '1200px',
    padding: '0 0 0 0', // 모든 패딩 제거
    boxSizing: 'border-box',
    position: 'relative'
  };

  const inputAreaStyle: React.CSSProperties = {
    display: 'flex',
    alignItems: 'center', // 중앙 정렬로 변경
    width: '100%',
    paddingLeft: '0',
    boxSizing: 'border-box',
    marginTop: '3px', // 상단 여백 3px 추가
    marginBottom: '10px' // 메시지 영역과의 간격 추가
  };

  const integratedInputStyle: React.CSSProperties = {
    flex: '0 0 90%', // 80%에서 90%로 확장
    position: 'relative',
    marginRight: '0',
    marginTop: '0'
  };

  const inputStyle: React.CSSProperties = {
    width: '100%',
    height: '2.475rem',
    border: '1px solid #ccc',
    borderRadius: '4px',
    padding: selectedStock ? '0 40px 0 130px' : '0 40px 0 8px', // 종목 선택 시 왼쪽 패딩 증가
    fontSize: '0.81rem',
    outline: 'none',
    boxSizing: 'border-box',
    position: 'relative'
  };

  const stockSuggestionsStyle: React.CSSProperties = {
    position: 'absolute',
    top: '100%',
    left: 0,
    width: '100%',
    maxHeight: 'none', // 최대 높이 제거
    overflowY: 'visible', // 세로 스크롤 제거
    backgroundColor: 'white',
    border: '1px solid #ccc',
    borderRadius: '4px',
    boxShadow: '0 2px 4px rgba(0, 0, 0, 0.1)',
    zIndex: 1000,
    marginTop: '4px',
    padding: '8px'
  };

  return (
    <div className="ai-chat-area" style={aiChatAreaStyle}>
      {/* 입력 영역 */}
      <div className="input-area" style={inputAreaStyle}>
        <div className="integrated-input" style={integratedInputStyle}>
          <input
            ref={inputRef}
            placeholder={selectedStock ? "종목에 대해 무엇이든 물어보세요" : "종목을 선택하고 메시지를 입력하세요"}
            className="integrated-input-field"
            type="text"
            value={inputMessage}
            onChange={handleInputChange}
            onFocus={handleInputFocus}
            style={inputStyle}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                handleSendMessage();
              }
            }}
          />
          
          {/* 전송 아이콘 */}
          <button
            onClick={handleSendMessage}
            disabled={isProcessing}
            style={{
              position: 'absolute',
              right: '8px',
              top: '50%',
              transform: 'translateY(-50%)',
              backgroundColor: 'transparent',
              border: 'none',
              cursor: isProcessing ? 'not-allowed' : 'pointer',
              padding: '4px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              zIndex: 2
            }}
            title="메시지 전송"
          >
            <svg 
              width="20" 
              height="20" 
              viewBox="0 0 24 24" 
              fill="none" 
              stroke={isProcessing ? "#cccccc" : "#4a90e2"} 
              strokeWidth="2" 
              strokeLinecap="round" 
              strokeLinejoin="round"
            >
              <line x1="22" y1="2" x2="11" y2="13"></line>
              <polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
            </svg>
          </button>
          
          {/* 선택된 종목 표시 영역 */}
          {selectedStock && (
            <div style={{
              position: 'absolute',
              left: '8px',
              top: '50%',
              transform: 'translateY(-50%)',
              backgroundColor: '#f0f0f0',
              padding: '2px 6px',
              borderRadius: '4px',
              fontSize: '0.75rem',
              maxWidth: '120px',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
              zIndex: 2,
              cursor: 'pointer'
            }}
            onClick={() => {
              setSelectedStock(null); // 클릭 시 선택된 종목 제거
              if (inputRef.current) {
                inputRef.current.focus();
              }
            }}
            title="클릭하여 선택 해제"
            >
              {selectedStock.stockName || selectedStock.display || selectedStock.label.split('(')[0]}
            </div>
          )}
          
          {/* 종목 추천 목록 */}
          {isMounted && showStockSuggestions && (
            <div ref={stockSuggestionsRef} style={stockSuggestionsStyle}>
              {/* 종목 검색 입력 필드 */}
              <div style={{ marginBottom: '8px', position: 'relative' }}>
                <input
                  ref={searchInputRef}
                  placeholder="종목명 또는 종목코드 검색..."
                  type="text"
                  value={searchTerm}
                  onChange={handleSearchInputChange}
                  onKeyDown={handleSearchInputKeyDown} // 엔터키 이벤트 처리 추가
                  onClick={handleSearchInputClick} // 클릭 이벤트 처리 추가
                  style={{
                    width: '100%',
                    padding: '6px 8px',
                    border: '1px solid #ddd',
                    borderRadius: '4px',
                    fontSize: '0.81rem',
                    boxSizing: 'border-box'
                  }}
                />
                {searchTerm && (
                  <button
                    onClick={() => {
                      setSearchTerm('');
                      setFilteredStocks(stockOptions.slice(0, 5));
                      if (searchInputRef.current) {
                        searchInputRef.current.focus();
                      }
                    }}
                    style={{
                      position: 'absolute',
                      right: '8px',
                      top: '50%',
                      transform: 'translateY(-50%)',
                      background: 'none',
                      border: 'none',
                      fontSize: '0.7rem',
                      color: '#999',
                      cursor: 'pointer',
                      padding: '2px 4px'
                    }}
                  >
                    ✕
                  </button>
                )}
              </div>

              {isLoading ? (
                <div style={{ padding: '8px', textAlign: 'center' }}>종목 로딩 중...</div>
              ) : error ? (
                <div style={{ padding: '8px', color: 'red' }}>{error}</div>
              ) : filteredStocks.length === 0 ? (
                <div style={{ padding: '8px', textAlign: 'center', color: '#666' }}>
                  검색 결과가 없습니다
                </div>
              ) : (
                <div>
                  <div style={{ 
                    display: 'flex',
                    flexDirection: 'row',
                    flexWrap: 'nowrap',
                    overflowX: 'auto',
                    gap: '8px',
                    paddingBottom: '4px',
                    msOverflowStyle: 'none', // IE, Edge 스크롤바 숨김
                    scrollbarWidth: 'none' // Firefox 스크롤바 숨김
                  }}>
                    {filteredStocks.map((stock) => (
                      <button 
                        key={stock.value} 
                        onClick={() => handleStockSelect(stock)}
                        style={{ 
                          padding: '4px 8px',
                          cursor: 'pointer',
                          fontSize: '0.75rem',
                          whiteSpace: 'nowrap',
                          borderRadius: '4px',
                          border: '1px solid #ddd',
                          backgroundColor: '#f5f5f5',
                          color: '#333',
                          display: 'flex',
                          alignItems: 'center',
                          minWidth: 'fit-content',
                          flexShrink: 0,
                          transition: 'background-color 0.2s'
                        }}
                        onMouseEnter={(e) => {
                          e.currentTarget.style.backgroundColor = '#e0e0e0';
                        }}
                        onMouseLeave={(e) => {
                          e.currentTarget.style.backgroundColor = '#f5f5f5';
                        }}
                      >
                        <span style={{ fontWeight: 'bold' }}>
                          {stock.stockName || stock.display || stock.label.split('(')[0]}
                        </span>
                        <span style={{ color: '#666', marginLeft: '4px', fontSize: '0.7rem' }}>
                          ({stock.value})
                        </span>
                      </button>
                    ))}
                  </div>
                </div>
              )}
              
              {/* 최근 조회 종목 목록 */}
              {!isLoading && !error && recentStocks.length > 0 && (
                <div style={{ 
                  marginTop: '12px',
                  borderTop: '1px solid #eee',
                  paddingTop: '8px'
                }}>
                  <div style={{ 
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    marginBottom: '6px'
                  }}>
                    <div style={{ 
                      fontSize: '0.75rem', 
                      color: '#666', 
                      fontWeight: 'bold'
                    }}>
                      최근 조회 종목
                    </div>
                    <button
                      onClick={() => {
                        setRecentStocks([]);
                        localStorage.removeItem('recentStocks');
                      }}
                      style={{
                        background: 'none',
                        border: 'none',
                        fontSize: '0.7rem',
                        color: '#999',
                        cursor: 'pointer',
                        padding: '2px 4px'
                      }}
                    >
                      지우기
                    </button>
                  </div>
                  <div style={{ 
                    display: 'flex',
                    flexDirection: 'row',
                    flexWrap: 'nowrap',
                    overflowX: 'auto',
                    gap: '8px',
                    paddingBottom: '4px',
                    msOverflowStyle: 'none', // IE, Edge 스크롤바 숨김
                    scrollbarWidth: 'none' // Firefox 스크롤바 숨김
                  }}>
                    {recentStocks.map((stock) => (
                      <button 
                        key={stock.value} 
                        onClick={() => handleStockSelect(stock)}
                        style={{ 
                          padding: '4px 8px',
                          cursor: 'pointer',
                          fontSize: '0.75rem',
                          whiteSpace: 'nowrap',
                          borderRadius: '4px',
                          border: '1px solid #ddd',
                          backgroundColor: '#f5f5f5',
                          color: '#333',
                          display: 'flex',
                          alignItems: 'center',
                          minWidth: 'fit-content',
                          flexShrink: 0,
                          transition: 'background-color 0.2s'
                        }}
                        onMouseEnter={(e) => {
                          e.currentTarget.style.backgroundColor = '#e0e0e0';
                        }}
                        onMouseLeave={(e) => {
                          e.currentTarget.style.backgroundColor = '#f5f5f5';
                        }}
                      >
                        <span style={{ fontWeight: 'bold' }}>
                          {stock.stockName || stock.display || stock.label.split('(')[0]}
                        </span>
                        <span style={{ color: '#666', marginLeft: '4px', fontSize: '0.7rem' }}>
                          ({stock.value})
                        </span>
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
      
      {/* 메시지 표시 영역 */}
      <div 
        className="messages-container"
        style={{
          flex: 1,
          overflowY: 'auto',
          padding: '10px',
          marginBottom: '0', // 하단 여백 제거
          border: '1px solid #eee',
          borderRadius: '4px',
          backgroundColor: '#ffffff', // 배경색을 흰색으로 변경
          marginTop: '0', // 상단 여백 제거
          width: '100%', // 너비 100%로 확장
          height: 'calc(100% - 50px)', // 입력 영역을 제외한 전체 높이
          boxSizing: 'border-box', // 패딩과 테두리를 너비에 포함
          borderRight: '1px solid #eee', // 우측 테두리 추가
          borderBottom: '1px solid #eee' // 하단 테두리 추가
        }}
      >
        {messages.length === 0 ? (
          <div style={{ 
            textAlign: 'center', 
            color: '#888', 
            padding: '20px',
            fontSize: '0.9rem', 
            display: 'none' // 안내 텍스트 숨기기
          }}>
            종목을 선택하고 질문을 입력하세요.
          </div>
        ) : (
          messages.map(message => (
            <div 
              key={message.id}
              style={{
                marginBottom: '16px',
                display: 'flex',
                flexDirection: 'column',
                alignItems: message.role === 'user' ? 'flex-end' : 'flex-start'
              }}
            >
              <div style={{
                backgroundColor: message.role === 'user' ? '#e1f5fe' : '#ffffff',
                padding: '10px 14px',
                borderRadius: '12px',
                maxWidth: '80%',
                boxShadow: '0 1px 2px rgba(0, 0, 0, 0.1)',
                position: 'relative'
              }}>
                {message.stockInfo && (
                  <div style={{
                    fontSize: '0.75rem',
                    fontWeight: 'bold',
                    color: '#0066cc',
                    marginBottom: '4px'
                  }}>
                    {message.stockInfo.stockName} ({message.stockInfo.stockCode})
                  </div>
                )}
                <div style={{
                  whiteSpace: message.role === 'user' ? 'nowrap' : 'pre-wrap',
                  overflow: message.role === 'user' ? 'hidden' : 'visible',
                  textOverflow: message.role === 'user' ? 'ellipsis' : 'clip',
                  wordBreak: 'break-word',
                  fontSize: '0.75rem',
                  lineHeight: '1.5'
                }}>
                  {message.content}
                </div>
              </div>
            </div>
          ))
        )}
        <div ref={messagesEndRef} />
      </div>
    </div>
  );
}

// 메인 컴포넌트
export default function AIChatArea() {
  return (
    <Suspense fallback={<div className="ai-chat-area animate-pulse">
      <div className="h-10 bg-gray-200 rounded"></div>
    </div>}>
      <AIChatAreaContent />
    </Suspense>
  )
}
