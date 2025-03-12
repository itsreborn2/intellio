/**
 * API 연결 설정 및 공통 유틸리티
 */

// API 기본 URL 설정
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL;
export const API_ENDPOINT_COMMON = `${API_BASE_URL}/v1`;
export const API_ENDPOINT_STOCKEASY = `${API_BASE_URL}/v1/stockeasy`;

// API 요청을 위한 기본 옵션
export const defaultFetchOptions: RequestInit = {
  credentials: 'include',
  headers: {
    'Content-Type': 'application/json',
    'Accept': 'application/json',
  }
};

/**
 * 공통 fetch 래퍼 함수
 * @param url API 엔드포인트 URL
 * @param options fetch 옵션
 * @returns fetch 응답
 */
export const apiFetch = async (url: string, options: RequestInit = {}) => {
  try {
    const response = await fetch(url, {
      ...defaultFetchOptions,
      ...options,
      headers: {
        ...defaultFetchOptions.headers,
        ...options.headers,
      }
    });

    if (response.status === 401) {
      // 세션 만료 이벤트 발생
      window.dispatchEvent(new CustomEvent('sessionExpired'));
      throw new Error('세션이 만료되었습니다. 다시 로그인해주세요.');
    }

    return response;
  } catch (error) {
    console.error('API request failed:', error);
    throw error;
  }
};
