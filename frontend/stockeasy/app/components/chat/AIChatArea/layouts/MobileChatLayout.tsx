/**
 * MobileChatLayout.tsx
 * 모바일 환경에 최적화된 채팅 레이아웃 컴포넌트
 */
'use client';

import React, { ReactNode, useEffect, useState } from 'react';
import { useIsMobile } from '../hooks';

interface MobileChatLayoutProps {
  children: ReactNode;
  isSidebarOpen?: boolean;
  isFullScreen?: boolean;
}

export function MobileChatLayout({ 
  children, 
  isSidebarOpen = false,
  isFullScreen = false
}: MobileChatLayoutProps) {
  const isMobile = useIsMobile();
  const [windowHeight, setWindowHeight] = useState<number>(0);
  const [statusBarHeight, setStatusBarHeight] = useState<number>(0);
  
  // 창 크기 및 상태바 높이 감지
  useEffect(() => {
    if (typeof window !== 'undefined') {
      setWindowHeight(window.innerHeight);
      
      // iOS 디바이스의 경우 상태바 높이를 추정
      const isIOS = /iPad|iPhone|iPod/.test(navigator.userAgent);
      setStatusBarHeight(isIOS ? 20 : 0);
      
      const handleResize = () => {
        setWindowHeight(window.innerHeight);
      };
      
      window.addEventListener('resize', handleResize);
      return () => {
        window.removeEventListener('resize', handleResize);
      };
    }
  }, []);
  
  // 개발자 도구에서도 모바일 레이아웃을 사용할 수 있도록 경고 제거
  // F12로 모바일 환경 테스트 시에도 오류가 발생하지 않도록 수정
  
  // 페이지 초기화 (body 스타일 직접 적용)
  useEffect(() => {
    // 모바일 레이아웃에 필요한 스타일을 body에 직접 적용
    document.body.style.overflow = 'hidden';
    document.body.style.position = 'fixed';
    document.body.style.width = '100%';
    document.body.style.height = '100%';
    
    // WebkitOverflowScrolling은 타입스크립트에서 직접 접근할 수 없으므로 any 타입으로 변환
    const bodyStyle = document.body.style as any;
    bodyStyle.WebkitOverflowScrolling = 'touch';
    
    // 언마운트 시 원래 스타일로 복원
    return () => {
      document.body.style.overflow = '';
      document.body.style.position = '';
      document.body.style.width = '';
      document.body.style.height = '';
      
      // WebkitOverflowScrolling 제거
      bodyStyle.WebkitOverflowScrolling = '';
    };
  }, []);
  
  // 모바일 최적화 스타일 정의
  const mobileChatAreaStyle: React.CSSProperties = {
    display: 'flex',
    flexDirection: 'column',
    height: '100%',
    width: '100%',
    position: 'relative',
    backgroundColor: '#F4F4F4',
    overflow: 'hidden',
    padding: '0',
    opacity: 1,
    fontSize: '14px',
  };
  
  // 스크롤 영역 스타일 - 모바일 환경에서 가상 키보드 등을 고려한 높이 조정
  const contentAreaStyle: React.CSSProperties = {
    overflowY: 'auto',
    overflowX: 'hidden',
    // 모바일 환경에서는 100vh가 정확하지 않을 수 있으므로 윈도우 높이 사용
    height: isFullScreen 
      ? `calc(${windowHeight}px - 90px - ${statusBarHeight}px)` // 전체 화면 모드일 때
      : `calc(${windowHeight}px - 110px - ${statusBarHeight}px)`, // 기본 모드일 때 (상단 헤더 추가 고려)
    width: '100%',
    padding: 0,
    overscrollBehaviorY: 'none',
  };
  
  return (
    <div className="mobile-chat-area">
      {/* 모바일 최적화 스타일 */}
      <style jsx global>{`
        /* 모바일 스크롤바 최적화 */
        @media (max-width: 768px) {
          ::-webkit-scrollbar {
            width: 4px;
            height: 4px;
          }
          
          ::-webkit-scrollbar-thumb {
            background-color: rgba(0, 0, 0, 0.2);
            border-radius: 4px;
          }
          
          ::-webkit-scrollbar-track {
            background-color: transparent;
          }
          
          /* iOS에서 탭 하이라이트 색상 제거 */
          * {
            -webkit-tap-highlight-color: transparent;
          }
          .body {
          overflow: hidden !important;
        }
          /* 메인 요소 스타일 적용 */
          main {
            width: 100vw !important;
            max-width: 100vw !important;
            margin-left: 0 !important;
            left: 0 !important;
            right: 0 !important;
            padding-top: 0px !important;
            position: absolute !important;
          }
          
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
        }
        
        /* 가상 키보드 표시 시 레이아웃 조정 - iOS Safari */
        @supports (-webkit-touch-callout: none) {
          /* iOS에서 가상 키보드가 열릴 때 조정 */
          @media (max-width: 768px) {
            .keyboard-open .content-container {
              height: calc(100% - 250px) !important;
            }
          }
        }
      `}</style>
      
      {/* 컨텐츠 영역 */}
      <div className="chat-content">
        {/* 모바일에서 사이드바 열렸을 때 숨김 처리 */}
        {!isSidebarOpen && children}
      </div>
      
      {/* 하단 안전 영역 (iOS의 홈 인디케이터 영역 고려) */}
      <div style={{
        height: '15px',
        width: '100%',
        backgroundColor: '#F4F4F4',
      }} />
    </div>
  );
}

export default MobileChatLayout; 