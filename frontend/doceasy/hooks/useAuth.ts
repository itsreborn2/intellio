import { create } from 'zustand';
import { IOAuthResponse, IOAuthUser } from '@/types/auth';
import { persist } from 'zustand/middleware';

interface AuthState {
    user: IOAuthUser | null;
    token: string | null; // Google, Kakao, Naver OAuth 토큰. 로그인 성공 시 서버에서 발행한 JWT 토큰.
    email: string | null;
    name: string | null;
    provider: string | null;
    isAuthenticated: boolean;
    login: (data: IOAuthResponse) => void;
    logout: () => void;
}

export const useAuth = create<AuthState>()(
    persist(
        (set) => ({
            user: null,
            token: null,
            email: null,
            name: null,
            provider: null,
            isAuthenticated: false,

            login: (data: IOAuthResponse) => {
                // 토큰을 로컬 스토리지에 저장
                localStorage.setItem('token', data.token);
                
                // user 객체가 있는 경우
                if (data.user) {
                    set({
                        user: data.user,
                        token: data.token,
                        email: data.user.email,
                        name: data.user.name,
                        provider: data.user.provider,
                        isAuthenticated: true,
                    });
                } 
                // 쿠키에서 user 정보를 가져오는 경우
                else {
                    const cookies = document.cookie.split(';').reduce((acc, cookie) => {
                        const [key, value] = cookie.trim().split('=');
                        try {
                            acc[key] = JSON.parse(decodeURIComponent(value));
                        } catch {
                            acc[key] = decodeURIComponent(value);
                        }
                        return acc;
                    }, {} as Record<string, any>);

                    if (cookies.user) {
                        const user = cookies.user as IOAuthUser;
                        set({
                            user,
                            token: data.token,
                            email: user.email,
                            name: user.name,
                            provider: user.provider,
                            isAuthenticated: true,
                        });
                    }
                }
            },

            logout: async () => {
                try {
                    // 백엔드 로그아웃 API 호출
                    await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/v1/auth/logout`, {
                        method: 'POST',
                        credentials: 'include'
                    });
                } catch (error) {
                    console.error('Logout error:', error);
                }

                // 토큰 제거
                localStorage.removeItem('token');
                
                // 쿠키 제거
                document.cookie = 'token=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;';
                document.cookie = 'user=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;';
                
                set({
                    user: null,
                    token: null,
                    email: null,
                    name: null,
                    provider: null,
                    isAuthenticated: false,
                });
            },
        }),
        {
            name: 'auth-storage',
            partialize: (state) => ({
                user: state.user,
                token: state.token,
                email: state.email,
                name: state.name,
                provider: state.provider,
                isAuthenticated: state.isAuthenticated,
            }),
        }
    )
);
