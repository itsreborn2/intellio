"use client"

import { useApp } from "@/contexts/AppContext"
import { ChatSection } from './components/ChatSection'
import { TableSection } from './components/TableSection'
import { UploadSection } from './components/UploadSection'
import { useState } from 'react'
import { Maximize2, Minimize2 } from 'lucide-react'
import { Button } from "intellio-common/components/ui/button"
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "intellio-common/components/ui/tooltip"
import { useAuth } from "@/hooks/useAuth"

export const DefaultTemplate = () => {
  const { state } = useApp()
  const { isAuthenticated } = useAuth()
  const [expandedSection, setExpandedSection] = useState<'none' | 'chat' | 'table'>('none')

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
        return (
          <div className="h-full w-full flex flex-col">
            <div className={`relative bg-background ${
              expandedSection === 'chat' 
                ? 'h-full' 
                : expandedSection === 'table' 
                  ? 'hidden' 
                  : 'h-[50%]'
            }`}>
              <div className="absolute right-2 top-2 z-30">
                <TooltipProvider>
                  <Tooltip delayDuration={100}>
                    <TooltipTrigger asChild>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-8 w-8 border bg-background hover:bg-accent"
                        onClick={() => setExpandedSection(expandedSection === 'chat' ? 'none' : 'chat')}
                      >
                        {expandedSection === 'chat' ? (
                          <Minimize2 className="h-4 w-4" />
                        ) : (
                          <Maximize2 className="h-4 w-4" />
                        )}
                      </Button>
                    </TooltipTrigger>
                    <TooltipContent side="bottom" align="end">
                      <p>{expandedSection === 'chat' ? '복원' : '채팅 영역 최대화'}</p>
                    </TooltipContent>
                  </Tooltip>
                </TooltipProvider>
              </div>
              <ChatSection />
            </div>
            <div className={`relative bg-background ${
              expandedSection === 'table' 
                ? 'h-full' 
                : expandedSection === 'chat' 
                  ? 'hidden' 
                  : 'flex-1'
            } overflow-hidden`}>
              <div className="absolute right-2 top-2 z-30">
                <TooltipProvider>
                  <Tooltip delayDuration={100}>
                    <TooltipTrigger asChild>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-8 w-8 border bg-background hover:bg-accent"
                        onClick={() => setExpandedSection(expandedSection === 'table' ? 'none' : 'table')}
                      >
                        {expandedSection === 'table' ? (
                          <Minimize2 className="h-4 w-4" />
                        ) : (
                          <Maximize2 className="h-4 w-4" />
                        )}
                      </Button>
                    </TooltipTrigger>
                    <TooltipContent side="bottom" align="end">
                      <p>{expandedSection === 'table' ? '복원' : '테이블 영역 최대화'}</p>
                    </TooltipContent>
                  </Tooltip>
                </TooltipProvider>
              </div>
              <TableSection />
            </div>
          </div>
        )
      
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
      {renderContent()}
    </div>
  )
}
