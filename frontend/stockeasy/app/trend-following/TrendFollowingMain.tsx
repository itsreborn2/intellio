// trend-following 페이지 전체 레이아웃 및 섹션 컴포넌트 배치 (임시)
"use client";

import { useState, useEffect } from 'react';
import MarketSignalSection from './components/MarketSignalSection';
import SectorLeaderSection from './components/SectorLeaderSection';
// 52주 신고가 주요 종목 섹션 (rs-rank/page.tsx와 100% 동일)
import High52Section from './components/High52Section';

import BreakoutCandidatesSection from './components/BreakoutCandidatesSection';
import BreakoutSustainSection from './components/BreakoutSustainSection';
import BreakoutFailSection from './components/BreakoutFailSection';
import MarketMonitor from './components/MarketMonitor';
import NewSectorEnter from './components/NewSectorEnter';
import IndisrtongrsChart from '../components/IndisrtongrsChart';
// @ts-ignore
import High52Chart from './components/High52Chart';
// 돌파 차트 메인 컴포넌트
import BreakoutChartMain from './components/breakout/BreakoutChartMain';

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
  const [updateDate, setUpdateDate] = useState<string>('');
  
  // 업데이트 날짜 로드
  useEffect(() => {
    async function loadUpdateDate() {
      try {
        // breakout.csv 파일의 마지막 수정 날짜 가져오기
        const response = await fetch('/requestfile/trend-following/breakout.csv', { cache: 'no-store' });
        
        if (!response.ok) {
          console.error(`데이터 파일 로드 실패: ${response.status}`);
          return;
        }
        
        // 응답 헤더에서 Last-Modified 값 추출
        const lastModified = response.headers.get('Last-Modified');
        
        if (lastModified) {
          // Last-Modified 헤더에서 날짜와 시간 추출하여 포맷팅
          const modifiedDate = new Date(lastModified);
          const month = modifiedDate.getMonth() + 1; // getMonth()는 0부터 시작하므로 1 더함
          const day = modifiedDate.getDate();
          const hours = modifiedDate.getHours();
          const minutes = modifiedDate.getMinutes();
          
          // M/DD HH:MM 형식으로 포맷팅
          const formattedDate = `${month}/${day.toString().padStart(2, '0')} ${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}`;
          setUpdateDate(formattedDate);
        }
      } catch (e) {
        console.error('업데이트 날짜 로드 실패:', e);
      }
    }
    
    // 돌파 리스트 탭이 활성화될 때 업데이트 날짜 로드
    if (activeTab === 'trend' && breakoutTab === 'list') {
      loadUpdateDate();
    }
  }, [activeTab, breakoutTab]);
  return (
    <div className="flex-1 p-0 sm:p-2 md:p-4 overflow-auto w-full">
      <div className="w-full max-w-[1280px] mx-auto">
        {/* 탭 메뉴와 시장 신호 섹션 통합 */}
        <div className="mb-2 md:mb-4 overflow-hidden">
          <div className="border-b border-gray-200">
            <div className="flex w-max space-x-0">
              <button
                className={`px-4 py-2 text-sm font-medium rounded-tl-[6px] border-t border-l border-r border-gray-200 ${activeTab === 'trend' ? 'bg-white font-extrabold text-base' : 'hover:bg-gray-100 border-b'}`}
                onClick={() => setActiveTab('trend')}
                style={{ 
                  color: activeTab === 'trend' ? 'var(--primary-text-color, var(--primary-text-color-fallback))' : 'var(--text-muted-color, var(--text-muted-color-fallback))',
                  fontWeight: activeTab === 'trend' ? 700 : 400
                }}
              >
                추세추종
              </button>
              <button
                className={`px-4 py-2 text-sm font-medium rounded-tr-[6px] border-t border-r border-gray-200 ${activeTab === 'monitor' ? 'bg-white font-extrabold text-base' : 'hover:bg-gray-100 border-b'}`}
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
                    className={`px-4 py-2 text-sm font-medium rounded-tl-[6px] border-t border-l border-r border-gray-200 ${sectorTab === 'sector' ? 'bg-white font-extrabold text-base' : 'hover:bg-gray-100 border-b'}`}
                    onClick={() => setSectorTab('sector')}
                    style={{ 
                      color: sectorTab === 'sector' ? 'var(--primary-text-color, var(--primary-text-color-fallback))' : 'var(--text-muted-color, var(--text-muted-color-fallback))',
                      fontWeight: sectorTab === 'sector' ? 700 : 400
                    }}
                  >
                    주도섹터/주도주
                  </button>
                  <button
                    className={`px-4 py-2 text-sm font-medium rounded-tr-[6px] border-t border-r border-gray-200 ${sectorTab === 'industry' ? 'bg-white font-extrabold text-base' : 'hover:bg-gray-100 border-b'}`}
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
                <NewSectorEnter />
              </div>
            </div>
            {/* 52주 신고가 주요 종목 섹션 - rs-rank/page.tsx와 완전히 동일하게 동작 */}
            <div className="mb-2 md:mb-4 overflow-hidden">
              <div className="border-b border-gray-200">
                <div className="flex w-max space-x-0">
                  <button
                    className={`px-4 py-2 text-sm font-medium rounded-tl-[6px] border-t border-l border-r border-gray-200 ${high52Tab === 'table' ? 'bg-white font-extrabold text-base' : 'hover:bg-gray-100 border-b'}`}
                    onClick={() => setHigh52Tab('table')}
                    style={{ 
                      color: high52Tab === 'table' ? 'var(--primary-text-color, var(--primary-text-color-fallback))' : 'var(--text-muted-color, var(--text-muted-color-fallback))',
                      fontWeight: high52Tab === 'table' ? 700 : 400
                    }}
                  >
                    52주 신고가
                  </button>
                  <button
                    className={`px-4 py-2 text-sm font-medium rounded-tr-[6px] border-t border-r border-gray-200 ${high52Tab === 'chart' ? 'bg-white font-extrabold text-base' : 'hover:bg-gray-100 border-b'}`}
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
                    className={`px-4 py-2 text-sm font-medium rounded-tl-[6px] border-t border-l border-r border-gray-200 ${breakoutTab === 'list' ? 'bg-white font-extrabold text-base' : 'hover:bg-gray-100 border-b'}`}
                    onClick={() => setBreakoutTab('list')}
                    style={{ 
                      color: breakoutTab === 'list' ? 'var(--primary-text-color, var(--primary-text-color-fallback))' : 'var(--text-muted-color, var(--text-muted-color-fallback))',
                      fontWeight: breakoutTab === 'list' ? 700 : 400
                    }}
                  >
                    돌파 리스트
                  </button>
                  <button
                    className={`px-4 py-2 text-sm font-medium rounded-tr-[6px] border-t border-r border-gray-200 ${breakoutTab === 'chart' ? 'bg-white font-extrabold text-base' : 'hover:bg-gray-100 border-b'}`}
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
                        <div className="font-semibold" style={{ fontSize: '18px', color: 'var(--primary-text-color, var(--primary-text-color-fallback))' }}>스탁이지 돌파 리스트</div>
                      </div>

                      <div className="grid grid-cols-1 md:grid-cols-2 gap-2 md:gap-4">
                        {/* 돌파 후보군(좌측) */}
                        <div className="bg-white rounded-[6px] shadow p-2 md:p-4 border border-gray-200 h-full">
                          <BreakoutCandidatesSection />
                        </div>
                        {/* 돌파 성공/실패(우측, 위아래로 분할) */}
                        <div className="flex flex-col gap-2 md:gap-4 h-full">
                          <div className="bg-white rounded-[6px] shadow p-2 md:p-4 border border-gray-200 flex-1">
                            <BreakoutSustainSection />
                          </div>
                          <div className="bg-white rounded-[6px] shadow p-2 md:p-4 border border-gray-200 flex-1">
                            <BreakoutFailSection />
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
    </div>
  );
}
