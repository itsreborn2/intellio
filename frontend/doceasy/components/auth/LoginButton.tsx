//"use client"

import { useState} from "react"
import { Button } from "intellio-common/components/ui/button"

// frontend/components/auth/LoginButton.tsx
interface ILoginButtonProps {
  provider: 'google' | 'naver' | 'kakao';
  redirectTo?: 'doceasy' | 'stockeasy' | string;
}

// OAuth 설정 정보 인터페이스 정의
interface IOAuthConfig {
  auth_uri: string;
  client_id: string;
  scope: string;
  redirect_uri: string;
}


export const LoginButton: React.FC<ILoginButtonProps> = ({ provider, redirectTo = 'doceasy' }) => {
  const [isLoading, setIsLoading] = useState(false);

  // 네이버 앱 감지
  const isNaverApp = (): boolean => {
    if (typeof window === 'undefined') return false;
    return /NAVER|NaverApp/i.test(window.navigator.userAgent);
  };

  // 모바일 기기 감지
  const isMobileDevice = (): boolean => {
    if (typeof window === 'undefined') return false;
    
    return /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(
      window.navigator.userAgent
    );
  };

  // 외부 브라우저 호출 (네이버 앱 전용)
  const openInExternalBrowser = (url: string) => {
    const userAgent = window.navigator.userAgent;
    
    // Chrome Custom Tabs (Android)
    if (/Android/i.test(userAgent)) {
      const chromeIntent = `intent://${url.replace(/^https?:\/\//, '')}#Intent;scheme=https;package=com.android.chrome;end`;
      try {
        window.location.href = chromeIntent;
        return true;
      } catch (e) {
        console.log('Chrome Intent 실패:', e);
      }
    }

    // 다양한 브라우저 스킴 시도
    const browserSchemes = [
      `googlechrome://navigate?url=${encodeURIComponent(url)}`,
      `firefox://open-url?url=${encodeURIComponent(url)}`,
      `samsung://internet?url=${encodeURIComponent(url)}`
    ];

    for (const scheme of browserSchemes) {
      try {
        window.location.href = scheme;
        return true;
      } catch (e) {
        console.log(`브라우저 스킴 실패 (${scheme}):`, e);
      }
    }

    // 최종 폴백: 현재 탭에서 이동
    window.location.href = url;
    return true;
  };

  // 로그인 처리 함수
  const handleLogin = async () => {
    if (isLoading) return; // 중복 클릭 방지
    
    try {
      setIsLoading(true);
      // 절대 URL 생성 (새 탭에서 접근할 때 필요)
      let backendUrl: string;
      
      if (typeof window !== 'undefined') {
        // 브라우저 환경에서는 현재 도메인 + /api 사용
        const currentDomain = window.location.origin;
        backendUrl = `${currentDomain}/api`;
      } else {
        // 서버 환경에서는 환경변수 또는 기본값 사용
        backendUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api';
      }
      
      const oauthUrl = `${backendUrl}/v1/auth/${provider}/login?redirectTo=${redirectTo}`;
      console.log('OAuth URL:', oauthUrl); // 디버깅용
      
      // 네이버 앱에서의 특별 처리
      if (isNaverApp()) {
        openInExternalBrowser(oauthUrl);
        return;
      }
      
      // 일반적인 처리 - 모든 환경에서 단순 이동 (네이버 앱 제외)
      window.location.href = oauthUrl;
    } catch (error) {
      console.error('Login error:', error);
      setIsLoading(false);
    }
  };

  // 제공자별 버튼 스타일 설정
  const getButtonStyle = () => {
    switch (provider) {
      case 'kakao':
        return 'bg-[#FEE500] text-black hover:bg-[#E6CF00]';
      case 'google':
        return 'bg-white text-black border border-gray-300 hover:bg-gray-100';
      case 'naver':
        return 'bg-[#03C75A] text-white hover:bg-[#02B350]';
      default:
        return '';
    }
  };

  // 제공자별 버튼 텍스트
  const getButtonText = () => {
    return `${provider.charAt(0).toUpperCase() + provider.slice(1)}로 로그인`;
  };

  return (
    <Button
      className={`w-full mb-2 ${getButtonStyle()}`}
      onClick={handleLogin}
      disabled={isLoading}
    >
      {isLoading ? '로그인 중...' : getButtonText()}
    </Button>
  );
};
