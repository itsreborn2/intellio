"use client"

import Link from "next/link"
import { useRouter } from "next/navigation"
import { Button } from "@/components/ui/button"
import { Send, User } from "lucide-react"
import { useAuth, useAuthCheck } from "@/hooks/useAuth"
import { useEffect } from "react"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger
} from "@/components/ui/dropdown-menu"

export default function Navbar() {
  const router = useRouter()
  const { isAuthenticated, setRedirectTo, user, logout } = useAuth()
  
  // 쿠키 기반 인증 상태 확인
  useAuthCheck();

  // 디버깅을 위한 로그 출력
  useEffect(() => {
    console.log('[Navbar] 인증 상태:', isAuthenticated, '사용자:', user);
  }, [isAuthenticated, user]);

  // 서비스 이동 시 로그인 상태 확인
  const handleServiceNavigation = (service: 'doceasy' | 'stockeasy') => {
    if (isAuthenticated) {
      // 로그인 상태면 해당 서비스로 바로 이동 (토큰과 사용자 정보 포함)
      const { token, user } = useAuth.getState();
      if (token && user) {
        // 사용자 정보 인코딩
        const encodedUser = encodeURIComponent(JSON.stringify(user));
        // 토큰을 URL 파라미터로 포함
        window.location.href = `https://${service}.intellio.kr/auto-login?token=${token}&user=${encodedUser}`;
      } else {
        // 토큰이 없으면 그냥 이동
        window.location.href = `https://${service}.intellio.kr`;
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

  return (
    <header className="sticky top-0 z-50 w-full border-b border-border/40 bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <div className="container flex h-14 max-w-screen-2xl items-center">
        <Link href="/" className="mr-6 flex items-center space-x-2">
          <span className="font-bold">Intellio</span>
        </Link>
        <nav className="flex flex-1 items-center space-x-6 text-sm font-medium">
          <button 
            onClick={() => handleServiceNavigation('doceasy')} 
            className="transition-colors hover:text-primary"
          >
            DocEasy
          </button>
          <button 
            onClick={() => handleServiceNavigation('stockeasy')} 
            className="transition-colors hover:text-primary"
          >
            StockEasy
          </button>
          <Link href="/about" className="transition-colors hover:text-primary">
            About Us
          </Link>
        </nav>
        <div className="flex items-center space-x-4">
          <Link href="https://t.me/maddingStock" target="_blank" rel="noreferrer">
            <Button variant="ghost" size="icon">
              <Send className="h-4 w-4" />
              <span className="sr-only">Telegram</span>
            </Button>
          </Link>
          {isAuthenticated ? (
            <div className="flex items-center gap-2">
              {user && <span className="text-sm text-gray-600">{user.email}</span>}
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button size="sm" variant="outline" className="flex items-center gap-1">
                    <User className="h-4 w-4" />
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
          ) : (
            <Button size="sm" onClick={() => router.push('/login')}>
              로그인
            </Button>
          )}
        </div>
      </div>
    </header>
  )
}

