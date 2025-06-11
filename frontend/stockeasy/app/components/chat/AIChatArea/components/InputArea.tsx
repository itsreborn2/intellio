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
import { checkTimeRestriction, getRestrictionMessage } from '@/app/utils/timeRestriction';
import { toast } from 'sonner';

interface InputAreaProps {
  inputMessage: string;
  setInputMessage: (message: string) => void;
  selectedStock: StockOption | null;
  isProcessing: boolean;
  isInputCentered: boolean;
  showStockSuggestions: boolean;
  recentStocks: StockOption[];
  stockOptions: StockOption[];
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
  currentChatSession?: any; // 현재 채팅 세션 정보 추가
}

export function InputArea({
  inputMessage,
  setInputMessage,
  selectedStock,
  isProcessing,
  isInputCentered,
  showStockSuggestions,
  recentStocks,
  stockOptions,
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
  showTitle,
  currentChatSession
}: InputAreaProps) {
  // 입력창이 처음부터 정확한 크기를 갖도록 초기화 플래그 추가
  const [initialized, setInitialized] = useState<boolean>(false);
  
  // 입력창의 초기 로딩 상태 추적 - 깨빡임 방지를 위해 완전히 로드될 때까지 화면에 표시하지 않음
  const [isInputReady, setInputReady] = useState<boolean>(false);
  
  // 렌더링 순서 제어를 통한 깨빡임 방지
  useEffect(() => {
    // 초기에는 입력창을 표시하지 않음
    setInputReady(false);
    
    // 사전에 CSS 스타일 정의
    const styleElement = document.createElement('style');
    styleElement.innerHTML = `
      .integrated-input-field {
        display: block;
        height: 40px !important;
        min-height: 40px !important;
        max-height: 40px !important;
        resize: none !important;
        transition: none !important;
        animation: none !important;
        overflow-y: hidden !important;
      }
      
      .input-area-hidden {
        opacity: 0;
        visibility: hidden;
      }
      
      .input-area-visible {
        opacity: 1;
        visibility: visible;
        transition: opacity 0.1s ease-out;
      }
    `;
    document.head.appendChild(styleElement);
    
    // 일정 시간 후에 입력창 표시 (렌더링 완료 때까지 대기)
    const timer = setTimeout(() => {
      if (inputRef.current) {
        // 높이 고정 적용
        inputRef.current.style.height = '40px';
        inputRef.current.style.minHeight = '40px';
        inputRef.current.style.maxHeight = '40px';
        inputRef.current.style.overflow = 'hidden';
        
        // 준비가 되었음을 표시
        setInitialized(true);
        // 입력창 표시
        setInputReady(true);
      }
    }, 100); // 최소한의 대기 시간 적용
    
    return () => {
      clearTimeout(timer);
      document.head.removeChild(styleElement);
    };
  }, []);
  
  // 입력창 텍스트 변경시 텍스트영역 상태를 고정 높이로 유지
  useEffect(() => {
    if (inputRef.current && initialized) {
      // 고정 높이 유지
      inputRef.current.style.height = '40px';
    }
  }, [inputMessage, searchMode, initialized]);

  const isMobile = useIsMobile();
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const inputBoxRef = useRef<HTMLDivElement>(null);
  const stockSuggestionsRef = useRef<HTMLDivElement>(null);
  
  const [isKeyPressed, setIsKeyPressed] = useState(false);
  const [filteredStocks, setFilteredStocks] = useState<StockOption[]>([]);
  const [focusedItemIndex, setFocusedItemIndex] = useState<number>(0);
  const [displayedStocks, setDisplayedStocks] = useState<StockOption[]>([]);
  
  // 사이드바 너비 상수 (픽셀 단위)
  const SIDEBAR_WIDTH = 59;
  
  // 현재 채팅 세션이 존재하는지 확인
  const hasActiveSession = Boolean(currentChatSession);
  
  // 입력 영역 스타일
  const inputAreaStyle: React.CSSProperties = {
    width: '100%',
    marginTop: isInputCentered ? (isMobile ? '25vh' : (windowWidth < 768 ? '30vh' : '27vh')) : '0px',
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
  
  // 입력박스의 스타일을 고정값으로 설정하여 렌더링 시 크기 변경 방지
  const inputStyle: React.CSSProperties = {
    width: '100%',
    height: '40px',
    minHeight: '40px',
    maxHeight: '40px',
    border: 'none',
    borderRadius: isMobile ? '6px' : '8px',
    paddingTop: '8px',
    paddingRight: isMobile ? '35px' : '40px',
    paddingBottom: '8px',
    paddingLeft: selectedStock ? (isMobile ? '75px' : '85px') : (isMobile ? '6px' : '8px'),
    fontSize: isMobile ? '14px' : (windowWidth < 768 ? '15px' : '16px'),
    outline: 'none',
    boxSizing: 'border-box',
    resize: 'none',
    overflow: 'hidden',
    maxWidth: '100%',
    backgroundColor: 'white',
    color: 'oklch(0.372 0.044 257.287)',
    WebkitAppearance: 'none',
    appearance: 'none',
    lineHeight: '1.5',
    transition: 'none',
    display: 'block', // 특정 브라우저에서 렌더링 개선
    position: 'relative' // 포지션 고정하여 레이아웃 안정성 향상
  };
  
  // 종목 필터링 함수
  const filterStocks = useCallback((searchValue: string) => {
    // 검색어가 없는 경우
    if (!searchValue.trim()) {
      // 최근 조회 종목이 있으면 표시
      if (recentStocks.length > 0) {
        setFilteredStocks(recentStocks);
      } else {
        // 최근 조회 종목이 없으면 상위 5개 종목 표시
        setFilteredStocks(stockOptions.slice(0, 5));
      }
      return;
    }

    // 검색어가 있는 경우 - 종목명이나 종목코드로 검색
    // 검색어 정리 및 소문자 변환
    const searchTerm = searchValue.toLowerCase().trim();
    
    // 전체 종목 목록에서 검색 수행
    const filtered = stockOptions
      .filter(stock => {
        const stockName = stock.stockName.toLowerCase();
        const stockCode = stock.stockCode;
        return stockName.includes(searchTerm) || stockCode.includes(searchTerm);
      })
      .slice(0, 30); // 최대 30개 결과로 확장

    // 검색어가 있을 때는 무조건 검색 결과를 적용
    setFilteredStocks(filtered);
    
    // 필터링된 결과가 바뀌면 포커스 인덱스를 초기화
    setFocusedItemIndex(0);
  }, [stockOptions, recentStocks]);
  
  // 종목 선택 시 inputMessage 초기화 핸들러
  const handleSelectStock = useCallback((stock: StockOption | null) => {
    // 종목이 선택되면 메시지 입력창 초기화 및 팝업 닫기
    if (stock) {
      setInputMessage('');
      onShowStockSuggestions(false);
      onSearchModeChange(false);
      
      // 선택 후 입력 필드에 포커스 설정
      setTimeout(() => {
        if (inputRef.current) {
          inputRef.current.focus();
        }
      }, 50);
    }
    
    // 부모 컴포넌트의 onStockSelect 호출
    onStockSelect(stock);
  }, [onStockSelect, setInputMessage, onShowStockSuggestions, onSearchModeChange]);
  
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
        // input 요소에 포커스 설정
        if (inputRef.current) {
          inputRef.current.focus();
        }
        
        // 선택된 종목 해제
        onStockSelect(null);
        
        // 활성 세션이 없는 경우에만 종목 추천 팝업 표시
        if (!currentChatSession) {
          onShowStockSuggestions(true);
          onSearchModeChange(true);
          
          // 최근 조회 종목 표시
          if (recentStocks.length > 0) {
            setFilteredStocks(recentStocks);
          } else {
            setFilteredStocks(stockOptions.slice(0, 5));
          }
        }
        
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
  }, [inputMessage, selectedStock, onStockSelect, onShowStockSuggestions, onSearchModeChange, isProcessing, recentStocks, stockOptions, currentChatSession]);
  
  // 키보드 이벤트 처리 (추가 기능 포함)
  const handleKeyDown = useCallback((e: React.KeyboardEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    // 검색 모드이고 종목 제안이 표시되고 있는 경우 방향키 및 엔터키 감지 처리
    if ((searchMode || showStockSuggestions) && displayedStocks.length > 0) {
      // 아래쪽 화살표 키: 다음 항목으로 포커스 이동
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        setFocusedItemIndex(prev => (prev < displayedStocks.length - 1 ? prev + 1 : prev));
        return;
      }
      
      // 위쪽 화살표 키: 이전 항목으로 포커스 이동
      if (e.key === 'ArrowUp') {
        e.preventDefault();
        setFocusedItemIndex(prev => (prev > 0 ? prev - 1 : 0));
        return;
      }
      
      // Enter 키: 현재 포커스된 종목 선택
      if (e.key === 'Enter' && !e.shiftKey && displayedStocks.length > 0) {
        // 포커스된 아이템이 있으면 선택
        if (focusedItemIndex >= 0 && focusedItemIndex < displayedStocks.length) {
          e.preventDefault();
          handleSelectStock(displayedStocks[focusedItemIndex]);
          return;
        }
      }
    }
    
    // 이미 키가 눌려 있는 상태라면 무시
    if (isKeyPressed) {
      e.preventDefault();
      return;
    }
    
    // Backspace 키이고, 입력창이 비어있고, 종목이 선택된 상태인지 확인
    if (e.key === 'Backspace' && inputMessage === '' && selectedStock) {
      e.preventDefault(); // 기본 Backspace 동작 방지
      
      // 선택된 종목 해제
      onStockSelect(null);
      
      // 활성 세션이 없는 경우에만 종목 추천 팝업 표시
      if (!currentChatSession) {
        onShowStockSuggestions(true);
        onSearchModeChange(true);
        
        // 최근 조회 종목 표시
        if (recentStocks.length > 0) {
          setFilteredStocks(recentStocks);
        } else {
          setFilteredStocks(stockOptions.slice(0, 5));
        }
      }
    }
    
    // Enter 키 눌렀을 때 메시지 전송 (Shift+Enter는 줄바꿈)
    // 종목이 선택되어 있거나 현재 채팅 세션이 있는 경우 메시지 전송 가능
    if (e.key === 'Enter' && !e.shiftKey && inputMessage.trim() !== '' && (selectedStock || hasActiveSession)) {
      e.preventDefault();
      
      // 시간 제한 체크
      const { isRestricted, nextAvailableTime } = checkTimeRestriction();
      if (isRestricted) {
        const restrictionMessage = getRestrictionMessage(nextAvailableTime);
        toast.error(restrictionMessage);
        return;
      }

      setIsKeyPressed(true);
      onSendMessage();
      // scrollToBottom이 제공되었다면 호출
      if (scrollToBottom) {
        scrollToBottom();
      }
    } else if (e.key === 'Enter' && !e.shiftKey && inputMessage.trim() !== '' && !selectedStock && !hasActiveSession) {
      // 전송 불가 상태
    }
  }, [
    inputMessage, 
    selectedStock, 
    onStockSelect, 
    onShowStockSuggestions, 
    onSearchModeChange, 
    onSendMessage, 
    isKeyPressed, 
    scrollToBottom, 
    recentStocks, 
    stockOptions,
    searchMode,
    showStockSuggestions,
    filteredStocks,
    focusedItemIndex,
    handleSelectStock,
    hasActiveSession,
    currentChatSession,
    displayedStocks
  ]);
  
  const handleKeyUp = useCallback((e: React.KeyboardEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    if (e.key === 'Enter') {
      setIsKeyPressed(false);
    }
  }, []);
  
  // 입력 필드 포커스 시 종목 추천 목록 표시
  const handleInputFocus = () => {
    // 활성 세션이 있으면 종목 제안 팝업을 표시하지 않음
    if (currentChatSession) {
      return;
    }
    
    // 종목 선택 팝업이 이미 열려 있으면 검색 모드 활성화
    if (showStockSuggestions) {
      onSearchModeChange(true);
      
      // 최근 종목이 있으면 표시
      if (recentStocks.length > 0) {
        setFilteredStocks(recentStocks);
      } else {
        // 최근 조회 종목이 없으면 기본 종목 추천 표시 (상위 5개)
        setFilteredStocks(stockOptions.slice(0, 5));
      }
      return;
    }
    
    // 종목이 선택되어 있지 않은 경우, 종목 추천 팝업 표시 및 검색 모드 활성화
    if (!selectedStock) {
      onShowStockSuggestions(true);
      onSearchModeChange(true);
      
      // 최근 조회 종목이 있으면 표시
      if (recentStocks.length > 0) {
        setFilteredStocks(recentStocks);
      } else {
        // 최근 조회 종목이 없으면 기본 종목 추천 표시 (상위 5개)
        setFilteredStocks(stockOptions.slice(0, 5));
      }
    }
  };
  
  // 입력 필드 값 변경 처리
  const handleInputChange = useCallback((e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    const value = e.target.value;
    
    // 입력값을 먼저 설정하여 UI가 즉시 업데이트되도록 함
    setInputMessage(value);
    
    // 활성 세션이 있으면 종목 제안 팝업을 표시하지 않음
    if (currentChatSession) {
      return;
    }
    
    // 종목이 선택되지 않은 경우, 종목 추천 표시
    if (!selectedStock) {
      if (!showStockSuggestions) {
        onShowStockSuggestions(true);
      }
      
      // 검색 모드 활성화
      if (!searchMode) {
        onSearchModeChange(true);
      }
    }
    
    // 종목 선택 팝업이 열려 있거나 검색 모드인 경우만 종목 검색 로직 실행
    if (showStockSuggestions || searchMode) {
      // 검색어가 있을 때만 필터링 수행, 없으면 최근 종목 표시
      if (value.trim().length > 0) {
        filterStocks(value);
      } else {
        // 검색어가 없을 때는 최근 조회 종목 또는 기본 종목 표시
        if (recentStocks.length > 0) {
          setFilteredStocks(recentStocks);
        } else {
          setFilteredStocks(stockOptions.slice(0, 5));
        }
      }
    }
  }, [
    setInputMessage, 
    selectedStock, 
    showStockSuggestions, 
    searchMode, 
    onShowStockSuggestions, 
    onSearchModeChange, 
    currentChatSession, 
    filterStocks,
    recentStocks,
    stockOptions,
    filteredStocks
  ]);
  
  // 종목 배지 클릭 시 종목 선택 팝업 표시
  const handleStockBadgeClick = () => {
    // 활성 세션이 있으면 종목 제안 팝업을 표시하지 않음
    if (currentChatSession) {
      return;
    }
    
    onShowStockSuggestions(true);
    onSearchModeChange(true);
    setInputMessage('');
    
    // 최근 조회 종목이 있으면 표시
    if (recentStocks.length > 0) {
      setFilteredStocks(recentStocks);
    } else {
      // 최근 조회 종목이 없으면 기본 종목 추천 표시 (상위 5개)
      setFilteredStocks(stockOptions.slice(0, 5));
    }
    
    // 포커스 설정
    setTimeout(() => {
      if (inputRef.current) {
        inputRef.current.focus();
      }
    }, 100);
  };
  
  // 전송 버튼 클릭 핸들러
  const handleSendButtonClick = useCallback(() => {
    // 시간 제한 체크
    const { isRestricted, nextAvailableTime } = checkTimeRestriction();
    if (isRestricted) {
      const restrictionMessage = getRestrictionMessage(nextAvailableTime);
      toast.error(restrictionMessage);
      return;
    }

    // 종목이 선택되어 있거나 현재 채팅 세션이 있는 경우 메시지 전송 가능
    if ((selectedStock || hasActiveSession) && inputMessage.trim() !== '' && !isProcessing) {
      onSendMessage();
      // scrollToBottom이 제공되었다면 호출
      if (scrollToBottom) {
        scrollToBottom();
      }
    } else if (!selectedStock && !hasActiveSession) {
      // 전송 불가 상태
    }
  }, [selectedStock, inputMessage, isProcessing, onSendMessage, scrollToBottom, hasActiveSession]);
  
  // 컴포넌트 마운트 시 초기 상태 설정
  useEffect(() => {
    // 초기 마운트 시 종목이 선택되어 있지 않고 활성 세션도 없는 경우 검색 모드 활성화
    if (!selectedStock && !currentChatSession && !isInputCentered) {
      onSearchModeChange(true);

      // 종목 추천 팝업도 표시
      if (!showStockSuggestions) {
        onShowStockSuggestions(true);
      }
    }
    
    if (showStockSuggestions) {
      // 최근 조회 종목이 있으면 표시
      if (recentStocks.length > 0) {
        setFilteredStocks(recentStocks);
      } else {
        // 최근 조회 종목이 없으면 기본 종목 추천 표시 (상위 5개)
        setFilteredStocks(stockOptions.slice(0, 5));
      }
      
      // 초기 포커스 인덱스 설정
      setFocusedItemIndex(0);
    }
  }, [showStockSuggestions, recentStocks, stockOptions, selectedStock, currentChatSession, isInputCentered, onSearchModeChange, onShowStockSuggestions]);
  
  // displayedStocks 변경 핸들러
  const handleDisplayedStocksChange = useCallback((stocks: StockOption[]) => {
    setDisplayedStocks(stocks);
  }, []);

  // 자동 높이 조절 기능 제거 - 일관된 고정 높이 유지 위해 해당 기능을 비활성화함
  
  return (
    <div className={`input-area ${isInputReady ? 'input-area-visible' : 'input-area-hidden'}`} ref={inputBoxRef} style={inputAreaStyle}>
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
              종목 선택 후 분석을 요청하세요.
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
          {selectedStock && !currentChatSession && (
            <StockBadge
              stock={selectedStock}
              isProcessing={isProcessing}
              onClick={handleStockBadgeClick}
            />
          )}
          
          <textarea
            ref={inputRef}
            placeholder={showStockSuggestions || searchMode 
              ? "종목명 또는 종목코드 검색" 
              : (hasActiveSession
                ? "생성된 문서 내에서 이어지는 질문을 해보세요. 다른 종목은 새 채팅을 시작해주세요."
                : "이 종목에 관하여 궁금한 점을 물어보세요.")}
            className="integrated-input-field fixed-height-textarea"
            value={inputMessage}
            onChange={handleInputChange}
            onFocus={(e) => {
              handleInputFocus();
            }}
            onBlur={() => {
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
              cursor: isProcessing ? 'not-allowed' : 'text',
              resize: 'none',
              overflow: 'hidden',
              minHeight: '40px',
              maxHeight: '120px',
              lineHeight: '1.5',
            }}
          />
          
          {/* 전송 아이콘 */}
          <SendButton
            onClick={handleSendButtonClick}
            disabled={isProcessing || !inputMessage.trim() || (!selectedStock && !hasActiveSession)}
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
              stockOptions={stockOptions}
              onSelectStock={handleSelectStock}
              onClearRecentStocks={onClearRecentStocks}
              isInputCentered={isInputCentered}
              focusedItemIndex={focusedItemIndex}
              searchTerm={inputMessage}
              onDisplayedStocksChange={handleDisplayedStocksChange}
            />
          </div>
        )}
      </div>
    </div>
  );
}

export default React.memo(InputArea); 