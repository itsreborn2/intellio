import { apiFetch, API_ENDPOINT_STOCKEASY } from './index';
import { ITelegramMessage, ITelegramSendResponse } from '@/types/api/telegram';

//////////////////////////////////
// 현재는 전부 더미 코드 2025.03.13
//////////////////////////////////


/**
 * 텔레그램 API 클라이언트
 */
export class TelegramAPI {
  private static baseUrl = `${API_ENDPOINT_STOCKEASY}/telegram`;

  /**
   * 텔레그램 메시지를 전송합니다.
   * @param message 전송할 메시지 객체
   * @returns 메시지 전송 결과
   */
  static async sendMessage(message: ITelegramMessage): Promise<ITelegramSendResponse> {
    const response = await apiFetch(`${this.baseUrl}/send`, {
      method: 'POST',
      body: JSON.stringify(message)
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.detail || '텔레그램 메시지 전송에 실패했습니다.');
    }

    return response.json();
  }

  /**
   * 최근 텔레그램 업데이트를 가져옵니다.
   * @returns 최근 업데이트 목록
   */
  static async getUpdates(): Promise<any[]> {
    const response = await apiFetch(`${this.baseUrl}/updates`);

    if (!response.ok) {
      throw new Error('텔레그램 업데이트 조회에 실패했습니다.');
    }

    return response.json();
  }
} 