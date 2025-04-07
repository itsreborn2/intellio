"use client"

import { useApp } from "@/contexts/AppContext"
import { ChatSection } from './components/ChatSection'
import { TableSection } from './components/TableSection'
import { UploadSection } from './components/UploadSection'
import { useState, useEffect, useCallback, useRef } from 'react'
import { Maximize2, Minimize2, MessageSquare, Table } from 'lucide-react'
import { Button } from "intellio-common/components/ui/button"
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "intellio-common/components/ui/tooltip"
import { useAuth } from "@/hooks/useAuth"
import { ResizablePanelGroup, ResizablePanel, ResizableHandle } from "../../../common/components/ui/resizable"

// 애니메이션 스타일 정의
const expandAnimation = {
  animation: 'expandSection 0.1s forwards',
  WebkitAnimation: 'expandSection 0.1s forwards'
};

const collapseAnimation = {
  animation: 'collapseSection 0.1s forwards',
  WebkitAnimation: 'collapseSection 0.1s forwards'
};

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

export const DefaultTemplate = () => {
  const { state, dispatch } = useApp()
  const { isAuthenticated } = useAuth()
  const [activeTab, setActiveTab] = useState<'chat' | 'table'>('chat')
  const [chatExpanded, setChatExpanded] = useState(false)
  const [tableExpanded, setTableExpanded] = useState(false)
  const isMobile = useIsMobile();
  const fileInputRef = useRef<HTMLInputElement>(null);

  // 파일 업로드 버튼 클릭 핸들러
  const handleUploadButtonClick = useCallback(() => {
    fileInputRef.current?.click();
  }, []);

  // 채팅 섹션 토글 핸들러
  const toggleChat = () => {
    if (isMobile) {
      setActiveTab('chat');
    } else {
      setChatExpanded(!chatExpanded);
    }
  }

  // 테이블 섹션 토글 핸들러
  const toggleTable = () => {
    if (isMobile) {
      setActiveTab('table');
    } else {
      setTableExpanded(!tableExpanded);
    }
  }

  // 모바일 환경에서 탭 변경 시 스크롤 초기화
  useEffect(() => {
    if (isMobile) {
      window.scrollTo(0, 0);
    }
  }, [activeTab, isMobile]);

  // 화면 크기 변경 시 레이아웃 조정
  useEffect(() => {
    if (!isMobile) {
      setChatExpanded(false);
      setTableExpanded(false);
    }
  }, [isMobile]);

  // ESC 키로 확장 모드 종료
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && (chatExpanded || tableExpanded)) {
        setChatExpanded(false);
        setTableExpanded(false);
      }
    };
    
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [chatExpanded, tableExpanded]);

  // 모바일 환경에서 통합분석/개별분석 버튼 클릭 시 탭 전환 처리
  useEffect(() => {
    const handleSwitchTab = (e: CustomEvent) => {
      if (e.detail && e.detail.tab) {
        setActiveTab(e.detail.tab);
      }
    };
    
    window.addEventListener('switchToTab', handleSwitchTab as EventListener);
    return () => window.removeEventListener('switchToTab', handleSwitchTab as EventListener);
  }, []);

  // 버튼 텍스트와 아이콘 일치시키기
  const chatButtonIcon = chatExpanded ? <Minimize2 className="h-4 w-4" /> : <Maximize2 className="h-4 w-4" />;
  const chatButtonText = chatExpanded ? '복원' : '채팅 영역 최대화';
  
  const tableButtonIcon = tableExpanded ? <Minimize2 className="h-4 w-4 " /> : <Maximize2 className="h-4 w-4" />;
  const tableButtonText = tableExpanded ? '복원' : '테이블 영역 최대화';

  const renderContent = () => {
    switch (state.currentView) {
      case 'upload':
        return isAuthenticated ? (
          <div className="w-full h-full flex items-center justify-center bg-background">
            <UploadSection />
          </div>
        ) : (
          <div className="w-full h-full flex items-center justify-center bg-background">
            <div className="text-center">
              <h2 className="text-2xl font-semibold mb-4">로그인이 필요합니다</h2>
              <p className="text-muted-foreground">문서를 업로드하려면 먼저 로그인해주세요.</p>
            </div>
          </div>
        )
      
      case 'table':
      case 'chat':
        if (isMobile) {
          return (
            <div className="flex flex-col h-full">
              {/* 메인 콘텐츠 영역 */}
              <div className="flex-1 overflow-hidden">
                {/* 채팅 섹션 */}
                <div 
                  className={`
                    ${activeTab === 'chat'
                      ? 'flex-1 opacity-100 max-h-full'
                      : 'max-h-0 opacity-0 overflow-hidden'
                    }
                    transition-all duration-300 ease-in-out
                    ${activeTab === 'chat' ? 'z-10' : 'z-0'}
                    h-full
                  `}
                >
                  {activeTab === 'chat' && (
                    <div className="h-full">
                      <ChatSection 
                        onUploadButtonClick={handleUploadButtonClick} 
                      />
                    </div>
                  )}
                </div>

                {/* 테이블 섹션 */}
                <div 
                  className={`
                    ${activeTab === 'table'
                      ? 'flex-1 opacity-100 max-h-full'
                      : 'max-h-0 opacity-0 overflow-hidden'
                    }
                    transition-all duration-300 ease-in-out
                    ${activeTab === 'table' ? 'z-10' : 'z-0'}
                    h-full
                  `}
                >
                  {activeTab === 'table' && (
                    <div className="h-full">
                      <TableSection 
                        fileInputRef={fileInputRef} 
                      />
                    </div>
                  )}
                </div>
              </div>
            </div>
          );
        } else {
          // 데스크톱 환경에서는 기존 레이아웃 유지
          return (
            <div className="h-full w-full flex flex-col">
              <ResizablePanelGroup direction="vertical" className="h-full">
                <ResizablePanel 
                  defaultSize={50} 
                  minSize={20} 
                  className={chatExpanded ? "!flex-grow" : ""}
                  style={{ display: tableExpanded ? 'none' : undefined }}
                >
                  <div 
                    className="relative bg-background h-full transition-all duration-300 ease-in-out text-sm"
                    style={{
                      transformOrigin: 'center',
                      ...(chatExpanded ? expandAnimation : collapseAnimation)
                    }}
                  >
                    <div className="absolute right-4 top-1 z-30">
                      <TooltipProvider>
                        <Tooltip delayDuration={100}>
                          <TooltipTrigger asChild>
                            <Button
                              variant="ghost"
                              size="icon"
                              className="h-8 w-8 border bg-background hover:bg-accent transition-all duration-100 relative top-[2px]" 
                              onClick={() => {
                                setChatExpanded(!chatExpanded);
                                if (!chatExpanded) {
                                  setTableExpanded(false); // 채팅 영역 최대화 시 테이블 영역 복원
                                }
                              }}
                            >
                              {chatButtonIcon}
                            </Button>
                          </TooltipTrigger>
                          <TooltipContent side="bottom" align="end">
                            <p>{chatButtonText}</p>
                          </TooltipContent>
                        </Tooltip>
                      </TooltipProvider>
                    </div>
                    <ChatSection 
                      onUploadButtonClick={handleUploadButtonClick} 
                    />
                  </div>
                </ResizablePanel>
                
                <ResizableHandle withHandle className={chatExpanded || tableExpanded ? "hidden" : ""} />
                
                <ResizablePanel 
                  defaultSize={50} 
                  minSize={20}
                  className={tableExpanded ? "!flex-grow" : ""}
                  style={{ display: chatExpanded ? 'none' : undefined }}
                >
                  <div 
                    className="relative bg-background h-full transition-all duration-200 ease-in-out text-sm"
                    style={{
                      transformOrigin: 'center',
                      ...(tableExpanded ? expandAnimation : collapseAnimation)
                    }}
                  >
                    <div className="absolute right-4 top-1 z-30">
                      <TooltipProvider>
                        <Tooltip delayDuration={100}>
                          <TooltipTrigger asChild>
                            <Button
                              variant="ghost"
                              size="icon"
                              className="h-8 w-8 border bg-background hover:bg-accent transition-all duration-100 relative top-[2px]" 
                              onClick={() => {
                                setTableExpanded(!tableExpanded);
                                if (!tableExpanded) {
                                  setChatExpanded(false); // 테이블 영역 최대화 시 채팅 영역 복원
                                }
                              }}
                            >
                              {tableButtonIcon}
                            </Button>
                          </TooltipTrigger>
                          <TooltipContent side="bottom" align="end">
                            <p>{tableButtonText}</p>
                          </TooltipContent>
                        </Tooltip>
                      </TooltipProvider>
                    </div>
                    <TableSection 
                      fileInputRef={fileInputRef} 
                    />
                  </div>
                </ResizablePanel>
              </ResizablePanelGroup>
            </div>
          )
        }
      
      default:
        return (
          <div className="w-full h-full flex items-center justify-center">
            <p>Unknown view</p>
          </div>
        )
    }
  }

  return (
    <div className="h-full w-full">
      {/* 모바일 환경 상단 분석 버튼 그룹 - 문서가 있을 때만 표시 */}
      {isMobile && state.documents && Object.keys(state.documents).length > 0 && (
        <div className="fixed top-3 right-3 z-[1200] flex gap-1 w-[160px]">
          <Button
            variant="outline"
            size="sm"
            className={`text-xs px-1 h-8 whitespace-nowrap flex-1 rounded-md ${activeTab === 'chat' ? 'bg-primary text-primary-foreground md:hover:bg-primary/90' : ''}`}
            onClick={() => {
              dispatch({ type: 'SET_MODE', payload: 'chat' });
              const event = new CustomEvent('switchToTab', { detail: { tab: 'chat' } });
              window.dispatchEvent(event);
            }}
          >
            통합분석
          </Button>
          <Button
            variant="outline"
            size="sm"
            className={`text-xs px-1 h-8 whitespace-nowrap flex-1 rounded-md ${activeTab === 'table' ? 'bg-primary text-primary-foreground md:hover:bg-primary/90' : ''}`}
            onClick={() => {
              dispatch({ type: 'SET_MODE', payload: 'table' });
              const event = new CustomEvent('switchToTab', { detail: { tab: 'table' } });
              window.dispatchEvent(event);
            }}
          >
            {isMobile ? '문서목록' : '개별분석'}
          </Button>
        </div>
      )}
      
      <style jsx global>{`
        @keyframes expandSection {
          0% { transform: scale(0.99); opacity: 0.95; }
          100% { transform: scale(1); opacity: 1; }
        }
        @keyframes collapseSection {
          0% { transform: scale(1.01); opacity: 0.95; }
          100% { transform: scale(1); opacity: 1; }
        }
      `}</style>
      {renderContent()}
    </div>
  )
}
