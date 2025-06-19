/**
 * CompletionPopup.tsx
 * 분석 완료 알림 팝업 컴포넌트
 */
'use client';

import React, { useEffect, useState } from 'react';

interface CompletionPopupProps {
  onViewFinalReport: () => void;
  onClose?: () => void;
}

export function CompletionPopup({ onViewFinalReport, onClose }: CompletionPopupProps) {
  const [isVisible, setIsVisible] = useState(false);
  const [isAnimating, setIsAnimating] = useState(false);

  useEffect(() => {
    // 컴포넌트 마운트 시 애니메이션 시작
    setIsVisible(true);
    setIsAnimating(true);
  }, []);

  const handleViewReport = () => {
    setIsAnimating(false);
    setTimeout(() => {
      onViewFinalReport();
    }, 300);
  };

  const handleClose = () => {
    setIsAnimating(false);
    setTimeout(() => {
      setIsVisible(false);
      onClose?.();
    }, 300);
  };

  if (!isVisible) return null;

  return (
    <div className="fixed bottom-0 left-4 right-4 sm:top-8 sm:right-4 sm:left-auto sm:bottom-auto z-50 max-w-sm sm:w-auto mx-auto sm:mx-0">
      {/* 팝업 컨테이너 - 모바일에서는 하단에, 데스크톱에서는 우상단에 위치 */}
      <div 
        className={`completion-popup bg-white rounded-lg shadow-xl p-6 border border-gray-200 transform transition-all duration-300 ${
          isAnimating 
            ? 'scale-100 opacity-100 translate-y-0' 
            : 'scale-95 opacity-0 translate-y-4'
        }`}
      >
        {/* 성공 아이콘 */}
        <div className="flex items-center justify-center w-12 h-12 mx-auto mb-4 bg-green-100 rounded-full">
          <svg 
            className="w-6 h-6 text-green-600" 
            fill="none" 
            stroke="currentColor" 
            viewBox="0 0 24 24"
          >
            <path 
              strokeLinecap="round" 
              strokeLinejoin="round" 
              strokeWidth={2} 
              d="M5 13l4 4L19 7" 
            />
          </svg>
        </div>

        {/* 제목 */}
        <h3 className="text-lg font-semibold text-gray-900 text-center mb-2">
          분석이 완료되었습니다!
        </h3>

        {/* 설명 */}
        <p className="text-gray-600 text-center mb-6">
          상세한 분석 결과를 확인해보세요.
        </p>

        {/* 버튼 그룹 */}
        <div className="flex space-x-3">
          <button
            onClick={handleClose}
            className="flex-1 px-4 py-2 text-gray-700 bg-gray-100 hover:bg-gray-200 rounded-lg transition-colors duration-200 font-medium"
          >
            나중에 보기
          </button>
          <button
            onClick={handleViewReport}
            className="flex-1 px-4 py-2 text-white bg-blue-600 hover:bg-blue-700 rounded-lg transition-colors duration-200 font-medium shadow-sm"
          >
            메시지 보기
          </button>
        </div>

        {/* 닫기 버튼 (X) */}
        <button
          onClick={handleClose}
          className="absolute top-4 right-4 text-gray-400 hover:text-gray-600 transition-colors duration-200"
          aria-label="닫기"
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>

        {/* 프로그레스 바 애니메이션 */}
        <div className="absolute bottom-0 left-0 right-0 h-1 bg-gray-200 rounded-b-lg overflow-hidden">
          <div 
            className="h-full bg-green-500 transform transition-transform duration-2000 ease-out"
            style={{ 
              transform: isAnimating ? 'translateX(0)' : 'translateX(-100%)',
              width: '100%'
            }}
          />
        </div>
      </div>
    </div>
  );
} 