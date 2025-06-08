'use client'

import { Suspense, useState, useRef, useEffect } from 'react'
import { Button } from "intellio-common/components/ui/button"
import {
  Bot,
  BarChart,
  ChartColumn,
  FileStack,
  FileText,
  User,
  Users,
  Settings,
  PieChart,
  Info,
  LayoutDashboard,
  Menu, // 햄버거 메뉴 아이콘 추가
  X, // X 아이콘 추가 (닫기 버튼용)
  Scale, // 밸류에이션 추가
  LineChart, // AI 애널리스트 추가
  ChevronRight, // 패널 닫기 아이콘
  Loader2, // 로딩 아이콘
  LogOut, // 로그아웃 아이콘 추가
  User as UserIcon,
} from 'lucide-react';
import axios from 'axios';
import { useRouter } from 'next/navigation';
import Link from 'next/link';

import SettingsPopup from './SettingsPopup'; // SettingsPopup 컴포넌트 import
import LoginDialog from './LoginDialog'; // LoginDialog 컴포넌트 추가
import { logout } from '../utils/auth';
import { Avatar, AvatarImage, AvatarFallback } from "intellio-common/components/ui/avatar"
import { parseCookies } from 'nookies';

// 컨텐츠 컴포넌트
function SidebarContent() {
  const router = useRouter();
  // 호버 상태를 관리하는 state
  const [hoveredButton, setHoveredButton] = useState<string | null>(null);
  const [tooltipPosition, setTooltipPosition] = useState<{ [key: string]: number }>({});
  const [isMenuOpen, setIsMenuOpen] = useState(false); // 모바일 메뉴 상태 추가
  const [isMobile, setIsMobile] = useState(false); // 모바일 감지 상태 추가
  const [userId, setUserId] = useState<string | null>(null); // 사용자 ID 추가
  const [settingsMenuOpen, setSettingsMenuOpen] = useState(false); // 설정 메뉴 상태 추가
  const [showSettingsPopup, setShowSettingsPopup] = useState(false); // 설정 팝업 상태 추가
  const [isLoggedIn, setIsLoggedIn] = useState<boolean>(false);
  const [userName, setUserName] = useState('');
  const [userProfileImage, setUserProfileImage] = useState('');
  const [userEmail, setUserEmail] = useState('');
  const [userProvider, setUserProvider] = useState('');
  const [isLoginDialogOpen, setIsLoginDialogOpen] = useState(false);
  const [showLoginTooltip, setShowLoginTooltip] = useState(false); // 로그인 툴팁 상태 추가

  // 로그인 페이지로 리다이렉트하는 함수
  const redirectToLogin = () => {
    // 알림 표시
    alert('로그인이 필요한 서비스입니다.');
    
    // 로그인 페이지로 리다이렉트
    window.location.href = `${process.env.NEXT_PUBLIC_INTELLIO_URL}/login?redirectTo=stockeasy`;
  };

  // 버튼 참조 객체
  const buttonRefs = {
    home: useRef<HTMLButtonElement>(null),
    trendFollowing: useRef<HTMLButtonElement>(null), // 추세추종 버튼 참조 추가
    chart: useRef<HTMLButtonElement>(null),
    etfSector: useRef<HTMLButtonElement>(null), // ETF/섹터 버튼 참조 추가
    value: useRef<HTMLButtonElement>(null), // 밸류에이션 버튼 참조 추가
    about: useRef<HTMLButtonElement>(null), // About 버튼 참조 추가
    doc: useRef<HTMLButtonElement>(null),
    settings: useRef<HTMLDivElement>(null), // 설정 버튼(Avatar 컨테이너) 참조 추가
  };

  // 설정 메뉴 참조 객체
  const settingsMenuRef = useRef<HTMLDivElement>(null);

  // Ref 정의
  const sidebarRef = useRef<HTMLDivElement>(null); // 사이드바 컨테이너 Ref
  const menuButtonRef = useRef<HTMLButtonElement>(null); // 모바일 메뉴 버튼 Ref

  // 환경 변수를 사용하여 URL 설정
  const stockEasyUrl = process.env.NEXT_PUBLIC_STOCKEASY_URL || 'https://stockeasy.intellio.kr';
  const docEasyUrl = process.env.NEXT_PUBLIC_DOCEASY_URL || 'https://doceasy.intellio.kr';
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'https://api.intellio.kr';
  
  // 페이지 이동 함수
  const goToHomePage = () => {
    // 홈버튼 클릭 이벤트 발생 (채팅 영역 초기화용)
    console.log('홈버튼 클릭: 이벤트 발생시킴', new Date().toISOString());

    // 현재 경로가 공유 페이지인지 확인
    const isShareChatPage = window.location.pathname.includes('/share_chat');

    // 공유 페이지이고, 로그인되어 있지 않다면 로그인 페이지로 리다이렉트
    if (isShareChatPage && (!isLoggedIn || userId === 'anonymous')) {
      redirectToLogin();
      return; // 로그인 페이지로 리다이렉트 후 함수 종료
    }
    
    try {
      // 현재 경로가 홈페이지(루트)인 경우에만 이벤트 발생
      if (window.location.pathname === '/') {
        // 이벤트 정의 (사용자 정의 이벤트의 경우 bubbles: true 추가)
        const event = new CustomEvent('homeButtonClick', { 
          bubbles: true, 
          detail: { timestamp: Date.now() } 
        });
        window.dispatchEvent(event);
        console.log('homeButtonClick 이벤트 발생 완료');
        
        // 토글 버튼 숨김 이벤트 발생
        const hideToggleEvent = new CustomEvent('hideToggleButton', {
          bubbles: true
        });
        window.dispatchEvent(hideToggleEvent);

        // 같은 페이지에서 초기화를 위해 refresh 호출
        router.refresh();
      } else {
        // 다른 경로에서는 홈으로 이동
        // 히스토리 스택에 쌓이지 않도록 replace 옵션 사용
        router.replace('/', { scroll: false });
        
        // 토글 버튼 숨김 이벤트 발생
        const hideToggleEvent = new CustomEvent('hideToggleButton', {
          bubbles: true
        });
        window.dispatchEvent(hideToggleEvent);
      }
    } catch (error) {
      console.error('페이지 이동 중 오류:', error);
    }
    
    if (isMobile) setIsMenuOpen(false); // 모바일에서 페이지 이동 시 메뉴 닫기
  };
  
  // RS랭크 페이지로 이동하는 함수
  const goToRSRankPage = () => {
    // 이미 RS랭크 페이지에 있는 경우 아무 작업도 수행하지 않음
    if (window.location.pathname === '/rs-rank') return;

    // prefetch: true 옵션을 사용하여 클라이언트 측 네비게이션 활성화
    router.push('/rs-rank', { scroll: false });
    if (isMobile) setIsMenuOpen(false); // 모바일에서 페이지 이동 시 메뉴 닫기

    // 토글 버튼 숨김 이벤트 발생
    const hideToggleEvent = new CustomEvent('hideToggleButton', {
      bubbles: true
    });
    window.dispatchEvent(hideToggleEvent);

  };
  
  const goToETFSectorPage = () => {
    // 이미 ETF/섹터 페이지에 있는 경우 아무 작업도 수행하지 않음
    if (window.location.pathname === '/etf-sector') return;
    
    // prefetch: true 옵션을 사용하여 클라이언트 측 네비게이션 활성화
    router.push('/etf-sector', { scroll: false });
    if (isMobile) setIsMenuOpen(false); // 모바일에서 페이지 이동 시 메뉴 닫기
    // 토글 버튼 숨김 이벤트 발생
    const hideToggleEvent = new CustomEvent('hideToggleButton', {
      bubbles: true
    });
    window.dispatchEvent(hideToggleEvent);

  };
  
  const goToValuePage = () => {
    // 이미 밸류에이션 페이지에 있는 경우 아무 작업도 수행하지 않음
    if (window.location.pathname === '/value') return;
    
    // prefetch: true 옵션을 사용하여 클라이언트 측 네비게이션 활성화
    router.push('/value', { scroll: false });
    if (isMobile) setIsMenuOpen(false); // 모바일에서 페이지 이동 시 메뉴 닫기

    // 토글 버튼 숨김 이벤트 발생
    const hideToggleEvent = new CustomEvent('hideToggleButton', {
      bubbles: true
    });
    window.dispatchEvent(hideToggleEvent);
    
  };
  
  // // AI 애널리스트 페이지로 이동하는 함수 추가 (주석 처리)
  // const goToAnalystPage = () => {
  //   // 이미 애널리스트 페이지에 있는 경우 아무 작업도 수행하지 않음
  //   if (window.location.pathname === '/analyst') return;
  //
  //   // prefetch: true 옵션을 사용하여 클라이언트 측 네비게이션 활성화
  //   router.push('/analyst', { scroll: false });
  //   if (isMobile) setIsMenuOpen(false); // 모바일에서 페이지 이동 시 메뉴 닫기
  // };

  // 이전 toggleHistoryPanel 함수 제거
  
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

  // 버튼 위치에 따라 툴팁 위치 계산
  useEffect(() => {
    const updateTooltipPositions = () => {
      const positions: { [key: string]: number } = {};

      Object.entries(buttonRefs).forEach(([key, ref]) => {
        // 각 버튼 ref의 위치 계산
        if (ref.current) {
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
  }, []); // 의존성 배열 비움

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

  // 초기 로드 시 페이지 확인 용도로 사용하던 useEffect 제거

  // AIChatArea 컴포넌트의 마운트/언마운트 이벤트 감지
  useEffect(() => {
    // AIChatArea 컴포넌트 마운트 이벤트 리스너
    const handleAIChatAreaMounted = (e: CustomEvent) => {
      console.log('AIChatArea 마운트됨', new Date().toISOString());
    };
    
    // AIChatArea 컴포넌트 언마운트 이벤트 리스너
    const handleAIChatAreaUnmounted = (e: CustomEvent) => {
      console.log('AIChatArea 언마운트됨', new Date().toISOString());
    };
    
    // 이벤트 리스너 등록
    window.addEventListener('aiChatAreaMounted', handleAIChatAreaMounted as EventListener);
    window.addEventListener('aiChatAreaUnmounted', handleAIChatAreaUnmounted as EventListener);
    
    // 컴포넌트 언마운트 시 이벤트 리스너 제거
    return () => {
      window.removeEventListener('aiChatAreaMounted', handleAIChatAreaMounted as EventListener);
      window.removeEventListener('aiChatAreaUnmounted', handleAIChatAreaUnmounted as EventListener);
    };
  }, []); // 의존성 제거
  
  // 헤더에서 발생한 설정 팝업 열기 이벤트 감지
  useEffect(() => {
    // 헤더에서 설정 팝업 열기 이벤트 리스너
    const handleOpenSettingsPopup = (e: CustomEvent) => {
      // 헤더에서 설정 팝업 열기 요청이 오면 설정 팝업 열기
      setShowSettingsPopup(true);
    };
    
    // 이벤트 리스너 등록
    window.addEventListener('openSettingsPopup', handleOpenSettingsPopup as EventListener);
    
    // 컴포넌트 언마운트 시 이벤트 리스너 제거
    return () => {
      window.removeEventListener('openSettingsPopup', handleOpenSettingsPopup as EventListener);
    };
  }, []);

  // 모바일 메뉴 토글 함수
  const toggleMenu = () => {
    setIsMenuOpen(!isMenuOpen);
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
  
  // 히스토리 패널 외부 클릭 이벤트 리스너 제거
  
  // 종목 선택 및 프롬프트 입력 이벤트 리스너 제거
  
  // 컴포넌트 마운트 시 로그인 상태 확인
  useEffect(() => {
    // 쿠키에서 사용자 정보 가져오기
    const getUserInfoFromCookie = () => {
      try {
        // nookies를 사용하여 쿠키 파싱
        const cookies = parseCookies();

        // user_id 쿠키가 있는지 확인
        if (cookies.user_id) {
          setUserId(cookies.user_id);
          setUserName(cookies.user_name || '');
          setUserEmail(cookies.user_email || '');
          setUserProvider(cookies.provider || '');
          
          if (cookies.profile_image) {
            console.log('사용자 프로필 이미지:', cookies.profile_image);
            setUserProfileImage(cookies.profile_image);
          }
          
          setIsLoggedIn(true);
          return true;
        }
        
        // user 쿠키가 있는지 확인
        if (cookies.user) {
          // 쿠키 값 디코딩 및 JSON 파싱
          let jsonString = decodeURIComponent(cookies.user);
          
          // 이중 따옴표로 감싸진 JSON 문자열인 경우 처리
          if (jsonString.startsWith('"') && jsonString.endsWith('"')) {
            jsonString = jsonString.slice(1, -1).replace(/\\"/g, '"');
          }
          
          // JSON 파싱하여 사용자 정보 추출
          const userInfo = JSON.parse(jsonString);
          
          // 사용자 정보 설정
          if (userInfo.id) setUserId(userInfo.id);
          if (userInfo.name) setUserName(userInfo.name);
          if (userInfo.email) setUserEmail(userInfo.email);
          if (userInfo.provider) setUserProvider(userInfo.provider);
          if (userInfo.profile_image) {
            console.log('사용자 프로필 이미지:', userInfo.profile_image);
            setUserProfileImage(userInfo.profile_image);
          }
          
          setIsLoggedIn(true);
          return true;
        }
        
        return false;
      } catch (error) {
        console.error('사용자 정보 파싱 오류:', error);
        return false;
      }
    };
    
    // 쿠키에서 사용자 정보 가져오기 시도
    const hasUserInfo = getUserInfoFromCookie();
    
    // 쿠키에서 사용자 정보를 가져오지 못한 경우
    if (!hasUserInfo) {
      // 현재 URL이 /share_chat인지 검사
      const isShareChatPage = window.location.pathname.includes('/share_chat');
      
      if(isShareChatPage) {
        // 공유 채팅 페이지인 경우 로그인 건너뛰기
        setUserId('anonymous');
        setUserName('Anonymous User');
        console.log('공유 채팅 페이지: 로그인 건너뛰기');
      } else {
        // 운영 환경에서는 로그인 페이지로 리다이렉트
        redirectToLogin();
      }
    }
  }, []);

  // 설정 메뉴 토글 함수
  const toggleSettingsMenu = (e: React.MouseEvent) => {
    console.log('설정 메뉴 토글 함수 호출됨');
    e.preventDefault(); // 기본 동작 방지
    e.stopPropagation(); // 이벤트 버블링 방지
    
    // 현재 상태 확인 로그
    //console.log('현재 설정 메뉴 상태:', settingsMenuOpen);
    
    // 상태 토글
    setSettingsMenuOpen(prevState => {
      //console.log('설정 메뉴 상태 변경:', !prevState);
      return !prevState;
    });
  };
  
  // 설정 팝업 열기 함수
  const openSettingsPopup = (e: React.MouseEvent) => {
    e.preventDefault(); // 기본 동작 방지
    e.stopPropagation(); // 이벤트 버블링 방지
    
    // 비로그인 상태면 로그인 페이지로 리다이렉트
    if (!isLoggedIn || userId === 'anonymous') {
      const intellioUrl = process.env.NEXT_PUBLIC_INTELLIO_URL || 'https://intellio.kr';
      const redirectTo = 'stockeasy';
      window.location.href = `${intellioUrl}/login?redirectTo=${redirectTo}`;
      return;
    }
    
    setShowSettingsPopup(true); // 설정 팝업 열기
    setSettingsMenuOpen(false); // 설정 메뉴 닫기
  };
  
  // 설정 팝업 닫기 함수
  const closeSettingsPopup = () => {
    setShowSettingsPopup(false);
  };
  
  // 로그아웃 처리 함수
  const handleLogout = async (e: React.MouseEvent) => {
    e.stopPropagation(); // 이벤트 버블링 방지
    
    console.log('로그아웃 시도');
    
    try {
      // 공통 로그아웃 함수 호출
      await logout();
      console.log('로그아웃 성공');
    } catch (error) {
      console.error('로그아웃 처리 중 오류 발생:', error);
    }
  };

  // 설정 메뉴 외부 클릭 시 닫기
  useEffect(() => {
    console.log('설정 메뉴 외부 클릭 감지 효과 실행:', settingsMenuOpen);
    
    const handleClickOutside = (e: MouseEvent) => {
      console.log('문서 클릭 이벤트 발생');
      
      if (
        settingsMenuRef.current && 
        !settingsMenuRef.current.contains(e.target as Node) &&
        buttonRefs.settings.current &&
        !buttonRefs.settings.current.contains(e.target as Node)
      ) {
        console.log('설정 메뉴 외부 클릭 감지됨, 메뉴 닫기');
        setSettingsMenuOpen(false);
      }
    };

    if (settingsMenuOpen) {
      console.log('설정 메뉴 열림 상태, 클릭 이벤트 리스너 등록');
      // 약간의 지연 후 이벤트 리스너 등록
      const timerId = setTimeout(() => {
        document.addEventListener('click', handleClickOutside);
      }, 100);
      
      return () => {
        console.log('설정 메뉴 클릭 이벤트 리스너 제거');
        clearTimeout(timerId);
        document.removeEventListener('click', handleClickOutside);
      };
    }
    
    return undefined;
  }, [settingsMenuOpen]);
  
  // 로그인 다이얼로그 토글 함수
  const toggleLoginDialog = (e: React.MouseEvent) => {
    e.preventDefault(); // 기본 동작 방지
    e.stopPropagation(); // 이벤트 버블링 방지
    setIsLoginDialogOpen(!isLoginDialogOpen);
  };

  return (
    <>
      {/* 모바일 햄버거 메뉴 버튼 */}
      {isMobile && (
        <button 
          ref={menuButtonRef} // Ref 연결
          className="mobile-menu-button" 
          onClick={toggleMenu}
          style={{ zIndex: 1200 }} 
        >
          {/* 메뉴가 열려있으면 X 아이콘 표시 */}
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
      {!isMobile && (hoveredButton || showLoginTooltip) && (
        <div 
          className="fixed left-[63px] bg-[#202123] text-[#ececf1] py-0.5 px-2 rounded-[6px] text-xs shadow-md z-[2000] border border-gray-700 pointer-events-none"
          style={{ 
            top: showLoginTooltip
              ? `${tooltipPosition['settings'] ? tooltipPosition['settings'] + 10 : 0}px`
              : tooltipPosition[hoveredButton!] ? `${tooltipPosition[hoveredButton!] + 10}px` : '0px',
            transition: 'opacity 0.2s',
            opacity: 1
          }}
        >
          {hoveredButton === 'home' && '스탁 AI'}
          {hoveredButton === 'trendFollowing' && '추세추종'}
          {hoveredButton === 'chart' && 'RS순위'}
          {hoveredButton === 'etfSector' && 'ETF/섹터'}
          {hoveredButton === 'value' && '밸류에이션'}
          {hoveredButton === 'about' && 'About'}
          {hoveredButton === 'doc' && '닥이지'}
          {hoveredButton === 'user' && '마이페이지'}
          {hoveredButton === 'settings' && (isLoggedIn && userId !== 'anonymous' ? '마이페이지' : '로그인')} 
          {showLoginTooltip && (!isLoggedIn || userId === 'anonymous') && '이 필요합니다'}
        </div>
      )}

      {/* 로그인 다이얼로그 */}
      <LoginDialog 
        isOpen={isLoginDialogOpen} 
        onOpenChange={setIsLoginDialogOpen} 
      />
      
      {/* 설정 팝업 - 분리된 컴포넌트 사용 */}
      <SettingsPopup 
        isOpen={showSettingsPopup} 
        onClose={closeSettingsPopup} 
        userId={userId} 
        userName={userName}
        userEmail={userEmail}
        userProvider={userProvider}
        userImage={userProfileImage}
      />

      {/* 사이드바 컨텐츠 */}
        <div 
          ref={sidebarRef} // Ref 연결
          className={`sidebar ${isMobile ? 'mobile' : 'desktop'} ${isMenuOpen ? 'open' : ''}`}
          style={{
            // ... 기존 스타일 유지 ...
          }}
        >
          <div className="flex-1 overflow-hidden">
            <div className="pt-2">  {/* pt-4에서 pt-2로 줄임 */}
              {/* 파비콘 로고 추가 */}
              <div className="w-full flex justify-center mb-2">  {/* mb-4에서 mb-2로 줄임 */}
                <div className="sidebar-button-container flex justify-center">
                  <img 
                    src="/favicon-32x32.png" 
                    alt="StockEasy Logo" 
                    width={32} 
                    height={32} 
                    className="icon" 
                  />
                </div>
              </div>
              <div className="w-full flex flex-col items-end gap-y-1 text-[#3F424A]">  {/* gap-y-1 추가로 버튼 간격 줄임 */}
                
                {/* 홈 버튼 - 스탁이지 메인 페이지로 이동 */}
                <div className="sidebar-button-container">
                  <button 
                    ref={buttonRefs.home}
                    className="sidebar-button" 
                    onClick={goToHomePage} 
                    onMouseEnter={() => handleMouseEnter('home')}
                    onMouseLeave={handleMouseLeave}
                  >
                    <Bot className="icon" />
                    {/* 모바일 환경에서는 아이콘 옆에 텍스트 표시 */}
                    {isMobile && <span className="ml-2 text-sm text-[#ececf1]">스탁 AI</span>}
                  </button>
                </div>
                
                {/* 추세추종(Trend Following) 버튼 */}
                <div className="sidebar-button-container">
                  <button
                    ref={buttonRefs.trendFollowing}
                    className="sidebar-button"
                    onClick={() => {
                      if (window.location.pathname !== '/trend-following') {
                        router.push('/trend-following', { scroll: false });
                        if (isMobile) setIsMenuOpen(false);
                      }
                    }}
                    onMouseEnter={() => handleMouseEnter('trendFollowing')}
                    onMouseLeave={handleMouseLeave}
                  >
                    <LineChart className="icon" />
                    {isMobile && <span className="ml-2 text-sm text-[#ececf1]">추세추종</span>}
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
                
                {/* 밸류에이션 버튼 추가 */}
                <div className="sidebar-button-container">
                  <button 
                    ref={buttonRefs.value}
                    className="sidebar-button" 
                    onClick={goToValuePage} // 밸류에이션 페이지로 이동하는 함수 연결
                    onMouseEnter={() => handleMouseEnter('value')}
                    onMouseLeave={handleMouseLeave}
                  >
                    <Scale className="icon" />
                    {/* 모바일 환경에서는 아이콘 옆에 텍스트 표시 */}
                    {isMobile && <span className="ml-2 text-sm text-[#ececf1]">밸류에이션</span>}
                  </button>
                </div>
              </div>
            </div>
          </div>
          
          {/* 하단 영역 - 설정 버튼만 남김 */}
          <div className="mt-auto pb-4">
            <div className="w-full flex flex-col items-end gap-y-1"> 
              {/* 문서 버튼 삭제 - 하단으로 이동 */}
              
              {/* About 버튼 추가 */}
              <div className="sidebar-button-container mt-1">
                <button 
                  ref={buttonRefs.about}
                  className="sidebar-button" 
                  onClick={() => {
                    // About 페이지로 이동하는 로직 구현
                    router.push('/about', { scroll: false });
                    if (isMobile) setIsMenuOpen(false); // 모바일에서는 메뉴 닫기
                  }} 
                  onMouseEnter={() => handleMouseEnter('about')}
                  onMouseLeave={handleMouseLeave}
                >
                  <Info className="icon" />
                  {/* 모바일 환경에서는 아이콘 옆에 텍스트 표시 */}
                  {isMobile && <span className="ml-2 text-sm text-[#ececf1]">About</span>}
                </button>
              </div>
              
              {/* 문서 버튼 - DocEasy로 이동 */}
              <div className="sidebar-button-container mt-1">
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
              
              {/* 설정 버튼 - 클릭 이벤트 추가 (여기서는 Avatar 사용) */}
              <div 
                ref={buttonRefs.settings} // Ref 추가
                className={isMobile ? "sidebar-button" : "sidebar-button-container relative flex items-center w-full"} 
                onClick={openSettingsPopup}
                onMouseEnter={() => {
                  if (!isMobile) {
                    handleMouseEnter('settings');
                    if (!isLoggedIn || userId === 'anonymous') {
                      setShowLoginTooltip(true);
                    }
                  }
                }}
                onMouseLeave={() => {
                  if (!isMobile) {
                    handleMouseLeave();
                    setShowLoginTooltip(false);
                  }
                }}
                style={{ cursor: 'pointer' }} // Let the class handle padding
              >
                {isMobile ? (
                  <> {/* 모바일: 아바타 + 설정 텍스트 */}
                    <Avatar className="h-6 w-6 cursor-pointer"> 
                      <AvatarImage src={userProfileImage} alt={userName || 'User'} />
                      <AvatarFallback>
                        {isLoggedIn && userId !== 'anonymous' 
                          ? (userName ? userName.charAt(0) : 'U') 
                          : <UserIcon size={14} />}
                      </AvatarFallback>
                    </Avatar>
                    {/* Apply same text style as DocEasy button */}
                    <span className="ml-2 text-sm text-[#ececf1]">마이페이지</span> 
                  </>
                ) : ( 
                   <> {/* 데스크탑: 아바타만 표시 */}
                    <Avatar className="h-8 w-8 cursor-pointer">
                      <AvatarImage src={userProfileImage} alt={userName || 'User'} />
                      <AvatarFallback>
                        {isLoggedIn && userId !== 'anonymous' 
                          ? (userName ? userName.charAt(0) : 'U') 
                          : <UserIcon size={16} />}
                      </AvatarFallback>
                    </Avatar>
                  </> 
                )}
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