// AIChatArea의 채팅 관련 타입 정의
import { IChatSession } from '@/types/api/chat';
import { StockOption } from './stock';

/**
 * 채팅 메시지 타입 정의
 */
export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant' | 'status';
  content: string;
  content_expert?: string;
  timestamp: number;
  stockInfo?: {
    stockName: string;
    stockCode: string;
  };
  responseId?: string; // 분석 결과의 고유 ID
  isProcessing?: boolean; // 처리 중 상태
  agent?: string; // 에이전트 정보
  elapsed?: number; // 경과 시간 (초 단위)
  elapsedStartTime?: number; // 경과 시간 시작 타임스탬프
}

/**
 * 메시지 처리를 위한 콜백 함수 타입들
 */
export interface MessageCallbacks {
  onStart?: () => void;
  onAgentStart?: (data: { agent: string; message: string; elapsed: number }) => void;
  onAgentComplete?: (data: { agent: string; message: string; elapsed: number }) => void;
  onComplete?: (data: { 
    message_id: string; 
    response: string; 
    response_expert?: string; 
    metadata?: any 
  }) => void;
  onError?: (error: Error) => void;
}

/**
 * 채팅 컨텍스트 상태 정의
 */
export interface ChatContextState {
  messages: ChatMessage[];
  isProcessing: boolean;
  selectedStock: StockOption | null;
  isInputCentered: boolean;
  showTitle: boolean;
  responseMessage: string;
  statusMessage: string;
  currentChatSession: IChatSession | null;
  copyStates: Record<string, boolean>;
  expertMode: Record<string, boolean>;
  elapsedTime: number;
}

/**
 * 채팅 컨텍스트 액션 정의
 */
export type ChatAction =
  | { type: 'ADD_MESSAGE'; payload: ChatMessage }
  | { type: 'UPDATE_MESSAGE'; payload: { id: string; message: Partial<ChatMessage> } }
  | { type: 'REMOVE_MESSAGE'; payload: string }
  | { type: 'SET_SELECTED_STOCK'; payload: StockOption | null }
  | { type: 'SET_PROCESSING'; payload: boolean }
  | { type: 'SET_INPUT_CENTERED'; payload: boolean }
  | { type: 'SET_SHOW_TITLE'; payload: boolean }
  | { type: 'SET_CHAT_SESSION'; payload: IChatSession | null }
  | { type: 'RESET_CHAT' }
  | { type: 'TOGGLE_EXPERT_MODE'; payload: string }
  | { type: 'SET_COPY_STATE'; payload: { id: string; state: boolean } }
  | { type: 'SET_ELAPSED_TIME'; payload: number }
  | { type: 'SET_ALL_MESSAGES'; payload: ChatMessage[] }; 