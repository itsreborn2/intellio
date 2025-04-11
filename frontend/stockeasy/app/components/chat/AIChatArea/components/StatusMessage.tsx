/**
 * StatusMessage.tsx
 * 메시지 처리 상태를 표시하는 컴포넌트
 */
'use client';

import React, { useEffect, useState, useCallback } from 'react';
import { ChatMessage } from '../types';
import { useIsMobile } from '../hooks';
import { formatElapsedTime } from '../utils/messageFormatters';

interface StatusMessageProps {
  message: ChatMessage;
}

export function StatusMessage({ message }: StatusMessageProps) {
  const isMobile = useIsMobile();
  const [elapsedTime, setElapsedTime] = useState<number>(message.elapsed || 0);
  const startTime = message.elapsedStartTime || Date.now();
  
  // 애니메이션 처리를 위한 코드
  const [dots, setDots] = useState<string>('');
  
  useEffect(() => {
    // 매초마다 경과 시간 업데이트
    const timer = setInterval(() => {
      if (message.isProcessing && message.elapsedStartTime) {
        // 처음 타이머가 시작된 시간부터 현재까지의 경과 시간 계산 (초 단위)
        const currentTime = Date.now();
        const elapsedFromStart = (currentTime - startTime) / 1000;
        setElapsedTime(elapsedFromStart);
      }
    }, 1000);
    
    // 애니메이션 처리
    const dotsTimer = setInterval(() => {
      setDots(prev => (prev.length >= 3 ? '' : prev + '.'));
    }, 500);
    
    return () => {
      clearInterval(timer);
      clearInterval(dotsTimer);
    };
  }, [message.isProcessing, message.elapsedStartTime, startTime]);
  
  return (
    <div
      className="status-message"
      style={{
        padding: isMobile ? '8px 12px' : '10px 16px',
        marginBottom: '8px',
        borderRadius: '8px',
        backgroundColor: '#f5f5f5',
        color: '#555',
        fontSize: isMobile ? '13px' : '14px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        maxWidth: '100%',
        width: '100%',
      }}
    >
      <div className="status-content" style={{ display: 'flex', alignItems: 'center' }}>
        {message.isProcessing && (
          <div className="loading-spinner" style={{ marginRight: '10px' }}>
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <circle cx="12" cy="12" r="10" stroke="#E5E5E5" strokeWidth="4" />
              <path
                d="M12 2C6.47715 2 2 6.47715 2 12"
                stroke="#555"
                strokeWidth="4"
                strokeLinecap="round"
              >
                <animateTransform
                  attributeName="transform"
                  attributeType="XML"
                  type="rotate"
                  from="0 12 12"
                  to="360 12 12"
                  dur="1s"
                  repeatCount="indefinite"
                />
              </path>
            </svg>
          </div>
        )}
        <span>
          {message.content}
          {message.isProcessing && <span className="animate-dots">{dots}</span>}
          {elapsedTime > 0 && (
            <span className="elapsed-time" style={{ display: 'block', fontSize: isMobile ? '12px' : '15px', color: '#777', marginTop: '4px' }}>
              {formatElapsedTime(elapsedTime)}
            </span>
          )}
        </span>
      </div>
      
      
    </div>
  );
}

// React.memo를 적용하여 불필요한 리렌더링 방지
export default React.memo(StatusMessage); 