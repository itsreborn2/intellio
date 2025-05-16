'use client';

import React from 'react';
import ClientFooter from '@/app/components/ClientFooter';

export default function SharedChatLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="w-full h-full flex flex-col">
      {/* 스크롤바 스타일 */}
      <style jsx global>{`
        /* 메인 영역 스크롤 스타일 */
        main {
          overflow-y: auto !important;
          overflow-x: hidden !important;
          /* 상단 헤더(44px)와 하단 채팅 입력 영역(24px)을 뺀 높이 */
          height: calc(100vh - 44px - 24px) !important;
          max-height: 100vh !important;
          width: 100% !important;
          scrollbar-width: auto;
          scrollbar-color: rgba(0, 0, 0, 0.2) transparent;
          padding: 0 !important;
        }
        
        /* 스크롤바 스타일 추가 */
        main::-webkit-scrollbar {
          width: 4px;
          height: 4px;
        }
        
        main::-webkit-scrollbar-thumb {
          background-color: rgba(0, 0, 0, 0.2);
          border-radius: 4px;
        }
        
        main::-webkit-scrollbar-track {
          background-color: transparent;
        }
      `}</style>
        {children}
      {/* 푸터 - 고정 위치에 배치 */}
      <div className="fixed bottom-0 left-0 md:left-[59px] w-full md:w-[calc(100%-59px)] z-10 bg-[rgba(244,244,244,0.95)]">
        <ClientFooter />
      </div>
    </div>
  );
} 