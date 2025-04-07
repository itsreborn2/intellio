import { create } from 'zustand';
import { IOAuthResponse, IOAuthUser } from '@/types/auth';
import { persist, createJSONStorage } from 'zustand/middleware';
import * as api from '@/services/api';
import { useEffect } from 'react';

interface User {
    id: string;
    email: string;
    name: string;
    provider: string;
    profile_image?: string;
}

interface AuthState {
    user: User | null;
    token: string | null; // Google, Kakao, Naver OAuth 토큰. 로그인 성공 시 서버에서 발행한 JWT 토큰.
    isAuthenticated: boolean;
    redirectTo: string | null; // 로그인 후 리디렉션할 경로
    setUser: (user: User | null) => void;
    setToken: (token: string | null) => void;
    setRedirectTo: (path: string | null) => void;
    login: (userData: User) => void;
    logout: () => Promise<void>;
    checkAuthCookie: () => void;
    clearAuthState: () => void; // 상태 초기화 함수 추가
}

// 쿠키 파싱 유틸리티 함수
const parseCookies = () => {
    return document.cookie.split(';').reduce((cookies, cookie) => {
        const [name, value] = cookie.trim().split('=');
        if (name && value) {
            cookies[name] = value;
        }
        return cookies;
    }, {} as Record<string, string>);
};

// API URL
const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api';

// 사용자 쿠키 파싱 함수 - URL 인코딩 및 일반 JSON 문자열 모두 처리
const parseUserCookie = (userCookie: string): User | null => {
    try {
        // 1. 쿠키가 URL 인코딩된 경우
        if (userCookie.includes('%')) {
            try {
                // URL 디코딩 시도
                const decodedCookie = decodeURIComponent(userCookie);
                console.debug('[useAuth] URL 디코딩된 사용자 쿠키:', decodedCookie);
                
                // 이중 따옴표로 감싸진 경우 처리
                let jsonString = decodedCookie;
                if (jsonString.startsWith('"') && jsonString.endsWith('"')) {
                    jsonString = jsonString.slice(1, -1).replace(/\\"/g, '"');
                    console.debug('[useAuth] 따옴표 제거 후 문자열:', jsonString);
                }
                
                // 손상된 JSON 문자열 복구 시도
                if (!jsonString.endsWith('}')) {
                    console.warn('[useAuth] 불완전한 JSON 문자열 감지, 복구 시도 중');
                    // 중괄호 개수 확인
                    const openBraces = (jsonString.match(/\{/g) || []).length;
                    const closeBraces = (jsonString.match(/\}/g) || []).length;
                    
                    // 닫는 중괄호가 부족한 경우 추가
                    if (openBraces > closeBraces) {
                        const missingBraces = openBraces - closeBraces;
                        jsonString = jsonString + '}'.repeat(missingBraces);
                        console.debug('[useAuth] 복구된 JSON 문자열:', jsonString);
                    }
                }
                
                return JSON.parse(jsonString);
            } catch (decodeError) {
                console.error('[useAuth] URL 디코딩 실패:', decodeError);
                return null;
            }
        }
        
        // 2. 쿠키가 일반 JSON 문자열인 경우(완전하거나 불완전한)
        if (userCookie.startsWith('{')) {
            let jsonString = userCookie;
            
            // 손상된 JSON 문자열 복구 시도
            if (!jsonString.endsWith('}')) {
                console.warn('[useAuth] 불완전한 JSON 문자열 감지, 복구 시도 중');
                // 중괄호 개수 확인
                const openBraces = (jsonString.match(/\{/g) || []).length;
                const closeBraces = (jsonString.match(/\}/g) || []).length;
                
                // 닫는 중괄호가 부족한 경우 추가
                if (openBraces > closeBraces) {
                    const missingBraces = openBraces - closeBraces;
                    jsonString = jsonString + '}'.repeat(missingBraces);
                    console.debug('[useAuth] 복구된 JSON 문자열:', jsonString);
                }
            }
            
            // 정규식을 사용하여 필수 필드만 추출하는 방식 시도
            try {
                return JSON.parse(jsonString);
            } catch (jsonError) {
                console.warn('[useAuth] 표준 JSON 파싱 실패, 정규식으로 필드 추출 시도');
                
                // 정규식으로 필수 필드 추출
                const idMatch = jsonString.match(/"id"\s*:\s*"([^"]+)"/);
                const emailMatch = jsonString.match(/"email"\s*:\s*"([^"]+)"/);
                const nameMatch = jsonString.match(/"name"\s*:\s*"([^"]+)"/);
                const providerMatch = jsonString.match(/"provider"\s*:\s*"([^"]+)"/);
                const profileMatch = jsonString.match(/"profile_image"\s*:\s*"([^"]+)"/);
                
                if (idMatch && emailMatch && nameMatch && providerMatch) {
                    const user: User = {
                        id: idMatch[1],
                        email: emailMatch[1],
                        name: nameMatch[1],
                        provider: providerMatch[1]
                    };
                    
                    if (profileMatch) {
                        user.profile_image = profileMatch[1];
                    }
                    
                    console.debug('[useAuth] 정규식으로 추출한 사용자 정보:', user);
                    return user;
                }
                
                console.error('[useAuth] 정규식 추출도 실패');
                return null;
            }
        }
        
        // 3. 이중 따옴표로 감싸진 JSON 문자열인 경우
        if (userCookie.startsWith('"') && userCookie.endsWith('"')) {
            const jsonString = userCookie.slice(1, -1).replace(/\\"/g, '"');
            console.debug('[useAuth] 따옴표 제거 후 문자열:', jsonString);
            
            // 손상된 JSON 문자열 복구 시도
            if (!jsonString.endsWith('}')) {
                // 중괄호 개수 확인
                const openBraces = (jsonString.match(/\{/g) || []).length;
                const closeBraces = (jsonString.match(/\}/g) || []).length;
                
                // 닫는 중괄호가 부족한 경우 추가
                if (openBraces > closeBraces) {
                    const fixedString = jsonString + '}'.repeat(openBraces - closeBraces);
                    try {
                        return JSON.parse(fixedString);
                    } catch (e) {
                        console.error('[useAuth] 복구된 문자열 파싱 실패:', e);
                    }
                }
            }
            
            return JSON.parse(jsonString);
        }
        
        // 4. 그 외 형식 - 처리 실패
        console.error('[useAuth] 지원되지 않는 쿠키 형식:', userCookie);
        return null;
    } catch (error) {
        console.error('[useAuth] 쿠키 파싱 오류:', error);
        return null;
    }
};

