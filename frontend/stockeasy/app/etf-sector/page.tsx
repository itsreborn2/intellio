'use client'

import { Suspense, useState, useEffect, useMemo, useCallback } from 'react'
import Sidebar from '../components/Sidebar'
import Papa from 'papaparse'
import { fetchCSVData } from '../utils/fetchCSVData'

// CSV 데이터를 파싱한 결과를 위한 인터페이스
interface CSVData {
  headers: string[];
  rows: any[];
  errors: any[]; // 파싱 오류 정보
}

// ETF/섹터 정보를 위한 인터페이스
interface ETFData {
  code: string;
  name: string;
  type: string; // 'ETF' 또는 'SECTOR'
  price: number;
  change: number;
  changePercent: number;
  volume: number;
  marketCap?: number; // 시가총액 (ETF의 경우)
  components?: number; // 구성 종목 수 (섹터의 경우)
}

// CSV 파일을 파싱하는 함수 (PapaParse 사용)
const parseCSV = (csvText: string): CSVData => {
  console.log('CSV 파싱 시작...');
  
  try {
    if (!csvText || typeof csvText !== 'string') {
      console.error('유효하지 않은 CSV 텍스트:', csvText);
      // 기본 데이터 반환
      return {
        headers: ['코드', '이름', '유형', '가격', '변동', '변동률', '거래량', '시가총액', '구성종목수'],
        rows: [],
        errors: [],
      };
    }
    
    // Papa Parse 옵션
    const results = Papa.parse(csvText, {
      header: true,       // 첫 번째 행을 헤더로 사용
      skipEmptyLines: true, // 빈 줄 건너뛰기
      dynamicTyping: false,  // 문자열 그대로 유지 (수동 변환)
    });
    
    console.log('파싱 결과 오류:', results.errors);
    console.log('파싱된 데이터 행 수:', results.data.length);
    
    return {
      headers: results.meta.fields || [],
      rows: results.data || [],
      errors: results.errors || [],
    };
  } catch (error) {
    console.error('CSV 파싱 오류:', error);
    // 오류 발생 시 빈 데이터 반환
    return {
      headers: ['코드', '이름', '유형', '가격', '변동', '변동률', '거래량', '시가총액', '구성종목수'],
      rows: [],
      errors: [],
    };
  }
};

// 정렬 타입 정의
type SortDirection = 'asc' | 'desc' | null;

