/**
 * 통합 테스트 페이지
 */
'use client';

import React, { useState } from 'react';
import { MessageList, InputArea } from '../../components';
import { createTestMessages, createTestStock, createTestStockOptions, createTestMessage } from '../../utils/testUtils';
import Link from 'next/link';

export default function IntegrationTestPage() {
  // 메시지 및 상태 관리
  const [messages, setMessages] = useState(createTestMessages(4));
  const [inputMessage, setInputMessage] = useState('');
  const [selectedStock, setSelectedStock] = useState<ReturnType<typeof createTestStock> | null>(
    createTestStock('005930', '삼성전자')
  );
  const [isProcessing, setIsProcessing] = useState(false);
  const [isInputCentered, setIsInputCentered] = useState(false);
  const [showStockSuggestions, setShowStockSuggestions] = useState(false);
  const [copyStates, setCopyStates] = useState<Record<string, boolean>>({});
  const [expertMode, setExpertMode] = useState<Record<string, boolean>>({});
  const [timerState] = useState<Record<string, number>>({});
  
  // 테스트 데이터
  const recentStocks = createTestStockOptions(3);
  
  // 이벤트 핸들러
  const handleSendMessage = () => {
    if (!inputMessage.trim() || !selectedStock) return;
    
    setIsProcessing(true);
    
    // 사용자 메시지 추가
    const userMessage = createTestMessage('user', 
        inputMessage, {
            stockName: selectedStock.stockName,
            stockCode: selectedStock.stockCode
            },
            'message-id-1'
    );
    
    setMessages([...messages, userMessage]);
    
    // 상태 메시지 추가
    const statusMessage = createTestMessage('status', '처리 중입니다...', {
      stockName: selectedStock.stockName,
      stockCode: selectedStock.stockCode
    }, 'message-id-2');
    
    setMessages([...messages, userMessage, statusMessage]);
    
    // 3초 후 어시스턴트 응답 추가
    setTimeout(() => {
      // 상태 메시지 제거 및 어시스턴트 메시지 추가
      const assistantMessage = createTestMessage('assistant', `"${inputMessage}"에 대한 답변입니다.`, {
        stockName: selectedStock.stockName,
        stockCode: selectedStock.stockCode
      }, 'message-id-3');
      
      setMessages(prevMessages => [
        ...prevMessages.filter(msg => msg.id !== statusMessage.id),
        assistantMessage
      ]);
      
      setInputMessage('');
      setIsProcessing(false);
    }, 3000);
  };
  
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
      display: 'flex',
      flexDirection: 'column',
      height: '100vh',
      width: '100%',
      position: 'relative',
      backgroundColor: '#F4F4F4',
      overflow: 'hidden',
    }}>
      {/* 헤더 */}
      <div style={{ 
        padding: '16px', 
        backgroundColor: '#282A2E', 
        color: 'white',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center'
      }}>
        <h1 style={{ margin: 0, fontSize: '20px' }}>AIChatArea 통합 테스트</h1>
        <Link href="/components/chat/AIChatArea/test" style={{ 
          color: 'white', 
          textDecoration: 'none',
          padding: '6px 12px',
          backgroundColor: 'rgba(255, 255, 255, 0.1)',
          borderRadius: '4px'
        }}>
          테스트 홈으로
        </Link>
      </div>
      
      {/* 테스트 환경 컨트롤 */}
      <div style={{ 
        padding: '10px 16px', 
        backgroundColor: '#fff', 
        borderBottom: '1px solid #eee',
        display: 'flex',
        gap: '10px',
        flexWrap: 'wrap'
      }}>
        <button 
          onClick={() => setIsInputCentered(!isInputCentered)}
          style={{
            padding: '6px 12px',
            backgroundColor: isInputCentered ? '#20c997' : '#f5f5f5',
            color: isInputCentered ? 'white' : '#333',
            border: 'none',
            borderRadius: '4px',
            cursor: 'pointer'
          }}
        >
          {isInputCentered ? '중앙 배치 모드 ON' : '중앙 배치 모드 OFF'}
        </button>
        
        <button 
          onClick={() => setShowStockSuggestions(!showStockSuggestions)}
          style={{
            padding: '6px 12px',
            backgroundColor: showStockSuggestions ? '#fab005' : '#f5f5f5',
            color: showStockSuggestions ? 'white' : '#333',
            border: 'none',
            borderRadius: '4px',
            cursor: 'pointer'
          }}
        >
          {showStockSuggestions ? '종목 추천 표시' : '종목 추천 숨김'}
        </button>
        
        <button 
          onClick={() => setMessages([])}
          style={{
            padding: '6px 12px',
            backgroundColor: '#ff6b6b',
            color: 'white',
            border: 'none',
            borderRadius: '4px',
            cursor: 'pointer'
          }}
        >
          메시지 초기화
        </button>
      </div>
      
      {/* 메시지 목록 */}
      <div style={{ 
        flex: 1, 
        overflow: 'hidden',
        display: 'flex',
        flexDirection: 'column'
      }}>
        <MessageList 
          messages={messages}
          copyStates={copyStates}
          expertMode={expertMode}
          timerState={timerState}
          isInputCentered={isInputCentered}
          onCopy={handleCopy}
          onToggleExpertMode={handleToggleExpertMode}
        />
      </div>
      
      {/* 입력 영역 */}
      <div style={{ 
        width: '100%',
        padding: '10px',
        backgroundColor: '#F4F4F4'
      }}>
        <InputArea
          inputMessage={inputMessage}
          setInputMessage={setInputMessage}
          selectedStock={selectedStock}
          isProcessing={isProcessing}
          isInputCentered={isInputCentered}
          showStockSuggestions={showStockSuggestions}
          filteredStocks={recentStocks}
          recentStocks={recentStocks}
          searchMode={false}
          isLoading={false}
          error={null}
          windowWidth={1024}
          onSendMessage={handleSendMessage}
          onStockSelect={setSelectedStock}
          onShowStockSuggestions={setShowStockSuggestions}
          onSearchModeChange={() => {}}
          onClearRecentStocks={() => {}}
          showTitle={isInputCentered}
        />
      </div>
    </div>
  );
} 