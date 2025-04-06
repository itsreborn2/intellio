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
import StockChatHistory from './StockChatHistory'; // StockChatHistory 컴포넌트 import

// 컨텐츠 컴포넌트
function SidebarContent() {
  const router = useRouter();
  // 호버 상태를 관리하는 state
  const [hoveredButton, setHoveredButton] = useState<string | null>(null);
  const [tooltipPosition, setTooltipPosition] = useState<{ [key: string]: number }>({});
  const [isMenuOpen, setIsMenuOpen] = useState(false); // 모바일 메뉴 상태 추가
  const [isMobile, setIsMobile] = useState(false); // 모바일 감지 상태 추가
  const [isHistoryPanelOpen, setIsHistoryPanelOpen] = useState(false); // 검색 히스토리 패널 상태
  const [userId, setUserId] = useState<string | null>(null); // 사용자 ID 추가
  const [showHistoryButton, setShowHistoryButton] = useState(false); // 검색 히스토리 버튼 표시 여부 상태 추가
  
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

  // Ref 정의
  const sidebarRef = useRef<HTMLDivElement>(null); // 사이드바 컨테이너 Ref
  const menuButtonRef = useRef<HTMLButtonElement>(null); // 모바일 메뉴 버튼 Ref

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
    setIsHistoryPanelOpen(newIsOpen);
  };
  
  // 트렌드 페이지로 이동하는 함수 추가 (원본 코드에 있었으므로 복원)
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

  // 버튼 위치에 따라 툴팁 위치 계산 (원본 코드 복원)
  useEffect(() => {
    const updateTooltipPositions = () => {
      const positions: { [key: string]: number } = {};

      Object.entries(buttonRefs).forEach(([key, ref]) => {
        // ref.current가 null이 아니고, history 버튼의 경우 showHistoryButton이 true일 때만 위치 계산
        if (ref.current && (key !== 'history' || showHistoryButton)) {
          const rect = ref.current.getBoundingClientRect();
          positions[key] = rect.top;
        }
      });

      setTooltipPosition(positions);
    };

    // 초기 실행 및 의존성 변경 시 실행
    updateTooltipPositions();

    // resize 이벤트에 대한 핸들러 추가
    window.addEventListener('resize', updateTooltipPositions);

    // 컴포넌트 언마운트 시 이벤트 리스너 제거
    return () => {
      window.removeEventListener('resize', updateTooltipPositions);
    };
  }, [showHistoryButton]); // showHistoryButton을 의존성 배열에 추가

  // 호버 이벤트 핸들러 (원본 코드 복원)
  const handleMouseEnter = (key: string) => {
    if (!isMobile) {
      setHoveredButton(key);
    }
  };

  const handleMouseLeave = () => {
    if (!isMobile) {
      setHoveredButton(null);
    }
  };

  // 모바일 환경 감지 (원본 코드 복원)
  useEffect(() => {
    const checkIfMobile = () => {
      const isMobileView = window.innerWidth <= 768; // 768px 이하를 모바일로 간주
      setIsMobile(isMobileView);
      
      // 모바일에서 데스크탑으로 변경 시 메뉴가 열려있다면 닫기
      if (!isMobileView && isMenuOpen) {
        setIsMenuOpen(false);
      }
    };
    
    // 초기 실행
    checkIfMobile();
    
    // 화면 크기 변경 시 감지
    window.addEventListener('resize', checkIfMobile);
    
    // 컴포넌트 언마운트 시 이벤트 리스너 제거
    return () => {
      window.removeEventListener('resize', checkIfMobile);
    };
  }, [isMenuOpen]);

  // 사용자 ID 가져오기 (원본 코드 복원)
  useEffect(() => {
    // 로컬 스토리지에서 사용자 ID 가져오기
    const storedUserId = localStorage.getItem('userId');
    if (storedUserId) {
      setUserId(storedUserId);
    } else {
      // 새 사용자 ID 생성 (실제로는 로그인 시스템에서 가져와야 함)
      const newUserId = `user_${Date.now()}`;
      localStorage.setItem('userId', newUserId);
      setUserId(newUserId);
    }
  }, []);
  
  // 초기 로드 시 현재 페이지가 AIChatArea인지 확인 (원본 코드 복원)
  useEffect(() => {
    // 현재 페이지가 홈페이지('/')인지 확인
    const isHomePage = window.location.pathname === '/';
    
    // 홈페이지인 경우 AIChatArea가 로드되어 있으므로 검색 히스토리 버튼 표시
    setShowHistoryButton(isHomePage);
  }, []);
  
  // AIChatArea 컴포넌트의 마운트/언마운트 이벤트 감지 (원본 코드 복원)
  useEffect(() => {
    // AIChatArea 컴포넌트 마운트 이벤트 리스너
    const handleAIChatAreaMounted = (e: CustomEvent) => {
      // AIChatArea 컴포넌트가 마운트되면 검색 히스토리 버튼 표시
      setShowHistoryButton(true);
    };
    
    // AIChatArea 컴포넌트 언마운트 이벤트 리스너
    const handleAIChatAreaUnmounted = (e: CustomEvent) => {
      // AIChatArea 컴포넌트가 언마운트되면 검색 히스토리 버튼 숨김
      setShowHistoryButton(false);
      // 히스토리 패널이 열려있다면 닫기
      if (isHistoryPanelOpen) {
        setIsHistoryPanelOpen(false);
      }
    };
    
    // 이벤트 리스너 등록
    window.addEventListener('aiChatAreaMounted', handleAIChatAreaMounted as EventListener);
    window.addEventListener('aiChatAreaUnmounted', handleAIChatAreaUnmounted as EventListener);
    
    // 컴포넌트 언마운트 시 이벤트 리스너 제거
    return () => {
      window.removeEventListener('aiChatAreaMounted', handleAIChatAreaMounted as EventListener);
      window.removeEventListener('aiChatAreaUnmounted', handleAIChatAreaUnmounted as EventListener);
    };
  }, [isHistoryPanelOpen]); // 히스토리 패널 상태 의존성 추가
  
  // 모바일 메뉴 토글 함수 (단순화: 히스토리 패널 열려있을 땐 호출 안 됨)
  const toggleMenu = () => {
    setIsMenuOpen(!isMenuOpen); // 메인 메뉴 상태만 토글
  };
  
  // 모바일 메뉴 닫기 함수 (오버레이 클릭 시)
  const closeMenu = () => {
    setIsMenuOpen(false);
    
    // 사이드바 닫힘 이벤트 발생 (필요시 사용)
    // const event = new CustomEvent('sidebarToggle', { detail: { isOpen: false } });
    // window.dispatchEvent(event);
  };

  // 모바일 사이드바 외부 클릭 시 닫기 로직
  useEffect(() => {
    // 모바일 환경이고 메뉴가 열려 있을 때만 실행
    if (isMobile && isMenuOpen) {
      const handleDocumentClick = (e: MouseEvent) => {
        // 클릭된 요소가 사이드바 내부 또는 메뉴 버튼이 아닐 경우 메뉴 닫기
        if (
          sidebarRef.current && 
          !sidebarRef.current.contains(e.target as Node) &&
          menuButtonRef.current &&
          !menuButtonRef.current.contains(e.target as Node)
        ) {
          setIsMenuOpen(false);
        }
      };

      // 이벤트 리스너 등록 (약간의 지연 후)
      const timerId = setTimeout(() => {
        document.addEventListener('click', handleDocumentClick);
      }, 0);

      // 클린업 함수
      return () => {
        clearTimeout(timerId);
        document.removeEventListener('click', handleDocumentClick);
      };
    }
  }, [isMobile, isMenuOpen]); // isMobile과 isMenuOpen 상태 변경 시 실행
  
  // 히스토리 패널 외부 클릭 시 패널 닫기 구현 (원본 코드 기반 복원)
  useEffect(() => {
    // 전역 클릭 이벤트 리스너 등록
    const handleDocumentClick = (e: MouseEvent) => {
      // 히스토리 패널이 열려 있을 때만 처리
      if (isHistoryPanelOpen) {
        // stopPropagation으로 인해 패널 내부 클릭은 여기까지 오지 않음
        // 따라서 별도 조건 없이 바로 패널을 닫으면 됨
        setIsHistoryPanelOpen(false);
      }
    };
    
    // isHistoryPanelOpen이 true일 때만 리스너 추가
    if (isHistoryPanelOpen) {
      // 약간의 지연 후 리스너 추가 (패널 열기 버튼 클릭과 겹치지 않도록)
      const timerId = setTimeout(() => {
        document.addEventListener('click', handleDocumentClick);
      }, 0);
      
      // 클린업 함수: 타이머 해제 및 리스너 제거
      return () => {
        clearTimeout(timerId);
        document.removeEventListener('click', handleDocumentClick);
      };
    } else {
      // isHistoryPanelOpen이 false이면 리스너 즉시 제거 (만약 남아있다면)
      document.removeEventListener('click', handleDocumentClick);
    }

  }, [isHistoryPanelOpen]); // isHistoryPanelOpen 상태에 따라 리스너 추가/제거
  
  // 전역 이벤트 리스너 설정 - 종목 선택 및 프롬프트 입력 감지
  useEffect(() => {
    // 종목 선택 이벤트 리스너
    const handleStockSelected = (e: CustomEvent) => {
      // 종목 선택 이벤트 발생 시, 히스토리 패널이 열려있다면 닫기
      if (isHistoryPanelOpen) {
        setIsHistoryPanelOpen(false);
      }
    };
    
    // 프롬프트 입력 이벤트 리스너
    const handlePromptInput = (e: CustomEvent) => {
      // 프롬프트 입력 이벤트 발생 시, 히스토리 패널이 열려있다면 닫기
      if (isHistoryPanelOpen) {
        setIsHistoryPanelOpen(false);
      }
    };
    
    // 이벤트 리스너 등록
    window.addEventListener('stockSelected', handleStockSelected as EventListener);
    window.addEventListener('promptInput', handlePromptInput as EventListener);
    
    // 컴포넌트 언마운트 시 이벤트 리스너 제거
    return () => {
      window.removeEventListener('stockSelected', handleStockSelected as EventListener);
      window.removeEventListener('promptInput', handlePromptInput as EventListener);
    };
  }, [isHistoryPanelOpen]); // 히스토리 패널 상태 의존성 추가
  
  return (
    <>
      {/* 모바일 햄버거 메뉴 버튼 - 히스토리 패널 열려있지 않을 때만 표시 */}
      {isMobile && !isHistoryPanelOpen && (
        <button 
          ref={menuButtonRef} // Ref 연결
          className="mobile-menu-button" 
          onClick={toggleMenu}
          style={{ zIndex: 1200 }} 
        >
          {/* 메뉴 또는 히스토리 패널이 열려있으면 X 아이콘 표시 -> 메뉴만 열려있을 때 X 아이콘 */}
          {isMenuOpen ? <X size={24} /> : <Menu size={24} />}
        </button>
      )}
      
      {/* 모바일 오버레이 */}
      {/* {isMobile && isMenuOpen && (
        <div 
          className="fixed inset-0 bg-black bg-opacity-50 z-[9998]"
          onClick={closeMenu} 
        />
      )} */}

      {/* 데스크탑 환경에서 사용할 툴팁 */}
      {!isMobile && hoveredButton && (
        <div 
          className="fixed left-[63px] bg-[#111827] text-[#ececf1] py-0.5 px-2 rounded-[6px] text-xs shadow-md z-[2000] border border-gray-700 pointer-events-none"
          style={{ 
            top: tooltipPosition[hoveredButton] ? `${tooltipPosition[hoveredButton] + 10}px` : '0px',
            transition: 'opacity 0.2s',
            opacity: 1
          }}
        >
          {hoveredButton === 'home' && '스탁이지'}
          {hoveredButton === 'analyst' && 'AI 애널리스트'} 
          {hoveredButton === 'chart' && 'RS순위'}
          {hoveredButton === 'etfSector' && 'ETF/섹터'}
          {hoveredButton === 'value' && '벨류에이션'}
          {hoveredButton === 'history' && '검색 히스토리'} 
          {hoveredButton === 'doc' && '닥이지'}
          {hoveredButton === 'user' && '마이페이지'}
          {hoveredButton === 'settings' && '설정'}
        </div>
      )}

      {/* 검색 히스토리 패널 컴포넌트 렌더링 */}
      <StockChatHistory 
        isHistoryPanelOpen={isHistoryPanelOpen} 
        toggleHistoryPanel={toggleHistoryPanel} 
        isMobile={isMobile} 
        style={isMobile && isHistoryPanelOpen ? { left: 0 } : {}} // 모바일 히스토리 활성 시 left: 0 적용
      />
      
      {/* 사이드바 컨텐츠 - 모바일에서 히스토리 패널 열려있지 않을 때만 렌더링 */}
      {!(isMobile && isHistoryPanelOpen) && (
        <div 
          ref={sidebarRef} // Ref 연결
          className={`sidebar ${isMobile ? 'mobile' : 'desktop'} ${isMenuOpen ? 'open' : ''}`}
          style={{
            // ... 기존 스타일 유지 ...
          }}
        >
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
                
                {/* 검색 히스토리 버튼 - AIChatArea 컴포넌트가 마운트되었을 때만 표시 */}
                {showHistoryButton && (
                  <div className="sidebar-button-container">
                    <button 
                      ref={buttonRefs.history}
                      className={`sidebar-button ${isHistoryPanelOpen ? 'bg-gray-700' : ''}`} 
                      onClick={() => {
                        setIsHistoryPanelOpen(true); // 히스토리 패널 열기
                        // 모바일 환경에서는 히스토리 버튼 클릭 시 메뉴를 닫음
                        if (isMobile) {
                          setIsMenuOpen(false);
                        }
                      }} 
                      onMouseEnter={() => handleMouseEnter('history')}
                      onMouseLeave={handleMouseLeave}
                    >
                      <History className="icon" />
                      {/* 모바일 환경에서는 아이콘 옆에 텍스트 표시 */}
                      {isMobile && <span className="ml-2 text-sm text-[#ececf1]">검색 히스토리</span>}
                    </button>
                  </div>
                )}
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
      )}
    </>
  )
}

// 메인 컴포넌트
export default function Sidebar() {
  return (
    <Suspense fallback={<div className="w-[59px] bg-background border-r animate-pulse fixed top-0 left-0 h-screen z-[9999]">
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
      {/* z-index 적용하여 다른 요소 위에 표시 */}
      <div className="fixed top-0 left-0 h-screen z-[9999]"> 
        <SidebarContent />
      </div>
    </Suspense>
  )
}