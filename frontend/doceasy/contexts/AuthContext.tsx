// frontend/contexts/AuthContext.tsx
import { createContext, useContext, useReducer, useEffect, useRef, useCallback } from 'react'
import * as api from '@/services/api'

// 사용자 정보 인터페이스 정의
interface IUser {
  id: string;
  email: string;
  name: string;
  provider: string;
  profile_image?: string;
}

// 인증 상태 인터페이스 정의
interface IAuthState {
  isAuthenticated: boolean;
  user: IUser | null;
  loading: boolean;
}

// 인증 액션 타입 정의
type AuthAction = 
  | { type: 'SET_AUTH'; payload: IUser }
  | { type: 'LOGOUT' }
  | { type: 'SET_LOADING'; payload: boolean };

// 초기 상태
const initialState: IAuthState = {
  isAuthenticated: false,
  user: null,
  loading: true
};

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

// 사용자 쿠키 파싱 함수
const parseUserCookie = (userCookie: string): IUser | null => {
  try {
    if (userCookie.includes('%')) {
      try {
        const decodedCookie = decodeURIComponent(userCookie);
        let jsonString = decodedCookie;
        if (jsonString.startsWith('"') && jsonString.endsWith('"')) {
          jsonString = jsonString.slice(1, -1).replace(/\\"/g, '"');
        }
        return JSON.parse(jsonString);
      } catch (decodeError) {
        console.error('[AuthContext] URL 디코딩 실패:', decodeError);
        return null;
      }
    }
    
    if (userCookie.startsWith('{')) {
      return JSON.parse(userCookie);
    }
    
    if (userCookie.startsWith('"') && userCookie.endsWith('"')) {
      const jsonString = userCookie.slice(1, -1).replace(/\\"/g, '"');
      return JSON.parse(jsonString);
    }
    
    return null;
  } catch (error) {
    console.error('[AuthContext] 쿠키 파싱 오류:', error);
    return null;
  }
};

// 인증 컨텍스트 생성
const AuthContext = createContext<{
  state: IAuthState;
  login: (code: string, provider: string) => Promise<void>;
  logout: () => Promise<void>;
} | null>(null);

// 인증 리듀서
const authReducer = (state: IAuthState, action: AuthAction): IAuthState => {
  switch (action.type) {
    case 'SET_AUTH':
      return {
        ...state,
        isAuthenticated: true,
        user: action.payload,
        loading: false
      };
    case 'LOGOUT':
      return {
        ...state,
        isAuthenticated: false,
        user: null,
        loading: false
      };
    case 'SET_LOADING':
      return {
        ...state,
        loading: action.payload
      };
    default:
      return state;
  }
};

// 인증 프로바이더 컴포넌트
export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [state, dispatch] = useReducer(authReducer, initialState);

  // 로그인 처리
  const login = async (code: string, provider: string) => {
    try {
      dispatch({ type: 'SET_LOADING', payload: true });
      const response = await api.socialLogin(code, provider);
      dispatch({ type: 'SET_AUTH', payload: response.user });
    } catch (error) {
      console.error('Login failed:', error);
      dispatch({ type: 'LOGOUT' });
    }
  };

  // 로그아웃 처리
  const logout = async () => {
    try {
      await api.logout();
      dispatch({ type: 'LOGOUT' });
    } catch (error) {
      console.error('Logout failed:', error);
    }
  };

  // 초기 인증 상태 확인 (쿠키 우선, API 폴백)
  useEffect(() => {
    const checkAuth = async () => {
      try {
        // 먼저 쿠키에서 사용자 정보 확인
        const cookies = parseCookies();
        const userCookie = cookies['user'];
        const tokenCookie = cookies['token'];
        
        console.debug('[AuthContext] 쿠키 확인:', { 
          userCookie: userCookie ? '있음' : '없음',
          tokenCookie: tokenCookie ? '있음' : '없음'
        });
        
        // 쿠키에 사용자 정보가 있으면 바로 사용
        if (userCookie && tokenCookie) {
          const userData = parseUserCookie(userCookie);
          if (userData) {
            console.log('[AuthContext] 쿠키에서 사용자 정보 로드:', userData);
            dispatch({ type: 'SET_AUTH', payload: userData });
            return;
          }
        }
        
        // 쿠키가 없거나 파싱 실패시에만 API 호출
        console.log('[AuthContext] 쿠키 없음, API로 인증 확인');
        const response = await api.checkAuth();
        if (response.user) {
          dispatch({ type: 'SET_AUTH', payload: response.user });
        } else {
          dispatch({ type: 'LOGOUT' });
        }
      } catch (error) {
        console.log('[AuthContext] 인증 확인 실패, 로그아웃 처리');
        dispatch({ type: 'LOGOUT' });
      }
    };

    checkAuth();
  }, []);

  return (
    <AuthContext.Provider value={{ state, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
};

// 커스텀 훅
export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};