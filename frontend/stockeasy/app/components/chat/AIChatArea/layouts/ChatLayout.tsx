/**
 * ChatLayout.tsx
 * 채팅 레이아웃 컴포넌트
 */
'use client';

import React, { ReactNode } from 'react';

interface ChatLayoutProps {
  children: ReactNode;
  isSidebarOpen?: boolean;
}

export function ChatLayout({ children, isSidebarOpen = false }: ChatLayoutProps) {
  return (
    <div className="w-full h-full flex flex-col">
      {/* 스크롤바 스타일 */}
      <style jsx global>{`
        /* content-container 스타일 재정의 */
        .content-container {
          overflow-y: auto !important;
          overflow-x: hidden !important;
          /* 상단 헤더(44px)와 하단 채팅 입력 영역(60px)을 뺀 높이 */
          height: calc(100vh - 44px - 60px) !important;
          max-height: 100vh !important;
          width: 100% !important;
          max-width: 100% !important;
          scrollbar-width: auto;
          scrollbar-color: rgba(0, 0, 0, 0.2) transparent;
          padding: 0 !important;
        }
        

      `}</style>
      
      {/* children을 직접 렌더링 */}
      {children}
      
      {/* 푸터 (기존 그대로 유지) */}
      <div className="fixed bottom-0 left-[59px] w-[calc(100%-59px)] text-center py-[5px] z-10 bg-[rgba(244,244,244,0.95)] text-[13px] text-[#888] font-light">
        2025 Intellio Corporation All Rights Reserved.
      </div>
    </div>
  );
}

export default ChatLayout; 