// API 타입들을 재내보내기
export * from './api/auth';
export * from './api/telegram';
export * from './api/chat';
export * from './api/stock'; 

// 히스토리 아이템 인터페이스
export interface IHistoryItem {
  id: string
  stockName: string // 종목명
  stockCode?: string // 종목코드 (선택적)
  prompt: string // 입력한 프롬프트
  timestamp: number // 저장 시간
  userId?: string // 사용자 ID
  responseId?: string // 분석 결과의 고유 ID
} 