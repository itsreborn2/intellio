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
  // 아이콘 크기 결정
  const iconSize = size === 'sm' ? 14 : 16;
  
  // 버튼 크기 결정
  const buttonSize = size === 'sm' ? {
    width: '24px',
    height: '20px'
  } : {
    width: '28px',
    height: '24px'
  };
  
  return (
    <button
      onClick={onToggle}
      style={{
        backgroundColor: isExpertMode ? 'rgba(16, 163, 127, 0.8)' : 'rgba(240, 240, 240, 0.8)',
        border: 'none',
        borderRadius: '4px',
        width: buttonSize.width,
        height: buttonSize.height,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        cursor: 'pointer',
        opacity: 0.8,
        transition: 'all 0.2s ease'
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.backgroundColor = isExpertMode ? 'rgba(16, 163, 127, 1)' : 'rgba(210, 210, 210, 0.5)';
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.backgroundColor = isExpertMode ? 'rgba(16, 163, 127, 0.8)' : 'rgba(240, 240, 240, 0.8)';
      }}
      title={isExpertMode ? "주린이 모드로 보기" : "전문가 모드로 보기"}
    >
      <Briefcase size={iconSize} color={isExpertMode ? '#FFFFFF' : '#333333'} />
    </button>
  );
}

export default ExpertModeToggle; 