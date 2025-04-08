"use client"

import { Header } from '@/components/common/Header'
import { Sidebar } from '@/components/common/Sidebar'
import { AppProvider } from '@/contexts/AppContext'
import '@/styles/globals.css'
import { useState, useEffect, useRef, forwardRef } from 'react'
import { Menu, X } from 'lucide-react'

// 모바일 환경 감지 훅
const useIsMobile = () => {
  const [isMobile, setIsMobile] = useState(false);

  useEffect(() => {
    const checkIsMobile = () => {
      setIsMobile(window.innerWidth < 768); // 768px 미만을 모바일로 간주
    };

    // 초기 체크
    checkIsMobile();

    // 리사이즈 이벤트에 대응
    window.addEventListener('resize', checkIsMobile);
    return () => window.removeEventListener('resize', checkIsMobile);
  }, []);

  return isMobile;
};

interface MobileMenuButtonProps {
  toggleSidebar: () => void;
}

const MobileMenuButton = forwardRef<HTMLButtonElement, MobileMenuButtonProps>(
  ({ toggleSidebar }, ref) => {
    return (
      <button
        ref={ref}
        className="fixed top-4 left-4 z-[1001] md:hidden p-1.5 rounded-md bg-[#212529] text-white hover:bg-[#343a40]"
        onClick={toggleSidebar}
        aria-label="메뉴 열기/닫기"
      >
        <Menu size={20} strokeWidth={2} />
      </button>
    );
  }
);
MobileMenuButton.displayName = 'MobileMenuButton';

export default function RootLayout({
  children
}: {
  children: React.ReactNode
}) {
  // 사이드바 상태 관리 - 초기값은 false로 설정하여 서버와 클라이언트 초기 렌더링 일치
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);
  const [isMenuOpen, setIsMenuOpen] = useState(false); // 모바일 메뉴 상태
  const isMobile = useIsMobile();
  const sidebarRef = useRef<HTMLDivElement>(null); // 사이드바 참조
  const menuButtonRef = useRef<HTMLButtonElement>(null); // 메뉴 버튼 참조

  // 모바일 메뉴 토글 함수
  const toggleMenu = () => {
    setIsMenuOpen(prev => !prev);
    const event = new CustomEvent('toggleSidebar');
    window.dispatchEvent(event);
  };

  // 사이드바 상태 변경 이벤트 리스너
  useEffect(() => {
    const handleSidebarStateChanged = (event: CustomEvent) => {
      setIsSidebarCollapsed(event.detail.isCollapsed);
    };
    window.addEventListener('sidebarStateChanged', handleSidebarStateChanged as EventListener);
    return () => {
      window.removeEventListener('sidebarStateChanged', handleSidebarStateChanged as EventListener);
    };
  }, []);

  // 사이드바에서 발생하는 closeMobileMenu 이벤트 수신
  useEffect(() => {
    const handleCloseMobileMenu = () => {
      setIsMenuOpen(false);
    };
    window.addEventListener('closeMobileMenu', handleCloseMobileMenu);
    return () => {
      window.removeEventListener('closeMobileMenu', handleCloseMobileMenu);
    };
  }, []);

  // 외부 클릭 감지 로직 추가
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (
        isMobile &&
        isMenuOpen &&
        sidebarRef.current &&
        !sidebarRef.current.contains(event.target as Node) &&
        menuButtonRef.current &&
        !menuButtonRef.current.contains(event.target as Node)
      ) {
        setIsMenuOpen(false);
        // Sidebar 컴포넌트 내부 상태 동기화를 위해 이벤트 전달 (선택 사항, Sidebar 구현에 따라 필요 없을 수 있음)
        // const closeEvent = new CustomEvent('closeSidebar');
        // window.dispatchEvent(closeEvent);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);

    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [isMobile, isMenuOpen, sidebarRef, menuButtonRef]);

  // 스크롤바 스타일을 적용하는 전역 스타일 요소 추가
  useEffect(() => {
    // 기존 스타일 태그가 있으면 제거
    const existingStyle = document.getElementById('custom-scrollbar-style');
    if (existingStyle) {
      existingStyle.remove();
    }

    // 새 스타일 태그 생성 및 추가
    const style = document.createElement('style');
    style.id = 'custom-scrollbar-style';
    style.innerHTML = `
      * {
        scrollbar-width: thin !important;
        scrollbar-color: rgba(133, 139, 157, 0.3) transparent !important;
        -webkit-overflow-scrolling: touch !important;
      }
      
      *::-webkit-scrollbar {
        width: 6px !important;
        height: 6px !important;
      }
      
      *::-webkit-scrollbar-track {
        background: transparent !important;
      }
      
      *::-webkit-scrollbar-thumb {
        background-color: rgba(133, 139, 157, 0.3) !important;
        border-radius: 3px !important;
        border: none !important;
      }
      
      *::-webkit-scrollbar-thumb:hover {
        background-color: rgba(133, 139, 157, 0.5) !important;
      }
      
      @media (max-width: 767px) {
        *::-webkit-scrollbar {
          width: 4px !important;
          height: 4px !important;
        }
        
        *::-webkit-scrollbar-thumb {
          background-color: rgba(133, 139, 157, 0.3) !important;
          border-radius: 2px !important;
        }
      }
    `;
    document.head.appendChild(style);

    return () => {
      if (style && document.head.contains(style)) {
        document.head.removeChild(style);
      }
    };
  }, []);

  return (
    <html lang="en">
      <body className="bg-background text-foreground">
        <AppProvider>
          {isMobile && !isMenuOpen && (
            <MobileMenuButton ref={menuButtonRef} toggleSidebar={toggleMenu} />
          )}

          <div className="flex h-screen overflow-hidden bg-background" style={{ position: 'relative', zIndex: 1 }}>
            <Sidebar 
              ref={sidebarRef} 
              className="transition-all duration-300 ease-in-out" 
              isMobileMenuOpen={isMenuOpen} 
              isCollapsed={isSidebarCollapsed} 
            />

            <div className={`flex-1 transition-all duration-300 ease-in-out ${
              isMobile ? 'ml-0' : (isSidebarCollapsed ? 'ml-[60px]' : 'ml-[300px]')
            }`}>
              {!isMobile && (
                <div
                  className={`fixed top-0 right-0  transition-all duration-300 ease-in-out ${
                    isSidebarCollapsed ? 'left-[60px]' : 'left-[300px]'
                  } h-[56px] z-40 bg-background`}
                >
                  <Header />
                </div>
              )}

              <main className={`fixed right-0 bottom-0 overflow-auto  transition-all duration-300 ease-in-out ${
                isMobile
                  ? 'left-0 top-0 h-screen' // 모바일: 전체 화면 높이 사용
                  : `${isSidebarCollapsed ? 'left-[60px]' : 'left-[300px]'} top-[56px] h-[calc(100vh-56px)]` // 데스크탑: 헤더 높이 제외
              }`}>
                {children}
              </main>
            </div>
          </div>
        </AppProvider>
      </body>
    </html>
  )
}
