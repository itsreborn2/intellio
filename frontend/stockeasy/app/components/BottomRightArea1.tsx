'use client'

import { Suspense } from 'react'

// 컨텐츠 컴포넌트
function BottomRightArea1Content() {
  return (
    <div className="bottom-right-area-1 bottom-area">
      {/* 하단 우측 영역 1 컨텐츠 */}
      <div className="p-2 h-full flex items-center justify-center border-t border-l border-white/40">
        하단 우측 영역 1
      </div>
    </div>
  )
}

// 메인 컴포넌트
export default function BottomRightArea1() {
  return (
    <Suspense fallback={<div className="bottom-right-area-1 bottom-area animate-pulse">
      <div className="h-full bg-gray-200 rounded"></div>
    </div>}>
      <BottomRightArea1Content />
    </Suspense>
  )
}