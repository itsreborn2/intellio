'use client'

import { Suspense } from 'react'

// 컨텐츠 컴포넌트
function BottomCenterAreaContent() {
  return (
    <div className="bottom-center-area">
      {/* 하단 중앙 영역 컨텐츠 */}
      하단 중앙 영역 2
    </div>
  )
}

// 메인 컴포넌트
export default function BottomCenterArea() {
  return (
    <Suspense fallback={<div className="bottom-center-area animate-pulse">
      <div className="h-full bg-gray-200 rounded"></div>
    </div>}>
      <BottomCenterAreaContent />
    </Suspense>
  )
}