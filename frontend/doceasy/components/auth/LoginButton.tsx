//"use client"

import { useState} from "react"
import { Button } from "intellio-common/components/ui/button"

// frontend/components/auth/LoginButton.tsx
interface ILoginButtonProps {
  provider: 'google' | 'naver' | 'kakao';
}

// OAuth 설정 정보 인터페이스 정의
interface IOAuthConfig {
  auth_uri: string;
  client_id: string;
  scope: string;
  redirect_uri: string;
}


export const LoginButton: React.FC<ILoginButtonProps> = ({ provider }) => {
  const [isLoading, setIsLoading] = useState(false);

  // 로그인 처리 함수
  const handleLogin = async () => {
    if (isLoading) return; // 중복 클릭 방지
    
    try {
      setIsLoading(true);
      // 백엔드 URL을 직접 사용 (Next.js 리다이렉트 우회)
      const backendUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api';
      window.location.href = `${backendUrl}/v1/auth/${provider}/login`;
    } catch (error) {
      console.error('Login error:', error);
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
