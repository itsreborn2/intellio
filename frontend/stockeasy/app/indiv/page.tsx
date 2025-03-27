'use client'

import React from 'react';
import Sidebar from '../components/Sidebar';
import Indiv1 from '../components/indiv_1';
import Indiv2 from '../components/indiv_2';
import Indiv3 from '../components/indiv_3';
import Indiv4 from '../components/indiv_4';
import Indiv5 from '../components/indiv_5';

export default function IndiePage() {
  return (
    <div className="flex h-screen overflow-hidden">
      {/* 사이드바 */}
      <Sidebar />
      
      {/* 메인 콘텐츠 영역 */}
      <div className="flex flex-col w-full h-screen overflow-auto" style={{ marginLeft: 'var(--sidebar-margin, 63px)' }}>
        {/* 상단 영역 (전체 높이의 40%) */}
        <div className="flex w-full h-[40%]">
          {/* 상단 영역을 5:2.5:2.5 비율로 나누기 */}
          <div className="w-[50%]">
            <Indiv1 />
          </div>
          <div className="w-[25%]">
            <Indiv2 />
          </div>
          <div className="w-[25%]">
            <Indiv3 />
          </div>
        </div>
        
        {/* 하단 영역 (전체 높이의 60%) */}
        <div className="flex w-full h-[60%]">
          {/* 하단 영역을 5:5 비율로 나누기 */}
          <div className="w-[50%]">
            <Indiv4 />
          </div>
          <div className="w-[50%]">
            <Indiv5 />
          </div>
        </div>
      </div>
    </div>
  );
}
