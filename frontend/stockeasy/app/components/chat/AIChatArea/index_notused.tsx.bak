'use client'

import React, { Suspense, useState, useEffect, useCallback, useMemo } from 'react'
import { toast } from 'sonner'
import { useChatStore } from '@/stores/chatStore'
import { useTokenUsageStore } from '@/stores/tokenUsageStore'
import { useQuestionCountStore } from '@/stores/questionCountStore'
import { IChatSession } from '@/types/api/chat'
import { createChatSession, streamChatMessage } from '@/services/api/chat'

// 내부 컴포넌트, 컨텍스트, 훅, 유틸리티 임포트
import { ChatProvider, StockSelectorProvider } from './context'
import { ChatLayout, InputCenteredLayout, MobileChatLayout } from './layouts'
import { 
  MessageList, 
  InputArea, 
  RecommendedQuestions, 
  LatestUpdates 
} from './components'
import { useIsMobile, useStockSearch, useTimers } from './hooks'
import { StockOption, ChatMessage } from './types'
import { formatTimestamp } from './utils/messageFormatters'
import { loadStockOptionsFromCSV, saveRecentStocksToStorage } from './utils/stockDataUtils'
import { getMarkdownStyles } from './utils/styleUtils'

// 추천 질문 데이터
const RECOMMENDED_QUESTIONS = [
  {
    stock: { 
      value: '005930', 
      label: '삼성전자(005930)', 
      stockName: '삼성전자',
      stockCode: '005930',
      display: '삼성전자'
    },
    question: '최근 HBM 개발 상황 및 경쟁사와의 비교'
  },
  {
    stock: { 
      value: '000660', 
      label: 'SK하이닉스(000660)', 
      stockName: 'SK하이닉스',
      stockCode: '000660',
      display: 'SK하이닉스'
    },
    question: 'AI 반도체 시장 진출 전략과 향후 전망'
  },
  {
    stock: { 
      value: '005380', 
      label: '현대차(005380)', 
      stockName: '현대차',
      stockCode: '005380',
      display: '현대차'
    },
    question: '전기차 시장에서의 경쟁력과 최근 실적 분석'
  },
  {
    stock: { 
      value: '373220', 
      label: 'LG에너지솔루션(373220)', 
      stockName: 'LG에너지솔루션',
      stockCode: '373220',
      display: 'LG에너지솔루션'
    },
    question: '배터리 기술 개발 현황 및 미래 전망 분석'
  }
];

// 최신 업데이트 종목 데이터
const LATEST_UPDATES = [
  {
    stock: { 
      value: '373220', 
      label: 'LG에너지솔루션(373220)', 
      stockName: 'LG에너지솔루션',
      stockCode: '373220',
      display: 'LG에너지솔루션'
    },
    updateInfo: '배터리 생산량 1분기 32% 증가, 전기차 시장 확대로 실적 개선 전망'
  },
  {
    stock: { 
      value: '035720', 
      label: '카카오(035720)', 
      stockName: '카카오',
      stockCode: '035720',
      display: '카카오'
    },
    updateInfo: 'AI 기술 투자 현황과 미래 사업 전략'
  }
];

