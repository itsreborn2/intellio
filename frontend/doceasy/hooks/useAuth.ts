import { create } from 'zustand';
import { IOAuthResponse, IOAuthUser } from '@/types/auth';
import { persist } from 'zustand/middleware';
import * as api from '@/services/api';
import { useEffect } from 'react';

interface User {
    id: string;
    email: string;
    name: string;
    provider: string;
}

interface AuthState {
    user: User | null;
    token: string | null; // Google, Kakao, Naver OAuth 토큰. 로그인 성공 시 서버에서 발행한 JWT 토큰.
    isAuthenticated: boolean;
    setUser: (user: User | null) => void;
    setToken: (token: string | null) => void;
    login: (userData: User) => void;
    logout: () => Promise<void>;
    checkAuthCookie: () => void;
}

// 쿠키 파싱 유틸리티 함수
const parseCookies = () => {
    return document.cookie.split(';').reduce((cookies, cookie) => {
        const [name, value] = cookie.trim().split('=');
        cookies[name] = value;
        return cookies;
    }, {} as Record<string, string>);
};

// API URL
const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api';

export const useAuth = create<AuthState>()(
    persist(
        (set, get) => ({
            user: null,
            token: null,
            isAuthenticated: false,

            setUser: (user) => set({ user, isAuthenticated: !!user }),
            setToken: (token) => set({ token }),

            login: (userData) => {
                set({
                    user: userData,
                    isAuthenticated: true,
                });
            },

            logout: async () => {
                try {
                    await api.logout();  // 서버에 로그아웃 요청 및 쿠키 삭제
                    set({
                        user: null,
                        token: null,
                        isAuthenticated: false,
                    });
                    console.log('[useAuth] 로그아웃 완료');
                } catch (error) {
                    console.error('[useAuth] 로그아웃 실패:', error);
                    // 에러가 발생하더라도 클라이언트 상태는 초기화
                    set({
                        user: null,
                        token: null,
                        isAuthenticated: false,
                    });
                }
            },

            // 쿠키에서 인증 정보 확인
            checkAuthCookie: async () => {
                try {
                    // 쿠키에서 세션 ID와 인증 정보 확인
                    const cookies = parseCookies();
                    const sessionId = cookies['session_id']; // 백엔드에서 사용하는 세션 쿠키
                    const userCookie = cookies['user']; // 사용자 정보 쿠키
                    const tokenCookie = cookies['token']; // 토큰 쿠키
                    
                    console.debug('[useAuth] 쿠키 확인:', { sessionId, userCookie, tokenCookie });
                    
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
                                set({
                                    user: null,
                                    token: null,
                                    isAuthenticated: false
                                });
                            }
                        } catch (error) {
                            console.error('[useAuth] 사용자 정보 요청 오류:', error);
                            set({
                                user: null,
                                token: null,
                                isAuthenticated: false
                            });
                        }
                    } else if (userCookie && tokenCookie) {
                        // 세션 ID는 없지만 user와 token 쿠키가 있는 경우
                        try {
                            const userData = JSON.parse(decodeURIComponent(userCookie));
                            set({
                                user: userData,
                                token: tokenCookie,
                                isAuthenticated: true
                            });
                            //console.debug('[useAuth] 쿠키에서 사용자 정보 로드 완료:', userData);
                        } catch (error) {
                            console.error('[useAuth] 쿠키 파싱 오류:', error);
                            set({
                                user: null,
                                token: null,
                                isAuthenticated: false
                            });
                        }
                    } else {
                        console.log('[useAuth] 인증 쿠키 없음');
                        // 로컬 스토리지에 인증 정보가 있는지 확인
                        const currentUser = get().user;
                        const currentToken = get().token;
                        const currentIsAuthenticated = get().isAuthenticated;
                        
                        // 로컬 스토리지에 인증 정보가 있지만 쿠키가 없는 경우
                        if (currentUser || currentToken || currentIsAuthenticated) {
                            console.log('[useAuth] 쿠키 없음, 로컬 스토리지 인증 정보 유지');
                            // doceasy 앱에서는 로컬 스토리지 정보를 유지하며 계속 사용할 수 있도록 함
                        }
                    }
                } catch (error) {
                    console.error('[useAuth] 인증 확인 오류:', error);
                    // 오류가 발생해도 기존 상태를 유지
                }
            }
        }),
        {
            name: 'auth-storage',
            partialize: (state) => ({
                user: state.user,
                token: state.token,
                isAuthenticated: state.isAuthenticated,
            }),
        }
    )
);

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
