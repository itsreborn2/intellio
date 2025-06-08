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
 * 인기 종목 응답 인터페이스
 */
export interface IPopularStocksResponse extends IBaseResponse {
  stocks: IStockPopularityItem[];
  period_hours: number;
  total_count: number;
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