export const useAuth = create<AuthState>()((set, get) => ({
    user: null,
    token: null,
    isAuthenticated: false,
    redirectTo: null,

    setUser: (user) => {
        const currentToken = get().token;
        set({ 
            user, 
            isAuthenticated: !!user && !!currentToken 
        });
        console.log('[useAuth] 사용자 정보 설정:', user, '인증 상태:', !!user && !!currentToken);
    },
    
    setToken: (token) => {
        const currentUser = get().user;
        set({ 
            token,
            isAuthenticated: !!currentUser && !!token
        });
        console.log('[useAuth] 토큰 설정:', token ? '있음' : '없음', '인증 상태:', !!currentUser && !!token);
    },
    
    setRedirectTo: (path) => set({ redirectTo: path }),

    login: (userData) => {
        set({
            user: userData,
            isAuthenticated: true,
        });
        console.log('[useAuth] 로그인 완료:', userData);
    },

    logout: async () => {
        try {
            await api.logout();  // 서버에 로그아웃 요청 및 쿠키 삭제
            get().clearAuthState();
            console.log('[useAuth] 로그아웃 완료');
        } catch (error) {
            console.error('[useAuth] 로그아웃 실패:', error);
            // 에러가 발생하더라도 클라이언트 상태는 초기화
            get().clearAuthState();
        }
    },
    
    // 상태 초기화 함수
    clearAuthState: () => {
        set({
            user: null,
            token: null,
            isAuthenticated: false,
            redirectTo: null
        });
        console.log('[useAuth] 상태 초기화 완료');
    },

    // 쿠키에서 인증 정보 확인
    checkAuthCookie: async () => {
        try {
            // 쿠키에서 세션 ID와 인증 정보 확인
            const cookies = parseCookies();
            const sessionId = cookies['session_id']; // 백엔드에서 사용하는 세션 쿠키
            const userCookie = cookies['user']; // 사용자 정보 쿠키
            const tokenCookie = cookies['token']; // 토큰 쿠키
            
            console.debug('[useAuth] 쿠키 확인:', { 
                sessionId, 
                userCookie: userCookie ? (userCookie.length > 50 ? userCookie.substring(0, 50) + '...' : userCookie) : null,
                tokenCookie: tokenCookie ? (tokenCookie.length > 20 ? tokenCookie.substring(0, 20) + '...' : tokenCookie) : null
            });
            
            if (sessionId) {
                // 세션 ID가 있으면 사용자 정보 요청
                try {
                    const response = await fetch(`${API_URL}/v1/auth/me`, {
                        method: 'GET',
                        headers: {
                            'Content-Type': 'application/json'
                        },
                        credentials: 'include', // 쿠키 포함
                    });
                    
                    if (response.ok) {
                        const userData = await response.json();
                        set({
                            user: userData,
                            token: tokenCookie || null,
                            isAuthenticated: true
                        });
                        console.log('[useAuth] 사용자 정보 로드 완료:', userData);
                    } else {
                        console.log('[useAuth] 사용자 정보 로드 실패:', response.status);
                        // 로그인 실패 시 상태 초기화
                        get().clearAuthState();
                    }
                } catch (error) {
                    console.error('[useAuth] 사용자 정보 요청 오류:', error);
                    get().clearAuthState();
                }
            } else if (userCookie && tokenCookie) {
                // 세션 ID는 없지만 user와 token 쿠키가 있는 경우
                const userData = parseUserCookie(userCookie);
                
                if (userData) {
                    set({
                        user: userData,
                        token: tokenCookie,
                        isAuthenticated: true
                    });
                    console.log('[useAuth] 쿠키에서 사용자 정보 로드 완료:', userData);
                } else {
                    console.error('[useAuth] 사용자 쿠키 파싱 실패');
                    get().clearAuthState();
                }
            } else {
                console.log('[useAuth] 인증 쿠키 없음');
                // 모든 인증 상태 초기화
                get().clearAuthState();
            }
        } catch (error) {
            console.error('[useAuth] 인증 확인 오류:', error);
            get().clearAuthState();
        }
    }
}));

// 쿠키 기반 인증 상태 확인을 위한 훅
export const useAuthCheck = () => {
    const { checkAuthCookie, isAuthenticated } = useAuth();
    
    useEffect(() => {
        // 페이지 로드 시 즉시 실행
        setTimeout(() => {
            checkAuthCookie();
        }, 0);
        
        // 주기적으로 쿠키 확인 (선택 사항)
        const intervalId = setInterval(() => {
            checkAuthCookie();
        }, 60000); // 1분마다 확인
        
        return () => clearInterval(intervalId);
    }, [checkAuthCookie]);
    
    return { isAuthenticated };
};
