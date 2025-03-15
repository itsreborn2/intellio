'use client'

import { Suspense } from 'react'
import Sidebar from '../components/Sidebar'
import ETFCurrentTable from '../components/ETFCurrentTable'
import ETFHighPrice from '../components/ETFHighPrice'
import IndustryCharts from '../components/IndustryCharts'

// ETF/섹터 페이지 컴포넌트
export default function ETFSectorPage() {
  return (
    <div className="flex">
      {/* 사이드바 */}
      <Sidebar />
      
      {/* 메인 콘텐츠 영역 */}
      <div className="flex-1 p-4 overflow-auto">
        {/* 페이지 제목 및 저작권 표시 */}
        <div className="flex justify-between items-center mb-4">
          <div>
            <h1 className="text-2xl font-bold">ETF/섹터</h1>
            <p className="text-sm text-gray-500">ETF 현재가 및 산업별 차트를 제공합니다.</p>
          </div>
          <div className="text-sm text-gray-500">
            Stockeasy (주)인텔리오
          </div>
        </div>
        
        {/* 상단 섹션: ETF 현재가 테이블과 52주 ETF 신고가 */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-4">
          {/* ETF 현재가 테이블 (2/3 너비) */}
          <div className="lg:col-span-2">
            <Suspense fallback={<div className="bg-white rounded-md shadow p-4 h-80 flex items-center justify-center">로딩 중...</div>}>
              <ETFCurrentTable />
            </Suspense>
          </div>
          
          {/* 52주 ETF 신고가 (1/3 너비) */}
          <div className="lg:col-span-1">
            <Suspense fallback={<div className="bg-white rounded-md shadow p-4 h-80 flex items-center justify-center">로딩 중...</div>}>
              <ETFHighPrice />
            </Suspense>
          </div>
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
