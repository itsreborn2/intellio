/**
 * MessageBubbleTest.tsx
 * MessageBubble 컴포넌트 테스트
 */
'use client';

import React, { useState } from 'react';
import { MessageBubble } from '../components';
import { createTestMessage, createTestStock } from '../utils/testUtils';

export default function MessageBubbleTest() {
  const [expertMode, setExpertMode] = useState<boolean>(false);
  const [isCopied, setIsCopied] = useState<boolean>(false);
  
  // 사용자 메시지
  const userMessage = createTestMessage('user', '테스트 사용자 메시지', {
    stockName: '삼성전자',
    stockCode: '005930'
    
  }, 'message-id-1');
  
  // 어시스턴트 메시지
  const assistantMessage = createTestMessage('assistant', '테스트 어시스턴트 응답', {
    stockName: '삼성전자',
    stockCode: '005930',
  }, 'message-id-2');
  
  // 상태 메시지
  const statusMessage = createTestMessage('status', '테스트 상태 메시지', {
    stockName: '삼성전자',
    stockCode: '005930',
  }, 'message-id-3');
  
  // 이벤트 핸들러
  const handleCopy = () => {
    setIsCopied(true);
    setTimeout(() => setIsCopied(false), 2000);
  };
  
  const handleToggleExpertMode = () => {
    setExpertMode(prevMode => !prevMode);
  };
  
  return (
    <div style={{ 
      padding: '20px', 
      backgroundColor: '#f0f0f0', 
      minHeight: '100vh',
      display: 'flex',
      flexDirection: 'column',
      gap: '20px'
    }}>
      <h1>MessageBubble 테스트</h1>
      
      <div>
        <h2>사용자 메시지</h2>
        <MessageBubble 
          message={userMessage}
          isExpertMode={expertMode}
          onCopy={() => handleCopy()}
          onToggleExpertMode={() => handleToggleExpertMode()}
          windowWidth={1024}
        />
      </div>
      
      <div>
        <h2>어시스턴트 메시지</h2>
        <MessageBubble 
          message={assistantMessage}
          isExpertMode={expertMode}
          onCopy={() => handleCopy()}
          onToggleExpertMode={() => handleToggleExpertMode()}
          windowWidth={1024}
        />
      </div>
      
      <div>
        <h2>상태 메시지</h2>
        <MessageBubble 
          message={statusMessage}
          isExpertMode={expertMode}
          onCopy={() => handleCopy()}
          onToggleExpertMode={() => handleToggleExpertMode()}
          windowWidth={1024}
        />
      </div>
      
      <div style={{ marginTop: '20px' }}>
        <button 
          onClick={handleToggleExpertMode}
          style={{
            padding: '8px 16px',
            backgroundColor: expertMode ? '#4169E1' : '#f5f5f5',
            color: expertMode ? '#fff' : '#333',
            border: '1px solid #ddd',
            borderRadius: '4px',
            cursor: 'pointer',
            marginRight: '10px'
          }}
        >
          {expertMode ? '전문가 모드 OFF' : '전문가 모드 ON'}
        </button>
      </div>
    </div>
  );
} 