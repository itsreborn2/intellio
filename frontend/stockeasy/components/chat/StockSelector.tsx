'use client'

import { CSSProperties, useState, useEffect } from 'react'
import { StockOption } from './types'

interface StockSelectorProps {
  selectedStock: StockOption | null
  onStockSelect: (stock: StockOption) => void
  stockOptions: StockOption[]
  filteredStocks: StockOption[]
  recentStocks: StockOption[]
  isMobile: boolean
  windowWidth: number
  showStockSuggestions: boolean
  setShowStockSuggestions: (show: boolean) => void
  isLoading: boolean
  error: string | null
  searchMode: boolean
  setSearchMode: (mode: boolean) => void
  stockSuggestionsRef: React.RefObject<HTMLDivElement>
  isInputCentered: boolean
}

export default function StockSelector({
  selectedStock,
  onStockSelect,
  stockOptions,
  filteredStocks,
  recentStocks,
  isMobile,
  windowWidth,
  showStockSuggestions,
  setShowStockSuggestions,
  isLoading,
  error,
  searchMode,
  setSearchMode,
  stockSuggestionsRef,
  isInputCentered
}: StockSelectorProps) {
  
  // 종목 추천 스타일
  const stockSuggestionsStyle: CSSProperties = {
    position: 'absolute',
    bottom: `calc(100% + ${isMobile ? 5 : 30}px)`,
    left: 0,
    right: 0,
    width: isMobile ? '90%' : '100%',
    margin: isMobile ? '0 auto' : '0',
    maxHeight: isMobile ? '180px' : '200px',
    overflowY: 'auto',
    backgroundColor: 'white',
    border: '1px solid #ccc',
    borderRadius: '8px',
    boxShadow: '0 2px 10px rgba(0, 0, 0, 0.1)',
    zIndex: 100,
    padding: isMobile ? '5px' : '6px',
    transform: isMobile ? 'none' : (isInputCentered ? 'translateY(-30px)' : 'none'),
  }

  // 종목 버튼 클릭 시 종목 목록 토글
  const handleStockBadgeClick = () => {
    setShowStockSuggestions(true)
    setSearchMode(true)
    
    // 최근 종목이 있으면 표시, 없으면 기본 종목 추천 표시
    if (recentStocks.length > 0) {
      // 최근 조회 종목 표시
    } else {
      // 기본 종목 추천 표시 (상위 5개)
    }
  }

  // 종목 선택 시 팝업 닫기
  const handleSelectStock = (stock: StockOption) => {
    onStockSelect(stock)
    setShowStockSuggestions(false)
  }

  // 선택된 종목 배지 렌더링
  const renderStockBadge = () => {
    if (!selectedStock) return null
    
    return (
      <div 
        style={{
          display: 'flex',
          alignItems: 'center',
          padding: '4px 10px',
          margin: '0 0 0 8px',
          height: '26px',
          borderRadius: '6px',
          border: '1px solid #ddd',
          backgroundColor: '#D8EFE9',
          color: '#333',
          fontSize: '0.7rem',
          fontWeight: 'normal',
          whiteSpace: 'nowrap',
          cursor: 'pointer'
        }}
        onClick={handleStockBadgeClick}
        title="클릭하여 종목 변경"
      >
        {selectedStock.stockName}
      </div>
    )
  }

  // 종목 추천 목록 팝업 렌더링
  const renderSuggestions = () => {
    if (!showStockSuggestions) return null
    
    return (
      <div
        style={stockSuggestionsStyle}
        ref={stockSuggestionsRef}
      >
        {isLoading ? (
          <div style={{ padding: '8px', textAlign: 'center' }}>종목 로딩 중...</div>
        ) : error ? (
          <div style={{ padding: '8px', color: 'red' }}>{error}</div>
        ) : filteredStocks.length === 0 ? (
          <div style={{ padding: '8px', textAlign: 'center', color: '#666' }}>
            검색 결과가 없습니다
          </div>
        ) : (
          <>
            <StockOptionsList 
              title="유저들의 TOP10" 
              stocks={filteredStocks} 
              onSelect={handleSelectStock}
              isMobile={isMobile}
            />
            
            {/* 최근 조회 종목 목록 */}
            {!isLoading && !error && recentStocks.length > 0 && (
              <RecentStocksList 
                stocks={recentStocks} 
                onSelect={handleSelectStock}
                onClear={() => {
                  setShowStockSuggestions(false)
                  localStorage.removeItem('recentStocks')
                  // recentStocks를 비우는 함수를 호출해야 하나, 이 컴포넌트에서는 상태를 변경할 수 없음
                  // props로 상태 변경 함수를 추가해야 함
                }}
                isMobile={isMobile}
              />
            )}
          </>
        )}
      </div>
    )
  }

  return (
    <>
      {renderStockBadge()}
      {renderSuggestions()}
    </>
  )
}

