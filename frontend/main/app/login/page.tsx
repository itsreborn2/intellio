'use client'

import { useEffect, Suspense } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { LoginButton } from '@/components/auth/LoginButton'
import { useAuth, useAuthCheck } from '@/hooks/useAuth'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import Link from 'next/link'

function LoginContent() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const { isAuthenticated, setRedirectTo } = useAuth()
  
  // 쿠키 기반 인증 상태 확인
  useAuthCheck();
  
  useEffect(() => {
    // 이미 로그인한 상태면 메인 페이지로 리다이렉트
    if (isAuthenticated) {
      const redirectTo = searchParams.get('redirectTo') || '/'
      
      // 다른 서비스로 리다이렉션
      if (redirectTo === 'doceasy' || redirectTo === 'stockeasy') {
        window.location.href = `https://${redirectTo}.intellio.kr`;
        return;
      }
      
      // 메인 사이트 내 리다이렉션
      router.push(redirectTo)
      return
    }
    
    // 로그인 후 리다이렉트할 경로 저장
    const redirectTo = searchParams.get('redirectTo')
    if (redirectTo) {
      console.log(`redirectTo: ${redirectTo}`)
      setRedirectTo(redirectTo)
    }
  }, [isAuthenticated, router, searchParams, setRedirectTo])

  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-b from-background via-background/90 to-background">
      <div className="relative z-10">
        <div className="absolute right-0 top-0 h-[300px] w-[300px] bg-blue-500/10 blur-[100px]" />
        <div className="absolute bottom-0 left-0 h-[300px] w-[300px] bg-purple-500/10 blur-[100px]" />
      </div>

      <Card className="w-[400px] shadow-lg">
        <CardHeader className="text-center">
          <CardTitle className="text-2xl">Intellio 로그인</CardTitle>
          <CardDescription>
            소셜 계정으로 로그인하세요
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            <div className="flex flex-col space-y-2">
              <LoginButton 
                provider="google" 
                redirectTo={searchParams.get('redirectTo') || '/'} 
              />
              {/* <LoginButton 
                provider="naver" 
                redirectTo={searchParams.get('redirectTo') || '/'} 
              /> */}
            </div>
            <div className="text-center text-sm text-muted-foreground mt-4">
              <p className="text-xs text-muted-foreground">계속하면 다음 약관에 동의하는 것으로 간주됩니다</p>
              <Link href={`${process.env.NEXT_PUBLIC_INTELLIO_URL}/terms`} className="text-primary hover:underline">
                서비스 이용약관
              </Link>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}

export default function LoginPage() {
  return (
    <Suspense fallback={
      <div className="flex min-h-screen items-center justify-center">
        <div className="text-center">로딩 중...</div>
      </div>
    }>
      <LoginContent />
    </Suspense>
  )
} 