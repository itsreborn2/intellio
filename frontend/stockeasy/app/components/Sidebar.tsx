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
  PieChart,
  LayoutDashboard,
  Menu, // 햄버거 메뉴 아이콘 추가
  X, // X 아이콘 추가 (닫기 버튼용)
  TrendingUp // 개별주 분석 아이콘 추가
} from 'lucide-react';
import { useRouter } from 'next/navigation';

// 컨텐츠 컴포넌트
function SidebarContent() {
  const router = useRouter();
  // 호버 상태를 관리하는 state
  const [hoveredButton, setHoveredButton] = useState<string | null>(null);
  const [tooltipPosition, setTooltipPosition] = useState<{ [key: string]: number }>({});
  const [isMenuOpen, setIsMenuOpen] = useState(false); // 모바일 메뉴 상태 추가
  const [isMobile, setIsMobile] = useState(false); // 모바일 감지 상태 추가
  
  // 버튼 참조 객체
  const buttonRefs = {
    home: useRef<HTMLButtonElement>(null),
    chart: useRef<HTMLButtonElement>(null),
    etfSector: useRef<HTMLButtonElement>(null), // ETF/섹터 버튼 참조 추가
    indiv: useRef<HTMLButtonElement>(null), // 개별주 분석 버튼 참조 추가
    doc: useRef<HTMLButtonElement>(null),
    user: useRef<HTMLButtonElement>(null),
    settings: useRef<HTMLButtonElement>(null)
  };

  // 환경 변수를 사용하여 URL 설정
  const stockEasyUrl = process.env.NEXT_PUBLIC_STOCKEASY_URL || 'https://stockeasy.intellio.kr';
  const docEasyUrl = process.env.NEXT_PUBLIC_DOCEASY_URL || 'https://doceasy.intellio.kr';
  
  // 페이지 이동 함수
  const goToHomePage = () => {
    router.push('/');
    if (isMobile) setIsMenuOpen(false); // 모바일에서 페이지 이동 시 메뉴 닫기
  };
  
  const goToRSRankPage = () => {
    router.push('/rs-rank');
    if (isMobile) setIsMenuOpen(false); // 모바일에서 페이지 이동 시 메뉴 닫기
  };
  
  const goToETFSectorPage = () => {
    router.push('/etf-sector');
    if (isMobile) setIsMenuOpen(false); // 모바일에서 페이지 이동 시 메뉴 닫기
  };
  
  const goToIndivPage = () => {
    router.push('/indiv');
    if (isMobile) setIsMenuOpen(false); // 모바일에서 페이지 이동 시 메뉴 닫기
  };
  
  const goToDocEasy = () => {
    window.open(docEasyUrl, '_blank');
    if (isMobile) setIsMenuOpen(false); // 모바일에서 페이지 이동 시 메뉴 닫기
  };

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
  
  // 모바일 환경 감지
  useEffect(() => {
    const checkIfMobile = () => {
      setIsMobile(window.innerWidth <= 768);
    };
    
    // 초기 실행
    checkIfMobile();
    
    // 화면 크기 변경 시 감지
    window.addEventListener('resize', checkIfMobile);
    
    // 컴포넌트 언마운트 시 이벤트 리스너 제거
    return () => {
      window.removeEventListener('resize', checkIfMobile);
    };
  }, []);
  
  // 모바일 메뉴 토글 함수
  const toggleMenu = () => {
    const newIsOpen = !isMenuOpen;
    setIsMenuOpen(newIsOpen);
    
    // 사이드바 상태 변경 이벤트 발생
    const event = new CustomEvent('sidebarToggle', { 
      detail: { isOpen: newIsOpen } 
    });
    window.dispatchEvent(event);
  };
  
  // 모바일 메뉴 닫기 함수
  const closeMenu = () => {
    setIsMenuOpen(false);
    
    // 사이드바 닫힘 이벤트 발생
    const event = new CustomEvent('sidebarToggle', { 
      detail: { isOpen: false } 
    });
    window.dispatchEvent(event);
  };

  return (
    <>
      {/* 모바일 햄버거 메뉴 버튼 */}
      {isMobile && (
        <button 
          className="mobile-menu-button" 
          onClick={toggleMenu}
          style={{ zIndex: 1200 }} // 사이드바보다 높은 z-index 설정
        >
          {isMenuOpen ? <X size={24} /> : <Menu size={24} />} {/* 사이드바 상태에 따라 아이콘 변경 */}
        </button>
      )}
      
      {/* 모바일 오버레이 (메뉴 열릴 때만 표시) */}
      {isMobile && (
        <div 
          className={`mobile-overlay ${isMenuOpen ? 'open' : ''}`} 
          onClick={closeMenu}
        />
      )}
      
      {/* 사이드바 컨텐츠 */}
      <div className={`w-[59px] border-r bg-gray-200 flex flex-col h-full relative sidebar ${isMenuOpen ? 'open' : ''}`}>
        
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
                    {hoveredButton === 'indiv' && '개별주 분석'} {/* 개별주 분석 툴팁 추가 */}
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
                  {/* 모바일 환경에서는 아이콘 옆에 텍스트 표시 */}
                  {isMobile && <span className="ml-2 text-sm">스탁이지</span>}
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
                  {/* 모바일 환경에서는 아이콘 옆에 텍스트 표시 */}
                  {isMobile && <span className="ml-2 text-sm">RS순위</span>}
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
                  {/* 모바일 환경에서는 아이콘 옆에 텍스트 표시 */}
                  {isMobile && <span className="ml-2 text-sm">ETF/섹터</span>}
                </button>
              </div>
              
              {/* 개별주 분석 버튼 추가 */}
              <div className="sidebar-button-container">
                <button 
                  ref={buttonRefs.indiv}
                  className="sidebar-button" 
                  onClick={goToIndivPage}
                  onMouseEnter={() => setHoveredButton('indiv')}
                  onMouseLeave={() => setHoveredButton(null)}
                >
                  <TrendingUp className="icon" />
                  {/* 모바일 환경에서는 아이콘 옆에 텍스트 표시 */}
                  {isMobile && <span className="ml-2 text-sm">개별주 분석</span>}
                </button>
              </div>
              
              {/* 닥이지 버튼 - 닥이지 사이트로 이동 */}
              <div className="sidebar-button-container">
                <button 
                  ref={buttonRefs.doc}
                  className="sidebar-button" 
                  onClick={goToDocEasy}
                  onMouseEnter={() => setHoveredButton('doc')}
                  onMouseLeave={() => setHoveredButton(null)}
                >
                  <FileText className="icon" />
                  {/* 모바일 환경에서는 아이콘 옆에 텍스트 표시 */}
                  {isMobile && <span className="ml-2 text-sm">닥이지</span>}
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
                {/* 모바일 환경에서는 아이콘 옆에 텍스트 표시 */}
                {isMobile && <span className="ml-2 text-sm">마이페이지</span>}
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
                {/* 모바일 환경에서는 아이콘 옆에 텍스트 표시 */}
                {isMobile && <span className="ml-2 text-sm">설정</span>}
              </button>
            </div>
          </div>
        </div>
      </div>
    </>
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
