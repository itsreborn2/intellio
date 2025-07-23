// trend-following 페이지 전체 레이아웃 및 섹션 컴포넌트 배치 (임시)
"use client";

import React, { useState, useEffect, useRef } from 'react'; // useRef 추가
import { X } from 'lucide-react'; // X 아이콘 추가
import ChartComponent from '../components/ChartComponent'; // 차트 컴포넌트 추가
import Papa from 'papaparse';
import MarketSignalSection from './components/MarketSignalSection';
import SectorLeaderSection from './components/SectorLeaderSection';
// 52주 신고가 주요 종목 섹션 (rs-rank/page.tsx와 100% 동일)
import High52Section from './components/High52Section';

import BreakoutCandidatesSection from './components/BreakoutCandidatesSection';
import BreakoutSustainSection from './components/BreakoutSustainSection';
import BreakoutFailSection from './components/BreakoutFailSection';
import MarketMonitor from './components/MarketMonitor';
import NewSectorEnter from './components/NewSectorEnter';
import NewSectorOut from './components/NewSectorOut';
import IndisrtongrsChart from '../components/IndisrtongrsChart';
// @ts-ignore
import High52Chart from './components/High52Chart';
// 돌파 차트 메인 컴포넌트
import BreakoutChartMain from './components/breakout/BreakoutChartMain';

// CSV 데이터 타입 정의 (하위 컴포넌트들과 동일하게)
interface BreakoutData {
  'Type'?: string;
  'Code': string;
  'Name': string;
  'Breakthrough Price': string;
  'Current Price'?: string;
  'Daily Change %'?: string;
  'Remaining %'?: string;
  'Gap %'?: string;
  'RS'?: string;
  'MTT'?: string;
  '저장시간'?: string;
  [key: string]: string | undefined;
}

// ETF 차트 데이터 타입 정의 (etf-sector/page.tsx와 동일)
interface ETFChartData {
  code: string;
  name: string;
  chartData: any[];
}

// 행 위치 정보를 위한 인터페이스 (etf-sector/page.tsx와 동일)
interface RowPosition {
  bottom: number;
  top: number;
  left: number;
  width: number;
}

