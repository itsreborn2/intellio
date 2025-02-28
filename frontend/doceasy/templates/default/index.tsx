"use client"

import { useApp } from "@/contexts/AppContext"
import { ChatSection } from './components/ChatSection'
import { TableSection } from './components/TableSection'
import { UploadSection } from './components/UploadSection'
import { useState, useEffect } from 'react'
import { Maximize2, Minimize2 } from 'lucide-react'
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

export const DefaultTemplate = () => {
  const { state } = useApp()
  const { isAuthenticated } = useAuth()
  const [expandedSection, setExpandedSection] = useState<'none' | 'chat' | 'table'>('none')

  // ESC 키로 확장 모드 종료
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && expandedSection !== 'none') {
        setExpandedSection('none');
      }
    };
    
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [expandedSection]);

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
        if (expandedSection === 'chat') {
          return (
            <div className="h-full w-full flex flex-col">
              <div 
                className="relative bg-background h-full transition-all duration-300 ease-in-out text-sm"
                style={{
                  transformOrigin: 'center',
                  ...expandAnimation
                }}
              >
                <div className="absolute right-2 top-2 z-30">
                  <TooltipProvider>
                    <Tooltip delayDuration={100}>
                      <TooltipTrigger asChild>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-8 w-8 border bg-background hover:bg-accent transition-all duration-100"
                          onClick={() => setExpandedSection('none')}
                        >
                          <Minimize2 className="h-4 w-4" />
                        </Button>
                      </TooltipTrigger>
                      <TooltipContent side="bottom" align="end">
                        <p>복원</p>
                      </TooltipContent>
                    </Tooltip>
                  </TooltipProvider>
                </div>
                <ChatSection />
              </div>
            </div>
          )
        } else if (expandedSection === 'table') {
          return (
            <div className="h-full w-full flex flex-col">
              <div 
                className="relative bg-background h-full overflow-hidden transition-all duration-300 ease-in-out text-sm"
                style={{
                  transformOrigin: 'center',
                  ...expandAnimation
                }}
              >
                <div className="absolute right-2 top-2 z-30">
                  <TooltipProvider>
                    <Tooltip delayDuration={100}>
                      <TooltipTrigger asChild>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-8 w-8 border bg-background hover:bg-accent transition-all duration-100"
                          onClick={() => setExpandedSection('none')}
                        >
                          <Minimize2 className="h-4 w-4" />
                        </Button>
                      </TooltipTrigger>
                      <TooltipContent side="bottom" align="end">
                        <p>복원</p>
                      </TooltipContent>
                    </Tooltip>
                  </TooltipProvider>
                </div>
                <TableSection />
              </div>
            </div>
          )
        } else {
          return (
            <div className="h-full w-full flex flex-col">
              <ResizablePanelGroup direction="vertical" className="h-full">
                <ResizablePanel defaultSize={50} minSize={20}>
                  <div 
                    className="relative bg-background h-full transition-all duration-300 ease-in-out text-sm"
                    style={{
                      transformOrigin: 'center',
                      ...(expandedSection === 'none' ? collapseAnimation : {})
                    }}
                  >
                    <div className="absolute right-2 top-2 z-30">
                      <TooltipProvider>
                        <Tooltip delayDuration={100}>
                          <TooltipTrigger asChild>
                            <Button
                              variant="ghost"
                              size="icon"
                              className="h-8 w-8 border bg-background hover:bg-accent transition-all duration-100"
                              onClick={() => setExpandedSection('chat')}
                            >
                              <Maximize2 className="h-4 w-4" />
                            </Button>
                          </TooltipTrigger>
                          <TooltipContent side="bottom" align="end">
                            <p>채팅 영역 최대화</p>
                          </TooltipContent>
                        </Tooltip>
                      </TooltipProvider>
                    </div>
                    <ChatSection />
                  </div>
                </ResizablePanel>
                
                <ResizableHandle withHandle />
                
                <ResizablePanel defaultSize={50} minSize={20}>
                  <div 
                    className="relative bg-background h-full transition-all duration-200 ease-in-out text-sm"
                    style={{
                      transformOrigin: 'center',
                      ...(expandedSection === 'none' ? collapseAnimation : {})
                    }}
                  >
                    <div className="absolute right-2 top-2 z-30">
                      <TooltipProvider>
                        <Tooltip delayDuration={100}>
                          <TooltipTrigger asChild>
                            <Button
                              variant="ghost"
                              size="icon"
                              className="h-8 w-8 border bg-background hover:bg-accent transition-all duration-100"
                              onClick={() => setExpandedSection('table')}
                            >
                              <Maximize2 className="h-4 w-4" />
                            </Button>
                          </TooltipTrigger>
                          <TooltipContent side="bottom" align="end">
                            <p>테이블 영역 최대화</p>
                          </TooltipContent>
                        </Tooltip>
                      </TooltipProvider>
                    </div>
                    <TableSection />
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
    <div className="w-full h-full">
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
