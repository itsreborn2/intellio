'use client'

import axios from 'axios';
import { API_ENDPOINT_COMMON } from '@/services/api/index';
import { parseCookies } from 'nookies';
/**
 * 로그아웃 처리 함수
 * - 쿠키 및 로컬 스토리지의 인증 정보 삭제
 * - 서버에 로그아웃 요청 전송
 * - 홈페이지로 리다이렉트
 */
export async function logout() {
  try {
    // API URL 설정
    //const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'https://api.intellio.kr';
    
    // 현재 세션 ID 가져오기
    let sessionId = '';
    try {
      // 쿠키에서 세션 ID 추출
      const sessionCookie = document.cookie
        .split(';')
        .find(cookie => cookie.trim().startsWith('session_id='));
      
      if (sessionCookie) {
        sessionId = sessionCookie.trim().split('=')[1];
        console.log('로그아웃 시 세션 ID:', sessionId);
      }
    } catch (e) {
      console.warn('세션 ID 추출 실패:', e);
    }
    
    // 쿠키 삭제
    document.cookie = 'refresh_token=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;';
    document.cookie = 'user=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;';
    document.cookie = 'session_id=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;';
    
    // 모든 도메인에 대한 쿠키 삭제 시도
    const domains = [
      '', // 현재 도메인
      '.intellio.kr', // 메인 도메인
      'stockeasy.intellio.kr', // 서브도메인
      'doceasy.intellio.kr', // 서브도메인
      'api.intellio.kr', // API 도메인
    ];
    
    // 각 도메인에 대해 쿠키 삭제 시도
    domains.forEach(domain => {
      const domainStr = domain ? `; domain=${domain}` : '';
      document.cookie = `refresh_token=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/${domainStr}`;
      document.cookie = `user=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/${domainStr}`;
      document.cookie = `session_id=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/${domainStr}`;
    });
    
    // 로컬 스토리지 인증 관련 정보 삭제
    localStorage.removeItem('user');
    localStorage.removeItem('authToken');
    localStorage.removeItem('userId');
    localStorage.removeItem('redirectAfterLogin');
    
    // 서버에 로그아웃 요청 전송
    // 백엔드 엔드포인트에 맞게 /api/v1/auth/logout으로 요청
    await axios.post(`${API_ENDPOINT_COMMON}/auth/logout`, {}, {
      withCredentials: true, // 쿠키 포함
      headers: {
        'Content-Type': 'application/json',
        // 세션 ID가 있으면 헤더에 포함
        ...(sessionId && { 'X-Session-ID': sessionId })
      }
    });
    
    console.log('서버 로그아웃 요청 성공');
    
    // 홈페이지로 리다이렉트
    window.location.href = '/';
    
    return { success: true };
  } catch (error) {
    console.error('로그아웃 중 오류 발생:', error);
    
    // 오류 발생해도 클라이언트 측에서 토큰 삭제 후 홈페이지로 리다이렉트
    window.location.href = '/';
    
    return { 
      success: false, 
      error: error instanceof Error ? error.message : '알 수 없는 오류' 
    };
  }
}

/**
 * 로그인 상태 확인 함수
 * @returns {boolean} 로그인 여부
 */
export function isLoggedIn(): boolean {
  // nookies를 사용하여 쿠키 파싱
  const cookies = parseCookies();
  
  // user 쿠키 또는 user_id 쿠키가 있는지 확인
  return !!cookies.user || !!cookies.user_id;
}

