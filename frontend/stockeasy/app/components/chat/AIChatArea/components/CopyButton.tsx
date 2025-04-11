/**
 * CopyButton.tsx
 * 채팅 메시지 내용을 클립보드에 복사하는 버튼 UI 컴포넌트
 */
'use client';

import React, { useState, useEffect } from 'react';
import { Copy, Check } from 'lucide-react';

interface CopyButtonProps {
  onClick: () => void; // 복사 버튼 클릭 시 호출할 함수
  isCopied: boolean; // 외부에서 관리하는 복사 상태 (초기값)
  size?: 'sm' | 'md';
  label?: string;
  variant?: 'default' | 'user' | 'assistant'; // 버튼 스타일 변형
}

export function CopyButton({ 
  onClick, 
  isCopied: externalIsCopied, 
  size = 'md', 
  label = '복사',
  variant = 'default'
}: CopyButtonProps) {
  // 내부적으로 복사 상태를 관리 (UI 표시용)
  const [localIsCopied, setLocalIsCopied] = useState(false);

  // 외부에서 isCopied가 true로 변경되면 내부 상태도 업데이트
  useEffect(() => {
    if (externalIsCopied) {
      setLocalIsCopied(true);
      
      // 3초 후에 복사 상태 초기화
      const timer = setTimeout(() => {
        setLocalIsCopied(false);
      }, 1500);
      
      return () => {
        clearTimeout(timer);
      };
    }
  }, [externalIsCopied]);
  
  // 버튼 클릭 핸들러
  const handleClick = () => {
    // 외부 onClick 핸들러 호출
    onClick();
    
    // 내부 상태 업데이트 (즉시 UI 반영)
    setLocalIsCopied(true);
    
    // 3초 후 UI 원상복구
    setTimeout(() => {
      setLocalIsCopied(false);
    }, 1500);
  };
  
  // 아이콘 크기 결정
  const iconSize = size === 'sm' ? 14 : 16;
  
  // 버튼 스타일 설정
  const getButtonStyle = () => {
    // 기본 스타일
    const baseStyle = {
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      gap: '4px',
      cursor: 'pointer',
      transition: 'all 0.2s ease',
    };
    
    // 변형에 따른 스타일
    if (variant === 'user') {
      return {
        ...baseStyle,
        backgroundColor: 'rgba(255, 255, 255, 0)',
        border: 'none',
        borderRadius: '4px',
        width: '24px',
        height: '20px',
        opacity: 0.8,
      };
    } else if (variant === 'assistant') {
      return {
        ...baseStyle,
        backgroundColor: localIsCopied ? 'rgba(16, 163, 127, 0.1)' : 'rgba(240, 240, 240, 0.8)',
        border: 'none',
        borderRadius: '4px',
        width: '24px',
        height: '20px',
        opacity: 0.8,
      };
    } else {
      // 기본 스타일 (기존 스타일)
      return {
        ...baseStyle,
        padding: size === 'sm' ? '4px 8px' : '6px 12px',
        borderRadius: '6px',
        border: '1px solid #ddd',
        backgroundColor: localIsCopied ? '#E7F7EE' : '#f5f5f5',
        color: localIsCopied ? '#34A853' : '#555',
        fontSize: size === 'sm' ? '12px' : '13px',
      };
    }
  };
  
  // 아이콘 색상 결정
  const getIconColor = () => {
    if (variant === 'user') {
      return localIsCopied ? '#FFFFFF' : '#FFFFFF';
    } else if (variant === 'assistant') {
      return localIsCopied ? '#10A37F' : '#333333';
    } else {
      return localIsCopied ? '#34A853' : '#555';
    }
  };
  
  // 마우스 호버 이벤트 핸들러
  const handleMouseEnter = (e: React.MouseEvent<HTMLButtonElement>) => {
    if (variant === 'user') {
      e.currentTarget.style.backgroundColor = 'rgba(175, 175, 175, 0.2)';
    } else if (variant === 'assistant') {
      e.currentTarget.style.backgroundColor = localIsCopied 
        ? 'rgba(16, 163, 127, 0.2)' 
        : 'rgba(210, 210, 210, 0.5)';
    }
  };
  
  // 마우스 나갔을 때 이벤트 핸들러
  const handleMouseLeave = (e: React.MouseEvent<HTMLButtonElement>) => {
    if (variant === 'user') {
      e.currentTarget.style.backgroundColor = 'rgba(255, 255, 255, 0)';
    } else if (variant === 'assistant') {
      e.currentTarget.style.backgroundColor = localIsCopied 
        ? 'rgba(16, 163, 127, 0.1)' 
        : 'rgba(240, 240, 240, 0.8)';
    }
  };
  
  return (
    <button
      onClick={handleClick}
      className={`copy-button ${localIsCopied ? 'copied' : ''}`}
      style={getButtonStyle()}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
      title={localIsCopied ? "복사 완료" : "복사"}
      aria-label={localIsCopied ? '복사됨' : '메시지 내용 복사'}
    >
      {variant === 'default' ? (
        localIsCopied ? (
          <>
            <svg
              width={size === 'sm' ? '12' : '14'}
              height={size === 'sm' ? '12' : '14'}
              viewBox="0 0 24 24"
              fill="none"
              xmlns="http://www.w3.org/2000/svg"
            >
              <path
                d="M9 16.2L4.8 12L3.4 13.4L9 19L21 7L19.6 5.6L9 16.2Z"
                fill="currentColor"
              />
            </svg>
            <span>{label === '복사' ? '복사됨' : label}</span>
          </>
        ) : (
          <>
            <svg
              width={size === 'sm' ? '12' : '14'}
              height={size === 'sm' ? '12' : '14'}
              viewBox="0 0 24 24"
              fill="none"
              xmlns="http://www.w3.org/2000/svg"
            >
              <path
                d="M16 1H4C2.9 1 2 1.9 2 3V17H4V3H16V1ZM19 5H8C6.9 5 6 5.9 6 7V21C6 22.1 6.9 23 8 23H19C20.1 23 21 22.1 21 21V7C21 5.9 20.1 5 19 5ZM19 21H8V7H19V21Z"
                fill="currentColor"
              />
            </svg>
            <span>{label}</span>
          </>
        )
      ) : (
        localIsCopied ? (
          <Check size={iconSize} color={getIconColor()} />
        ) : (
          <Copy size={iconSize} color={getIconColor()} />
        )
      )}
    </button>
  );
}

export default CopyButton; 