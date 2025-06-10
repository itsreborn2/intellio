'use client';

import React, { useState, useEffect, useCallback } from 'react';
import Papa from 'papaparse';
import LoadingSpinner from '@/app/components/LoadingSpinner'; // LoadingSpinner 경로 확인 필요

interface StockData {
  stock_code: string;
  stock_name: string;
  // 필요한 경우 다른 필드 추가
}

interface CagrAnalysisResult {
  // n8n에서 반환될 CAGR 분석 결과의 타입 정의
  // 예시:
  period?: string;
  cagr?: number;
  error?: string;
}

export default function ValueAnalyticsPage() {
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedStock, setSelectedStock] = useState<StockData | null>(null);
  const [stockList, setStockList] = useState<StockData[]>([]);
  const [filteredStockList, setFilteredStockList] = useState<StockData[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isFetchingStocks, setIsFetchingStocks] = useState(true);
  const [analysisResult, setAnalysisResult] = useState<CagrAnalysisResult | null>(null);
  const [showSuggestions, setShowSuggestions] = useState(false);

  // CSV 파일에서 종목 데이터 로드
  useEffect(() => {
    async function fetchStockData() {
      setIsFetchingStocks(true);
      try {
        const response = await fetch('/requestfile/stock-data/stock_1uyjvdmzfxarsxs0jy16fegfrqy9fs8yd.csv');
        const reader = response.body?.getReader();
        const result = await reader?.read();
        const decoder = new TextDecoder('utf-8');
        const csv = decoder.decode(result?.value);
        
        Papa.parse(csv, {
          header: true,
          skipEmptyLines: true,
          complete: (results) => {
            const data = results.data as any[];
            const stocks = data.map(row => ({
              stock_code: row['종목코드'] || '', // CSV 헤더명 확인 필요
              stock_name: row['종목명'] || '',   // CSV 헤더명 확인 필요
            })).filter(stock => stock.stock_code && stock.stock_name);
            setStockList(stocks);
            setFilteredStockList(stocks); // 초기에는 전체 목록 표시
          }
        });
      } catch (error) {
        console.error('Error fetching stock data:', error);
        // 사용자에게 오류 메시지 표시 로직 추가 가능
      } finally {
        setIsFetchingStocks(false);
      }
    }
    fetchStockData();
  }, []);

  // 검색어에 따라 종목 필터링
  useEffect(() => {
    if (searchTerm === '') {
      setFilteredStockList(stockList.slice(0, 10)); // 검색어가 없으면 처음 10개만 표시
    } else {
      const lowercasedFilter = searchTerm.toLowerCase();
      const filtered = stockList.filter(stock =>
        stock.stock_name.toLowerCase().includes(lowercasedFilter) ||
        stock.stock_code.includes(searchTerm)
      );
      setFilteredStockList(filtered.slice(0, 10)); // 검색 결과도 10개로 제한
    }
  }, [searchTerm, stockList]);

  const handleSearchChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setSearchTerm(e.target.value);
    setSelectedStock(null); // 검색어 변경 시 선택된 종목 초기화
    setAnalysisResult(null); // 검색어 변경 시 분석 결과 초기화
    setShowSuggestions(true);
  };

  const handleStockSelect = (stock: StockData) => {
    setSelectedStock(stock);
    setSearchTerm(stock.stock_name); // 입력창에 선택된 종목명 표시
    setShowSuggestions(false);
    setAnalysisResult(null); // 종목 선택 시 이전 분석 결과 초기화
  };

  const handleAnalyzeCAGR = async () => {
    if (!selectedStock) {
      alert('먼저 종목을 선택해주세요.');
      return;
    }
    setIsLoading(true);
    setAnalysisResult(null);

    // n8n 워크플로우 URL (실제 URL로 교체 필요)
    const n8nWebhookUrl = 'YOUR_N8N_WEBHOOK_URL_HERE'; 

    try {
      // n8n으로 종목 정보 전송
      const response = await fetch(n8nWebhookUrl, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ 
          stockCode: selectedStock.stock_code,
          stockName: selectedStock.stock_name 
        }),
      });

      if (!response.ok) {
        throw new Error(`n8n 요청 실패: ${response.statusText}`);
      }

      const result = await response.json();
      setAnalysisResult(result as CagrAnalysisResult);

    } catch (error) {
      console.error('CAGR 분석 오류:', error);
      setAnalysisResult({ error: error instanceof Error ? error.message : '알 수 없는 오류 발생' });
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-900 text-white p-4 flex flex-col items-center pt-10">
      <h1 className="text-3xl font-bold mb-8 text-center">CAGR 분석기 (Value Analytics)</h1>
      
      <div className="w-full max-w-lg mb-6 relative">
        <div className="flex items-center bg-gray-800 p-3 rounded-lg shadow-md">
          {selectedStock && (
            <button 
              className="bg-sky-600 text-white px-3 py-1 rounded-md mr-2 text-sm whitespace-nowrap hover:bg-sky-700 transition-colors"
              onClick={() => {
                setSelectedStock(null);
                setSearchTerm('');
                setAnalysisResult(null);
                setShowSuggestions(true);
              }}
            >
              {selectedStock.stock_name} (X)
            </button>
          )}
          <input
            type="text"
            placeholder={selectedStock ? '종목이 선택되었습니다.' : '종목명 또는 코드를 검색하세요...'}
            value={searchTerm}
            onChange={handleSearchChange}
            onFocus={() => setShowSuggestions(true)}
            // onBlur={() => setTimeout(() => setShowSuggestions(false), 100)} // 클릭 이벤트 처리를 위해 지연
            className={`w-full p-2 rounded-md bg-gray-700 text-white focus:ring-2 focus:ring-sky-500 outline-none ${selectedStock ? 'pl-2' : ''}`}
            disabled={!!selectedStock}
          />
        </div>

        {showSuggestions && !selectedStock && filteredStockList.length > 0 && (
          <ul className="absolute z-10 w-full bg-gray-800 border border-gray-700 rounded-md mt-1 max-h-60 overflow-y-auto shadow-lg">
            {isFetchingStocks ? (
              <li className="p-3 text-center text-gray-400">종목 목록을 불러오는 중...</li>
            ) : (
              filteredStockList.map(stock => (
                <li 
                  key={stock.stock_code}
                  className="p-3 hover:bg-gray-700 cursor-pointer transition-colors border-b border-gray-700 last:border-b-0"
                  onClick={() => handleStockSelect(stock)}
                >
                  {stock.stock_name} ({stock.stock_code})
                </li>
              ))
            )}
            {filteredStockList.length === 0 && !isFetchingStocks && (
                 <li className="p-3 text-center text-gray-400">검색 결과가 없습니다.</li>
            )}
          </ul>
        )}
      </div>

      <button
        onClick={handleAnalyzeCAGR}
        disabled={!selectedStock || isLoading}
        className="bg-sky-600 hover:bg-sky-700 text-white font-semibold py-3 px-6 rounded-lg shadow-md transition-colors duration-150 ease-in-out disabled:opacity-50 disabled:cursor-not-allowed w-full max-w-lg"
      >
        {isLoading ? '분석 중...' : 'CAGR 분석기 실행'}
      </button>

      {isLoading && (
        <div className="mt-8 w-full max-w-lg text-center">
          <LoadingSpinner message="CAGR 데이터를 n8n에서 가져오는 중입니다..." />
        </div>
      )}

      {analysisResult && !isLoading && (
        <div className="mt-8 p-6 bg-gray-800 rounded-lg shadow-md w-full max-w-lg">
          <h2 className="text-xl font-semibold mb-4 text-sky-400">분석 결과</h2>
          {analysisResult.error ? (
            <p className="text-red-400">오류: {analysisResult.error}</p>
          ) : (
            <div>
              <p><strong>종목:</strong> {selectedStock?.stock_name} ({selectedStock?.stock_code})</p>
              {/* n8n 결과에 따라 아래 내용을 수정하세요 */}
              <p><strong>분석 기간:</strong> {analysisResult.period || 'N/A'}</p>
              <p><strong>연평균 성장률 (CAGR):</strong> {analysisResult.cagr !== undefined ? `${analysisResult.cagr.toFixed(2)}%` : 'N/A'}</p>
              {/* 추가적인 결과 필드 표시 */}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
