/**
 * analyst-searchbar.tsx
 * 애널리스트 페이지용 종목 검색 및 선택 컴포넌트
 */
'use client';

import React, { useState, useEffect, useRef } from 'react';

// 종목 타입 정의
interface StockOption {
  value: string;
  label: string;
  display?: string;
  stockName: string;
  stockCode: string;
}

// 컴포넌트 Props 타입 정의
interface AnalystSearchbarProps {
  stockOptions: StockOption[];
  selectedStock: StockOption | null;
  onStockSelect: (stock: StockOption) => void;
  isMobile: boolean;
}

const AnalystSearchbar: React.FC<AnalystSearchbarProps> = ({
  stockOptions,
  selectedStock,
  onStockSelect,
  isMobile
}) => {
  // 상태 관리
  const [showStockSuggestions, setShowStockSuggestions] = useState<boolean>(false);
  const [searchTerm, setSearchTerm] = useState<string>('');
  const [filteredStocks, setFilteredStocks] = useState<StockOption[]>([]);
  const [recentStocks, setRecentStocks] = useState<StockOption[]>([]);
  const [isMounted, setIsMounted] = useState<boolean>(false);
  
  const inputRef = useRef<HTMLInputElement>(null);
  const stockSuggestionsRef = useRef<HTMLDivElement>(null);
  
  const MAX_RECENT_STOCKS = 5; // 최근 조회 종목 최대 개수

  // 클라이언트 사이드 렌더링 확인
  useEffect(() => {
    setIsMounted(true);

    // 로컬 스토리지에서 최근 조회 종목 불러오기
    try {
      const recentStocksStr = localStorage.getItem('recentStocks');
      if (recentStocksStr) {
        const savedRecentStocks = JSON.parse(recentStocksStr);
        if (Array.isArray(savedRecentStocks)) {
          setRecentStocks(savedRecentStocks);
        }
      }
    } catch (error) {
      console.warn('최근 조회 종목 불러오기 실패:', error);
    }

    // 외부 클릭 이벤트 리스너 추가
    const handleClickOutside = (event: MouseEvent) => {
      if (
        stockSuggestionsRef.current && 
        !stockSuggestionsRef.current.contains(event.target as Node) &&
        inputRef.current && 
        !inputRef.current.contains(event.target as Node)
      ) {
        setShowStockSuggestions(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);

    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, []);

  // 입력 변경 처리
  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value;
    setSearchTerm(value);

    // 검색어가 있는 경우 종목 필터링
    if (value.trim()) {
      const filtered = stockOptions.filter(stock => 
        stock.stockName.toLowerCase().includes(value.toLowerCase()) || 
        stock.stockCode.toLowerCase().includes(value.toLowerCase())
      );
      setFilteredStocks(filtered.slice(0, 10)); // 최대 10개 결과만 표시
    } else {
      // 검색어가 없는 경우 최근 조회 종목 또는 기본 종목 표시
      if (recentStocks.length > 0) {
        setFilteredStocks(recentStocks);
      } else {
        setFilteredStocks(stockOptions.slice(0, 10));
      }
    }
    
    // 검색어가 있으면 종목 추천 목록 표시
    if (!showStockSuggestions) {
      setShowStockSuggestions(true);
    }
  };

  // 종목 선택 처리
  const handleStockSelect = (stock: StockOption) => {
    onStockSelect(stock);
    setSearchTerm('');
    setShowStockSuggestions(false);

    // 최근 조회 종목에 추가
    const isExist = recentStocks.some(item => item.value === stock.value);
    if (!isExist) {
      const newRecentStocks = [stock, ...recentStocks].slice(0, MAX_RECENT_STOCKS);
      setRecentStocks(newRecentStocks);
      
      // 로컬 스토리지에 저장
      try {
        localStorage.setItem('recentStocks', JSON.stringify(newRecentStocks));
      } catch (error) {
        console.warn('최근 조회 종목 저장 실패:', error);
      }
    }
  };

  // 종목 추천 목록 스타일
  const stockSuggestionsStyle: React.CSSProperties = {
    position: 'absolute',
    top: '100%',
    left: '0',
    right: '0',
    zIndex: 1000,
    backgroundColor: 'white',
    border: '1px solid #ddd',
    borderRadius: '8px',
    boxShadow: '0 4px 8px rgba(0, 0, 0, 0.1)',
    marginTop: '8px',
    maxHeight: '300px',
    overflowY: 'auto',
    width: '100%'
  };

  return (
    <div className="relative w-full">
      <div className="flex items-center justify-between w-full">
        <div className="flex items-center flex-1">
          {/* 종목 선택 버튼 */}
          <div className="flex items-center flex-1">
            {selectedStock ? (
              <div 
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  padding: '4px 10px',
                  margin: '0',
                  height: '40px',
                  width: '100%',
                  borderRadius: '30px',
                  backgroundColor: '#D8EFE9', // 연한 민트색으로 변경
                  color: '#333',
                  fontSize: '13px',
                  fontWeight: 'normal',
                  whiteSpace: 'nowrap',
                  cursor: 'pointer'
                }}
                onClick={() => {
                  setShowStockSuggestions(true);
                  setSearchTerm('');
                  
                  // 최근 종목이 있으면 표시, 없으면 기본 종목 추천 표시
                  if (recentStocks.length > 0) {
                    setFilteredStocks(recentStocks);
                  } else {
                    setFilteredStocks(stockOptions.slice(0, 10));
                  }
                }}
                title="클릭하여 종목 변경"
              >
                <span style={{ fontWeight: 'bold' }}>{selectedStock.stockName}</span>
                <span style={{ marginLeft: '6px', color: '#666' }}>({selectedStock.stockCode})</span>
              </div>
            ) : (
              <div 
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  padding: '4px 10px',
                  margin: '0',
                  height: '40px',
                  width: '100%',
                  borderRadius: '30px',
                  backgroundColor: isMobile ? '#ffffff' : '#f5f5f5',
                  color: '#333',
                  fontSize: '13px',
                  fontWeight: 'normal',
                  whiteSpace: 'nowrap',
                  cursor: 'pointer'
                }}
                onClick={() => {
                  setShowStockSuggestions(true);
                  setSearchTerm('');
                  
                  // 최근 종목이 있으면 표시, 없으면 기본 종목 추천 표시
                  if (recentStocks.length > 0) {
                    setFilteredStocks(recentStocks);
                  } else {
                    setFilteredStocks(stockOptions.slice(0, 10));
                  }
                }}
                title="클릭하여 종목 선택"
              >
                {/* 주식 캔들 아이콘 */}
                <svg 
                  width="16" 
                  height="16" 
                  viewBox="0 0 24 24" 
                  fill="none" 
                  xmlns="http://www.w3.org/2000/svg"
                  style={{ marginRight: '6px' }}
                >
                  {/* 첫 번째 캔들 (상승) */}
                  <rect x="4" y="8" width="3" height="8" fill="#10A37F" />
                  <line x1="5.5" y1="4" x2="5.5" y2="8" stroke="#10A37F" strokeWidth="1" />
                  <line x1="5.5" y1="16" x2="5.5" y2="20" stroke="#10A37F" strokeWidth="1" />
                  
                  {/* 두 번째 캔들 (하락) */}
                  <rect x="10" y="6" width="3" height="10" fill="#E74C3C" />
                  <line x1="11.5" y1="3" x2="11.5" y2="6" stroke="#E74C3C" strokeWidth="1" />
                  <line x1="11.5" y1="16" x2="11.5" y2="21" stroke="#E74C3C" strokeWidth="1" />
                  
                  {/* 세 번째 캔들 (상승) */}
                  <rect x="16" y="10" width="3" height="6" fill="#10A37F" />
                  <line x1="17.5" y1="6" x2="17.5" y2="10" stroke="#10A37F" strokeWidth="1" />
                  <line x1="17.5" y1="16" x2="17.5" y2="19" stroke="#10A37F" strokeWidth="1" />
                </svg>
                종목선택
              </div>
            )}
            {!selectedStock && (
              <input
                ref={inputRef}
                placeholder=""
                type="text"
                value={searchTerm}
                onChange={handleInputChange}
                onFocus={() => {
                  setShowStockSuggestions(true);
                  if (!searchTerm.trim()) {
                    if (recentStocks.length > 0) {
                      setFilteredStocks(recentStocks);
                    } else {
                      setFilteredStocks(stockOptions.slice(0, 10));
                    }
                  }
                }}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && showStockSuggestions && filteredStocks.length > 0) {
                    e.preventDefault();
                    e.stopPropagation();
                    handleStockSelect(filteredStocks[0]);
                  }
                }}
                style={{
                  width: '0',
                  height: '0',
                  border: 'none',
                  boxShadow: 'none',
                  padding: '0',
                  margin: '0',
                  opacity: '0',
                  position: 'absolute'
                }}
              />
            )}
            
            {/* 검색 아이콘 */}
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                width: '36px',
                height: '36px',
                borderRadius: '50%',
                border: 'none',
                backgroundColor: 'transparent',
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
                  d="M21 21L15 15M17 10C17 13.866 13.866 17 10 17C6.13401 17 3 13.866 3 10C3 6.13401 6.13401 3 10 3C13.866 3 17 6.13401 17 10Z"
                  stroke="#333333"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
            </div>
          </div>
        </div>
        
        {/* 종목 추천 목록 */}
        {isMounted && showStockSuggestions && (
          <div
            style={stockSuggestionsStyle}
            ref={stockSuggestionsRef}
          >
            {filteredStocks.length === 0 ? (
              <div style={{ padding: '8px', textAlign: 'center', color: '#666' }}>
                검색 결과가 없습니다
              </div>
            ) : (
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
                    fontSize: '13px',
                    fontWeight: 'normal',
                    color: '#666'
                  }}>
                    유저들의 TOP10
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
                  {filteredStocks.map((stock, index) => (
                    <button
                      key={`${stock.value}-${index}`}
                      onClick={() => handleStockSelect(stock)}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '4px',
                        padding: '6px 10px',
                        backgroundColor: '#f5f5f5',
                        border: 'none',
                        borderRadius: '20px',
                        fontSize: '13px',
                        color: '#333',
                        whiteSpace: 'nowrap',
                        cursor: 'pointer',
                        transition: 'all 0.2s ease',
                        flexShrink: 0
                      }}
                      onMouseEnter={(e) => {
                        e.currentTarget.style.color = 'white';
                        e.currentTarget.style.backgroundColor = '#40414F';
                      }}
                      onMouseLeave={(e) => {
                        e.currentTarget.style.color = '#333';
                        e.currentTarget.style.backgroundColor = '#f5f5f5';
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
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default AnalystSearchbar;
