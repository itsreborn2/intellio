/**
 * MessageListTest.tsx
 * MessageList 컴포넌트 테스트
 */
'use client';

import React, { useState } from 'react';
import { MessageList } from '../components';
import { createTestMessages } from '../utils/testUtils';

export default function MessageListTest() {
  // 메시지 수 설정
  const messageCount = 6;
  
  // 테스트 메시지 생성 (3개 사용자 + 3개 어시스턴트)
  const testMessages = createTestMessages(messageCount, {
    stockName: '삼성전자',
    stockCode: '005930'
  });
  
  // 상태 관리
  const [copyStates, setCopyStates] = useState<Record<string, boolean>>({});
  const [expertMode, setExpertMode] = useState<Record<string, boolean>>({});
  const [timerState] = useState<Record<string, number>>({});
  
  // 이벤트 핸들러
  const handleCopy = (id: string) => {
    setCopyStates(prev => ({ ...prev, [id]: true }));
    setTimeout(() => {
      setCopyStates(prev => ({ ...prev, [id]: false }));
    }, 2000);
  };
  
  const handleToggleExpertMode = (id: string) => {
    setExpertMode(prev => ({ ...prev, [id]: !prev[id] }));
  };
  
  return (
    <div style={{ 
      padding: '20px', 
      backgroundColor: '#f4f4f4', 
      minHeight: '100vh',
      maxWidth: '900px',
      margin: '0 auto',
      fontFamily: 'Arial, sans-serif'
    }}>
      <h1 style={{ marginBottom: '20px', color: '#333' }}>MessageList 컴포넌트 테스트</h1>
      
      <div style={{ 
        border: '1px solid #ddd', 
        borderRadius: '8px', 
        overflow: 'hidden',
        backgroundColor: '#fff',
        marginBottom: '20px'
      }}>
        <div style={{ 
          padding: '12px', 
          backgroundColor: '#f9f9f9', 
          borderBottom: '1px solid #eee' 
        }}>
          <h2 style={{ margin: 0, fontSize: '16px', color: '#333' }}>테스트 채팅 목록</h2>
        </div>
        
        <div style={{ 
          height: '600px', 
          overflowY: 'auto', 
          padding: '0 20px'
        }}>
          <MessageList 
            messages={testMessages}
            copyStates={copyStates}
            expertMode={expertMode}
            timerState={timerState}
            isInputCentered={false}
            onCopy={handleCopy}
            onToggleExpertMode={handleToggleExpertMode}
          />
        </div>
      </div>
      
      <div style={{ 
        marginTop: '20px',
        backgroundColor: '#f9f9f9',
        border: '1px solid #ddd',
        borderRadius: '8px',
        padding: '12px' 
      }}>
        <h3 style={{ marginTop: 0, color: '#333' }}>테스트 정보</h3>
        <p>메시지 개수: {messageCount}개</p>
        <p>현재 전문가 모드 활성화 메시지: {Object.keys(expertMode).filter(id => expertMode[id]).length}개</p>
        <p>복사 상태 메시지: {Object.keys(copyStates).filter(id => copyStates[id]).length}개</p>
      </div>
    </div>
  );
} 