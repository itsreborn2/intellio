/**
 * stockDataUtils.ts
 * 종목 데이터 관련 유틸리티 함수
 */
import { StockOption } from '../types';
import Papa from 'papaparse';

// 최대 최근 조회 종목 수
export const MAX_RECENT_STOCKS = 5;

/**
 * CSV 파일에서 종목 목록 로드
 * @param csvFilePath CSV 파일 경로
 * @returns 종목 옵션 배열
 */
export async function loadStockOptionsFromCSV(csvFilePath: string): Promise<StockOption[]> {
  try {
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
        value: row.종목코드,
        label: `${row.종목명}(${row.종목코드})`, 
        display: row.종목명,
        stockName: row.종목명,
        stockCode: row.종목코드
      }));

    return stockData;
  } catch (error) {
    console.error('종목 데이터 로드 실패:', error);
    throw error;
  }
}

/**
 * 최근 조회 종목 로컬 스토리지에서 불러오기
 * @returns 최근 조회 종목 배열
 */
export function loadRecentStocksFromStorage(): StockOption[] {
  try {
    const savedStocks = localStorage.getItem('recentStocks');
    if (savedStocks) {
      const parsedStocks = JSON.parse(savedStocks);
      if (Array.isArray(parsedStocks) && parsedStocks.length > 0) {
        return parsedStocks.slice(0, MAX_RECENT_STOCKS);
      }
    }
    return [];
  } catch (error) {
    console.error('최근 조회 종목 로드 실패:', error);
    return [];
  }
}

/**
 * 최근 조회 종목 로컬 스토리지에 저장
 * @param stocks 저장할 종목 배열
 */
export function saveRecentStocksToStorage(stocks: StockOption[]): void {
  try {
    localStorage.setItem('recentStocks', JSON.stringify(stocks.slice(0, MAX_RECENT_STOCKS)));
  } catch (error) {
    console.error('최근 조회 종목 저장 실패:', error);
  }
}

/**
 * 종목 배열에 새 종목 추가 (중복 제거 및 최대 개수 제한)
 * @param stocks 기존 종목 배열
 * @param newStock 추가할 종목
 * @returns 새 종목이 추가된 배열
 */
export function addToRecentStocks(stocks: StockOption[], newStock: StockOption): StockOption[] {
  const updatedStocks = [
    newStock,
    ...stocks.filter(stock => stock.value !== newStock.value)
  ].slice(0, MAX_RECENT_STOCKS);
  
  saveRecentStocksToStorage(updatedStocks);
  return updatedStocks;
}

/**
 * 종목명 또는 코드로 종목 검색
 * @param stockOptions 전체 종목 목록
 * @param searchTerm 검색어
 * @param maxResults 최대 결과 수
 * @returns 검색 결과 종목 배열
 */
export function searchStocks(
  stockOptions: StockOption[], 
  searchTerm: string, 
  maxResults: number = 10
): StockOption[] {
  if (!searchTerm.trim()) {
    return [];
  }

  const term = searchTerm.toLowerCase().trim();
  return stockOptions
    .filter(stock => {
      const stockName = stock.stockName.toLowerCase();
      const stockCode = stock.stockCode;
      return stockName.includes(term) || stockCode.includes(term);
    })
    .slice(0, maxResults);
} 