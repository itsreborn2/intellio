import { apiFetch, API_ENDPOINT_STOCKEASY } from './index';
import { IChatRequest, IChatResponse } from '@/types/api/chat';

/**
 * AI 채팅 메시지를 전송합니다.
 * @param stockCode 주식 코드
 * @param message 전송할 메시지
 * @returns 응답 데이터
 */
export const sendChatMessage = async (
  stockCode: string, 
  stockName: string,
  message: string
): Promise<IChatResponse> => {
  const request: IChatRequest = {
    question: message,
    stock_code: stockCode,
    stock_name: stockName
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