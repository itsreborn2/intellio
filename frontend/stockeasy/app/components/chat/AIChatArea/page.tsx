'use client';

import React, { useEffect, useState, useCallback, useRef, useMemo } from 'react';
import { toast } from 'sonner';
import { useRouter } from 'next/navigation';
import { checkTimeRestriction, getRestrictionMessage } from '@/app/utils/timeRestriction';
import { StockSelectorProvider, useStockSelector } from './context/StockSelectorContext';
import { ChatLayout, MobileChatLayout } from './layouts';
import { 
  MessageList, 
  InputArea, 
  StockSuggestions, 
  RecommendedQuestions, 
  LatestUpdates
} from './components';
import { PreliminaryChartDisplay } from './components/PreliminaryChartDisplay';

import { useMessageProcessing } from './hooks';
import { useIsMobile } from './hooks';
import { useChatStore } from '@/stores/chatStore';
import { useTokenUsageStore } from '@/stores/tokenUsageStore';
import { useQuestionCountStore } from '@/stores/questionCountStore';
import { useUserModeStore } from '@/stores/userModeStore';
import { StockOption, PopularStock } from './types';
import { getPopularStocks } from '@/services/api/stats';
import type { IStockPopularityItem } from '@/types/api/stats';

/**
 * AIChatArea 메인 컴포넌트
 * 분리된 기능 컴포넌트들을 통합하고 상태를 관리합니다.
 */
