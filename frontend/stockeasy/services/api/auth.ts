import { apiFetch, API_ENDPOINT_COMMON, API_ENDPOINT_STOCKEASY } from './index';
import { IOAuthLoginResponse } from '@/types/api/auth';

//////////////////////////////////
// 현재는 전부 더미 코드 2025.03.13
//////////////////////////////////

/**
 * 사용자의 인증 상태를 확인합니다.
 * @returns 사용자 정보와 토큰
 */
export const checkAuth = async (): Promise<IOAuthLoginResponse> => {
  const response = await apiFetch(`${API_ENDPOINT_COMMON}/auth/check`, {
    credentials: 'include'
  });
  
  if (!response.ok) {
    throw new Error('인증 확인에 실패했습니다.');
  }
  
  return response.json();
};

/**
 * 로그아웃 처리를 합니다.
 */
export const logout = async (): Promise<void> => {
  try {
    const response = await apiFetch(`${API_ENDPOINT_COMMON}/auth/logout`, {
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