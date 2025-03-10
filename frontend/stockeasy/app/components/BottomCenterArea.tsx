'use client'

import { Suspense } from 'react'

// 컨텐츠 컴포넌트
function BottomCenterAreaContent() {
  return (
    <div className="bottom-center-area bottom-area">
      {/* 하단 중앙 영역 컨텐츠 */}
      <div className="p-2 h-full flex items-center justify-center border-t border-l border-white/40">
        하단 중앙 영역 2
      </div>
    </div>
  )
}

// 메인 컴포넌트
export default function BottomCenterArea() {
  return (
    <Suspense fallback={<div className="bottom-center-area bottom-area animate-pulse">
      <div className="h-full bg-gray-200 rounded"></div>
    </div>}>
      <BottomCenterAreaContent />
    </Suspense>
  )
}