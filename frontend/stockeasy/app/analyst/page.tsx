'use client';

import React, { useState, useEffect, useRef } from 'react';
import Sidebar from '../components/Sidebar'; // 사이드바 컴포넌트 import
import Papa from 'papaparse';
import dynamic from 'next/dynamic';

// 동적으로 StockAnalyticsChart 컴포넌트 로드
const StockAnalyticsChart = dynamic(
  () => import('../components/StockAnalyticsChart'),
  { ssr: false, loading: () => <p className="text-sm text-gray-500">차트를 불러오는 중...</p> }
);

// 종목 타입 정의
interface StockOption {
  value: string;
  label: string;
  display?: string;
  stockName: string;
  stockCode: string;
}

/**
 * AI 애널리스트 페이지 컴포넌트
 * 주식 분석 및 투자 전략에 대한 AI 기반 분석 정보를 제공하는 페이지
 */
const AnalystPage = () => {
  const [loading, setLoading] = useState(true);
  const [stockOptions, setStockOptions] = useState<StockOption[]>([]);
  const [selectedStock, setSelectedStock] = useState<StockOption | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [showStockSuggestions, setShowStockSuggestions] = useState<boolean>(false);
  const [searchTerm, setSearchTerm] = useState<string>('');
  const [filteredStocks, setFilteredStocks] = useState<StockOption[]>([]);
  const [recentStocks, setRecentStocks] = useState<StockOption[]>([]);
  const [isMounted, setIsMounted] = useState<boolean>(false);
  const [isMobile, setIsMobile] = useState<boolean>(false);
  
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

  // 모바일 환경 감지
  useEffect(() => {
    const checkIfMobile = () => {
      setIsMobile(window.innerWidth <= 768);
    };

    // 초기 실행
    checkIfMobile();

    // 화면 크기 변경 시 감지
    window.addEventListener('resize', checkIfMobile);

    // 컴포넌트 언마운트 시 이벤트 리스너 제거
    return () => {
      window.removeEventListener('resize', checkIfMobile);
    };
  }, []);

  // CSV 파일에서 종목 리스트 가져오기
  useEffect(() => {
    // 클라이언트 사이드에서만 실행
    if (!isMounted) return;

    const fetchStockList = async () => {
      try {
        setIsLoading(true);
        setError(null);

        // 서버 캐시 CSV 파일 경로
        const csvFilePath = '/requestfile/stock-data/stock_1idvb5kio0d6dchvoywe7ovwr-ez1cbpb.csv';

        // 서버 캐시 파일 가져오기
        const response = await fetch(csvFilePath, { cache: 'no-store' });

        if (!response.ok) {
          throw new Error(`서버 캐시 파일 로드 오류: ${response.status}`);
        }

        // CSV 파일 내용 가져오기
        const csvContent = await response.text();

        // CSV 파싱
        const parsedData = Papa.parse(csvContent, {
          header: true,
          skipEmptyLines: true
        });

        // 중복 제거를 위한 Set 생성
        const uniqueStocks = new Set();

        // 종목 데이터 추출
        const stockData = parsedData.data
          .filter((row: any) => row.종목명 && row.종목코드) // 종목명과 종목코드가 있는 행만 필터링
          .filter((row: any) => {
            // 중복 제거 (같은 종목코드는 한 번만 포함)
            if (uniqueStocks.has(row.종목코드)) {
              return false;
            }
            uniqueStocks.add(row.종목코드);
            return true;
          })
          .map((row: any) => ({
            value: row.종목코드, // 값은 종목코드로 설정
            label: `${row.종목명}(${row.종목코드})`, // 라벨은 종목명(종목코드)로 설정
            display: row.종목명, // 메인 디스플레이 텍스트는 종목명만
            stockName: row.종목명, // 종목명 저장
            stockCode: row.종목코드 // 종목코드 저장
          }));

        if (stockData.length > 0) {
          console.log(`종목 데이터 ${stockData.length}개 로드 완료`);
          setStockOptions(stockData);
          setFilteredStocks(stockData.slice(0, 10)); // 상위 10개 종목만 표시
        } else {
          const errorMsg = '유효한 종목 데이터를 받지 못했습니다.';
          console.error(errorMsg);
          setError(errorMsg);
        }

        setIsLoading(false);
        setLoading(false);
      } catch (error) {
        const errorMsg = error instanceof Error ? error.message : '종목 리스트를 가져오는 중 오류가 발생했습니다.';
        console.error('종목 리스트 가져오기 오류:', error);
        setError(errorMsg);
        setIsLoading(false);
        setLoading(false);
      }
    };

    fetchStockList();
  }, [isMounted]);

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
    setSelectedStock(stock);
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

  // 종목 선택 팝업 스타일
  const stockSuggestionsStyle: React.CSSProperties = {
    position: 'absolute',
    top: 'calc(100% + 8px)',
    right: 0, // 오른쪽 정렬 유지
    width: '600px', // 너비를 500px로 조정
    maxHeight: '200px',
    overflowY: 'auto',
    backgroundColor: 'white',
    borderRadius: '8px',
    boxShadow: '0 4px 12px rgba(0, 0, 0, 0.1)',
    zIndex: 1000,
    padding: '8px',
    border: '1px solid #ddd'
  };

  if (loading) {
    return <div className="p-4">Loading...</div>;
  }

  return (
    <div className="flex"> {/* flex 컨테이너 추가 */}
      {/* 사이드바 */}
      <Sidebar />
      
      {/* 메인 콘텐츠 영역 - 모바일 최적화 */}
      <div className="flex-1 p-0 sm:p-2 md:p-4 overflow-auto ml-0 md:ml-16 w-full">
        {/* Inner container for width limit and centering */}
        <div className="max-w-6xl mx-auto">
          {/* 세로로 6:4 비율로 나누기 위한 flex 컨테이너 */}
          <div className="flex flex-col md:flex-row gap-2 md:gap-4">
            {/* 첫 번째 영역 (60%) */}
            <div className="w-full md:w-[60%]">
              <div className="mb-2 md:mb-4"> {/* 바깥쪽 div: 하단 여백 */}
                {/* 안쪽 div: 배경, 라운딩, 그림자, 패딩 적용 */}
                <div className="bg-white rounded-md shadow p-4 md:p-6 overflow-x-auto border border-gray-200">
                  {/* 제목 및 설명 영역과 종목 선택 영역을 한 줄에 배치 */}
                  <div className="flex flex-col md:flex-row justify-between items-start md:items-center mb-3">
                    {/* 제목 및 설명 영역 */}
                    <div>
                      <h1 className="font-semibold text-gray-800" style={{ fontSize: 'clamp(0.75rem, 0.9vw, 0.9rem)' }}>AI 애널리스트</h1>
                      <p className="text-xs text-gray-500 mt-1">
                        AI 기반 주식 분석 및 투자 전략 정보를 제공합니다.
                      </p>
                    </div>
                    
                    {/* 종목 선택 영역 */}
                    <div className="mt-2 md:mt-0">
                      <div className="relative">
                        <div className="flex items-center justify-center w-full">
                          <div 
                            style={{
                              position: 'relative',
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'center',
                              width: '100%',
                              maxWidth: '250px',
                              backgroundColor: 'white',
                              borderRadius: '30px',
                              padding: '0',
                              boxShadow: '0 2px 6px rgba(0, 0, 0, 0.05)',
                              border: '2px solid #282A2E',
                              transition: 'border-color 0.3s ease'
                            }}
                            onMouseEnter={(e) => {
                              e.currentTarget.style.borderColor = '#10A37F';
                            }}
                            onMouseLeave={(e) => {
                              e.currentTarget.style.borderColor = '#282A2E';
                            }}
                          >
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
                            {isLoading ? (
                              <div style={{ padding: '8px', textAlign: 'center' }}>종목 로딩 중...</div>
                            ) : error ? (
                              <div style={{ padding: '8px', color: 'red' }}>{error}</div>
                            ) : filteredStocks.length === 0 ? (
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
                                  {filteredStocks.map((stock) => (
                                    <button 
                                      key={stock.value} 
                                      onClick={(e) => {
                                        e.preventDefault();
                                        e.stopPropagation();
                                        handleStockSelect(stock);
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
                                        e.currentTarget.style.color = '#ffffff';
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
                            
                            {/* 최근 조회 종목 목록 */}
                            {!isLoading && !error && recentStocks.length > 0 && (
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
                                      e.preventDefault();
                                      e.stopPropagation();
                                      setShowStockSuggestions(false); 
                                      setRecentStocks([]);
                                      localStorage.removeItem('recentStocks');
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
                                  marginTop: '4px',
                                  msOverflowStyle: 'none', 
                                  scrollbarWidth: 'none'
                                }}>
                                  {recentStocks.map((stock) => (
                                    <button 
                                      key={stock.value} 
                                      onClick={(e) => {
                                        e.preventDefault();
                                        e.stopPropagation();
                                        handleStockSelect(stock);
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
                                        e.currentTarget.style.color = '#ffffff';
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
                  </div>
                  
                  {/* 추가 설명 영역 */}
                  <div className="mt-4 mb-6">
                    <div className="bg-gray-50 rounded-md p-3">
                      <h3 className="text-sm font-medium text-gray-800 mb-2">AI 애널리스트 소개</h3>
                      <p className="text-xs text-gray-600 mb-3">
                        AI 애널리스트는 방대한 금융 데이터를 분석하여 투자자에게 객관적이고 정확한 투자 인사이트를 제공합니다. 
                        종목별 심층 분석, 투자 전략, 시장 동향 등 다양한 정보를 확인할 수 있습니다.
                      </p>
                      
                      <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mt-4">
                        <div className="bg-white rounded-md p-3 border border-gray-200">
                          <div className="flex items-center mb-2">
                            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" className="mr-2">
                              <path d="M12 6V12L16 14M22 12C22 17.5228 17.5228 22 12 22C6.47715 22 2 17.5228 2 12C2 6.47715 6.47715 2 12 2C17.5228 2 22 6.47715 22 12Z" stroke="#10A37F" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                            </svg>
                            <h4 className="text-xs font-medium text-gray-800">실시간 분석</h4>
                          </div>
                          <p className="text-xs text-gray-600">
                            최신 시장 데이터를 기반으로 실시간 분석 정보를 제공합니다.
                          </p>
                        </div>
                        
                        <div className="bg-white rounded-md p-3 border border-gray-200">
                          <div className="flex items-center mb-2">
                            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" className="mr-2">
                              <path d="M9 12L11 14L15 10M21 12C21 16.9706 16.9706 21 12 21C7.02944 21 3 16.9706 3 12C3 7.02944 7.02944 3 12 3C16.9706 3 21 7.02944 21 12Z" stroke="#10A37F" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                            </svg>
                            <h4 className="text-xs font-medium text-gray-800">객관적 분석</h4>
                          </div>
                          <p className="text-xs text-gray-600">
                            감정을 배제한 데이터 기반의 객관적인 분석 결과를 제공합니다.
                          </p>
                        </div>
                        
                        <div className="bg-white rounded-md p-3 border border-gray-200">
                          <div className="flex items-center mb-2">
                            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" className="mr-2">
                              <path d="M13 16H12V12H11M12 8H12.01M21 12C21 16.9706 16.9706 21 12 21C7.02944 21 3 16.9706 3 12C3 7.02944 7.02944 3 12 3C16.9706 3 21 7.02944 21 12Z" stroke="#10A37F" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                            </svg>
                            <h4 className="text-xs font-medium text-gray-800">투자 교육</h4>
                          </div>
                          <p className="text-xs text-gray-600">
                            투자 의사결정에 필요한 핵심 정보와 교육 콘텐츠를 제공합니다.
                          </p>
                        </div>
                      </div>
                    </div>
                  </div>
                  
                  {/* 사용 방법 안내 */}
                  <div className="mt-4 mb-2">
                    <div className="flex items-center mb-2">
                      <h3 className="text-sm font-medium text-gray-800">사용 방법</h3>
                      <div className="ml-2 px-2 py-1 bg-gray-100 rounded-md">
                        <span className="text-xs text-gray-600">간편 가이드</span>
                      </div>
                    </div>
                    
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                      <div className="flex items-start p-3 bg-gray-50 rounded-md">
                        <div className="flex items-center justify-center w-6 h-6 bg-gray-200 rounded-full mr-3 text-xs font-medium">1</div>
                        <div>
                          <p className="text-xs text-gray-700">
                            <span className="font-medium">종목 선택</span>: 상단의 종목 선택 버튼을 클릭하여 분석하고자 하는 종목을 선택하세요.
                          </p>
                        </div>
                      </div>
                      
                      <div className="flex items-start p-3 bg-gray-50 rounded-md">
                        <div className="flex items-center justify-center w-6 h-6 bg-gray-200 rounded-full mr-3 text-xs font-medium">2</div>
                        <div>
                          <p className="text-xs text-gray-700">
                            <span className="font-medium">분석 확인</span>: 선택한 종목에 대한 AI 분석 결과와 투자 인사이트를 확인하세요.
                          </p>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            {/* 두 번째 영역 (40%) */}
            <div className="w-full md:w-[40%]">
              <div className="mb-2 md:mb-4">
                <div className="bg-white rounded-md shadow p-4 md:p-6">
                  {/* 제목 영역 - ETF 테이블처럼 별도 섹션으로 분리 */}
                  <div className="bg-gray-50 rounded-md p-2 mb-3">
                    <div className="flex justify-between items-center">
                      <div>
                        <h1 className="font-semibold text-gray-800" style={{ fontSize: 'clamp(0.75rem, 0.9vw, 0.9rem)' }}>투자 인사이트</h1>
                      </div>
                    </div>
                  </div>
                  
                  {/* 내용 영역 - 별도 섹션으로 감싸기 */}
                  <div className="bg-white rounded-md border border-gray-200 p-3 md:p-4">
                    <div className="mb-3">
                      <p className="text-xs text-gray-500">
                        AI가 분석한 최신 투자 인사이트와 추천 정보를 확인하세요.
                      </p>
                    </div>
                    
                    {/* 콘텐츠 영역 */}
                    <div className="mt-4 min-h-[400px]">
                      {selectedStock ? (
                        <div className="space-y-4">
                          <p className="text-sm text-gray-700">
                            <strong>{selectedStock.stockName}</strong>({selectedStock.stockCode}) 종목에 대한 투자 인사이트입니다.
                          </p>
                          
                          {/* 추가 콘텐츠 영역 */}
                          <div className="mt-6 space-y-4">
                            <div className="p-3 bg-gray-50 rounded-md">
                              <h3 className="text-sm font-medium text-gray-800 mb-2">기업 개요</h3>
                              <p className="text-xs text-gray-600">
                                선택한 종목에 대한 기업 개요 정보가 표시됩니다. AI가 분석한 기업의 주요 사업 영역, 경쟁력, 시장 포지션 등의 정보를 확인할 수 있습니다.
                              </p>
                            </div>
                            
                            <div className="p-3 bg-gray-50 rounded-md">
                              <h3 className="text-sm font-medium text-gray-800 mb-2">투자 포인트</h3>
                              <p className="text-xs text-gray-600">
                                AI가 분석한 주요 투자 포인트와 투자 전략을 확인할 수 있습니다. 기업의 성장성, 수익성, 안정성 등 다양한 관점에서의 분석 결과를 제공합니다.
                              </p>
                            </div>
                            
                            <div className="p-3 bg-gray-50 rounded-md">
                              <h3 className="text-sm font-medium text-gray-800 mb-2">재무 분석</h3>
                              <p className="text-xs text-gray-600">
                                기업의 주요 재무 지표와 동종 업계 평균과의 비교 분석 정보를 제공합니다. 매출액, 영업이익, ROE, PER, PBR 등 주요 지표의 추이와 전망을 확인할 수 있습니다.
                              </p>
                              {/* 재무 지표 차트 추가 */}
                              <div className="mt-4 flex justify-center items-center">
                                <StockAnalyticsChart stockCode={selectedStock?.stockCode} stockName={selectedStock?.stockName} />
                              </div>
                            </div>
                            
                            <div className="p-3 bg-gray-50 rounded-md">
                              <h3 className="text-sm font-medium text-gray-800 mb-2">위험 요소</h3>
                              <p className="text-xs text-gray-600">
                                투자 시 고려해야 할 주요 위험 요소와 주의사항을 제공합니다. 산업 환경, 경쟁 상황, 규제 변화 등 투자 결정에 영향을 미칠 수 있는 요소들을 분석합니다.
                              </p>
                            </div>
                          </div>
                        </div>
                      ) : (
                        <div className="flex flex-col items-center justify-center h-[400px]">
                          <p className="text-sm text-gray-500 mb-4">종목을 선택하면 투자 인사이트가 이곳에 표시됩니다.</p>
                          <div className="p-4 bg-gray-50 rounded-md w-full max-w-md">
                            <p className="text-xs text-gray-500 text-center">
                              AI 애널리스트는 선택한 종목에 대한 심층 분석과 투자 전략을 제공합니다. 
                              상단의 종목 선택 버튼을 클릭하여 분석하고자 하는 종목을 선택해 주세요.
                            </p>
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default AnalystPage;
