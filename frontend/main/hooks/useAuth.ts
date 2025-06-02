import { create } from 'zustand';
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
    isAuthenticated: boolean;
    redirectTo: string | null; // 로그인 후 리디렉션할 경로
    setUser: (user: User | null) => void;
    setRedirectTo: (path: string | null) => void;
    login: (userData: User) => void;
    logout: () => Promise<void>;
    checkAuth: () => Promise<void>; // 간단한 인증 확인 함수
    initializeFromCookies: () => void; // 쿠키에서 초기 상태 설정
    clearAuthState: () => void;
}

// 쿠키 파싱 유틸리티 함수
const parseCookies = () => {
    if (typeof window === 'undefined') return {};
    
    return document.cookie.split(';').reduce((cookies, cookie) => {
        const [name, value] = cookie.trim().split('=');
        if (name && value) {
            cookies[name] = value;
        }
        return cookies;
    }, {} as Record<string, string>);
};

// 백엔드 API URL
const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api';

export const useAuth = create<AuthState>()((set, get) => ({
    user: null,
    isAuthenticated: false,
    redirectTo: null,

    setUser: (user) => {
        set({ 
            user, 
            isAuthenticated: !!user 
        });
        console.log('[useAuth] 사용자 정보 설정:', user, '인증 상태:', !!user);
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
            // 백엔드 로그아웃 API 호출
            await fetch(`${API_URL}/v1/auth/logout`, {
                method: 'POST',
                credentials: 'include', // 쿠키 포함
            });
            
            // 상태 초기화 함수 호출
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
            isAuthenticated: false,
            redirectTo: null
        });
        
        // 브라우저 환경에서만 실행
        if (typeof window !== 'undefined') {
            // 인증 확인 시간 기록도 삭제
            localStorage.removeItem('auth-last-check-time');
            console.log('[useAuth] 인증 확인 시간 기록 삭제');
        }
        
        console.log('[useAuth] 인증 상태 초기화 완료');
    },

    // 쿠키에서 초기 상태 설정
    initializeFromCookies: () => {
        try {
            const cookies = parseCookies();
            const userCookie = cookies['user'];
            const tokenCookie = cookies['token'];
            
            console.log('[useAuth] 쿠키 초기화 확인:', { 
                userCookie: userCookie ? '있음' : '없음',
                tokenCookie: tokenCookie ? '있음' : '없음'
            });

            if (userCookie && tokenCookie) {
                try {
                    const decodedUserCookie = decodeURIComponent(userCookie);
                    
                    if (decodedUserCookie && decodedUserCookie.trim() !== '') {
                        console.debug('[useAuth] 디코딩된 사용자 쿠키:', decodedUserCookie);
                        
                        let jsonString = decodedUserCookie;
                        if (jsonString.startsWith('"') && jsonString.endsWith('"')) {
                            jsonString = jsonString.slice(1, -1).replace(/\\"/g, '"');
                            console.debug('[useAuth] 따옴표 제거 후 문자열:', jsonString);
                        }
                        
                        const userData = JSON.parse(jsonString);
                        set({
                            user: userData,
                            isAuthenticated: true
                        });
                        console.log('[useAuth] 쿠키에서 사용자 정보 로드 완료:', userData);
                    } else {
                        console.error('[useAuth] 디코딩된 사용자 쿠키가 비어있음');
                        get().clearAuthState();
                    }
                } catch (error) {
                    console.error('[useAuth] 쿠키 파싱 오류:', error);
                    get().clearAuthState();
                }
            } else {
                console.log('[useAuth] 인증 쿠키 없음, 상태 초기화');
                get().clearAuthState();
            }
        } catch (error) {
            console.error('[useAuth] 쿠키 초기화 오류:', error);
            get().clearAuthState();
        }
    },
    
    // 쿠키 기반 인증 확인 (API 호출만 사용)
    checkAuth: async () => {
        try {
            console.log('[useAuth] 인증 상태 확인 시작');
            
            // 쿠키 확인 - 쿠키가 없고 현재 인증되지 않은 상태라면 API 호출 스킵
            const cookies = parseCookies();
            const userCookie = cookies['user'];
            const tokenCookie = cookies['token'];
            const currentState = get();
            
            if (!userCookie && !tokenCookie && !currentState.isAuthenticated) {
                console.log('[useAuth] 쿠키 없고 비인증 상태 - API 호출 스킵');
                return;
            }
            
            const response = await fetch(`${API_URL}/v1/auth/me`, {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json'
                },
                credentials: 'include', // httponly 쿠키 자동 포함
            });
            
            if (response.ok) {
                const userData = await response.json();
                set({
                    user: userData.user || userData,
                    isAuthenticated: true
                });
                console.log('[useAuth] 인증 확인 성공:', userData.user?.email || userData.email);
            } else {
                console.log('[useAuth] 인증 실패, 상태 초기화:', response.status);
                get().clearAuthState();
            }
        } catch (error) {
            console.error('[useAuth] 인증 확인 오류:', error);
            get().clearAuthState();
        }
    }
}));