// ETF/섹터 페이지 컴포넌트
export default function ETFSectorPage() {
  // 상태 관리
  const [csvData, setCsvData] = useState<CSVData>({ headers: [], rows: [], errors: [] });
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [currentPage, setCurrentPage] = useState<number>(1);
  const [sortKey, setSortKey] = useState<string>('');
  const [sortDirection, setSortDirection] = useState<SortDirection>(null);
  const [filterType, setFilterType] = useState<string>('all'); // 'all', 'etf', 'sector'
  const [searchTerm, setSearchTerm] = useState<string>('');
  
  // 페이지 로드 시 스크롤 위치를 최상단으로 설정
  useEffect(() => {
    window.scrollTo(0, 0);
    
    // 페이지 이동 시 스크롤 위치를 최상단으로 설정
    const handleRouteChange = () => {
      window.scrollTo(0, 0);
    };
    
    window.addEventListener('popstate', handleRouteChange);
    
    return () => {
      window.removeEventListener('popstate', handleRouteChange);
    };
  }, []);
  
  // CSV 데이터 로드
  useEffect(() => {
    const loadCSVData = async () => {
      setLoading(true);
      setError(null);
      
      try {
        // 샘플 데이터 (실제로는 API 호출로 대체)
        const sampleData = [
          { code: '069500', name: 'KODEX 200', type: 'ETF', price: 35850, change: 350, changePercent: 0.99, volume: 1234567, marketCap: 5678900000 },
          { code: '102110', name: 'TIGER 200', type: 'ETF', price: 35900, change: 400, changePercent: 1.13, volume: 987654, marketCap: 4567800000 },
          { code: '005930', name: '삼성전자', type: 'SECTOR', price: 68700, change: -300, changePercent: -0.43, volume: 9876543, components: 1 },
          { code: '000660', name: 'SK하이닉스', type: 'SECTOR', price: 156000, change: 2000, changePercent: 1.30, volume: 3456789, components: 1 },
          { code: '035420', name: 'NAVER', type: 'SECTOR', price: 214500, change: 1500, changePercent: 0.70, volume: 567890, components: 1 },
          { code: '051910', name: 'LG화학', type: 'SECTOR', price: 456000, change: -4000, changePercent: -0.87, volume: 234567, components: 1 },
          { code: '373220', name: 'LG에너지솔루션', type: 'SECTOR', price: 432000, change: 5000, changePercent: 1.17, volume: 345678, components: 1 },
          { code: '207940', name: '삼성바이오로직스', type: 'SECTOR', price: 789000, change: -1000, changePercent: -0.13, volume: 123456, components: 1 },
          { code: '152100', name: 'ARIRANG 200', type: 'ETF', price: 35800, change: 300, changePercent: 0.85, volume: 234567, marketCap: 2345600000 },
          { code: '278530', name: 'KODEX 미국S&P500', type: 'ETF', price: 15650, change: 150, changePercent: 0.97, volume: 345678, marketCap: 3456700000 },
        ];
        
        // 실제 구현 시에는 아래 주석을 해제하고 API 호출
        // const csvText = await fetchCSVData('etf_sector_data.csv');
        // const parsedData = parseCSV(csvText);
        // setCsvData(parsedData);
        
        // 샘플 데이터 사용
        setCsvData({
          headers: ['코드', '이름', '유형', '가격', '변동', '변동률', '거래량', '시가총액', '구성종목수'],
          rows: sampleData,
          errors: []
        });
      } catch (err) {
        console.error('데이터 로드 오류:', err);
        setError('데이터를 불러오는 중 오류가 발생했습니다.');
      } finally {
        setLoading(false);
      }
    };
    
    loadCSVData();
  }, []);
  
  // 정렬 처리 함수
  const handleSort = useCallback((key: string) => {
    if (sortKey === key) {
      // 같은 컬럼을 다시 클릭한 경우, 정렬 방향 변경
      setSortDirection(prev => prev === 'asc' ? 'desc' : prev === 'desc' ? null : 'asc');
    } else {
      // 다른 컬럼을 클릭한 경우, 해당 컬럼으로 오름차순 정렬
      setSortKey(key);
      setSortDirection('asc');
    }
  }, [sortKey]);
  
  // 필터링된 데이터
  const filteredData = useMemo(() => {
    let result = [...csvData.rows];
    
    // 유형별 필터링
    if (filterType !== 'all') {
      result = result.filter(item => item.type.toLowerCase() === filterType);
    }
    
    // 검색어 필터링
    if (searchTerm.trim()) {
      const term = searchTerm.toLowerCase();
      result = result.filter(item => 
        item.code.toLowerCase().includes(term) || 
        item.name.toLowerCase().includes(term)
      );
    }
    
    // 정렬
    if (sortKey && sortDirection) {
      result.sort((a, b) => {
        const valueA = a[sortKey];
        const valueB = b[sortKey];
        
        // 숫자인 경우 숫자 비교, 그 외에는 문자열 비교
        const compareResult = typeof valueA === 'number' && typeof valueB === 'number'
          ? valueA - valueB
          : String(valueA).localeCompare(String(valueB));
          
        return sortDirection === 'asc' ? compareResult : -compareResult;
      });
    }
    
    return result;
  }, [csvData.rows, filterType, searchTerm, sortKey, sortDirection]);
  
  // 페이지네이션 설정
  const itemsPerPage = 20;
  const totalPages = Math.ceil(filteredData.length / itemsPerPage);
  
  // 현재 페이지 데이터
  const currentData = useMemo(() => {
    const startIndex = (currentPage - 1) * itemsPerPage;
    return filteredData.slice(startIndex, startIndex + itemsPerPage);
  }, [filteredData, currentPage, itemsPerPage]);
  
  // 페이지 변경 핸들러
  const handlePageChange = (page: number) => {
    setCurrentPage(page);
    window.scrollTo(0, 0);
  };
  
  return (
    <div className="flex h-screen bg-gray-100">
      <Sidebar />
      
      <div className="flex-1 overflow-auto p-4">
        <h1 className="text-2xl font-bold mb-4">ETF/섹터 정보</h1>
        
        {/* 필터 및 검색 영역 */}
        <div className="flex flex-wrap gap-4 mb-4">
          <div className="flex items-center space-x-2">
            <label className="text-sm font-medium">유형:</label>
            <select 
              className="border rounded p-1 text-sm"
              value={filterType}
              onChange={(e) => setFilterType(e.target.value)}
            >
              <option value="all">전체</option>
              <option value="etf">ETF</option>
              <option value="sector">섹터</option>
            </select>
          </div>
          
          <div className="flex-1">
            <input
              type="text"
              placeholder="코드 또는 이름으로 검색"
              className="border rounded p-1 text-sm w-full"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
            />
          </div>
        </div>
        
        {/* 로딩 및 에러 표시 */}
        {loading && <div className="text-center py-4">데이터를 불러오는 중...</div>}
        {error && <div className="text-red-500 py-4">{error}</div>}
        
        {/* 데이터 테이블 */}
        {!loading && !error && (
          <div className="overflow-x-auto">
            <table className="min-w-full bg-white border">
              <thead>
                <tr className="bg-gray-100">
                  <th className="border p-2 text-sm text-left cursor-pointer" onClick={() => handleSort('code')}>
                    코드 {sortKey === 'code' && (sortDirection === 'asc' ? '↑' : sortDirection === 'desc' ? '↓' : '')}
                  </th>
                  <th className="border p-2 text-sm text-left cursor-pointer" onClick={() => handleSort('name')}>
                    이름 {sortKey === 'name' && (sortDirection === 'asc' ? '↑' : sortDirection === 'desc' ? '↓' : '')}
                  </th>
                  <th className="border p-2 text-sm text-left cursor-pointer" onClick={() => handleSort('type')}>
                    유형 {sortKey === 'type' && (sortDirection === 'asc' ? '↑' : sortDirection === 'desc' ? '↓' : '')}
                  </th>
                  <th className="border p-2 text-sm text-right cursor-pointer" onClick={() => handleSort('price')}>
                    가격 {sortKey === 'price' && (sortDirection === 'asc' ? '↑' : sortDirection === 'desc' ? '↓' : '')}
                  </th>
                  <th className="border p-2 text-sm text-right cursor-pointer" onClick={() => handleSort('changePercent')}>
                    변동률 {sortKey === 'changePercent' && (sortDirection === 'asc' ? '↑' : sortDirection === 'desc' ? '↓' : '')}
                  </th>
                  <th className="border p-2 text-sm text-right cursor-pointer" onClick={() => handleSort('volume')}>
                    거래량 {sortKey === 'volume' && (sortDirection === 'asc' ? '↑' : sortDirection === 'desc' ? '↓' : '')}
                  </th>
                  <th className="border p-2 text-sm text-right">
                    {filterType === 'etf' ? '시가총액' : filterType === 'sector' ? '구성종목수' : '추가 정보'}
                  </th>
                </tr>
              </thead>
              <tbody>
                {currentData.map((item, index) => (
                  <tr key={index} className="hover:bg-gray-50">
                    <td className="border p-2 text-sm">{item.code}</td>
                    <td className="border p-2 text-sm font-medium">{item.name}</td>
                    <td className="border p-2 text-sm">{item.type}</td>
                    <td className="border p-2 text-sm text-right">{item.price.toLocaleString()}</td>
                    <td className={`border p-2 text-sm text-right ${item.changePercent > 0 ? 'text-red-500' : item.changePercent < 0 ? 'text-blue-500' : ''}`}>
                      {item.change > 0 ? '+' : ''}{item.change.toLocaleString()} ({item.changePercent > 0 ? '+' : ''}{item.changePercent.toFixed(2)}%)
                    </td>
                    <td className="border p-2 text-sm text-right">{item.volume.toLocaleString()}</td>
                    <td className="border p-2 text-sm text-right">
                      {item.type === 'ETF' && item.marketCap ? (item.marketCap / 100000000).toFixed(0) + '억' : ''}
                      {item.type === 'SECTOR' && item.components ? item.components + '개' : ''}
                    </td>
                  </tr>
                ))}
                
                {currentData.length === 0 && (
                  <tr>
                    <td colSpan={7} className="border p-4 text-center text-gray-500">
                      데이터가 없습니다.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        )}
        
        {/* 페이지네이션 */}
        {!loading && !error && totalPages > 1 && (
          <div className="flex justify-center mt-4">
            <div className="flex space-x-1">
              <button
                onClick={() => handlePageChange(1)}
                disabled={currentPage === 1}
                className={`px-3 py-1 rounded ${currentPage === 1 ? 'bg-gray-200 text-gray-500' : 'bg-gray-300 hover:bg-gray-400'}`}
              >
                처음
              </button>
              
              <button
                onClick={() => handlePageChange(currentPage - 1)}
                disabled={currentPage === 1}
                className={`px-3 py-1 rounded ${currentPage === 1 ? 'bg-gray-200 text-gray-500' : 'bg-gray-300 hover:bg-gray-400'}`}
              >
                이전
              </button>
              
              {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
                // 현재 페이지를 중심으로 5개의 페이지 번호 표시
                const pageNum = Math.max(1, Math.min(currentPage - 2 + i, totalPages));
                return (
                  <button
                    key={pageNum}
                    onClick={() => handlePageChange(pageNum)}
                    className={`px-3 py-1 rounded ${currentPage === pageNum ? 'bg-blue-500 text-white' : 'bg-gray-300 hover:bg-gray-400'}`}
                  >
                    {pageNum}
                  </button>
                );
              })}
              
              <button
                onClick={() => handlePageChange(currentPage + 1)}
                disabled={currentPage === totalPages}
                className={`px-3 py-1 rounded ${currentPage === totalPages ? 'bg-gray-200 text-gray-500' : 'bg-gray-300 hover:bg-gray-400'}`}
              >
                다음
              </button>
              
              <button
                onClick={() => handlePageChange(totalPages)}
                disabled={currentPage === totalPages}
                className={`px-3 py-1 rounded ${currentPage === totalPages ? 'bg-gray-200 text-gray-500' : 'bg-gray-300 hover:bg-gray-400'}`}
              >
                마지막
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
