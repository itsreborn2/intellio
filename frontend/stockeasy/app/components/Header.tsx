'use client'

import React, { useState, useRef, useEffect } from 'react';
import { Avatar, AvatarFallback, AvatarImage } from "intellio-common/components/ui/avatar";

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
  const [isLoggedIn, setIsLoggedIn] = useState<boolean>(false);

  // 사용자 정보 가져오기
  useEffect(() => {
    // 로컬 스토리지에서 사용자 정보 가져오기
    const storedUserInfo = localStorage.getItem('userInfo');
    
    if (storedUserInfo) {
      try {
        const userInfo = JSON.parse(storedUserInfo);
        if (userInfo.id) setUserId(userInfo.id);
        setIsLoggedIn(true);
        setUserName(userInfo.name || '');
        if (userInfo.picture) setUserProfileImage(userInfo.picture);
        setUserEmail(userInfo.email || '');
        setUserProvider(userInfo.provider || '');
      } catch (error) {
        console.error('Error parsing user info:', error);
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
        
        {/* 아바타 */}
        {isLoggedIn && (
          <div 
            className="cursor-pointer" 
            onClick={openSettingsPopup}
          >
            <Avatar className="h-8 w-8">
              <AvatarImage key={userProfileImage} src={userProfileImage || '/default-avatar.png'} alt={userName || 'User'} />
              <AvatarFallback>{userName ? userName.charAt(0) : 'U'}</AvatarFallback>
            </Avatar>
            <div style={{ fontSize: 10, color: 'red' }}>{userProfileImage}</div>
          </div>
        )}
      </div>

      {/* 설정 팝업은 사이드바에서 관리하므로 여기서는 제거 */}
    </header>
  );
};

export default Header;
