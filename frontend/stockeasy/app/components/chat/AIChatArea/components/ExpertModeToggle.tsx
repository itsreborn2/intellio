/**
 * ExpertModeToggle.tsx
 * 전문가/주린이 모드 전환 토글 버튼 컴포넌트
 */
'use client';

import React from 'react';
import { Briefcase } from 'lucide-react';

interface ExpertModeToggleProps {
  isExpertMode: boolean;
  onToggle: () => void;
  size?: 'sm' | 'md';
}

export function ExpertModeToggle({ 
  isExpertMode, 
  onToggle, 
  size = 'sm' 
}: ExpertModeToggleProps) {
  /**
   * Pill 스타일 토글 스위치 구현
   * - Speak/Listen 라벨 사용
   * - isExpertMode: true면 Listen(우측) 활성화, false면 Speak(좌측) 활성화
   * - 접근성: role="switch", aria-checked 적용
   * - TailwindCSS로 스타일 구현
   * - 기존 주석 및 props 최대 보존
   */
  const height = size === 'sm' ? '36px' : '44px';
  const width = size === 'sm' ? '120px' : '144px';
  const fontSize = size === 'sm' ? 'text-base' : 'text-lg';

  return (
    <div
      className={`flex items-center select-none`}
      style={{ height, width }}
      role="switch"
      aria-checked={isExpertMode}
      tabIndex={0}
      onClick={onToggle}
      onKeyDown={e => {
        if (e.key === 'Enter' || e.key === ' ') onToggle();
      }}
      title={isExpertMode ? "Listen 모드 (전문가)" : "Speak 모드 (주린이)"}
    >
      {/* 전체 pill 배경 */}
      <div
        className={`w-full h-full flex rounded-full bg-black transition-colors duration-200 relative cursor-pointer border border-black`}
        style={{ boxShadow: '0 1px 4px rgba(0,0,0,0.03)' }}
      >
        {/* Speak 버튼(좌측) */}
        <div
          className={`flex-1 flex items-center justify-center rounded-full z-10 transition-colors duration-200
            ${!isExpertMode ? 'bg-white font-normal text-black' : 'bg-black text-white font-normal'}
            ${fontSize}
            ${!isExpertMode ? 'font-bold' : ''}
          `}
          style={{
            boxShadow: !isExpertMode ? '0 2px 8px 0 rgba(0,0,0,0.07)' : undefined,
            transition: 'background 0.2s, color 0.2s',
            cursor: 'pointer',
            height: '100%'
          }}
        >
          Speak
        </div>
        {/* Listen 버튼(우측) */}
        <div
          className={`flex-1 flex items-center justify-center rounded-full z-10 transition-colors duration-200
            ${isExpertMode ? 'bg-white font-bold text-black' : 'bg-black text-white font-normal'}
            ${fontSize}
          `}
          style={{
            boxShadow: isExpertMode ? '0 2px 8px 0 rgba(0,0,0,0.07)' : undefined,
            transition: 'background 0.2s, color 0.2s',
            cursor: 'pointer',
            height: '100%'
          }}
        >
          Listen
        </div>
        {/* 활성화된 쪽에만 흰색 배경 오버레이 */}
        <div
          className={`absolute top-0 bottom-0 transition-all duration-200 rounded-full bg-white`}
          style={{
            left: isExpertMode ? '50%' : '0%',
            width: '50%',
            boxShadow: '0 2px 8px 0 rgba(0,0,0,0.05)',
            zIndex: 5,
            transition: 'left 0.2s'
          }}
        />
      </div>
    </div>
  );
}


export default ExpertModeToggle; 