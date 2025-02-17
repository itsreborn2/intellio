'use client'

import { Suspense } from 'react'

// 컨텐츠 컴포넌트
function TelegramSummaryAreaContent() {
  return (
    <div className="telegram-summary-area">
      {/* 텔레그램 요약 영역 컨텐츠 */}
    </div>
  )
}

// 메인 컴포넌트
export default function TelegramSummaryArea() {
  return (
    <Suspense fallback={<div className="telegram-summary-area animate-pulse">
      <div className="h-full bg-gray-200 rounded"></div>
    </div>}>
      <TelegramSummaryAreaContent />
    </Suspense>
  )
}