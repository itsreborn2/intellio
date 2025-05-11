/**
 * messageFormatters.ts
 * 채팅 메시지 포맷 관련 유틸리티 함수
 */
import { ChatMessage } from '../types';
import { IChatMessageDetail } from '@/types/api/chat';

/**
 * 타임스탬프를 시간:분 형식의 문자열로 변환
 * @param timestamp 타임스탬프 (밀리초)
 * @returns HH:MM 형식의 시간 문자열
 */
export function formatTimestamp(timestamp: number): string {
  const date = new Date(timestamp);
  const hours = date.getHours().toString().padStart(2, '0');
  const minutes = date.getMinutes().toString().padStart(2, '0');
  return `${hours}:${minutes}`;
}

/**
 * 경과 시간(초)을 MM:SS 형식의 문자열로 변환
 * @param seconds 경과 시간(초)
 * @returns MM:SS 형식의 시간 문자열
 */
export function formatElapsedTime(seconds: number): string {
  // 전체 초를 정수부와 소수부로 나눔
  const totalSeconds = Math.floor(seconds);
  const minutes = Math.floor(totalSeconds / 60).toString().padStart(2, '0');
  const remainingSeconds = (totalSeconds % 60).toString().padStart(2, '0');
  
  // 1분 미만이면 초 단위로만 표시 (소수점 없이)
  // if (minutes === '00') {
  //   return `${totalSeconds}초`;
  // }
  
  // 1분 이상이면 분:초 형식으로 표시
  return `${minutes}:${remainingSeconds}`;
}

/**
 * API 응답 메시지를 컴포넌트 메시지 형식으로 변환
 * @param message API 응답 메시지
 * @returns 컴포넌트 메시지 형식
 */
export function convertApiMessageToComponentMessage(message: IChatMessageDetail): ChatMessage {
  return {
    id: message.id,
    role: message.role as 'user' | 'assistant' | 'status',
    content: message.content,
    content_expert: message.content_expert,
    components: message.components,
    timestamp: message.created_at ? new Date(message.created_at).getTime() : Date.now(),
    responseId: message.metadata?.responseId,
    stockInfo: message.stock_code && message.stock_name ? {
      stockName: message.stock_name,
      stockCode: message.stock_code
    } : undefined,
    isProcessing: message.metadata?.isProcessing,
    agent: message.metadata?.agent,
    elapsed: message.metadata?.elapsed
  };
}

/**
 * 사용자 메시지 생성
 * @param content 메시지 내용
 * @param stockName 종목명
 * @param stockCode 종목코드
 * @returns 사용자 메시지 객체
 */
export function createUserMessage(content: string, stockName?: string, stockCode?: string): ChatMessage {
  return {
    id: `user-${Date.now()}`,
    role: 'user',
    content,
    timestamp: Date.now(),
    stockInfo: stockName && stockCode ? {
      stockName,
      stockCode
    } : undefined
  };
}

/**
 * 상태 메시지 생성
 * @param content 메시지 내용
 * @param isProcessing 처리 중 여부
 * @param stockName 종목명
 * @param stockCode 종목코드
 * @returns 상태 메시지 객체
 */
export function createStatusMessage(
  content: string, 
  isProcessing: boolean = true, 
  stockName?: string, 
  stockCode?: string
): ChatMessage {
  return {
    id: `status-${Date.now()}`,
    role: 'status',
    content,
    timestamp: Date.now(),
    isProcessing,
    stockInfo: stockName && stockCode ? {
      stockName,
      stockCode
    } : undefined
  };
}

/**
 * 어시스턴트 메시지 생성
 * @param content 메시지 내용
 * @param contentExpert 전문가 모드 내용
 * @param stockName 종목명
 * @param stockCode 종목코드
 * @param responseId 응답 ID
 * @returns 어시스턴트 메시지 객체
 */
export function createAssistantMessage(
  content: string,
  contentExpert?: string,
  stockName?: string,
  stockCode?: string,
  responseId?: string
): ChatMessage {
  return {
    id: `assistant-${Date.now()}`,
    role: 'assistant',
    content,
    content_expert: contentExpert,
    timestamp: Date.now(),
    responseId,
    stockInfo: stockName && stockCode ? {
      stockName,
      stockCode
    } : undefined
  };
} 