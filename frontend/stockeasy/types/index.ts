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

// 20malist.csv 파일의 데이터 구조
export interface MaListData {
  종목코드: string;
  종목명: string;
  섹터?: string;
  대표종목?: string;
  등락률?: string; // 종목 등락률
  변동일?: string;
  포지션?: string;
  '20일 이격'?: string;
  산업?: string; // 산업명 필드 추가
  '산업 등락률'?: string; // 산업 등락률 필드 추가
  '대표종목(RS)'?: string;
  // 필요에 따라 다른 필드 추가 가능
}

// 사용자 정보 인터페이스 (관리자 대시보드용)
export interface IUser {
  id: string; // UUID
  email: string;
  name: string;
  is_active: boolean;
  is_superuser: boolean;
  oauth_provider?: string | null;
  profile_image?: string | null;
  created_at?: string;
}