function AIChatAreaContent() {
  const isMobile = useIsMobile();
  const router = useRouter();
  // ChatStore에서 필요한 상태 및 액션 직접 가져오기
  const { 
    currentSession, 
    messages: storeMessages, 
    isLoading,
    selectedStock,
    isInputCentered,
    showTitle,
    copyStates,
    expertMode,
    elapsedTime,
    // 액션들
    setCurrentSession: setStoreSession,
    setMessages,
    addMessage,
    clearMessages,
    updateMessage,
    removeMessage,
    setIsLoading: setProcessing,
    setSelectedStock,
    setInputCentered,
    setShowTitle,
    resetChat,
    toggleExpertMode,
    setCopyState,
    getUiMessages
  } = useChatStore();

  const { 
    state: stockState,
    setSearchTerm,
    setFilteredStocks,
    showSuggestions,
    setSearchMode,
    addRecentStock,
    clearRecentStocks,
    fetchStockList
  } = useStockSelector();

  // MessageList에 대한 ref 생성
  const messageListRef = useRef<{scrollToBottom: () => void}>(null);

  // 사용자 메시지 전송 상태 추가
  const [isUserSending, setIsUserSending] = useState<boolean>(false);
  
  // 전송 중 상태를 즉시 추적하기 위한 ref 추가
  const isSendingRef = useRef<boolean>(false);
  
  // 상태 메시지 ID 참조 추가
  const statusMessageIdRef = useRef<string | null>(null);

  // 사용자 모드 스토어 추가
  const { mode: userMode } = useUserModeStore();
  
  const { fetchSummary } = useTokenUsageStore();
  const questionStore = useQuestionCountStore();
  const questionCount = questionStore.summary?.total_questions || 0;

  
  // 창 너비 상태 추가
  const [isInitialLoadComplete, setIsInitialLoadComplete] = useState(false);
  const [popularStocksDaily, setPopularStocksDaily] = useState<PopularStock[]>([]);
  const [popularStocksWeekly, setPopularStocksWeekly] = useState<PopularStock[]>([]); // CSV 데이터를 저장할 상태
  const [windowWidth, setWindowWidth] = useState<number>(1024); // 기본값 설정

  // 실시간 차트 스트리밍 관련 상태
  const [preliminaryChart, setPreliminaryChart] = useState<{
    components: any[];
    message: string;
    timestamp: number;
    stockCode: string;
    stockName: string;
    stockInfo?: any;  // stockInfo 필드 추가
  } | null>(null);

  const [finalResponse, setFinalResponse] = useState<any>(null);
  const [currentStatus, setCurrentStatus] = useState<string>('');

  // API에서 인기 검색 종목 데이터를 가져오기 위한 함수 (useCallback으로 메모이제이션)
  const fetchPopularStocks = useCallback(async () => {
    try {
      const response = await getPopularStocks(10); // API 한 번만 호출

      // 당일 데이터 처리 (data_24h 사용)
      if (response.ok && response.data_24h?.stocks) {
        const parsedDailyData = response.data_24h.stocks.map((item: IStockPopularityItem, index: number) => ({
          rank: index + 1,
          stock: {
            value: item.stock_code,
            label: item.stock_name,
            stockName: item.stock_name,
            stockCode: item.stock_code,
          },
          rankChange: item.rank_change, // 순위 변동 정보 추가
        }));
        setPopularStocksDaily(parsedDailyData);
      } else {
        setPopularStocksDaily([]);
      }

      // 주간 데이터 처리 (data_7d 사용)
      if (response.ok && response.data_7d?.stocks) {
        const parsedWeeklyData = response.data_7d.stocks.map((item: IStockPopularityItem, index: number) => ({
          rank: index + 1,
          stock: {
            value: item.stock_code,
            label: item.stock_name,
            stockName: item.stock_name,
            stockCode: item.stock_code,
          },
          rankChange: item.rank_change, // 순위 변동 정보 추가
        }));
        setPopularStocksWeekly(parsedWeeklyData);
      } else {
        setPopularStocksWeekly([]);
      }
    } catch (error) {
      console.error('[AIChatArea] 인기 검색어 API 호출 중 에러 발생:', error);
      setPopularStocksDaily([]);
      setPopularStocksWeekly([]);
    }
  }, [getPopularStocks, setPopularStocksDaily, setPopularStocksWeekly]); // useCallback 의존성 배열에 필요한 함수들 추가

  // API에서 인기 검색 종목 데이터를 가져오기 위한 useEffect
  useEffect(() => {
    fetchPopularStocks();
  }, [fetchPopularStocks]); // useEffect의 의존성 배열에 fetchPopularStocks 추가

  useEffect(() => {
  }, [popularStocksDaily]);

  useEffect(() => {
  }, [popularStocksWeekly]);

  // 사용자가 주식 종목을 선택했을 때 호출되는 함수
  // useCallback을 사용하여 함수 재생성 방지관리 함수 전달
  const { 
    elapsedTime: processingElapsedTime, 
    sendMessage
  } = useMessageProcessing(
    questionCount,
    {
      addMessage: addMessage as any, // 타입 호환성 문제 해결
      updateMessage,
      removeMessage,
      setCurrentSession: setStoreSession,
      setProcessing,
      getMessages: getUiMessages
    },
    currentSession,
    {
      onQuestionLimitExceeded: () => {
        console.log('질문 할당량 초과');
        // 할당량 초과 시 안내 메시지
        toast.error('오늘의 질문 할당량(10개)을 모두 소진하였습니다. 내일 다시 이용해주세요.');
      },
      onProcessingStart: () => {
        // 첫 메시지 전송 시 중앙 정렬 해제
        if (isInputCentered) {
          setInputCentered(false);
        }
      },
      onProcessingComplete: () => {
        // 질문 개수 업데이트 (Zustand 스토어)
        questionStore.fetchSummary && questionStore.fetchSummary('day', 'day');
        
        // 토큰 사용량 업데이트 (Zustand 스토어)
        fetchSummary && fetchSummary();
        
        // 최종 응답 설정 (기존 메시지들을 최종 응답으로 설정)
        setFinalResponse(uiMessages);
      },
      onPreliminaryChart: (data) => {
        console.log('[AI채팅영역] 임시 차트 수신:', data);
        console.log('[AI채팅영역] data.stockInfo:', data.stockInfo);
        // 임시 차트 데이터 설정 (stockInfo 포함)
        setPreliminaryChart({
          components: data.components,
          message: data.message,
          timestamp: data.timestamp,
          stockCode: data.stock_code,
          stockName: data.stock_name,
          stockInfo: data.stockInfo  // stockInfo 추가
        });
        // 현재 상태 업데이트
        setCurrentStatus("📊 차트가 준비되었습니다. 추가 분석을 진행하고 있습니다...");
      },
    }
  );

  // 마운트/언마운트 이벤트 핸들링
  useEffect(() => {
    
    // AIChatArea 컴포넌트가 마운트되었음을 알리는 이벤트 발생
    const mountEvent = new CustomEvent('aiChatAreaMounted', { detail: { isMounted: true } });
    window.dispatchEvent(mountEvent);
    
    // 초기 마운트 시 항상 상태 초기화 - 페이지 새로고침 또는 다른 페이지에서 이동 시 적용
    
    // 리액트 상태 초기화
    setInputCentered(true);
    setMessages([]);
    setStoreSession(null);
    setSelectedStock(null);
    setSearchTerm('');
    
    // searchMode를 true로 설정하여 "종목명 또는 종목코드 검색" 표시
    setSearchMode(true);
    
    // Zustand 스토어 상태도 초기화
    setStoreSession(null);
    clearMessages();
    
    // isLoading 상태 초기화 추가
    setProcessing(false);
    
    // homeButtonClick 이벤트 리스너 등록 - 한 번만 등록되도록 함
    const handleHomeButtonClick = (event: Event) => {
      //console.log('[AIChatArea] 홈버튼 클릭 이벤트 감지:', event);
      
      try {
        // 이벤트 세부 정보 로깅
        const customEvent = event as CustomEvent;
        //console.log('[AIChatArea] 이벤트 detail:', customEvent.detail);
        
        // Zustand 스토어 상태 초기화 전 로그
        console.log('[AIChatArea] 스토어 초기화 전 상태:', 
          '세션:', useChatStore.getState().currentSession?.id,
          '메시지 수:', useChatStore.getState().messages.length
        );
        
        // Zustand 스토어 상태도 초기화
        setStoreSession(null);
        //console.log('[AIChatArea] 세션 초기화 후:', useChatStore.getState().currentSession);
        
        clearMessages();
        //console.log('[AIChatArea] 메시지 초기화 후:', useChatStore.getState().messages.length);
        
        // isLoading 상태 초기화 추가
        setProcessing(false);
        
        // 함수형 업데이트를 사용하여 최신 상태 참조
        setInputCentered(true);
        setMessages([]);
        setStoreSession(null);
        setSelectedStock(null);
        setSearchTerm('');
        
        // searchMode를 true로 설정하여 "종목명 또는 종목코드 검색" 표시
        setSearchMode(true);
        
        console.log('[AIChatArea] 모든 상태 초기화 완료');
      } catch (error) {
        console.error('[AIChatArea] 홈버튼 클릭 이벤트 처리 중 오류:', error);
      }
    };
    
    // 이벤트 리스너 등록 - document에도 등록 시도
    window.addEventListener('homeButtonClick', handleHomeButtonClick);
    document.addEventListener('homeButtonClick', handleHomeButtonClick);
    
    // 전역 리셋 함수 - 디버깅용 (직접 호출 가능)
    // @ts-ignore - 전역 객체에 속성 추가
    window.__resetAIChatArea = () => {
      console.log('[AIChatArea] 직접 리셋 함수 호출됨');
      handleHomeButtonClick(new CustomEvent('manual_reset'));
    };
    
    // 컴포넌트 언마운트 시 cleanup 함수
    return () => {
      console.log('[AIChatArea] 컴포넌트 언마운트: 이벤트 리스너 제거');
      
      // AIChatArea 컴포넌트가 언마운트되었음을 알리는 이벤트 발생
      const unmountEvent = new CustomEvent('aiChatAreaUnmounted', { detail: { isMounted: false } });
      window.dispatchEvent(unmountEvent);
      
      // homeButtonClick 이벤트 리스너 제거
      window.removeEventListener('homeButtonClick', handleHomeButtonClick);
      document.removeEventListener('homeButtonClick', handleHomeButtonClick);
      
      // 전역 리셋 함수 제거
      // @ts-ignore - 전역 객체에서 속성 제거
      delete window.__resetAIChatArea;
    };
  }, []); // 의존성 배열 비움 - 마운트 시 한 번만 실행

  // 클라이언트 측에서만 window 객체 접근
  useEffect(() => {
    if (typeof window !== 'undefined') {
      setWindowWidth(window.innerWidth);
      
      const handleResize = () => {
        setWindowWidth(window.innerWidth);
      };
      
      window.addEventListener('resize', handleResize);
      return () => {
        window.removeEventListener('resize', handleResize);
      };
    }
  }, []);

  // 메시지 전송 핸들러
  const handleSendMessage = async () => {
    // 입력창을 즉시 중앙에서 해제하여 하단 입력창이 보이지 않도록 함
    if (isInputCentered) {
      setInputCentered(false);
    }
    
    // 시간 제한 체크
    const { isRestricted, nextAvailableTime } = checkTimeRestriction();
    if (isRestricted) {
      const restrictionMessage = getRestrictionMessage(nextAvailableTime);
      toast.error(restrictionMessage);
      return;
    }

    // ref를 사용하여 즉시 전송 상태 확인
    if (isSendingRef.current || isLoading) {
      console.log('[AIChatAreaContent] 이미 메시지 전송 중입니다.');
      return;
    }

    console.log(`[AIChatAreaContent] 메시지 전송 요청 : ${stockState.searchTerm.trim()}`);

    // 선택된 종목과 입력 메시지 확인
    if ((!selectedStock && !currentSession) || !stockState.searchTerm.trim()) {
      console.error('종목이 선택되지 않았거나 활성 세션이 없거나 메시지가 없습니다.');
      return;
    }
    
    // ref를 사용하여 전송 상태 즉시 설정
    isSendingRef.current = true;
    // UI 업데이트를 위한 state 설정
    setIsUserSending(true);
    
    try {
      // 현재 메시지와 종목 상태 저장
      const currentMessage = stockState.searchTerm;
      const currentStock = selectedStock;
      const currentRecentStocks = stockState.recentStocks;
      
      // 메시지 전송 전 입력창 초기화
      setSearchTerm('');


      // 메세지 전송 요청할때, 젤 아래로 한번 내려주자.
      if (messageListRef.current?.scrollToBottom) {
        messageListRef.current.scrollToBottom();
        
        // 추가 안정성을 위해 약간의 지연 후 한 번 더 실행
        setTimeout(() => {
          messageListRef.current?.scrollToBottom && messageListRef.current.scrollToBottom();
        }, 100);
      }
      
      // 토글 버튼 표시를 위한 커스텀 이벤트 발생
      const showToggleEvent = new CustomEvent('showToggleButton', {
        bubbles: true
      });
      window.dispatchEvent(showToggleEvent);
     
      
      // 세션 정보 및 종목 정보 준비
      const sessionId = currentSession?.id || '';
      const stockName = currentStock?.stockName || currentSession?.stock_name || '';
      const stockCode = currentStock?.stockCode || currentSession?.stock_code || '';
      
      // 메시지 ID 생성 (UUID 사용)
      const userMessageId = `user-${Date.now()}-${Math.random().toString(36).substring(2, 9)}`;
      console.log('[AIChatAreaContent] 생성된 사용자 메시지 ID:', userMessageId);
      
      // ChatStore에 사용자 메시지 추가
      addMessage({
        id: userMessageId,
        role: 'user',
        content: currentMessage,
        created_at: new Date().toISOString(),
        stock_name: stockName,
        stock_code: stockCode,
        chat_session_id: sessionId,
        ok: true,
        status_message: '',
        metadata: {
          stockInfo: {
            stockName,
            stockCode
          }
        }
      });
      
      console.log('[AIChatAreaContent] ChatStore에 사용자 메시지 추가됨:', userMessageId);
      
      // useMessageProcessing 훅의 sendMessage 함수 호출 - 이제는 상태 메시지 생성만 담당
      await sendMessage(
        currentMessage,
        currentStock || null, // 종목이 선택되지 않아도 null로 전달
        currentRecentStocks,
        currentSession !== null // 현재 세션이 있으면 후속질문으로 간주
      );
      
      // 기존 로그 대신 사용자 메시지 추적 로그 추가
      console.log('[AIChatAreaContent] 메시지 전송 중 - chatStore 메시지 수:', useChatStore.getState().messages.length);
      
      // 세션이 없는 경우에는 종목 선택 초기화
      if (!currentSession) {
        setSelectedStock(null);
      } else {
        console.log('[AIChatAreaContent] 세션 있음 - 종목 선택 유지');
      }
      
      // 세션 상태에 관계없이 종목 선택 초기화
      // 후속 질문 모드에서는 종목 선택이 필요 없음
      setSelectedStock(null);
      setSearchMode(false);
      
      // 종목이 선택된 경우에만 최근 종목에 추가
      if (currentStock) {
        addRecentStock(currentStock);
      }
      
      // 채팅 메시지 전송 이벤트 발생 - 채팅 세션 갱신을 위한 이벤트
      const chatMessageSentEvent = new CustomEvent('chatMessageSent');
      window.dispatchEvent(chatMessageSentEvent);
      
      // 전송 플래그 리셋 (AI 응답이 완료된 후)
      setTimeout(() => {
        setIsUserSending(false);
        isSendingRef.current = false;
      }, 1000);
    } catch (error: any) {
      console.error('[AIChatAreaContent] 메시지 전송 중 오류 발생:', error);
      
      // 에러 메시지 표시 - useMessageProcessing에서 이미 toast가 표시되므로 중복 방지
      if (!error.message?.includes('채팅 세션 생성')) {
        const errorMessage = error.message || '메시지 전송 중 오류가 발생했습니다.';
        toast.error(errorMessage);
      }
      
      setIsUserSending(false);
      isSendingRef.current = false;
    }
  };

  // 종목 선택 핸들러
  const handleSelectStock = (stock: StockOption | null) => {
    if (stock) {
      addRecentStock(stock);
      // ChatStore에 선택된 종목 업데이트
      setSelectedStock(stock);
    } else {
      // stock이 null인 경우(종목 선택 해제) 처리
      setSelectedStock(null);
    }
  };

  // 질문 선택 핸들러
  const handleSelectQuestion = (stock: StockOption, question: string) => {
    // ChatStore에 상태 업데이트
    handleSelectStock(stock);
    
    // 질문을 입력창에 설정
    setSearchTerm(question);
    
    // 종목 제안 팝업 닫기
    showSuggestions(false);
  };

  // 업데이트 선택 핸들러
  const handleSelectUpdate = (stock: StockOption, updateInfo: string) => {
    // ChatStore에 상태 업데이트
    handleSelectStock(stock);
    
    // 입력창을 비워서 placeholder("이 종목에 관하여 궁금한 점을 물어보세요")가 보이도록 설정
    setSearchTerm("");
    
    // 종목 제안 팝업 닫기
    showSuggestions(false);
    
    // searchMode를 false로 설정하여 "이 종목에 관하여 궁금한 점을 물어보세요" 문구가 표시되도록 함
    setSearchMode(false);
  };

  // ChatStore에서 UI용 메시지 가져오기
  const uiMessages = useMemo(() => getUiMessages(), [storeMessages]);

  // 채팅 컨텐츠 렌더링
  const renderChatContent = () => {
    // 메모이제이션된 StockSuggestions Props 생성
    const stockSuggestionsProps = useMemo(() => ({
      onSelectStock: handleSelectStock,
      popularStocksDaily,
      popularStocksWeekly,
      recentStocks: stockState.recentStocks,
      isMobile,
      isInputCentered,
      searchTerm: stockState.searchTerm,
      isLoading: stockState.isLoading,
      error: stockState.error,
      filteredStocks: stockState.filteredStocks,
      onClearRecentStocks: clearRecentStocks,
    }), [
      handleSelectStock,
      popularStocksDaily,
      popularStocksWeekly,
      stockState.recentStocks,
      isMobile,
      isInputCentered,
      stockState.searchTerm,
      stockState.isLoading,
      stockState.error,
      stockState.filteredStocks,
      clearRecentStocks,
    ]);

    return (
      <>
        {/* 메시지 목록 영역 */}
        {!isInputCentered && uiMessages.length > 0 && (
          <MessageList
            ref={messageListRef}
            messages={uiMessages}
            copyStates={copyStates}
            expertMode={expertMode}
            timerState={{}}
            isInputCentered={isInputCentered}
            isUserSending={isUserSending}
            onCopy={(id) => setCopyState(id, true)}
            onToggleExpertMode={(id) => toggleExpertMode(id)}
          />
        )}

        {/* 임시 차트 팝업 - 분석 중이거나 완료된 상태에서 표시 */}
        {preliminaryChart && (isLoading || !isLoading) && (
          <PreliminaryChartDisplay 
            chartData={preliminaryChart}
            onClose={() => setPreliminaryChart(null)}
            isCompleted={!isLoading}
            onViewFinalReport={() => {
              // 임시 차트 팝업 닫기
              setPreliminaryChart(null);
              // 최종 메시지로 스크롤
              if (messageListRef.current?.scrollToBottom) {
                messageListRef.current.scrollToBottom();
              }
            }}
          />
        )}

        {/* 입력 영역 (상단 중앙 또는 하단에 위치) */}
        {/* 후속 질문 일단 차단.*/}
        {!currentSession && !isUserSending && (
          <InputArea
            inputMessage={stockState.searchTerm || ''}
            setInputMessage={setSearchTerm}
            selectedStock={selectedStock}
            isProcessing={isLoading}
            isInputCentered={isInputCentered}
            showStockSuggestions={stockState.showStockSuggestions}
            stockOptions={stockState.stockOptions}
            recentStocks={stockState.recentStocks}
            searchMode={stockState.searchMode}
            isLoading={stockState.isLoading}
            error={stockState.error}
            windowWidth={windowWidth}
            onSendMessage={handleSendMessage}
            onStockSelect={handleSelectStock}
            onShowStockSuggestions={showSuggestions}
            onSearchModeChange={setSearchMode}
            onClearRecentStocks={clearRecentStocks}
            scrollToBottom={() => messageListRef.current?.scrollToBottom && messageListRef.current.scrollToBottom()}
            showTitle={showTitle}
            currentChatSession={currentSession}
          />
        )}
        
        {/* 추천 질문 및 최신 업데이트 종목 영역 - 첫 진입 시 */}
        {isInputCentered && uiMessages.length === 0 && (
          <div 
            style={{
              display: 'flex',
              flexDirection: isMobile ? 'column' : 'row',
              gap: isMobile ? '20px' : '20px',
              width: '100%',
              justifyContent: 'center', 
              alignItems: isMobile ? 'center' : 'flex-start',
              marginTop: isMobile ? '2rem' : '0'
            }}
          >
            {/* 추천 질문 컴포넌트 */}
            <RecommendedQuestions 
              onSelectQuestion={handleSelectQuestion}
            />
            
            {/* 최신 업데이트 종목 컴포넌트 */}
            <LatestUpdates 
              updatesDaily={popularStocksDaily}
              updatesWeekly={popularStocksWeekly}
              onSelectUpdate={handleSelectUpdate}
            />
          </div>
        )}
        
        {/* 종목 제안 영역 - 메모이제이션된 props 사용 */}
        <StockSuggestions {...stockSuggestionsProps} />
      </>
    );
};

// 컴포넌트 마운트 시 종목 데이터 로드 (빈 의존성 배열로 최초 1회만 실행)
useEffect(() => {
  // 로컬 상태 변수로 이미 실행 여부 확인
  let isFirstLoad = true;

  if (isFirstLoad) {
    const { stockOptions } = stockState;
    if (stockOptions.length === 0) {
      fetchStockList();
    } else {
    }
    isFirstLoad = false;
  }
}, []); // 빈 의존성 배열로 최초 한 번만 실행

// window 객체에 디버깅 함수 추가 (개발용)
useEffect(() => {
  if (typeof window !== 'undefined') {
    // 전역 초기화 함수 정의
    const resetChatArea = () => {
      console.log('[AIChatArea] 직접 초기화 함수 호출');
      
      try {
        // 스토어 상태 초기화 전 상태 확인
        console.log('[AIChatArea] 초기화 전 상태:', 
          'useChatStore 세션:', useChatStore.getState().currentSession?.id,
          'useChatStore 메시지 수:', useChatStore.getState().messages.length
        );
        
        // Zustand 스토어 상태 초기화
        setStoreSession(null);
        clearMessages();
        
        // isLoading 상태 초기화 추가
        setProcessing(false);
        
        // 리액트 상태 초기화
        setInputCentered(true);
        setMessages([]);
        setSelectedStock(null);
        setSearchTerm('');
        
        // searchMode를 true로 설정하여 "종목명 또는 종목코드 검색" 표시
        setSearchMode(true);
        
        console.log('[AIChatArea] 초기화 후 상태:', 
          'useChatStore 세션:', useChatStore.getState().currentSession,
          'useChatStore 메시지 수:', useChatStore.getState().messages.length
        );
      } catch (error) {
        console.error('[AIChatArea] 초기화 중 오류:', error);
      }
    };
    
    // @ts-ignore - 디버깅용 메서드 추가
    window.__debug_resetAIChatArea = resetChatArea;
    
    // homeButtonClick 이벤트 리스너 함수 정의
    const handleHomeButtonClick = () => {
      resetChatArea();
    };
    
    // 이벤트 리스너 등록
    window.addEventListener('homeButtonClick', handleHomeButtonClick);
    
    // 클린업
    return () => {
      if (typeof window !== 'undefined') {
        // @ts-ignore - 디버깅용 메서드 제거
        delete window.__debug_resetAIChatArea;
        
        // 이벤트 리스너 제거
        window.removeEventListener('homeButtonClick', handleHomeButtonClick);
      }
    };
  }
}, [
  setInputCentered, 
  setMessages, 
  setStoreSession, 
  setSelectedStock, 
  setSearchTerm, 
  clearMessages
]);

// 활성 세션이 있을 때 종목 선택 초기화
useEffect(() => {
  if (currentSession) {
    console.log('[AIChatAreaContent] 활성 세션 감지 - 종목 선택 초기화');
    setSelectedStock(null);
  }
}, [currentSession, setSelectedStock]);

return (
  <>
    {isMobile ? (
      // 모바일 레이아웃
      <MobileChatLayout>
        {renderChatContent()}
      </MobileChatLayout>
    ) : (
      // 데스크톱 레이아웃
      <ChatLayout>
        {renderChatContent()}
      </ChatLayout>
    )}
  </>
);
}

/**
 * AIChatArea 페이지 컴포넌트
 * 컨텍스트 제공자로 래핑하여 전체 상태를 관리합니다.
 */
export default function AIChatArea() {
  return (
    <StockSelectorProvider>
      <AIChatAreaContent />
    </StockSelectorProvider>
  );
}
