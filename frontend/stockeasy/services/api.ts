const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL
export const API_ENDPOINT = `${API_BASE_URL}/v1/stockeasy`

// API 요청을 위한 기본 옵션
const defaultFetchOptions: RequestInit = {
  credentials: 'include',
  headers: {
    'Content-Type': 'application/json',
    'Accept': 'application/json',
  }
};

// fetch 함수 래퍼
const apiFetch = async (url: string, options: RequestInit = {}) => {
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

export interface IOAuthLoginResponse {
  user: {
    id: string;
    email: string;
    name: string;
    provider: string;
  };
  token: string;
}

export const checkAuth = async (): Promise<IOAuthLoginResponse> => {
  const response = await apiFetch(`${API_ENDPOINT}/auth/check`, {
    credentials: 'include'
  });
  if (!response.ok) {
    throw new Error('인증 확인에 실패했습니다.');
  }
  return response.json();
};

export const logout = async (): Promise<void> => {
  try {
    const response = await apiFetch(`${API_ENDPOINT}/auth/logout`, {
      method: 'POST',
      credentials: 'include'
    });
    
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.detail || '로그아웃에 실패했습니다.');
    }
  } catch (error) {
    console.error('Logout failed:', error);
    throw error;
  }
}; 