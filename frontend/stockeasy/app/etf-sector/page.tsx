'use client';

import React, { Suspense, useState, useEffect, useRef } from 'react';
import ETFCurrentTable from '../components/ETFCurrentTable';
import IndustryCharts from '../components/IndustryCharts';
import ChartComponent from '../components/ChartComponent';
import { X } from 'lucide-react';

// ETF 차트 데이터 타입 정의
interface ETFChartData {
  code: string;
  name: string;
  chartData: any[];
}

export default function ETFSectorPage() {
  // 현재 선택된 탭 상태 관리 ('table': ETF 테이블 뷰, 'chart': 산업 차트 뷰)
  const [activeTab, setActiveTab] = useState<'table' | 'chart'>('table');

  // 팝업 상태 관리
  const [showChartPopup, setShowChartPopup] = useState<boolean>(false);
  // 선택된 ETF 정보 상태
  const [selectedETF, setSelectedETF] = useState<{code?: string; name?: string} | null>(null);
  // 차트 데이터 상태
  const [etfChartData, setETFChartData] = useState<any[]>([]);
  // 차트 로딩 상태
  const [isChartLoading, setIsChartLoading] = useState<boolean>(false);
  // 차트 에러 상태
  const [chartError, setChartError] = useState<string | null>(null);
  // 팝업 참조 - 외부 클릭 감지용
  const popupRef = useRef<HTMLDivElement | null>(null);

  // ETF 차트 데이터 로드 함수
  const loadETFChartData = async (code: string, name: string) => {
    setIsChartLoading(true);
    setChartError(null);
    setETFChartData([]);
    
    console.log(`ETF 차트 데이터 로드 시도 - 코드: ${code}, 이름: ${name}`);
    
    try {
      // 사용자가 확인한 정확한 경로 패턴 사용
      const chartFilePath = `/requestfile/etf_industry/${code}_${encodeURIComponent(name.replace(/\//g, '-'))}_*.csv`;
      console.log(`실제 파일 패턴: ${chartFilePath}`);
      
      // IndustryCharts처럼 file_list.json 가져와서 해당 코드를 가진 파일 찾기
      const listRes = await fetch('/requestfile/etf_industry/file_list.json?t=' + Date.now());
      
      if (!listRes.ok) {
        throw new Error('file_list.json 파일을 찾을 수 없습니다.');
      }
      
      const { files }: { files: string[] } = await listRes.json();
      console.log('찾은 파일 목록:', files);
      
      // 코드로 시작하는 파일 찾기
      const matchingFile = files.find(filename => filename.startsWith(`${code}_`));
      
      if (!matchingFile) {
        throw new Error(`코드 ${code}에 해당하는 차트 파일을 찾을 수 없습니다.`);
      }
      
      console.log(`매칭된 파일: ${matchingFile}`);
      
      const response = await fetch(`/requestfile/etf_industry/${matchingFile}?t=${Date.now()}`, { cache: 'no-store' });
      
      if (!response.ok) {
        throw new Error(`차트 데이터 로드 실패 (${response.status})`);
      }
      
      const csvText = await response.text();
      
      if (!csvText || csvText.trim().length === 0) {
        throw new Error('비어있는 CSV 파일');
      }
      
      // 차트 데이터 파싱
      const parsedData = parseChartData(csvText);
      
      if (parsedData && parsedData.length > 0) {
        console.log(`데이터 로드 성공 (${parsedData.length}개 항목)`);
        setETFChartData(parsedData);
      } else {
        throw new Error('파싱된 데이터가 비어 있습니다.');
      }
    } catch (error: any) {
      console.error('ETF 차트 데이터 로드 오류:', error);
      setChartError(`차트 데이터를 불러오는 중 오류가 발생했습니다: ${error.message || ''}`);
      setETFChartData([]);
    } finally {
      setIsChartLoading(false);
    }
  };

  // CSV 차트 데이터 파싱 함수 (IndustryCharts 컴포넌트의 parseChartData 함수와 유사)
  const parseChartData = (csvText: string) => {
    const rows = csvText.trim().split('\n');
    const headers = rows[0].split(',');
    
    const candleData = [];
    
    for (let i = 1; i < rows.length; i++) {
      const row = rows[i].split(',');
      if (row.length < 6) continue; // 데이터 부족
      
      const time = row[0].trim();
      const open = parseFloat(row[1]);
      const high = parseFloat(row[2]);
      const low = parseFloat(row[3]);
      const close = parseFloat(row[4]);
      const volume = parseFloat(row[5]);
      
      if (isNaN(open) || isNaN(high) || isNaN(low) || isNaN(close)) continue;
      
      candleData.push({ time, open, high, low, close, volume });
    }
    
    // 날짜순 정렬 (최신이 마지막)
    return candleData.sort((a, b) => {
      return new Date(a.time).getTime() - new Date(b.time).getTime();
    });
  };

  // 행 위치 정보를 위한 인터페이스
  interface RowPosition {
    bottom: number; // 행의 하단 위치 (Y 좌표)
    top: number;    // 행의 상단 위치 (Y 좌표)
    left: number;   // 행의 좌측 위치 (X 좌표)
    width: number;  // 행의 너비
  }

  // 클릭한 행의 위치 정보 저장
  const [rowPosition, setRowPosition] = useState<RowPosition | null>(null);

  // ETF 클릭 이벤트 핸들러
  const handleETFClick = (code: string, name: string, position?: RowPosition) => {
    setSelectedETF({ code, name });
    // 행 위치 정보가 있는 경우 저장
    if (position) {
      setRowPosition(position);
    } else {
      setRowPosition(null);
    }
    loadETFChartData(code, name);
    setShowChartPopup(true);
  };

  // 팝업 닫기 핸들러
  const handleClosePopup = () => {
    setShowChartPopup(false);
    setSelectedETF(null);
    setETFChartData([]);
  };
  
  // 화면 뷰포트 내에 팝업이 들어오도록 위치를 조정하는 함수
  const calculatePopupPosition = (position: RowPosition | null) => {
    if (!position) return {
      top: '50%',
      left: '50%',
      transform: 'translate(-50%, -50%)',
      maxWidth: '600px'
    };
    
    // 팝업 평균 높이 - 대략적인 값으로 설정
    const popupHeight = 350; // 팝업의 대략적인 높이
    const bottomMargin = 20; // 화면 하단과의 여백
    
    // 뷰포트 높이
    const viewportHeight = window.innerHeight;
    
    // 클릭 위치가 화면 하단에 가까운 경우
    const isNearBottom = position.bottom + popupHeight > viewportHeight - bottomMargin;
    
    // 화면 하단에 가까우면 클릭한 셀 위에 표시, 아니면 셀 아래에 표시
    return {
      top: isNearBottom ? `${position.top - popupHeight - 10}px` : `${position.bottom + 10}px`,
      left: `${position.left}px`,
      transform: 'none',
      maxWidth: `${position.width}px`
    };
  };

  // 외부 클릭 감지 핸들러 - 팝업이 열려있을 때만 동작
  useEffect(() => {
    // 팝업 외부 클릭 시 팝업 닫기 핸들러
    const handleClickOutside = (event: MouseEvent) => {
      // popupRef가 설정되어 있고, 클릭한 요소가 팝업 내부가 아닐 경우
      if (popupRef.current && !popupRef.current.contains(event.target as Node)) {
        handleClosePopup();
      }
    };
    
    // 팝업이 열려있을 때만 이벤트 리스너 등록
    if (showChartPopup) {
      // 약간의 지연을 두어 동일한 클릭 이벤트가 팝업을 열자마자 닫는 것을 방지
      setTimeout(() => {
        document.addEventListener('mousedown', handleClickOutside);
      }, 100);
    }
    
    // 컴포넌트 언마운트 또는 팝업이 닫힐 때 이벤트 리스너 제거
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [showChartPopup]); // 팝업 상태가 변경될 때마다 이펙트 재실행

  return (
    <div className="flex-1 p-0 sm:p-2 md:p-4 overflow-auto w-full">
      {/* 사이드바 제거 - 이미 layout.tsx에 포함됨 */}
      
      {/* 메인 콘텐츠 영역 - 모바일 최적화 */}
      <div className="w-full max-w-[1280px] mx-auto"> 
        {/* 탭 메뉴 */}
        <div className="mb-2 md:mb-4 overflow-hidden">
          <div className="border-b border-gray-200">
            <div className="flex w-max space-x-0">
              <button
                className={`px-4 py-2 text-xs sm:text-sm font-medium rounded-tl-[6px] border-t border-l border-r border-gray-200 ${activeTab === 'table' ? 'bg-white font-extrabold text-sm sm:text-base' : 'hover:bg-gray-100 border-b'}`}
                onClick={() => setActiveTab('table')}
                style={{ 
                  color: activeTab === 'table' ? 'var(--primary-text-color, oklch(0.372 0.044 257.287))' : 'var(--text-muted-color, var(--text-muted-color-fallback))',
                  fontWeight: activeTab === 'table' ? 700 : 400
                }}
              >
                ETF 현재가
              </button>
              <button
                className={`px-4 py-2 text-xs sm:text-sm font-medium rounded-tr-[6px] border-t border-r border-gray-200 ${activeTab === 'chart' ? 'bg-white font-extrabold text-sm sm:text-base' : 'hover:bg-gray-100 border-b'}`}
                onClick={() => setActiveTab('chart')}
                style={{ 
                  color: activeTab === 'chart' ? 'var(--primary-text-color, oklch(0.372 0.044 257.287))' : 'var(--text-muted-color, var(--text-muted-color-fallback))',
                  fontWeight: activeTab === 'chart' ? 700 : 400
                }}
              >
                산업 차트
              </button>
            </div>
          </div>
          
          {/* 탭 콘텐츠 영역 */}
          <div className="bg-white rounded-b-[6px] shadow p-2 md:p-4 border-b border-l border-r border-gray-200">
            {/* ETF 현재가 테이블 탭 */}
            {activeTab === 'table' && (
              <div className="bg-white rounded border border-gray-100 p-2 md:p-4">
                <Suspense fallback={<div className="h-80 flex items-center justify-center">로딩 중...</div>}>
                  <ETFCurrentTable onETFClick={handleETFClick} />
                </Suspense>
              </div>
            )}
            
            {/* 산업 차트 탭 */}
            {activeTab === 'chart' && (
              <div className="bg-white rounded border border-gray-100 p-2 md:p-4">
                <IndustryCharts />
              </div>
            )}
          </div>
        </div>
      </div>
      
      {/* ETF 차트 팝업 모달 - 스크롤 가능하고 팝업은 고정 위치 유지 */}
      {showChartPopup && selectedETF && (
        <div
          ref={popupRef} // 팝업 외부 클릭 감지를 위한 ref 추가
          className="fixed bg-white rounded-md shadow-lg w-7/12 md:w-2/5 lg:w-1/3 max-w-2xl max-h-[70vh] overflow-hidden flex flex-col z-50" 
          style={{ 
            borderRadius: '6px',
            ...calculatePopupPosition(rowPosition) // 뷰포트 외부로 나가지 않도록 위치 자동 계산
          }}>
          {/* 모달 헤더 - ETF 테이블 헤더와 동일한 배경색 적용 */}
          <div className="flex justify-between items-center px-3 py-2 border-b border-gray-200 bg-gray-100">
            <h3 className="text-sm font-medium">
              {selectedETF.name} 
              {selectedETF.code && (
                <span className="ml-2 text-xs text-gray-600">({selectedETF.code})</span>
              )}
            </h3>
            <button
              onClick={handleClosePopup}
              className="text-gray-400 hover:text-gray-600 focus:outline-none"
            >
              <X size={18} />
            </button>
          </div>
          
          {/* 모달 본문 - 차트 영역 */}
          <div className="p-4 overflow-auto flex-grow">
            {isChartLoading ? (
              <div className="h-64 flex items-center justify-center">
                <p className="text-gray-500">차트 데이터 로딩 중...</p>
              </div>
            ) : chartError ? (
              <div className="h-64 flex items-center justify-center">
                <p className="text-red-500">{chartError}</p>
              </div>
            ) : etfChartData.length > 0 ? (
              <div className="w-full">
                <ChartComponent 
                  data={etfChartData} 
                  title={selectedETF.name} 
                  subtitle={`(${selectedETF.code})`}
                  height={210} 
                  showVolume={true}
                  showMA20={true}
                  parentComponent="ETFSector"
                />
              </div>
            ) : (
              <div className="h-64 flex items-center justify-center">
                <p className="text-gray-500">차트 데이터가 없습니다.</p>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}