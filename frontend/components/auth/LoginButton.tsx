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

// OAuth 제공자별 설정
const oAuthConfigs: Record<string, IOAuthConfig> = {
  kakao: {
    auth_uri: 'https://kauth.kakao.com/oauth/authorize',
    client_id: process.env.NEXT_PUBLIC_KAKAO_CLIENT_ID || '',
    scope: 'profile_nickname account_email',
    redirect_uri: `${process.env.NEXT_PUBLIC_API_URL}/api/v1/auth/kakao/callback`
  },
  google: {
    auth_uri: 'https://accounts.google.com/o/oauth2/v2/auth',
    client_id: process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID || '',
    scope: 'email profile',
    redirect_uri: `${process.env.NEXT_PUBLIC_API_URL}/api/v1/auth/google/callback`
  },
  naver: {
    // https://nid.naver.com/oauth2.0/authorize?client_id=&redirect_uri=undefined%2Fapi%2Fv1%2Fauth%2Fnaver%2Fcallback&response_type=code&scope=name+email
    auth_uri: 'https://nid.naver.com/oauth2.0/authorize',
    client_id: process.env.NEXT_PUBLIC_NAVER_CLIENT_ID || '',
    scope: 'name email',
    redirect_uri: process.env.NEXT_PUBLIC_NAVER_REDIRECT_URI || ''
  }
};

export const LoginButton: React.FC<ILoginButtonProps> = ({ provider }) => {
    const handleLoginTest = () => {
        const config = oAuthConfigs[provider];
        console.log(`${provider} : ${config.auth_uri}`);
        console.log(`${provider} : ${config.scope}`);
        console.log(`${provider} : ${config.redirect_uri}`);
    }
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
