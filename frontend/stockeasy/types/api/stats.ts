/**
 * 스탁이지 통계 API 타입 정의
 */

export interface IBaseResponse {
  ok: boolean;
  status_message: string;
}

/**
 * 인기 종목 항목 인터페이스
 */
export interface IStockPopularityItem {
  stock_code: string;
  stock_name: string;
  query_count: number;
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
  data_24h: IPopularStocksPeriodData;
  data_7d: IPopularStocksPeriodData;
}

/**
 * 세션 개수 응답 인터페이스
 */
export interface ISessionCountResponse extends IBaseResponse {
  period_hours: number;
  total_sessions: number;
  sessions_with_stock: number;
  sessions_without_stock: number;
} 