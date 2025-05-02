/**
 * StockSuggestions.tsx
 * 종목 검색 제안 컴포넌트
 */
'use client';

import React, { useRef, useEffect, useMemo } from 'react';
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
  focusedItemIndex?: number; // 현재 포커스된 아이템 인덱스 추가
  searchTerm?: string; // 검색어 추가
}

export function StockSuggestions({
  isLoading,
  error,
  filteredStocks,
  recentStocks,
  stockOptions = [], // 전체 종목 목록 (기본값 빈 배열)
  onSelectStock,
  onClearRecentStocks,
  isInputCentered = false,
  focusedItemIndex = 0, // 기본값은 첫 번째 아이템
  searchTerm = ''
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
    // 헤더 영역을 침범하지 않도록 최대 높이를 동적으로 계산
    // 화면 높이의 40%를 최대로 하되, 모바일에서는 더 작게 설정
    maxHeight: `calc(40vh - ${isMobile ? 80 : 100}px)`,
    // 최소 높이도 설정하여 너무 작아지지 않도록 함
    minHeight: isMobile ? '150px' : '200px',
    overflowY: 'auto',
    backgroundColor: 'white',
    border: '1px solid #ccc',
    borderRadius: '12px',
    boxShadow: '0 4px 16px rgba(0, 0, 0, 0.15)',
    zIndex: 100,
    padding: '0',
    transform: isMobile ? 'none' : (isInputCentered ? 'translateY(-30px)' : 'none'),
    WebkitFontSmoothing: 'antialiased',
    MozOsxFontSmoothing: 'grayscale',
    backfaceVisibility: 'hidden',
  };
  
  // 헤더 고정 스타일
  const headerStyle: React.CSSProperties = {
    position: 'sticky',
    top: 0,
    backgroundColor: 'white',
    zIndex: 2,
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: '8px 10px', // 패딩 감소
    borderBottom: '2px solid #e0e0e0',
    boxShadow: '0 2px 4px rgba(0, 0, 0, 0.05)',
    minHeight: '44px', // 최소 높이 감소
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
  
  // 포커스된 아이템이 뷰에 보이도록 자동 스크롤
  const scrollToFocusedItem = (focusedIndex: number) => {
    if (containerRef.current && displayedStocks.length > 0 && 
        focusedIndex >= 0 && focusedIndex < displayedStocks.length) {
      const container = containerRef.current;
      const focusedItem = container.querySelector(`[data-index="${focusedIndex}"]`) as HTMLElement;
      
      if (focusedItem) {
        const containerTop = container.scrollTop;
        const containerBottom = containerTop + container.clientHeight;
        
        // 헤더의 높이를 계산 (헤더가 있는 경우)
        const shouldShowHeader = searchTerm === '' && recentStocks.length > 0;
        const headerHeight = shouldShowHeader ? 41 : 0;
        
        const itemTop = focusedItem.offsetTop;
        const itemBottom = itemTop + focusedItem.clientHeight;
        
        if (itemTop - headerHeight < containerTop) {
          // 아이템이 위에 있어서 보이지 않는 경우 (헤더 높이 고려)
          container.scrollTop = itemTop - headerHeight;
        } else if (itemBottom > containerBottom) {
          // 아이템이 아래에 있어서 보이지 않는 경우
          container.scrollTop = itemBottom - container.clientHeight;
        }
      }
    }
  };
  
  // 포커스된 아이템이 변경될 때 스크롤 조정
  useEffect(() => {
    scrollToFocusedItem(focusedItemIndex);
  }, [focusedItemIndex]);
  
  // 강제로 재렌더링 방지하기 위한 메모이제이션 추가
  const displayedStocks = useMemo(() => {
    const trimmedSearchTerm = searchTerm.trim();
    
    // 검색어가 있으면 검색 결과만 표시 (검색어가 최우선)
    if (trimmedSearchTerm.length > 0) {
      // 검색어와 관련된 종목만 직접 필터링
      const searchResults = stockOptions
        .filter(stock => {
          const stockName = stock.stockName.toLowerCase();
          const stockCode = stock.stockCode;
          return stockName.includes(trimmedSearchTerm.toLowerCase()) || 
                 stockCode.includes(trimmedSearchTerm);
        })
        .slice(0, 30);
      
      return searchResults;
    }
    
    // 검색어가 없고 최근 조회 종목이 있으면 최근 종목 표시
    if (recentStocks.length > 0) {
      return recentStocks;
    }
    
    // 그 외의 경우 (검색어 없고 최근 종목도 없음) 기본 필터링 결과 표시
    return filteredStocks;
  }, [searchTerm, filteredStocks, recentStocks, stockOptions]);
  
  // 최근 조회 종목 헤더 렌더링
  const renderRecentStocksHeader = () => {
    return (
      <div className="recent-stocks-header" style={headerStyle}>
        <span style={{ 
          fontSize: '14px', // 글꼴 크기 감소 
          fontWeight: 'bold', 
          color: '#333' 
        }}>
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
              padding: '4px 8px',
              borderRadius: '4px',
              transition: 'color 0.2s ease',
              backgroundColor: 'transparent',
              fontWeight: 'normal'
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.color = '#10A37F';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.color = '#666';
            }}
          >
            목록 지우기
          </button>
        )}
      </div>
    );
  };
  
  // 검색 결과 헤더 렌더링 추가
  const renderSearchResultsHeader = () => {
    // 검색어가 있을 때 직접 계산된 displayedStocks 개수 사용
    const resultCount = displayedStocks.length;
    
    return (
      <div className="search-results-header" style={headerStyle}>
        <span style={{ 
          fontSize: '14px',
          fontWeight: 'bold', 
          color: '#333' 
        }}>
          "{searchTerm}" 검색 결과 ({resultCount}개)
        </span>
      </div>
    );
  };
  
  // 검색어가 있는지와 최근 조회종목을 표시해야 하는지 확인
  const shouldShowRecentHeader = searchTerm === '' && recentStocks.length > 0 && 
                                displayedStocks.some(stock => recentStocks.some(r => r.value === stock.value));
                                
  // 검색 결과 헤더를 표시해야 하는지 확인
  const shouldShowSearchHeader = searchTerm !== '' && displayedStocks.length > 0;
  
  return (
    <div
      style={stockSuggestionsStyle}
      ref={containerRef}
    >
      {displayedStocks.length === 0 ? (
        noResultsMessage()
      ) : (
        <div className="stock-suggestions" style={{ position: 'relative' }}>
          {/* 검색 결과 헤더 - 검색어가 있을 때만 표시 */}
          {shouldShowSearchHeader && renderSearchResultsHeader()}
          
          {/* 최근 조회 종목 헤더 - 검색어가 없을 때만 표시 */}
          {shouldShowRecentHeader && renderRecentStocksHeader()}

          <div style={{ 
            paddingTop: (shouldShowRecentHeader || shouldShowSearchHeader) ? '8px' : '4px', // 패딩 감소
            paddingBottom: '4px', // 패딩 감소
            borderTop: (shouldShowRecentHeader || shouldShowSearchHeader) ? '1px solid #f0f0f0' : 'none'
          }}>
            {displayedStocks.map((stock, index) => (
              <div
                key={stock.value}
                data-index={index}
                className="stock-item"
                onClick={handleStockItemClick(stock)}
                style={{
                  padding: '8px 10px', // 패딩 감소
                  cursor: 'pointer',
                  transition: 'background-color 0.2s ease, border-color 0.2s ease, color 0.2s ease, transform 0.15s ease',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  backgroundColor: focusedItemIndex === index ? '#EAF9F6' : 'transparent',
                  border: '1px solid ' + (focusedItemIndex === index ? '#10A37F' : 'transparent'),
                  borderRadius: focusedItemIndex === index ? '10px' : '10px', // 라운딩 약간 감소
                  marginLeft: '4px',
                  marginRight: '6px',
                  marginTop: focusedItemIndex === index && index === 0 ? '2px' : index === 0 ? '2px' : '0', // 마진 감소
                  marginBottom: focusedItemIndex === index && index === displayedStocks.length - 1 ? '4px' : '0', // 마진 감소
                  zIndex: focusedItemIndex === index ? 1 : 'auto',
                  position: 'relative',
                  outline: 'none',
                  minHeight: '38px', // 최소 높이 감소
                  transform: focusedItemIndex === index ? 'scale(1.005)' : 'scale(1)',
                  transformOrigin: 'center center',
                  backfaceVisibility: 'hidden',
                }}
                onMouseEnter={(e) => {
                  if (focusedItemIndex !== index) {
                    e.currentTarget.style.backgroundColor = '#f5f5f5';
                  }
                }}
                onMouseLeave={(e) => {
                  if (focusedItemIndex !== index) {
                    e.currentTarget.style.backgroundColor = 'transparent';
                  }
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <div
                    style={{
                      fontSize: '12px', // 글꼴 크기 감소
                      color: focusedItemIndex === index ? '#0E866C' : '#666',
                      padding: '4px 8px', // 패딩 감소
                      borderRadius: '4px',
                      backgroundColor: focusedItemIndex === index ? '#e6f0ff' : '#f0f0f0',
                      fontWeight: focusedItemIndex === index ? 'bold' : 'normal',
                      transition: 'background-color 0.2s ease, color 0.2s ease, font-weight 0.2s ease'
                    }}
                  >
                    {stock.stockCode}
                  </div>
                  
                  <span style={{ 
                    fontSize: '14px', // 글꼴 크기 감소
                    fontWeight: focusedItemIndex === index ? 'bold' : 'normal',
                    color: focusedItemIndex === index ? '#0E866C' : '#333',
                    transition: 'color 0.2s ease, font-weight 0.2s ease'
                  }}>
                    {stock.stockName}
                  </span>
                </div>
                
              </div>
            ))}
          </div>
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
        paddingTop: '4px', // 패딩 감소
        paddingRight: '8px', // 패딩 감소
        paddingBottom: '4px', // 패딩 감소
        paddingLeft: '8px', // 패딩 감소
        borderRadius: '6px', // 라운딩 약간 감소
        border: '1px solid #ddd',
        backgroundColor: '#f5f5f5',
        textAlign: 'center',
        cursor: 'pointer',
        transition: 'background-color 0.2s',
        fontSize: '12px', // 글꼴 크기 감소
        color: '#333',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        gap: '4px', // 간격 감소
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
        paddingTop: '2px', // 패딩 감소
        paddingRight: '6px', // 패딩 감소
        paddingBottom: '2px', // 패딩 감소
        paddingLeft: '6px', // 패딩 감소
        height: '20px', // 높이 감소
        borderRadius: '4px', // 라운딩 약간 감소
        border: '1px solid #ddd',
        backgroundColor: '#f5f5f5',
        color: '#333',
        fontSize: '12px', // 글꼴 크기 감소
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