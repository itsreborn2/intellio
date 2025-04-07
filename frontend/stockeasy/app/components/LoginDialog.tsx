'use client'

import { useState } from 'react'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogOverlay,
  DialogPortal
} from "intellio-common/components/ui/dialog"
import { Button } from "intellio-common/components/ui/button"
import { cn } from "intellio-common/lib/utils"

interface LoginDialogProps {
  isOpen: boolean
  onOpenChange: (open: boolean) => void
}

// 커스텀 오버레이 컴포넌트
const CustomDialogOverlay = ({ className, ...props }: React.ComponentPropsWithoutRef<typeof DialogOverlay>) => (
  <DialogOverlay
    className={cn(
      "fixed inset-0 z-[10000] bg-black/80",
      className
    )}
    {...props}
  />
)

// OAuth 로그인 버튼 컴포넌트
interface LoginButtonProps {
  provider: 'google' | 'naver' | 'kakao'
  redirectTo?: 'doceasy' | 'stockeasy' | string
}

const LoginButton: React.FC<LoginButtonProps> = ({ provider, redirectTo = 'stockeasy' }) => {
  const [isLoading, setIsLoading] = useState(false)

  // 로그인 처리 함수
  const handleLogin = async () => {
    if (isLoading) return // 중복 클릭 방지
    
    try {
      setIsLoading(true)
      // 백엔드 URL을 직접 사용
      const backendUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api'
      window.location.href = `${backendUrl}/v1/auth/${provider}/login?redirectTo=${redirectTo}`
    } catch (error) {
      console.error('로그인 오류:', error)
      setIsLoading(false)
    }
  }

  // 제공자별 버튼 스타일 설정
  const getButtonStyle = () => {
    switch (provider) {
      case 'kakao':
        return 'bg-[#FEE500] text-black hover:bg-[#E6CF00]'
      case 'google':
        return 'bg-white text-black border border-gray-300 hover:bg-gray-100'
      case 'naver':
        return 'bg-[#03C75A] text-white hover:bg-[#02B350]'
      default:
        return ''
    }
  }

  // 제공자별 버튼 텍스트
  const getButtonText = () => {
    return `${provider.charAt(0).toUpperCase() + provider.slice(1)}로 로그인`
  }

  return (
    <Button
      className={`w-full mb-2 ${getButtonStyle()} rounded-xl h-12 text-base font-medium`}
      onClick={handleLogin}
      disabled={isLoading}
    >
      {isLoading ? '로그인 중...' : getButtonText()}
    </Button>
  )
}

export default function LoginDialog({ isOpen, onOpenChange }: LoginDialogProps) {
  return (
    <Dialog open={isOpen} onOpenChange={onOpenChange}>
      <DialogPortal>
        <CustomDialogOverlay />
        <DialogContent className="z-[10001] sm:max-w-[425px] bg-white dark:bg-gray-900 border border-gray-300 dark:border-gray-700 rounded-2xl">
          <DialogHeader>
            <DialogTitle className="text-center text-xl">로그인</DialogTitle>
            <DialogDescription className="text-center">
              소셜 계정으로 로그인하세요
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="flex flex-col space-y-2">
              <LoginButton provider="google" redirectTo="stockeasy" />
              {/* <LoginButton provider="kakao" redirectTo="stockeasy" /> */}
            </div>
          </div>
        </DialogContent>
      </DialogPortal>
    </Dialog>
  )
} 