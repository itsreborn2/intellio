/**
 * SendButton.tsx
 * 메시지 전송 버튼 컴포넌트
 */
'use client';

import React from 'react';
import { useIsMobile } from '../hooks';

interface SendButtonProps {
  onClick: (e: React.MouseEvent) => void;
  disabled: boolean;
  isProcessing: boolean;
}

export function SendButton({ onClick, disabled, isProcessing }: SendButtonProps) {
  const isMobile = useIsMobile();
  
  return (
    <button
      onClick={(e) => {
        if (isProcessing) {
          e.preventDefault();
          return;
        }
        onClick(e);
      }}
      disabled={disabled || isProcessing}
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        width: isMobile ? '30px' : '36px',
        height: '36px',
        borderRadius: '50%',
        border: 'none',
        backgroundColor: 'transparent',
        cursor: disabled || isProcessing ? 'not-allowed' : 'pointer',
        opacity: disabled || isProcessing ? 0.5 : 1,
        marginRight: isMobile ? '6px' : '8px'
      }}
    >
      <svg
        width="20"
        height="20"
        viewBox="0 0 24 24"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
      >
        <path
          d="M22 2L11 13"
          stroke="#333333"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
        <path
          d="M22 2L15 22L11 13L2 9L22 2Z"
          stroke="#333333"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    </button>
  );
}

export default SendButton; 