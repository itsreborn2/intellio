/**
 * API 연결 설정 및 공통 유틸리티
 */

import axios from 'axios';

// API 기본 URL 설정
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL;
export const API_ENDPOINT_COMMON = `${API_BASE_URL}/v1`;
export const API_ENDPOINT_STOCKEASY = `${API_BASE_URL}/v1/stockeasy`;
export const API_ENDPOINT_TOKEN_USAGE = `${API_BASE_URL}/v1/token-usage`;

/**
 * 널 문자를 제거하는 유틸리티 함수
 * @param str 처리할 문자열
 * @returns 널 문자가 제거된 문자열
 */
export const removeNullCharacters = (str: string): string => {
  if (!str) return str;
  // 널 문자(\u0000)를 모두 제거
  return str.replace(/\0/g, '');
};

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
    // body가 문자열이고 널 문자가 포함된 경우 처리
    if (options.body && typeof options.body === 'string') {
      options.body = removeNullCharacters(options.body);
    }

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

// 토큰 사용량 요약 정보 조회
export const getTokenUsageSummary = async (projectType: string = 'stockeasy', period: string = 'month') => {
  try {
    const response = await axios.get(`${API_ENDPOINT_TOKEN_USAGE}/summary`, {
      params: {
        project_type: projectType,
        period
      },
      withCredentials: true
    });
    return response.data;
  } catch (error) {
    console.error('토큰 사용량 요약 정보 조회 실패:', error);
    throw error;
  }
};

// 질문 개수 요약 정보 조회
export const getQuestionCountSummary = async (period: string = 'month', groupBy: string | null = null) => {
  try {
    const params: any = { period };
    if (groupBy) {
      params.group_by = groupBy;
    }
    
    const response = await axios.get(`${API_ENDPOINT_TOKEN_USAGE}/question-count`, {
      params,
      withCredentials: true
    });
    return response.data;
  } catch (error) {
    console.error('질문 개수 요약 정보 조회 실패:', error);
    throw error;
  }
};

// 토큰 사용량 상세 정보 조회
export const getTokenUsageDetail = async (
  projectType: string = 'stockeasy',
  tokenType: string | null = null,
  startDate: string | null = null,
  endDate: string | null = null,
  groupBy: string[] | null = null
) => {
  try {
    const response = await axios.get(`${API_ENDPOINT_TOKEN_USAGE}`, {
      params: {
        project_type: projectType,
        token_type: tokenType,
        start_date: startDate,
        end_date: endDate,
        group_by: groupBy
      },
      withCredentials: true
    });
    return response.data;
  } catch (error) {
    console.error('토큰 사용량 상세 정보 조회 실패:', error);
    throw error;
  }
};
