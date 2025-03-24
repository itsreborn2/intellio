"use client"

import { Header } from '@/components/common/Header'
import { Sidebar } from '@/components/common/Sidebar'
import { AppProvider } from '@/contexts/AppContext'
import '@/styles/globals.css'
import { useState, useEffect } from 'react'

export default function RootLayout({
  children
}: {
  children: React.ReactNode
}) {
  // 사이드바 상태 관리
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);

  // 초기 상태 로드 (로컬 스토리지에서 사용자 선호도 가져오기)
  useEffect(() => {
    const savedState = localStorage.getItem('sidebarCollapsed');
    if (savedState !== null) {
      setIsSidebarCollapsed(savedState === 'true');
    }
  }, []);

  // 사이드바 상태 변경 이벤트 리스너
  useEffect(() => {
    const handleSidebarStateChanged = (event: CustomEvent) => {
      setIsSidebarCollapsed(event.detail.isCollapsed);
    };

    // 이벤트 리스너 등록
    window.addEventListener('sidebarStateChanged', handleSidebarStateChanged as EventListener);

    // 컴포넌트 언마운트 시 이벤트 리스너 제거
    return () => {
      window.removeEventListener('sidebarStateChanged', handleSidebarStateChanged as EventListener);
    };
  }, []);

  return (
    <html lang="en">
      <body className="bg-background text-foreground">
        <AppProvider>
          <div className="flex h-screen overflow-hidden bg-background">
            {/* 사이드바 */}
            <Sidebar className="fixed left-0 top-0 h-full z-50" />
            
            {/* 메인 컨테이너 */}
            <div className={`flex-1 transition-all duration-300 ease-in-out ${isSidebarCollapsed ? 'ml-[50px]' : 'ml-[250px]'}`}>
              {/* 헤더 */}
              <Header className={`fixed top-0 right-0 transition-all duration-300 ease-in-out ${isSidebarCollapsed ? 'left-[50px]' : 'left-[250px]'} h-[56px] z-40 bg-background border-b`} />
              
              {/* 메인 콘텐츠 영역 */}
              <main className={`fixed top-[56px] right-0 transition-all duration-300 ease-in-out ${isSidebarCollapsed ? 'left-[50px]' : 'left-[250px]'} bottom-0 overflow-hidden`}>
                {children}
              </main>
            </div>
          </div>
        </AppProvider>
      </body>
    </html>
  )
}
