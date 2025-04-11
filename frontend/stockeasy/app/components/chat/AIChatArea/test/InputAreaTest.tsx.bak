/**
 * InputAreaTest.tsx
 * InputArea 컴포넌트 테스트
 */
'use client';

import React, { useState } from 'react';
import { InputArea } from '../components';
import { createTestStock, createTestStockOptions } from '../utils/testUtils';

export default function InputAreaTest() {
  // 상태 관리
  const [inputMessage, setInputMessage] = useState<string>('');
  const [selectedStock, setSelectedStock] = useState<ReturnType<typeof createTestStock> | null>(null);
  const [isProcessing, setIsProcessing] = useState<boolean>(false);
  const [isInputCentered, setIsInputCentered] = useState<boolean>(true);
  const [showStockSuggestions, setShowStockSuggestions] = useState<boolean>(false);
  const [searchMode, setSearchMode] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  
  // 테스트 데이터
  const recentStocks = createTestStockOptions(3);
  const filteredStocks = createTestStockOptions(5);
  
  // 이벤트 핸들러
  const handleSendMessage = () => {
    if (!inputMessage.trim() || !selectedStock) return;
    
    setIsProcessing(true);
    console.log(`메시지 전송: ${inputMessage}`);
    console.log(`선택된 종목: ${selectedStock.stockName}(${selectedStock.stockCode})`);
    
    // 3초 후 처리 완료
    setTimeout(() => {
      setIsProcessing(false);
      setInputMessage('');
      // 초기화면 모드는 해제
      setIsInputCentered(false);
    }, 3000);
  };
  
  const handleStockSelect = (stock: ReturnType<typeof createTestStock> | null) => {
    setSelectedStock(stock);
    setShowStockSuggestions(false);
  };
  
  const handleInputChange = (value: string) => {
    setInputMessage(value);
    
    if (showStockSuggestions && searchMode) {
      // 검색 모드일 때 종목 필터링 로직 (실제로는 여기서 API 호출)
      console.log(`종목 검색: ${value}`);
    }
  };
  
  const toggleProcessing = () => {
    setIsProcessing(!isProcessing);
  };
  
  const toggleInputCentered = () => {
    setIsInputCentered(!isInputCentered);
  };
  
  const toggleStockSuggestions = () => {
    setShowStockSuggestions(!showStockSuggestions);
  };
  
  return (
    <div style={{ 
      padding: '20px', 
      backgroundColor: '#f4f4f4', 
      minHeight: '100vh',
      fontFamily: 'Arial, sans-serif'
    }}>
      <h1 style={{ marginBottom: '20px', color: '#333' }}>InputArea 컴포넌트 테스트</h1>
      
      <div style={{ 
        backgroundColor: '#fff',
        border: '1px solid #ddd',
        borderRadius: '8px',
        padding: '20px',
        marginBottom: '20px'
      }}>
        <h2 style={{ marginTop: 0, color: '#333', fontSize: '18px' }}>컨트롤 패널</h2>
        
        <div style={{ 
          display: 'flex', 
          flexWrap: 'wrap', 
          gap: '10px', 
          marginBottom: '20px' 
        }}>
          <button 
            onClick={toggleProcessing} 
            style={{ 
              padding: '8px 16px', 
              backgroundColor: isProcessing ? '#ff6b6b' : '#4dabf7', 
              color: 'white', 
              border: 'none', 
              borderRadius: '4px', 
              cursor: 'pointer' 
            }}
          >
            {isProcessing ? '처리 중 해제' : '처리 중 상태로 변경'}
          </button>
          
          <button 
            onClick={toggleInputCentered} 
            style={{ 
              padding: '8px 16px', 
              backgroundColor: isInputCentered ? '#20c997' : '#868e96', 
              color: 'white', 
              border: 'none', 
              borderRadius: '4px', 
              cursor: 'pointer' 
            }}
          >
            {isInputCentered ? '중앙 배치 모드' : '일반 모드'}
          </button>
          
          <button 
            onClick={toggleStockSuggestions} 
            style={{ 
              padding: '8px 16px', 
              backgroundColor: showStockSuggestions ? '#fab005' : '#868e96', 
              color: 'white', 
              border: 'none', 
              borderRadius: '4px', 
              cursor: 'pointer' 
            }}
          >
            {showStockSuggestions ? '종목 추천 표시 중' : '종목 추천 숨김'}
          </button>
          
          <button 
            onClick={() => setSearchMode(!searchMode)} 
            style={{ 
              padding: '8px 16px', 
              backgroundColor: searchMode ? '#ae3ec9' : '#868e96', 
              color: 'white', 
              border: 'none', 
              borderRadius: '4px', 
              cursor: 'pointer' 
            }}
          >
            {searchMode ? '검색 모드 ON' : '검색 모드 OFF'}
          </button>
        </div>
        
        {selectedStock && (
          <div style={{ 
            backgroundColor: '#e9ecef', 
            padding: '10px', 
            borderRadius: '4px', 
            marginBottom: '15px' 
          }}>
            <p style={{ margin: '0', fontWeight: 'bold' }}>
              선택된 종목: {selectedStock.stockName} ({selectedStock.stockCode})
            </p>
          </div>
        )}
      </div>
      
      <div style={{ 
        position: 'relative',
        height: '400px',
        border: '1px solid #ddd',
        borderRadius: '8px',
        backgroundColor: '#fff',
        padding: '20px',
        display: 'flex',
        flexDirection: 'column',
        justifyContent: isInputCentered ? 'center' : 'flex-end'
      }}>
        <InputArea
          inputMessage={inputMessage}
          setInputMessage={handleInputChange}
          selectedStock={selectedStock}
          isProcessing={isProcessing}
          isInputCentered={isInputCentered}
          showStockSuggestions={showStockSuggestions}
          filteredStocks={filteredStocks}
          recentStocks={recentStocks}
          searchMode={searchMode}
          isLoading={false}
          error={error}
          windowWidth={1024}
          onSendMessage={handleSendMessage}
          onStockSelect={handleStockSelect}
          onShowStockSuggestions={setShowStockSuggestions}
          onSearchModeChange={setSearchMode}
          onClearRecentStocks={() => console.log('최근 조회 종목 초기화')}
          showTitle={isInputCentered}
        />
      </div>
      
      <div style={{ 
        marginTop: '20px',
        backgroundColor: '#f9f9f9',
        border: '1px solid #ddd',
        borderRadius: '8px',
        padding: '12px' 
      }}>
        <h3 style={{ marginTop: 0, color: '#333' }}>테스트 상태</h3>
        <p>입력 메시지: {inputMessage || '<없음>'}</p>
        <p>처리 중: {isProcessing ? 'Y' : 'N'}</p>
        <p>중앙 배치 모드: {isInputCentered ? 'Y' : 'N'}</p>
        <p>종목 추천 표시: {showStockSuggestions ? 'Y' : 'N'}</p>
        <p>검색 모드: {searchMode ? 'Y' : 'N'}</p>
      </div>
    </div>
  );
} 