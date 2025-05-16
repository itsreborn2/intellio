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
      
      {/* 헤더 영역 */}
      <div className="fixed top-0 left-0 w-full h-[44px] bg-[#F4F4F4] z-40 flex items-center px-4">
        <div className="flex justify-between items-center w-full">
          <div className="flex items-center">
            <div className="text-lg font-semibold">StockEasy 공유 채팅</div>
          </div>
        </div>
      </div>

      {/* 본문 영역 - content-container 제거하고 직접 children 렌더링 */}
      <main className="fixed top-[44px] bottom-0 right-0 left-0 md:left-[59px]">
        {children}
      </main>
      
      {/* 푸터 - 고정 위치에 배치 */}
      <div className="fixed bottom-0 left-0 md:left-[59px] w-full md:w-[calc(100%-59px)] z-10 bg-[rgba(244,244,244,0.95)]">
        <ClientFooter />
      </div>
    </div>
  );
} 