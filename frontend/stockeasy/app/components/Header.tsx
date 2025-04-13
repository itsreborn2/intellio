'use client'

import React, { useState, useRef, useEffect } from 'react';
import { Avatar, AvatarFallback, AvatarImage } from "intellio-common/components/ui/avatar";
import { parseCookies } from 'nookies';
import { isLoggedIn } from '../utils/auth';
import { useQuestionCountStore } from '@/stores/questionCountStore';
import { MessageSquare, HelpCircle } from 'lucide-react';
import { Badge } from "@/components/ui/badge";

/**
 * StockEasy 애플리케이션의 고정 헤더 컴포넌트.
 * 화면 상단에 고정되며, 데스크톱에서는 사이드바 영역을 제외한 너비를 가집니다.
 */
const Header: React.FC = () => {
  // 사용자 정보 관련 상태
  const [userId, setUserId] = useState<string | null>(null);
  const [userName, setUserName] = useState('');
  const [userProfileImage, setUserProfileImage] = useState('');
  const [userEmail, setUserEmail] = useState('');
  const [userProvider, setUserProvider] = useState('');
  const [isUserLoggedIn, setIsUserLoggedIn] = useState<boolean>(false);

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

  // 오늘 질문 개수 계산
  const getTodayQuestionCount = (): number => {
    if (!questionSummary || !questionSummary.grouped_data) return 0;
    
    // 오늘 날짜 가져오기 (YYYY-MM-DD 형식)
    const today = new Date().toISOString().split('T')[0];
    
    // 오늘 질문 개수 반환
    return questionSummary.grouped_data[today] || 0;
  };

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
        {/* 로고 텍스트 */}
        <div className="text-lg font-semibold pl-[25px] md:pl-0">StockEasy</div>
        
        {/* 우측 영역: 질문 개수 + 아바타 */}
        <div className="flex items-center gap-3">
          {/* 질문 개수 표시 */}
          {isUserLoggedIn && (
            <div className="flex items-center gap-1">
              <MessageSquare size={18} className="text-gray-600" />
              {/* 반응형 클래스 추가: 기본(모바일)은 text-xs, px-2 / sm 이상은 text-sm, px-2.5 */}
              <Badge variant="outline" className="rounded-md py-0 h-5 bg-[#D8EFE9] border-[#D8EFE9] text-xs px-2 sm:text-sm sm:px-2.5" style={{ borderRadius: '6px' }}>
                {isQuestionLoading ? "..." : `${questionSummary?.total_questions} / 30`}
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

      {/* 설정 팝업은 사이드바에서 관리하므로 여기서는 제거 */}
    </header>
  );
};

export default Header;
