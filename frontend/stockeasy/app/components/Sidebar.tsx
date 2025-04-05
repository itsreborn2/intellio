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
  History, // 검색 히스토리 아이콘
  ChevronRight, // 패널 닫기 아이콘
  Clock, // 히스토리 아이콘
  Loader2, // 로딩 아이콘
} from 'lucide-react';
import axios from 'axios';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import StockChatHistory from './StockChatHistory';

// 컨텐츠 컴포넌트
function SidebarContent() {
  const router = useRouter();
  // 호버 상태를 관리하는 state
  const [hoveredButton, setHoveredButton] = useState<string | null>(null);
  const [tooltipPosition, setTooltipPosition] = useState<{ [key: string]: number }>({});
  const [isMenuOpen, setIsMenuOpen] = useState(false); // 모바일 메뉴 상태 추가
  const [isMobile, setIsMobile] = useState(false); // 모바일 감지 상태 추가
  const [isHistoryPanelOpen, setIsHistoryPanelOpen] = useState(false); // 검색 히스토리 패널 상태
  
  // 버튼 참조 객체
  const buttonRefs = {
    home: useRef<HTMLButtonElement>(null),
    analyst: useRef<HTMLButtonElement>(null), // AI 애널리스트 버튼 참조 추가
    chart: useRef<HTMLButtonElement>(null),
    etfSector: useRef<HTMLButtonElement>(null), // ETF/섹터 버튼 참조 추가
    value: useRef<HTMLButtonElement>(null), // 벨류에이션 버튼 참조 추가
    history: useRef<HTMLButtonElement>(null), // 검색 히스토리 버튼 참조 추가
    doc: useRef<HTMLButtonElement>(null),
    user: useRef<HTMLButtonElement>(null),
    settings: useRef<HTMLButtonElement>(null)
  };

  // 환경 변수를 사용하여 URL 설정
  const stockEasyUrl = process.env.NEXT_PUBLIC_STOCKEASY_URL || 'https://stockeasy.intellio.kr';
  const docEasyUrl = process.env.NEXT_PUBLIC_DOCEASY_URL || 'https://doceasy.intellio.kr';
  
  // 페이지 이동 함수
  const goToHomePage = () => {
    // 현재 경로가 홈페이지(루트)인 경우
    if (window.location.pathname === '/') {
      // 홈버튼 클릭 이벤트 발생 (채팅 영역 초기화용)
      const event = new CustomEvent('homeButtonClick');
      window.dispatchEvent(event);
      
      // 클라이언트 측 네비게이션 사용 (새로고침 대신)
      router.refresh();
    } else {
      // 클라이언트 측 네비게이션 사용
      router.push('/', { scroll: false });
    }
    if (isMobile) setIsMenuOpen(false); // 모바일에서 페이지 이동 시 메뉴 닫기
  };
  
  // AI 애널리스트 페이지로 이동하는 함수 추가
  const goToAnalystPage = () => {
    // 이미 애널리스트 페이지에 있는 경우 아무 작업도 수행하지 않음
    if (window.location.pathname === '/analyst') return;
    
    // prefetch: true 옵션을 사용하여 클라이언트 측 네비게이션 활성화
    router.push('/analyst', { scroll: false });
    if (isMobile) setIsMenuOpen(false); // 모바일에서 페이지 이동 시 메뉴 닫기
  };
  
  const goToRSRankPage = () => {
    // 이미 RS랭크 페이지에 있는 경우 아무 작업도 수행하지 않음
    if (window.location.pathname === '/rs-rank') return;
    
    // prefetch: true 옵션을 사용하여 클라이언트 측 네비게이션 활성화
    router.push('/rs-rank', { scroll: false });
    if (isMobile) setIsMenuOpen(false); // 모바일에서 페이지 이동 시 메뉴 닫기
  };
  
  const goToETFSectorPage = () => {
    // 이미 ETF/섹터 페이지에 있는 경우 아무 작업도 수행하지 않음
    if (window.location.pathname === '/etf-sector') return;
    
    // prefetch: true 옵션을 사용하여 클라이언트 측 네비게이션 활성화
    router.push('/etf-sector', { scroll: false });
    if (isMobile) setIsMenuOpen(false); // 모바일에서 페이지 이동 시 메뉴 닫기
  };
  
  const goToValuePage = () => {
    // 이미 벨류에이션 페이지에 있는 경우 아무 작업도 수행하지 않음
    if (window.location.pathname === '/value') return;
    
    // prefetch: true 옵션을 사용하여 클라이언트 측 네비게이션 활성화
    router.push('/value', { scroll: false });
    if (isMobile) setIsMenuOpen(false); // 모바일에서 페이지 이동 시 메뉴 닫기
  };
  
  // 검색 히스토리 패널 토글 함수
  const toggleHistoryPanel = () => {
    const newIsOpen = !isHistoryPanelOpen;
    console.log('[사이드바] 히스토리 패널 토글:', newIsOpen);
    setIsHistoryPanelOpen(newIsOpen);
    if (isMobile) setIsMenuOpen(false); // 모바일에서 패널 열 때 메뉴 닫기
  };
  
  // 트렌드 페이지로 이동하는 함수 추가
  const goToTrendPage = () => {
    // 이미 트렌드 페이지에 있는 경우 아무 작업도 수행하지 않음
    if (window.location.pathname === '/trend') return;
    
    // prefetch: true 옵션을 사용하여 클라이언트 측 네비게이션 활성화
    router.push('/trend', { scroll: false });
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
      //console.log('툴팁 위치 업데이트됨:', positions);
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
  
  // 히스토리 패널 외부 클릭 시 패널 닫기 구현
  useEffect(() => {
    // 전역 클릭 이벤트 리스너 등록
    const handleDocumentClick = (e: MouseEvent) => {
      // 히스토리 패널이 열려 있을 때만 처리
      if (isHistoryPanelOpen) {
        console.log('[사이드바] 외부 클릭으로 히스토리 패널 닫기');
        setIsHistoryPanelOpen(false);
      }
    };
    
    document.addEventListener('click', handleDocumentClick);
    
    return () => {
      document.removeEventListener('click', handleDocumentClick);
    };
  }, [isHistoryPanelOpen]); // isHistoryPanelOpen이 변경될 때마다 이벤트 리스너 재설정
  
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
          {hoveredButton === 'history' && '검색 히스토리'} {/* 검색 히스토리 툴팁 추가 */}
          {hoveredButton === 'doc' && '닥이지'}
          {hoveredButton === 'user' && '마이페이지'}
          {hoveredButton === 'settings' && '설정'}
        </div>
      )}
      
      {/* StockChatHistory 컴포넌트 사용 */}
      <StockChatHistory 
        isHistoryPanelOpen={isHistoryPanelOpen}
        toggleHistoryPanel={toggleHistoryPanel}
        isMobile={isMobile}
      />
      
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
              
              {/* 검색 히스토리 버튼 추가 */}
              <div className="sidebar-button-container">
                <button 
                  ref={buttonRefs.history}
                  className={`sidebar-button ${isHistoryPanelOpen ? 'bg-gray-700' : ''}`} 
                  onClick={toggleHistoryPanel} // 검색 히스토리 패널 토글 함수 연결
                  onMouseEnter={() => handleMouseEnter('history')}
                  onMouseLeave={handleMouseLeave}
                >
                  <History className="icon" />
                  {/* 모바일 환경에서는 아이콘 옆에 텍스트 표시 */}
                  {isMobile && <span className="ml-2 text-sm text-[#ececf1]">검색 히스토리</span>}
                </button>
              </div>
            </div>
          </div>
        </div>
        
        {/* 하단 영역 - 마이페이지와 설정 버튼을 맨 아래로 이동 */}
        <div className="mt-auto pb-4">
          <div className="w-full flex flex-col items-center">
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
