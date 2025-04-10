/**
 * InputArea.tsx
 * 메시지 입력 및 전송을 담당하는 컴포넌트
 */
'use client';

import React, { useRef, useState, useEffect, useCallback } from 'react';
import { StockOption } from '../types';
import { useIsMobile } from '../hooks';
import StockBadge from './StockBadge';
import StockSuggestions from './StockSuggestions';
import SendButton from './SendButton';

interface InputAreaProps {
  inputMessage: string;
  setInputMessage: (message: string) => void;
  selectedStock: StockOption | null;
  isProcessing: boolean;
  isInputCentered: boolean;
  showStockSuggestions: boolean;
  filteredStocks: StockOption[];
  recentStocks: StockOption[];
  searchMode: boolean;
  isLoading: boolean;
  error: string | null;
  windowWidth: number;
  onSendMessage: () => void;
  onStockSelect: (stock: StockOption | null) => void;
  onShowStockSuggestions: (show: boolean) => void;
  onSearchModeChange: (mode: boolean) => void;
  onClearRecentStocks: () => void;
  scrollToBottom?: () => void;
  showTitle?: boolean;
}

export function InputArea({
  inputMessage,
  setInputMessage,
  selectedStock,
  isProcessing,
  isInputCentered,
  showStockSuggestions,
  filteredStocks,
  recentStocks,
  searchMode,
  isLoading,
  error,
  windowWidth,
  onSendMessage,
  onStockSelect,
  onShowStockSuggestions,
  onSearchModeChange,
  onClearRecentStocks,
  scrollToBottom,
  showTitle = false
}: InputAreaProps) {
  const isMobile = useIsMobile();
  const inputRef = useRef<HTMLInputElement>(null);
  const inputBoxRef = useRef<HTMLDivElement>(null);
  const stockSuggestionsRef = useRef<HTMLDivElement>(null);
  
  const [isKeyPressed, setIsKeyPressed] = useState(false);
  
  // 사이드바 너비 상수 (픽셀 단위)
  const SIDEBAR_WIDTH = 59;
  
  // 입력 영역 스타일
  const inputAreaStyle: React.CSSProperties = {
    width: '100%',
    marginTop: isInputCentered ? (isMobile ? '25vh' : (windowWidth < 768 ? '30vh' : '35vh')) : '0px',
    marginBottom: '5px',
    position: isInputCentered ? 'relative' : 'fixed',
    bottom: isInputCentered ? 'auto' : '0',
    left: isInputCentered ? '0' : (!isMobile ? `calc(50% - ${1037 / 2}px + ${SIDEBAR_WIDTH / 2}px)` : '0'),
    zIndex: 100,
    backgroundColor: isInputCentered ? 'transparent' : '#F4F4F4',
    maxWidth: isInputCentered ? '100%' : (!isMobile ? `1037px` : '100%'),
    paddingBottom: '5px'
  };
  
  const integratedInputStyle: React.CSSProperties = {
    position: 'relative',
    width: isMobile ? '100%' : (windowWidth < 768 ? '95%' : (windowWidth < 1024 ? '85%' : '70%')),
    maxWidth: isMobile ? '100%' : (windowWidth < 768 ? '95%' : (windowWidth < 1024 ? '85%' : '70%')),
    margin: isMobile ? '0' : '0 auto',
    boxSizing: 'border-box',
    padding: 0
  };
  
  const inputStyle: React.CSSProperties = {
    width: '100%',
    minHeight: isMobile ? '2.2rem' : (windowWidth < 768 ? '2.3rem' : '2.5rem'),
    height: 'auto',
    border: '1px solid #ccc',
    borderRadius: isMobile ? '6px' : '8px',
    paddingTop: '0',
    paddingRight: isMobile ? '35px' : '40px',
    paddingBottom: '0',
    paddingLeft: selectedStock ? (isMobile ? '75px' : '85px') : (isMobile ? '6px' : '8px'),
    fontSize: isMobile ? '14px' : (windowWidth < 768 ? '15px' : '16px'),
    outline: 'none',
    boxSizing: 'border-box',
    resize: 'none',
    overflow: 'hidden',
    maxWidth: '100%'
  };
  
  // 외부 클릭 이벤트 리스너 (종목 추천 창 닫기)
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (
        stockSuggestionsRef.current && 
        !stockSuggestionsRef.current.contains(event.target as Node) &&
        inputRef.current && 
        !inputRef.current.contains(event.target as Node)
      ) {
        onShowStockSuggestions(false);
      }
    };
    
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [onShowStockSuggestions]);
  
  // 글로벌 키다운 이벤트 리스너 추가
  useEffect(() => {
    const handleGlobalKeyDown = (e: KeyboardEvent) => {
      // Backspace 키를 감지하여 종목 선택 해제 처리
      if (e.key === 'Backspace' && inputMessage === '' && selectedStock && !isProcessing) {
        console.log('[InputArea] 글로벌 Backspace 감지 - 종목 선택 해제');
        
        // input 요소에 포커스 설정
        if (inputRef.current) {
          inputRef.current.focus();
        }
        
        // 선택된 종목 해제하고 종목 추천 표시
        onStockSelect(null);
        onShowStockSuggestions(true);
        onSearchModeChange(true);
        
        // 이벤트 전파 방지
        e.preventDefault();
      }
    };
    
    // 이벤트 리스너 등록
    document.addEventListener('keydown', handleGlobalKeyDown);
    
    // 컴포넌트 언마운트 시 제거
    return () => {
      document.removeEventListener('keydown', handleGlobalKeyDown);
    };
  }, [inputMessage, selectedStock, onStockSelect, onShowStockSuggestions, onSearchModeChange, isProcessing]);
  
  // 키보드 이벤트 처리
  const handleKeyDown = useCallback((e: React.KeyboardEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    
    // 이미 키가 눌려 있는 상태라면 무시
    if (isKeyPressed) {
      e.preventDefault();
      return;
    }
    
    // 전체 키 이벤트 로깅
    console.log(`[InputArea] KeyDown: ${e.key}, inputMessage: "${inputMessage}", selectedStock: ${selectedStock ? selectedStock.stockName : 'none'}`);
    
    // Backspace 키이고, 입력창이 비어있고, 종목이 선택된 상태인지 확인
    if (e.key === 'Backspace' && inputMessage === '' && selectedStock) {
      e.preventDefault(); // 기본 Backspace 동작 방지
      console.log('[InputArea] Backspace 누름 - 종목 선택 해제 및 팝업 표시');
      
      // 포커스 확인
      const activeElement = document.activeElement;
      console.log('[InputArea] Active Element:', activeElement);
      console.log('[InputArea] Input Ref:', inputRef.current);
      console.log('[InputArea] 포커스 일치 여부:', activeElement === inputRef.current);
      
      // 선택된 종목 해제하고 종목 추천 표시
      onStockSelect(null);
      onShowStockSuggestions(true);
      onSearchModeChange(true);
      
      // 최근 조회 종목 또는 기본 추천 종목 표시 로직은 부모 컴포넌트에서 처리
    }
    
    // Enter 키 눌렀을 때 메시지 전송 (Shift+Enter는 줄바꿈)
    if (e.key === 'Enter' && !e.shiftKey && inputMessage.trim() !== '' && selectedStock) {
      e.preventDefault();
      setIsKeyPressed(true);
      onSendMessage();
      // scrollToBottom이 제공되었다면 호출
      if (scrollToBottom) {
        scrollToBottom();
      }
    }
  }, [inputMessage, selectedStock, onStockSelect, onShowStockSuggestions, onSearchModeChange, onSendMessage, isKeyPressed, scrollToBottom]);
  
  const handleKeyUp = useCallback((e: React.KeyboardEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    if (e.key === 'Enter') {
      setIsKeyPressed(false);
    }
  }, []);
  
  // 입력 필드 포커스 시 종목 추천 목록 표시
  const handleInputFocus = () => {
    // 종목 선택 팝업이 이미 열려 있으면 검색 모드 활성화
    if (showStockSuggestions) {
      onSearchModeChange(true);
      return;
    }
    
    // 종목이 선택되어 있지 않은 경우, 종목 추천 팝업 표시 및 검색 모드 활성화
    if (!selectedStock) {
      onShowStockSuggestions(true);
      onSearchModeChange(true);
    }
  };
  
  // 입력 필드 값 변경 처리
  const handleInputChange = useCallback((e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    const value = e.target.value;
    setInputMessage(value);
    
    // 종목이 선택되지 않은 경우, 종목 추천 표시
    if (!selectedStock && !showStockSuggestions) {
      onShowStockSuggestions(true);
      onSearchModeChange(true);
    }
    
    // 종목 선택 팝업이 열려 있거나 검색 모드인 경우 종목 검색 로직
    if (showStockSuggestions || searchMode) {
      // 검색 모드 활성화
      onSearchModeChange(true);
      
      // 검색어가 있으면 표시, 없으면 최근 조회 종목 표시
      // 부모 컴포넌트에 검색어 변경 알림을 통해 filteredStocks를 업데이트하도록 함
      // 이 값은 StockSelectorContext를 통해 관리됨
      setInputMessage(value);
    }
  }, [setInputMessage, selectedStock, showStockSuggestions, onShowStockSuggestions, onSearchModeChange, searchMode]);
  
  // 종목 배지 클릭 시 종목 선택 팝업 표시
  const handleStockBadgeClick = () => {
    onShowStockSuggestions(true);
    onSearchModeChange(true);
    setInputMessage('');
    
    // 포커스 설정
    setTimeout(() => {
      if (inputRef.current) {
        inputRef.current.focus();
      }
    }, 100);
  };
  
  // 전송 버튼 클릭 핸들러
  const handleSendButtonClick = useCallback(() => {
    if (selectedStock && inputMessage.trim() !== '' && !isProcessing) {
      onSendMessage();
      // scrollToBottom이 제공되었다면 호출
      if (scrollToBottom) {
        scrollToBottom();
      }
    }
  }, [selectedStock, inputMessage, isProcessing, onSendMessage, scrollToBottom]);
  
  return (
    <div className="input-area" ref={inputBoxRef} style={inputAreaStyle}>
      <div className="integrated-input" style={integratedInputStyle}>
        {/* 텍스트 박스 바로 위 안내 문구 */}
        {showTitle && isInputCentered && !isMobile && (
          <div style={{
            textAlign: 'center',
            marginBottom: '20px',
            padding: '0',
            width: '100%',
            position: 'relative',
            marginTop: isMobile ? '-80px' : '-100px',
            left: '0',
            right: '0',
            transition: 'all 0.3s ease-in-out'
          }}>
            <h1 style={{
              fontSize: isMobile ? '1rem' : '1.3rem',
              fontWeight: 'bold',
              color: '#333',
              lineHeight: '1.3',
              wordBreak: 'keep-all',
              letterSpacing: '-0.02em',
              transition: 'all 0.3s ease-in-out',
              display: isMobile ? 'none' : 'block'
            }}>
              종목을 선택 후 분석을 요청하세요.
            </h1>
          </div>
        )}
        
        <div style={{
          position: 'relative',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          width: '100%',
          backgroundColor: 'white',
          borderRadius: '6px',
          padding: '0',
          boxShadow: '0 2px 6px rgba(0, 0, 0, 0.05)',
          border: '2px solid #282A2E',
        }}>
          {selectedStock && (
            <StockBadge
              stock={selectedStock}
              isProcessing={isProcessing}
              onClick={handleStockBadgeClick}
            />
          )}
          
          <input
            ref={inputRef}
            placeholder={showStockSuggestions || searchMode 
              ? "종목명 또는 종목코드 검색" 
              : (selectedStock 
                ? "이 종목, 뭔가 궁금하다면 지금 바로 질문해 보세요" 
                : "어떤 종목이든 좋아요! 먼저 입력하거나 골라주세요.")}
            className="integrated-input-field"
            type="text"
            value={inputMessage}
            onChange={handleInputChange}
            onFocus={(e) => {
              console.log("[InputArea] Input 포커스 받음");
              handleInputFocus();
            }}
            onBlur={() => {
              console.log("[InputArea] Input 포커스 잃음");
            }}
            onKeyDown={handleKeyDown}
            onKeyUp={handleKeyUp}
            readOnly={isProcessing}
            style={{
              ...inputStyle,
              border: 'none',
              boxShadow: 'none',
              paddingTop: '8px',
              paddingRight: isMobile ? '8px' : '16px',
              paddingBottom: '8px',
              paddingLeft: isMobile ? '8px' : '16px',
              flex: 1,
              borderRadius: '6px',
              cursor: isProcessing ? 'not-allowed' : 'text'
            }}
          />
          
          {/* 전송 아이콘 */}
          <SendButton
            onClick={handleSendButtonClick}
            disabled={!selectedStock || !inputMessage.trim()}
            isProcessing={isProcessing}
          />
        </div>
        
        {/* 종목 추천 목록 */}
        {showStockSuggestions && (
          <div ref={stockSuggestionsRef}>
            <StockSuggestions
              isLoading={isLoading}
              error={error}
              filteredStocks={filteredStocks}
              recentStocks={recentStocks}
              onSelectStock={onStockSelect}
              onClearRecentStocks={onClearRecentStocks}
              isInputCentered={isInputCentered}
            />
          </div>
        )}
      </div>
    </div>
  );
}

export default React.memo(InputArea); 