import { apiFetch, API_ENDPOINT_STOCKEASY } from './index';
import { 
  IChatRequest, 
  IChatResponse, 
  IChatSessionCreateRequest, 
  IChatSession,
  IChatMessageCreateRequest,
  IChatMessageDetail,
  IChatSessionListResponse,
  IChatMessageListResponse
} from '@/types/api/chat';

/**
 * 새 채팅 세션을 생성합니다.
 * @param title 세션 제목 (기본값: "새 채팅")
 * @returns 생성된 채팅 세션 정보
 */
export const createChatSession = async (
  title: string = "새 채팅"
): Promise<IChatSession> => {
  const request: IChatSessionCreateRequest = {
    title
  };

  const response = await apiFetch(`${API_ENDPOINT_STOCKEASY}/chat/sessions`, {
    method: 'POST',
    body: JSON.stringify(request)
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || '채팅 세션 생성에 실패했습니다.');
  }

  return response.json();
};

/**
 * 사용자의 채팅 세션 목록을 조회합니다.
 * @param isActive 활성화 상태 필터 (선택)
 * @returns 채팅 세션 목록
 */
export const getChatSessions = async (
  isActive?: boolean
): Promise<IChatSessionListResponse> => {
  const queryParams = isActive !== undefined ? `?is_active=${isActive}` : '';
  const response = await apiFetch(`${API_ENDPOINT_STOCKEASY}/chat/sessions${queryParams}`);

  if (!response.ok) {
    throw new Error('채팅 세션 목록을 가져오는데 실패했습니다.');
  }

  return response.json();
};

/**
 * 채팅 세션 메시지를 생성합니다.
 * @param sessionId 채팅 세션 ID
 * @param message 메시지 내용
 * @param stockCode 종목 코드
 * @param stockName 종목 이름
 * @returns 생성된 메시지 정보
 */
export const createChatMessage = async (
  sessionId: string,
  message: string,
  stockCode: string,
  stockName: string
): Promise<IChatMessageDetail> => {
  const request: IChatMessageCreateRequest = {
    message,
    stock_code: stockCode,
    stock_name: stockName
  };

  const response = await apiFetch(`${API_ENDPOINT_STOCKEASY}/chat/sessions/${sessionId}/messages`, {
    method: 'POST',
    body: JSON.stringify(request)
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || '메시지 생성에 실패했습니다.');
  }

  return response.json();
};

/**
 * AI 채팅 메시지를 전송합니다.
 * @param stockCode 주식 코드
 * @param stockName 주식 이름
 * @param message 전송할 메시지
 * @param chatSessionId 채팅 세션 ID (선택)
 * @returns 응답 데이터
 */
export const sendChatMessage = async (
  stockCode: string, 
  stockName: string,
  message: string,
  chatSessionId?: string
): Promise<IChatResponse> => {
  const request: IChatRequest = {
    message: message,
    stock_code: stockCode,
    stock_name: stockName,
    chat_session_id: chatSessionId
  };

  const response = await apiFetch(`${API_ENDPOINT_STOCKEASY}/user_question`, {
    method: 'POST',
    body: JSON.stringify(request)
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || '메시지 전송에 실패했습니다.');
  }

  return response.json();
};

/**
 * 채팅 기록을 가져옵니다.
 * @param stockCode 주식 코드
 * @returns 채팅 기록
 */
export const getChatHistory = async (stockCode: string): Promise<IChatResponse[]> => {
  const response = await apiFetch(
    `${API_ENDPOINT_STOCKEASY}/chat/history?stock_code=${stockCode}`
  );

  if (!response.ok) {
    throw new Error('채팅 기록을 가져오는데 실패했습니다.');
  }

  return response.json();
};

/**
 * 채팅 세션의 메시지 목록을 조회합니다.
 * @param sessionId 채팅 세션 ID
 * @param limit 페이지당 항목 수 (선택)
 * @param offset 페이지 오프셋 (선택)
 * @returns 메시지 목록
 */
export const getChatMessages = async (
  sessionId: string,
  limit: number = 100,
  offset: number = 0
): Promise<IChatMessageListResponse> => {
  const response = await apiFetch(
    `${API_ENDPOINT_STOCKEASY}/chat/sessions/${sessionId}/messages?limit=${limit}&offset=${offset}`
  );

  if (!response.ok) {
    throw new Error('채팅 메시지를 가져오는데 실패했습니다.');
  }

  return response.json();
}; 