/**
 * ChatContext.tsx
 * 채팅 상태 관리를 위한 컨텍스트 API
 */
import React, { createContext, useContext, useReducer, ReactNode, useMemo } from 'react';
import { ChatContextState, ChatAction, ChatMessage, StockOption } from '../types';
import { IChatSession } from '@/types/api/chat';

// 초기 상태 정의
const initialState: ChatContextState = {
  messages: [],
  isProcessing: false,
  selectedStock: null,
  isInputCentered: true,
  showTitle: true,
  responseMessage: '',
  statusMessage: '',
  currentChatSession: null,
  copyStates: {},
  expertMode: {},
  elapsedTime: 0
};

// 리듀서 함수 정의
function chatReducer(state: ChatContextState, action: ChatAction): ChatContextState {
  switch (action.type) {
    case 'ADD_MESSAGE':
      return {
        ...state,
        messages: [...state.messages, action.payload]
      };
    case 'UPDATE_MESSAGE':
      return {
        ...state,
        messages: state.messages.map(msg =>
          msg.id === action.payload.id
            ? { ...msg, ...action.payload.message }
            : msg
        )
      };
    case 'REMOVE_MESSAGE':
      return {
        ...state,
        messages: state.messages.filter(msg => msg.id !== action.payload)
      };
    case 'SET_SELECTED_STOCK':
      return {
        ...state,
        selectedStock: action.payload
      };
    case 'SET_PROCESSING':
      return {
        ...state,
        isProcessing: action.payload
      };
    case 'SET_INPUT_CENTERED':
      return {
        ...state,
        isInputCentered: action.payload
      };
    case 'SET_SHOW_TITLE':
      return {
        ...state,
        showTitle: action.payload
      };
    case 'SET_CHAT_SESSION':
      return {
        ...state,
        currentChatSession: action.payload
      };
    case 'RESET_CHAT':
      return {
        ...initialState,
        // 아래 항목들은 초기화하지 않음
        copyStates: state.copyStates,
        expertMode: state.expertMode
      };
    case 'TOGGLE_EXPERT_MODE':
      return {
        ...state,
        expertMode: {
          ...state.expertMode,
          [action.payload]: !state.expertMode[action.payload]
        }
      };
    case 'SET_COPY_STATE':
      return {
        ...state,
        copyStates: {
          ...state.copyStates,
          [action.payload.id]: action.payload.state
        }
      };
    case 'SET_ELAPSED_TIME':
      return {
        ...state,
        elapsedTime: action.payload
      };
    case 'SET_ALL_MESSAGES':
      return {
        ...state,
        messages: action.payload
      };
    default:
      return state;
  }
}

// 컨텍스트 객체 생성
type ChatContextType = {
  state: ChatContextState;
  dispatch: React.Dispatch<ChatAction>;
  // 편의 함수들
  addMessage: (message: ChatMessage) => void;
  updateMessage: (id: string, message: Partial<ChatMessage>) => void;
  removeMessage: (id: string) => void;
  setSelectedStock: (stock: StockOption | null) => void;
  setProcessing: (isProcessing: boolean) => void;
  setInputCentered: (isCentered: boolean) => void;
  resetChat: () => void;
  toggleExpertMode: (messageId: string) => void;
  setCopyState: (id: string, state: boolean) => void;
  setChatSession: (session: IChatSession | null) => void;
  setAllMessages: (messages: ChatMessage[]) => void;
};

const ChatContext = createContext<ChatContextType | undefined>(undefined);

// 컨텍스트 프로바이더 컴포넌트
export function ChatProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(chatReducer, initialState);
  
  // 편의 함수들 메모이제이션
  const contextValue = useMemo(() => ({
    state,
    dispatch,
    addMessage: (message: ChatMessage) => 
      dispatch({ type: 'ADD_MESSAGE', payload: message }),
    updateMessage: (id: string, message: Partial<ChatMessage>) => 
      dispatch({ type: 'UPDATE_MESSAGE', payload: { id, message } }),
    removeMessage: (id: string) => 
      dispatch({ type: 'REMOVE_MESSAGE', payload: id }),
    setSelectedStock: (stock: StockOption | null) => 
      dispatch({ type: 'SET_SELECTED_STOCK', payload: stock }),
    setProcessing: (isProcessing: boolean) => 
      dispatch({ type: 'SET_PROCESSING', payload: isProcessing }),
    setInputCentered: (isCentered: boolean) => 
      dispatch({ type: 'SET_INPUT_CENTERED', payload: isCentered }),
    resetChat: () => 
      dispatch({ type: 'RESET_CHAT' }),
    toggleExpertMode: (messageId: string) => 
      dispatch({ type: 'TOGGLE_EXPERT_MODE', payload: messageId }),
    setCopyState: (id: string, state: boolean) => 
      dispatch({ type: 'SET_COPY_STATE', payload: { id, state } }),
    setChatSession: (session: IChatSession | null) => 
      dispatch({ type: 'SET_CHAT_SESSION', payload: session }),
    setAllMessages: (messages: ChatMessage[]) =>
      dispatch({ type: 'SET_ALL_MESSAGES', payload: messages })
  }), [state, dispatch]);

  return (
    <ChatContext.Provider value={contextValue}>
      {children}
    </ChatContext.Provider>
  );
}

// 커스텀 훅
export function useChatContext() {
  const context = useContext(ChatContext);
  if (context === undefined) {
    throw new Error('useChatContext must be used within a ChatProvider');
  }
  return context;
}

export default ChatContext; 