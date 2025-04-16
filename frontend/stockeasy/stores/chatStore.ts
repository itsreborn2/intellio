import { create } from 'zustand'
import { IChatMessageDetail, IChatSession, IChatMessage } from '@/types/api/chat'

interface ChatState {
  // 현재 채팅 세션 상태
  currentSession: IChatSession | null
  // 현재 채팅 세션의 메시지들
  messages: IChatMessageDetail[]
  // 메시지 로딩 상태
  isLoading: boolean
  
  // 액션들
  setCurrentSession: (session: IChatSession | null) => void
  setMessages: (messages: IChatMessageDetail[]) => void
  addMessage: (message: IChatMessageDetail) => void
  clearMessages: () => void
  setIsLoading: (isLoading: boolean) => void
  
  // 채팅 세션 로드 함수
  loadChatSession: (sessionId: string, title: string, messages: IChatMessageDetail[]) => void
}

// 채팅 스토어 생성
export const useChatStore = create<ChatState>((set) => ({
  // 초기 상태
  currentSession: null,
  messages: [],
  isLoading: false,
  
  // 세션 설정
  setCurrentSession: (session) => set({ currentSession: session }),
  
  // 메시지 설정
  setMessages: (messages) => {
    console.log('[채팅 스토어] 메시지 목록 설정:', messages.length, '개');
    set({ messages });
  },
  
  // 메시지 추가
  addMessage: (message) => {
    console.log('[채팅 스토어] 새 메시지 추가:', message.role, message.id);
    set((state) => ({ 
      messages: [...state.messages, message] 
    }));
  },
  
  // 메시지 초기화
  clearMessages: () => set({ messages: [] }),
  
  // 로딩 상태 설정
  setIsLoading: (isLoading) => set({ isLoading }),
  
  // 채팅 세션 로드 함수
  loadChatSession: (sessionId, title, messages) => {
    console.log('[채팅 스토어] 채팅 세션 로드 시작:', sessionId, title)
    console.log('[채팅 스토어] 메시지 수:', messages.length)
    
    // 세션 제목에서 종목 정보 추출 (예: "삼성전자(005930) : 질문내용")
    const titleRegex = /^(.+?)\(([A-Za-z0-9]+)\)(?:\s*:\s*(.+))?$/
    let titleMatch = null
    if (title) {
      titleMatch = title.match(titleRegex)
    }
    
    // 종목 정보 초기화
    let stockName = ''
    let stockCode = ''
    
    // 정규식 매칭 결과가 있으면 종목 정보 추출
    if (titleMatch && titleMatch.length >= 3) {
      stockName = titleMatch[1].trim()
      stockCode = titleMatch[2].trim()
      console.log('[채팅 스토어] 세션 제목에서 종목 정보 추출:', stockName, stockCode)
    }
    
    // 메시지에서 종목 정보 찾기
    if (messages.length > 0) {
      for (const message of messages) {
        //console.log('[채팅 스토어] 메시지 검사:', message)
        
        // 메시지 직접 속성에서 종목 정보 확인
        if (message.stock_name && message.stock_code) {
          stockName = message.stock_name
          stockCode = message.stock_code
          //console.log('[채팅 스토어] 메시지 직접 속성에서 종목 정보 추출:', stockName, stockCode)
          break
        }
        
        // 메시지 메타데이터에서 종목 정보 확인
        if (message.metadata) {
          const metaStockName = message.metadata.stock_name
          const metaStockCode = message.metadata.stock_code
          
          if (metaStockName && metaStockCode) {
            stockName = metaStockName
            stockCode = metaStockCode
            //console.log('[채팅 스토어] 메시지 메타데이터에서 종목 정보 추출:', stockName, stockCode)
            break
          }
        }
      }
    }
    
    console.log('[채팅 스토어] 최종 추출된 종목 정보:', stockName, stockCode)
    
    // 종목 정보가 포함된 메시지 생성
    const enhancedMessages = messages.map(msg => {
      // 새 객체 생성 (원본 메시지 유지)
      const newMsg = { ...msg }
      
      // 메타데이터가 없는 경우 초기화
      if (!newMsg.metadata) {
        newMsg.metadata = {}
      }
      
      // 종목 정보가 있는 경우에만 추가
      if (stockName && stockCode) {
        // 메타데이터에 종목 정보 추가
        newMsg.metadata.stock_name = newMsg.metadata.stock_name || stockName
        newMsg.metadata.stock_code = newMsg.metadata.stock_code || stockCode
        
        // 직접 속성으로 종목 정보 추가
        newMsg.stock_name = newMsg.stock_name || stockName
        newMsg.stock_code = newMsg.stock_code || stockCode
      }
      
      return newMsg
    })
    
    // 세션 정보와 종목 정보 설정
    set({
      currentSession: {
        id: sessionId,
        title,
        is_active: true,
        user_id: '',
        ok: true,
        status_message: '',
        stock_name: stockName, // 종목명 설정
        stock_code: stockCode  // 종목코드 설정
      },
      messages: enhancedMessages,
      isLoading: false
    })
    
    console.log('[채팅 스토어] 채팅 세션 로드 완료')
  }
})) 