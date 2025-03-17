'use client'

import { Suspense } from 'react'
import Sidebar from '../components/Sidebar'
import ETFCurrentTable from '../components/ETFCurrentTable'
import IndustryCharts from '../components/IndustryCharts'

// ETF/섹터 페이지 컴포넌트
export default function ETFSectorPage() {
  return (
    <div className="flex">
      {/* 사이드바 */}
      <Sidebar />
      
      {/* 메인 콘텐츠 영역 */}
      <div className="flex-1 p-4 overflow-auto ml-16">
        {/* ETF 현재가 테이블 */}
        <div className="mb-4">
          <Suspense fallback={<div className="bg-white rounded-md shadow p-4 h-80 flex items-center justify-center">로딩 중...</div>}>
            <ETFCurrentTable />
          </Suspense>
        </div>
        
        {/* 하단 섹션: 산업 차트 */}
        <div className="mb-4">
          <Suspense fallback={<div className="bg-white rounded-md shadow p-4 h-80 flex items-center justify-center">로딩 중...</div>}>
            <IndustryCharts />
          </Suspense>
        </div>
      </div>
    </div>
  );
}