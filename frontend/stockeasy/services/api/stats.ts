/**
 * 스탁이지 통계 API 서비스
 */

import { apiFetch, API_ENDPOINT_STOCKEASY } from './index';
import { IPopularStocksResponse, ISessionCountResponse } from '../../types/api/stats';

const STATS_API_BASE = `${API_ENDPOINT_STOCKEASY}/stats`;

/**
 * 인기 종목 조회
 * 24시간 및 7일 기간의 인기 종목 데이터를 Redis 캐시를 통해 조회합니다.
 * @param limit 반환할 종목 수 (기본값: 20)
 * @returns 24시간과 7일 인기 종목 데이터
 */
export const getPopularStocks = async (
  limit: number = 20
): Promise<IPopularStocksResponse> => {
  const response = await apiFetch(
    `${STATS_API_BASE}/popular-stocks?limit=${limit}`
  );

  if (!response.ok) {
    throw new Error(`인기 종목 조회 실패: ${response.status}`);
  }

  return response.json();
};

/**
 * 세션 개수 통계 조회
 * @param hours 조회 기간 (시간, 기본값: 24)
 * @returns 세션 개수 통계
 */
export const getSessionCount = async (
  hours: number = 24
): Promise<ISessionCountResponse> => {
  const response = await apiFetch(
    `${STATS_API_BASE}/session-count?hours=${hours}`
  );

  if (!response.ok) {
    throw new Error(`세션 개수 조회 실패: ${response.status}`);
  }

  return response.json();
}; 