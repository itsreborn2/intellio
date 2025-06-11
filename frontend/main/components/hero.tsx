"use client"

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { Button } from "@/common/components/ui/button" // Button 컴포넌트 import
import { useAuth, useAuthCheck } from "@/hooks/useAuth"
import { useState, useEffect } from 'react';
import { Loader2 } from 'lucide-react';

const doceasyUrl = process.env.NEXT_PUBLIC_DOCEASY_URL
const stockeasyUrl = process.env.NEXT_PUBLIC_STOCKEASY_URL
console.log('process.env.NEXT_PUBLIC_ENV : ', process.env.NEXT_PUBLIC_ENV)
console.log('process.env.NEXT_PUBLIC_USE_SERVER_FRONTEND : ', process.env.NEXT_PUBLIC_USE_SERVER_FRONTEND)
console.log('doceasy : ', doceasyUrl, ', stockeasy : ', stockeasyUrl)

export default function Hero() {
  const router = useRouter()
  const { isAuthenticated, setRedirectTo } = useAuth()
  const [isAuthLoading, setIsAuthLoading] = useState(true)
  
  // 쿠키 기반 인증 상태 확인
  useAuthCheck();
  
  // 인증 상태 로딩 처리
  useEffect(() => {
    // 인증 상태가 확인되면 로딩 상태를 false로 설정
    setIsAuthLoading(false);
  }, [isAuthenticated]);
  
  // 서비스 이동 시 로그인 상태 확인
  const handleServiceNavigation = (service: 'doceasy' | 'stockeasy') => {
    if (isAuthenticated) {
      // 로그인 상태면 해당 서비스로 바로 이동 (쿠키 기반)
      const domain_url = process.env.NEXT_PUBLIC_ENV === 'production' ? 'https://' : 'http://';
      let service_url
      if( process.env.NEXT_PUBLIC_ENV === 'production')
      {
        service_url = `${service}.intellio.kr`;
      }
      else
      {
        if( service === 'doceasy') service_url = `localhost:3010`;
        else if( service === 'stockeasy') service_url = `localhost:3020`;
      }
      
      // 쿠키가 자동으로 전달되므로 토큰 파라미터 불필요
      window.location.href = `${domain_url}${service_url}`;
    } else {
      // 비로그인 상태면 로그인 페이지로 이동 후 리디렉션
      setRedirectTo(service);
      router.push(`/login?redirectTo=${service}`);
    }
  }
  
  // 서비스 버튼 렌더링
  const renderServiceButton = (service: 'doceasy' | 'stockeasy', label: string, gradientClass: string) => {
    const buttonContent = isAuthLoading ? (
      <>
        <Loader2 className="h-5 w-5 animate-spin mr-2" />
        
      </>
    ) : label;
    
    return (
      <span 
        onClick={() => !isAuthLoading && handleServiceNavigation(service)}
        className={`relative inline-block overflow-hidden rounded-full p-[1.5px] cursor-pointer ${isAuthLoading ? 'opacity-70' : ''}`}
      >
        <span className={`absolute inset-[-1000%] animate-[spin_2s_linear_infinite] ${gradientClass}`} />
        <Button 
          size="lg" 
          className="relative rounded-full bg-background px-14 py-6 text-xl font-semibold leading-none tracking-tight inline-flex h-20 w-full cursor-pointer items-center justify-center text-foreground hover:bg-accent/10 transition-colors"
          disabled={isAuthLoading}
        >
          {buttonContent}
        </Button>
      </span>
    );
  };
  
  return (
    <section className="container relative flex min-h-[calc(100vh-6rem)] max-w-screen-2xl flex-col items-center justify-center space-y-10 pt-12 pb-8 mt-10 text-center md:pt-16 md:pb-12">
      <div className="absolute inset-0 bg-radial-gradient from-primary to-accent opacity-10 blur-xl"></div>
      <div className="relative space-y-3">
        <h1 className="bg-gradient-to-br from-foreground from-30% via-foreground/90 to-foreground/70 bg-clip-text text-4xl font-bold tracking-tight text-transparent sm:text-5xl md:text-6xl lg:text-7xl leading-tight">
  전업 투자자들이 직접 만든 AI
  <span className="block mt-[0.5em] leading-tight">스탁이지</span>
  <span className="block mt-[0.5em] leading-loose text-[40%] font-normal ">실전 투자에 필요한 정보로 당신의 리서치 시간을 줄여줍니다.</span>
</h1>
      </div>
      <div className="relative flex gap-6 justify-center mt-8">
        {renderServiceButton(
          'stockeasy', 
          '스탁이지 무료체험 시작하기',
          'bg-[conic-gradient(from_90deg_at_50%_50%,#E2CBFF_0%,#393BB2_50%,#E2CBFF_100%)]'
        )}
      </div>
    </section>
  )
}
