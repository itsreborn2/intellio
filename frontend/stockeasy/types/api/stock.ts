/**
 * 주식 정보 인터페이스
 */
export interface IStockInfo {
  code: string;
  name: string;
  market: string;
  sector?: string;
  currentPrice: number;
  change: number;
  changePercent: number;
  volume: number;
  marketCap?: number;
  lastUpdated: string;
}

/**
 * 주식 가격 기록 인터페이스
 */
export interface IStockPriceHistory {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  adjustedClose?: number;
}

/**
 * 주식 검색 요청 인터페이스
 */
export interface IStockSearchRequest {
  query: string;
  market?: 'KOSPI' | 'KOSDAQ' | 'ALL';
  limit?: number;
}

/**
 * 주식 뉴스 인터페이스
 */
export interface IStockNews {
  id: string;
  title: string;
  summary: string;
  url: string;
  source: string;
  publishedAt: string;
  sentiment?: 'positive' | 'negative' | 'neutral';
} 