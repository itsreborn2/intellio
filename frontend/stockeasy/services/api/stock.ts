import { apiFetch, API_ENDPOINT_STOCKEASY } from './index';
import { IStockInfo, IStockPriceHistory, IStockSearchRequest } from '@/types/api/stock';
//////////////////////////////////
// 현재는 전부 더미 코드 2025.03.13
//////////////////////////////////
/**
 * 주식 정보를 가져옵니다.
 * @param stockCode 주식 코드
 * @returns 주식 정보
 */
export const getStockInfo = async (stockCode: string): Promise<IStockInfo> => {
  const response = await apiFetch(`${API_ENDPOINT_STOCKEASY}/stocks/${stockCode}`);
  
  if (!response.ok) {
    throw new Error('주식 정보를 가져오는데 실패했습니다.');
  }
  
  return response.json();
};

/**
 * 주식 가격 기록을 가져옵니다.
 * @param stockCode 주식 코드
 * @param period 기간 (daily, weekly, monthly)
 * @returns 주식 가격 기록
 */
export const getStockPriceHistory = async (
  stockCode: string, 
  period: 'daily' | 'weekly' | 'monthly' = 'daily'
): Promise<IStockPriceHistory[]> => {
  const response = await apiFetch(
    `${API_ENDPOINT_STOCKEASY}/stocks/${stockCode}/prices?period=${period}`
  );
  
  if (!response.ok) {
    throw new Error('주식 가격 기록을 가져오는데 실패했습니다.');
  }
  
  return response.json();
};

/**
 * 주식을 검색합니다.
 * @param query 검색어
 * @returns 검색 결과
 */
export const searchStocks = async (query: string): Promise<IStockInfo[]> => {
  const request: IStockSearchRequest = { query };
  
  const response = await apiFetch(`${API_ENDPOINT_STOCKEASY}/stocks/search`, {
    method: 'POST',
    body: JSON.stringify(request)
  });
  
  if (!response.ok) {
    throw new Error('주식 검색에 실패했습니다.');
  }
  
  return response.json();
}; 