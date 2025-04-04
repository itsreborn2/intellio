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

// 컨텐츠 컴포넌트
// 히스토리 아이템 타입 정의
interface HistoryItem {
  id: string;
  stockName: string; // 종목명
  stockCode?: string; // 종목코드 (선택적)
  prompt: string; // 입력한 프롬프트
  timestamp: number; // 저장 시간
  userId?: string; // 사용자 ID
  responseId?: string; // 분석 결과의 고유 ID
}

function SidebarContent() {
  const router = useRouter();
  // 호버 상태를 관리하는 state
  const [hoveredButton, setHoveredButton] = useState<string | null>(null);
  const [tooltipPosition, setTooltipPosition] = useState<{ [key: string]: number }>({});
  const [isMenuOpen, setIsMenuOpen] = useState(false); // 모바일 메뉴 상태 추가
  const [isMobile, setIsMobile] = useState(false); // 모바일 감지 상태 추가
  const [isHistoryPanelOpen, setIsHistoryPanelOpen] = useState(false); // 검색 히스토리 패널 상태
  const [historyItems, setHistoryItems] = useState<HistoryItem[]>([]); // 히스토리 아이템
  const [isLoading, setIsLoading] = useState(false); // 로딩 상태
  const [isLoadingAnalysis, setIsLoadingAnalysis] = useState(false); // 분석 결과 로딩 상태
  const [userId, setUserId] = useState<string | null>(null); // 사용자 ID
  
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
    setIsHistoryPanelOpen(newIsOpen);
    if (isMobile) setIsMenuOpen(false); // 모바일에서 패널 열 때 메뉴 닫기
    
    // 패널이 열릴 때 서버에서 사용자의 히스토리 가져오기
    if (newIsOpen) {
      fetchUserHistory();
    }
  };
  
  // 히스토리 패널 닫기 함수
  const closeHistoryPanel = () => {
    if (isHistoryPanelOpen) {
      setIsHistoryPanelOpen(false);
    }
  };
  
  // 히스토리 패널 영역 클릭 이벤트 핸들러 (이벤트 전파 중단)
  const handleHistoryPanelClick = (e: React.MouseEvent) => {
    e.stopPropagation(); // 이벤트 전파 중단하여 패널 내부 클릭 시 패널이 닫히지 않도록 함
  };
  
  // 사용자 히스토리 가져오기
  const fetchUserHistory = async () => {
    if (!userId) return;
    
    setIsLoading(true);
    try {
      const response = await axios.get(`/api/user-history?userId=${userId}`);
      if (response.data && Array.isArray(response.data.history)) {
        setHistoryItems(response.data.history);
      }
    } catch (error) {
      console.error('사용자 히스토리 가져오기 오류:', error);
    } finally {
      setIsLoading(false);
    }
  };
  
  // 히스토리 아이템 추가 함수
  const addHistoryItem = (stockName: string, stockCode: string | undefined, prompt: string) => {
    if (!userId) return;
    
    const newItem: HistoryItem = {
      id: Date.now().toString(),
      stockName,
      stockCode,
      prompt,
      timestamp: Date.now(),
      userId
    };
    
    // 새 아이템을 배열 맨 앞에 추가 (최신 항목이 맨 위에 표시)
    setHistoryItems(prev => [newItem, ...prev.slice(0, 19)]); // 최대 20개 항목 유지
    
    // 서버에 히스토리 저장
    saveHistoryToServer(newItem);
  };
  
  // 서버에 히스토리 저장
  const saveHistoryToServer = async (item: HistoryItem) => {
    try {
      await axios.post('/api/user-history', item);
    } catch (error) {
      console.error('히스토리 저장 오류:', error);
    }
  };
  
  // 히스토리 분석 결과 불러오기
  const loadHistoryAnalysis = async (item: HistoryItem) => {
    if (!item.responseId) {
      console.error('분석 결과 ID가 없습니다');
      return;
    }
    
    setIsLoadingAnalysis(true);
    try {
      // 분석 결과 불러오기 API 호출
      const response = await axios.get(`/api/analysis-result?responseId=${item.responseId}`);
      
      if (response.data && response.data.result) {
        // 분석 결과를 AIChatArea 컴포넌트에 전달하기 위한 이벤트 발생
        const event = new CustomEvent('loadHistoryAnalysis', {
          detail: {
            stockName: item.stockName,
            stockCode: item.stockCode,
            prompt: item.prompt,
            result: response.data.result,
            responseId: item.responseId
          }
        });
        window.dispatchEvent(event);
        
        // 모바일 환경에서는 히스토리 패널 닫기
        if (isMobile) {
          setIsHistoryPanelOpen(false);
        }
      }
    } catch (error) {
      console.error('분석 결과 불러오기 오류:', error);
    } finally {
      setIsLoadingAnalysis(false);
    }
  };
  
  // 사용자 ID 가져오기
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
  
  // 사용자 ID가 있을 때 히스토리 가져오기
  useEffect(() => {
    if (userId && isHistoryPanelOpen) {
      fetchUserHistory();
    }
  }, [userId, isHistoryPanelOpen]);
  
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
  
  // 히스토리 패널 외부 클릭 시 패널 닫기 구현
  useEffect(() => {
    // 전역 클릭 이벤트 리스너 등록
    const handleDocumentClick = (e: MouseEvent) => {
      // 히스토리 패널이 열려 있을 때만 처리
      if (isHistoryPanelOpen) {
        closeHistoryPanel();
      }
    };
    
    document.addEventListener('click', handleDocumentClick);
    
    return () => {
      document.removeEventListener('click', handleDocumentClick);
    };
  }, [isHistoryPanelOpen]); // isHistoryPanelOpen이 변경될 때마다 이벤트 리스너 재설정
  
  // 전역 이벤트 리스너 설정 - 종목 선택 및 프롬프트 입력 감지
  useEffect(() => {
    // 커스텀 이벤트 리스너 추가
    const handleStockPrompt = (e: CustomEvent) => {
      const { stockName, stockCode, prompt, responseId } = e.detail;
      if (stockName && prompt) {
        addHistoryItem(stockName, stockCode, prompt);
      }
    };
    
    // 이벤트 리스너 등록
    window.addEventListener('stockPromptSubmitted', handleStockPrompt as EventListener);
    
    // 컴포넌트 언마운트 시 이벤트 리스너 제거
    return () => {
      window.removeEventListener('stockPromptSubmitted', handleStockPrompt as EventListener);
    };
  }, [userId]); // userId가 변경될 때마다 이벤트 리스너 재설정
  
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
      
      {/* 사이드바 컨텐츠 */}
      <div className={`w-[59px] border-r bg-gray-200 flex flex-col h-full relative sidebar ${isMenuOpen ? 'open' : ''}`}>
        
        {/* 검색 히스토리 패널 - 애니메이션 개선 */}
        <div 
          className={`fixed left-[59px] top-0 h-full overflow-hidden`}
          style={{ 
            height: '100vh',
            width: isHistoryPanelOpen ? '280px' : '0',
            transform: isHistoryPanelOpen ? 'translateX(0)' : 'translateX(-30px)',
            opacity: isHistoryPanelOpen ? 1 : 0,
            transition: isHistoryPanelOpen 
              ? 'width 0.35s cubic-bezier(0.25, 1, 0.5, 1), transform 0.35s cubic-bezier(0.25, 1, 0.5, 1), opacity 0.25s ease-in-out' 
              : 'width 0.4s cubic-bezier(0.4, 0, 0.2, 1), transform 0.4s cubic-bezier(0.4, 0, 0.2, 1), opacity 0.3s ease-in-out',
            pointerEvents: isHistoryPanelOpen ? 'auto' : 'none',
            transformOrigin: 'left center',
            boxShadow: isHistoryPanelOpen ? '4px 0 12px rgba(0, 0, 0, 0.2)' : 'none',
            zIndex: 20, // 항상 높은 z-index를 유지하여 애니메이션이 완료될 때까지 보이게 함
            clipPath: isHistoryPanelOpen ? 'inset(0 0 0 0)' : 'inset(0 0 0 100%)', // 열리고 닫힐 때 클립 효과 추가
            visibility: isHistoryPanelOpen ? 'visible' : 'hidden', // 애니메이션 완료 후 숨김
            backgroundColor: '#282A2E', // 사이드바와 동일한 배경색
            borderRight: '1px solid #1e2022' // 사이드바와 동일한 테두리 색상
          }}
          onClick={(e) => e.stopPropagation()} // 패널 내부 클릭 시 이벤트 전파 중단하여 패널이 닫히지 않도록 함
        >
          <div className="flex flex-col h-full">
            {/* 헤더 영역 - 애니메이션 추가 */}
            <div 
              className="flex items-center justify-between p-3 border-b border-[#1e2022]"
              style={{
                opacity: isHistoryPanelOpen ? 1 : 0,
                transform: isHistoryPanelOpen ? 'translateX(0)' : 'translateX(-10px)',
                transition: isHistoryPanelOpen
                  ? 'opacity 0.3s ease-out 0.1s, transform 0.3s ease-out 0.1s'
                  : 'opacity 0.25s ease-in, transform 0.25s ease-in'
              }}
            >
              <div className="flex items-center justify-between w-full">
                <div className="flex items-center">
                  <Clock className="w-4 h-4 mr-2 text-[#ececf1]" />
                  <h3 className="text-sm font-medium text-[#ececf1]">최근 검색 히스토리</h3>
                </div>
                <button 
                  className="p-1 rounded-full hover:bg-[#3e4044]"
                  onClick={toggleHistoryPanel}
                >
                  <X className="w-4 h-4 text-[#ececf1]" />
                </button>
              </div>
            </div>
            
            {/* 콘텐츠 영역 - 애니메이션 추가 */}
            <div 
              className="flex-1 overflow-y-auto p-2 text-[#ececf1]"
              style={{
                opacity: isHistoryPanelOpen ? 1 : 0,
                transform: isHistoryPanelOpen ? 'translateX(0)' : 'translateX(-15px)',
                transition: isHistoryPanelOpen
                  ? 'opacity 0.3s ease-out 0.15s, transform 0.3s ease-out 0.15s'
                  : 'opacity 0.2s ease-in, transform 0.2s ease-in'
              }}
            >
              {isLoading ? (
                <div className="flex flex-col items-center justify-center h-full text-[#ececf1] text-sm">
                  <Loader2 className="w-8 h-8 mb-2 animate-spin" />
                  <p>히스토리 불러오는 중...</p>
                </div>
              ) : historyItems.length > 0 ? (
                <div className="space-y-2">
                  {historyItems.map((item) => (
                    <div 
                      key={item.id} 
                      className="p-2 rounded border border-[#1e2022] hover:bg-[#3e4044] cursor-pointer transition-colors"
                      onClick={() => item.responseId ? loadHistoryAnalysis(item) : null}
                    >
                      <div className="flex items-center justify-between mb-1">
                        <div className="flex items-center">
                          <span className="text-xs font-semibold text-[#ececf1]">{item.stockName}</span>
                          {item.stockCode && (
                            <span className="text-xs text-[#a0a0a0] ml-1">({item.stockCode})</span>
                          )}
                        </div>
                        <span className="text-[10px] text-[#a0a0a0]">
                          {new Date(item.timestamp).toLocaleDateString()}
                        </span>
                      </div>
                      <p className="text-xs text-[#ececf1] line-clamp-2 break-all">{item.prompt}</p>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="flex flex-col items-center justify-center h-full text-[#ececf1] text-sm">
                  <Clock className="w-8 h-8 mb-2 opacity-50 text-[#ececf1]" />
                  <p>아직 저장된 히스토리가 없습니다</p>
                </div>
              )}
            </div>
          </div>
        </div>
        
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
