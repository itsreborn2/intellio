/**
 * 텔레그램 메시지 인터페이스
 */
export interface ITelegramMessage {
  chatId: string;
  text: string;
  parseMode?: 'HTML' | 'Markdown';
}

/**
 * 텔레그램 메시지 전송 응답 인터페이스
 */
export interface ITelegramSendResponse {
  success: boolean;
  messageId?: string;
  error?: string;
}

/**
 * 텔레그램 업데이트 인터페이스
 */
export interface ITelegramUpdate {
  updateId: number;
  message?: {
    messageId: number;
    from: {
      id: number;
      firstName: string;
      lastName?: string;
      username?: string;
    };
    chat: {
      id: number;
      type: 'private' | 'group' | 'supergroup' | 'channel';
      title?: string;
      username?: string;
      firstName?: string;
      lastName?: string;
    };
    date: number;
    text?: string;
  };
} 