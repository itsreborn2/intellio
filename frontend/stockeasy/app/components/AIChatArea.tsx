'use client'

import { Suspense, useState, useEffect, useMemo, useRef } from 'react'
import Select from 'react-select'
import Papa from 'papaparse'
import { MentionsInput, Mention } from 'react-mentions'
import { sendChatMessage, createChatSession, createChatMessage } from '@/services/api/chat'
import { IChatMessageDetail, IChatResponse, IChatSession } from '@/types/api/chat'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import remarkBreaks from 'remark-breaks'
import rehypeRaw from 'rehype-raw'
import rehypeHighlight from 'rehype-highlight'
import { CSSProperties } from 'react'
import 'highlight.js/styles/github.css' // 하이라이트 스타일 추가
import { useChatStore } from '@/stores/chatStore'

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
  responseId?: string; // 분석 결과의 고유 ID
}

// 컨텐츠 컴포넌트
function AIChatAreaContent(): JSX.Element {
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
  const [isMobile, setIsMobile] = useState(false); // 사이드바 열림 상태 감지를 위한 상태 추가
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [isInputCentered, setIsInputCentered] = useState(true); // 입력 필드 중앙 배치 상태 추가
  const [showTitle, setShowTitle] = useState(true); // 제목 표시 여부
  const [transitionInProgress, setTransitionInProgress] = useState(false);
  const [searchMode, setSearchMode] = useState(false); // 종목 검색 모드 상태 추가
  const [popupHovered, setPopupHovered] = useState(false); // 팝업 호버 상태 추가
  const [windowWidth, setWindowWidth] = useState(0);
  const [currentChatSession, setCurrentChatSession] = useState<IChatSession | null>(null);

  const inputRef = useRef<HTMLInputElement>(null); // 입력 필드 참조
  const searchInputRef = useRef<HTMLInputElement>(null); // 검색 입력 필드 참조
  const stockSuggestionsRef = useRef<HTMLDivElement>(null); // 종목 추천 컨테이너 참조
  const messagesEndRef = useRef<HTMLDivElement>(null); // 메시지 영역 끝 참조
  const messagesContainerRef = useRef<HTMLDivElement>(null); // 메시지 컨테이너 참조

  const CACHE_DURATION = 3600000; // 캐시 유효 시간 (1시간 = 3600000ms)
  const MAX_RECENT_STOCKS = 5; // 최근 조회 종목 최대 개수

  // Zustand 스토어 사용
  const { 
    currentSession, 
    messages: storeMessages, 
    isLoading: storeIsLoading 
  } = useChatStore()
  
  // 스토어에서 가져온 메시지를 컴포넌트 메시지 형식으로 변환
  useEffect(() => {
    if (currentSession && storeMessages.length > 0) {
      // 채팅 세션이 있을 경우, 화면 레이아웃을 메시지 모드로 변경
      setIsInputCentered(false)
      setShowTitle(false)
      
      // 현재 세션의 종목 정보 설정 (세션에서 가져오거나 없으면 첫 번째 메시지에서 추출)
      const stockName = currentSession.stock_name || '';
      const stockCode = currentSession.stock_code || '';
      
      console.log('세션 정보:', currentSession)
      console.log('종목 정보:', stockName, stockCode)
      
      // 스토어의 메시지를 컴포넌트 형식으로 변환
      const convertedMessages: ChatMessage[] = storeMessages.map(msg => {
        //console.log('변환 중인 메시지 전체:', msg)
        //console.log('변환 중인 메시지 메타데이터:', msg.metadata)
        
        // 메시지 자체 또는 메타데이터에서 종목 정보 추출
        let msgStockName = '';
        let msgStockCode = '';
        
        // 1. 먼저 메시지 자체에 속성으로 있는지 확인 (로그에서 보이는 구조)
        if (msg.stock_name && msg.stock_code) {
          msgStockName = msg.stock_name;
          msgStockCode = msg.stock_code;
          //console.log('메시지 직접 속성에서 종목 정보 추출:', msgStockName, msgStockCode);
        } 
        // 3. 세션 정보 사용
        else {
          msgStockName = stockName;
          msgStockCode = stockCode;
          console.log('세션에서 종목 정보 사용:', msgStockName, msgStockCode);
        }
        
        const messageWithStock = {
          id: msg.id,
          role: msg.role as 'user' | 'assistant',
          content: msg.content,
          timestamp: msg.created_at ? new Date(msg.created_at).getTime() : Date.now(),
          responseId: msg.metadata?.responseId,
          stockInfo: (msgStockName && msgStockCode) ? {
            stockName: msgStockName,
            stockCode: msgStockCode
          } : undefined
        }
        
        //console.log('변환된 단일 메시지:', messageWithStock)
        //console.log('stockInfo 확인:', messageWithStock.stockInfo)
        return messageWithStock
      })
      
      //console.log('변환된 메시지들:', convertedMessages)
      
      // 현재 세션 정보 설정
      setCurrentChatSession({
        id: currentSession.id,
        user_id: currentSession.user_id || '',
        title: currentSession.title,
        is_active: currentSession.is_active,
        ok: currentSession.ok,
        status_message: currentSession.status_message,
        stock_code: stockCode,
        stock_name: stockName
      })

      // 종목 선택 상태 업데이트
      if (stockName && stockCode) {
        const stockOption: StockOption = {
          value: stockCode,
          label: `${stockName} (${stockCode})`,
          stockName,
          stockCode,
          display: stockName
        };
        setSelectedStock(stockOption);
        console.log('종목 선택 업데이트:', stockOption)
      }
      
      // 메시지 설정
      setMessages(convertedMessages)
    }
  }, [currentSession, storeMessages])

  // 히스토리 분석 결과 로드 이벤트 리스너
  useEffect(() => {
    const handleLoadHistoryAnalysis = (e: CustomEvent) => {
      const { stockName, stockCode, prompt, result, responseId } = e.detail;
      
      // 선택된 종목 설정
      if (stockName && stockCode) {
        const stockOption: StockOption = {
          value: stockCode,
          label: `${stockName} (${stockCode})`,
          stockName,
          stockCode,
          display: `${stockName} (${stockCode})`
        };
        setSelectedStock(stockOption);
        
        // 최근 조회 종목에 추가
        const updatedRecentStocks = [stockOption, ...recentStocks.filter(s => s.value !== stockCode)].slice(0, MAX_RECENT_STOCKS);
        setRecentStocks(updatedRecentStocks);
        try {
          localStorage.setItem('recentStocks', JSON.stringify(updatedRecentStocks));
        } catch (error) {
          console.error('최근 조회 종목 저장 실패:', error);
        }
      }
      
      // 메시지 설정
      const userMessage: ChatMessage = {
        id: Date.now().toString(),
        role: 'user',
        content: prompt,
        timestamp: Date.now(),
        stockInfo: {
          stockName,
          stockCode
        },
        responseId
      };
      
      const assistantMessage: ChatMessage = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: result,
        timestamp: Date.now() + 1,
        stockInfo: {
          stockName,
          stockCode
        },
        responseId
      };
      
      // 메시지 설정 및 입력 필드 중앙 배치 해제
      setMessages([userMessage, assistantMessage]);
      setIsInputCentered(false);
      setShowTitle(false);
      
      // 입력 필드 초기화
      setInputMessage('');
    };
    
    // 이벤트 리스너 등록
    window.addEventListener('loadHistoryAnalysis', handleLoadHistoryAnalysis as EventListener);
    
    return () => {
      window.removeEventListener('loadHistoryAnalysis', handleLoadHistoryAnalysis as EventListener);
    };
  }, [recentStocks]);

  // 클라이언트 사이드 렌더링 확인
  useEffect(() => {
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

    // 홈 버튼 클릭 이벤트 리스너 추가 (페이지 초기화용)
    const handleHomeButtonClick = () => {
      resetChatArea();
    };
    
    // 컴포넌트가 마운트되었음을 설정
    setIsMounted(true);
    
    // 현재 창 너비 설정
    setWindowWidth(window.innerWidth);
    
    // 초기화
    setCurrentChatSession(null);
    
    // 클릭 이벤트 리스너 설정
    document.addEventListener('mousedown', handleClickOutside);
    
    // 홈 버튼 클릭 이벤트 설정
    window.addEventListener('homeButtonClick' as any, handleHomeButtonClick);
    
    // 최근 조회 종목 로드
    try {
      const savedRecentStocks = localStorage.getItem('recentStocks');
      if (savedRecentStocks) {
        setRecentStocks(JSON.parse(savedRecentStocks));
      }
    } catch (error) {
      console.error('Failed to load recent stocks from localStorage:', error);
    }

    // 컴포넌트 언마운트 시 이벤트 리스너 제거
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
      window.removeEventListener('homeButtonClick' as any, handleHomeButtonClick);

      // 타이머 정리
      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
    };
  }, []);

  // 채팅 영역 초기화 함수
  const resetChatArea = () => {
    
    // 상태 초기화
    setSelectedStock(null);
    setInputMessage('');
    setMessages([]);
    setIsProcessing(false);
    setElapsedTime(0);
    setIsInputCentered(true);
    setShowTitle(true);
    setSearchMode(false);
    setShowStockSuggestions(false);
    setTransitionInProgress(false);
    setSearchTerm('');
    setFilteredStocks([]);
    setCurrentChatSession(null);

    
    console.log('채팅 영역이 초기화되었습니다.');
  };

  // 모바일 환경 감지
  useEffect(() => {
    const checkIfMobile = () => {
      const isMobileView = windowWidth <= 640;
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
  }, [windowWidth]);

  // 사이드바 상태 감지
  useEffect(() => {
    // 사이드바 열림/닫힘 이벤트 리스너
    const handleSidebarToggle = (e: MessageEvent) => {
      if (e.data && typeof e.data === 'object' && 'type' in e.data) {
        if (e.data.type === 'SIDEBAR_TOGGLE') {
          setIsSidebarOpen(e.data.isOpen);
        }
      }
    };

    // 화면 크기 변경 감지
    const handleResize = () => {
      setWindowWidth(window.innerWidth);
    };

    window.addEventListener('message', handleSidebarToggle);
    window.addEventListener('resize', handleResize);
    
    return () => {
      window.removeEventListener('message', handleSidebarToggle);
      window.removeEventListener('resize', handleResize);
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
      setTransitionInProgress(true);
    }
    console.log('selectedStock : ', selectedStock);
    console.log('inputMessage : ', inputMessage);
    console.log('currentChatSession : ', currentChatSession);
    // 메시지 ID 생성
    const messageId = `msg_${Date.now()}`;
    // 응답 ID 생성 (실제로는 서버에서 생성해야 함)
    const responseId = `response_${Date.now()}`;

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
      } : undefined,
      responseId // 응답 ID 추가
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
      // 채팅 세션 ID가 없으면 새로 생성
      let sessionId = currentChatSession?.id;
      if (!sessionId) {
        try {
          // 새 채팅 세션 생성
          const sessionTitle = selectedStock?.stockName 
            ? `${selectedStock.stockName}(${selectedStock.stockCode}) : ${userMessageContent}` 
            : userMessageContent;
          const newSession = await createChatSession(sessionTitle);
          setCurrentChatSession(newSession);
          sessionId = newSession.id;
          
          console.log('새 채팅 세션 생성됨:', sessionId);
        } catch (sessionError) {
          console.error('채팅 세션 생성 오류:', sessionError);
          return;
        }
      }

      // 사용자 메시지 저장 (백엔드에 직접 저장)
      
      const response:IChatMessageDetail = await createChatMessage(
        sessionId,  
        userMessageContent,
        selectedStock?.stockCode || '',
        selectedStock?.stockName || ''
      );
      if (!response.ok) {
        throw new Error(`API 응답 오류: ${response.status_message}`);
      }


      // 백엔드 API 호출

      const responseData = response.content;
      console.log('answer : ', responseData);

      // 응답 메시지 생성
      const assistantMessage: ChatMessage = {
        id: `assistant-${Date.now()}`,
        role: 'assistant', 
        content: responseData || '죄송합니다. 응답을 생성하는 중 오류가 발생했습니다.',
        timestamp: Date.now(),
        stockInfo: selectedStock ? {
          stockName: selectedStock.stockName,
          stockCode: selectedStock.stockCode
        } : undefined,
        responseId // 응답 ID 추가
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
    // 입력 위치가 중앙에서 하단으로 변경될 때는 스크롤 동작을 지연시켜 레이아웃 변화가 완료된 후 작동하도록 함
    if (messagesEndRef.current && messages.length > 0) {
      // 최초 메시지 추가 또는 isInputCentered가 false인 상태에서 메시지 추가 시 스크롤 동작
      if (messages.length === 1 || !transitionInProgress) {
        setTimeout(() => {
          if (messagesEndRef.current) {
            messagesEndRef.current.scrollIntoView({ behavior: 'auto' });
          }
        }, 300); // 레이아웃 전환 애니메이션(0.3s)보다 약간 더 길게 설정
      }
    }
  }, [messages, transitionInProgress]);

  // 입력 필드 위치 전환 상태 관리
  useEffect(() => {
    if (!isInputCentered) {
      setTransitionInProgress(true);
      // transition 시간(0.3s) 이후에 전환 완료 상태로 변경
      setTimeout(() => {
        setTransitionInProgress(false);
      }, 400); // transition duration + 약간의 여유
    }
  }, [isInputCentered]);

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

    // currentChatSession 초기화
    setCurrentChatSession(null);

    // 초기 메시지 설정 로직은 위의 fetchMessages 함수에서 처리
  }, [isMounted, messages.length]);

  // URL에서 initialStockCode 가져오기
  useEffect(() => {
    const urlParams = new URLSearchParams(window.location.search);
    const initialStockCode = urlParams.get('initialStockCode');
    if (initialStockCode) {
      const stock = stockOptions.find(stock => stock.value === initialStockCode);
      if (stock) {
        setSelectedStock(stock);
      }
    }
  }, [isMounted, stockOptions]);

  // 입력 필드 포커스 시 종목 추천 목록 표시
  const handleInputFocus = () => {
    // 종목 선택 팝업이 열려 있으면 검색 모드 활성화
    if (showStockSuggestions) {
      setSearchMode(true);
      
      // 최근 종목이 있으면 표시
      if (recentStocks.length > 0) {
        setFilteredStocks(recentStocks);
      } else {
        // 최근 조회 종목이 없으면 기본 종목 추천 표시 (상위 5개)
        setFilteredStocks(stockOptions.slice(0, 5));
      }
      return;
    }
    
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
  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    const value = e.target.value;
    setInputMessage(value);
    
    // 종목 선택 팝업이 열려 있으면 항상 종목 검색 모드로 동작
    if (showStockSuggestions) {
      setSearchMode(true);
      // 종목 검색 로직
      const searchValue = value.trim();
      if (searchValue.length > 0) {
        // 종목 검색 로직
        const filtered = stockOptions.filter(stock => {
          const stockName = stock.stockName || stock.display || stock.label || '';
          const stockCode = stock.value || '';
          return stockName.toLowerCase().includes(searchValue.toLowerCase()) || 
                 stockCode.includes(searchValue);
        }).slice(0, 10);
        
        setFilteredStocks(filtered);
      } else {
        // 입력값이 없으면 최근 조회 종목 표시
        if (recentStocks.length > 0) {
          setFilteredStocks(recentStocks);
        } else {
          setFilteredStocks(stockOptions.slice(0, 5));
        }
      }
      return; // 종목 검색 모드일 때는 여기서 함수 종료
    }
    
    // searchMode가 활성화되어 있으면 종목 검색 수행
    if (searchMode) {
      // 종목 검색 로직
      const searchValue = value.trim();
      if (searchValue.length > 0) {
        // 종목 검색 로직
        const filtered = stockOptions.filter(stock => {
          const stockName = stock.stockName || stock.display || stock.label || '';
          const stockCode = stock.value || '';
          return stockName.toLowerCase().includes(searchValue.toLowerCase()) || 
                 stockCode.includes(searchValue);
        }).slice(0, 10);
        
        setFilteredStocks(filtered);
        
        // 검색 결과가 있으면 종목 추천 목록 표시
        setShowStockSuggestions(true);
      } else {
        // 입력값이 없으면 최근 조회 종목 표시
        setShowStockSuggestions(recentStocks.length > 0);
        setFilteredStocks([]);
      }
      return; // 종목 검색 모드일 때는 여기서 함수 종료
    }
    
    // 일반 채팅 모드 - 기존 로직 유지
    if (!selectedStock) {
      // 종목이 선택되지 않은 경우, 입력된 텍스트로 종목 검색
      const searchValue = value.trim();
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
    
    // 기존 높이 조정 로직 유지 (TextArea일 경우에만 적용)
    if (e.target instanceof HTMLTextAreaElement) {
      const target = e.target;
      target.style.height = 'auto'; // 높이를 auto로 초기화하여 정확한 scrollHeight 계산
      const newHeight = Math.min(150, Math.max(target.scrollHeight, 40)); // 최소 40px, 최대 150px
      target.style.height = `${newHeight}px`;
    }
  };

  // 종목 선택 처리
  const handleStockSelect = (stock: StockOption) => {
    console.log('종목 선택: ', stock.label); // 디버깅용 로그
    
    // 즉시 팝업 닫기 (최우선 처리)
    setShowStockSuggestions(false);
    
    // 종목 검색 모드 종료
    setSearchMode(false);
    
    // 선택된 종목 설정
    setSelectedStock(stock);
    setInputMessage(''); // 입력 필드 초기화
    
    // 중앙 배치 해제 - 종목 선택 시에도 화면을 아래로 내림
    if (isInputCentered) {
      setIsInputCentered(false);
      setTransitionInProgress(true);
    }
    
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
        borderTop: '3px solid #10A37F', // #3498db에서 #10A37F로 변경
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
      gap: isMobile ? '6px' : '8px',
      backgroundColor: '#D8EFE9', // #f5f9ff에서 #D8EFE9로 변경
      padding: isMobile ? '6px 10px' : (windowWidth < 768 ? '7px 11px' : '8px 12px'),
      borderRadius: isMobile ? '6px' : '8px',
      boxShadow: '0 2px 5px rgba(0, 0, 0, 0.05)',
      marginBottom: isMobile ? '10px' : '12px',
      maxWidth: '100%',
      wordBreak: 'break-word'
    }}>
      <div style={{
        position: 'relative',
        width: isMobile ? '24px' : '28px',
        height: isMobile ? '24px' : '28px',
        borderRadius: '50%',
        border: isMobile ? '1.5px solid #e1e1e1' : '2px solid #e1e1e1',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        flexShrink: 0
      }}>
        <div style={{
          position: 'absolute',
          top: '50%',
          left: '50%',
          width: isMobile ? '12px' : '14px',
          height: isMobile ? '1.5px' : '2px',
          background: 'transparent',
          transform: 'rotate(0deg) translateX(0)',
          transformOrigin: '0 0',
          zIndex: 2
        }}>
          <div style={{
            position: 'absolute',
            width: isMobile ? '6px' : '8px',
            height: isMobile ? '1.5px' : '2px',
            backgroundColor: '#10A37F', // #3498db에서 #10A37F로 변경
            animation: 'stopwatch-sec 60s steps(60, end) infinite',
            transformOrigin: 'left center'
          }}></div>
        </div>
        <div style={{
          width: isMobile ? '5px' : '6px',
          height: isMobile ? '5px' : '6px',
          backgroundColor: '#10A37F', // #3498db에서 #10A37F로 변경
          borderRadius: '50%',
          zIndex: 3
        }}></div>
      </div>
      <div style={{
        fontFamily: 'monospace',
        fontSize: isMobile ? '14px' : (windowWidth < 768 ? '15px' : '16px'),
        fontWeight: 'bold',
        color: '#555',
        flexShrink: 0
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
      padding: isMobile ? '8px 12px' : (windowWidth < 768 ? '9px 13px' : '10px 14px'),
      backgroundColor: '#D8EFE9', // #ffffff에서 #D8EFE9로 변경
      borderRadius: isMobile ? '10px' : '12px',
      boxShadow: '0 1px 2px rgba(0, 0, 0, 0.1)',
      maxWidth: isMobile ? '95%' : (windowWidth < 768 ? '90%' : '85%'),
      marginBottom: isMobile ? '12px' : '16px',
      width: 'auto',
      wordBreak: 'break-word'
    }}>
      <div style={{ 
        fontSize: isMobile ? '14px' : (windowWidth < 768 ? '15px' : '16px'),
        marginBottom: isMobile ? '6px' : '8px',
        color: '#555',
        display: 'flex',
        alignItems: 'center',
        gap: isMobile ? '6px' : '8px',
        maxWidth: '100%',
        flexWrap: 'wrap'
      }}>
        <div className="loading-icon" style={{
          width: isMobile ? '14px' : '16px',
          height: isMobile ? '14px' : '16px',
          borderRadius: '50%',
          border: isMobile ? '1.5px solid #f3f3f3' : '2px solid #f3f3f3',
          borderTop: isMobile ? '1.5px solid #10A37F' : '2px solid #10A37F', // #3498db에서 #10A37F로 변경
          animation: 'spin 1s linear infinite',
          flexShrink: 0
        }}></div>
        <span>정보를 검색 중입니다...</span>
      </div>
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: isMobile ? '5px' : '6px',
        margin: isMobile ? '3px 0' : '4px 0',
        fontSize: isMobile ? '13px' : (windowWidth < 768 ? '14px' : '16px'),
        color: '#888',
        maxWidth: '100%',
        flexWrap: 'wrap'
      }}>
        <div className="dot" style={{
          width: isMobile ? '5px' : '6px',
          height: isMobile ? '5px' : '6px',
          borderRadius: '50%',
          backgroundColor: '#3498db',
          flexShrink: 0,
          opacity: 0.5,
          animation: 'pulse 1.5s infinite',
        }}></div>
        <span>종목 정보 확인 중</span>
      </div>
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: isMobile ? '5px' : '6px',
        margin: isMobile ? '3px 0' : '4px 0',
        fontSize: isMobile ? '13px' : (windowWidth < 768 ? '14px' : '16px'),
        color: '#888',
        maxWidth: '100%',
        flexWrap: 'wrap'
      }}>
        <div className="dot" style={{
          width: isMobile ? '5px' : '6px',
          height: isMobile ? '5px' : '6px',
          borderRadius: '50%',
          backgroundColor: '#3498db',
          flexShrink: 0,
          opacity: 0.8,
          animation: 'pulse 1.5s infinite',
          animationDelay: '0.5s'
        }}></div>
        <span>투자 분석 보고서 조회 중</span>
      </div>
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: isMobile ? '5px' : '6px',
        margin: isMobile ? '3px 0' : '4px 0',
        fontSize: isMobile ? '13px' : (windowWidth < 768 ? '14px' : '16px'),
        color: '#888',
        maxWidth: '100%',
        flexWrap: 'wrap'
      }}>
        <div className="dot" style={{
          width: isMobile ? '5px' : '6px',
          height: isMobile ? '5px' : '6px',
          borderRadius: '50%',
          backgroundColor: '#3498db',
          flexShrink: 0,
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
    height: '100%', // 전체 높이로 변경
    width: '100%', // 전체 너비를 사용
    position: 'relative',
    backgroundColor: '#F4F4F4', // Figma 디자인에 맞게 배경색 변경
    overflow: 'hidden', // 오버플로우를 hidden으로 변경하여 브라우저 기본 스크롤 사용 안함
    paddingTop: isMobile ? '0' : '10px',
    paddingRight: isMobile ? '0' : '10px',
    paddingBottom: isMobile ? '0' : '10px',
    paddingLeft: isMobile ? '0' : '10px',
    opacity: 1,
    fontSize: isMobile ? '14px' : undefined, // 모바일 기본 폰트 크기 14px
  };

  // 컨테이너 너비를 위한 변수 (일관성 유지를 위해)
  const contentWidth = isMobile ? '100%' : (windowWidth < 768 ? '90%' : (windowWidth < 1024 ? '80%' : '65%'));
  
  const inputAreaStyle: React.CSSProperties = {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center', // 중앙 정렬 강화
    width: '100%', // 전체 너비로 변경
    margin: '0 auto', // 중앙 정렬
    paddingTop: '0',
    paddingRight: '0',
    paddingBottom: '0',
    paddingLeft: '0',
    boxSizing: 'border-box',
    marginTop: isInputCentered ? (isMobile ? '25vh' : (windowWidth < 768 ? '30vh' : '35vh')) : '0px',
    marginBottom: isMobile ? '5px' : (windowWidth < 768 ? '8px' : '10px'),
    position: isMobile ? 'unset' : 'relative',
    bottom: isInputCentered ? 'auto' : (isMobile ? '15px' : '20px'),
    zIndex: isMobile ? 'unset' : 10,
    backgroundColor: 'transparent',
    transition: 'all 0.3s ease-in-out',
    maxWidth: '100%' // 최대 너비 제한
  };

  const integratedInputStyle: React.CSSProperties = {
    position: 'relative',
    width: contentWidth, // 메시지 컨테이너와 동일한 너비 사용
    maxWidth: isMobile ? '100%' : (windowWidth < 768 ? '90%' : (windowWidth < 1024 ? '80%' : '65%')), // 최대 너비 제한
    margin: '0 auto',
    transition: 'width 0.3s ease-in-out', // 전체가 아닌 width만 transition
    boxSizing: 'border-box',
    padding: isMobile ? '0 5px' : '0' // 모바일에서 양쪽 여백 추가
  };

  const inputStyle: React.CSSProperties = {
    width: '100%',
    minHeight: isMobile ? '2.2rem' : (windowWidth < 768 ? '2.3rem' : '2.5rem'), // 화면 크기에 따라 적응
    height: 'auto',
    border: '1px solid #ccc',
    borderRadius: isMobile ? '6px' : '8px',
    paddingTop: '0',
    paddingRight: isMobile ? '35px' : '40px',
    paddingBottom: '0',
    paddingLeft: selectedStock ? (isMobile ? '75px' : '85px') : (isMobile ? '6px' : '8px'), 
    fontSize: isMobile ? '14px' : (windowWidth < 768 ? '15px' : '16px'), // 화면 크기에 따라 적응
    outline: 'none',
    boxSizing: 'border-box',
    resize: 'none',
    overflow: 'hidden',
    maxWidth: '100%' // 최대 너비 제한
  };

  const messagesContainerStyle: React.CSSProperties = {
    overflowY: 'auto',
    overflowX: 'hidden',
    paddingTop: isMobile ? '5px' : (windowWidth < 768 ? '8px' : '10px'),
    paddingRight: isMobile ? '5px' : (windowWidth < 768 ? '8px' : '10px'),
    paddingBottom: isMobile ? '5px' : (windowWidth < 768 ? '8px' : '10px'),
    paddingLeft: isMobile ? '5px' : (windowWidth < 768 ? '8px' : '10px'),
    margin: '0 auto', // 중앙 정렬
    border: 'none', 
    borderRadius: '0', 
    backgroundColor: '#F4F4F4',
    width: contentWidth, // 일관된 너비 사용
    height: '100%', // 전체 높이로 변경
    minHeight: 'calc(100% - 60px)',
    boxSizing: 'border-box',
    position: 'relative',
    display: isInputCentered ? 'none' : 'block',
    opacity: transitionInProgress ? 0 : 1, // 트랜지션 중에는 투명하게 처리
    transition: 'opacity 0.3s ease-in-out', // 오직 opacity만 transition
    maxWidth: '100%' // 최대 너비 제한
  };

  const aiMessageStyle: React.CSSProperties = {
    backgroundColor: 'transparent', // 박스 배경 제거
    borderRadius: '0', // 테두리 둥글기 제거
    padding: isMobile ? '8px 12px' : (windowWidth < 768 ? '9px 14px' : '10px 15px'),
    marginBottom: isMobile ? '10px' : '12px',
    width: '100%', // 전체 너비 사용
    boxShadow: 'none', // 그림자 제거
    lineHeight: '1.5',
    fontSize: isMobile ? '0.85rem' : (windowWidth < 768 ? '0.87rem' : '0.9rem'),
    wordBreak: 'break-word',
    boxSizing: 'border-box',
    maxWidth: '100%' // 최대 너비 제한
  };

  // 마크다운 글로벌 스타일 추가
  const markdownStyles = `
    .markdown-content {
      font-size: ${isMobile ? '0.9rem' : (windowWidth < 768 ? '0.95rem' : '1rem')};
      line-height: 1.6;
      max-width: 100%;
      overflow-wrap: break-word;
      word-wrap: break-word;
    }
    .markdown-content p {
      margin-top: 0.5em;
      margin-bottom: 1em;
      white-space: pre-line;
      max-width: 100%;
    }
    .markdown-content ul, .markdown-content ol {
      margin-top: 0.5em;
      margin-bottom: 1em;
      padding-left: 1.5em;
    }
    .markdown-content li {
      margin-top: 0;
      margin-bottom: 0;
      line-height: 1.3;
      padding-bottom: 0;
      white-space: normal;
    }
    .markdown-content li p {
      margin-top: 0;
      margin-bottom: 0;
      white-space: pre-line;
    }
    .markdown-content li + li {
      margin-top: 0;
    }
    .markdown-content h1, .markdown-content h2, .markdown-content h3, .markdown-content h4 {
      margin-top: 1.5em;
      margin-bottom: 1em;
      line-height: 1.3;
    }
    .markdown-content blockquote {
      margin-left: 0;
      padding-left: 1em;
      border-left: 3px solid #ddd;
      color: #555;
      margin-top: 1em;
      margin-bottom: 1em;
      white-space: pre-line;
    }
  `;

  const stockSuggestionsStyle: React.CSSProperties = {
    position: 'absolute',
    bottom: `calc(100% + ${isMobile ? 5 : 30}px)`, // 모바일 5px, 데스크톱 30px로 간격 확대
    left: 0,
    right: 0,
    width: isMobile ? '90%' : '100%', // 모바일 환경에서 너비 조정
    margin: isMobile ? '0 auto' : '0', // 모바일 환경에서 중앙 정렬
    maxHeight: isMobile ? '180px' : '200px', // 모바일 환경에서 최대 높이 조정
    overflowY: 'auto',
    backgroundColor: 'white',
    border: '1px solid #ccc',
    borderRadius: '8px',
    boxShadow: '0 2px 10px rgba(0, 0, 0, 0.1)',
    zIndex: 100,
    paddingTop: isMobile ? '5px' : '6px', // 모바일 5px, 데스크톱 6px 패딩 (일관성을 위해 조정)
    paddingRight: isMobile ? '5px' : '6px', // 모바일 5px, 데스크톱 6px 패딩 (일관성을 위해 조정)
    paddingBottom: isMobile ? '5px' : '6px', // 모바일 5px, 데스크톱 6px 패딩 (일관성을 위해 조정)
    paddingLeft: isMobile ? '5px' : '6px', // 모바일 5px, 데스크톱 6px 패딩 (일관성을 위해 조정)
    transform: isMobile ? 'none' : (isInputCentered ? 'translateY(-30px)' : 'none'), // 데스크톱 + 중앙 정렬 시에만 적용
  };

  return (
    <div className="ai-chat-area" style={aiChatAreaStyle}>
      {/* 마크다운 스타일 태그 추가 */}
      <style jsx>{markdownStyles}</style>
      
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
            paddingTop: '20px',
            paddingBottom: '20px',
            fontSize: '16px', // 0.9rem에서 16px로 변경
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
                padding: isMobile ? '8px 12px' : (windowWidth < 768 ? '9px 13px' : '10px 14px'),
                borderRadius: isMobile ? '10px' : '12px',
                maxWidth: isMobile ? '95%' : (windowWidth < 768 ? '90%' : '85%'), // 화면 크기에 따라 적응
                width: 'auto',
                boxShadow: '0 1px 2px rgba(0, 0, 0, 0.1)',
                position: 'relative',
                border: '1px solid #e0e0e0', // 테두리 추가하여 구분
                wordBreak: 'break-word'
              }}>
                {message.stockInfo && (
                  <div style={{
                    fontSize: isMobile ? '14px' : (windowWidth < 768 ? '15px' : '16px'), // 화면 크기에 따라 적응
                    fontWeight: 'bold',
                    color: '#10A37F', // 초록색 색상 유지
                    marginBottom: isMobile ? '3px' : '4px',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '4px'
                  }}>
                    <span>{message.stockInfo.stockName}</span>
                    <span style={{ 
                      fontSize: 'smaller', 
                      color: '#555', 
                      fontWeight: 'normal' 
                    }}>
                      ({message.stockInfo.stockCode})
                    </span>
                  </div>
                )}
                <div style={{
                  overflow: message.role === 'user' ? 'hidden' : 'visible',
                  textOverflow: message.role === 'user' ? 'ellipsis' : 'clip',
                  wordBreak: 'break-word',
                  width: '100%',
                  padding: message.role === 'user' ? '0' : (isMobile ? '3px 1px' : '4px 2px'),
                  maxWidth: '100%' // 최대 너비 제한
                }}>
                  {message.role === 'user' ? (
                    // 사용자 메시지는 일반 텍스트로 표시
                    <div style={{
                      whiteSpace: 'pre-wrap', // nowrap에서 pre-wrap으로 변경하여 긴 텍스트가 줄바꿈 되도록 설정
                      fontSize: isMobile ? '14px' : (windowWidth < 768 ? '15px' : '16px'), // 화면 크기에 따라 적응
                      lineHeight: '1.6',
                      letterSpacing: 'normal',
                      wordBreak: 'break-word' // 단어 단위로 줄바꿈 가능하도록 설정
                    }}>
                      {message.content}
                    </div>
                  ) : (
                    // AI 응답은 마크다운으로 렌더링
                    <div className="markdown-content">
                      <ReactMarkdown 
                        remarkPlugins={[
                          remarkGfm,
                          [remarkBreaks, { breaks: false }]
                        ]}
                        components={{
                          text: ({node, ...props}) => <>{props.children}</>,
                          h1: ({node, ...props}) => <h1 style={{marginTop: '1.5em', marginBottom: '1em'}} {...props} />,
                          h2: ({node, ...props}) => <h2 style={{marginTop: '1.5em', marginBottom: '1em'}} {...props} />,
                          h3: ({node, ...props}) => <h3 style={{marginTop: '1.2em', marginBottom: '0.8em'}} {...props} />,
                          ul: ({node, ...props}) => <ul style={{marginTop: '0.5em', marginBottom: '1em', paddingLeft: '1.5em'}} {...props} />,
                          ol: ({node, ...props}) => <ol style={{marginTop: '0.5em', marginBottom: '1em', paddingLeft: '1.5em'}} {...props} />,
                          li: ({node, ...props}) => <li style={{marginBottom: '0'}} {...props} />,
                          p: ({node, ...props}) => <p style={{marginTop: '0.5em', marginBottom: '1em'}} {...props} />
                        }}
                      >
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
            gap: isMobile ? '8px' : (windowWidth < 768 ? '10px' : '12px'),
            marginBottom: isMobile ? '12px' : '16px',
            flexWrap: 'wrap',
            width: '100%'
          }}>
            <SearchTimer />
            <SearchingAnimation />
          </div>
        )}
        
        <div ref={messagesEndRef} />
      </div>
      
      {/* 입력 영역 */}
      {!(isMobile && isSidebarOpen) && (
        <div className="input-area" style={{ 
          ...inputAreaStyle
        }}>
          <div className="integrated-input" style={integratedInputStyle}>
            {/* 텍스트 박스 바로 위 안내 문구 */}
            {showTitle && isInputCentered && !isMobile && (
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
                  transition: 'all 0.3s ease-in-out',
                  display: isMobile ? 'none' : 'block' // 모바일에서는 숨김 처리
                }}>
                  종목을 선택 후 분석을 요청하세요.
                </h1>
              </div>
            )}
            
            <div style={{
              position: 'relative',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center', // 가운데 정렬 추가
              width: '100%',
              backgroundColor: 'white',
              borderRadius: '6px',
              paddingTop: '0',
              paddingRight: '0',
              paddingBottom: '0',
              paddingLeft: '0',
              boxShadow: '0 2px 6px rgba(0, 0, 0, 0.05)',
              border: '2px solid #282A2E', // 테두리선 추가
              transition: 'border-color 0.3s ease' // 부드러운 색상 전환 효과
            }}
              onMouseEnter={(e) => {
                // 마우스 오버 시 테두리 색상 변경
                e.currentTarget.style.borderColor = '#10A37F';
              }}
              onMouseLeave={(e) => {
                // 마우스가 벗어날 때 테두리 색상 복원
                e.currentTarget.style.borderColor = '#282A2E';
              }}
            >
              {selectedStock && (
                <div 
                  style={{
                    display: 'flex', // Flexbox 활성화
                    alignItems: 'center', // 수직 가운데 정렬
                    padding: '4px 10px', // 패딩 유지
                    margin: '0 0 0 8px',
                    height: '26px', // 높이 28px -> 26px로 줄임
                    borderRadius: '6px',
                    border: '1px solid #ddd',
                    backgroundColor: '#D8EFE9', // 연한 민트색으로 변경
                    color: '#333',
                     fontSize: '0.7rem',
                    fontWeight: 'normal',
                    whiteSpace: 'nowrap',
                    cursor: 'pointer'
                  }}
                  onClick={() => {
                    setShowStockSuggestions(true); // 종목 선택 팝업 표시
                    setSearchMode(true); // 종목 검색 모드로 변경
                    setInputMessage(''); // 입력 필드를 비워서 종목 검색을 할 수 있도록 함
                    
                    // 최근 종목이 있으면 표시, 없으면 기본 종목 추천 표시
                    if (recentStocks.length > 0) {
                      setFilteredStocks(recentStocks);
                    } else {
                      setFilteredStocks(stockOptions.slice(0, 5));
                    }
                    
                    setTimeout(() => {
                      if (inputRef.current) {
                        inputRef.current.focus();
                      }
                    }, 100);
                  }}
                  title="클릭하여 종목 변경"
                >
                  {selectedStock.stockName}
                </div>
              )}
              <input
                ref={inputRef}
                placeholder={showStockSuggestions || searchMode ? "종목명 또는 종목코드 검색" : (selectedStock ? "이 종목, 뭔가 궁금하다면 지금 바로 질문해 보세요" : "어떤 종목이든 좋아요! 먼저 입력하거나 골라주세요.")}
                className="integrated-input-field"
                type="text"
                value={inputMessage}
                onChange={handleInputChange}
                onFocus={handleInputFocus}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    if (showStockSuggestions && filteredStocks.length > 0) {
                      // 종목 선택 팝업이 열려 있고 검색 결과가 있는 경우, 첫 번째 종목 선택
                      e.preventDefault();
                      e.stopPropagation();
                      handleStockSelect(filteredStocks[0]);
                    } else if (selectedStock && inputMessage.trim() && !searchMode) {
                      // 종목이 선택된 상태에서 메시지가 있고 검색 모드가 아니면 전송
                      handleSendMessage();
                    }
                  }
                }}
                style={{
                  ...inputStyle,
                  border: 'none',
                  boxShadow: 'none',
                  paddingTop: '8px', // 패딩 감소 (12px -> 8px)
                  paddingRight: '16px',
                  paddingBottom: '8px', // 패딩 감소 (12px -> 8px)
                  paddingLeft: '16px',
                  flex: 1,
                  borderRadius: '6px'
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
              <div
                style={stockSuggestionsStyle}
                ref={stockSuggestionsRef}
              >
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
                  <div style={{ 
                    paddingLeft: '5px', 
                    paddingRight: '5px', 
                    paddingTop: '0', 
                    paddingBottom: '4px' 
                  }}>
                    <div style={{ 
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      marginBottom: '0' // 여백 완전 제거
                    }}>
                      <div style={{ 
                       fontSize: '0.7rem', 
                        fontWeight: 'normal',
                        color: '#666'
                      }}>
                        유저들의 TOP10
                      </div>
                    </div>
                    <div style={{ 
                      display: 'flex',
                      flexDirection: 'row',
                      flexWrap: 'nowrap',
                      overflowX: 'auto',
                      gap: '8px',
                      paddingBottom: '4px',
                      paddingTop: '4px', // 최근 조회 종목과 동일하게 수정
                      marginTop: '4px', // 최근 조회 종목과 동일하게 수정
                      msOverflowStyle: 'none', 
                      scrollbarWidth: 'none' 
                    }}>
                      {filteredStocks.map((stock) => (
                        <button 
                          key={stock.value} 
                          onClick={(e) => {
                            e.preventDefault();
                            e.stopPropagation();
                            setShowStockSuggestions(false); 
                            handleStockSelect(stock);
                          }}
                          style={{
                            width: 'auto',
                            padding: '6px 10px',
                            borderRadius: '8px',
                            border: '1px solid #ddd',
                            backgroundColor: '#f5f5f5',
                            textAlign: 'center',
                            cursor: 'pointer',
                            transition: 'background-color 0.2s',
                            fontSize: '13px', // 16px에서 13px로 변경
                            color: '#333',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            gap: '6px',
                            whiteSpace: 'nowrap',
                            minWidth: 'fit-content',
                            flexShrink: 0
                          }}
                          onMouseEnter={(e) => {
                            e.currentTarget.style.color = '#ffffff';
                            e.currentTarget.style.backgroundColor = '#40414F';
                          }}
                          onMouseLeave={(e) => {
                            e.currentTarget.style.color = '#333';
                            e.currentTarget.style.backgroundColor = '#f5f5f5';
                          }}
                        >
                          <span style={{
                            padding: '3px 8px',
                            height: '24px',
                            borderRadius: '6px',
                            border: '1px solid #ddd',
                            backgroundColor: '#f5f5f5',
                            color: '#333',
                            fontSize: '13px', // 16px에서 13px로 변경
                            fontWeight: 'normal',
                            whiteSpace: 'nowrap',
                            display: 'flex',
                            alignItems: 'center'
                          }}>
                            {stock.stockName || stock.display || stock.label.split('(')[0]}
                          </span>
                          <span style={{
                            overflow: 'hidden',
                            textOverflow: 'ellipsis',
                            whiteSpace: 'nowrap',
                            maxWidth: '100%'
                          }}>({stock.value})</span>
                        </button>
                      ))}
                    </div>
                  </div>
                )}
                
                {/* 최근 조회 종목 목록 */}
                {!isLoading && !error && recentStocks.length > 0 && (
                  <div style={{ 
                    marginTop: '4px', // 여백 완전 제거
                    borderTop: '1px solid #eee',
                    paddingTop: '4px',
                    paddingLeft: '5px', 
                    paddingRight: '5px', 
                    paddingBottom: '0' 
                  }}>
                    <div style={{ 
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      marginBottom: '0' // 여백 완전 제거
                    }}>
                      <div style={{ 
                        fontSize: '13px', // 16px에서 13px로 변경
                        fontWeight: 'normal',
                        color: '#666'
                      }}>
                        최근 조회 종목
                      </div>
                      <button
                        onClick={(e) => {
                          e.preventDefault();
                          e.stopPropagation();
                          setShowStockSuggestions(false); 
                          setRecentStocks([]);
                          localStorage.removeItem('recentStocks');
                        }}
                        style={{
                          background: 'none',
                          border: 'none',
                          fontSize: '13px', // 16px에서 13px로 변경
                          color: '#999',
                          cursor: 'pointer',
                          padding: '4px 10px', 
                          height: '28px' 
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
                      paddingTop: '0',
                      marginTop: '2px', // 최소한의 여백만 남김
                      msOverflowStyle: 'none', 
                      scrollbarWidth: 'none'
                    }}>
                      {recentStocks.map((stock) => (
                        <button 
                          key={stock.value} 
                          onClick={(e) => {
                            e.preventDefault();
                            e.stopPropagation();
                            setShowStockSuggestions(false); 
                            handleStockSelect(stock);
                          }}
                          style={{
                            width: 'auto',
                            padding: '6px 10px',
                            borderRadius: '8px',
                            border: '1px solid #ddd',
                            backgroundColor: '#f5f5f5',
                            textAlign: 'center',
                            cursor: 'pointer',
                            transition: 'background-color 0.2s',
                            fontSize: '13px', // 16px에서 13px로 변경
                            color: '#333',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            gap: '6px',
                            whiteSpace: 'nowrap',
                            minWidth: 'fit-content',
                            flexShrink: 0
                          }}
                          onMouseEnter={(e) => {
                            e.currentTarget.style.color = '#ffffff';
                            e.currentTarget.style.backgroundColor = '#40414F';
                          }}
                          onMouseLeave={(e) => {
                            e.currentTarget.style.color = '#333';
                            e.currentTarget.style.backgroundColor = '#f5f5f5';
                          }}
                        >
                          <span style={{
                            padding: '3px 8px',
                            height: '24px',
                            borderRadius: '6px',
                            border: '1px solid #ddd',
                            backgroundColor: '#f5f5f5',
                            color: '#333',
                            fontSize: '13px', // 16px에서 13px로 변경
                            fontWeight: 'normal',
                            whiteSpace: 'nowrap',
                            display: 'flex',
                            alignItems: 'center'
                          }}>
                            {stock.stockName || stock.display || stock.label.split('(')[0]}
                          </span>
                          <span style={{
                            overflow: 'hidden',
                            textOverflow: 'ellipsis',
                            whiteSpace: 'nowrap',
                            maxWidth: '100%'
                          }}>({stock.value})</span>
                        </button>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      )}
      
      {/* 추천 질문 버튼 */}
      {isInputCentered && messages.length === 0 && (
        <div style={{
          width: isMobile ? '90%' : '57.6%', 
          margin: isMobile ? '50px auto 0' : '12px auto 0',
          display: 'flex',
          flexDirection: isMobile ? 'column' : 'row',
          gap: '8px'
        }}>
          <div style={{
            display: 'flex',
            flexDirection: isMobile ? 'column' : 'row',
            gap: isMobile ? '6px' : '8px',
            width: '100%'
          }}>
            {/* 추천 질문 그룹 */}
            <div className="recommendation-buttons-group" style={{
              display: 'flex',
              flexDirection: 'column',
              gap: isMobile ? '6px' : '8px',
              border: '1px solid #ddd',
              borderRadius: '10px',
              padding: isMobile ? '10px' : '12px',
              backgroundColor: '#ffffff',
              flex: '1',
              width: isMobile ? '100%' : '50%',  
            }}>
              <div style={{ 
                fontSize: '13px', // 16px에서 13px로 변경
                marginBottom: '8px',
                color: '#333', 
                fontWeight: '500' 
              }}>
                추천 질문
              </div>
              <button
                onClick={() => {
                  const samsungStock = { 
                    value: '005930', 
                    label: '삼성전자', 
                    stockName: '삼성전자',
                    stockCode: '005930',
                    display: '삼성전자 (005930)'
                  };
                  setSelectedStock(samsungStock);
                  setInputMessage('최근 HBM 개발 상황 및 경쟁사와의 비교');
                  
                  const updatedRecentStocks = [samsungStock, ...recentStocks.filter(s => s.value !== samsungStock.value)].slice(0, 5);
                  setRecentStocks(updatedRecentStocks);
                  try {
                    localStorage.setItem('recentStocks', JSON.stringify(updatedRecentStocks));
                  } catch (error) {
                    console.error('Failed to save recent stocks to localStorage:', error);
                  }
                }}
                style={{
                  width: '100%',
                  padding: '6px 10px',
                  borderRadius: '8px',
                  border: '1px solid #ddd',
                  backgroundColor: '#f5f5f5',
                  textAlign: 'left',
                  cursor: 'pointer',
                  transition: 'background-color 0.2s',
                  fontSize: '13px', // 16px에서 13px로 변경
                  color: '#333',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.color = '#ffffff';
                  e.currentTarget.style.backgroundColor = '#40414F';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.color = '#333';
                  e.currentTarget.style.backgroundColor = '#f5f5f5';
                }}
              >
                <span style={{
                  padding: '3px 8px',
                  height: '24px',
                  borderRadius: '6px',
                  border: '1px solid #ddd',
                  backgroundColor: '#f5f5f5',
                  color: '#333',
                  fontSize: '13px', // 16px에서 13px로 변경
                  fontWeight: 'normal',
                  whiteSpace: 'nowrap',
                  display: 'flex',
                  alignItems: 'center'
                }}>
                  삼성전자
                </span>
                <span style={{
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  whiteSpace: 'nowrap',
                  maxWidth: '100%'
                }}>최근 HBM 개발 상황 및 경쟁사와의 비교</span>
              </button>
              
              <button
                onClick={() => {
                  const skStock = { 
                    value: '000660', 
                    label: 'SK하이닉스', 
                    stockName: 'SK하이닉스',
                    stockCode: '000660',
                    display: 'SK하이닉스 (000660)'
                  };
                  setSelectedStock(skStock);
                  setInputMessage('AI 반도체 시장 진출 전략과 향후 전망');
                  
                  const updatedRecentStocks = [skStock, ...recentStocks.filter(s => s.value !== skStock.value)].slice(0, 5);
                  setRecentStocks(updatedRecentStocks);
                  try {
                    localStorage.setItem('recentStocks', JSON.stringify(updatedRecentStocks));
                  } catch (error) {
                    console.error('Failed to save recent stocks to localStorage:', error);
                  }
                }}
                style={{
                  width: '100%',
                  padding: '6px 10px',
                  borderRadius: '8px',
                  border: '1px solid #ddd',
                  backgroundColor: '#f5f5f5',
                  textAlign: 'left',
                  cursor: 'pointer',
                  transition: 'background-color 0.2s',
                  fontSize: '13px', // 16px에서 13px로 변경
                  color: '#333',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.color = '#ffffff';
                  e.currentTarget.style.backgroundColor = '#40414F';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.color = '#333';
                  e.currentTarget.style.backgroundColor = '#f5f5f5';
                }}
              >
                <span style={{
                  padding: '3px 8px',
                  height: '24px',
                  borderRadius: '6px',
                  border: '1px solid #ddd',
                  backgroundColor: '#f5f5f5',
                  color: '#333',
                  fontSize: '13px', // 16px에서 13px로 변경
                  fontWeight: 'normal',
                  whiteSpace: 'nowrap',
                  display: 'flex',
                  alignItems: 'center'
                }}>
                  SK하이닉스
                </span>
                <span style={{
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  whiteSpace: 'nowrap',
                  maxWidth: '100%'
                }}>AI 반도체 시장 진출 전략과 향후 전망</span>
              </button>
              
              <button
                onClick={() => {
                  const hyundaiStock = { 
                    value: '005380', 
                    label: '현대차', 
                    stockName: '현대차',
                    stockCode: '005380',
                    display: '현대차 (005380)'
                  };
                  setSelectedStock(hyundaiStock);
                  setInputMessage('전기차 시장에서의 경쟁력과 최근 실적 분석');
                  
                  const updatedRecentStocks = [hyundaiStock, ...recentStocks.filter(s => s.value !== hyundaiStock.value)].slice(0, 5);
                  setRecentStocks(updatedRecentStocks);
                  try {
                    localStorage.setItem('recentStocks', JSON.stringify(updatedRecentStocks));
                  } catch (error) {
                    console.error('Failed to save recent stocks to localStorage:', error);
                  }
                }}
                style={{
                  width: '100%',
                  padding: '6px 10px',
                  borderRadius: '8px',
                  border: '1px solid #ddd',
                  backgroundColor: '#f5f5f5',
                  textAlign: 'left',
                  cursor: 'pointer',
                  transition: 'background-color 0.2s',
                  fontSize: '13px', // 16px에서 13px로 변경
                  color: '#333',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.color = '#ffffff';
                  e.currentTarget.style.backgroundColor = '#40414F';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.color = '#333';
                  e.currentTarget.style.backgroundColor = '#f5f5f5';
                }}
              >
                <span style={{
                  padding: '3px 8px',
                  height: '24px',
                  borderRadius: '6px',
                  border: '1px solid #ddd',
                  backgroundColor: '#f5f5f5',
                  color: '#333',
                  fontSize: '13px', // 16px에서 13px로 변경
                  fontWeight: 'normal',
                  whiteSpace: 'nowrap',
                  display: 'flex',
                  alignItems: 'center'
                }}>
                  현대차
                </span>
                <span style={{
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  whiteSpace: 'nowrap',
                  maxWidth: '100%'
                }}>전기차 시장에서의 경쟁력과 최근 실적 분석</span>
              </button>
              
              <button
                onClick={() => {
                  const lgStock = { 
                    value: '373220', 
                    label: 'LG에너지솔루션', 
                    stockName: 'LG에너지솔루션',
                    stockCode: '373220',
                    display: 'LG에너지솔루션 (373220)'
                  };
                  setSelectedStock(lgStock);
                  setInputMessage('배터리 기술 개발 현황 및 글로벌 시장 점유율');
                  
                  const updatedRecentStocks = [lgStock, ...recentStocks.filter(s => s.value !== lgStock.value)].slice(0, 5);
                  setRecentStocks(updatedRecentStocks);
                  try {
                    localStorage.setItem('recentStocks', JSON.stringify(updatedRecentStocks));
                  } catch (error) {
                    console.error('Failed to save recent stocks to localStorage:', error);
                  }
                }}
                style={{
                  width: '100%',
                  padding: '6px 10px',
                  borderRadius: '8px',
                  border: '1px solid #ddd',
                  backgroundColor: '#f5f5f5',
                  textAlign: 'left',
                  cursor: 'pointer',
                  transition: 'background-color 0.2s',
                  fontSize: '13px', // 16px에서 13px로 변경
                  color: '#333',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.color = '#ffffff';
                  e.currentTarget.style.backgroundColor = '#40414F';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.color = '#333';
                  e.currentTarget.style.backgroundColor = '#f5f5f5';
                }}
              >
                <span style={{
                  padding: '3px 8px',
                  height: '24px',
                  borderRadius: '6px',
                  border: '1px solid #ddd',
                  backgroundColor: '#f5f5f5',
                  color: '#333',
                  fontSize: '13px', // 16px에서 13px로 변경
                  fontWeight: 'normal',
                  whiteSpace: 'nowrap',
                  display: 'flex',
                  alignItems: 'center'
                }}>
                  LG에너지솔루션
                </span>
                <span style={{
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  whiteSpace: 'nowrap',
                  maxWidth: '100%'
                }}>배터리 기술 개발 현황 및 글로벌 시장 점유율</span>
              </button>
              
              <button
                onClick={() => {
                  const naverStock = { 
                    value: '035420', 
                    label: 'NAVER', 
                    stockName: 'NAVER',
                    stockCode: '035420',
                    display: 'NAVER (035420)'
                  };
                  setSelectedStock(naverStock);
                  setInputMessage('인공지능 사업 확장과 해외 시장 진출 전략');
                  
                  const updatedRecentStocks = [naverStock, ...recentStocks.filter(s => s.value !== naverStock.value)].slice(0, 5);
                  setRecentStocks(updatedRecentStocks);
                  try {
                    localStorage.setItem('recentStocks', JSON.stringify(updatedRecentStocks));
                  } catch (error) {
                    console.error('Failed to save recent stocks to localStorage:', error);
                  }
                }}
                style={{
                  width: '100%',
                  padding: '6px 10px',
                  borderRadius: '8px',
                  border: '1px solid #ddd',
                  backgroundColor: '#f5f5f5',
                  textAlign: 'left',
                  cursor: 'pointer',
                  transition: 'background-color 0.2s',
                  fontSize: '13px', // 16px에서 13px로 변경
                  color: '#333',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.color = '#ffffff';
                  e.currentTarget.style.backgroundColor = '#40414F';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.color = '#333';
                  e.currentTarget.style.backgroundColor = '#f5f5f5';
                }}
              >
                <span style={{
                  padding: '3px 8px',
                  height: '24px',
                  borderRadius: '6px',
                  border: '1px solid #ddd',
                  backgroundColor: '#f5f5f5',
                  color: '#333',
                  fontSize: '13px', // 16px에서 13px로 변경
                  fontWeight: 'normal',
                  whiteSpace: 'nowrap',
                  display: 'flex',
                  alignItems: 'center'
                }}>
                  NAVER
                </span>
                <span style={{
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  whiteSpace: 'nowrap',
                  maxWidth: '100%'
                }}>인공지능 사업 확장과 해외 시장 진출 전략</span>
              </button>
            </div>
            
            {/* 최신 업데이트 종목 그룹 */}
            <div className="latest-updates-group" style={{
              display: 'flex',
              flexDirection: 'column',
              gap: isMobile ? '6px' : '8px',
              border: '1px solid #ddd',
              borderRadius: '10px',
              padding: isMobile ? '10px' : '12px',
              backgroundColor: '#ffffff',
              flex: '1',
              width: isMobile ? '100%' : '50%',  
              marginTop: isMobile ? '12px' : '0'
            }}>
              <div style={{ 
                fontSize: '13px', // 16px에서 13px로 변경
                marginBottom: '8px',
                color: '#333', 
                fontWeight: '500' 
              }}>
                최신 업데이트 종목
              </div>
              <button
                onClick={() => {
                  const lgStock = { 
                    value: '373220', 
                    label: 'LG에너지솔루션', 
                    stockName: 'LG에너지솔루션',
                    stockCode: '373220',
                    display: 'LG에너지솔루션 (373220)'
                  };
                  setSelectedStock(lgStock);
                  setInputMessage('배터리 기술 개발 현황 및 미래 전망 분석');
                  
                  const updatedRecentStocks = [lgStock, ...recentStocks.filter(s => s.value !== lgStock.value)].slice(0, 5);
                  setRecentStocks(updatedRecentStocks);
                  try {
                    localStorage.setItem('recentStocks', JSON.stringify(updatedRecentStocks));
                  } catch (error) {
                    console.error('Failed to save recent stocks to localStorage:', error);
                  }
                }}
                style={{
                  width: '100%',
                  padding: '6px 10px',
                  borderRadius: '8px',
                  border: '1px solid #ddd',
                  backgroundColor: '#f5f5f5',
                  textAlign: 'left',
                  cursor: 'pointer',
                  transition: 'background-color 0.2s',
                  fontSize: '13px', // 16px에서 13px로 변경
                  color: '#333',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.color = '#ffffff';
                  e.currentTarget.style.backgroundColor = '#40414F';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.color = '#333';
                  e.currentTarget.style.backgroundColor = '#f5f5f5';
                }}
              >
                <span style={{
                  padding: '3px 8px',
                  height: '24px',
                  borderRadius: '6px',
                  border: '1px solid #ddd',
                  backgroundColor: '#f5f5f5',
                  color: '#333',
                  fontSize: '13px', // 16px에서 13px로 변경
                  fontWeight: 'normal',
                  whiteSpace: 'nowrap',
                  display: 'flex',
                  alignItems: 'center'
                }}>
                  LG에너지솔루션
                </span>
                <span style={{
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  whiteSpace: 'nowrap',
                  maxWidth: '100%'
                }}>배터리 생산량 1분기 32% 증가, 전기차 시장 확대로 실적 개선 전망</span>
              </button>
              
              <button
                onClick={() => {
                  const kakaoStock = { 
                    value: '035720', 
                    label: '카카오', 
                    stockName: '카카오',
                    stockCode: '035720',
                    display: '카카오 (035720)'
                  };
                  setSelectedStock(kakaoStock);
                  setInputMessage('AI 기술 투자 현황과 미래 사업 전략');
                  
                  const updatedRecentStocks = [kakaoStock, ...recentStocks.filter(s => s.value !== kakaoStock.value)].slice(0, 5);
                  setRecentStocks(updatedRecentStocks);
                  try {
                    localStorage.setItem('recentStocks', JSON.stringify(updatedRecentStocks));
                  } catch (error) {
                    console.error('Failed to save recent stocks to localStorage:', error);
                  }
                }}
                style={{
                  width: '100%',
                  padding: '6px 10px',
                  borderRadius: '8px',
                  border: '1px solid #ddd',
                  backgroundColor: '#f5f5f5',
                  textAlign: 'left',
                  cursor: 'pointer',
                  transition: 'background-color 0.2s',
                  fontSize: '13px', // 16px에서 13px로 변경
                  color: '#333',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.color = '#ffffff';
                  e.currentTarget.style.backgroundColor = '#40414F';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.color = '#333';
                  e.currentTarget.style.backgroundColor = '#f5f5f5';
                }}
              >
                <span style={{
                  padding: '3px 8px',
                  height: '24px',
                  borderRadius: '6px',
                  border: '1px solid #ddd',
                  backgroundColor: '#f5f5f5',
                  color: '#333',
                  fontSize: '13px', // 16px에서 13px로 변경
                  fontWeight: 'normal',
                  whiteSpace: 'nowrap',
                  display: 'flex',
                  alignItems: 'center'
                }}>
                  카카오
                </span>
                <span style={{
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  whiteSpace: 'nowrap',
                  maxWidth: '100%'
                }}>글로벌 AI 기업과 협력 발표, 생성형 AI 기술 통합으로 시장 점유율 확대 계획</span>
              </button>
            </div>
          </div>
        </div>
      )}
      
    </div> // containerStyle 끝
  );
}

// 메인 컴포넌트
export default function AIChatArea() {
  return (
    <AIChatAreaContent />
  )
}
