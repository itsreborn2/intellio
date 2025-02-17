'use client'

import { Suspense } from 'react'

// 컨텐츠 컴포넌트
function AIChatAreaContent() {
  return (
    <div className="ai-chat-area">
      <div className="input-area" style={{ display: 'flex', alignItems: 'center' }}>
        <div className="stock-selector" style={{ width: '13%' }}> {/* Fixed width reduced by another 20% */}
          <select defaultValue="">
            <option value="" disabled>종목 선택</option> {/* Placeholder option */}
          </select>
        </div>
        <div className="chat-input" style={{ flex: 1 }}> {/* chat-input takes remaining space */}
          <input type="text" placeholder="메세지를 입력하세요" />
        </div>
      </div>
      {/* AI 채팅 영역 */}
    </div>
  );
}

// 메인 컴포넌트
export default function AIChatArea() {
  return (
    <Suspense fallback={<div className="ai-chat-area animate-pulse">
      <div className="h-10 bg-gray-200 rounded"></div>
    </div>}>
      <AIChatAreaContent />
    </Suspense>
  );
}
