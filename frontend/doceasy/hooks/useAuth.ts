import { create } from 'zustand';
import { IOAuthResponse, IOAuthUser } from '@/types/auth';
import { persist } from 'zustand/middleware';
import * as api from '@/services/api';

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
}

export const useAuth = create<AuthState>()(
    persist(
        (set) => ({
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
