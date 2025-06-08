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
  
  // 스타일 정의
  const centeredContainerStyle: React.CSSProperties = {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center', 
    width: '100%',
    height: '100%',
    position: 'relative',
  };

  // 데스크톱 환경에서만 transform 적용
  const desktopTransform = !isMobile ? { transform: 'translateY(-8vh)' } : {};
  
  // 중앙 컨텐츠를 감싸는 블록 스타일
  const contentBlockStyle: React.CSSProperties = {
    width: '100%', 
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center', 
    ...desktopTransform, 
  };
  
  return (
    <div style={centeredContainerStyle}> 
      <div style={contentBlockStyle}> 
        {/* 입력 영역 (제목, 입력 필드) */}
        <div style={{
          width: '100%',
          textAlign: 'center',
          position: 'relative',
          zIndex: 10,
        }}>
          {children}
        </div>
        
        {/* 추천 질문 및 순위 영역 */}
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
    </div>
  );
}

export default InputCenteredLayout;