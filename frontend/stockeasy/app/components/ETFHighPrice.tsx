'use client'

import { useState, useEffect, useMemo } from 'react'
import Papa from 'papaparse'
import { fetchCSVData } from '../utils/fetchCSVData'
import { getETFHighPricesPath } from '../utils/googleDriveSync'

// CSV 데이터를 파싱한 결과를 위한 인터페이스
interface CSVData {
  headers: string[];
  rows: any[];
  errors: any[]; // 파싱 오류 정보
}

// ETF 52주 신고가 정보를 위한 인터페이스
interface ETFHighData {
  code: string;
  name: string;
  price: number;
  highPrice: number;
  highDate: string;
  changePercent: number; // 52주 신고가 대비 현재가 변동률
  volume: number;
}

// 정렬 타입 정의
type SortDirection = 'asc' | 'desc' | null;

// CSV 파일을 파싱하는 함수 (PapaParse 사용)
const parseCSV = (csvText: string): CSVData => {
  console.log('CSV 파싱 시작...');
  
  try {
    if (!csvText || typeof csvText !== 'string') {
      console.error('유효하지 않은 CSV 텍스트:', csvText);
      // 기본 데이터 반환
      return {
        headers: ['코드', '이름', '현재가', '52주 신고가', '신고가 날짜', '등락률', '거래량'],
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
      headers: ['코드', '이름', '현재가', '52주 신고가', '신고가 날짜', '등락률', '거래량'],
      rows: [],
      errors: [],
    };
  }
};

// ETF 52주 신고가 컴포넌트
export default function ETFHighPrice() {
  // 상태 관리
  const [highData, setHighData] = useState<CSVData>({ headers: [], rows: [], errors: [] });
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [currentPage, setCurrentPage] = useState<number>(1);
  const [sortKey, setSortKey] = useState<string>('');
  const [sortDirection, setSortDirection] = useState<SortDirection>(null);
  
  // 페이지당 표시할 항목 수
  const itemsPerPage = 10;
  
  useEffect(() => {
    // 페이지 로드 시 데이터 로드
    const loadHighData = async () => {
      setLoading(true);
      setError(null);
      
      try {
        // 구글 드라이브에서 ETF 52주 신고가 데이터 파일 경로 가져오기
        const filePath = await getETFHighPricesPath();
        
        if (!filePath) {
          throw new Error('ETF 52주 신고가 데이터 파일 경로를 가져오는데 실패했습니다.');
        }
        
        // 로컬 캐시 파일 로드
        const csvText = await fetchCSVData(filePath);
        console.log(`ETF 52주 신고가 데이터 로드 완료: ${csvText.length}자`);
        
        // CSV 파싱 및 데이터 처리
        const parsedData = parseCSV(csvText);
        console.log(`파싱 완료: ${parsedData.rows.length}개 데이터 로드됨`);
        
        setHighData(parsedData);
      } catch (err) {
        console.error('ETF 52주 신고가 데이터 로드 오류:', err);
        setError(`데이터를 로드하는데 실패했습니다: ${err instanceof Error ? err.message : '알 수 없는 오류'}`);
        
        // 샘플 데이터 생성
        const sampleData = generateSampleETFHighData();
        setHighData(sampleData);
      } finally {
        setLoading(false);
      }
    };
    
    loadHighData();
  }, []);
  
  // 샘플 ETF 52주 신고가 데이터 생성 함수
  const generateSampleETFHighData = (): CSVData => {
    const headers = ['코드', '이름', '현재가', '52주 신고가', '신고가 날짜', '등락률', '거래량'];
    const etfNames = [
      'KODEX 200', 'TIGER 200', 'KODEX 바이오', 'KODEX IT', 'TIGER 반도체',
      'KODEX 자동차', 'KODEX 배당', 'TIGER 배당', 'KODEX 중소형', 'KODEX 은행'
    ];
    
    const rows = etfNames.map((name, index) => {
      const code = `069${index.toString().padStart(3, '0')}`;
      const price = Math.round(10000 + Math.random() * 40000);
      const highPrice = Math.round(price * (1 + Math.random() * 0.2));
      
      // 최근 1년 내 랜덤 날짜 생성
      const today = new Date();
      const randomDaysAgo = Math.floor(Math.random() * 365);
      const highDate = new Date(today);
      highDate.setDate(today.getDate() - randomDaysAgo);
      const formattedHighDate = highDate.toISOString().split('T')[0]; // YYYY-MM-DD 형식
      
      const changePercent = +((price / highPrice - 1) * 100).toFixed(2);
      const volume = Math.round(100000 + Math.random() * 9000000);
      
      return {
        '코드': code,
        '이름': name,
        '현재가': price.toString(),
        '52주 신고가': highPrice.toString(),
        '신고가 날짜': formattedHighDate,
        '등락률': changePercent.toString(),
        '거래량': volume.toString()
      };
    });
    
    return { headers, rows, errors: [] };
  };
  
  // 정렬 처리 함수
  const handleSort = (key: string) => {
    if (sortKey === key) {
      // 같은 컬럼을 다시 클릭한 경우, 정렬 방향 변경
      setSortDirection(sortDirection === 'asc' ? 'desc' : sortDirection === 'desc' ? null : 'asc');
    } else {
      // 다른 컬럼을 클릭한 경우, 해당 컬럼으로 오름차순 정렬
      setSortKey(key);
      setSortDirection('asc');
    }
  };
  
  // 정렬된 데이터 계산
  const sortedData = useMemo(() => {
    if (!sortKey || !sortDirection || !highData.rows.length) {
      return highData.rows;
    }
    
    return [...highData.rows].sort((a, b) => {
      let aValue = a[sortKey];
      let bValue = b[sortKey];
      
      // 숫자 문자열을 숫자로 변환
      if (!isNaN(parseFloat(aValue)) && !isNaN(parseFloat(bValue))) {
        aValue = parseFloat(aValue);
        bValue = parseFloat(bValue);
      }
      
      if (aValue < bValue) return sortDirection === 'asc' ? -1 : 1;
      if (aValue > bValue) return sortDirection === 'asc' ? 1 : -1;
      return 0;
    });
  }, [highData.rows, sortKey, sortDirection]);
  
  // 페이지네이션 처리
  const paginatedData = useMemo(() => {
    const startIndex = (currentPage - 1) * itemsPerPage;
    return sortedData.slice(startIndex, startIndex + itemsPerPage);
  }, [sortedData, currentPage, itemsPerPage]);
  
  // 총 페이지 수 계산
  const totalPages = Math.ceil(sortedData.length / itemsPerPage);
  
  // 페이지 변경 함수
  const handlePageChange = (page: number) => {
    setCurrentPage(page);
  };
  
  // 변동률에 따른 색상 클래스 반환 함수
  const getChangeColorClass = (change: number) => {
    if (change > 0) return 'text-red-500';
    if (change < 0) return 'text-blue-500';
    return '';
  };
  
  // 로딩 중 표시
  if (loading) {
    return (
      <div className="bg-white rounded-md shadow p-4 h-80 flex items-center justify-center">
        <div className="text-gray-500">데이터 로딩 중...</div>
      </div>
    );
  }
  
  // 오류 표시
  if (error) {
    return (
      <div className="bg-white rounded-md shadow p-4 h-80 flex items-center justify-center">
        <div className="text-red-500">{error}</div>
      </div>
    );
  }
  
  // 데이터가 없는 경우
  if (!highData.rows.length) {
    return (
      <div className="bg-white rounded-md shadow p-4 h-80 flex items-center justify-center">
        <div className="text-gray-500">데이터가 없습니다.</div>
      </div>
    );
  }
  
  return (
    <div className="bg-white rounded-md shadow">
      <div className="p-4 border-b border-gray-200 font-medium">
        52주 ETF 신고가
      </div>
      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              {highData.headers.map((header) => (
                <th
                  key={header}
                  scope="col"
                  className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer"
                  onClick={() => handleSort(header)}
                >
                  {header}
                  {sortKey === header && (
                    <span className="ml-1">
                      {sortDirection === 'asc' ? '↑' : sortDirection === 'desc' ? '↓' : ''}
                    </span>
                  )}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {paginatedData.map((row: Record<string, any>, rowIndex: number) => (
              <tr key={rowIndex} className="hover:bg-gray-50">
                {highData.headers.map((header) => {
                  // 등락률 컬럼에 색상 적용
                  const isChangeColumn = header === '등락률';
                  const value = row[header];
                  const numericValue = isChangeColumn ? parseFloat(value) : null;
                  const colorClass = isChangeColumn ? getChangeColorClass(numericValue!) : '';
                  
                  return (
                    <td
                      key={header}
                      className={`px-6 py-4 whitespace-nowrap text-sm ${colorClass}`}
                    >
                      {isChangeColumn && numericValue! > 0 ? '+' : ''}
                      {value}
                      {header === '등락률' ? '%' : ''}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      
      {/* 페이지네이션 */}
      <div className="px-4 py-3 flex items-center justify-center border-t border-gray-200">
        <nav className="flex items-center">
          <button
            onClick={() => handlePageChange(Math.max(1, currentPage - 1))}
            disabled={currentPage === 1}
            className="px-3 py-1 rounded-md mr-2 text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed"
          >
            이전
          </button>
          
          {Array.from({ length: totalPages }, (_, i) => i + 1).map((page) => (
            <button
              key={page}
              onClick={() => handlePageChange(page)}
              className={`px-3 py-1 rounded-md mx-1 text-sm font-medium ${
                currentPage === page
                  ? 'bg-blue-600 text-white'
                  : 'text-gray-700 hover:bg-gray-100'
              }`}
            >
              {page}
            </button>
          ))}
          
          <button
            onClick={() => handlePageChange(Math.min(totalPages, currentPage + 1))}
            disabled={currentPage === totalPages}
            className="px-3 py-1 rounded-md ml-2 text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed"
          >
            다음
          </button>
        </nav>
      </div>
    </div>
  );
}
