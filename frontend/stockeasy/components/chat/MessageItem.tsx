'use client'

import { CSSProperties } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import remarkBreaks from 'remark-breaks'
import { ChatMessage } from './types'

interface MessageItemProps {
  message: ChatMessage
  isMobile: boolean
  windowWidth: number
}

export default function MessageItem({ message, isMobile, windowWidth }: MessageItemProps) {
  // AI 메시지 스타일
  const aiMessageStyle: CSSProperties = {
    backgroundColor: 'transparent',
    borderRadius: '0',
    padding: isMobile ? '8px 12px' : (windowWidth < 768 ? '9px 14px' : '10px 15px'),
    marginBottom: isMobile ? '10px' : '12px',
    width: '100%',
    boxShadow: 'none',
    lineHeight: '1.5',
    fontSize: isMobile ? '0.85rem' : (windowWidth < 768 ? '0.87rem' : '0.9rem'),
    wordBreak: 'break-word',
    boxSizing: 'border-box',
    maxWidth: '100%'
  }

  // 사용자 메시지 스타일
  const userMessageStyle: CSSProperties = {
    backgroundColor: '#f5f5f5',
    padding: isMobile ? '8px 12px' : (windowWidth < 768 ? '9px 13px' : '10px 14px'),
    borderRadius: isMobile ? '10px' : '12px',
    maxWidth: isMobile ? '95%' : (windowWidth < 768 ? '90%' : '85%'),
    width: 'auto',
    boxShadow: '0 1px 2px rgba(0, 0, 0, 0.1)',
    position: 'relative',
    border: '1px solid #e0e0e0',
    wordBreak: 'break-word'
  }

  return (
    <div 
      style={{
        marginBottom: '16px',
        display: 'flex',
        flexDirection: 'row',
        alignItems: 'center',
        justifyContent: message.role === 'user' ? 'flex-end' : 'flex-start',
        width: '100%'
      }}
    >
      <div style={message.role === 'assistant' ? aiMessageStyle : userMessageStyle}>
        {message.stockInfo && (
          <div style={{
            fontSize: isMobile ? '14px' : (windowWidth < 768 ? '15px' : '16px'),
            fontWeight: 'bold',
            color: '#10A37F',
            marginBottom: isMobile ? '3px' : '4px'
          }}>
            <span>{message.stockInfo.stockName}</span>
            <span style={{ 
              fontSize: 'smaller', 
              color: '#555', 
              fontWeight: 'normal' 
            }}>
              ({message.stockInfo.stockCode})
            </span>
          </div>
        )}
        <div style={{
          overflow: message.role === 'user' ? 'hidden' : 'visible',
          textOverflow: message.role === 'user' ? 'ellipsis' : 'clip',
          wordBreak: 'break-word',
          width: '100%',
          padding: message.role === 'user' ? '0' : (isMobile ? '3px 1px' : '4px 2px'),
          maxWidth: '100%'
        }}>
          {message.role === 'user' ? (
            // 사용자 메시지는 일반 텍스트로 표시
            <div style={{
              whiteSpace: 'pre-wrap',
              fontSize: isMobile ? '14px' : (windowWidth < 768 ? '15px' : '16px'),
              lineHeight: '1.6',
              letterSpacing: 'normal',
              wordBreak: 'break-word'
            }}>
              {message.content}
            </div>
          ) : (
            // AI 응답은 마크다운으로 렌더링
            <div className="markdown-content">
              <ReactMarkdown 
                remarkPlugins={[
                  remarkGfm,
                  [remarkBreaks, { breaks: false }]
                ]}
                components={{
                  text: ({node, ...props}) => <>{props.children}</>,
                  h1: ({node, ...props}) => <h1 style={{marginTop: '1.5em', marginBottom: '1em'}} {...props} />,
                  h2: ({node, ...props}) => <h2 style={{marginTop: '1.5em', marginBottom: '1em'}} {...props} />,
                  h3: ({node, ...props}) => <h3 style={{marginTop: '1.2em', marginBottom: '0.8em'}} {...props} />,
                  ul: ({node, ...props}) => <ul style={{marginTop: '0.5em', marginBottom: '1em', paddingLeft: '1.5em'}} {...props} />,
                  ol: ({node, ...props}) => <ol style={{marginTop: '0.5em', marginBottom: '1em', paddingLeft: '1.5em'}} {...props} />,
                  li: ({node, ...props}) => <li style={{marginBottom: '0'}} {...props} />,
                  p: ({node, ...props}) => <p style={{marginTop: '0.5em', marginBottom: '1em'}} {...props} />
                }}
              >
                {message.content}
              </ReactMarkdown>
            </div>
          )}
        </div>
      </div>
    </div>
  )
} 