// 중복 호출 방지를 위한 전역 플래그
let isInitializing = false;
let initializationPromise: Promise<void> | null = null;

// 쿠키 기반 인증 상태 확인을 위한 훅
export const useAuthCheck = () => {
    const { checkAuth, initializeFromCookies, isAuthenticated } = useAuth();
    
    // 마지막 인증 확인 시간을 체크하여 시간이 지났는지 확인
    const shouldCheckAuth = () => {
        if (typeof window === 'undefined') return false;
        
        // 로그아웃 상태에서는 체크할 필요 없음
        if (!isAuthenticated) return false;
        
        const lastCheckTime = localStorage.getItem('auth-last-check-time');
        if (!lastCheckTime) return true;
        
        const now = Date.now();
        // 로그인 상태에서만 체크 (6시간)
        const checkInterval = 60 * 60 * 1000 * 6; // 6시간
        
        return (now - parseInt(lastCheckTime)) > checkInterval;
    };
    
    // 인증 확인 실행 및 시간 기록
    const performAuthCheck = () => {
        if (typeof window !== 'undefined') {
            localStorage.setItem('auth-last-check-time', Date.now().toString());
        }
        checkAuth();
    };

    // 초기화 함수 (중복 실행 방지)
    const initializeAuth = async () => {
        if (isInitializing) {
            // 이미 초기화 중이면 해당 Promise를 기다림
            if (initializationPromise) {
                await initializationPromise;
            }
            return;
        }

        isInitializing = true;
        initializationPromise = new Promise<void>((resolve) => {
            // 페이지 로드 시 즉시 쿠키에서 상태 초기화
            initializeFromCookies();
            
            // 시간이 지났을 때만 API로 인증 확인
            if (shouldCheckAuth()) {
                setTimeout(() => {
                    performAuthCheck();
                    resolve();
                }, 1000); // 1초 후에 실행 (쿠키 초기화 후)
            } else {
                resolve();
            }
        });

        await initializationPromise;
        isInitializing = false;
        initializationPromise = null;
    };
    
    useEffect(() => {
        initializeAuth();
        
        // 로그인 상태일 때만 주기적 확인 설정
        if (isAuthenticated) {
            const checkInterval = 21600000; // 6시간마다 (6 * 60 * 60 * 1000)
                
            const intervalId = setInterval(() => {
                if (shouldCheckAuth()) {
                    performAuthCheck();
                }
            }, checkInterval);
            
            return () => clearInterval(intervalId);
        }
        
        // 로그아웃 상태에서는 주기적 체크 없음
        return () => {};
    }, [checkAuth, initializeFromCookies, isAuthenticated]); // isAuthenticated 의존성 추가
    
    return { isAuthenticated };
}; 