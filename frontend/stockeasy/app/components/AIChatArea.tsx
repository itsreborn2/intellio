'use client'

import { Suspense } from 'react'

// 컨텐츠 컴포넌트
function AIChatAreaContent() {
  return (
    <div className="ai-chat-area">
      <div className="input-area" style={{ display: 'flex', alignItems: 'center', marginTop: '4px' }}> {/* 위에 4px 여백으로 통일 */}
        <div className="stock-selector" style={{ width: '13%', marginRight: '4px' }}> {/* 우측에 4px 여백으로 통일 */}
          <select defaultValue="">
            <option value="" disabled>종목 선택</option> {/* Placeholder option */}
          </select>
        </div>
        <div className="chat-input" style={{ flex: 1, marginRight: '4px' }}> {/* 우측에 4px 여백으로 통일 */}
          <input type="text" placeholder="메세지를 입력하세요" style={{ width: 'calc(100% - 4px)' }} /> {/* 계산값도 4px로 통일 */}
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
