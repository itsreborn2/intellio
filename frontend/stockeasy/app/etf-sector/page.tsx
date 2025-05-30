'use client'

import { Suspense, useState } from 'react'
import ETFCurrentTable from '../components/ETFCurrentTable'
import IndustryCharts from '../components/IndustryCharts'
import IndisrtongrsChart from '../components/IndisrtongrsChart'

// ETF/섹터 페이지 컴포넌트
export default function ETFSectorPage() {
  const [activeTab, setActiveTab] = useState<'industry' | 'leading'>('leading');

  return (
    <div className="flex-1 p-0 sm:p-2 md:p-4 overflow-auto w-full">
      {/* 사이드바 제거 - 이미 layout.tsx에 포함됨 */}
      
      {/* 메인 콘텐츠 영역 - 모바일 최적화 */}
      <div className="w-full max-w-[1280px] mx-auto"> 
        {/* ETF 현재가 테이블 */}
        <div className="mb-2 md:mb-4">
          <div className="bg-white rounded-md shadow p-2 md:p-4">
            <div className="bg-white rounded border border-gray-100 p-2 md:p-4">
              <Suspense fallback={<div className="h-80 flex items-center justify-center">로딩 중...</div>}>
                <ETFCurrentTable />
              </Suspense>
            </div>
          </div>
        </div>

        {/* 하단 섹션: 산업 차트 */}
        <div className="mb-2 md:mb-4 mt-4 md:mt-8">
          <div className="flex mb-0" style={{ marginLeft: '3px' }}>
            <button
              className={`px-2 sm:px-4 py-1 sm:py-2 rounded-t-[6px] rounded-l-[6px] font-medium text-xs transition-all ${
                activeTab === 'leading' 
                ? 'bg-gray-300 text-gray-800 shadow-lg transform scale-105 -translate-y-0.5 z-10 relative' 
                : 'bg-gray-200 text-gray-600 shadow-md hover:bg-gray-250'
              }`}
              onClick={() => setActiveTab('leading')}
            >
              섹터별 주도주 차트
            </button>
            <button
              className={`px-2 sm:px-4 py-1 sm:py-2 rounded-t-[6px] rounded-r-[6px] font-medium text-xs transition-all ${
                activeTab === 'industry' 
                ? 'bg-gray-300 text-gray-800 shadow-lg transform scale-105 -translate-y-0.5 z-10 relative' 
                : 'bg-gray-200 text-gray-600 shadow-md hover:bg-gray-250'
              }`}
              onClick={() => setActiveTab('industry')}
            >
              산업별 등락률 차트
            </button>
          </div>
          <div className="bg-white rounded-md shadow p-2 md:p-4 border border-gray-200">
            <div className="bg-white rounded border border-gray-100 p-2 md:p-4">
              {activeTab === 'industry' ? (
                <IndustryCharts />
              ) : (
                <IndisrtongrsChart />
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}