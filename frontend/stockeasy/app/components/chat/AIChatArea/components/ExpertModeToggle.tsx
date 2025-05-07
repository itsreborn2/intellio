/**
 * ExpertModeToggle.tsx
 * 전문가/주린이 모드 전환 토글 버튼 컴포넌트
 */
'use client';

import React from 'react';

interface ExpertModeToggleProps {
  isExpertMode: boolean;
  onToggle: () => void;
}

export function ExpertModeToggle({
  isExpertMode,
  onToggle,
}: ExpertModeToggleProps) {
  return (
    <button
      onClick={onToggle}
      className="relative inline-flex items-center h-7 w-[88px] rounded-full p-0.5 bg-gray-200 cursor-pointer focus:outline-none"
      aria-label={isExpertMode ? "전문가 모드로 전환됨" : "주린이 모드로 전환됨"}
      role="switch"
      aria-checked={isExpertMode}
    >
      {/* Sliding Background */}
      <span
        aria-hidden="true"
        className={`absolute top-[2px] left-[2px] inline-block h-[24px] w-[40px] transform rounded-full bg-white shadow transition-transform duration-200 ease-in-out
                  ${isExpertMode ? 'translate-x-[42px]' : 'translate-x-0'}`}
      />

      {/* Text Labels Container */}
      <div className="relative z-10 flex w-full justify-between text-xs font-medium">
        {/* 주린이 Label */}
        <span className={`flex-1 text-center px-1 transition-colors duration-200 ease-in-out ${!isExpertMode ? 'text-gray-800' : 'text-gray-500'}`}>
          주린이
        </span>
        {/* 전문가 Label */}
        <span className={`flex-1 text-center px-1 transition-colors duration-200 ease-in-out ${isExpertMode ? 'text-gray-800' : 'text-gray-500'}`}>
          전문가
        </span>
      </div>
    </button>
  );
}

export default ExpertModeToggle;