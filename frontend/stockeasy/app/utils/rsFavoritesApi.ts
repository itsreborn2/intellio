/**
 * RS 즐겨찾기 API 유틸리티 함수들
 * 
 * RS 페이지에서 사용자의 즐겨찾기 종목을 관리하기 위한 API 호출 함수들을 제공합니다.
 */

// RS 즐겨찾기 응답 타입 정의
export interface RSFavoriteResponse {
  id: number;
  user_id: string;
  stock_code: string;
  stock_name: string | null;
  created_at: string;
  updated_at: string;
}

// RS 즐겨찾기 토글 요청 타입 정의
export interface RSFavoriteToggleRequest {
  stock_code: string;
  stock_name?: string;
}

// RS 즐겨찾기 토글 응답 타입 정의
export interface RSFavoriteToggleResponse {
  is_favorite: boolean;
  message: string;
  favorite: RSFavoriteResponse | null;
}

/**
 * 사용자의 RS 즐겨찾기 목록을 조회합니다.
 * 
 * @returns Promise<RSFavoriteResponse[]> 즐겨찾기 목록
 */
export async function getRSFavorites(): Promise<RSFavoriteResponse[]> {
  try {
    const response = await fetch('http://localhost:8000/api/v1/stockeasy/rs-favorites/', {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
      credentials: 'include', // 쿠키 포함하여 인증 처리
    });

    if (!response.ok) {
      throw new Error(`RS 즐겨찾기 목록 조회 실패: ${response.status}`);
    }

    const data = await response.json();
    return data;
  } catch (error) {
    console.error('RS 즐겨찾기 목록 조회 중 오류:', error);
    throw error;
  }
}

/**
 * RS 즐겨찾기를 토글합니다. (추가/제거)
 * 
 * @param request 토글 요청 데이터
 * @returns Promise<RSFavoriteToggleResponse> 토글 결과
 */
export async function toggleRSFavorite(request: RSFavoriteToggleRequest): Promise<RSFavoriteToggleResponse> {
  try {
    const response = await fetch('http://localhost:8000/api/v1/stockeasy/rs-favorites/toggle', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      credentials: 'include', // 쿠키 포함하여 인증 처리
      body: JSON.stringify(request),
    });

    if (!response.ok) {
      throw new Error(`RS 즐겨찾기 토글 실패: ${response.status}`);
    }

    const data = await response.json();
    return data;
  } catch (error) {
    console.error('RS 즐겨찾기 토글 중 오류:', error);
    throw error;
  }
}

/**
 * 사용자의 RS 즐겨찾기 종목 코드 목록을 조회합니다.
 * 
 * @returns Promise<string[]> 즐겨찾기 종목 코드 목록
 */
export async function getRSFavoriteStockCodes(): Promise<string[]> {
  try {
    const response = await fetch('http://localhost:8000/api/v1/stockeasy/rs-favorites/stock-codes', {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
      credentials: 'include', // 쿠키 포함하여 인증 처리
    });

    if (!response.ok) {
      throw new Error(`RS 즐겨찾기 종목 코드 목록 조회 실패: ${response.status}`);
    }

    const data = await response.json();
    return data;
  } catch (error) {
    console.error('RS 즐겨찾기 종목 코드 목록 조회 중 오류:', error);
    throw error;
  }
}

/**
 * 특정 종목이 사용자의 RS 즐겨찾기에 있는지 확인합니다.
 * 
 * @param stockCode 확인할 종목 코드
 * @returns Promise<boolean> 즐겨찾기 여부
 */
export async function checkRSFavorite(stockCode: string): Promise<boolean> {
  try {
    const response = await fetch(`http://localhost:8000/api/v1/stockeasy/rs-favorites/check/${stockCode}`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
      credentials: 'include', // 쿠키 포함하여 인증 처리
    });

    if (!response.ok) {
      throw new Error(`RS 즐겨찾기 확인 실패: ${response.status}`);
    }

    const data = await response.json();
    return data;
  } catch (error) {
    console.error('RS 즐겨찾기 확인 중 오류:', error);
    throw error;
  }
}
