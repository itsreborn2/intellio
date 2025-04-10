/**
 * messageUtils.ts
 * 메시지 처리 관련 심화 유틸리티 함수
 */
import { ChatMessage } from '../types';

/**
 * 마크다운 코드 블록 감지 정규식
 */
const CODE_BLOCK_REGEX = /```([a-zA-Z0-9]*)\n([\s\S]*?)```/g;
const INLINE_CODE_REGEX = /`([^`]+)`/g;

/**
 * 메시지 내용에서 코드 블록을 추출하는 함수
 * @param content 메시지 내용
 * @returns 추출된 코드 블록 배열
 */
export function extractCodeBlocks(content: string): Array<{ language: string; code: string }> {
  const codeBlocks: Array<{ language: string; code: string }> = [];
  let match;
  
  while ((match = CODE_BLOCK_REGEX.exec(content)) !== null) {
    codeBlocks.push({
      language: match[1] || 'text',
      code: match[2].trim()
    });
  }
  
  return codeBlocks;
}

/**
 * 메시지 내용에서 인라인 코드를 추출하는 함수
 * @param content 메시지 내용
 * @returns 추출된 인라인 코드 배열
 */
export function extractInlineCodes(content: string): string[] {
  const inlineCodes: string[] = [];
  let match;
  
  while ((match = INLINE_CODE_REGEX.exec(content)) !== null) {
    inlineCodes.push(match[1]);
  }
  
  return inlineCodes;
}

/**
 * 메시지 내용에서 링크를 추출하는 함수
 * @param content 메시지 내용
 * @returns 추출된 링크 배열
 */
export function extractLinks(content: string): string[] {
  const urlRegex = /(https?:\/\/[^\s]+)/g;
  const matches = content.match(urlRegex);
  return matches || [];
}

/**
 * 메시지 내용에서 표(테이블)를 추출하는 함수
 * @param content 메시지 내용
 * @returns 추출된 표 텍스트 배열
 */
export function extractTables(content: string): string[] {
  const tableRegex = /(\|[^\n]+\|\n)((?:\|[^\n]+\|\n)+)/g;
  const tables: string[] = [];
  let match;
  
  while ((match = tableRegex.exec(content)) !== null) {
    tables.push(match[0]);
  }
  
  return tables;
}

/**
 * 주어진 메시지가 텍스트 시작 부분에 특정 종목명을 포함하는지 확인
 * @param message 검사할 메시지
 * @param stockName 검색할 종목명
 * @returns 포함 여부
 */
export function messageStartsWithStock(message: ChatMessage, stockName: string): boolean {
  if (!message.content || !stockName) return false;
  
  const firstLine = message.content.split('\n')[0];
  return firstLine.includes(stockName);
}

/**
 * 메시지 목록에서 특정 종목에 관한 메시지들만 필터링
 * @param messages 메시지 목록
 * @param stockCode 종목 코드
 * @returns 필터링된 메시지 목록
 */
export function filterMessagesByStock(messages: ChatMessage[], stockCode: string): ChatMessage[] {
  if (!stockCode) return messages;
  
  return messages.filter(message => 
    message.stockInfo && message.stockInfo.stockCode === stockCode
  );
}

/**
 * 연속된 사용자 질문 여부 확인
 * @param messages 메시지 목록
 * @returns 마지막 두 메시지가 연속된 사용자 메시지인지 여부
 */
export function hasConsecutiveUserQuestions(messages: ChatMessage[]): boolean {
  if (messages.length < 2) return false;
  
  const lastTwoMessages = messages.slice(-2);
  return lastTwoMessages[0].role === 'user' && lastTwoMessages[1].role === 'user';
}

/**
 * 메시지 내용 분석
 * @param message 분석할 메시지
 * @returns 분석 결과
 */
export function analyzeMessageContent(message: ChatMessage): {
  hasCodeBlocks: boolean;
  hasInlineCodes: boolean;
  hasLinks: boolean;
  hasTables: boolean;
  wordCount: number;
  estimatedReadTime: number;
} {
  const content = message.content || '';
  
  const codeBlocks = extractCodeBlocks(content);
  const inlineCodes = extractInlineCodes(content);
  const links = extractLinks(content);
  const tables = extractTables(content);
  
  // 단어 수 계산 (공백으로 구분)
  const wordCount = content.trim().split(/\s+/).length;
  
  // 읽는 시간 추정 (평균 분당 200단어 기준)
  const estimatedReadTime = Math.ceil(wordCount / 200);
  
  return {
    hasCodeBlocks: codeBlocks.length > 0,
    hasInlineCodes: inlineCodes.length > 0,
    hasLinks: links.length > 0,
    hasTables: tables.length > 0,
    wordCount,
    estimatedReadTime
  };
}

export default {
  extractCodeBlocks,
  extractInlineCodes,
  extractLinks,
  extractTables,
  messageStartsWithStock,
  filterMessagesByStock,
  hasConsecutiveUserQuestions,
  analyzeMessageContent
}; 