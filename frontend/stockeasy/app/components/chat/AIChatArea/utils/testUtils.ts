/**
 * testUtils.ts
 * 컴포넌트 테스트를 위한 유틸리티 함수
 */
import { StockOption, ChatMessage } from '../types';

/**
 * 테스트용 메시지 생성
 * @param role 메시지 역할 (user, assistant, status)
 * @param content 메시지 내용
 * @param stockInfo 종목 정보
 * @returns 테스트용 메시지 객체
 */
export function createTestMessage(
  role: 'user' | 'assistant' | 'status' = 'user',
  content: string = '테스트 메시지',
  stockInfo?: { stockName: string; stockCode: string },
  messageId?: string // ID를 외부에서 지정할 수 있도록 추가
): ChatMessage {
  return {
    id: messageId || `test-${Date.now()}-${Math.random().toString(36).substring(2, 9)}`,
    role,
    content,
    timestamp: Date.now(),
    isProcessing: role === 'status',
    stockInfo,
    ...(role === 'assistant' && { content_expert: `Expert mode content for: ${content}` })
  };
}

/**
 * 테스트용 종목 정보 생성
 * @param stockCode 종목 코드
 * @param stockName 종목명
 * @returns 테스트용 종목 정보 객체
 */
export function createTestStock(
  stockCode: string = '005930',
  stockName: string = '삼성전자'
): StockOption {
  return {
    value: stockCode,
    label: `${stockName} (${stockCode})`,
    stockName,
    stockCode,
    display: stockName
  };
}

/**
 * 테스트용 메시지 목록 생성
 * @param count 생성할 메시지 수
 * @param stockInfo 종목 정보
 * @returns 테스트용 메시지 목록
 */
export function createTestMessages(
  count: number = 5,
  stockInfo?: { stockName: string; stockCode: string }
): ChatMessage[] {
  const messages: ChatMessage[] = [];
  
  for (let i = 0; i < count; i++) {
    const isEven = i % 2 === 0;
    const role = isEven ? 'user' : 'assistant';
    const content = isEven 
      ? `사용자 테스트 메시지 ${Math.floor(i/2) + 1}` 
      : `어시스턴트 테스트 응답 ${Math.floor(i/2) + 1}`;
    
    messages.push(createTestMessage(role, content, stockInfo, `message-id-${i}`));
  }
  
  return messages;
}

/**
 * 테스트용 스톡 옵션 목록 생성
 * @param count 생성할 옵션 수
 * @returns 테스트용 스톡 옵션 목록
 */
export function createTestStockOptions(count: number = 5): StockOption[] {
  const stockCodes = ['005930', '000660', '035420', '035720', '005380', '051910', '068270', '207940'];
  const stockNames = ['삼성전자', 'SK하이닉스', 'NAVER', '카카오', '현대차', 'LG화학', '셀트리온', '삼성바이오로직스'];
  
  return Array.from({ length: Math.min(count, stockCodes.length) }, (_, i) => 
    createTestStock(stockCodes[i], stockNames[i])
  );
}

/**
 * 테스트용 에러 객체 생성
 * @param message 에러 메시지
 * @param code 에러 코드
 * @returns 테스트용 에러 객체
 */
export function createTestError(message: string = '오류가 발생했습니다', code: string = 'ERROR'): Error {
  const error = new Error(message);
  (error as any).code = code;
  return error;
}

/**
 * 고유 ID 생성 (테스트용)
 * @returns 랜덤 ID 문자열
 */
export function generateTestId(): string {
  return `id-${Date.now()}-${Math.random().toString(36).substring(2, 9)}`;
}

export default {
  createTestMessage,
  createTestStock,
  createTestMessages,
  createTestStockOptions,
  createTestError,
  generateTestId
}; 