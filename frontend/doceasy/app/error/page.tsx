'use client'

import { Suspense } from 'react'
import { Button } from "intellio-common/components/ui/button"
import { useRouter } from "next/navigation"

// 에러 컨텐츠 컴포넌트
function ErrorContent() {
  const router = useRouter()

  return (
    <div className="flex h-screen flex-col items-center justify-center">
      <div className="text-center">
        <h1 className="text-4xl font-bold text-red-600 mb-4">인증 오류</h1>
        <p className="text-lg text-gray-600 mb-8">
          로그인이 필요한 서비스입니다.
        </p>
        <div className="space-x-4">
          <Button
            onClick={() => router.push('/auth/login')}
            className="bg-primary hover:bg-primary/90"
          >
            로그인하기
          </Button>
          <Button
            variant="outline"
            onClick={() => router.push('/')}
          >
            홈으로 가기
          </Button>
        </div>
      </div>
    </div>
  )
}

// Page 컴포넌트
export default function ErrorPage() {
  return (
    <Suspense fallback={<div>Loading...</div>}>
      <ErrorContent />
    </Suspense>
  )
} 