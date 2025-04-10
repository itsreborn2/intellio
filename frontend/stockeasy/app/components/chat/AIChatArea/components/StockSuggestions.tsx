/**
 * StockSuggestions.tsx
 * 종목 검색 제안 컴포넌트
 */
'use client';

import React, { useRef } from 'react';
import { StockOption } from '../types';
import { useIsMobile } from '../hooks';

interface StockSuggestionsProps {
  isLoading: boolean;
  error: string | null;
  filteredStocks: StockOption[];
  recentStocks: StockOption[];
  stockOptions?: StockOption[]; // 전체 종목 목록 추가
  onSelectStock: (stock: StockOption) => void;
  onClearRecentStocks: () => void;
  isInputCentered?: boolean;
}

export function StockSuggestions({
  isLoading,
  error,
  filteredStocks,
  recentStocks,
  stockOptions = [], // 전체 종목 목록 (기본값 빈 배열)
  onSelectStock,
  onClearRecentStocks,
  isInputCentered = false
}: StockSuggestionsProps) {
  const isMobile = useIsMobile();
  const containerRef = useRef<HTMLDivElement>(null);
  
  // 종목 제안 스타일
  const stockSuggestionsStyle: React.CSSProperties = {
    position: 'absolute',
    bottom: `calc(100% + ${isMobile ? 5 : 30}px)`,
    left: 0,
    right: 0,
    width: isMobile ? '100%' : '100%',
    margin: isMobile ? '0 auto' : '0',
    maxHeight: isMobile ? '180px' : '200px',
    overflowY: 'auto',
    backgroundColor: 'white',
    border: '1px solid #ccc',
    borderRadius: '8px',
    boxShadow: '0 2px 10px rgba(0, 0, 0, 0.1)',
    zIndex: 100,
    paddingTop: isMobile ? '5px' : '6px',
    paddingRight: isMobile ? '5px' : '6px',
    paddingBottom: isMobile ? '5px' : '6px',
    paddingLeft: isMobile ? '5px' : '6px',
    transform: isMobile ? 'none' : (isInputCentered ? 'translateY(-30px)' : 'none'),
  };
  
  // 종목 아이템 클릭 핸들러
  const handleStockItemClick = (stock: StockOption) => (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    onSelectStock(stock);
  };
  
  // 종목 목록이 없거나 오류가 발생한 경우 - 종목 데이터 가져오기 시도 로직 추가
  const noResultsMessage = () => {
    if (isLoading) {
      return <div style={{ paddingTop: '8px', paddingRight: '8px', paddingBottom: '8px', paddingLeft: '8px', textAlign: 'center', color: '#666' }}>종목 데이터를 불러오는 중...</div>;
    }
    
    if (error) {
      return (
        <div style={{ paddingTop: '8px', paddingRight: '8px', paddingBottom: '8px', paddingLeft: '8px', color: 'red' }}>{error}</div>
      );
    }
    
    if (!stockOptions || stockOptions.length === 0) {
      return <div style={{ paddingTop: '8px', paddingRight: '8px', paddingBottom: '8px', paddingLeft: '8px', textAlign: 'center', color: '#666' }}>종목 데이터를 불러올 수 없습니다.</div>;
    }
    
    return <div style={{ paddingTop: '8px', paddingRight: '8px', paddingBottom: '8px', paddingLeft: '8px', textAlign: 'center', color: '#666' }}>검색 결과가 없습니다.</div>;
  };
  
  return (
    <div
      style={stockSuggestionsStyle}
      ref={containerRef}
    >
      {filteredStocks.length === 0 ? (
        noResultsMessage()
      ) : (
        <div className="stock-suggestions">
          {/* 최근 조회 종목 표시 - 필터링된 종목이 최근 종목과 동일하면 제목 표시 */}
          {filteredStocks.length > 0 && JSON.stringify(filteredStocks) === JSON.stringify(recentStocks) && (
            <div className="recent-stocks-header" style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              padding: '8px 12px',
              borderBottom: '1px solid #f0f0f0'
            }}>
              <span style={{ fontSize: '14px', fontWeight: 'bold', color: '#333' }}>
                최근 조회 종목
              </span>
              {recentStocks.length > 0 && (
                <button
                  onClick={(e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    onClearRecentStocks();
                  }}
                  style={{
                    fontSize: '12px',
                    color: '#666',
                    background: 'none',
                    border: 'none',
                    cursor: 'pointer',
                    padding: '2px 4px'
                  }}
                >
                  목록 지우기
                </button>
              )}
            </div>
          )}

          {filteredStocks.map((stock, index) => (
            <div
              key={stock.value}
              className="stock-item"
              onClick={handleStockItemClick(stock)}
              style={{
                padding: '10px 12px',
                cursor: 'pointer',
                borderBottom: index < filteredStocks.length - 1 ? '1px solid #f0f0f0' : 'none',
                transition: 'background-color 0.2s',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between'
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.backgroundColor = '#f5f5f5';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.backgroundColor = 'transparent';
              }}
            >
              <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
                <span style={{ fontSize: '14px', fontWeight: 'bold', color: '#333' }}>
                  {stock.stockName}
                </span>
                <span style={{ fontSize: '12px', color: '#666' }}>
                  {stock.stockCode}
                </span>
              </div>
              <div
                style={{
                  fontSize: '12px',
                  color: '#666',
                  padding: '4px 8px',
                  borderRadius: '4px',
                  backgroundColor: '#f0f0f0'
                }}
              >
                {stock.stockCode}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// 종목 항목 컴포넌트
function StockItem({ stock, onClick }: { stock: StockOption; onClick: (e: React.MouseEvent) => void }) {
  return (
    <button 
      onClick={onClick}
      style={{
        width: 'auto',
        paddingTop: '6px',
        paddingRight: '10px',
        paddingBottom: '6px',
        paddingLeft: '10px',
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
        e.currentTarget.style.color = '#ffffff';
        e.currentTarget.style.backgroundColor = '#40414F';
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.color = '#333';
        e.currentTarget.style.backgroundColor = '#f5f5f5';
      }}
    >
      <span style={{
        paddingTop: '3px',
        paddingRight: '8px',
        paddingBottom: '3px',
        paddingLeft: '8px',
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
      }}>({stock.stockCode || stock.value})</span>
    </button>
  );
}

export default React.memo(StockSuggestions); 