"use client"

import { useState, useRef, useEffect } from "react"
import { Settings, User } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { useApp } from "@/contexts/AppContext"
import * as api from "@/services/api"

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

  // 로그인 처리 함수
  const handleLogin = () => {
    // 백엔드의 OAuth 로그인 엔드포인트로 리다이렉트
    window.location.href = `${process.env.NEXT_PUBLIC_API_URL}/api/v1/auth/${provider}/login`;
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
      //onClick={handleLogin}
      onClick={handleLogin}
    >
      {getButtonText()}
    </Button>
  );
};
