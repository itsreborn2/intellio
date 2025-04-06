'use client'

import { useState, useEffect } from 'react'
import AIChatArea from '../../components/chat'
import StockChatHistory from './StockChatHistory'

// 메인 컴포넌트
export default function AIChatAreaWrapper() {
  const [isHistoryPanelOpen, setIsHistoryPanelOpen] = useState(false)
  const [isMobile, setIsMobile] = useState(false)

  useEffect(() => {
    // 모바일 여부 확인
    const checkIsMobile = () => {
      setIsMobile(window.innerWidth <= 640)
    }
    
    checkIsMobile()
    window.addEventListener('resize', checkIsMobile)
    
    // 히스토리 토글 이벤트 리스너
    const handleToggleHistory = () => {
      setIsHistoryPanelOpen(prev => !prev)
    }
    
    window.addEventListener('toggleHistory', handleToggleHistory)
    
    return () => {
      window.removeEventListener('resize', checkIsMobile)
      window.removeEventListener('toggleHistory', handleToggleHistory)
    }
  }, [])

  // 히스토리 패널 토글 함수
  const toggleHistoryPanel = () => {
    setIsHistoryPanelOpen(prev => !prev)
  }

  return (
    <div className="relative flex h-full">
      {/* 채팅 영역 */}
      <div className="flex-1">
        <AIChatArea />
      </div>
      
      {/* 히스토리 패널 */}
      <StockChatHistory 
        isHistoryPanelOpen={isHistoryPanelOpen}
        toggleHistoryPanel={toggleHistoryPanel}
        isMobile={isMobile}
      />
    </div>
  )
}
