'use client';

import React, { useEffect, useState, useCallback, useRef } from 'react';
import { toast } from 'sonner';
import { ChatProvider, useChatContext } from './context/ChatContext';
import { StockSelectorProvider, useStockSelector } from './context/StockSelectorContext';
import { ChatLayout, MobileChatLayout } from './layouts';
import { 
  MessageList, 
  InputArea, 
  StockSuggestions, 
  RecommendedQuestions, 
  LatestUpdates
} from './components';
import { useIsMobile, useMessageProcessing } from './hooks';
import { useChatStore } from '@/stores/chatStore';
import { useTokenUsageStore } from '@/stores/tokenUsageStore';
import { useQuestionCountStore } from '@/stores/questionCountStore';
import { useUserModeStore } from '@/stores/userModeStore';
import { StockOption, ChatMessage } from './types';

/**
 * AIChatArea 메인 컴포넌트
 * 분리된 기능 컴포넌트들을 통합하고 상태를 관리합니다.
 */
function AIChatAreaContent() {
  const isMobile = useIsMobile();
  const { state, toggleExpertMode, setCopyState, setSelectedStock, addMessage, updateMessage, removeMessage, setProcessing, setInputCentered, setChatSession, setAllMessages } = useChatContext();
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

  // Zustand 스토어 사용
  const { 
    currentSession, 
    messages: storeMessages, 
    setCurrentSession: setStoreSession,  
    clearMessages                       
  } = useChatStore();
  
  // 사용자 모드 스토어 추가
  const { mode: userMode } = useUserModeStore();
  
  const { fetchSummary } = useTokenUsageStore();
  const questionStore = useQuestionCountStore();
  const questionCount = questionStore.summary?.total_questions || 0;
  
  // 메시지 처리 로직을 위한 커스텀 훅 사용 - 상태 관리 함수 전달
  const { 
    elapsedTime, 
    sendMessage
  } = useMessageProcessing(
    questionCount,
    {
      addMessage,
      updateMessage,
      removeMessage,
      setCurrentSession: setChatSession,
      setProcessing,
      getMessages: () => state.messages
    },
    state.currentChatSession,
    {
      onQuestionLimitExceeded: () => {
        console.log('질문 할당량 초과');
        // 할당량 초과 시 안내 메시지
        toast.error('오늘의 질문 할당량(30개)을 모두 소진하였습니다. 내일 다시 이용해주세요.');
      },
      onProcessingStart: () => {
        // 첫 메시지 전송 시 중앙 정렬 해제
        if (state.isInputCentered) {
          setInputCentered(false);
        }
      },
      onProcessingComplete: () => {
        // 질문 개수 업데이트 (Zustand 스토어)
        questionStore.fetchSummary && questionStore.fetchSummary('day', 'day');
        
        // 토큰 사용량 업데이트 (Zustand 스토어)
        fetchSummary && fetchSummary();
      }
    }
  );
  
  // Zustand 스토어와 동기화 하는 로직 추가 (필요한 경우)
  useEffect(() => {
    if (currentSession && storeMessages.length > 0) {
      // console.log('[AIChatArea] 스토어 동기화 시작 - 세션:', currentSession.id, '메시지 수:', storeMessages.length);
      // console.log('[AIChatArea] 동기화 전 상태 - ChatContext 메시지 수:', state.messages.length);
      // console.log('[AIChatArea] 동기화 전 ChatContext 메시지:', 
      //   state.messages.map(m => ({ id: m.id, role: m.role, content: m.content.substring(0, 20) }))
      // );
      // console.log('[AIChatArea] 동기화 전 ChatStore 메시지:', 
      //   storeMessages.map(m => ({ id: m.id, role: m.role, content: m.content.substring(0, 20) }))
      // );

      // 저장소에 메시지가 있으면 ChatContext 상태 업데이트
      const convertedMessages = storeMessages.map(msg => {
        const stockName = currentSession.stock_name || '';
        const stockCode = currentSession.stock_code || '';
        
        return {
          id: msg.id,
          role: msg.role as 'user' | 'assistant' | 'status',
          content: msg.content,
          content_expert: msg.content_expert,
          timestamp: msg.created_at ? new Date(msg.created_at).getTime() : Date.now(),
          responseId: msg.metadata?.responseId,
          stockInfo: (stockName && stockCode) ? {
            stockName: stockName,
            stockCode: stockCode
          } : undefined,
          isProcessing: msg.metadata?.isProcessing,
          agent: msg.metadata?.agent,
          elapsed: msg.metadata?.elapsed
        };
      });
      
      // 레이아웃 설정 변경
      setInputCentered(false);
      
      // 메시지 목록 업데이트 전 로그
      console.log('[AIChatArea] 메시지 설정 전:', convertedMessages.map(m => ({ id: m.id, role: m.role })));
      
      // 메시지 목록 업데이트
      setAllMessages(convertedMessages);
      
      console.log('[AIChatArea] 메시지 설정 후 - ChatContext 메시지 수:', state.messages.length);
      
      // 채팅 세션 정보 설정 - 이 부분이 누락되어 있었음
      setChatSession(currentSession);
      console.log('[AIChatArea] 채팅 세션 설정:', currentSession.id);
      
      // 세션 정보에서 종목 정보 가져오기
      if (currentSession.stock_name && currentSession.stock_code) {
        const stockOption: StockOption = {
          value: currentSession.stock_code,
          label: `${currentSession.stock_name} (${currentSession.stock_code})`,
          stockName: currentSession.stock_name,
          stockCode: currentSession.stock_code,
          display: currentSession.stock_name
        };
        setSelectedStock(stockOption);
        console.log('[AIChatArea] 종목 정보 설정:', stockOption.stockName);
      }
    }
  }, [currentSession, storeMessages]);
  
  // currentChatSession이 변경될 때마다 ChatContext에 세션 정보 업데이트
  // --> useMessageProcessing에서 직접 setChatSession을 호출하므로 이 useEffect는 불필요

  // 추천 질문 데이터
  const sampleRecommendedQuestions = [
    {
      stock: { 
        value: '005930', 
        label: '삼성전자', 
        stockName: '삼성전자', 
        stockCode: '005930' 
      },
      question: '최근 HBM 개발 상황은?'
    },
    {
      stock: { 
        value: '000660', 
        label: 'SK하이닉스', 
        stockName: 'SK하이닉스', 
        stockCode: '000660' 
      },
      question: 'AI 반도체 시장 전망은?'
    },
    {
      stock: { 
        value: '005380', 
        label: '현대차', 
        stockName: '현대차', 
        stockCode: '005380' 
      },
      question: '전기차 시장에서의 경쟁력은?'
    },
    {
      stock: { 
        value: '051910', 
        label: 'LG에너지솔루션', 
        stockName: 'LG에너지솔루션', 
        stockCode: '051910' 
      },
      question: '배터리 기술 개발 현황은?'
    },
    {
      stock: { 
        value: '035420', 
        label: 'NAVER', 
        stockName: 'NAVER', 
        stockCode: '035420' 
      },
      question: '인공지능 사업 확장과 전망은?'
    }
  ];

  // 최신 업데이트 종목 데이터
  const sampleLatestUpdates = [
    {
      stock: { 
        value: '051910', 
        label: 'LG에너지솔루션', 
        stockName: 'LG에너지솔루션', 
        stockCode: '051910' 
      },
      updateInfo: '배터리 생산량 증대'
    },
    {
      stock: { 
        value: '035720', 
        label: '카카오', 
        stockName: '카카오', 
        stockCode: '035720' 
      },
      updateInfo: '글로벌 AI 기업과 협력 발표'
    },
    {
      stock: { 
        value: '049800', 
        label: '우진플라임', 
        stockName: '우진플라임', 
        stockCode: '049800' 
      },
      updateInfo: '월별 전망, 잠정치, 실적 등의 통계, 앞으로 전망'
    }
  ];

  // 마운트/언마운트 이벤트 핸들링
  useEffect(() => {
    console.log('[AIChatArea] 컴포넌트 마운트: 이벤트 리스너 설정');
    
    // AIChatArea 컴포넌트가 마운트되었음을 알리는 이벤트 발생
    const mountEvent = new CustomEvent('aiChatAreaMounted', { detail: { isMounted: true } });
    window.dispatchEvent(mountEvent);
    
    // 초기 마운트 시 항상 상태 초기화 - 페이지 새로고침 또는 다른 페이지에서 이동 시 적용
    // 이전에 storeMessages 의존성을 사용했으나, 항상 초기화되도록 수정
    console.log('[AIChatArea] 컴포넌트 마운트 - 초기 상태로 초기화');
    
    // 리액트 상태 초기화
    setInputCentered(true);
    setAllMessages([]);
    setChatSession(null);
    setSelectedStock(null);
    setSearchTerm('');
    
    // Zustand 스토어 상태도 초기화
    setStoreSession(null);
    clearMessages();
    
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
        
        // 함수형 업데이트를 사용하여 최신 상태 참조
        setInputCentered(true);
        setAllMessages([]);
        setChatSession(null);
        setSelectedStock(null);
        setSearchTerm('');
        
        console.log('[AIChatArea] 모든 상태 초기화 완료');
      } catch (error) {
        console.error('[AIChatArea] 홈버튼 클릭 이벤트 처리 중 오류:', error);
      }
    };
    
    // 이벤트 리스너 등록 - document에도 등록 시도
    console.log('[AIChatArea] homeButtonClick 이벤트 리스너 등록');
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
  }, []); // 의존성 배열에서 storeMessages.length 제거, 마운트 시 한 번만 실행

  // 창 너비 상태 추가
  const [windowWidth, setWindowWidth] = useState<number>(1024); // 기본값 설정

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
    // ref를 사용하여 즉시 전송 상태 확인
    if (isSendingRef.current || state.isProcessing) {
      console.log('[AIChatAreaContent] 이미 메시지 전송 중입니다.');
      return;
    }

    console.log(`[AIChatAreaContent] 메시지 전송 요청 : ${stockState.searchTerm.trim()}`);

    // 선택된 종목과 입력 메시지 확인
    if ((!state.selectedStock && !state.currentChatSession) || !stockState.searchTerm.trim()) {
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
      const currentStock = state.selectedStock;
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
      console.log('[AIChatAreaContent] 이벤트 발생: showToggleButton');
      
      // 세션 정보 및 종목 정보 준비
      const sessionId = state.currentChatSession?.id || '';
      const stockName = currentStock?.stockName || state.currentChatSession?.stock_name || '';
      const stockCode = currentStock?.stockCode || state.currentChatSession?.stock_code || '';
      
      // 메시지 ID 생성 (UUID 사용)
      const userMessageId = `user-${Date.now()}-${Math.random().toString(36).substring(2, 9)}`;
      console.log('[AIChatAreaContent] 생성된 사용자 메시지 ID:', userMessageId);
      
      // ChatContext에 사용자 메시지 직접 추가 (동기화 보장)
      const userMessageObj: ChatMessage = {
        id: userMessageId,
        role: 'user',
        content: currentMessage,
        timestamp: Date.now(),
        stockInfo: (stockName && stockCode) ? {
          stockName,
          stockCode
        } : undefined
      };
      
      // ChatContext에 사용자 메시지 추가
      addMessage(userMessageObj);
      console.log('[AIChatAreaContent] ChatContext에 사용자 메시지 추가됨:', userMessageId);
      
      // ChatStore에도 직접 사용자 메시지 추가
      const chatStore = useChatStore.getState();
      chatStore.addMessage({
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
          stockInfo: userMessageObj.stockInfo
        }
      });
      console.log('[AIChatAreaContent] ChatStore에 사용자 메시지 추가됨:', userMessageId);
      
      // useMessageProcessing 훅의 sendMessage 함수 호출 - 이제는 상태 메시지 생성만 담당
      await sendMessage(
        currentMessage,
        currentStock || null, // 종목이 선택되지 않아도 null로 전달
        currentRecentStocks,
        state.currentChatSession !== null // 현재 세션이 있으면 후속질문으로 간주
      );
      
      // 기존 로그 대신 사용자 메시지 추적 로그 추가
      console.log('[AIChatAreaContent] 메시지 전송 중 - chatStore 메시지 수:', useChatStore.getState().messages.length);
      console.log('[AIChatAreaContent] 메시지 전송 중 - ChatContext 메시지 수:', state.messages.length);
      
      // 세션이 없는 경우에는 종목 선택 초기화
      if (!state.currentChatSession) {
        setSelectedStock(null);
      } else {
        console.log('[AIChatAreaContent] 세션 있음 - 종목 선택 유지');
      }
      
      // 세션 상태에 관계없이 종목 선택 초기화
      // 후속 질문 모드에서는 종목 선택이 필요 없음
      setSelectedStock(null);
      console.log('[AIChatAreaContent] 메시지 전송 후 종목 선택 초기화');
      
      setSearchMode(false);
      
      // 종목이 선택된 경우에만 최근 종목에 추가
      if (currentStock) {
        addRecentStock(currentStock);
      }
      
      // 채팅 메시지 전송 이벤트 발생 - 채팅 세션 갱신을 위한 이벤트
      const chatMessageSentEvent = new CustomEvent('chatMessageSent');
      window.dispatchEvent(chatMessageSentEvent);
      
      console.log('[AIChatAreaContent] 메시지 전송 완료');
      
      // 전송 플래그 리셋 (AI 응답이 완료된 후)
      setTimeout(() => {
        setIsUserSending(false);
        isSendingRef.current = false;
      }, 1000);
    } catch (error) {
      console.error('[AIChatAreaContent] 메시지 전송 중 오류 발생:', error);
      setIsUserSending(false);
      isSendingRef.current = false;
    }
  };

  // 종목 선택 핸들러
  const handleSelectStock = (stock: StockOption | null) => {
    if (stock) {
      addRecentStock(stock);
      // ChatContext에 선택된 종목 업데이트
      setSelectedStock(stock);
    } else {
      // stock이 null인 경우(종목 선택 해제) 처리
      setSelectedStock(null);
    }
  };

  // 질문 선택 핸들러
  const handleSelectQuestion = (stock: StockOption, question: string) => {
    // StockContext와 ChatContext에 모두 상태 업데이트
    handleSelectStock(stock);
    
    // 질문을 입력창에 설정
    setSearchTerm(question);
    
    // 종목 제안 팝업 닫기
    showSuggestions(false);
  };

  // 업데이트 선택 핸들러
  const handleSelectUpdate = (stock: StockOption, updateInfo: string) => {
    // StockContext와 ChatContext에 모두 상태 업데이트
    handleSelectStock(stock);
    
    // 업데이트 정보를 입력창에 설정
    setSearchTerm(updateInfo);
    
    // 종목 제안 팝업 닫기
    showSuggestions(false);
  };

  // 채팅 컨텐츠 렌더링
  const renderChatContent = () => (
    <>
      {/* 메시지 목록 영역 */}
      {!state.isInputCentered && state.messages.length > 0 && (
        <MessageList
          ref={messageListRef}
          messages={state.messages}
          copyStates={state.copyStates}
          expertMode={state.expertMode}
          timerState={{}}
          isInputCentered={state.isInputCentered}
          isUserSending={isUserSending}
          onCopy={(id) => setCopyState(id, true)}
          onToggleExpertMode={toggleExpertMode}
        />
      )}

      {/* 입력 영역 (상단 중앙 또는 하단에 위치) */}
      {/* 후속 질문 일단 차단.*/}
      {!state.currentChatSession && (
        <InputArea
          inputMessage={stockState.searchTerm || ''}
          setInputMessage={setSearchTerm}
          selectedStock={state.selectedStock}
          isProcessing={state.isProcessing}
          isInputCentered={state.isInputCentered}
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
          showTitle={state.showTitle}
          currentChatSession={state.currentChatSession}
        />
      )}
      
      {/* 추천 질문 및 최신 업데이트 종목 영역 - 첫 진입 시 */}
      {state.isInputCentered && state.messages.length === 0 && (
        <div style={{
          width: isMobile ? '100%' : 'min(85%, 1000px)',
          minWidth: isMobile ? 'unset' : '280px',
          maxWidth: '1000px',
          margin: isMobile ? '50px auto 0' : '12px auto 0',
          padding: isMobile ? '0 0' : '0',
          display: 'flex',
          flexDirection: 'column',
          gap: '8px'
        }}>
          {/* 데스크탑: 중앙정렬, 모바일: 기존 중앙정렬 유지 */}
          <div
            style={{
              display: 'flex',
              flexDirection: isMobile ? 'column' : 'row',
              gap: isMobile ? '6px' : '8px',
              width: '100%',
              justifyContent: isMobile ? 'center' : 'center', // 항상 중앙정렬
              alignItems: isMobile ? 'center' : 'flex-start', // 데스크탑은 위에서부터 시작
            }}
          >
          {/* 추천 질문 컴포넌트 */}
          <RecommendedQuestions 
            questions={sampleRecommendedQuestions}
            onSelectQuestion={handleSelectQuestion}
          />
          
          {/* 최신 업데이트 종목 컴포넌트 */}
          <LatestUpdates 
            updates={sampleLatestUpdates}
            onSelectUpdate={handleSelectUpdate}
          />
        </div>
      </div>
    )}
    
    {/* 종목 제안 영역 */}
    <StockSuggestions
      isLoading={stockState.isLoading}
      error={stockState.error}
      filteredStocks={stockState.filteredStocks}
      recentStocks={stockState.recentStocks}
      stockOptions={stockState.stockOptions}
      onSelectStock={(stock) => handleSelectStock(stock)}
      onClearRecentStocks={clearRecentStocks}
      isInputCentered={state.isInputCentered}
    />
  </>
);

  // 컴포넌트 마운트 시 종목 데이터 로드 (빈 의존성 배열로 최초 1회만 실행)
  useEffect(() => {
    // 로컬 상태 변수로 이미 실행 여부 확인
    let isFirstLoad = true;

    if (isFirstLoad) {
      console.log('[AIChatAreaContent] 컴포넌트 마운트 - 종목 데이터 로드 검사');
      const { stockOptions } = stockState;
      if (stockOptions.length === 0) {
        console.log('[AIChatAreaContent] 종목 데이터 없음 - 로드 시작');
        fetchStockList();
      } else {
        console.log('[AIChatAreaContent] 종목 데이터 이미 로드됨 (', stockOptions.length, '개)');
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
          
          // 리액트 상태 초기화
          setInputCentered(true);
          setAllMessages([]);
          setChatSession(null);
          setSelectedStock(null);
          setSearchTerm('');
          
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
        console.log('[AIChatArea] homeButtonClick 이벤트 캡처');
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
    setAllMessages, 
    setChatSession, 
    setSelectedStock, 
    setSearchTerm, 
    setStoreSession, 
    clearMessages
  ]);

  // 활성 세션이 있을 때 종목 선택 초기화
  useEffect(() => {
    if (state.currentChatSession) {
      console.log('[AIChatAreaContent] 활성 세션 감지 - 종목 선택 초기화');
      setSelectedStock(null);
    }
  }, [state.currentChatSession, setSelectedStock]);

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
    <ChatProvider>
      <StockSelectorProvider>
        <AIChatAreaContent />
      </StockSelectorProvider>
    </ChatProvider>
  );
}
