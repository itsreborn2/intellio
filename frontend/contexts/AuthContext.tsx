// frontend/contexts/AuthContext.tsx
import { createContext, useContext, useReducer, useEffect, useRef, useCallback } from 'react'
import * as api from '@/services/api'

// 사용자 정보 인터페이스 정의
interface IUser {
  id: string;
  email: string;
  name: string;
  provider: string;
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

  // 초기 인증 상태 확인
  useEffect(() => {
    const checkAuth = async () => {
      try {
        const response = await api.checkAuth();
        if (response.user) {
          dispatch({ type: 'SET_AUTH', payload: response.user });
        } else {
          dispatch({ type: 'LOGOUT' });
        }
      } catch (error) {
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