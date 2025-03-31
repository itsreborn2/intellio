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
  Scale, // 벨류에이션 추가
  LineChart, // AI 애널리스트 추가
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
    analyst: useRef<HTMLButtonElement>(null), // AI 애널리스트 버튼 참조 추가
    chart: useRef<HTMLButtonElement>(null),
    etfSector: useRef<HTMLButtonElement>(null), // ETF/섹터 버튼 참조 추가
    value: useRef<HTMLButtonElement>(null), // 벨류에이션 버튼 참조 추가
    doc: useRef<HTMLButtonElement>(null),
    user: useRef<HTMLButtonElement>(null),
    settings: useRef<HTMLButtonElement>(null)
  };

  // 환경 변수를 사용하여 URL 설정
  const stockEasyUrl = process.env.NEXT_PUBLIC_STOCKEASY_URL || 'https://stockeasy.intellio.kr';
  const docEasyUrl = process.env.NEXT_PUBLIC_DOCEASY_URL || 'https://doceasy.intellio.kr';
  
  // 페이지 이동 함수
  const goToHomePage = () => {
    // 현재 경로가 홈페이지(루트)인 경우 페이지 새로고침 및 채팅 영역 초기화
    if (window.location.pathname === '/') {
      // 홈버튼 클릭 이벤트 발생 (채팅 영역 초기화용)
      const event = new CustomEvent('homeButtonClick');
      window.dispatchEvent(event);
      
      // 약간의 지연 후 페이지 새로고침 (이벤트가 처리될 시간 확보)
      setTimeout(() => {
        window.location.reload();
      }, 100);
    } else {
      router.push('/');
    }
    if (isMobile) setIsMenuOpen(false); // 모바일에서 페이지 이동 시 메뉴 닫기
  };
  
  // AI 애널리스트 페이지로 이동하는 함수 추가
  const goToAnalystPage = () => {
    router.push('/analyst');
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
  
  const goToValuePage = () => {
    router.push('/value');
    if (isMobile) setIsMenuOpen(false); // 모바일에서 페이지 이동 시 메뉴 닫기
  };
  
  const goToDocEasy = () => {
    window.open(docEasyUrl, '_blank');
    if (isMobile) setIsMenuOpen(false); // 모바일에서 페이지 이동 시 메뉴 닫기
  };

  // 버튼 위치에 따라 툴팁 위치 계산
  useEffect(() => {
    const updateTooltipPositions = () => {
      const positions: { [key: string]: number } = {};
      
      Object.entries(buttonRefs).forEach(([key, ref]) => {
        if (ref.current) {
          const rect = ref.current.getBoundingClientRect();
          positions[key] = rect.top;
        }
      });
      
      setTooltipPosition(positions);
      console.log('툴팁 위치 업데이트됨:', positions);
    };
    
    // 초기 실행
    updateTooltipPositions();
    
    // resize 이벤트에 대한 핸들러 추가
    window.addEventListener('resize', updateTooltipPositions);
    
    // 사이드바 상태 변경 이벤트에 대한 핸들러 추가
    window.addEventListener('sidebarToggle', updateTooltipPositions);
    
    // 컴포넌트 언마운트 시 이벤트 리스너 제거
    return () => {
      window.removeEventListener('resize', updateTooltipPositions);
      window.removeEventListener('sidebarToggle', updateTooltipPositions);
    };
  }, []);
  
  // 호버 이벤트 핸들러
  const handleMouseEnter = (key: string) => {
    if (!isMobile) {
      console.log('마우스 엔터:', key);
      setHoveredButton(key);
    }
  };

  const handleMouseLeave = () => {
    if (!isMobile) {
      console.log('마우스 리브');
      setHoveredButton(null);
    }
  };

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
      
      {/* 데스크탑 환경에서 사용할 툴팁 (모바일 환경과 완전히 분리) */}
      {!isMobile && hoveredButton && (
        <div 
          className="fixed left-[63px] bg-gray-100 text-gray-800 py-0.5 px-2 rounded-lg text-xs shadow-md z-[2000] border border-gray-200"
          style={{ 
            top: tooltipPosition[hoveredButton] ? `${tooltipPosition[hoveredButton] + 10}px` : '0px',
            transition: 'opacity 0.2s',
            opacity: 1
          }}
        >
          {hoveredButton === 'home' && '스탁이지'}
          {hoveredButton === 'analyst' && 'AI 애널리스트'} {/* AI 애널리스트 툴팁 추가 */}
          {hoveredButton === 'chart' && 'RS순위'}
          {hoveredButton === 'etfSector' && 'ETF/섹터'}
          {hoveredButton === 'value' && '벨류에이션'}
          {hoveredButton === 'doc' && '닥이지'}
          {hoveredButton === 'user' && '마이페이지'}
          {hoveredButton === 'settings' && '설정'}
        </div>
      )}
      
      {/* 사이드바 컨텐츠 */}
      <div className={`w-[59px] border-r bg-gray-200 flex flex-col h-full relative sidebar ${isMenuOpen ? 'open' : ''}`}>
        
        <div className="flex-1 overflow-hidden">
          <div className="pt-4">
            <div className="w-full flex flex-col items-center">
              
              {/* 홈 버튼 - 스탁이지 메인 페이지로 이동 */}
              <div className="sidebar-button-container">
                <button 
                  ref={buttonRefs.home}
                  className="sidebar-button" 
                  onClick={goToHomePage} 
                  onMouseEnter={() => handleMouseEnter('home')}
                  onMouseLeave={handleMouseLeave}
                >
                  <Home className="icon" />
                  {/* 모바일 환경에서는 아이콘 옆에 텍스트 표시 */}
                  {isMobile && <span className="ml-2 text-sm text-[#ececf1]">스탁이지</span>}
                </button>
              </div>
              
              {/* AI 애널리스트 버튼 추가 */}
              <div className="sidebar-button-container">
                <button 
                  ref={buttonRefs.analyst}
                  className="sidebar-button" 
                  onClick={goToAnalystPage}
                  onMouseEnter={() => handleMouseEnter('analyst')}
                  onMouseLeave={handleMouseLeave}
                >
                  <LineChart className="icon" />
                  {/* 모바일 환경에서는 아이콘 옆에 텍스트 표시 */}
                  {isMobile && <span className="ml-2 text-sm text-[#ececf1]">AI 애널리스트</span>}
                </button>
              </div>
              
              {/* 차트 버튼 - RS순위 페이지로 이동 */}
              <div className="sidebar-button-container">
                <button 
                  ref={buttonRefs.chart}
                  className="sidebar-button" 
                  onClick={goToRSRankPage}
                  onMouseEnter={() => handleMouseEnter('chart')}
                  onMouseLeave={handleMouseLeave}
                >
                  <ChartColumn className="icon" />
                  {/* 모바일 환경에서는 아이콘 옆에 텍스트 표시 */}
                  {isMobile && <span className="ml-2 text-sm text-[#ececf1]">RS순위</span>}
                </button>
              </div>
              
              {/* ETF/섹터 버튼 추가 */}
              <div className="sidebar-button-container">
                <button 
                  ref={buttonRefs.etfSector}
                  className="sidebar-button" 
                  onClick={goToETFSectorPage} // ETF/섹터 페이지로 이동하는 함수 연결
                  onMouseEnter={() => handleMouseEnter('etfSector')}
                  onMouseLeave={handleMouseLeave}
                >
                  <PieChart className="icon" />
                  {/* 모바일 환경에서는 아이콘 옆에 텍스트 표시 */}
                  {isMobile && <span className="ml-2 text-sm text-[#ececf1]">ETF/섹터</span>}
                </button>
              </div>
              
              {/* 벨류에이션 버튼 추가 */}
              <div className="sidebar-button-container">
                <button 
                  ref={buttonRefs.value}
                  className="sidebar-button" 
                  onClick={goToValuePage} // 벨류에이션 페이지로 이동하는 함수 연결
                  onMouseEnter={() => handleMouseEnter('value')}
                  onMouseLeave={handleMouseLeave}
                >
                  <Scale className="icon" />
                  {/* 모바일 환경에서는 아이콘 옆에 텍스트 표시 */}
                  {isMobile && <span className="ml-2 text-sm text-[#ececf1]">벨류에이션</span>}
                </button>
              </div>
              
              {/* 문서 버튼 - DocEasy로 이동 */}
              <div className="sidebar-button-container">
                <button 
                  ref={buttonRefs.doc}
                  className="sidebar-button" 
                  onClick={goToDocEasy} 
                  onMouseEnter={() => handleMouseEnter('doc')}
                  onMouseLeave={handleMouseLeave}
                >
                  <FileStack className="icon" />
                  {/* 모바일 환경에서는 아이콘 옆에 텍스트 표시 */}
                  {isMobile && <span className="ml-2 text-sm text-[#ececf1]">닥이지</span>}
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
                onMouseEnter={() => handleMouseEnter('user')}
                onMouseLeave={handleMouseLeave}
              >
                <User className="icon" />
                {/* 모바일 환경에서는 아이콘 옆에 텍스트 표시 */}
                {isMobile && <span className="ml-2 text-sm text-[#ececf1]">마이페이지</span>}
              </button>
            </div>
            
            {/* 설정 버튼 */}
            <div className="sidebar-button-container">
              <button 
                ref={buttonRefs.settings}
                className="sidebar-button" 
                onMouseEnter={() => handleMouseEnter('settings')}
                onMouseLeave={handleMouseLeave}
              >
                <Settings className="icon" />
                {/* 모바일 환경에서는 아이콘 옆에 텍스트 표시 */}
                {isMobile && <span className="ml-2 text-sm text-[#ececf1]">설정</span>}
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
