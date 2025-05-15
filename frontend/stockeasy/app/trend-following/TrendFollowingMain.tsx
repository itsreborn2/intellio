// trend-following 페이지 전체 레이아웃 및 섹션 컴포넌트 배치 (임시)
"use client";

import { useState } from 'react';
import MarketSignalSection from './components/MarketSignalSection';
import SectorLeaderSection from './components/SectorLeaderSection';
// 52주 신고가 주요 종목 섹션 (rs-rank/page.tsx와 100% 동일)
import High52Section from './components/High52Section';
import TrendChartSection from './components/TrendChartSection';
import BreakoutCandidatesSection from './components/BreakoutCandidatesSection';
import BreakoutSustainSection from './components/BreakoutSustainSection';
import BreakoutFailSection from './components/BreakoutFailSection';
import MarketMonitor from './components/MarketMonitor';

export default function TrendFollowingMain() {
  // 탭 선택 상태 관리 ("trend": 추세추종, "monitor": 시장지표)
  const [activeTab, setActiveTab] = useState<'trend' | 'monitor'>('trend');
  return (
    <div className="flex-1 p-0 sm:p-2 md:p-4 overflow-auto w-full">
      <div className="w-full max-w-[1280px] mx-auto">
        {/* 탭 메뉴와 시장 신호 섹션 통합 */}
        <div className="mb-2 md:mb-4 overflow-hidden">
          <div className="border-b border-gray-200">
            <div className="flex w-max space-x-0">
              <button
                className={`px-4 py-2 text-sm font-medium rounded-tl-[6px] border-t border-l border-r border-gray-200 ${activeTab === 'trend' ? 'bg-white text-blue-600 font-semibold' : 'text-gray-700 hover:bg-gray-100 border-b'}`}
                onClick={() => setActiveTab('trend')}
              >
                추세추종
              </button>
              <button
                className={`px-4 py-2 text-sm font-medium rounded-tr-[6px] border-t border-r border-gray-200 ${activeTab === 'monitor' ? 'bg-white text-blue-600 font-semibold' : 'text-gray-700 hover:bg-gray-100 border-b'}`}
                onClick={() => setActiveTab('monitor')}
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
            <div className="mb-2 md:mb-4">
              <div className="bg-white rounded-[6px] shadow p-2 md:p-4 border border-gray-200">
                <SectorLeaderSection />
              </div>
            </div>
            {/* 52주 신고가 주요 종목 섹션 - rs-rank/page.tsx와 완전히 동일하게 동작 */}
            <div className="mb-2 md:mb-4">
              <div className="bg-white rounded-[6px] shadow p-2 md:p-4 border border-gray-200">
                <High52Section />
              </div>
            </div>
            {/* 트렌드 차트 섹션 */}
            <div className="mb-2 md:mb-4">
              <div className="bg-white rounded-[6px] shadow p-2 md:p-4 border border-gray-200">
                <div className="bg-white rounded border border-gray-100 p-2 md:p-4">
                  <TrendChartSection />
                </div>
              </div>
            </div>
            {/* 돌파 후보/성공/실패: 후보는 좌측, 성공+실패는 우측에서 위아래로 */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-2 md:gap-4 mb-2 md:mb-4">
              {/* 돌파 후보군(좌측) */}
              <div className="bg-white rounded-[6px] shadow p-2 md:p-4 border border-gray-200 h-full">
                <div className="bg-white rounded border border-gray-100 p-2 md:p-4 h-full">
                  <BreakoutCandidatesSection />
                </div>
              </div>
              {/* 돌파 성공/실패(우측, 위아래로 분할) */}
              <div className="flex flex-col gap-2 md:gap-4 h-full">
                <div className="bg-white rounded-[6px] shadow p-2 md:p-4 border border-gray-200 flex-1">
                  <div className="bg-white rounded border border-gray-100 p-2 md:p-4 h-full">
                    <BreakoutSustainSection />
                  </div>
                </div>
                <div className="bg-white rounded-[6px] shadow p-2 md:p-4 border border-gray-200 flex-1">
                  <div className="bg-white rounded border border-gray-100 p-2 md:p-4 h-full">
                    <BreakoutFailSection />
                  </div>
                </div>
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
