'use client'

import React, { useState, useEffect, useCallback, useRef } from 'react';
import Papa from 'papaparse';
import ChartComponent from './ChartComponent';

/**
 * 종목 타입 정의
 */
interface StockOption {
  value: string;
  label: string;
  stockName: string;
  stockCode: string;
}

/**
 * 캔들 데이터 인터페이스 정의
 */
interface CandleData {
  time: string; // 'YYYY-MM-DD' 형식
  open: number;
  high: number;
  low: number;
  close: number;
  volume?: number;
}

/**
 * 종목 정보 인터페이스 정의
 */
interface StockInfo {
  stockCode: string;
  stockName: string;
  industry?: string; // 업종 추가
  rs?: string; // RS 값 추가
}

/**
 * Indie1 컴포넌트 - 상단 영역의 첫 번째 컴포넌트(50%)
 * 상단 영역을 가로로 5:2.5:2.5 비율로 나눈 첫 번째 영역
 */
export default function Indie1() {
  // 종목 관련 상태
  const [stockOptions, setStockOptions] = useState<StockOption[]>([]);
  const [selectedStock, setSelectedStock] = useState<StockInfo | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [showStockSuggestions, setShowStockSuggestions] = useState<boolean>(false);
  const [searchTerm, setSearchTerm] = useState<string>('');
  const [filteredStocks, setFilteredStocks] = useState<StockOption[]>([]);
  const [recentStocks, setRecentStocks] = useState<StockOption[]>([]);
  const [candleData, setCandleData] = useState<CandleData[]>([]);
  const [isLoadingChart, setIsLoadingChart] = useState<boolean>(false);
  const [chartError, setChartError] = useState<string | null>(null);
  
  // 종목 상세 정보 상태 추가
  const [stockDetails, setStockDetails] = useState<{
    industry?: string;
    rs?: string;
  }>({});

  // 참조
  const inputRef = useRef<HTMLInputElement>(null);
  const searchInputRef = useRef<HTMLInputElement>(null);
  const stockSuggestionsRef = useRef<HTMLDivElement>(null);
  
  const MAX_RECENT_STOCKS = 5; // 최근 조회 종목 최대 개수

  // 클라이언트 사이드 렌더링 확인
  useEffect(() => {
    setIsLoading(true);

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

    // 컴포넌트 언마운트 시 이벤트 리스너 제거
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, []);

  // CSV 파일에서 종목 리스트 가져오기
  useEffect(() => {
    const fetchStockList = async () => {
      try {
        setIsLoading(true);
        setError(null); // 요청 시작 시 오류 상태 초기화

        // 서버 캐시 CSV 파일 경로
        const csvFilePath = '/requestfile/stock-data/stock_1idvb5kio0d6dchvoywe7ovwr-ez1cbpb.csv';

        // 서버 캐시 파일 가져오기 (항상 최신 데이터 사용)
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

        // 종목 데이터 추출 (종목명(종목코드) 형식으로 변경)
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
            stockName: row.종목명, // 종목명 저장
            stockCode: row.종목코드 // 종목코드 저장
          }));

        if (stockData.length > 0) {
          setStockOptions(stockData);
        } else {
          const errorMsg = '유효한 종목 데이터를 받지 못했습니다.';
          setError(errorMsg);
        }

        setIsLoading(false);
      } catch (error) {
        const errorMsg = error instanceof Error ? error.message : '종목 리스트를 가져오는 중 오류가 발생했습니다.';
        console.error('종목 리스트 가져오기 오류:', error);
        setError(errorMsg);
        setIsLoading(false);
      }
    };

    fetchStockList();
  }, []);

  // 종목 선택 시 해당 종목의 차트 데이터 가져오기
  useEffect(() => {
    if (!selectedStock) {
      setCandleData([]);
      return;
    }

    const fetchStockChartData = async () => {
      try {
        setIsLoadingChart(true);
        setChartError(null);
        
        // 종목코드 앞에 0 추가하여 6자리 맞추기
        const stockCode = selectedStock.stockCode.padStart(6, '0');
        const csvFilePath = `/requestfile/indiv/stocks/${stockCode}.csv`;
        
        // CSV 파일 가져오기
        const response = await fetch(csvFilePath);
        
        if (!response.ok) {
          throw new Error(`차트 데이터 로드 오류: ${response.status}`);
        }
        
        // CSV 파일 내용 가져오기
        const csvContent = await response.text();
        
        // CSV 파싱
        const parsedData = Papa.parse(csvContent, {
          header: true,
          skipEmptyLines: true,
          dynamicTyping: true
        });
        
        // 데이터 변환
        const chartData = parsedData.data
          .filter((row: any) => row && row.날짜 && row.시가 && row.고가 && row.저가 && row.종가)
          .map((row: any) => ({
            time: row.날짜,
            open: parseFloat(row.시가),
            high: parseFloat(row.고가),
            low: parseFloat(row.저가),
            close: parseFloat(row.종가),
            volume: parseFloat(row.거래량 || 0)
          }));
        
        // 최신 데이터가 위로 오도록 정렬
        chartData.sort((a: CandleData, b: CandleData) => {
          return new Date(a.time).getTime() - new Date(b.time).getTime();
        });
        
        setCandleData(chartData);
      } catch (error) {
        console.error('차트 데이터 가져오기 오류:', error);
        setChartError(error instanceof Error ? error.message : '알 수 없는 오류');
        setCandleData([]);
      } finally {
        setIsLoadingChart(false);
      }
    };
    
    fetchStockChartData();
  }, [selectedStock]);

  // 종목 상세 정보 가져오기
  useEffect(() => {
    if (selectedStock) {
      // 종목 상세 정보 가져오기
      fetchStockDetails(selectedStock.stockCode);
    }
  }, [selectedStock]);

  // 종목 상세 정보 가져오는 함수
  const fetchStockDetails = async (stockCode: string) => {
    try {
      const response = await fetch('/requestfile/stock-data/stock_1uyjvdmzfxarsxs0jy16fegfrqy9fs8yd.csv');
      const csvText = await response.text();
      
      Papa.parse(csvText, {
        header: true,
        complete: (results) => {
          const stockData = results.data.find((item: any) => item.종목코드 === stockCode);
          
          if (stockData) {
            setStockDetails({
              industry: (stockData as any).업종 || '정보 없음',
              rs: (stockData as any).RS || '정보 없음'
            });
          } else {
            setStockDetails({
              industry: '정보 없음',
              rs: '정보 없음'
            });
          }
        },
        error: (error: Error) => {
          console.error('종목 상세 정보 파싱 오류:', error);
          setStockDetails({
            industry: '정보 없음',
            rs: '정보 없음'
          });
        }
      });
    } catch (error) {
      console.error('종목 상세 정보 로드 오류:', error);
      setStockDetails({
        industry: '정보 없음',
        rs: '정보 없음'
      });
    }
  };

  // 입력 필드 포커스 시 종목 추천 목록 표시
  const handleInputFocus = () => {
    // 종목이 선택되어 있지 않은 경우에만 종목 추천 목록 표시
    if (!selectedStock) {
      setShowStockSuggestions(true);
      // 초기 검색 결과는 전체 목록의 첫 5개
      setFilteredStocks(stockOptions.slice(0, 5));

      // 검색 입력 필드에 하이라이트 효과 추가
      if (searchInputRef.current) {
        // 0.1초 후에 검색 입력 필드에 포커스 및 하이라이트 효과 적용
        setTimeout(() => {
          if (searchInputRef.current) {
            searchInputRef.current.focus();
            searchInputRef.current.style.backgroundColor = '#ffffcc'; // 노란색 배경으로 하이라이트
            searchInputRef.current.style.border = '2px solid #ffd700'; // 테두리 강조
          }
        }, 100);
      }
    }
  };

  // 입력 필드 클릭 처리 - 종목이 선택되지 않은 경우 종목 선택창 표시
  const handleInputClick = () => {
    if (!selectedStock) {
      setShowStockSuggestions(true);
      // 초기 검색 결과는 전체 목록의 첫 5개
      setFilteredStocks(stockOptions.slice(0, 5));

      // 검색 입력 필드에 하이라이트 효과 추가
      if (searchInputRef.current) {
        // 0.1초 후에 검색 입력 필드에 포커스 및 하이라이트 효과 적용
        setTimeout(() => {
          if (searchInputRef.current) {
            searchInputRef.current.focus();
            searchInputRef.current.style.backgroundColor = '#ffffcc'; // 노란색 배경으로 하이라이트
            searchInputRef.current.style.border = '2px solid #ffd700'; // 테두리 강조
          }
        }, 100);
      }
    }
  };

  // 종목 선택 처리
  const handleStockSelect = (stock: StockOption) => {
    setSelectedStock(stock);
    setShowStockSuggestions(false);
    setSearchTerm(''); // 검색어 초기화

    // 최근 조회 종목에 추가
    updateRecentStocks(stock);
  };

  // 최근 조회 종목 업데이트
  const updateRecentStocks = (stock: StockOption) => {
    // 이미 있는 종목이면 제거 (중복 방지)
    const filteredRecent = recentStocks.filter((item: StockOption) => item.value !== stock.value);

    // 새 종목을 맨 앞에 추가
    const newRecentStocks = [stock, ...filteredRecent].slice(0, MAX_RECENT_STOCKS);
    setRecentStocks(newRecentStocks);

    // 로컬 스토리지에 저장
    try {
      localStorage.setItem('recentStocks', JSON.stringify(newRecentStocks));
    } catch (error) {
      console.warn('최근 조회 종목 저장 실패:', error);
    }
  };

  // 종목 검색 입력 처리
  const handleSearchInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const searchValue = e.target.value;
    setSearchTerm(searchValue);

    // 검색어에 따라 종목 필터링
    if (searchValue.trim()) {
      const filtered = stockOptions.filter(stock => {
        const stockName = stock.stockName;
        return (
          stockName.toLowerCase().includes(searchValue.toLowerCase()) ||
          stock.value.toLowerCase().includes(searchValue.toLowerCase()) ||
          stock.label.toLowerCase().includes(searchValue.toLowerCase())
        );
      });
      setFilteredStocks(filtered.slice(0, 20)); // 최대 20개까지 표시
    } else {
      setFilteredStocks(stockOptions.slice(0, 5)); // 검색어 없을 때는 첫 5개만
    }
  };

  // 검색 입력 필드에서 엔터키 처리
  const handleSearchInputKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      // 검색 결과가 있으면 첫 번째 종목 선택
      if (filteredStocks.length > 0) {
        handleStockSelect(filteredStocks[0]);
      }
    }
  };

  // 검색 입력 필드 클릭 시 전체 선택
  const handleSearchInputClick = (e: React.MouseEvent<HTMLInputElement>) => {
    e.stopPropagation(); // 이벤트 버블링 방지
    // 클릭 시 하이라이트 효과 유지
    if (searchInputRef.current) {
      searchInputRef.current.style.backgroundColor = '#ffffcc';
      searchInputRef.current.style.border = '2px solid #ffd700';
    }
  };

  // 검색 입력 필드 포커스 아웃 처리 함수 추가
  const handleSearchInputBlur = () => {
    // 포커스 아웃 시 하이라이트 효과 제거
    if (searchInputRef.current) {
      searchInputRef.current.style.backgroundColor = 'white';
      searchInputRef.current.style.border = '1px solid #ddd';
    }
  };

  // 선택된 종목 초기화
  const handleClearStock = () => {
    setSelectedStock(null);
  };

  return (
    <div className="w-full h-full p-4 bg-[#f5f5f5] rounded-md shadow-md">
      
      {/* 종목 선택 영역 - 크기 추가 축소 */}
      <div className="mb-1 relative" style={{ width: '27%' }}>
        <div className="flex items-center">
          <div className="relative w-full">
            {!selectedStock ? (
              <input
                ref={inputRef}
                placeholder="종목을 선택하세요"
                type="text"
                value=""
                onFocus={handleInputFocus}
                onClick={handleInputClick}
                readOnly
                className="w-full h-8 px-3 py-1 border border-gray-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
                style={{
                  backgroundColor: '#f5f5f5',
                  cursor: 'pointer'
                }}
              />
            ) : (
              <button
                onClick={handleClearStock}
                className="px-3 py-1 bg-blue-100 hover:bg-blue-200 rounded-xl text-sm transition-colors flex items-center"
                title="클릭하여 다른 종목 선택"
              >
                <span className="font-semibold text-blue-500">{selectedStock.stockName}</span>
                <span className="ml-2 text-xs text-gray-600">({selectedStock.stockCode})</span>
              </button>
            )}
          </div>
        </div>
        
        {/* 종목 검색 및 선택 드롭다운 */}
        {showStockSuggestions && (
          <div 
            ref={stockSuggestionsRef}
            className="absolute top-full left-0 w-[300%] bg-[#f5f5f5] border border-gray-300 rounded-xl shadow-lg z-50 mt-1"
          >
            <div className="p-2 border-b border-gray-200 relative">
              <input
                ref={searchInputRef}
                type="text"
                value={searchTerm}
                onChange={handleSearchInputChange}
                onKeyDown={handleSearchInputKeyDown}
                onClick={handleSearchInputClick}
                onBlur={handleSearchInputBlur}
                placeholder="종목명 또는 코드 검색"
                className="w-full px-3 py-2 border border-gray-300 rounded-xl focus:outline-none"
              />
              {searchTerm && (
                <button
                  onClick={() => {
                    setSearchTerm('');
                    setFilteredStocks(stockOptions.slice(0, 5));
                    if (searchInputRef.current) {
                      searchInputRef.current.focus();
                    }
                  }}
                  className="absolute right-4 top-1/2 transform -translate-y-1/2 bg-transparent border-none text-gray-500 cursor-pointer rounded-full p-1"
                >
                  ✕
                </button>
              )}
            </div>
            
            {/* 최근 조회 종목 */}
            {recentStocks.length > 0 && (
              <div className="p-2 border-b border-gray-200">
                <div className="text-xs font-semibold text-gray-500 mb-2">최근 조회 종목</div>
                <div className="flex flex-wrap gap-2">
                  {recentStocks.map((stock: StockOption) => (
                    <button
                      key={stock.value}
                      onClick={() => handleStockSelect(stock)}
                      className="px-3 py-1 bg-gray-100 hover:bg-gray-200 rounded-xl text-sm transition-colors flex items-center"
                    >
                      <span className="font-semibold">{stock.stockName}</span>
                    </button>
                  ))}
                </div>
              </div>
            )}
            
            {/* 검색 결과 */}
            <div className="p-2">
              {isLoading ? (
                <div className="p-3 text-center text-gray-500">로딩 중...</div>
              ) : filteredStocks.length > 0 ? (
                <div>
                  <div className="text-xs font-semibold text-gray-500 mb-2">
                    {searchTerm ? '검색 결과' : '추천 종목'}
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {filteredStocks.map((stock: StockOption) => (
                      <button
                        key={stock.value}
                        onClick={() => handleStockSelect(stock)}
                        className="px-3 py-1 bg-gray-100 hover:bg-gray-200 rounded-xl text-sm transition-colors flex items-center"
                      >
                        <span className="font-semibold">{stock.stockName}</span>
                      </button>
                    ))}
                  </div>
                </div>
              ) : (
                <div className="p-3 text-center text-gray-500">
                  {searchTerm ? '검색 결과가 없습니다.' : '종목을 검색하세요.'}
                </div>
              )}
            </div>
          </div>
        )}
      </div>
      
      {/* 차트 영역 - 섹션 안으로 조정 */}
      {selectedStock ? (
        <div className="h-[calc(100%-2.5rem)] mt-1 px-0 overflow-hidden">
          {isLoadingChart ? (
            <div className="flex justify-center items-center h-full">
              <p>차트 데이터를 불러오는 중...</p>
            </div>
          ) : chartError ? (
            <div className="flex justify-center items-center h-full">
              <p>차트 데이터 로드 오류: {chartError}</p>
            </div>
          ) : candleData.length > 0 ? (
            <div className="w-full h-full">
              {/* 헤더 추가 */}
              <div className="px-3 py-1 border flex justify-between items-center bg-blue-100 border-blue-200" style={{ borderRadius: '0.375rem 0.375rem 0 0' }}>
                <div className="flex items-center gap-2">
                  <span className="font-medium text-sm">{stockDetails.industry || '업종 정보 없음'}</span>
                  <span className="text-xs px-1.5 py-0.5 rounded text-red-600">{selectedStock.stockCode}</span>
                </div>
                <div className="flex items-center gap-1">
                  <span className="font-medium text-xs text-blue-600" style={{ fontSize: 'clamp(0.65rem, 0.75vw, 0.75rem)' }}>RS {stockDetails.rs || 'N/A'}</span>
                </div>
              </div>
              {/* 차트 컨테이너 */}
              <div className="h-full mb-4" style={{ overflow: 'hidden' }}>
                <ChartComponent 
                  data={candleData}
                  title={`${selectedStock.stockName} 차트`}
                  subtitle={`종목코드: ${selectedStock.stockCode}`}
                  height={320} 
                  width="100%"
                  showVolume={true}
                  marketType="KOSPI" 
                  stockName={selectedStock.stockName}
                  showMA20={true}
                  parentComponent="Indie1"
                />
              </div>
            </div>
          ) : (
            <div className="flex justify-center items-center h-full">
              <p>차트 데이터가 없습니다.</p>
            </div>
          )}
        </div>
      ) : (
        <div className="h-[calc(100%-2.5rem)] flex justify-center items-center">
          <p>종목을 선택하면 분석 정보가 표시됩니다.</p>
        </div>
      )}
    </div>
  );
}
