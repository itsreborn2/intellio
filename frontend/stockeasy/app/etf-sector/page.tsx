'use client'

import { Suspense, useState } from 'react'
import Sidebar from '../components/Sidebar'
import ETFCurrentTable from '../components/ETFCurrentTable'
import IndustryCharts from '../components/IndustryCharts'
import IndisrtongrsChart from '../components/IndisrtongrsChart'

// ETF/섹터 페이지 컴포넌트
export default function ETFSectorPage() {
  const [activeTab, setActiveTab] = useState<'industry' | 'leading'>('industry');

  return (
    <div className="flex">
      {/* 사이드바 */}
      <Sidebar />
      
      {/* 메인 콘텐츠 영역 */}
      <div className="flex-1 p-4 overflow-auto ml-16">
        {/* ETF 현재가 테이블 */}
        <div className="mb-4">
          <div className="bg-white rounded-md shadow p-4">
            <Suspense fallback={<div className="h-80 flex items-center justify-center">로딩 중...</div>}>
              <ETFCurrentTable />
            </Suspense>
          </div>
        </div>

        {/* 하단 섹션: 산업 차트 */}
        <div className="mb-4 mt-8">
          <div className="flex mb-0">
            <button
              className={`px-4 py-2 rounded-t-lg font-medium text-xs transition-all ${
                activeTab === 'leading' 
                ? 'bg-gray-300 text-gray-800 shadow-lg transform scale-105 -translate-y-0.5 z-10 relative' 
                : 'bg-gray-200 text-gray-600 shadow-md hover:bg-gray-250'
              }`}
              onClick={() => setActiveTab('leading')}
            >
              섹터별 주도주 차트
            </button>
            <button
              className={`px-4 py-2 rounded-t-lg font-medium text-xs transition-all ${
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
            <div className="p-4">
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