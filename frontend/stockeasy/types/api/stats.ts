/**
 * 스탁이지 통계 API 관련 타입 정의
 */

/**
 * 기본 응답 인터페이스
 */
export interface IBaseResponse {
  ok: boolean;
  status_message: string;
}

/**
 * 순위 변동 타입
 */
export type RankChangeType = 'UP' | 'DOWN' | 'SAME' | 'NEW' | 'OUT';

/**
 * 순위 변동 정보 인터페이스
 */
export interface IRankChange {
  change_type: RankChangeType;
  change_value: number;
  previous_rank?: number;
}

/**
 * 인기 종목 항목 인터페이스
 */
export interface IStockPopularityItem {
  stock_code: string;
  stock_name: string;
  query_count: number;
  rank: number;
  rank_change?: IRankChange;
}

/**
 * 기간별 인기 종목 데이터 인터페이스
 */
export interface IPopularStocksPeriodData {
  stocks: IStockPopularityItem[];
  period_hours: number;
  total_count: number;
  from_cache: boolean;
}

/**
 * 인기 종목 응답 인터페이스
 */
export interface IPopularStocksResponse extends IBaseResponse {
  data_24h?: IPopularStocksPeriodData; // 24시간 데이터
  data_7d?: IPopularStocksPeriodData;  // 7일 데이터
}

/**
 * 세션 수 응답 인터페이스
 */
export interface ISessionCountResponse extends IBaseResponse {
  period_hours: number;
  total_sessions: number;
  sessions_with_stock: number;
  sessions_without_stock: number;
}