// 종목 옵션 목록 컴포넌트
interface StockOptionsListProps {
  title: string
  stocks: StockOption[]
  onSelect: (stock: StockOption) => void
  isMobile: boolean
}

function StockOptionsList({ title, stocks, onSelect, isMobile }: StockOptionsListProps) {
  return (
    <div style={{ 
      paddingLeft: '5px', 
      paddingRight: '5px', 
      paddingTop: '0', 
      paddingBottom: '4px' 
    }}>
      <div style={{ 
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        marginBottom: '0'
      }}>
        <div style={{ 
          fontSize: '0.7rem', 
          fontWeight: 'normal',
          color: '#666'
        }}>
          {title}
        </div>
      </div>
      <div style={{ 
        display: 'flex',
        flexDirection: 'row',
        flexWrap: 'nowrap',
        overflowX: 'auto',
        gap: '8px',
        paddingBottom: '4px',
        paddingTop: '4px',
        marginTop: '4px',
        msOverflowStyle: 'none', 
        scrollbarWidth: 'none' 
      }}>
        {stocks.map((stock) => (
          <StockButton 
            key={stock.value} 
            stock={stock} 
            onClick={() => onSelect(stock)}
            isMobile={isMobile}
          />
        ))}
      </div>
    </div>
  )
}

// 최근 조회 종목 목록 컴포넌트
interface RecentStocksListProps {
  stocks: StockOption[]
  onSelect: (stock: StockOption) => void
  onClear: () => void
  isMobile: boolean
}

function RecentStocksList({ stocks, onSelect, onClear, isMobile }: RecentStocksListProps) {
  return (
    <div style={{ 
      marginTop: '4px',
      borderTop: '1px solid #eee',
      paddingTop: '4px',
      paddingLeft: '5px', 
      paddingRight: '5px', 
      paddingBottom: '0' 
    }}>
      <div style={{ 
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        marginBottom: '0'
      }}>
        <div style={{ 
          fontSize: '13px',
          fontWeight: 'normal',
          color: '#666'
        }}>
          최근 조회 종목
        </div>
        <button
          onClick={(e) => {
            e.preventDefault()
            e.stopPropagation()
            onClear()
          }}
          style={{
            background: 'none',
            border: 'none',
            fontSize: '13px',
            color: '#999',
            cursor: 'pointer',
            padding: '4px 10px', 
            height: '28px' 
          }}
        >
          지우기
        </button>
      </div>
      <div style={{ 
        display: 'flex',
        flexDirection: 'row',
        flexWrap: 'nowrap',
        overflowX: 'auto',
        gap: '8px',
        paddingBottom: '4px',
        paddingTop: '0',
        marginTop: '2px',
        msOverflowStyle: 'none', 
        scrollbarWidth: 'none'
      }}>
        {stocks.map((stock) => (
          <StockButton 
            key={stock.value} 
            stock={stock} 
            onClick={() => onSelect(stock)}
            isMobile={isMobile}
          />
        ))}
      </div>
    </div>
  )
}

// 종목 버튼 컴포넌트
interface StockButtonProps {
  stock: StockOption
  onClick: () => void
  isMobile: boolean
}

function StockButton({ stock, onClick, isMobile }: StockButtonProps) {
  return (
    <button 
      onClick={(e) => {
        e.preventDefault()
        e.stopPropagation()
        onClick()
      }}
      style={{
        width: 'auto',
        padding: '6px 10px',
        borderRadius: '8px',
        border: '1px solid #ddd',
        backgroundColor: '#f5f5f5',
        textAlign: 'center',
        cursor: 'pointer',
        transition: 'background-color 0.2s',
        fontSize: '13px',
        color: '#333',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        gap: '6px',
        whiteSpace: 'nowrap',
        minWidth: 'fit-content',
        flexShrink: 0
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.color = '#ffffff'
        e.currentTarget.style.backgroundColor = '#40414F'
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.color = '#333'
        e.currentTarget.style.backgroundColor = '#f5f5f5'
      }}
    >
      <span style={{
        padding: '3px 8px',
        height: '24px',
        borderRadius: '6px',
        border: '1px solid #ddd',
        backgroundColor: '#f5f5f5',
        color: '#333',
        fontSize: '13px',
        fontWeight: 'normal',
        whiteSpace: 'nowrap',
        display: 'flex',
        alignItems: 'center'
      }}>
        {stock.stockName || stock.display || stock.label.split('(')[0]}
      </span>
      <span style={{
        overflow: 'hidden',
        textOverflow: 'ellipsis',
        whiteSpace: 'nowrap',
        maxWidth: '100%'
      }}>({stock.value})</span>
    </button>
  )
} 