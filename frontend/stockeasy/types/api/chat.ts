export interface IBaseResponse {
  ok:boolean;
  status_message:string;
}

/**
 * 채팅 요청 인터페이스
 */
export interface IChatRequest {
  message: string;
  stock_code: string;
  stock_name: string;
  chat_session_id?: string;
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

/**
 * 채팅 세션 생성 요청 인터페이스
 */
export interface IChatSessionCreateRequest {
  title?: string;
  stock_code?: string;
  stock_name?: string;
  stock_info?: any;
}

/**
 * 채팅 세션 업데이트 요청 인터페이스
 */
export interface IChatSessionUpdateRequest {
  title?: string;
  stock_code?: string;
  stock_name?: string;
  stock_info?: any;
  is_active?: boolean;
}

/**
 * 채팅 메시지 생성 요청 인터페이스
 */
export interface IChatMessageCreateRequest  {
  message: string;
  stock_code: string;
  stock_name: string;
}

/**
 * 채팅 세션 인터페이스
 */
export interface IChatSession  extends IBaseResponse {
  id: string;
  user_id: string;
  title: string;
  stock_code?: string;
  stock_name?: string;
  stock_info?: any;
  is_active: boolean;
  created_at?: string;
  updated_at?: string;
}

/**
 * 상세 채팅 메시지 인터페이스
 */
export interface IChatMessageDetail  extends IBaseResponse {
  id: string;
  chat_session_id: string;
  role: 'user' | 'assistant' | 'system' | 'status';
  content: string;
  content_expert?: string;
  stock_code: string;
  stock_name: string;
  metadata?: any;
  created_at?: string;
  updated_at?: string;
}

/**
 * 채팅 세션 목록 응답 인터페이스
 */
export interface IChatSessionListResponse extends IBaseResponse  {
  sessions: IChatSession[];
  total: number;
}

/**
 * 채팅 메시지 목록 응답 인터페이스
 */
export interface IChatMessageListResponse extends IBaseResponse  {
  messages: IChatMessageDetail[];
  total: number;
} 