// AIChatArea 메인 컴포넌트 내용
function AIChatAreaContent() {
  // 상태 관리
  const [isMounted, setIsMounted] = useState<boolean>(false)
  const [selectedStock, setSelectedStock] = useState<StockOption | null>(null)
  const [inputMessage, setInputMessage] = useState<string>('')
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [isProcessing, setIsProcessing] = useState<boolean>(false)
  const [isInputCentered, setIsInputCentered] = useState(true)
  const [showTitle, setShowTitle] = useState(true)
  const [currentChatSession, setCurrentChatSession] = useState<IChatSession | null>(null)
  const [error, setError] = useState<string | null>(null)
  
  // 메시지 상태 관리
  const [copyStates, setCopyStates] = useState<Record<string, boolean>>({})
  const [expertMode, setExpertMode] = useState<Record<string, boolean>>({})
  const [timerState, setTimerState] = useState<Record<string, number>>({})

  // 커스텀 훅 사용
  const isMobile = useIsMobile()
  const { elapsedTime, startTimer, stopTimer } = useTimers()
  const { 
    stockOptions, 
    isLoading: isStockLoading, 
    error: stockError,
    recentStocks
  } = useStockSearch()

  // Zustand 스토어
  const { currentSession, messages: storeMessages } = useChatStore()
  const { summary, fetchSummary } = useTokenUsageStore()
  const { summary: questionSummary, fetchSummary: fetchQuestionSummary } = useQuestionCountStore()

  // 종목 선택 업데이트 및 저장
  const updateRecentStocks = useCallback((stocks: StockOption[]) => {
    // 이 함수에서는 직접적으로 useStockSearch의 상태를 업데이트하지 않고,
    // 로컬 스토리지에만 저장합니다. 다음 로드 시 useStockSearch가 이를 읽어들입니다.
    saveRecentStocksToStorage(stocks)
  }, [])

  // 복사 상태 변경 핸들러
  const handleCopy = useCallback((id: string) => {
    setCopyStates(prev => ({
      ...prev,
      [id]: true
    }))
    
    // 2초 후 복사 상태 초기화
    setTimeout(() => {
      setCopyStates(prev => ({
        ...prev,
        [id]: false
      }))
    }, 2000)
  }, [])
  
  // 전문가 모드 토글 핸들러
  const handleToggleExpertMode = useCallback((id: string) => {
    setExpertMode(prev => ({
      ...prev,
      [id]: !prev[id]
    }))
  }, [])

  // 컴포넌트 마운트 시 초기화
  useEffect(() => {
    setIsMounted(true)
    
    // AIChatArea 컴포넌트가 마운트되었음을 알리는 이벤트 발생
    const mountEvent = new CustomEvent('aiChatAreaMounted', { detail: { isMounted: true } })
    window.dispatchEvent(mountEvent)
    
    // 컴포넌트 언마운트 시 cleanup 함수
    return () => {
      // 타이머 정리
      stopTimer()
      
      // AIChatArea 컴포넌트가 언마운트되었음을 알리는 이벤트 발생
      const unmountEvent = new CustomEvent('aiChatAreaUnmounted', { detail: { isMounted: false } })
      window.dispatchEvent(unmountEvent)
    }
  }, [])

  // Zustand 스토어에서 데이터를 가져와 상태 업데이트
  useEffect(() => {
    if (currentSession && storeMessages.length > 0) {
      // 레이아웃 설정 즉시 변경
      setIsInputCentered(false)
      setShowTitle(false)
      
      // 현재 세션의 종목 정보 설정
      const stockName = currentSession.stock_name || ''
      const stockCode = currentSession.stock_code || ''
      
      // 스토어의 메시지를 컴포넌트 형식으로 변환
      const convertedMessages: ChatMessage[] = storeMessages.map(msg => {
        // 메시지 자체 또는 메타데이터에서 종목 정보 추출
        let msgStockName = ''
        let msgStockCode = ''
        
        // 메시지 직접 속성에 있는지 확인
        if (msg.stock_name && msg.stock_code) {
          msgStockName = msg.stock_name
          msgStockCode = msg.stock_code
        } 
        // 세션 정보 사용
        else {
          msgStockName = stockName
          msgStockCode = stockCode
        }
        
        // 반환할 메시지 객체 생성
        return {
          id: msg.id,
          role: msg.role as 'user' | 'assistant' | 'status',
          content: msg.content,
          content_expert: msg.content_expert,
          timestamp: msg.created_at ? new Date(msg.created_at).getTime() : Date.now(),
          responseId: msg.metadata?.responseId,
          stockInfo: (msgStockName && msgStockCode) ? {
            stockName: msgStockName,
            stockCode: msgStockCode
          } : undefined,
          isProcessing: msg.metadata?.isProcessing,
          agent: msg.metadata?.agent,
          elapsed: msg.metadata?.elapsed
        }
      })
      
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
        }
        setSelectedStock(stockOption)
      }
      
      // 메시지 설정
      setMessages(convertedMessages)
    }
  }, [currentSession, storeMessages])

  // 히스토리 분석 결과 로드 이벤트 리스너
  useEffect(() => {
    const handleLoadHistoryAnalysis = (e: CustomEvent) => {
      const { stockName, stockCode, prompt, result, responseId } = e.detail
      
      // 선택된 종목 설정
      if (stockName && stockCode) {
        const stockOption: StockOption = {
          value: stockCode,
          label: `${stockName} (${stockCode})`,
          stockName,
          stockCode,
          display: `${stockName} (${stockCode})`
        }
        setSelectedStock(stockOption)
        
        // 최근 조회 종목에 추가
        const updatedRecentStocks = [stockOption, ...recentStocks.filter(s => s.value !== stockCode)].slice(0, 5)
        updateRecentStocks(updatedRecentStocks)
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
      }
      
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
      }
      
      // 메시지 설정 및 입력 필드 중앙 배치 해제
      setMessages([userMessage, assistantMessage])
      setIsInputCentered(false)
      setShowTitle(false)
      
      // 입력 필드 초기화
      setInputMessage('')
    }
    
    // 이벤트 리스너 등록
    window.addEventListener('loadHistoryAnalysis', handleLoadHistoryAnalysis as EventListener)
    
    return () => {
      window.removeEventListener('loadHistoryAnalysis', handleLoadHistoryAnalysis as EventListener)
    }
  }, [recentStocks, updateRecentStocks])

  // 채팅 영역 초기화 함수
  const resetChatArea = () => {
    // 상태 초기화
    setSelectedStock(null)
    setInputMessage('')
    setMessages([])
    setIsProcessing(false)
    setIsInputCentered(true)
    setShowTitle(true)
    setCurrentChatSession(null)
    stopTimer()
    
    console.log('채팅 영역이 초기화되었습니다.')
  }

  // 홈 버튼 클릭 이벤트 리스너 추가 (페이지 초기화용)
  useEffect(() => {
    const handleHomeButtonClick = () => {
      resetChatArea()
    }
    
    // 홈 버튼 클릭 이벤트 설정
    window.addEventListener('homeButtonClick' as any, handleHomeButtonClick)
    
    return () => {
      window.removeEventListener('homeButtonClick' as any, handleHomeButtonClick)
    }
  }, [])

  // 메시지 전송 처리
  const handleSendMessage = async () => {
    // 질문 개수 제한 체크
    if (questionSummary && questionSummary.total_questions >= 30) {
      // 할당량 초과 알림
      toast.error('오늘의 질문 할당량(30개)을 모두 소진하였습니다. 내일 다시 이용해주세요.')
      return
    }
    
    try {
      setIsProcessing(true)
      startTimer()
      
      // 사용자 메시지 추가
      const userMessageObj: ChatMessage = {
        id: `user-${Date.now()}`,
        role: 'user',
        content: inputMessage,
        timestamp: Date.now(),
        stockInfo: {
          stockName: selectedStock?.stockName || '',
          stockCode: selectedStock?.value || ''
        }
      }
      
      // 상태 표시 메시지 추가
      const statusMessageObj: ChatMessage = {
        id: `status-${Date.now()}`,
        role: 'status',
        content: '처리 중입니다...',
        timestamp: Date.now(),
        isProcessing: true,
        stockInfo: {
          stockName: selectedStock?.stockName || '',
          stockCode: selectedStock?.value || ''
        }
      }
      
      // 메시지 목록에 사용자 메시지와 처리 중 상태 메시지 추가
      setMessages((prevMessages) => [...prevMessages, userMessageObj, statusMessageObj])
      
      // 첫 메시지 전송 시 중앙 정렬 해제
      if (isInputCentered) {
        setIsInputCentered(false)
        setShowTitle(false)
      }
      
      // 채팅 세션이 없으면 생성
      let sessionId = currentChatSession?.id
      
      if (!sessionId) {
        try {
          // 종목명(종목코드) : 질문내용 으로 session_name 생성
          const stockName = selectedStock?.stockName || '종목명'
          const stockCode = selectedStock?.stockCode || '000000'
          const question = inputMessage || ''

          const session_name = `${stockName}(${stockCode}) : ${question}`
          const newSession = await createChatSession(session_name)
          sessionId = newSession.id
          setCurrentChatSession(newSession)
          console.log('새 채팅 세션 생성:', newSession)
        } catch (error) {
          console.error('채팅 세션 생성 실패:', error)
          throw error
        }
      }
      
      // 스트리밍 방식 API 호출
      await streamChatMessage(
        sessionId,
        inputMessage,
        selectedStock?.value || '',
        selectedStock?.stockName || '',
        {
          onStart: () => {
            console.log('[AIChatArea] 처리 시작')
            // 상태 메시지 업데이트
            setMessages((prevMessages) => 
              prevMessages.map((msg) => 
                msg.id === statusMessageObj.id 
                  ? { ...msg, content: '처리를 시작합니다...', elapsed: elapsedTime } 
                  : msg
              )
            )
          },
          onAgentStart: (data) => {
            console.log('[AIChatArea] 에이전트 시작:', data)
            // 상태 메시지 업데이트 (경과시간에 시작 시간 추가)
            setMessages((prevMessages) => 
              prevMessages.map((msg) => 
                msg.id === statusMessageObj.id 
                  ? { 
                      ...msg, 
                      content: data.message, 
                      agent: data.agent, 
                      elapsed: data.elapsed,
                      elapsedStartTime: Date.now() // 경과 시간 시작점 추가
                    } 
                  : msg
              )
            )
          },
          onAgentComplete: (data) => {
            console.log('[AIChatArea] 에이전트 완료:', data)
            // 상태 메시지 업데이트 (경과시간에 시작 시간 추가)
            setMessages((prevMessages) => 
              prevMessages.map((msg) => 
                msg.id === statusMessageObj.id 
                  ? { 
                      ...msg, 
                      content: data.message, 
                      agent: data.agent, 
                      elapsed: data.elapsed,
                      elapsedStartTime: Date.now() // 경과 시간 시작점 업데이트
                    } 
                  : msg
              )
            )
          },
          onComplete: (data) => {
            console.log('[AIChatArea] 처리 완료:', data)
            
            // 타이머 중지
            stopTimer()
            
            // 상태 메시지 제거
            setMessages((prevMessages) => 
              prevMessages.filter((msg) => msg.id !== statusMessageObj.id)
            )
            
            // 최종 응답 메시지 추가
            const assistantMessageObj: ChatMessage = {
              id: data.message_id || `ai-${Date.now()}`,
              role: 'assistant',
              content: data.response,
              content_expert: data.response_expert,
              timestamp: Date.now(),
              responseId: data.metadata?.responseId,
              elapsed: 0,
              stockInfo: {
                stockName: selectedStock?.stockName || '',
                stockCode: selectedStock?.value || ''
              }
            }
            
            setMessages((prevMessages) => [...prevMessages, assistantMessageObj])
            setIsProcessing(false)
            
            // 질문 개수 업데이트
            fetchQuestionSummary('day', 'day')
          },
          onError: (error) => {
            console.error('[AIChatArea] 스트리밍 오류:', error)
            
            // 타이머 중지
            stopTimer()
            
            // 상태 메시지를 오류 메시지로 변경
            setMessages((prevMessages) => 
              prevMessages.map((msg) => 
                msg.id === statusMessageObj.id 
                  ? { 
                      ...msg, 
                      content: `오류가 발생했습니다: ${error.message || '알 수 없는 오류'}`, 
                      isProcessing: false,
                      elapsedStartTime: undefined
                    } 
                  : msg
              )
            )
            
            setIsProcessing(false)
            setError(`메시지 처리 중 오류: ${error.message || '알 수 없는 오류'}`)
          }
        }
      )
      
      // 입력 필드 초기화
      setInputMessage('')
      
      // 최근 조회 종목에 추가
      if (selectedStock) {
        const updatedRecentStocks = [
          selectedStock,
          ...recentStocks.filter((s) => s.value !== selectedStock.value)
        ].slice(0, 5)
        
        updateRecentStocks(updatedRecentStocks)
      }
    } catch (error: any) {
      console.error('[AIChatArea] 메시지 전송 오류:', error)
      
      // 타이머 중지
      stopTimer()
      
      setIsProcessing(false)
      setError(`메시지 전송 실패: ${error.message || '알 수 없는 오류'}`)
    }
  }

  // 입력 핸들러
  const handleInputChange = (value: string) => {
    setInputMessage(value)
  }

  // 종목 선택 핸들러
  const handleStockSelect = (stock: StockOption | null) => {
    setSelectedStock(stock)
    
    // 최근 조회 종목에 추가
    if (stock) {
      const updatedRecentStocks = [
        stock,
        ...recentStocks.filter((s) => s.value !== stock.value)
      ].slice(0, 5)
      
      updateRecentStocks(updatedRecentStocks)
    }
  }

  // 마크다운 스타일을 메모이제이션
  const markdownStyles = useMemo(() => 
    getMarkdownStyles(isMobile, typeof window !== 'undefined' ? window.innerWidth : 1024), 
    [isMobile]
  );

  // 추천 질문 영역을 메모이제이션
  const recommendedQuestionsArea = useMemo(() => {
    if (isInputCentered && messages.length === 0) {
      return (
        <div style={{
          width: isMobile ? '100%' : '57.6%', 
          margin: isMobile ? '50px auto 0' : '12px auto 0',
          padding: isMobile ? '0 0' : '0',
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
            <RecommendedQuestions
              questions={RECOMMENDED_QUESTIONS}
              onSelectQuestion={(stock, question) => {
                setSelectedStock(stock);
                setInputMessage(question);
              }}
            />
            <LatestUpdates
              updates={LATEST_UPDATES}
              onSelectUpdate={(stock, question) => {
                setSelectedStock(stock);
                setInputMessage(question);
              }}
            />
          </div>
        </div>
      );
    }
    return null;
  }, [isInputCentered, messages.length, isMobile, setSelectedStock, setInputMessage]);

  // 입력 영역 props를 메모이제이션
  const inputAreaProps = useMemo(() => ({
    inputMessage,
    setInputMessage: handleInputChange,
    selectedStock,
    isProcessing,
    isInputCentered,
    showStockSuggestions: false,
    filteredStocks: [],
    recentStocks,
    searchMode: false,
    isLoading: isStockLoading,
    error,
    windowWidth: typeof window !== 'undefined' ? window.innerWidth : 1024,
    onSendMessage: handleSendMessage,
    onStockSelect: handleStockSelect,
    onShowStockSuggestions: () => {},
    onSearchModeChange: () => {},
    onClearRecentStocks: () => {},
    showTitle
  }), [
    inputMessage, 
    handleInputChange, 
    selectedStock, 
    isProcessing, 
    isInputCentered, 
    recentStocks, 
    isStockLoading, 
    error, 
    handleSendMessage, 
    handleStockSelect, 
    showTitle
  ]);

  // 메시지 목록 props를 메모이제이션
  const messageListProps = useMemo(() => ({
    messages,
    copyStates,
    expertMode,
    timerState,
    isInputCentered,
    onCopy: handleCopy,
    onToggleExpertMode: handleToggleExpertMode
  }), [
    messages, 
    copyStates, 
    expertMode, 
    timerState, 
    isInputCentered, 
    handleCopy, 
    handleToggleExpertMode
  ]);

  // 클라이언트 측에서 마운트될 때까지 렌더링하지 않음
  if (!isMounted) {
    return (
      <div className="ai-chat-area" style={{
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
        width: '100%',
        justifyContent: 'center',
        alignItems: 'center',
        backgroundColor: '#F4F4F4',
      }}>
        <div style={{ textAlign: 'center', color: '#666' }}>
          <div style={{ marginBottom: '10px' }}>로딩 중...</div>
        </div>
      </div>
    )
  }

  return (
    <div className="ai-chat-area" style={{
      display: 'flex',
      flexDirection: 'column',
      height: '100%',
      width: '100%',
      position: 'relative',
      backgroundColor: '#F4F4F4',
      overflow: 'hidden',
      paddingTop: isMobile ? '0' : '10px',
      paddingRight: isMobile ? '0' : '10px',
      paddingBottom: isMobile ? '0' : '10px',
      paddingLeft: isMobile ? '0' : '10px',
      opacity: 1,
      fontSize: isMobile ? '14px' : undefined,
    }}>
      {/* 마크다운 스타일 태그 추가 */}
      <style jsx>{markdownStyles}</style>
      
      {isInputCentered ? (
        // 초기 화면 (중앙 배치 입력 필드)
        <InputCenteredLayout>
          {/* 제목 표시 영역 */}
          {showTitle && (
            <div style={{
              textAlign: 'center',
              marginBottom: '20px',
              paddingTop: '0',
              paddingRight: '0',
              paddingBottom: '0',
              paddingLeft: '0',
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
                display: isMobile ? 'none' : 'block'
              }}>
                index - 종목을 선택 후 분석을 요청하세요.
              </h1>
            </div>
          )}
          
          {/* 입력 영역 */}
          <InputArea {...inputAreaProps} />
          
          {/* 추천 질문 및 최신 업데이트 종목 컴포넌트 */}
          {recommendedQuestionsArea}
        </InputCenteredLayout>
      ) : (
        // 채팅 진행 화면 - 모바일/데스크톱에 따라 다른 레이아웃 사용
        isMobile ? (
          // 모바일 레이아웃
          <MobileChatLayout>
            {/* 메시지 목록 */}
            <MessageList {...messageListProps} />
            
            {/* 입력 영역 */}
            <InputArea {...inputAreaProps} />
          </MobileChatLayout>
        ) : (
          // 데스크톱 레이아웃
          <ChatLayout>
            {/* 메시지 목록 */}
            <MessageList {...messageListProps} />
            
            {/* 입력 영역 */}
            <InputArea {...inputAreaProps} />
          </ChatLayout>
        )
      )}
      
      {/* 푸터 */}
      {!isMobile && (
        <div style={{
          position: 'fixed',
          bottom: 0,
          left: '59px',
          width: 'calc(100% - 59px)',
          textAlign: 'center',
          paddingTop: '5px',
          paddingBottom: '5px',
          height: 'auto',
          zIndex: 10,
          backgroundColor: 'rgba(244, 244, 244, 0.95)',
          fontSize: '13px',
          color: '#888',
          fontWeight: '300',
        }}>
          2025 Intellio Corporation All Rights Reserved.
        </div>
      )}
    </div>
  )
}

// React.memo를 적용하여 불필요한 리렌더링 방지
const MemoizedAIChatAreaContent = React.memo(AIChatAreaContent);

// 메인 컴포넌트 (컨텍스트 프로바이더 포함)
export default function AIChatArea() {
  return (
    <Suspense fallback={<div>Loading...</div>}>
      <ChatProvider>
        <StockSelectorProvider>
          <MemoizedAIChatAreaContent />
        </StockSelectorProvider>
      </ChatProvider>
    </Suspense>
  )
} 