export default function TrendFollowingMain() {
  // 탭 선택 상태 관리 ("trend": 추세추종, "monitor": 시장지표)
  const [activeTab, setActiveTab] = useState<'trend' | 'monitor'>('trend');
  // 섹터 탭 선택 상태 관리 ("sector": 주도섹터/주도주, "industry": 산업동향)
  const [sectorTab, setSectorTab] = useState<'sector' | 'industry'>('sector');
  // 52주 신고가 탭 선택 상태 관리 ("table": 테이블 뷰, "chart": 차트 뷰)
  const [high52Tab, setHigh52Tab] = useState<'table' | 'chart'>('table');
  // 돌파 섹션 탭 선택 상태 관리 ("list": 리스트 뷰, "chart": 차트 뷰)
  const [breakoutTab, setBreakoutTab] = useState<'list' | 'chart'>('list');
  // 돌파 리스트 업데이트 날짜/시간
  const [breakoutUpdateDate, setBreakoutUpdateDate] = useState<string>('');
  const [allBreakoutData, setAllBreakoutData] = useState<BreakoutData[]>([]); // 전체 데이터
  const [breakoutCandidatesData, setBreakoutCandidatesData] = useState<BreakoutData[]>([]);
  const [breakoutSustainData, setBreakoutSustainData] = useState<BreakoutData[]>([]);
  const [breakoutFailData, setBreakoutFailData] = useState<BreakoutData[]>([]);
  const [breakoutLoading, setBreakoutLoading] = useState<boolean>(true);
  const [breakoutError, setBreakoutError] = useState<string | null>(null);

  // --- 차트 팝업 관련 상태 (etf-sector/page.tsx에서 가져옴) ---
  const [showChartPopup, setShowChartPopup] = useState<boolean>(false);
  const [selectedETF, setSelectedETF] = useState<{code?: string; name?: string} | null>(null);
  const [etfChartData, setETFChartData] = useState<any[]>([]);
  const [isChartLoading, setIsChartLoading] = useState<boolean>(false);
  const [chartError, setChartError] = useState<string | null>(null);
  const popupRef = useRef<HTMLDivElement | null>(null);
  const [fileList, setFileList] = useState<string[]>([]);
  const [rowPosition, setRowPosition] = useState<RowPosition | null>(null);
  
  // breakout.csv 데이터 로드 (최초 마운트 시 한 번만 실행)
  useEffect(() => {
    async function loadBreakoutData() {
      // 데이터가 이미 로드되었거나 로딩 중이면 다시 로드하지 않음
      if (allBreakoutData.length > 0 || breakoutLoading === false && breakoutError === null) {
        // console.log('Data already loaded or successfully loaded previously.');
        // 기존 데이터로 필터링만 다시 수행할 수 있도록 breakoutLoading을 false로 유지
        // 만약 탭 전환 시 필터링된 데이터가 초기화되지 않도록 하려면 여기서 상태 업데이트를 하지 않거나
        // 필터링 로직을 useEffect 외부 또는 다른 useEffect로 분리해야 합니다.
        // 현재는 최초 로드만 처리하므로, 이 조건은 데이터가 이미 있을 때 재로드를 방지합니다.
        // 만약 activeTab, breakoutTab 변경 시 필터링만 다시 하고 싶다면, 
        // 이 useEffect는 최초 로드만 담당하고, 다른 useEffect에서 allBreakoutData를 기반으로 필터링합니다.
        // 여기서는 최초 로드에 집중합니다.
        // setBreakoutLoading(false); // 데이터가 이미 있으므로 로딩 완료 상태로 유지
        return; 
      }
      setBreakoutLoading(true);
      setBreakoutError(null);
      try {
        const response = await fetch('/requestfile/trend-following/breakout.csv', { cache: 'no-store' });
        if (!response.ok) {
          throw new Error(`breakout.csv 로드 실패: ${response.status}`);
        }
        const csvText = await response.text();
        Papa.parse<BreakoutData>(csvText, {
          header: true,
          skipEmptyLines: true,
          complete: (results) => {
            const parsedData = results.data;
            setAllBreakoutData(parsedData); // 전체 데이터 저장

            if (parsedData && parsedData.length > 0) {
              // '저장시간' 컬럼에서 첫 번째 유효한 값으로 업데이트 날짜 설정
              const firstValidDate = parsedData.find(row => row['저장시간'])?.['저장시간'];
              if (firstValidDate) {
                const dateObj = new Date(firstValidDate);
                if (!isNaN(dateObj.getTime())) {
                    const month = dateObj.getMonth() + 1;
                    const day = dateObj.getDate();
                    const hours = dateObj.getHours();
                    const minutes = dateObj.getMinutes();
                    setBreakoutUpdateDate(`${month}/${day.toString().padStart(2, '0')} ${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}`);
                } else {
                  setBreakoutUpdateDate(firstValidDate); // 원본 문자열 그대로 사용
                }
              } else {
                setBreakoutUpdateDate('날짜 정보 없음');
              }
            } else if (parsedData && parsedData.length > 0) { // 저장시간이 없지만 데이터는 있는 경우
              setBreakoutUpdateDate('날짜 정보 없음'); // 또는 기본 메시지
            } else {
              // CSV에 '저장시간'이 없는 경우 Last-Modified 헤더 사용
              const lastModifiedHeader = response.headers.get('Last-Modified');
            }
            // 필터링된 데이터 설정은 별도의 useEffect에서 처리하거나 여기서 직접 수행
            // allBreakoutData가 변경될 때마다 하위 컴포넌트에 전달할 데이터 필터링
            if (parsedData && parsedData.length > 0) {
              setBreakoutCandidatesData(parsedData.filter(item => item.Type === '돌파 후보'));
              setBreakoutSustainData(parsedData.filter(item => item.Type === '돌파 유지'));
              setBreakoutFailData(parsedData.filter(item => item.Type === '돌파 실패'));
            }
            setBreakoutLoading(false);
          },
          error: (error: any) => {
            console.error('CSV 파싱 오류:', error);
            setBreakoutError('데이터 파싱 중 오류 발생');
            setBreakoutLoading(false);
          }
        });
      } catch (e: any) {
        console.error('breakout.csv 데이터 로드 실패:', e);
        setBreakoutError(e.message || '데이터 로드 중 오류 발생');
        setBreakoutLoading(false);
      }
    }
    loadBreakoutData();
  }, []); // 의존성 배열을 빈 배열로 변경하여 최초 마운트 시에만 실행

  // allBreakoutData가 변경되면 각 섹션별 데이터 필터링
  useEffect(() => {
    if (allBreakoutData.length > 0) {
      // TODO: 실제 'Type' 컬럼 값에 맞게 필터링 조건 수정 필요
      // 예시: const candidates = breakoutDataAll.filter(item => item.Type === '돌파후보' || item.Type === 'Candidate');
      // 현재는 임의의 값을 사용하거나, 사용자님께서 직접 CSV를 확인 후 수정하셔야 합니다.
      // 아래는 'Type' 컬럼이 존재하고, '돌파 후보', '돌파 지속', '돌파 실패'라는 값을 가진다고 가정한 예시입니다.
      // 실제 CSV 파일의 'Type' 컬럼명과 값으로 수정해주세요.
      const candidates = allBreakoutData.filter((item: BreakoutData) => item.Type === '돌파 임박'); // 또는 다른 조건
      const sustain = allBreakoutData.filter((item: BreakoutData) => item.Type === '돌파 지속'); // 또는 다른 조건
      const fail = allBreakoutData.filter((item: BreakoutData) => item.Type === '돌파 실패'); // 또는 다른 조건

      setBreakoutCandidatesData(candidates);
      setBreakoutSustainData(sustain);
      setBreakoutFailData(fail);
    } else {
      setBreakoutCandidatesData([]);
      setBreakoutSustainData([]);
      setBreakoutFailData([]);
    }
  }, [allBreakoutData]);

  // --- 차트 팝업 관련 로직 (etf-sector/page.tsx에서 가져옴) ---

  // 컴포넌트 마운트 시 ETF 파일 목록 미리 로드
  useEffect(() => {
    const fetchFileList = async () => {
      try {
        const listRes = await fetch('/requestfile/etf_industry/file_list.json?t=' + Date.now());
        if (!listRes.ok) {
          throw new Error('file_list.json 파일을 찾을 수 없습니다.');
        }
        const { files }: { files: string[] } = await listRes.json();
        setFileList(files);
      } catch (error) {
        console.error('ETF 파일 목록 로드 오류:', error);
      }
    };

    fetchFileList();
  }, []);

  // ETF 차트 데이터 로드 함수
  const loadETFChartData = async (code: string, name: string) => {
    setIsChartLoading(true);
    setChartError(null);
    setETFChartData([]);
    
    try {
      if (fileList.length === 0) {
        throw new Error('ETF 파일 목록이 아직 로드되지 않았습니다.');
      }

      const matchingFile = fileList.find(filename => filename.startsWith(`${code}_`));
      
      if (!matchingFile) {
        throw new Error(`코드 ${code}에 해당하는 차트 파일을 찾을 수 없습니다.`);
      }
      
      const response = await fetch(`/requestfile/etf_industry/${matchingFile}?t=${Date.now()}`, { cache: 'no-store' });
      
      if (!response.ok) {
        throw new Error(`차트 데이터 로드 실패 (${response.status})`);
      }
      
      const csvText = await response.text();
      
      if (!csvText || csvText.trim().length === 0) {
        throw new Error('비어있는 CSV 파일');
      }
      
      const parsedData = parseChartData(csvText);
      
      if (parsedData && parsedData.length > 0) {
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

  // CSV 차트 데이터 파싱 함수
  const parseChartData = (csvText: string) => {
    const rows = csvText.trim().split('\n');
    const headers = rows[0].split(',');
    const candleData = [];
    for (let i = 1; i < rows.length; i++) {
      const row = rows[i].split(',');
      if (row.length < 6) continue;
      const time = row[0].trim();
      const open = parseFloat(row[1]);
      const high = parseFloat(row[2]);
      const low = parseFloat(row[3]);
      const close = parseFloat(row[4]);
      const volume = parseFloat(row[5]);
      if (isNaN(open) || isNaN(high) || isNaN(low) || isNaN(close)) continue;
      candleData.push({ time, open, high, low, close, volume });
    }
    return candleData.sort((a, b) => new Date(a.time).getTime() - new Date(b.time).getTime());
  };

  // ETF 클릭 이벤트 핸들러
  const handleETFClick = (code: string, name: string, position?: RowPosition) => {
    setSelectedETF({ code, name });
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
  
  // 팝업 위치 계산 함수
  const calculatePopupPosition = (position: RowPosition | null) => {
    if (!position) return {
      top: '50%',
      left: '50%',
      transform: 'translate(-50%, -50%)',
      maxWidth: '600px'
    };
    
    const popupHeight = 350;
    const bottomMargin = 20;
    const viewportHeight = window.innerHeight;
    const isNearBottom = position.bottom + popupHeight > viewportHeight - bottomMargin;
    
    return {
      top: isNearBottom ? `${position.top - popupHeight - 10}px` : `${position.bottom + 10}px`,
      left: `${position.left}px`,
      transform: 'none',
      maxWidth: `${position.width}px`
    };
  };

  // 외부 클릭 감지 핸들러
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (popupRef.current && !popupRef.current.contains(event.target as Node)) {
        handleClosePopup();
      }
    };
    
    if (showChartPopup) {
      setTimeout(() => {
        document.addEventListener('mousedown', handleClickOutside);
      }, 100);
    }
    
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [showChartPopup]);

  return (
    <div className="flex-1 p-0 sm:p-2 md:p-4 overflow-auto w-full">
      <div className="w-full max-w-[1280px] mx-auto">
        {/* 탭 메뉴와 시장 신호 섹션 통합 */}
        <div className="mb-2 md:mb-4 overflow-hidden">
          <div className="border-b border-gray-200">
            <div className="flex w-max space-x-0">
              <button
                className={`px-4 py-2 text-xs sm:text-sm font-medium rounded-tl-[6px] border-t border-l border-r border-gray-200 ${activeTab === 'trend' ? 'bg-white font-extrabold text-sm sm:text-base' : 'hover:bg-gray-100 border-b'}`}
                onClick={() => setActiveTab('trend')}
                style={{ 
                  color: activeTab === 'trend' ? 'var(--primary-text-color, var(--primary-text-color-fallback))' : 'var(--text-muted-color, var(--text-muted-color-fallback))',
                  fontWeight: activeTab === 'trend' ? 700 : 400
                }}
              >
                추세추종
              </button>
              <button
                className={`px-4 py-2 text-xs sm:text-sm font-medium rounded-tr-[6px] border-t border-r border-gray-200 ${activeTab === 'monitor' ? 'bg-white font-extrabold text-sm sm:text-base' : 'hover:bg-gray-100 border-b'}`}
                onClick={() => setActiveTab('monitor')}
                style={{ 
                  color: activeTab === 'monitor' ? 'var(--primary-text-color, var(--primary-text-color-fallback))' : 'var(--text-muted-color, var(--text-muted-color-fallback))',
                  fontWeight: activeTab === 'monitor' ? 700 : 400
                }}
              >
                시장지표
              </button>
            </div>
          </div>
          <div className="bg-white rounded-b-[6px] shadow p-2 md:p-4 border-b border-l border-r border-gray-200">
            <MarketSignalSection />
          </div>
        </div>
        
        {/* 추세추종 탭 콘텐츠 */}
        {activeTab === 'trend' && (
          <>
            {/* 섹터/산업 탭 메뉴 */}
            <div className="mb-2 md:mb-4 overflow-hidden">
              <div className="border-b border-gray-200">
                <div className="flex w-max space-x-0">
                  <button
                    className={`px-4 py-2 text-xs sm:text-sm font-medium rounded-tl-[6px] border-t border-l border-r border-gray-200 ${sectorTab === 'sector' ? 'bg-white font-extrabold text-sm sm:text-base' : 'hover:bg-gray-100 border-b'}`}
                    onClick={() => setSectorTab('sector')}
                    style={{ 
                      color: sectorTab === 'sector' ? 'var(--primary-text-color, var(--primary-text-color-fallback))' : 'var(--text-muted-color, var(--text-muted-color-fallback))',
                      fontWeight: sectorTab === 'sector' ? 700 : 400
                    }}
                  >
                    주도섹터
                  </button>
                  <button
                    className={`px-4 py-2 text-xs sm:text-sm font-medium rounded-tr-[6px] border-t border-r border-gray-200 ${sectorTab === 'industry' ? 'bg-white font-extrabold text-sm sm:text-base' : 'hover:bg-gray-100 border-b'}`}
                    onClick={() => setSectorTab('industry')}
                    style={{ 
                      color: sectorTab === 'industry' ? 'var(--primary-text-color, var(--primary-text-color-fallback))' : 'var(--text-muted-color, var(--text-muted-color-fallback))',
                      fontWeight: sectorTab === 'industry' ? 700 : 400
                    }}
                  >
                    차트
                  </button>
                </div>
              </div>
              <div className="bg-white rounded-b-[6px] shadow p-2 md:p-4 border-b border-l border-r border-gray-200">
                {sectorTab === 'sector' && <SectorLeaderSection />}
                {sectorTab === 'industry' && <IndisrtongrsChart />}
              </div>
            </div>
            <div className="mb-2 md:mb-4">
              <div className="bg-white rounded-[6px] shadow p-2 md:p-4 border border-gray-200">
                <NewSectorEnter onETFClick={handleETFClick} />
              </div>
            </div>
            <div className="mb-2 md:mb-4">
              <div className="bg-white rounded-[6px] shadow p-2 md:p-4 border border-gray-200">
                <NewSectorOut onETFClick={handleETFClick} />
              </div>
            </div>
            {/* 52주 신고가 주요 종목 섹션 - rs-rank/page.tsx와 완전히 동일하게 동작 */}
            <div className="mb-2 md:mb-4 overflow-hidden">
              <div className="border-b border-gray-200">
                <div className="flex w-max space-x-0">
                  <button
                    className={`px-4 py-2 text-xs sm:text-sm font-medium rounded-tl-[6px] border-t border-l border-r border-gray-200 ${high52Tab === 'table' ? 'bg-white font-extrabold text-sm sm:text-base' : 'hover:bg-gray-100 border-b'}`}
                    onClick={() => setHigh52Tab('table')}
                    style={{ 
                      color: high52Tab === 'table' ? 'var(--primary-text-color, var(--primary-text-color-fallback))' : 'var(--text-muted-color, var(--text-muted-color-fallback))',
                      fontWeight: high52Tab === 'table' ? 700 : 400
                    }}
                  >
                    52주 신고가
                  </button>
                  <button
                    className={`px-4 py-2 text-xs sm:text-sm font-medium rounded-tr-[6px] border-t border-r border-gray-200 ${high52Tab === 'chart' ? 'bg-white font-extrabold text-sm sm:text-base' : 'hover:bg-gray-100 border-b'}`}
                    onClick={() => setHigh52Tab('chart')}
                    style={{ 
                      color: high52Tab === 'chart' ? 'var(--primary-text-color, var(--primary-text-color-fallback))' : 'var(--text-muted-color, var(--text-muted-color-fallback))',
                      fontWeight: high52Tab === 'chart' ? 700 : 400
                    }}
                  >
                    차트
                  </button>
                </div>
              </div>
              <div className="bg-white rounded-b-[6px] shadow p-2 md:p-4 border-b border-l border-r border-gray-200">
                {high52Tab === 'table' && <High52Section />}
                {high52Tab === 'chart' && <High52Chart />}
              </div>
            </div>
            {/* 돌파 후보/성공/실패 섹션 */}
            <div className="mb-2 md:mb-4 overflow-hidden">
              <div className="border-b border-gray-200">
                <div className="flex w-max space-x-0">
                  <button
                    className={`px-4 py-2 text-xs sm:text-sm font-medium rounded-tl-[6px] border-t border-l border-r border-gray-200 ${breakoutTab === 'list' ? 'bg-white font-extrabold text-sm sm:text-base' : 'hover:bg-gray-100 border-b'}`}
                    onClick={() => setBreakoutTab('list')}
                    style={{ 
                      color: breakoutTab === 'list' ? 'var(--primary-text-color, var(--primary-text-color-fallback))' : 'var(--text-muted-color, var(--text-muted-color-fallback))',
                      fontWeight: breakoutTab === 'list' ? 700 : 400
                    }}
                  >
                    돌파 리스트
                  </button>
                  <button
                    className={`px-4 py-2 text-xs sm:text-sm font-medium rounded-tr-[6px] border-t border-r border-gray-200 ${breakoutTab === 'chart' ? 'bg-white font-extrabold text-sm sm:text-base' : 'hover:bg-gray-100 border-b'}`}
                    onClick={() => setBreakoutTab('chart')}
                    style={{ 
                      color: breakoutTab === 'chart' ? 'var(--primary-text-color, var(--primary-text-color-fallback))' : 'var(--text-muted-color, var(--text-muted-color-fallback))',
                      fontWeight: breakoutTab === 'chart' ? 700 : 400
                    }}
                  >
                    차트
                  </button>
                </div>
              </div>
              <div className="bg-white rounded-b-[6px] shadow p-2 md:p-4 border-b border-l border-r border-gray-200">
                {breakoutTab === 'list' && (
                  <>
                    <section className="bg-white rounded border border-gray-100 px-2 md:px-4 py-2 md:py-3">
                      <div className="mb-2">
                        <div className="font-semibold text-base md:text-lg" style={{ color: 'var(--primary-text-color, var(--primary-text-color-fallback))' }}>스탁이지 돌파 리스트</div>
                      </div>

                      <div className="grid grid-cols-1 md:grid-cols-2 gap-2 md:gap-4">
                        {/* 돌파 후보군(좌측) */}
                        <div className="bg-white rounded-[6px] shadow p-2 md:p-4 border border-gray-200 h-full">
                          <BreakoutCandidatesSection data={breakoutCandidatesData} updateDate={breakoutUpdateDate} loading={breakoutLoading} error={breakoutError} />
                        </div>
                        {/* 돌파 성공/실패(우측, 위아래로 분할) */}
                        <div className="flex flex-col gap-2 md:gap-4 h-full">
                          <div className="bg-white rounded-[6px] shadow p-2 md:p-4 border border-gray-200 flex-1">
                            <BreakoutSustainSection data={breakoutSustainData} updateDate={breakoutUpdateDate} loading={breakoutLoading} error={breakoutError} />
                          </div>
                          <div className="bg-white rounded-[6px] shadow p-2 md:p-4 border border-gray-200 flex-1">
                            <BreakoutFailSection data={breakoutFailData} updateDate={breakoutUpdateDate} loading={breakoutLoading} error={breakoutError} />
                          </div>
                        </div>
                      </div>
                    </section>
                  </>
                )}
                {breakoutTab === 'chart' && <BreakoutChartMain />}
              </div>
            </div>
          </>
        )}
        
        {/* 시장모니터 탭 콘텐츠 */}
        {activeTab === 'monitor' && (
          <div className="mb-2 md:mb-4">
            <div className="bg-white rounded-[6px] shadow p-2 md:p-4 border border-gray-200">
              <MarketMonitor />
            </div>
          </div>
        )}
      </div>

      {/* ETF 차트 팝업 모달 (etf-sector/page.tsx에서 가져옴) */}
      {showChartPopup && selectedETF && (
        <div
          ref={popupRef}
          className="fixed bg-white rounded-md shadow-lg w-7/12 md:w-2/5 lg:w-1/3 max-w-2xl max-h-[70vh] overflow-hidden flex flex-col z-50"
          style={{
            borderRadius: '6px',
            ...calculatePopupPosition(rowPosition)
          }}>
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
