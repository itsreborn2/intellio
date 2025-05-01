import { create } from 'zustand'
import { IChatMessageDetail, IChatSession, IChatMessage } from '@/types/api/chat'
import { StockOption } from '@/app/components/chat/AIChatArea/types/stock'
import { ChatMessage, MessageComponent } from '@/app/components/chat/AIChatArea/types/chat'

interface ChatState {
  // 현재 채팅 세션 상태
  currentSession: IChatSession | null
  // 현재 채팅 세션의 메시지들
  messages: IChatMessageDetail[]
  // 메시지 로딩 상태
  isLoading: boolean
  
  // ChatContext에서 가져온 추가 상태들
  selectedStock: StockOption | null
  isInputCentered: boolean
  showTitle: boolean
  copyStates: Record<string, boolean>
  expertMode: Record<string, boolean>
  elapsedTime: number
  
  // 액션들
  setCurrentSession: (session: IChatSession | null) => void
  setMessages: (messages: IChatMessageDetail[]) => void
  addMessage: (message: IChatMessageDetail) => void
  clearMessages: () => void
  setIsLoading: (isLoading: boolean) => void
  
  // ChatContext에서 가져온 추가 액션들
  updateMessage: (id: string, message: Partial<IChatMessageDetail>) => void
  removeMessage: (id: string) => void
  setSelectedStock: (stock: StockOption | null) => void
  setInputCentered: (isCentered: boolean) => void
  setShowTitle: (show: boolean) => void
  resetChat: () => void
  toggleExpertMode: (messageId: string) => void
  setCopyState: (id: string, state: boolean) => void
  setElapsedTime: (time: number) => void
  
  // 채팅 세션 로드 함수
  loadChatSession: (sessionId: string, title: string, messages: IChatMessageDetail[]) => void
  
  // 타입 변환 유틸리티
  convertToUiMessage: (message: IChatMessageDetail) => ChatMessage
  convertToApiMessage: (message: ChatMessage) => IChatMessageDetail
  getUiMessages: () => ChatMessage[]
}

// 채팅 스토어 생성
export const useChatStore = create<ChatState>((set, get) => ({
  // 초기 상태
  currentSession: null,
  messages: [],
  isLoading: false,
  
  // ChatContext에서 가져온 초기 상태
  selectedStock: null,
  isInputCentered: true,
  showTitle: true,
  copyStates: {},
  expertMode: {},
  elapsedTime: 0,
  
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
  
  // ChatContext에서 가져온 추가 액션들
  updateMessage: (id, messageUpdate) => {
    //console.log('[채팅 스토어] 메시지 업데이트:', id);
    set((state) => ({
      messages: state.messages.map(msg => 
        msg.id === id ? { ...msg, ...messageUpdate } : msg
      )
    }));
  },
  
  removeMessage: (id) => {
    console.log('[채팅 스토어] 메시지 제거:', id);
    set((state) => ({
      messages: state.messages.filter(msg => msg.id !== id)
    }));
  },
  
  setSelectedStock: (stock) => set({ selectedStock: stock }),
  
  setInputCentered: (isCentered) => set({ isInputCentered: isCentered }),
  
  setShowTitle: (show) => set({ showTitle: show }),
  
  resetChat: () => {
    const { copyStates, expertMode } = get();
    console.log('[채팅 스토어] 채팅 초기화');
    set({
      currentSession: null,
      messages: [],
      selectedStock: null,
      isInputCentered: true,
      showTitle: true,
      elapsedTime: 0,
      // 아래 항목들은 초기화하지 않음
      copyStates,
      expertMode
    });
  },
  
  toggleExpertMode: (messageId) => {
    // 기존 expertMode 객체 복사
    const currentExpertMode = { ...get().expertMode };
    // 토글 상태 업데이트
    currentExpertMode[messageId] = !currentExpertMode[messageId];
    // 상태 설정
    set({ expertMode: currentExpertMode });
  },
  
  setCopyState: (id, state) => {
    // 기존 copyStates 객체 복사
    const currentCopyStates = { ...get().copyStates };
    // 상태 업데이트
    currentCopyStates[id] = state;
    // 상태 설정
    set({ copyStates: currentCopyStates });
  },
  
  setElapsedTime: (time) => set({ elapsedTime: time }),
  
  // API 메시지를 UI 메시지로 변환
  convertToUiMessage: (message) => {
    const stockInfo = message.stock_name && message.stock_code ? {
      stockName: message.stock_name,
      stockCode: message.stock_code
    } : undefined;
    
    // components 직접 사용 또는 metadata에서 추출
    const components = message.components || message.metadata?.components as MessageComponent[] | undefined;
    // components 데이터가 있는 경우 콘솔에 출력 (디버깅용)
    if (components && components.length > 0) {
      console.log('[채팅 스토어] 메시지 컴포넌트 변환:', message.id, components.length, '개');
    }

    return {
      id: message.id,
      role: message.role as 'user' | 'assistant' | 'status',
      content: message.content,
      content_expert: message.content_expert,
      timestamp: message.created_at ? new Date(message.created_at).getTime() : Date.now(),
      stockInfo,
      components,
      responseId: message.metadata?.responseId,
      isProcessing: message.metadata?.isProcessing,
      agent: message.metadata?.agent,
      elapsed: message.metadata?.elapsed
    };
  },
  
  // UI 메시지를 API 메시지로 변환
  convertToApiMessage: (message) => {
    return {
      id: message.id,
      role: message.role,
      content: message.content,
      content_expert: message.content_expert,
      chat_session_id: get().currentSession?.id || "",
      stock_name: message.stockInfo?.stockName || "",
      stock_code: message.stockInfo?.stockCode || "",
      created_at: new Date(message.timestamp).toISOString(),
      ok: true,
      status_message: "",
      metadata: {
        components: message.components,
        responseId: message.responseId,
        isProcessing: message.isProcessing,
        agent: message.agent,
        elapsed: message.elapsed,
        stockInfo: message.stockInfo
      }
    };
  },
  
  // UI용 메시지 배열 반환
  getUiMessages: () => {
    return get().messages.map(get().convertToUiMessage);
  },
  
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
      isLoading: false,
      // 세션 로드 시 UI 상태도 업데이트
      isInputCentered: false,
      showTitle: true
    })
    
    console.log('[채팅 스토어] 채팅 세션 로드 완료')
  }
})) 