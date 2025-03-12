export interface IBaseResponse {
  ok:boolean;
  status_message:string;
}

/**
 * 채팅 요청 인터페이스
 */
export interface IChatRequest {
  question: string;
  stock_code: string;
  stock_name: string;
}

/**
 * 채팅 응답 인터페이스
 */
export interface IChatResponse extends IBaseResponse {
  answer: string;
  context?: {
    sources: Array<{
      title: string;
      url?: string;
      content?: string;
    }>;
  };
  timestamp?: string;
  queryId?: string;
}

/**
 * 채팅 메시지 인터페이스
 */
export interface IChatMessage {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: string;
} 