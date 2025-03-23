/**
 * OAuth 로그인 응답 인터페이스
 */
export interface IOAuthLoginResponse {
  user: {
    id: string;
    email: string;
    name: string;
    provider: string;
  };
  token: string;
}

/**
 * 로그인 요청 인터페이스
 */
export interface ILoginRequest {
  username: string;
  password: string;
}

/**
 * 로그인 응답 인터페이스
 */
export interface ILoginResponse {
  success: boolean;
  userId?: string;
  error?: string;
  message?: string;
} 