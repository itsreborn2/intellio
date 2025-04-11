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
import { StockOption } from './types';

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
  
  // 상태 메시지 ID 참조 추가
  const statusMessageIdRef = useRef<string | null>(null);

  // Zustand 스토어 사용
  const { currentSession, messages: storeMessages } = useChatStore();
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
      setProcessing
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
      setAllMessages(convertedMessages);
      
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
        value: '373220', 
        label: '우진플라임', 
        stockName: '우진플라임', 
        stockCode: '373220' 
      },
      updateInfo: '발전소 수주 확대 소식'
    }
  ];

  // 마운트/언마운트 이벤트 핸들링
  useEffect(() => {
    console.log('[AIChatArea] 컴포넌트 마운트: 이벤트 리스너 설정');
    
    // AIChatArea 컴포넌트가 마운트되었음을 알리는 이벤트 발생
    const mountEvent = new CustomEvent('aiChatAreaMounted', { detail: { isMounted: true } });
    window.dispatchEvent(mountEvent);
    
    // homeButtonClick 이벤트 리스너 등록 - 한 번만 등록되도록 함
    const handleHomeButtonClick = () => {
      console.log('[AIChatArea] 홈버튼 클릭 이벤트 감지: AIChatArea 리셋');
      
      // 함수형 업데이트를 사용하여 최신 상태 참조
      setInputCentered(true);
      setAllMessages([]);
      setChatSession(null);
      setSelectedStock(null);
      setSearchTerm('');
    };
    
    // 이벤트 리스너 등록
    window.addEventListener('homeButtonClick', handleHomeButtonClick);
    
    // 컴포넌트 언마운트 시 cleanup 함수
    return () => {
      console.log('[AIChatArea] 컴포넌트 언마운트: 이벤트 리스너 제거');
      
      // AIChatArea 컴포넌트가 언마운트되었음을 알리는 이벤트 발생
      const unmountEvent = new CustomEvent('aiChatAreaUnmounted', { detail: { isMounted: false } });
      window.dispatchEvent(unmountEvent);
      
      // homeButtonClick 이벤트 리스너 제거
      window.removeEventListener('homeButtonClick', handleHomeButtonClick);
    };
  }, []); // 빈 의존성 배열: 컴포넌트 마운트/언마운트 시에만 실행

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
    console.log(`[AIChatAreaContent] 메시지 전송 요청 : ${stockState.searchTerm.trim()}`);

    // 선택된 종목과 입력 메시지 확인
    if (!state.selectedStock || !stockState.searchTerm.trim()) {
      console.error('종목이 선택되지 않았거나 메시지가 없습니다.');
      return;
    }
    
    try {
      // 사용자 메시지 전송 플래그 설정
      setIsUserSending(true);

      // 메세지 전송 요청할때, 젤 아래로 한번 내려주자.
      if (messageListRef.current?.scrollToBottom) {
        messageListRef.current.scrollToBottom();
        
        // 추가 안정성을 위해 약간의 지연 후 한 번 더 실행
        setTimeout(() => {
          messageListRef.current?.scrollToBottom && messageListRef.current.scrollToBottom();
        }, 100);
      }
      
      // useMessageProcessing 훅의 sendMessage 함수 호출
      await sendMessage(
        stockState.searchTerm,
        state.selectedStock,
        stockState.recentStocks
      );
      
      // 메시지 전송 후 입력창 초기화
      setSearchTerm('');
      
      // 최근 종목에 추가
      if (state.selectedStock) {
        addRecentStock(state.selectedStock);
      }
      

      
      console.log('[AIChatAreaContent] 메시지 전송 완료');

      
      // 전송 플래그 리셋 (AI 응답이 완료된 후)
      setTimeout(() => setIsUserSending(false), 1000);
    } catch (error) {
      console.error('[AIChatAreaContent] 메시지 전송 중 오류 발생:', error);
      setIsUserSending(false);
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
      />
      
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
          <div style={{
            display: 'flex',
            flexDirection: isMobile ? 'column' : 'row',
            gap: isMobile ? '6px' : '8px',
            width: '100%',
            justifyContent: 'center', // 중앙 정렬
            alignItems: 'stretch', // 컴포넌트 높이 맞춤
          }}>
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
  // window 객체에 디버깅 함수 추가 (개발용)
  useEffect(() => {
    if (typeof window !== 'undefined') {
      // @ts-ignore - 디버깅용 메서드 추가
      window.__debug_resetAIChatArea = () => {
        console.log('디버그: AIChatArea 리셋 시도');
        // 직접 이벤트 발생시켜 테스트
        const event = new CustomEvent('homeButtonClick', {
          bubbles: true,
          detail: { timestamp: Date.now(), source: 'debug' }
        });
        window.dispatchEvent(event);
      };
    }
    // 클린업
    return () => {
      if (typeof window !== 'undefined') {
        // @ts-ignore - 디버깅용 메서드 제거
        delete window.__debug_resetAIChatArea;
      }
    };
  }, []);

  return (
    <ChatProvider>
      <StockSelectorProvider>
        <AIChatAreaContent />
      </StockSelectorProvider>
    </ChatProvider>
  );
}
