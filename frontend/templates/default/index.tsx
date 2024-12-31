"use client"

import { useApp } from "@/contexts/AppContext"
import { ChatSection } from './components/ChatSection'
import { TableSection } from './components/TableSection'
import { UploadSection } from './components/UploadSection'
import { useState } from 'react'
import { ChevronUp, ChevronDown } from 'lucide-react'

export const DefaultTemplate = () => {
  const { state } = useApp()
  const [chatExpanded, setChatExpanded] = useState(true)

  const renderContent = () => {
    switch (state.currentView) {
      case 'upload':
        return (
          <div className="w-full h-full flex items-center justify-center bg-background">
            <UploadSection />
          </div>
        )
      
      case 'table':
      case 'chat':
        return (
          <div className="h-full w-full flex flex-col">
            <div className={`${chatExpanded ? 'h-[50%]' : 'hidden'} bg-background`}>
              <ChatSection />
            </div>
            <div className="relative">
              <button
                className="absolute left-1/2 -translate-x-1/2 -top-3 z-30 bg-background border rounded-full p-1 shadow-md hover:bg-muted/50 transition-colors"
                onClick={() => setChatExpanded(!chatExpanded)}
              >
                {chatExpanded ? (
                  <ChevronUp className="h-4 w-4" />
                ) : (
                  <ChevronDown className="h-4 w-4" />
                )}
              </button>
            </div>
            <div className="flex-1 bg-background overflow-auto">
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
    <div className="h-full">
      {renderContent()}
    </div>
  )
}
