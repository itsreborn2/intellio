'use client'

import { Suspense } from 'react'

// 컨텐츠 컴포넌트
function BottomLeftAreaContent() {
  return (
    <div className="bottom-left-area">
      {/* 하단 좌측 영역 컨텐츠 */}
      하단 좌측 영역 1
    </div>
  )
}

// 메인 컴포넌트
export default function BottomLeftArea() {
  return (
    <Suspense fallback={<div className="bottom-left-area animate-pulse">
      <div className="h-full bg-gray-200 rounded"></div>
    </div>}>
      <BottomLeftAreaContent />
    </Suspense>
  )
}