'use client'

import { Suspense, useState, useRef, useEffect } from 'react'
import { Button } from "intellio-common/components/ui/button"
import {
  Home,
  BarChart,
  ChartColumn,
  FileStack,
  FileText,
  User,
  Users,
  Settings,
  PieChart, // ETF/섹터 아이콘으로 PieChart 추가
  LayoutDashboard // 로고 대신 LayoutDashboard 아이콘 사용 (V와 유사)
} from 'lucide-react';
import { useRouter } from 'next/navigation';

// 컨텐츠 컴포넌트
function SidebarContent() {
  const router = useRouter();
  // 호버 상태를 관리하는 state
  const [hoveredButton, setHoveredButton] = useState<string | null>(null);
  const [tooltipPosition, setTooltipPosition] = useState<{ [key: string]: number }>({});
  
  // 버튼 참조 객체
  const buttonRefs = {
    home: useRef<HTMLButtonElement>(null),
    chart: useRef<HTMLButtonElement>(null),
    etfSector: useRef<HTMLButtonElement>(null), // ETF/섹터 버튼 참조 추가
    doc: useRef<HTMLButtonElement>(null),
    user: useRef<HTMLButtonElement>(null),
    settings: useRef<HTMLButtonElement>(null)
  };

  // 스탁이지 메인 페이지로 이동하는 함수
  const goToHomePage = () => router.push('/');
  const goToRSRankPage = () => router.push('/rs-rank');
  const goToETFSectorPage = () => router.push('/etf-sector'); // ETF/섹터 페이지 이동 함수 추가
  const goToDocEasy = () => window.open('http://localhost:3010', '_blank');

  // 버튼 위치에 따라 툴팁 위치 계산
  useEffect(() => {
    const positions: { [key: string]: number } = {};
    
    Object.entries(buttonRefs).forEach(([key, ref]) => {
      if (ref.current) {
        const rect = ref.current.getBoundingClientRect();
        positions[key] = rect.top;
      }
    });
    
    setTooltipPosition(positions);
  }, []);

  return (
    <div className="w-[59px] border-r bg-gray-200 flex flex-col h-full relative">
      <div className="flex-1 overflow-hidden">
        <div className="pt-4">
          <div className="w-full flex flex-col items-center">
            {/* 툴팁을 사이드바 외부에 표시하기 위한 컨테이너 */}
            <div className="sidebar-tooltips-container">
              {hoveredButton && tooltipPosition[hoveredButton] && (
                <span 
                  className="sidebar-tooltip" 
                  style={{ top: `${tooltipPosition[hoveredButton] - 10}px` }}
                >
                  {hoveredButton === 'home' && '스탁이지'}
                  {hoveredButton === 'chart' && 'RS순위'}
                  {hoveredButton === 'etfSector' && 'ETF/섹터'} {/* ETF/섹터 툴팁 추가 */}
                  {hoveredButton === 'doc' && '닥이지'}
                  {hoveredButton === 'user' && '마이페이지'}
                  {hoveredButton === 'settings' && '설정'}
                </span>
              )}
            </div>
            
            {/* 홈 버튼 - 스탁이지 메인 페이지로 이동 */}
            <div className="sidebar-button-container">
              <button 
                ref={buttonRefs.home}
                className="sidebar-button" 
                onClick={goToHomePage} 
                onMouseEnter={() => setHoveredButton('home')}
                onMouseLeave={() => setHoveredButton(null)}
              >
                <Home className="icon" />
              </button>
            </div>
            
            {/* 차트 버튼 - RS순위 페이지로 이동 */}
            <div className="sidebar-button-container">
              <button 
                ref={buttonRefs.chart}
                className="sidebar-button" 
                onClick={goToRSRankPage}
                onMouseEnter={() => setHoveredButton('chart')}
                onMouseLeave={() => setHoveredButton(null)}
              >
                <ChartColumn className="icon" />
              </button>
            </div>
            
            {/* ETF/섹터 버튼 추가 */}
            <div className="sidebar-button-container">
              <button 
                ref={buttonRefs.etfSector}
                className="sidebar-button" 
                onClick={goToETFSectorPage} // ETF/섹터 페이지로 이동하는 함수 연결
                onMouseEnter={() => setHoveredButton('etfSector')}
                onMouseLeave={() => setHoveredButton(null)}
              >
                <PieChart className="icon" />
              </button>
            </div>
            
            {/* 문서 버튼 - DocEasy로 이동 */}
            <div className="sidebar-button-container">
              <button 
                ref={buttonRefs.doc}
                className="sidebar-button" 
                onClick={goToDocEasy} 
                onMouseEnter={() => setHoveredButton('doc')}
                onMouseLeave={() => setHoveredButton(null)}
              >
                <FileStack className="icon" />
              </button>
            </div>
          </div>
        </div>
      </div>
      
      {/* 하단 영역 - 마이페이지와 설정 버튼을 맨 아래로 이동 */}
      <div className="mt-auto pb-4">
        <div className="w-full flex flex-col items-center">
          {/* 사용자 버튼 */}
          <div className="sidebar-button-container">
            <button 
              ref={buttonRefs.user}
              className="sidebar-button" 
              onMouseEnter={() => setHoveredButton('user')}
              onMouseLeave={() => setHoveredButton(null)}
            >
              <User className="icon" />
            </button>
          </div>
          
          {/* 설정 버튼 */}
          <div className="sidebar-button-container">
            <button 
              ref={buttonRefs.settings}
              className="sidebar-button" 
              onMouseEnter={() => setHoveredButton('settings')}
              onMouseLeave={() => setHoveredButton(null)}
            >
              <Settings className="icon" />
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

// 메인 컴포넌트
export default function Sidebar() {
  return (
    <Suspense fallback={<div className="w-[59px] bg-background border-r animate-pulse fixed top-0 left-0 h-screen z-50">
      <div className="p-4">
        <div className="h-6 bg-gray-200 rounded w-3/4"></div>
      </div>
      <div className="p-2">
        <div className="space-y-2">
          <div className="h-4 bg-gray-200 rounded w-1/2"></div>
          <div className="h-4 bg-gray-200 rounded w-2/3"></div>
        </div>
      </div>
    </div>}>
      <div className="fixed top-0 left-0 h-screen z-50">
        <SidebarContent />
      </div>
    </Suspense>
  )
}
