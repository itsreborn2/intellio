'use client'

import { Suspense, useState } from 'react'
import Sidebar from '../components/Sidebar'
import ETFCurrentTable from '../components/ETFCurrentTable'
import IndustryCharts from '../components/IndustryCharts'
import IndisrtongrsChart from '../components/IndisrtongrsChart'

// ETF/섹터 페이지 컴포넌트
export default function ETFSectorPage() {
  const [activeTab, setActiveTab] = useState<'industry' | 'leading'>('leading');

  return (
    <div className="flex">
      {/* 사이드바 */}
      <Sidebar />
      
      {/* 메인 콘텐츠 영역 - 모바일 최적화 */}
      <div className="flex-1 p-0 sm:p-2 md:p-4 overflow-auto ml-0 md:ml-16 w-full">
        {/* ETF 현재가 테이블 */}
        <div className="mb-2 md:mb-4">
          <div className="bg-white rounded-md shadow p-2 md:p-4">
            <Suspense fallback={<div className="h-80 flex items-center justify-center">로딩 중...</div>}>
              <ETFCurrentTable />
            </Suspense>
          </div>
        </div>

        {/* 하단 섹션: 산업 차트 */}
        <div className="mb-2 md:mb-4 mt-4 md:mt-8">
          <div className="flex mb-0" style={{ marginLeft: '3px' }}>
            <button
              className={`px-2 sm:px-4 py-1 sm:py-2 rounded-t-xl rounded-l-xl font-medium text-xs transition-all ${
                activeTab === 'leading' 
                ? 'bg-gray-300 text-gray-800 shadow-lg transform scale-105 -translate-y-0.5 z-10 relative' 
                : 'bg-gray-200 text-gray-600 shadow-md hover:bg-gray-250'
              }`}
              onClick={() => setActiveTab('leading')}
            >
              섹터별 주도주 차트
            </button>
            <button
              className={`px-2 sm:px-4 py-1 sm:py-2 rounded-t-xl rounded-r-xl font-medium text-xs transition-all ${
                activeTab === 'industry' 
                ? 'bg-gray-300 text-gray-800 shadow-lg transform scale-105 -translate-y-0.5 z-10 relative' 
                : 'bg-gray-200 text-gray-600 shadow-md hover:bg-gray-250'
              }`}
              onClick={() => setActiveTab('industry')}
            >
              산업별 ETF 차트
            </button>
          </div>
          <div className="bg-white rounded-b-md rounded-tr-md shadow">
            <div className="p-2 md:p-4">
              <Suspense fallback={<div className="h-80 flex items-center justify-center">로딩 중...</div>}>
                {activeTab === 'industry' ? <IndustryCharts /> : <IndisrtongrsChart />}
              </Suspense>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}