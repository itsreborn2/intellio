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

// 토큰 사용량 요약 정보 인터페이스
export interface ITokenUsageSummary {
  period: string;
  start_date: string;
  end_date: string;
  summary: {
    total_prompt_tokens: number;
    total_completion_tokens: number;
    total_tokens: number;
    total_cost: number;
  };
  token_type_summary: {
    [key: string]: {
      total_prompt_tokens: number;
      total_completion_tokens: number;
      total_tokens: number;
      total_cost: number;
    };
  };
}

// 토큰 사용량 상세 정보 인터페이스
export interface ITokenUsageDetail {
  token_usages: Array<{
    id: string;
    user_id: string;
    project_type: string;
    token_type: string;
    model_name: string;
    prompt_tokens: number;
    completion_tokens: number | null;
    total_tokens: number;
    cost: number;
    created_at: string;
  }>;
  summary: {
    total_prompt_tokens: number;
    total_completion_tokens: number;
    total_tokens: number;
    total_cost: number;
  };
  project_summary: {
    [key: string]: {
      total_prompt_tokens: number;
      total_completion_tokens: number;
      total_tokens: number;
      total_cost: number;
    };
  };
  token_type_summary: {
    [key: string]: {
      total_prompt_tokens: number;
      total_completion_tokens: number;
      total_tokens: number;
      total_cost: number;
    };
  };
}

// 사용자 질문 수 요약 정보 인터페이스
export interface IQuestionCountSummary {
  period: string;
  start_date: string;
  end_date: string;
  total_questions: number;
  grouped_data: {
    [key: string]: number; // 날짜별 질문 수 (YYYY-MM-DD: count)
  };
} 