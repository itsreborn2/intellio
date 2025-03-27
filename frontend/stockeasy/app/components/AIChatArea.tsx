'use client'

import { Suspense, useState, useEffect, useMemo, useRef } from 'react'
import Select from 'react-select'
import Papa from 'papaparse'
import { MentionsInput, Mention } from 'react-mentions'
import { sendChatMessage } from '@/services/api/chat'
import { IChatResponse } from '@/types/api/chat'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import rehypeRaw from 'rehype-raw'
import rehypeHighlight from 'rehype-highlight'
import { CSSProperties } from 'react'
import 'highlight.js/styles/github.css' // 하이라이트 스타일 추가

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
  const [elapsedTime, setElapsedTime] = useState<number>(0);
  const timerRef = useRef<NodeJS.Timeout | null>(null);
  const [isMobile, setIsMobile] = useState<boolean>(false);
  const [isSidebarOpen, setIsSidebarOpen] = useState<boolean>(false); // 사이드바 상태 추가
  const [isInputCentered, setIsInputCentered] = useState<boolean>(true); // 입력 필드 중앙 배치 상태 추가
  const [showTitle, setShowTitle] = useState<boolean>(true); // 제목 표시 여부

  const inputRef = useRef<HTMLInputElement>(null); // 입력 필드 참조
  const searchInputRef = useRef<HTMLInputElement>(null); // 검색 입력 필드 참조
  const stockSuggestionsRef = useRef<HTMLDivElement>(null); // 종목 추천 컨테이너 참조
  const messagesEndRef = useRef<HTMLDivElement>(null); // 메시지 영역 끝 참조
  const messagesContainerRef = useRef<HTMLDivElement>(null); // 메시지 컨테이너 참조

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

      // 타이머 정리
      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
    };
  }, []);

  // 모바일 환경 감지
  useEffect(() => {
    const checkIfMobile = () => {
      const isMobileView = window.innerWidth <= 768;
      setIsMobile(isMobileView);
      
      // 모바일 상태가 변경될 때마다 DOM에 클래스 추가/제거
      if (isMobileView) {
        document.body.classList.add('mobile-view');
      } else {
        document.body.classList.remove('mobile-view');
        setIsSidebarOpen(false); // PC 화면으로 전환 시 사이드바 상태 초기화
      }
    };

    // 초기 실행
    checkIfMobile();

    // 화면 크기 변경 시 감지
    window.addEventListener('resize', checkIfMobile);

    // 컴포넌트 언마운트 시 이벤트 리스너 제거
    return () => {
      window.removeEventListener('resize', checkIfMobile);
    };
  }, []);

  // 사이드바 상태 감지
  useEffect(() => {
    // 사이드바 열림/닫힘 이벤트 리스너
    const handleSidebarToggle = (e: CustomEvent) => {
      setIsSidebarOpen(e.detail.isOpen);
    };

    // 커스텀 이벤트 리스너 등록
    window.addEventListener('sidebarToggle' as any, handleSidebarToggle);

    return () => {
      window.removeEventListener('sidebarToggle' as any, handleSidebarToggle);
    };
  }, []);

  // CSV 파일에서 종목 리스트 가져오기
  useEffect(() => {
    // 클라이언트 사이드에서만 실행
    if (!isMounted) return;

    const fetchStockList = async () => {
      try {
        setIsLoading(true);
        setError(null); // 요청 시작 시 오류 상태 초기화

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
          setStockOptions(stockData);
          setCachedStockData(stockData);
          setLastFetchTime(Date.now());
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

    fetchStockList();
  }, [isMounted]); // 의존성 배열에서 cachedStockData와 lastFetchTime 제거

  // 메시지 전송 처리
  const handleSendMessage = async () => {
    if (isProcessing || !selectedStock || !inputMessage.trim()) return;

    // 중앙 배치 해제 - 메시지 전송 시에만 화면을 아래로 내림
    if (isInputCentered) {
      setIsInputCentered(false);
    }

    // 메시지 ID 생성
    const messageId = `msg_${Date.now()}`;

    // 사용자 메시지 생성
    const userMessageContent = inputMessage;

    const userMessage: ChatMessage = {
      id: messageId,
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

    // 메시지 처리 중 상태로 변경
    setIsProcessing(true);
    setElapsedTime(0);

    // 타이머 시작
    if (timerRef.current) {
      clearInterval(timerRef.current);
    }

    timerRef.current = setInterval(() => {
      setElapsedTime(prev => prev + 1);
    }, 1000);

    try {
      // 백엔드 API 호출
      const response:IChatResponse = await sendChatMessage(selectedStock?.stockCode || '', selectedStock?.stockName || '', inputMessage);

      if (!response.ok) {
        throw new Error(`API 응답 오류: ${response.status_message}`);
      }

      const responseData = response.answer;
      console.log('answer : ', responseData);

      // 응답 메시지 생성
      const assistantMessage: ChatMessage = {
        id: `assistant-${Date.now()}`,
        role: 'assistant', 
        content: responseData || '죄송합니다. 응답을 생성하는 중 오류가 발생했습니다.',
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

      // 타이머 중지
      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
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

  }, [isMounted]);

  // 메시지 저장 - 서버 측 저장 방식으로 변경 (현재는 구현하지 않음)
  useEffect(() => {
    // 메시지 저장 로직은 서버 측 구현이 필요하므로 여기서는 생략
    // 추후 API 엔드포인트를 통해 메시지를 서버에 저장하는 방식으로 변경 가능
  }, [messages, isMounted]);

  // 컴포넌트가 마운트되었을 때 초기 메시지 설정
  useEffect(() => {
    if (!isMounted) return;

    // 이미 메시지가 있으면 초기화하지 않음
    if (messages.length > 0) {
      return;
    }

    // 초기 메시지 설정 로직은 위의 fetchMessages 함수에서 처리
  }, [isMounted, messages.length]);

  // 입력 필드 포커스 시 종목 추천 목록 표시
  const handleInputFocus = () => {
    // 종목이 선택되어 있지 않은 경우, 최근 종목 목록 및 기본 종목 추천 표시
    if (!selectedStock) {
      // 최근 조회 종목이 있으면 표시
      if (recentStocks.length > 0) {
        setFilteredStocks(recentStocks);
      } else {
        // 최근 조회 종목이 없으면 기본 종목 추천 표시 (상위 5개)
        setFilteredStocks(stockOptions.slice(0, 5));
      }
      // 팝업 표시
      setShowStockSuggestions(true);
    }
  };

  // 입력 필드에 텍스트 입력 시 중앙 배치에서 일반 배치로 전환
  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const inputValue = e.target.value;
    setInputMessage(inputValue);
    
    // 종목이 선택되지 않은 상태에서 입력 시 종목 검색 기능 활성화
    if (!selectedStock) {
      // 입력값에 따라 종목 검색
      const searchValue = inputValue.trim();
      setSearchTerm(searchValue);
      
      if (searchValue.length > 0) {
        // 종목 검색 로직
        const filtered = stockOptions.filter(stock => {
          const stockName = stock.stockName || stock.display || stock.label || '';
          const stockCode = stock.value || '';
          return stockName.toLowerCase().includes(searchValue.toLowerCase()) || 
                 stockCode.includes(searchValue);
        }).slice(0, 5);
        
        setFilteredStocks(filtered);
        
        // 검색 결과가 있으면 종목 추천 목록 표시
        if (filtered.length > 0) {
          setShowStockSuggestions(true);
        } else {
          setShowStockSuggestions(false);
        }
      } else {
        // 입력값이 없으면 최근 조회 종목 표시
        setShowStockSuggestions(recentStocks.length > 0);
        setFilteredStocks([]);
      }
    }
    
    // 기존 높이 조정 로직 유지
    const target = e.target;
    const textLength = target.value.length;
    if (textLength > 0) {
      const newHeight = Math.min(100, Math.max(40, 40 + Math.floor(textLength / 50) * 20));
      target.style.height = `${newHeight}px`;
    } else {
      target.style.height = '2.97rem';
    }
  };

  // 종목 선택 처리
  const handleStockSelect = (stock: StockOption) => {
    console.log('종목 선택: ', stock.label); // 디버깅용 로그
    
    // 즉시 팝업 닫기 (최우선 처리)
    setShowStockSuggestions(false);
    
    // 선택된 종목 설정
    setSelectedStock(stock);
    setInputMessage(''); // 입력 필드 초기화
    
    // 선택한 종목을 최근 조회 목록에 추가
    const updatedRecentStocks = [stock, ...recentStocks.filter(s => s.value !== stock.value)].slice(0, 5);
    setRecentStocks(updatedRecentStocks);
    
    // 로컬 스토리지에 최근 조회 종목 저장
    try {
      localStorage.setItem('recentStocks', JSON.stringify(updatedRecentStocks));
    } catch (error) {
      console.error('Failed to save recent stocks to localStorage:', error);
    }
    
    // 입력 필드에 포커스
    setTimeout(() => {
      if (inputRef.current) {
        inputRef.current.focus();
      }
    }, 100);
  };

  // 메시지가 있으면 중앙 배치 해제
  useEffect(() => {
    if (messages.length > 0 && isInputCentered) {
      setIsInputCentered(false);
    }
  }, [messages, isInputCentered]);

  // 타임스탬프 포맷팅 함수 수정
  const formatTimestamp = (timestamp: number): string => {
    const date = new Date(timestamp);
    const hours = date.getHours().toString().padStart(2, '0');
    const minutes = date.getMinutes().toString().padStart(2, '0');
    return `${hours}:${minutes}`;
  };

  // 로딩 스피너 컴포넌트
  const LoadingSpinner = () => (
    <div className="loading-spinner" style={{
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      margin: '12px 0'
    }}>
      <div style={{
        width: '36px',
        height: '36px',
        borderRadius: '50%',
        border: '3px solid #f3f3f3',
        borderTop: '3px solid #3498db',
        animation: 'spin 1s linear infinite',
      }}></div>
      <style jsx>{`
        @keyframes spin {
          0% { transform: rotate(0deg); }
          100% { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  );

  // 검색 중 타이머 컴포넌트
  const SearchTimer = () => (
    <div className="search-timer" style={{
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      gap: '8px',
      backgroundColor: '#f5f9ff',
      padding: '8px 12px',
      borderRadius: '8px',
      boxShadow: '0 2px 5px rgba(0, 0, 0, 0.05)',
      marginBottom: '12px'
    }}>
      <div style={{
        position: 'relative',
        width: '28px',
        height: '28px',
        borderRadius: '50%',
        border: '2px solid #e1e1e1',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center'
      }}>
        <div style={{
          position: 'absolute',
          top: '50%',
          left: '50%',
          width: '14px',
          height: '2px',
          background: 'transparent',
          transform: 'rotate(0deg) translateX(0)',
          transformOrigin: '0 0',
          zIndex: 2
        }}>
          <div style={{
            position: 'absolute',
            width: '8px',
            height: '2px',
            backgroundColor: '#3498db',
            animation: 'stopwatch-sec 60s steps(60, end) infinite',
            transformOrigin: 'left center'
          }}></div>
        </div>
        <div style={{
          width: '6px',
          height: '6px',
          backgroundColor: '#3498db',
          borderRadius: '50%',
          zIndex: 3
        }}></div>
      </div>
      <div style={{
        fontFamily: 'monospace',
        fontSize: '0.9rem',
        fontWeight: 'bold',
        color: '#555'
      }}>
        {Math.floor(elapsedTime / 60).toString().padStart(2, '0')}:{(elapsedTime % 60).toString().padStart(2, '0')}
      </div>
      <style jsx>{`
        @keyframes stopwatch-sec {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  );

  // 검색 애니메이션 컴포넌트
  const SearchingAnimation = () => (
    <div className="searching-animation" style={{
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'flex-start',
      padding: '10px 14px',
      backgroundColor: '#ffffff',
      borderRadius: '12px',
      boxShadow: '0 1px 2px rgba(0, 0, 0, 0.1)',
      maxWidth: '95%',
      marginBottom: '16px'
    }}>
      <div style={{ 
        fontSize: '0.85rem',
        marginBottom: '8px',
        color: '#555',
        display: 'flex',
        alignItems: 'center',
        gap: '8px'
      }}>
        <div className="loading-icon" style={{
          width: '16px',
          height: '16px',
          borderRadius: '50%',
          border: '2px solid #f3f3f3',
          borderTop: '2px solid #3498db',
          animation: 'spin 1s linear infinite',
        }}></div>
        <span>정보를 검색 중입니다...</span>
      </div>
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: '6px',
        margin: '4px 0',
        fontSize: '0.75rem',
        color: '#888'
      }}>
        <div className="dot" style={{
          width: '6px',
          height: '6px',
          borderRadius: '50%',
          backgroundColor: '#3498db',
          opacity: 0.5,
          animation: 'pulse 1.5s infinite',
        }}></div>
        <span>종목 정보 확인 중</span>
      </div>
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: '6px',
        margin: '4px 0',
        fontSize: '0.75rem',
        color: '#888'
      }}>
        <div className="dot" style={{
          width: '6px',
          height: '6px',
          borderRadius: '50%',
          backgroundColor: '#3498db',
          opacity: 0.8,
          animation: 'pulse 1.5s infinite',
          animationDelay: '0.5s'
        }}></div>
        <span>투자 분석 보고서 조회 중</span>
      </div>
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: '6px',
        margin: '4px 0',
        fontSize: '0.75rem',
        color: '#888'
      }}>
        <div className="dot" style={{
          width: '6px',
          height: '6px',
          borderRadius: '50%',
          backgroundColor: '#3498db',
          opacity: 0.8,
          animation: 'pulse 1.5s infinite',
          animationDelay: '1s'
        }}></div>
        <span>최신 종목 뉴스 분석 중</span>
      </div>
      <style jsx>{`
        @keyframes spin {
          0% { transform: rotate(0deg); }
          100% { transform: rotate(360deg); }
        }
        @keyframes pulse {
          0%, 100% { opacity: 0.3; }
          50% { opacity: 1; }
        }
      `}</style>
    </div>
  );

  // 스타일 정의
  const aiChatAreaStyle: React.CSSProperties = {
    display: 'flex',
    flexDirection: 'column',
    height: 'auto', // 자동 높이로 변경하여 컨텐츠에 따라 늘어나도록 함
    width: '100%', // 전체 너비를 사용
    position: 'relative',
    backgroundColor: '#f5f5f5',
    overflow: 'visible', // 오버플로우를 visible로 변경하여 브라우저 기본 스크롤 사용
    padding: isMobile ? '0' : '10px', // 모바일에서는 패딩 제거
  };

  const inputAreaStyle: React.CSSProperties = {
    display: 'flex',
    alignItems: 'center', // 중앙 정렬로 변경
    width: isMobile ? '100%' : '96%', // 모바일에서는 전체 너비, 데스크탑에서는 96%로 증가
    margin: '0 auto', // 중앙 정렬
    paddingLeft: '0',
    boxSizing: 'border-box',
    marginTop: isInputCentered ? (isMobile ? '30vh' : '35vh') : '0px', // 중앙 배치 시 상단 여백 추가
    marginBottom: isMobile ? '5px' : '10px', // 여백 증가
    paddingBottom: isMobile ? '5px' : '0',   // 여백 증가
    position: isMobile ? 'unset' : 'relative',  // sticky 대신 relative로 변경
    bottom: isInputCentered ? 'auto' : '20px', // 중앙 배치가 아닐 때 저작권 텍스트 위에 위치하도록 조정
    zIndex: isMobile ? 'unset' : 10,          // 다른 요소보다 위에 표시
    backgroundColor: isMobile ? '#f5f5f5' : 'transparent', // 모바일에서 배경색 추가
    transition: 'all 0.3s ease-in-out' // 부드러운 전환 효과 추가
  };

  const integratedInputStyle: React.CSSProperties = {
    position: 'relative',
    width: isInputCentered ? '56%' : '56%', // 기존 70%에서 20% 줄임
    margin: '0 auto',
    transition: 'all 0.3s ease-in-out',
  };

  const inputStyle: React.CSSProperties = {
    width: '100%',
    minHeight: '2.97rem', // 최소 높이 20% 증가 (2.475rem * 1.2 ≈ 2.97rem)
    height: 'auto', // 높이를 자동으로 조정
    border: '1px solid #ccc',
    borderRadius: '8px', // 모서리를 더 둥글게 수정
    padding: selectedStock ? '0 40px 0 85px' : '0 40px 0 8px', 
    fontSize: '0.81rem',
    outline: 'none',
    boxSizing: 'border-box',
    resize: 'none', // 사용자가 크기 조절 불가능
    overflow: 'hidden' // 오버플로우 숨김
  };

  const stockSuggestionsStyle: React.CSSProperties = {
    position: 'absolute',
    bottom: '100%',
    left: '0',
    width: '100%',
    maxHeight: '200px',
    overflowY: 'visible', // 세로 스크롤 제거
    backgroundColor: 'white',
    border: '1px solid #ccc',
    borderRadius: '8px', // 모서리를 더 둥글게 수정
    boxShadow: '0 -2px 4px rgba(0, 0, 0, 0.1)', // 그림자 방향 변경
    zIndex: 1000,
    marginBottom: '4px', // 하단 마진 추가
    display: showStockSuggestions ? 'block' : 'none',
    padding: '8px' // 좌우 여백 절반으로 감소
  };

  const messagesContainerStyle: React.CSSProperties = {
    overflowY: 'visible', // 스크롤을 브라우저로 위임
    overflowX: 'hidden',
    padding: isMobile ? '5px' : '10px', // 모바일에서는 패딩 축소
    margin: '0 auto', // 중앙 정렬
    border: 'none', 
    borderRadius: '0', 
    backgroundColor: '#f5f5f5', 
    width: isMobile ? '100%' : '80%', // 모바일에서는 전체 너비, 데스크탑에서는 80%
    height: 'auto', // 높이를 자동으로 조정
    minHeight: 'calc(100% - 60px)', // 최소 높이 설정
    boxSizing: 'border-box',
    position: 'relative',
    display: isInputCentered ? 'none' : 'block' // 입력 필드가 중앙에 있을 때는 메시지 영역 숨김
  };

  const aiMessageStyle: React.CSSProperties = {
    backgroundColor: '#ffffff',
    borderRadius: '8px',
    padding: '10px 15px',
    marginBottom: '12px',
    width: isMobile ? '100%' : '100%', // 모바일에서도 전체 너비 사용
    boxShadow: '0 1px 2px rgba(0,0,0,0.05)',
    lineHeight: '1.5',
    fontSize: '0.9rem',
    whiteSpace: 'pre-wrap',
    overflowWrap: 'break-word',
    boxSizing: 'border-box'
  };

  return (
    <div className="ai-chat-area" style={aiChatAreaStyle}>
      {/* 메시지 표시 영역 */}
      <div 
        className="messages-container" 
        ref={messagesContainerRef} 
        style={messagesContainerStyle}
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
                flexDirection: 'row',
                alignItems: 'center',
                justifyContent: message.role === 'user' ? 'flex-end' : 'flex-start',
                width: '100%' // 전체 너비 사용
              }}
            >
              {/* 메시지 내용 */}
              <div style={message.role === 'assistant' ? aiMessageStyle : {
                backgroundColor: '#f5f5f5', // 사용자 메시지 배경색
                padding: '10px 14px',
                borderRadius: '12px',
                maxWidth: isMobile ? '95%' : '85%', // 모바일에서는 더 넓게 사용
                width: 'auto',
                boxShadow: '0 1px 2px rgba(0, 0, 0, 0.1)',
                position: 'relative',
                border: '1px solid #e0e0e0' // 테두리 추가하여 구분
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
                  overflow: message.role === 'user' ? 'hidden' : 'visible',
                  textOverflow: message.role === 'user' ? 'ellipsis' : 'clip',
                  wordBreak: 'break-word',
                  width: '100%',
                  padding: message.role === 'user' ? '0' : '4px 2px'
                }}>
                  {message.role === 'user' ? (
                    // 사용자 메시지는 일반 텍스트로 표시
                    <div style={{
                      whiteSpace: 'nowrap',
                      fontSize: '0.75rem',
                      lineHeight: '1.6',
                      letterSpacing: 'normal'
                    }}>
                      {message.content}
                    </div>
                  ) : (
                    // AI 응답은 마크다운으로 렌더링
                    <div className="markdown-content">
                      <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeRaw, rehypeHighlight]}>
                        {message.content}
                      </ReactMarkdown>
                    </div>
                  )}
                </div>
              </div>
            </div>
          ))
        )}
        
        {/* 메시지 처리 중 로딩 표시 (말풍선 왼쪽에 시간 카운터와 함께) */}
        {isProcessing && (
          <div style={{
            display: 'flex',
            flexDirection: 'row',
            alignItems: 'flex-start',
            gap: '12px',
            marginBottom: '16px'
          }}>
            <SearchTimer />
            <SearchingAnimation />
          </div>
        )}
        
        <div ref={messagesEndRef} />
      </div>
      
      {/* 입력 영역 */}
      <div className="input-area" style={inputAreaStyle}>
        <div className="integrated-input" style={integratedInputStyle}>
          {/* 텍스트 박스 바로 위 안내 문구 */}
          {showTitle && isInputCentered && (
            <div style={{
              textAlign: 'center',
              marginBottom: '20px',
              padding: '0',
              width: '100%',
              position: 'relative',
              marginTop: isMobile ? '-80px' : '-100px',
              left: '0',
              right: '0',
              transition: 'all 0.3s ease-in-out'
            }}>
              <h1 style={{
                fontSize: isMobile ? '1rem' : '1.3rem',
                fontWeight: 'bold',
                color: '#333',
                lineHeight: '1.3',
                wordBreak: 'keep-all',
                letterSpacing: '-0.02em',
                transition: 'all 0.3s ease-in-out'
              }}>
                기업,산업 리포트부터 SNS, 그리고 스탁이지가 보유한 비공개 자료들까지<br />
                한번에 분석해드려요.
              </h1>
            </div>
          )}
          
          <div style={{
            position: 'relative',
            display: 'flex',
            alignItems: 'center',
            width: '100%',
            backgroundColor: 'white',
            borderRadius: '30px',
            border: '1px solid #e0e0e0',
            padding: '0',
            boxShadow: '0 2px 6px rgba(0, 0, 0, 0.05)'
          }}>
            {selectedStock && (
              <div 
                style={{
                  padding: '4px 10px',
                  margin: '0 0 0 8px',
                  height: '28px',
                  borderRadius: '6px',
                  border: '1px solid #ddd',
                  backgroundColor: '#f5f5f5',
                  color: '#333',
                  fontSize: '0.7rem',
                  fontWeight: 'normal',
                  whiteSpace: 'nowrap',
                  display: 'flex',
                  alignItems: 'center',
                  cursor: 'pointer'
                }}
                onClick={() => {
                  setShowStockSuggestions(true); // 종목 선택 팝업 표시
                  if (searchInputRef.current) {
                    setTimeout(() => {
                      if (searchInputRef.current) {
                        searchInputRef.current.focus();
                      }
                    }, 100);
                  }
                }}
                title="클릭하여 종목 변경"
              >
                {selectedStock.stockName}
              </div>
            )}
            <input
              ref={inputRef}
              placeholder={selectedStock ? "종목에 대해 궁굼한걸 물어보세요" : "먼저 종목을 입력하거나 선택하세요"}
              className="integrated-input-field"
              type="text"
              value={inputMessage}
              onChange={handleInputChange}
              onFocus={handleInputFocus}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  if (!selectedStock && filteredStocks.length > 0) {
                    // 종목이 선택되지 않고 검색 결과가 있는 경우, 첫 번째 종목 선택
                    e.preventDefault();
                    e.stopPropagation();
                    handleStockSelect(filteredStocks[0]);
                  } else if (selectedStock && inputMessage.trim()) {
                    // 종목이 선택된 상태에서 메시지가 있으면 전송
                    handleSendMessage();
                  }
                }
              }}
              style={{
                ...inputStyle,
                border: 'none',
                boxShadow: 'none',
                padding: '12px 16px',
                marginLeft: selectedStock ? '8px' : '0',
                flex: 1,
                borderRadius: '30px'
              }}
            />
            
            {/* 전송 아이콘 */}
            <button
              onClick={handleSendMessage}
              disabled={!selectedStock || !inputMessage.trim()}
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                width: '36px',
                height: '36px',
                borderRadius: '50%',
                border: 'none',
                backgroundColor: 'transparent',
                cursor: selectedStock && inputMessage.trim() ? 'pointer' : 'not-allowed',
                opacity: selectedStock && inputMessage.trim() ? 1 : 0.5,
                marginRight: '8px'
              }}
            >
              <svg
                width="20"
                height="20"
                viewBox="0 0 24 24"
                fill="none"
                xmlns="http://www.w3.org/2000/svg"
              >
                <path
                  d="M22 2L11 13"
                  stroke="#333333"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
                <path
                  d="M22 2L15 22L11 13L2 9L22 2Z"
                  stroke="#333333"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
            </button>
          </div>
          
          {/* 종목 추천 목록 */}
          {isMounted && showStockSuggestions && (
            <div ref={stockSuggestionsRef} style={stockSuggestionsStyle}>
              {/* 검색 입력 필드 제거 - 기본 텍스트 입력창만 사용 */}
              
              {isLoading ? (
                <div style={{ padding: '8px', textAlign: 'center' }}>종목 로딩 중...</div>
              ) : error ? (
                <div style={{ padding: '8px', color: 'red' }}>{error}</div>
              ) : filteredStocks.length === 0 ? (
                <div style={{ padding: '8px', textAlign: 'center', color: '#666' }}>
                  검색 결과가 없습니다
                </div>
              ) : (
                <div style={{ padding: '0 5px' }}>
                  <div style={{ 
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    marginBottom: '6px'
                  }}>
                    <div style={{ 
                      fontSize: '0.7rem', 
                      fontWeight: 'normal',
                      color: '#666'
                    }}>
                      최근 유저들이 선택한 종목 TOP10 종목
                    </div>
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
                    {filteredStocks.map((stock) => (
                      <button 
                        key={stock.value} 
                        onClick={(e) => {
                          e.preventDefault();
                          e.stopPropagation();
                          setShowStockSuggestions(false); // 즉시 팝업 닫기
                          handleStockSelect(stock);
                        }}
                        style={{ 
                          padding: '4px 10px', // 기존 6px 12px에서 20% 줄임
                          height: '28px', // 기존 36px에서 20% 줄임
                          cursor: 'pointer',
                          fontSize: '0.7rem', // 글자 크기도 약간 줄임
                          whiteSpace: 'nowrap',
                          borderRadius: '6px',
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
                        <span style={{ color: '#666', marginLeft: '6px', fontSize: '0.7rem' }}>
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
                  paddingTop: '12px',
                  padding: '0 8px'
                }}>
                  <div style={{ 
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    marginBottom: '6px'
                  }}>
                    <div style={{ 
                      fontSize: '0.7rem', 
                      fontWeight: 'normal',
                      color: '#666'
                    }}>
                      최근 조회 종목
                    </div>
                    <button
                      onClick={(e) => {
                        e.preventDefault();
                        e.stopPropagation();
                        setShowStockSuggestions(false); // 팝업 즉시 닫기
                        setRecentStocks([]);
                        localStorage.removeItem('recentStocks');
                      }}
                      style={{
                        background: 'none',
                        border: 'none',
                        fontSize: '0.7rem',
                        color: '#999',
                        cursor: 'pointer',
                        padding: '4px 10px', // 기존 6px 12px에서 20% 줄임
                        height: '28px' // 기존 36px에서 20% 줄임
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
                        onClick={(e) => {
                          e.preventDefault();
                          e.stopPropagation();
                          setShowStockSuggestions(false); // 즉시 팝업 닫기
                          handleStockSelect(stock);
                        }}
                        style={{ 
                          padding: '4px 10px', // 기존 6px 12px에서 20% 줄임
                          height: '28px', // 기존 36px에서 20% 줄임
                          cursor: 'pointer',
                          fontSize: '0.7rem', // 글자 크기도 약간 줄임
                          whiteSpace: 'nowrap',
                          borderRadius: '6px',
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
                        <span style={{ color: '#666', marginLeft: '6px', fontSize: '0.7rem' }}>
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
      
      {/* 추천 질문 버튼 */}
      {isInputCentered && messages.length === 0 && (
        <div style={{
          width: '56%',
          margin: '12px auto 0',
          display: 'flex',
          flexDirection: 'column',
          gap: '8px'
        }}>
          <button
            onClick={() => {
              // 삼성전자 종목 정보
              const samsungStock = { 
                value: '005930', 
                label: '삼성전자', 
                stockName: '삼성전자',
                stockCode: '005930',
                display: '삼성전자 (005930)'
              };
              setSelectedStock(samsungStock);
              setInputMessage('최근 HBM 개발 상황 및 경쟁사와의 비교');
              
              // 최근 조회 종목에 추가
              const updatedRecentStocks = [samsungStock, ...recentStocks.filter(s => s.value !== samsungStock.value)].slice(0, 5);
              setRecentStocks(updatedRecentStocks);
              try {
                localStorage.setItem('recentStocks', JSON.stringify(updatedRecentStocks));
              } catch (error) {
                console.error('Failed to save recent stocks to localStorage:', error);
              }
              
              // 메시지 전송
              setTimeout(() => handleSendMessage(), 100);
            }}
            style={{
              width: '100%',
              padding: '8px 14px',
              borderRadius: '8px',
              border: '1px solid #e0e0e0',
              backgroundColor: '#f9f9f9',
              textAlign: 'left',
              cursor: 'pointer',
              transition: 'background-color 0.2s',
              fontSize: '0.8rem',
              color: '#333',
              display: 'flex',
              alignItems: 'center',
              gap: '8px'
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.backgroundColor = '#f0f0f0';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.backgroundColor = '#f9f9f9';
            }}
          >
            <span style={{
              padding: '4px 10px',
              height: '28px',
              borderRadius: '6px',
              border: '1px solid #ddd',
              backgroundColor: '#f5f5f5',
              color: '#333',
              fontSize: '0.7rem',
              fontWeight: 'normal',
              whiteSpace: 'nowrap'
            }}>
              삼성전자
            </span>
            <span>최근 HBM 개발 상황 및 경쟁사와의 비교</span>
          </button>
          
          <button
            onClick={() => {
              // SK하이닉스 종목 정보
              const skStock = { 
                value: '000660', 
                label: 'SK하이닉스', 
                stockName: 'SK하이닉스',
                stockCode: '000660',
                display: 'SK하이닉스 (000660)'
              };
              setSelectedStock(skStock);
              setInputMessage('AI 반도체 시장 진출 전략과 향후 전망');
              
              // 최근 조회 종목에 추가
              const updatedRecentStocks = [skStock, ...recentStocks.filter(s => s.value !== skStock.value)].slice(0, 5);
              setRecentStocks(updatedRecentStocks);
              try {
                localStorage.setItem('recentStocks', JSON.stringify(updatedRecentStocks));
              } catch (error) {
                console.error('Failed to save recent stocks to localStorage:', error);
              }
              
              // 메시지 전송
              setTimeout(() => handleSendMessage(), 100);
            }}
            style={{
              width: '100%',
              padding: '8px 14px',
              borderRadius: '8px',
              border: '1px solid #e0e0e0',
              backgroundColor: '#f9f9f9',
              textAlign: 'left',
              cursor: 'pointer',
              transition: 'background-color 0.2s',
              fontSize: '0.8rem',
              color: '#333',
              display: 'flex',
              alignItems: 'center',
              gap: '8px'
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.backgroundColor = '#f0f0f0';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.backgroundColor = '#f9f9f9';
            }}
          >
            <span style={{
              padding: '4px 10px',
              height: '28px',
              borderRadius: '6px',
              border: '1px solid #ddd',
              backgroundColor: '#f5f5f5',
              color: '#333',
              fontSize: '0.7rem',
              fontWeight: 'normal',
              whiteSpace: 'nowrap'
            }}>
              SK하이닉스
            </span>
            <span>AI 반도체 시장 진출 전략과 향후 전망</span>
          </button>
          
          <button
            onClick={() => {
              // 현대차 종목 정보
              const hyundaiStock = { 
                value: '005380', 
                label: '현대차', 
                stockName: '현대차',
                stockCode: '005380',
                display: '현대차 (005380)'
              };
              setSelectedStock(hyundaiStock);
              setInputMessage('전기차 시장에서의 경쟁력과 최근 실적 분석');
              
              // 최근 조회 종목에 추가
              const updatedRecentStocks = [hyundaiStock, ...recentStocks.filter(s => s.value !== hyundaiStock.value)].slice(0, 5);
              setRecentStocks(updatedRecentStocks);
              try {
                localStorage.setItem('recentStocks', JSON.stringify(updatedRecentStocks));
              } catch (error) {
                console.error('Failed to save recent stocks to localStorage:', error);
              }
              
              // 메시지 전송
              setTimeout(() => handleSendMessage(), 100);
            }}
            style={{
              width: '100%',
              padding: '8px 14px',
              borderRadius: '8px',
              border: '1px solid #e0e0e0',
              backgroundColor: '#f9f9f9',
              textAlign: 'left',
              cursor: 'pointer',
              transition: 'background-color 0.2s',
              fontSize: '0.8rem',
              color: '#333',
              display: 'flex',
              alignItems: 'center',
              gap: '8px'
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.backgroundColor = '#f0f0f0';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.backgroundColor = '#f9f9f9';
            }}
          >
            <span style={{
              padding: '4px 10px',
              height: '28px',
              borderRadius: '6px',
              border: '1px solid #ddd',
              backgroundColor: '#f5f5f5',
              color: '#333',
              fontSize: '0.7rem',
              fontWeight: 'normal',
              whiteSpace: 'nowrap'
            }}>
              현대차
            </span>
            <span>전기차 시장에서의 경쟁력과 최근 실적 분석</span>
          </button>
          
          <button
            onClick={() => {
              // LG에너지솔루션 종목 정보
              const lgStock = { 
                value: '373220', 
                label: 'LG에너지솔루션', 
                stockName: 'LG에너지솔루션',
                stockCode: '373220',
                display: 'LG에너지솔루션 (373220)'
              };
              setSelectedStock(lgStock);
              setInputMessage('배터리 기술 개발 현황 및 글로벌 시장 점유율');
              
              // 최근 조회 종목에 추가
              const updatedRecentStocks = [lgStock, ...recentStocks.filter(s => s.value !== lgStock.value)].slice(0, 5);
              setRecentStocks(updatedRecentStocks);
              try {
                localStorage.setItem('recentStocks', JSON.stringify(updatedRecentStocks));
              } catch (error) {
                console.error('Failed to save recent stocks to localStorage:', error);
              }
              
              // 메시지 전송
              setTimeout(() => handleSendMessage(), 100);
            }}
            style={{
              width: '100%',
              padding: '8px 14px',
              borderRadius: '8px',
              border: '1px solid #e0e0e0',
              backgroundColor: '#f9f9f9',
              textAlign: 'left',
              cursor: 'pointer',
              transition: 'background-color 0.2s',
              fontSize: '0.8rem',
              color: '#333',
              display: 'flex',
              alignItems: 'center',
              gap: '8px'
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.backgroundColor = '#f0f0f0';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.backgroundColor = '#f9f9f9';
            }}
          >
            <span style={{
              padding: '4px 10px',
              height: '28px',
              borderRadius: '6px',
              border: '1px solid #ddd',
              backgroundColor: '#f5f5f5',
              color: '#333',
              fontSize: '0.7rem',
              fontWeight: 'normal',
              whiteSpace: 'nowrap'
            }}>
              LG에너지솔루션
            </span>
            <span>배터리 기술 개발 현황 및 글로벌 시장 점유율</span>
          </button>
          
          <button
            onClick={() => {
              // NAVER 종목 정보
              const naverStock = { 
                value: '035420', 
                label: 'NAVER', 
                stockName: 'NAVER',
                stockCode: '035420',
                display: 'NAVER (035420)'
              };
              setSelectedStock(naverStock);
              setInputMessage('인공지능 사업 확장과 해외 시장 진출 전략');
              
              // 최근 조회 종목에 추가
              const updatedRecentStocks = [naverStock, ...recentStocks.filter(s => s.value !== naverStock.value)].slice(0, 5);
              setRecentStocks(updatedRecentStocks);
              try {
                localStorage.setItem('recentStocks', JSON.stringify(updatedRecentStocks));
              } catch (error) {
                console.error('Failed to save recent stocks to localStorage:', error);
              }
              
              // 메시지 전송
              setTimeout(() => handleSendMessage(), 100);
            }}
            style={{
              width: '100%',
              padding: '8px 14px',
              borderRadius: '8px',
              border: '1px solid #e0e0e0',
              backgroundColor: '#f9f9f9',
              textAlign: 'left',
              cursor: 'pointer',
              transition: 'background-color 0.2s',
              fontSize: '0.8rem',
              color: '#333',
              display: 'flex',
              alignItems: 'center',
              gap: '8px'
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.backgroundColor = '#f0f0f0';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.backgroundColor = '#f9f9f9';
            }}
          >
            <span style={{
              padding: '4px 10px',
              height: '28px',
              borderRadius: '6px',
              border: '1px solid #ddd',
              backgroundColor: '#f5f5f5',
              color: '#333',
              fontSize: '0.7rem',
              fontWeight: 'normal',
              whiteSpace: 'nowrap'
            }}>
              NAVER
            </span>
            <span>인공지능 사업 확장과 해외 시장 진출 전략</span>
          </button>
        </div>
      )}
      
      {/* 저작권 정보 */}
      {!isMobile && (
        <div style={{
          width: isMobile ? '100%' : '80%', // 모바일에서는 전체 너비, 데스크탑에서는 80%
          textAlign: 'center',
          padding: '10px 0', 
          margin: '0 auto',
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center', 
          height: '20px',
          position: 'fixed', // 고정 위치로 변경
          bottom: '10px', // 하단에서 10px 위에 배치
          left: '0',
          right: '0',
          zIndex: 5, // 다른 요소보다 위에 표시
          backgroundColor: 'rgba(245, 245, 245, 0.8)', // 약간 투명한 배경색
          borderTop: '1px solid #eee', // 상단 경계선 추가
        }}>
          <div style={{
            fontSize: '0.75rem',
            color: '#888',
            fontWeight: '300'
          }}>
            스탁이지 (주)Intellio since 2025
          </div>
        </div>
      )}
    </div>
  );
}

// 메인 컴포넌트
export default function AIChatArea() {
  return (
    <AIChatAreaContent />
  )
}
