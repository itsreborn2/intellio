'use client'

import { useEffect } from 'react'

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string }
  reset: () => void
}) {
  useEffect(() => {
    // 에러 로깅
    console.error(error)
  }, [error])

  return (
    <div className="flex items-center justify-center min-h-screen bg-background">
      <div className="text-center">
        <h2 className="text-3xl font-bold">오류가 발생했습니다</h2>
        <p className="mt-4 text-xl">
          예상치 못한 문제가 발생했습니다.
        </p>
        <p className="mt-2 text-muted-foreground">
          {error.message || '알 수 없는 오류가 발생했습니다.'}
        </p>
        <button
          onClick={reset}
          className="inline-block mt-8 px-6 py-3 bg-primary text-primary-foreground rounded-md hover:bg-primary/90"
        >
          다시 시도
        </button>
      </div>
    </div>
  )
} 