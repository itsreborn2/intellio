"use client";

import React, { useState, useEffect } from 'react';
import { usePathname } from 'next/navigation';
import Sidebar from './Sidebar';
import Header from './Header';
import HistoryButton from './HistoryButton';
import ConditionalFooter from './ConditionalFooter';
import { Toaster } from 'sonner';

interface AppClientLayoutProps {
  children: React.ReactNode;
}

export default function AppClientLayout({ children }: AppClientLayoutProps) {
  const [isHistoryPanelOpen, setIsHistoryPanelOpen] = useState(false);
  const [isPanelContentVisible, setIsPanelContentVisible] = useState(false);
  const [isMobile, setIsMobile] = useState(false);
  const pathname = usePathname();

  useEffect(() => {
    const checkIfMobile = () => {
      setIsMobile(window.innerWidth <= 768);
    };
    checkIfMobile();
    window.addEventListener('resize', checkIfMobile);
    return () => window.removeEventListener('resize', checkIfMobile);
  }, []);

  useEffect(() => {
    if (isHistoryPanelOpen) {
      setIsPanelContentVisible(true);
    } else {
      const timer = setTimeout(() => {
        setIsPanelContentVisible(false);
      }, 300); // Corresponds to HistoryButton's animation duration
      return () => clearTimeout(timer);
    }
  }, [isHistoryPanelOpen]);

  const toggleHistoryPanel = () => {
    setIsHistoryPanelOpen(prev => !prev);
  };

  return (
    <>
      <Toaster position="bottom-center" richColors closeButton />
      {/* 모바일이고 히스토리 패널이 열려있으면 사이드바를 숨김 */}
      {!(isMobile && isHistoryPanelOpen) && <Sidebar />} 

      <HistoryButton 
        isHistoryPanelOpen={isHistoryPanelOpen}
        isPanelContentVisible={isPanelContentVisible}
        toggleHistoryPanel={toggleHistoryPanel}
      />
      <Header 
        isMobile={isMobile}
        pathname={pathname}
        isHistoryPanelOpen={isHistoryPanelOpen}
        toggleHistoryPanel={toggleHistoryPanel}
      /> 
      <main className="fixed top-[44px] bottom-0 right-0 left-0 md:left-[59px] overflow-auto">
        <div className="content-container">
          {children}
        </div>
        <ConditionalFooter />
      </main>
    </>
  );
}
