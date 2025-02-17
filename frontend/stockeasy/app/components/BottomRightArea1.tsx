'use client'

import { Suspense } from 'react'

// 컨텐츠 컴포넌트
function BottomRightArea1Content() {
  return (
    <div className="bottom-right-area-1">
      {/* 하단 우측 영역 1 컨텐츠 */}
    </div>
  )
}

// 메인 컴포넌트
export default function BottomRightArea1() {
  return (
    <Suspense fallback={<div className="bottom-right-area-1 animate-pulse">
      <div className="h-full bg-gray-200 rounded"></div>
    </div>}>
      <BottomRightArea1Content />
    </Suspense>
  )
}