"use client"

import Link from "next/link"
import { useRouter } from "next/navigation"
import { Button } from "@/components/ui/button"
import { Send, User, Loader2 } from "lucide-react"
import { useAuth, useAuthCheck } from "@/hooks/useAuth"
import { useEffect, useState } from "react"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger
} from "@/components/ui/dropdown-menu"
import {
  Avatar,
  AvatarFallback,
  AvatarImage
} from "@/components/ui/avatar"

export default function Navbar() {
  const router = useRouter()
  const { isAuthenticated, setRedirectTo, user, logout } = useAuth()
  const [isAuthLoading, setIsAuthLoading] = useState(true)
  
  // 쿠키 기반 인증 상태 확인
  useAuthCheck();

  // 디버깅을 위한 로그 출력 및 로딩 상태 관리
  useEffect(() => {
    console.log('[Navbar] 인증 상태:', isAuthenticated, '사용자:', user);
    // 인증 상태가 확인되면 로딩 상태를 false로 설정
    setIsAuthLoading(false);
  }, [isAuthenticated, user]);

  // 서비스 이동 시 로그인 상태 확인
  const handleServiceNavigation = (service: 'doceasy' | 'stockeasy') => {
    if (isAuthenticated) {
      // 로그인 상태면 해당 서비스로 바로 이동 (토큰과 사용자 정보 포함)
      const { token, user } = useAuth.getState();
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
      if (token && user) {
        // 사용자 정보 인코딩
        const encodedUser = encodeURIComponent(JSON.stringify(user));
        // 토큰을 URL 파라미터로 포함
        window.location.href = `${domain_url}${service_url}/auto-login?token=${token}&user=${encodedUser}`;
      } else {
        // 토큰이 없으면 그냥 이동
        window.location.href = `${domain_url}${service_url}`;
      }
    } else {
      // 비로그인 상태면 로그인 페이지로 이동 후 리디렉션
      setRedirectTo(service);
      router.push(`/login?redirectTo=${service}`);
    }
  }

  // 로그아웃 처리
  const handleLogout = async () => {
    try {
      await logout();
      console.log('[Navbar] 로그아웃 완료');
      // 로그아웃 후 홈페이지로 리다이렉션
      router.push('/');
    } catch (error) {
      console.error('[Navbar] 로그아웃 실패:', error);
    }
  }

  // 인증 버튼 렌더링 함수
  const renderAuthButton = () => {
    if (isAuthLoading) {
      return (
        <Button size="sm" variant="ghost" disabled>
          <Loader2 className="h-4 w-4 animate-spin mr-2" />
        </Button>
      );
    }

    if (isAuthenticated) {
      const userInitials = user?.name ? user.name.substring(0, 2).toUpperCase() : 'U';
      
      return (
        <div className="flex items-center gap-2">
          {user && <span className="text-sm text-gray-600">{user.email}</span>}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button size="sm" variant="outline" className="flex items-center gap-1">
                <Avatar className="h-6 w-6">
                  {user?.profile_image ? (
                    <AvatarImage src={user.profile_image} alt={user.name} />
                  ) : (
                    <AvatarFallback>{userInitials}</AvatarFallback>
                  )}
                </Avatar>
                <span>내 계정</span>
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem onClick={handleLogout}>
                로그아웃
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      );
    }

    return (
      <Button size="sm" onClick={() => router.push('/login?redirectTo=/')}>
        로그인
      </Button>
    );
  };

  return (
    <header className="sticky top-0 z-50 w-full border-b border-border/40 bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <div className="container flex h-14 max-w-screen-2xl items-center">
        <Link href="/" className="mr-6 flex items-center space-x-2">
          <span className="font-bold">Intellio</span>
        </Link>
        <Link href="/about" className="text-sm font-medium text-muted-foreground transition-colors hover:text-primary mr-4">
          About
        </Link>
        <Link href="/info" className="text-sm font-medium text-muted-foreground transition-colors hover:text-primary mr-4">
          Info
        </Link>
        <span
          onClick={() => handleServiceNavigation('doceasy')}
          className="text-sm font-medium text-muted-foreground transition-colors hover:text-primary mr-4 cursor-pointer"
        >
          DocEasy
        </span>
        <div className="flex-1"></div>
        <div className="flex items-center space-x-4">
          <Link href="https://t.me/maddingStock" target="_blank" rel="noreferrer">
            <Button variant="ghost" size="icon">
              <Send className="h-4 w-4" />
              <span className="sr-only">Telegram</span>
            </Button>
          </Link>
          {renderAuthButton()}
        </div>
      </div>
    </header>
  )
}

