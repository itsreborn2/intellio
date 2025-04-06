'use client'

import { useRef, CSSProperties } from 'react'
import { ChatInputProps } from './types'
import StockSelector from './StockSelector'
import { createInputAreaStyle, getContentWidth } from './styles'

export default function ChatInput({
  selectedStock,
  inputMessage,
  onInputChange,
  onSendMessage,
  onStockSelect,
  isInputCentered,
  showTitle,
  isMobile,
  windowWidth,
  showStockSuggestions,
  setShowStockSuggestions,
  stockOptions,
  filteredStocks,
  recentStocks,
  searchMode,
  setSearchMode,
  isLoading,
  error,
  inputRef,
  stockSuggestionsRef,
  handleInputFocus
}: ChatInputProps) {
  // 입력 영역 스타일
  const inputAreaStyle = createInputAreaStyle(isMobile, windowWidth, isInputCentered)

  // 통합 입력 스타일
  const integratedInputStyle: CSSProperties = {
    position: 'relative',
    width: getContentWidth(isMobile, windowWidth),
    //maxWidth: isMobile ? '100%' : (windowWidth < 768 ? '95%' : (windowWidth < 1024 ? '85%' : '70%')),
    maxWidth: '100%',
    margin: '0 auto',
    transition: 'width 0.3s ease-in-out',
    boxSizing: 'border-box',
    padding: isMobile ? '0 5px' : '0'
  }

  // 입력 필드 스타일
  const inputStyle: CSSProperties = {
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
    resize: 'none' as const,
    overflow: 'hidden',
    maxWidth: '100%'
  }

  // 엔터 키 처리
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      if (showStockSuggestions && filteredStocks.length > 0) {
        // 종목 선택 팝업이 열려 있고 검색 결과가 있는 경우, 첫 번째 종목 선택
        e.preventDefault()
        e.stopPropagation()
        onStockSelect(filteredStocks[0])
      } else if (selectedStock && inputMessage.trim() && !searchMode) {
        // 종목이 선택된 상태에서 메시지가 있고 검색 모드가 아니면 전송
        e.preventDefault()
        onSendMessage()
      }
    }
  }

  return (
    <>
      {!(isMobile && false /* isSidebarOpen */) && (
        <div className="input-area" style={inputAreaStyle}>
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
              transition: 'border-color 0.3s ease'
            }}
              onMouseEnter={(e) => {
                e.currentTarget.style.borderColor = '#10A37F'
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.borderColor = '#282A2E'
              }}
            >
              {/* 종목 선택기 */}
              <StockSelector
                selectedStock={selectedStock}
                onStockSelect={onStockSelect}
                stockOptions={stockOptions}
                filteredStocks={filteredStocks}
                recentStocks={recentStocks}
                isMobile={isMobile}
                windowWidth={windowWidth}
                showStockSuggestions={showStockSuggestions}
                setShowStockSuggestions={setShowStockSuggestions}
                isLoading={isLoading}
                error={error}
                searchMode={searchMode}
                setSearchMode={setSearchMode}
                stockSuggestionsRef={stockSuggestionsRef}
                isInputCentered={isInputCentered}
              />
              
              {/* 입력 필드 */}
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
                onChange={onInputChange}
                onFocus={handleInputFocus}
                onKeyDown={handleKeyDown}
                style={{
                  ...inputStyle,
                  border: 'none',
                  boxShadow: 'none',
                  paddingTop: '8px',
                  paddingRight: '16px',
                  paddingBottom: '8px',
                  paddingLeft: '16px',
                  flex: 1,
                  borderRadius: '6px'
                }}
              />
              
              {/* 전송 버튼 */}
              <button
                onClick={onSendMessage}
                disabled={!selectedStock || !inputMessage.trim()}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  width: '36px',
                  height: '36px',
                  borderRadius: '50%',
                  border: 'none',
                  backgroundColor: 'transparent',
                  cursor: selectedStock && inputMessage.trim() ? 'pointer' : 'not-allowed',
                  opacity: selectedStock && inputMessage.trim() ? 1 : 0.5,
                  marginRight: '8px'
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
            </div>
          </div>
        </div>
      )}
    </>
  )
} 