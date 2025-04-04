'use client';

import React, { useState, useEffect } from 'react';
import Papa from 'papaparse'; 
import dynamic from 'next/dynamic'; 

const AnalystStickChart = dynamic(
  () => import('../components/analyst-stickchart'),
  { ssr: false, loading: () => <p className="text-sm text-gray-500">차트를 불러오는 중...</p> }
);

const AnalystSearchbar = dynamic(
  () => import('../components/analyst-searchbar'),
  { ssr: false }
);

interface StockOption {
  value: string;
  label: string;
  display?: string;
  stockName: string;
  stockCode: string;
}

const AnalystPage = () => {
  const [loading, setLoading] = useState(true);
  const [stockOptions, setStockOptions] = useState<StockOption[]>([]);
  const [selectedStock, setSelectedStock] = useState<StockOption | null>(null);
  const [isMounted, setIsMounted] = useState<boolean>(false);
  const [isMobile, setIsMobile] = useState<boolean>(false);

  useEffect(() => {
    setIsMounted(true);
  }, []);

  useEffect(() => {
    const checkIfMobile = () => {
      setIsMobile(window.innerWidth <= 768);
    };
    checkIfMobile();
    window.addEventListener('resize', checkIfMobile);
    return () => {
      window.removeEventListener('resize', checkIfMobile);
    };
  }, []);

  useEffect(() => {
    if (!isMounted) return;
    setLoading(true); 

    const fetchStockList = async () => {
      try {
        const csvFilePath = '/requestfile/stock-data/stock_1idvb5kio0d6dchvoywe7ovwr-ez1cbpb.csv';
        const response = await fetch(csvFilePath, { cache: 'no-store' });
        if (!response.ok) {
          throw new Error(`서버 캐시 파일 로드 오류: ${response.status}`);
        }
        const csvContent = await response.text();
        const parsedData = Papa.parse(csvContent, {
          header: true,
          skipEmptyLines: true
        });
        const uniqueStocks = new Set();
        const stockData = parsedData.data
          .filter((row: any) => row.종목명 && row.종목코드)
          .filter((row: any) => {
            if (uniqueStocks.has(row.종목코드)) {
              return false;
            }
            uniqueStocks.add(row.종목코드);
            return true;
          })
          .map((row: any) => ({
            value: row.종목코드,
            label: `${row.종목명}(${row.종목코드})`,
            display: row.종목명,
            stockName: row.종목명,
            stockCode: row.종목코드
          }));

        if (stockData.length > 0) {
          console.log(`종목 데이터 ${stockData.length}개 로드 완료`);
          setStockOptions(stockData);
        } else {
          console.error('유효한 종목 데이터를 받지 못했습니다.');
        }
      } catch (error) {
        console.error('종목 리스트 가져오기 오류:', error);
      } finally {
        setLoading(false); 
      }
    };

    fetchStockList();
  }, [isMounted]);

  const handleStockSelect = (stock: StockOption) => {
    setSelectedStock(stock);
  };

  if (loading && !isMounted) {
    return <div className="p-4">페이지 준비 중...</div>;
  }

  return (
    <div className="max-w-6xl mx-auto">
      <div className="bg-white rounded-md shadow p-2 md:p-4 flex-1 flex flex-col overflow-hidden">
        <div className="bg-white rounded-md shadow">
          <div className="p-2 md:p-4">
            {/* === 6:4 비율 분할 컨테이너 === */}
            <div className="flex flex-col md:flex-row gap-4">

              {/* --- 왼쪽 영역 (60%) --- */}
              <div className="w-full md:w-[60%] flex flex-col gap-4">
                {/* 제목 및 검색 바 영역 */}
                <div className="bg-white rounded-md shadow border border-gray-200 p-3"> {/* Card 스타일 */}
                  <div className="flex flex-col md:flex-row justify-between items-start md:items-center mb-1"> {/* mb 감소 */}
                    {/* 제목 및 설명 */}
                    <div>
                      <h2 className="font-semibold whitespace-nowrap" style={{ fontSize: 'clamp(0.75rem, 0.9vw, 0.9rem)' }}>AI 애널리스트</h2>
                      <p className="text-xs text-gray-500 mt-1 hidden sm:inline">AI 기반 주식 분석 및 투자 전략 정보를 제공합니다.</p>
                    </div>
                    {/* 종목 검색 바 (AnalystSearchbar) */}
                    <div className="mt-2 md:mt-0">
                      <AnalystSearchbar
                        stockOptions={stockOptions}
                        selectedStock={selectedStock}
                        onStockSelect={handleStockSelect}
                        isMobile={isMobile}
                      />
                    </div>
                  </div>
                </div>

                {/* AI 응답 박스 */} 
                <div className="bg-white rounded-md shadow border border-gray-200 p-4 min-h-[400px]"> {/* Card 스타일 및 최소 높이 증가 */}
                  <h3 className="text-sm font-semibold text-gray-700 mb-2">AI 분석 결과</h3>
                  {/* 실제 AI 응답은 여기에 표시됩니다. */}
                  <div className="text-sm text-gray-500">
                    {selectedStock
                      ? `[${selectedStock.label}]에 대한 AI 분석 결과가 여기에 표시됩니다.`
                      : '종목을 선택하면 AI 분석 결과를 볼 수 있습니다.'}
                  </div>
                </div>
              </div>
              {/* --- /왼쪽 영역 (60%) --- */}

              {/* --- 오른쪽 영역 (40%) --- */}
              <div className="w-full md:w-[40%]">
                <div className="bg-white rounded-md shadow border border-gray-200 p-3 h-full"> {/* Card 스타일 */}
                  <h3 className="text-sm font-semibold text-gray-700 mb-2">주요 지표 분석</h3>
                  {/* 로딩 중 또는 데이터 없는 경우 메시지 표시 */}
                  {loading && isMounted && (
                    <p className="text-sm text-gray-500 text-center py-4">종목 데이터를 불러오는 중입니다...</p>
                  )}
                  {!loading && !selectedStock && (
                    <div className="text-center py-10 border rounded-md bg-gray-50 h-full flex flex-col justify-center items-center min-h-[400px]"> {/* 최소 높이 추가 */}
                      <p className="text-gray-600 font-medium">종목을 선택해주세요.</p>
                      <p className="text-xs text-gray-400 mt-1">지표 분석 결과를 보려면 종목을 선택하세요.</p>
                    </div>
                  )}
                  {/* 종목 선택 시 차트 표시 */}
                  {!loading && selectedStock && (
                    <AnalystStickChart
                      stockCode={selectedStock.stockCode}
                      stockName={selectedStock.stockName}
                    />
                  )}
                </div>
              </div>
              {/* --- /오른쪽 영역 (40%) --- */}

            </div>
            {/* === /6:4 비율 분할 컨테이너 === */}
          </div>
        </div>
      </div>
    </div>
  );
};

export default AnalystPage;
