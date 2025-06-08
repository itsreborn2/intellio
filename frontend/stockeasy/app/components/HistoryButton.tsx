'use client'

import React, { useRef, useState, useEffect } from 'react';
import { History } from 'lucide-react';
import { usePathname } from 'next/navigation';
import StockChatHistory from './StockChatHistory';

/**
 * 히스토리 버튼 컴포넌트
 * 사이드바 오른쪽, 헤더 아래에 위치하는 히스토리 버튼 및 히스토리 패널
 */
export default function HistoryButton({
  isHistoryPanelOpen,
  isPanelContentVisible,
  toggleHistoryPanel,
}: {
  isHistoryPanelOpen: boolean;
  isPanelContentVisible: boolean;
  toggleHistoryPanel: () => void;
}) {
  // Panel state is now managed by props: isHistoryPanelOpen, isPanelContentVisible
  const [isMobile, setIsMobile] = useState(false);
  const buttonRef = useRef<HTMLButtonElement>(null);
  const pathname = usePathname();

  // 모바일 환경 감지
  useEffect(() => {
    const checkIfMobile = () => {
      const isMobileView = window.innerWidth <= 768; // 768px 이하를 모바일로 간주
      setIsMobile(isMobileView);
    };
    
    // 초기 실행
    checkIfMobile();
    
    // 화면 크기 변경 시 감지
    window.addEventListener('resize', checkIfMobile);
    
    // 컴포넌트 언마운트 시 이벤트 리스너 제거
    return () => {
      window.removeEventListener('resize', checkIfMobile);
    };
  }, []);

  // 히스토리 패널 외부 클릭 시 패널 닫기 구현
  useEffect(() => {
    const handleDocumentClick = (e: MouseEvent) => {
      // 히스토리 패널이 열려 있을 때만 처리
      if (isHistoryPanelOpen) {
        const historyButton = buttonRef.current;
        // 클릭된 요소가 히스토리 버튼이 아니고, 이벤트 전파가 중지되지 않았다면 패널 닫기
        if (historyButton && !historyButton.contains(e.target as Node)) {
          toggleHistoryPanel();
        }
      }
    };
    
    // isHistoryPanelOpen이 true일 때만 리스너 추가
    if (isHistoryPanelOpen) {
      // 약간의 지연 후 리스너 추가 (패널 열기 버튼 클릭과 겹치지 않도록)
      const timerId = setTimeout(() => {
        document.addEventListener('click', handleDocumentClick);
      }, 0);
      
      // 클린업 함수: 타이머 해제 및 리스너 제거
      return () => {
        clearTimeout(timerId);
        document.removeEventListener('click', handleDocumentClick);
      };
    }
    
    return undefined;
  }, [isHistoryPanelOpen]);

  useEffect(() => {
    // 종목 선택 이벤트 리스너
    const handleStockSelected = (e: CustomEvent) => {
      if (isHistoryPanelOpen) {
        toggleHistoryPanel();
      }
    };
    
    // 프롬프트 입력 이벤트 리스너
    const handlePromptInput = (e: CustomEvent) => {
      if (isHistoryPanelOpen) {
        toggleHistoryPanel();
      }
    };
    
    // 이벤트 리스너 등록
    window.addEventListener('stockSelected', handleStockSelected as EventListener);
    window.addEventListener('promptInput', handlePromptInput as EventListener);
    
    // 컴포넌트 언마운트 시 이벤트 리스너 제거
    return () => {
      window.removeEventListener('stockSelected', handleStockSelected as EventListener);
      window.removeEventListener('promptInput', handlePromptInput as EventListener);
    };
  }, [isHistoryPanelOpen]);

  const [showTooltip, setShowTooltip] = useState(false);

  return (
    <>
      {/* 히스토리 버튼 - 데스크톱: 패널 닫힘, 메인 페이지, 모바일 아님 */}
      {!isMobile && pathname === '/' && !isHistoryPanelOpen && (
        <div className="fixed top-[44px] left-[80px] z-[9998]">
          <div className="relative">
            <button 
              ref={buttonRef}
              className={`flex items-center justify-center w-10 h-10 p-2 text-neutral-900 hover:text-neutral-700`}
              onClick={(e) => {
                e.stopPropagation(); // 이벤트 버블링 방지
                toggleHistoryPanel(); // Call prop
              }}
              onMouseEnter={() => setShowTooltip(true)}
              onMouseLeave={() => setShowTooltip(false)}
            >
              <History className="w-6 h-6" />
            </button>
            {showTooltip && (
              <div className="absolute top-1/2 left-full transform -translate-y-1/2 ml-2 px-2 py-1 bg-slate-800 text-white text-xs rounded-[6px] whitespace-nowrap z-[9999]">
                검색 히스토리
              </div>
            )}
          </div>
        </div>
      )}
      
      {/* 반투명 오버레이 - 히스토리 패널이 열려있을 때만 표시 */}
      {isHistoryPanelOpen && (
        <div 
          className="fixed inset-0 bg-black/30 z-[9996]"
          onClick={() => toggleHistoryPanel()}
        />
      )}
      
      {/* 히스토리 패널 */}
      <div onClick={(e: React.MouseEvent) => e.stopPropagation()}>
        <StockChatHistory
          isHistoryPanelOpen={isPanelContentVisible} // 내부 콘텐츠 표시는 isPanelContentVisible prop 사용
          toggleHistoryPanel={toggleHistoryPanel} // Pass down prop
          isMobile={isMobile}
          style={{
            position: 'fixed',
            top: '0',
            left: isMobile ? '0' : '60px', // 사이드바와 겹치도록 조정 (64px - 4px)
            width: isMobile ? '80%' : '350px', // 모바일에서는 화면의 80%만 차지하도록 수정
            height: '100vh',
            zIndex: 9997, // 버튼(9998)보다 낮게 설정, 오버레이(9996)보다 높게 설정
            backgroundColor: 'rgba(38, 38, 38, 1)', // bg-neutral-800과 유사한 색상 (기존 패널 색상 유지)
            boxShadow: '0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05)', // shadow-xl과 유사
            borderRadius: '0.5rem', // rounded-lg
            overflow: 'hidden', // overflow-hidden
            transition: 'transform 0.3s ease-in-out',
            transform: isHistoryPanelOpen ? 'translateX(0)' : 'translateX(-100%)', // Use isHistoryPanelOpen prop for transform
          }}
        />
      </div>
    </>
  );
}
