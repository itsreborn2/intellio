import { create } from 'zustand';
import { IOAuthResponse, IOAuthUser } from '@/types/auth';
import { persist } from 'zustand/middleware';

interface AuthState {
    user: IOAuthUser | null;
    token: string | null;
    email: string | null;
    name: string | null;
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
            isAuthenticated: false,

            login: (data: IOAuthResponse) => {
                // 토큰을 로컬 스토리지에 저장
                localStorage.setItem('token', data.token);
                
                set({
                    user: data.user,
                    token: data.token,
                    email: data.user.email,
                    name: data.user.name,
                    isAuthenticated: true,
                });
            },

            logout: () => {
                // 토큰 제거
                localStorage.removeItem('token');
                
                set({
                    user: null,
                    token: null,
                    email: null,
                    name: null,
                    isAuthenticated: false,
                });
            },
        }),
        {
            name: 'auth-storage', // localStorage에 저장될 키 이름
            partialize: (state) => ({
                user: state.user,
                token: state.token,
                email: state.email,
                name: state.name,
                isAuthenticated: state.isAuthenticated,
            }),
        }
    )
);
