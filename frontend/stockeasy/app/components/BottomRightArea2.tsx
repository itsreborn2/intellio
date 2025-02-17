'use client'

import { Suspense } from 'react'

// 컨텐츠 컴포넌트
function BottomRightArea2Content() {
  return (
    <div className="bottom-right-area-2">
      {/* 하단 우측 영역 2 컨텐츠 */}
    </div>
  )
}

// 메인 컴포넌트
export default function BottomRightArea2() {
  return (
    <Suspense fallback={<div className="bottom-right-area-2 animate-pulse">
      <div className="h-full bg-gray-200 rounded"></div>
    </div>}>
      <BottomRightArea2Content />
    </Suspense>
  )
}