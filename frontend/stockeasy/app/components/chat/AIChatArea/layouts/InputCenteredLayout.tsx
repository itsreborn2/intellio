/**
 * InputCenteredLayout.tsx
 * 입력 필드가 중앙에 배치된 레이아웃 컴포넌트
 */
'use client';

import React, { ReactNode } from 'react';
import { useIsMobile } from '../hooks';

interface InputCenteredLayoutProps {
  children: ReactNode;
  recommendedQuestionsArea?: ReactNode;
}

export function InputCenteredLayout({ children, recommendedQuestionsArea }: InputCenteredLayoutProps) {
  const isMobile = useIsMobile();
  
  // 초기 화면 스타일
  const centeredContainerStyle: React.CSSProperties = {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    width: '100%',
    height: '100%',
    position: 'relative',
  };
  
  return (
    <div style={centeredContainerStyle}>
      {/* 입력 영역 */}
      <div style={{
        width: '100%',
        textAlign: 'center',
        position: 'relative',
        zIndex: 10,
      }}>
        {children}
      </div>
      
      {/* 추천 질문 영역 */}
      {recommendedQuestionsArea && (
        <div style={{
          width: isMobile ? '100%' : '57.6%', 
          margin: isMobile ? '50px auto 0' : '12px auto 0',
          padding: isMobile ? '0' : '0',
          display: 'flex',
          flexDirection: isMobile ? 'column' : 'row',
          gap: '8px'
        }}>
          <div style={{
            display: 'flex',
            flexDirection: isMobile ? 'column' : 'row',
            gap: isMobile ? '6px' : '8px',
            width: '100%'
          }}>
            {recommendedQuestionsArea}
          </div>
        </div>
      )}
    </div>
  );
}

export default InputCenteredLayout; 