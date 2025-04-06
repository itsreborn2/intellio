'use client'

import { useRef, useEffect } from 'react'
import { MessageListProps } from './types'
import MessageItem from './MessageItem'
import { SearchTimer, SearchingAnimation } from './LoadingIndicators'
import { createMessagesContainerStyle } from './styles'

export default function MessageList({ 
  messages, 
  isProcessing, 
  elapsedTime, 
  isMobile, 
  windowWidth 
}: MessageListProps) {
  // ref 정의
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const messagesContainerRef = useRef<HTMLDivElement>(null)
  
  // 메시지 추가 시 자동 스크롤
  useEffect(() => {
    if (messagesEndRef.current && messages.length > 0) {
      messagesEndRef.current.scrollIntoView({ behavior: 'auto' })
    }
  }, [messages])

  return (
    <div 
      className="messages-container" 
      ref={messagesContainerRef}
      style={createMessagesContainerStyle(isMobile, windowWidth, false, false)}
    >
      {messages.length === 0 ? (
        <div style={{ 
          textAlign: 'center', 
          color: '#888', 
          paddingTop: '20px',
          paddingBottom: '20px',
          fontSize: '16px',
          display: 'none' // 안내 텍스트 숨기기
        }}>
          종목을 선택하고 질문을 입력하세요.
        </div>
      ) : (
        messages.map(message => (
          <MessageItem
            key={message.id}
            message={message}
            isMobile={isMobile}
            windowWidth={windowWidth}
          />
        ))
      )}
      
      {/* 메시지 처리 중 로딩 표시 */}
      {isProcessing && (
        <div style={{
          display: 'flex',
          flexDirection: 'row',
          alignItems: 'flex-start',
          gap: isMobile ? '8px' : (windowWidth < 768 ? '10px' : '12px'),
          marginBottom: isMobile ? '12px' : '16px',
          flexWrap: 'wrap',
          width: '100%'
        }}>
          <SearchTimer 
            isMobile={isMobile} 
            windowWidth={windowWidth} 
            elapsedTime={elapsedTime} 
          />
          <SearchingAnimation 
            isMobile={isMobile} 
            windowWidth={windowWidth} 
          />
        </div>
      )}
      
      {/* 스크롤 위치 참조를 위한 빈 div */}
      <div ref={messagesEndRef} />
    </div>
  )
} 