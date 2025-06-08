'use client'

import React, { useState, useEffect } from 'react';
import { Avatar, AvatarFallback, AvatarImage } from "intellio-common/components/ui/avatar";
import { parseCookies } from 'nookies';
import { isLoggedIn } from '../utils/auth';
import { useQuestionCountStore } from '@/stores/questionCountStore';
import { useUserModeStore, useIsClient } from '@/stores/userModeStore';
import { MessageSquare, Download, Loader2, Share, History } from 'lucide-react';
import { Badge } from "@/components/ui/badge";
import { usePathname } from 'next/navigation';
import Link from 'next/link';
import { useChatStore } from '@/stores/chatStore';
import { toast } from 'sonner';
import { usePdfExport } from '@/services/api/usePdfExport';
import { useChatShare } from '@/services/api/useChatShare';
/**
 * StockEasy 애플리케이션의 고정 헤더 컴포넌트.
 * 화면 상단에 고정되며, 데스크톱에서는 사이드바 영역을 제외한 너비를 가집니다.
 */
interface HeaderProps {
  isMobile: boolean;
  pathname: string;
  isHistoryPanelOpen: boolean;
  toggleHistoryPanel: () => void;
}

const Header: React.FC<HeaderProps> = ({
  isMobile,
  pathname,
  isHistoryPanelOpen,
  toggleHistoryPanel,
}) => {
  // 사용자 정보 관련 상태
  const [userId, setUserId] = useState<string | null>(null);
  const [userName, setUserName] = useState('');
  const [userProfileImage, setUserProfileImage] = useState('');
  const [userEmail, setUserEmail] = useState('');
  const [isUserLoggedIn, setIsUserLoggedIn] = useState<boolean>(false);
  const [toggleVisible, setToggleVisible] = useState(false);
  
  // 사용자 모드 스토어 사용
  const { mode: userMode, setMode: setUserMode } = useUserModeStore();

  // 클라이언트 측 마운트 상태 확인
  const isClient = useIsClient();

  // pathname is now passed as a prop
  
  // 채팅 스토어에서 메시지 목록과 현재 세션 가져오기
  const { messages: storeMessages, currentSession } = useChatStore();
  
  // PDF 내보내기 훅 사용
  const { isPdfLoading, exportToPdf } = usePdfExport();
  
  // 공유 링크 생성 훅 사용
  const { isShareLoading, createShareLink } = useChatShare();
  
  // 메시지가 있는지 확인하여 토글 버튼을 표시할지 결정
  const hasChatMessages = storeMessages.length > 0;

  // useChatStore 변경 감시
  useEffect(() => {
    console.log('[Header] 채팅 스토어 변경 감지:', 
      '메시지:', storeMessages.length, 
      '세션:', !!currentSession,
      '세션ID:', currentSession?.id
    );
  }, [storeMessages, currentSession]);

  // 질문 개수 스토어 사용
  const { 
    summary: questionSummary, 
    fetchSummary: fetchQuestionSummary, 
    isLoading: isQuestionLoading 
  } = useQuestionCountStore();

  // 오늘 질문 개수 가져오기
  useEffect(() => {
    if (isUserLoggedIn) {
      fetchQuestionSummary('day', 'day');
    }
  }, [isUserLoggedIn, fetchQuestionSummary]);

  // 토글 버튼 가시성을 메시지 존재 여부로만 결정
  useEffect(() => {
    // 다른 페이지에서는 메시지가 있을 때 토글 버튼 표시
    console.log('[헤더] 메시지가 있을 때 토글 버튼 표시', hasChatMessages);
    setToggleVisible(hasChatMessages);
  }, [hasChatMessages]);

  // 토글 버튼 표시 이벤트 리스너
  useEffect(() => {
    // 토글 버튼 표시 이벤트 핸들러
    const handleShowToggle = () => {
      console.log('[헤더] 토글 버튼 표시 이벤트 수신');
      setToggleVisible(true);
    };

    // 이벤트 리스너 등록
    if (isClient) {
      window.addEventListener('showToggleButton', handleShowToggle);
    }

    // 클린업 함수
    return () => {
      if (typeof window !== 'undefined') {
        window.removeEventListener('showToggleButton', handleShowToggle);
      }
    };
  }, [isClient, pathname]);

  // 홈 버튼 클릭 시 토글 버튼 숨김 이벤트 리스너
  useEffect(() => {
    // 토글 버튼 숨김 이벤트 핸들러
    const handleHideToggle = () => {
      console.log('[헤더] 토글 버튼 숨김 이벤트 수신');
      setToggleVisible(false);
    };

    // 이벤트 리스너 등록
    if (isClient) {
      window.addEventListener('hideToggleButton', handleHideToggle);
    }

    // 클린업 함수
    return () => {
      if (typeof window !== 'undefined') {
        window.removeEventListener('hideToggleButton', handleHideToggle);
      }
    };
  }, [isClient]);

  // 사용자 정보 가져오기
  useEffect(() => {
    // auth.tsx의 isLoggedIn 함수로 로그인 상태 확인
    const loggedIn = isLoggedIn();
    setIsUserLoggedIn(loggedIn);
    
    if (loggedIn) {
      // nookies를 사용하여 쿠키에서 사용자 정보 가져오기
      const cookies = parseCookies();
      
      // user_id 쿠키가 있는 경우
      if (cookies.user_id) {
        setUserId(cookies.user_id);
        setUserName(cookies.user_name || '');
        setUserProfileImage(cookies.profile_image || '');
        setUserEmail(cookies.user_email || '');
        return;
      }
      
      // user 쿠키에서 정보 파싱 시도
      if (cookies.user) {
        try {
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
          if (userInfo.profile_image) setUserProfileImage(userInfo.profile_image);
          if (userInfo.email) setUserEmail(userInfo.email);
        } catch (error) {
          console.error('사용자 정보 파싱 오류:', error);
        }
      }
    }
  }, []);

  // 사이드바의 설정 팝업을 열기 위한 함수
  const openSettingsPopup = (e: React.MouseEvent) => {
    e.preventDefault(); // 기본 동작 방지
    e.stopPropagation(); // 이벤트 버블링 방지
    
    // 사이드바의 설정 팝업을 열기 위한 커스텀 이벤트 발생
    const event = new CustomEvent('openSettingsPopup', {
      detail: { source: 'header' }
    });
    window.dispatchEvent(event);
  };

  // 모드 변경 처리
  const handleModeToggle = () => {
    // 현재 모드의 반대 모드로 전환
    const newMode = userMode === 'beginner' ? 'expert' : 'beginner';
    setUserMode(newMode);
  };

  // 질문 비율 계산
  const getQuestionRatio = () => {
    if (!questionSummary || isQuestionLoading) return 0;
    return (questionSummary.total_questions / 30) * 100;
  };

  // PDF 내보내기 처리 핸들러
  const handleSaveAsPdf = () => {
    if (!currentSession) {
      toast.error('채팅 세션이 없습니다.');
      return;
    }
    
    // usePdfExport 훅의 exportToPdf 함수 호출
    exportToPdf(currentSession.id, userMode === 'expert');
  };

  // 공유 링크 생성 처리 핸들러
  const handleShareChat = async () => {
    if (!currentSession) {
      toast.error('채팅 세션이 없습니다.', { position: 'top-center' });
      return;
    }
    
    try {
      const result = await createShareLink(currentSession.id);
      
      // 클립보드에 링크 복사
      await navigator.clipboard.writeText(result.share_url);
      
      toast.success('공유 링크가 클립보드에 복사되었습니다.', { position: 'top-center' });
    } catch (error) {
      toast.error('공유 링크 생성에 실패했습니다.', { position: 'top-center' });
    }
  };

  // console.log('[Header] 렌더링:', 
  //   '로그인:', isUserLoggedIn, 
  //   '메시지:', storeMessages.length, 
  //   '세션:', !!currentSession
  // );

  return (
    <header 
      className="
        fixed top-0 left-0 md:left-[59px] 
        w-full md:w-[calc(100%-59px)] 
        h-[44px] 
        bg-[#F4F4F4] 
        z-40 
        flex items-center px-4 
      "
    >
      {/* 헤더 내용 - 로고와 아바타 배치 */}
      <div className="flex justify-between items-center w-full">
        <div className="flex items-center">
          {/* 로고 텍스트 */}
          <div className="text-lg font-semibold pl-[27px] md:pl-0">StockEasy</div>
          {/* 모바일 히스토리 버튼 */}
          {isMobile && pathname === '/' && !isHistoryPanelOpen && (
            <div className="relative ml-2">
              <button
                onClick={toggleHistoryPanel}
                className="p-1 text-gray-600 hover:text-gray-900"
                onMouseEnter={() => setToggleVisible(true)}
                onMouseLeave={() => setToggleVisible(false)}
              >
                <History size={22} />
              </button>
              {toggleVisible && (
                <div className="absolute top-1/2 left-full transform -translate-y-1/2 ml-2 px-2 py-1 bg-slate-800 text-white text-xs rounded-[6px] whitespace-nowrap z-[9999]">
                  검색 히스토리
                </div>
              )}
            </div>
          )}
          {/* 헤더 메뉴 */}
          {/* <nav>
            <ul className="flex items-center ml-4 space-x-4 text-[#3F424A] text-sm">
              <li><Link href="/trend-following"><span className="hover:text-gray-900 transition-colors font-bold">메인</span></Link></li>
              <li><Link href="/"><span className="hover:text-gray-900 transition-colors font-bold">스탁AI</span></Link></li>
              <li><Link href="/rs-rank"><span className="hover:text-gray-900 transition-colors font-bold">RS순위</span></Link></li>
              <li><Link href="/etf-sector"><span className="hover:text-gray-900 transition-colors font-bold">ETF섹터</span></Link></li>
              <li><Link href="/value"><span className="hover:text-gray-900 transition-colors font-bold">밸류에이션</span></Link></li>
            </ul>
          </nav> */}
        </div>
        <div className="flex items-center gap-3">
          {/* 중앙 영역: 모드 선택 토글 - 채팅 메시지가 있을 때만 표시 */}
          {/* 토글 버튼 일시적으로 비활성화 */}
          {/* <div 
            className={`
              flex items-center 
              transition-opacity duration-300 ease-in-out
              ${toggleVisible ? 'opacity-100' : 'opacity-0'}
            `}
            style={{ 
              display: toggleVisible ? '' : 'none',
              height: '44px',
              visibility: toggleVisible ? 'visible' : 'hidden'
            }}
          >
            토글 스위치 버튼
            <div className="flex items-center">
              각 라벨에 고정 너비를 적용하고 텍스트 정렬을 중앙으로 설정
              <div className="w-16 text-center">
                <span className={`${userMode === 'beginner' ? 'text-lg font-semibold text-[#10A37F]' : 'text-xs text-gray-500'}`}>
                  주린이
                </span>
              </div>
              
              토글 스위치
              <div className="flex justify-center items-center mx-1">
                <button 
                  onClick={handleModeToggle}
                  className="relative inline-flex h-6 w-11 items-center rounded-full"
                  role="switch"
                  aria-checked={userMode === 'expert'}
                >
                  <span 
                    className={`
                      absolute w-full h-full rounded-full transition-colors duration-200 ease-in-out
                      ${userMode === 'expert' ? 'bg-[#4A72B0]' : 'bg-[#10A37F]'}
                    `}
                  ></span>
                  <span 
                    className={`
                      pointer-events-none block h-4 w-4 rounded-full bg-white shadow-lg ring-0 transition-transform duration-200
                      ${userMode === 'expert' ? 'translate-x-5' : 'translate-x-1'}
                    `}
                  ></span>
                </button>
              </div>
              
              각 라벨에 고정 너비를 적용하고 텍스트 정렬을 중앙으로 설정
              <div className="w-16 text-center">
                <span className={`${userMode === 'expert' ? 'text-lg font-semibold text-[#4A72B0]' : 'text-xs text-gray-500'}`}>
                  전문가
                </span>
              </div>
            </div>
          </div> */}
          {/* 공유하기 버튼 - 채팅 메시지가 있고 세션이 있을 때만 표시 */}
          {isUserLoggedIn && hasChatMessages && currentSession && (
            <button
              onClick={handleShareChat}
              disabled={isShareLoading}
              className="flex items-center gap-1 text-sm px-2.5 py-1 rounded-md bg-[#F5F5F5] hover:bg-[#E5E5E5] transition-colors border border-[#DDD]"
            >
              {isShareLoading ? (
                <Loader2 size={16} className="animate-spin" />
              ) : (
                <Share size={16} />
              )}
              <span className="hidden sm:inline">공유</span>
            </button>
          )}
          {/* PDF 내보내기 버튼 - 채팅 메시지가 있고 세션이 있을 때만 표시 */}
          {isUserLoggedIn && hasChatMessages && currentSession && (
            <button
              onClick={handleSaveAsPdf}
              disabled={isPdfLoading}
              className="flex items-center gap-1 text-sm px-2.5 py-1 rounded-md bg-[#F5F5F5] hover:bg-[#E5E5E5] transition-colors border border-[#DDD]"
            >
              {isPdfLoading ? (
                <Loader2 size={16} className="animate-spin" />
              ) : (
                <Download size={16} />
              )}
              <span className="hidden sm:inline">PDF</span>
            </button>
          )}
          {/* 질문 개수 표시 */}
          {isUserLoggedIn && (
            <div className="flex items-center gap-0.5">
              <MessageSquare size={16} className="text-gray-600" />
              <Badge variant="outline" className="h-5 text-xs px-1.5 ml-0.5 rounded-md flex items-center justify-center">
                {isQuestionLoading ? "..." : `${10 - (questionSummary?.total_questions || 0)}`}
              </Badge>
            </div>
          )}
          {/* 아바타 */}
          {isUserLoggedIn && (
            <div 
              className="cursor-pointer" 
              onClick={openSettingsPopup}
            >
              <Avatar className="h-8 w-8">
                <AvatarImage src={userProfileImage || '/default-avatar.png'} alt={userName || 'User'} />
                <AvatarFallback>{userName ? userName.charAt(0) : 'U'}</AvatarFallback>
              </Avatar>
            </div>
          )}
        </div>
      </div>
    </header>
  );
};

export default Header;
