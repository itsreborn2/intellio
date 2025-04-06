'use client'

import { useState, useEffect, useRef } from 'react'
import { IChatSession } from '@/types/api/chat'
import { useChatStore } from '@/stores/chatStore'
import MessageList from './MessageList'
import ChatInput from './ChatInput'
import SuggestedQuestions from './SuggestedQuestions'
import { StockOption, ChatMessage } from './types'
import Papa from 'papaparse'
import { createChatSession, createChatMessage } from '@/services/api/chat'
import { createChatAreaStyle, getMarkdownStyles } from './styles'

export default function AIChatArea() {
  // 상태 정의
  const [stockOptions, setStockOptions] = useState<StockOption[]>([])
  const [selectedStock, setSelectedStock] = useState<StockOption | null>(null)
  const [isLoading, setIsLoading] = useState<boolean>(false)
  const [inputMessage, setInputMessage] = useState<string>('')
  const [isMounted, setIsMounted] = useState<boolean>(false)
  const [error, setError] = useState<string | null>(null)
  const [filteredStocks, setFilteredStocks] = useState<StockOption[]>([])
  const [recentStocks, setRecentStocks] = useState<StockOption[]>([])
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [isProcessing, setIsProcessing] = useState<boolean>(false)
  const [elapsedTime, setElapsedTime] = useState<number>(0)
  const [isMobile, setIsMobile] = useState(false)
  const [isInputCentered, setIsInputCentered] = useState(true)
  const [showTitle, setShowTitle] = useState(true)
  const [transitionInProgress, setTransitionInProgress] = useState(false)
  const [searchMode, setSearchMode] = useState(false)
  const [showStockSuggestions, setShowStockSuggestions] = useState<boolean>(false)
  const [windowWidth, setWindowWidth] = useState(0)
  const [currentChatSession, setCurrentChatSession] = useState<IChatSession | null>(null)

  // ref 정의
  const timerRef = useRef<NodeJS.Timeout | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)
  const stockSuggestionsRef = useRef<HTMLDivElement>(null)

  // Zustand 스토어 사용
  const { currentSession, messages: storeMessages } = useChatStore()

  // 종목 리스트 로드
  useEffect(() => {
    if (!isMounted) return

    const fetchStockList = async () => {
      try {
        setIsLoading(true)
        setError(null)

        // 서버 캐시 CSV 파일 경로
        const csvFilePath = '/requestfile/stock-data/stock_1idvb5kio0d6dchvoywe7ovwr-ez1cbpb.csv'

        // 서버 캐시 파일 가져오기
        const response = await fetch(csvFilePath, { cache: 'no-store' })

        if (!response.ok) {
          throw new Error(`서버 캐시 파일 로드 오류: ${response.status}`)
        }

        // CSV 파일 내용 가져오기
        const csvContent = await response.text()

        // CSV 파싱
        const parsedData = Papa.parse(csvContent, {
          header: true,
          skipEmptyLines: true
        })

        // 중복 제거를 위한 Set 생성
        const uniqueStocks = new Set()

        // 종목 데이터 추출
        const stockData = parsedData.data
          .filter((row: any) => row.종목명 && row.종목코드)
          .filter((row: any) => {
            if (uniqueStocks.has(row.종목코드)) {
              return false
            }
            uniqueStocks.add(row.종목코드)
            return true
          })
          .map((row: any) => ({
            value: row.종목코드,
            label: `${row.종목명}(${row.종목코드})`,
            display: row.종목명,
            stockName: row.종목명,
            stockCode: row.종목코드
          }))

        if (stockData.length > 0) {
          setStockOptions(stockData)
          setIsLoading(false)
        } else {
          const errorMsg = '유효한 종목 데이터를 받지 못했습니다.'
          setError(errorMsg)
          setIsLoading(false)
        }
      } catch (error) {
        const errorMsg = error instanceof Error 
          ? error.message 
          : '종목 리스트를 가져오는 중 오류가 발생했습니다.'
        setError(errorMsg)
        setIsLoading(false)
      }
    }

    fetchStockList()
  }, [isMounted])

  // 최근 조회 종목 로드
  useEffect(() => {
    if (!isMounted) return
    
    try {
      const savedRecentStocks = localStorage.getItem('recentStocks')
      if (savedRecentStocks) {
        setRecentStocks(JSON.parse(savedRecentStocks))
      }
    } catch (error) {
      console.error('Failed to load recent stocks from localStorage:', error)
    }
  }, [isMounted])

  // 클라이언트 사이드 렌더링 확인
  useEffect(() => {
    // 컴포넌트가 마운트되었음을 설정
    setIsMounted(true)
    
    // 현재 창 너비 설정
    setWindowWidth(window.innerWidth)
    setIsMobile(window.innerWidth <= 640)
    
    // 초기화
    setCurrentChatSession(null)
    
    // 외부 클릭 이벤트 리스너 추가
    const handleClickOutside = (event: MouseEvent) => {
      if (
        stockSuggestionsRef.current && 
        !stockSuggestionsRef.current.contains(event.target as Node) &&
        inputRef.current && 
        !inputRef.current.contains(event.target as Node)
      ) {
        setShowStockSuggestions(false)
      }
    }
    
    // 화면 크기 변경 감지
    const handleResize = () => {
      const width = window.innerWidth
      setWindowWidth(width)
      setIsMobile(width <= 640)
    }
    
    // 홈 버튼 클릭 이벤트 리스너 추가 (페이지 초기화용)
    const handleHomeButtonClick = () => {
      resetChatArea()
    }
    
    // 이벤트 리스너 설정
    document.addEventListener('mousedown', handleClickOutside)
    window.addEventListener('resize', handleResize)
    window.addEventListener('homeButtonClick' as any, handleHomeButtonClick)
    
    // 컴포넌트 언마운트 시 이벤트 리스너 및 타이머 제거
    return () => {
      document.removeEventListener('mousedown', handleClickOutside)
      window.removeEventListener('resize', handleResize)
      window.removeEventListener('homeButtonClick' as any, handleHomeButtonClick)
      
      if (timerRef.current) {
        clearInterval(timerRef.current)
        timerRef.current = null
      }
    }
  }, [])

  // Zustand 스토어에서 메시지 로드
  useEffect(() => {
    if (currentSession && storeMessages.length > 0) {
      // 채팅 세션이 있을 경우, 화면 레이아웃을 메시지 모드로 변경
      setIsInputCentered(false)
      setShowTitle(false)
      
      // 현재 세션의 종목 정보 설정
      const stockName = currentSession.stock_name || ''
      const stockCode = currentSession.stock_code || ''
      
      // 스토어의 메시지를 컴포넌트 형식으로 변환
      const convertedMessages: ChatMessage[] = storeMessages.map(msg => {
        // 메시지 자체 또는 메타데이터에서 종목 정보 추출
        let msgStockName = msg.stock_name || stockName;
        let msgStockCode = msg.stock_code || stockCode;
        
        return {
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

  // 메시지 추가 시 중앙 배치 해제
  useEffect(() => {
    if (messages.length > 0 && isInputCentered) {
      setIsInputCentered(false)
    }
  }, [messages, isInputCentered])

  // 입력 필드 위치 전환 상태 관리
  useEffect(() => {
    if (!isInputCentered) {
      setTransitionInProgress(true)
      setTimeout(() => {
        setTransitionInProgress(false)
      }, 400) // transition duration + 약간의 여유
    }
  }, [isInputCentered])

  // 채팅 영역 초기화 함수
  const resetChatArea = () => {
    setSelectedStock(null)
    setInputMessage('')
    setMessages([])
    setIsProcessing(false)
    setElapsedTime(0)
    setIsInputCentered(true)
    setShowTitle(true)
    setSearchMode(false)
    setShowStockSuggestions(false)
    setTransitionInProgress(false)
    setFilteredStocks([])
    setCurrentChatSession(null)
  }

  // 종목 선택 처리
  const handleStockSelect = (stock: StockOption) => {
    // 종목 선택 팝업 닫기
    setShowStockSuggestions(false)
    
    // 종목 검색 모드 종료
    setSearchMode(false)
    
    // 선택된 종목 설정
    setSelectedStock(stock)
    setInputMessage('') // 입력 필드 초기화
    
    // 중앙 배치 해제
    if (isInputCentered) {
      setIsInputCentered(false)
      setTransitionInProgress(true)
    }
    
    // 선택한 종목을 최근 조회 목록에 추가
    const updatedRecentStocks = [stock, ...recentStocks.filter(s => s.value !== stock.value)].slice(0, 5)
    setRecentStocks(updatedRecentStocks)
    
    // 로컬 스토리지에 최근 조회 종목 저장
    try {
      localStorage.setItem('recentStocks', JSON.stringify(updatedRecentStocks))
    } catch (error) {
      console.error('Failed to save recent stocks to localStorage:', error)
    }
    
    // 입력 필드에 포커스
    setTimeout(() => {
      if (inputRef.current) {
        inputRef.current.focus()
      }
    }, 100)
  }

  // 메시지 전송 처리
  const handleSendMessage = async () => {
    if (isProcessing || !selectedStock || !inputMessage.trim()) return

    // 중앙 배치 해제
    if (isInputCentered) {
      setIsInputCentered(false)
      setTransitionInProgress(true)
    }

    // 메시지 ID 생성
    const messageId = `msg_${Date.now()}`
    const responseId = `response_${Date.now()}`

    // 사용자 메시지 생성
    const userMessage: ChatMessage = {
      id: messageId,
      role: 'user',
      content: inputMessage,
      timestamp: Date.now(),
      stockInfo: selectedStock ? {
        stockName: selectedStock.stockName,
        stockCode: selectedStock.stockCode
      } : undefined,
      responseId
    }

    // 메시지 목록에 사용자 메시지 추가
    setMessages(prevMessages => [...prevMessages, userMessage])

    // 입력 필드 초기화
    setInputMessage('')

    // 메시지 처리 중 상태로 변경
    setIsProcessing(true)
    setElapsedTime(0)

    // 타이머 시작
    if (timerRef.current) {
      clearInterval(timerRef.current)
    }

    timerRef.current = setInterval(() => {
      setElapsedTime(prev => prev + 1)
    }, 1000)

    try {
      // 채팅 세션 ID가 없으면 새로 생성
      let sessionId = currentChatSession?.id
      if (!sessionId) {
        try {
          // 새 채팅 세션 생성
          const sessionTitle = selectedStock?.stockName 
            ? `${selectedStock.stockName}(${selectedStock.stockCode}) : ${inputMessage}` 
            : inputMessage
          const newSession = await createChatSession(sessionTitle)
          setCurrentChatSession(newSession)
          sessionId = newSession.id
        } catch (sessionError) {
          console.error('채팅 세션 생성 오류:', sessionError)
          return
        }
      }

      // 사용자 메시지 저장 (백엔드에 직접 저장)
      const response = await createChatMessage(
        sessionId,  
        inputMessage,
        selectedStock?.stockCode || '',
        selectedStock?.stockName || ''
      )

      if (!response.ok) {
        throw new Error(`API 응답 오류: ${response.status_message}`)
      }

      // 응답 메시지 생성
      const assistantMessage: ChatMessage = {
        id: `assistant-${Date.now()}`,
        role: 'assistant', 
        content: response.content || '죄송합니다. 응답을 생성하는 중 오류가 발생했습니다.',
        timestamp: Date.now(),
        stockInfo: selectedStock ? {
          stockName: selectedStock.stockName,
          stockCode: selectedStock.stockCode
        } : undefined,
        responseId
      }

      // 메시지 목록에 응답 메시지 추가
      setMessages(prevMessages => [...prevMessages, assistantMessage])
      
    } catch (error) {
      console.error('메시지 전송 오류:', error)

      // 오류 메시지 생성
      const errorMessage: ChatMessage = {
        id: `error-${Date.now()}`,
        role: 'assistant',
        content: '죄송합니다. 서버와 통신 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.',
        timestamp: Date.now()
      }

      // 메시지 목록에 오류 메시지 추가
      setMessages(prevMessages => [...prevMessages, errorMessage])
    } finally {
      // 메시지 처리 완료 상태로 변경
      setIsProcessing(false)

      // 타이머 중지
      if (timerRef.current) {
        clearInterval(timerRef.current)
        timerRef.current = null
      }
    }
  }

  // 입력 필드 포커스 시 종목 추천 목록 표시
  const handleInputFocus = () => {
    // 종목이 선택되어 있지 않은 경우, 최근 종목 목록 및 기본 종목 추천 표시
    if (!selectedStock) {
      // 최근 조회 종목이 있으면 표시
      if (recentStocks.length > 0) {
        setFilteredStocks(recentStocks)
      } else {
        // 최근 조회 종목이 없으면 기본 종목 추천 표시 (상위 5개)
        setFilteredStocks(stockOptions.slice(0, 5))
      }
      // 팝업 표시
      setShowStockSuggestions(true)
    }
  }

  // 입력 필드에 텍스트 입력 시 처리
  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    const value = e.target.value
    setInputMessage(value)
    
    // 종목 선택 팝업이 열려 있으면 종목 검색 모드로 동작
    if (showStockSuggestions) {
      setSearchMode(true)
      // 종목 검색 로직
      const searchValue = value.trim()
      if (searchValue.length > 0) {
        const filtered = stockOptions.filter(stock => {
          const stockName = stock.stockName || stock.display || stock.label || ''
          const stockCode = stock.value || ''
          return stockName.toLowerCase().includes(searchValue.toLowerCase()) || 
                stockCode.includes(searchValue)
        }).slice(0, 10)
        
        setFilteredStocks(filtered)
      } else {
        // 입력값이 없으면 최근 조회 종목 표시
        if (recentStocks.length > 0) {
          setFilteredStocks(recentStocks)
        } else {
          setFilteredStocks(stockOptions.slice(0, 5))
        }
      }
    }
  }

  return (
    <div className="ai-chat-area" style={createChatAreaStyle(isMobile)}>
      {/* 마크다운 스타일 */}
      <style jsx global>{`${getMarkdownStyles(isMobile, windowWidth)}`}</style>
      
      {/* 메시지 목록 */}
      {!isInputCentered && (
        <MessageList
          messages={messages}
          isProcessing={isProcessing}
          elapsedTime={elapsedTime}
          isMobile={isMobile}
          windowWidth={windowWidth}
        />
      )}
      
      {/* 입력 영역 */}
      <ChatInput
        selectedStock={selectedStock}
        inputMessage={inputMessage}
        onInputChange={handleInputChange}
        onSendMessage={handleSendMessage}
        onStockSelect={handleStockSelect}
        isInputCentered={isInputCentered}
        showTitle={showTitle}
        isMobile={isMobile}
        windowWidth={windowWidth}
        showStockSuggestions={showStockSuggestions}
        setShowStockSuggestions={setShowStockSuggestions}
        stockOptions={stockOptions}
        filteredStocks={filteredStocks}
        recentStocks={recentStocks}
        searchMode={searchMode}
        setSearchMode={setSearchMode}
        isLoading={isLoading}
        error={error}
        inputRef={inputRef}
        stockSuggestionsRef={stockSuggestionsRef}
        handleInputFocus={handleInputFocus}
      />
      
      {/* 추천 질문 영역 (중앙 배치일 때만 표시) */}
      {isInputCentered && messages.length === 0 && (
        <SuggestedQuestions
          onStockSelect={handleStockSelect}
          setInputMessage={setInputMessage}
          recentStocks={recentStocks}
          setRecentStocks={setRecentStocks}
          isMobile={isMobile}
          windowWidth={windowWidth}
        />
      )}
    </div>
  )
} 