/**
 * MessageBubble.tsx
 * 채팅 메시지를 표시하는 UI 컴포넌트
 */
'use client';

import React, { useState, useEffect, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkBreaks from 'remark-breaks';
import { ChatMessage } from '../types';
import { useIsMobile } from '../hooks';
import { CopyButton } from './CopyButton';
import { toast } from 'sonner';
import ExpertModeToggle from './ExpertModeToggle';
import { useUserModeStore, useIsClient } from '@/stores/userModeStore';

interface MessageBubbleProps {
  message: ChatMessage;
  isExpertMode?: boolean; // 개별 메시지 전문가 모드 (옵션)
  timerState?: Record<string, number>;
  onCopy?: (id: string) => void; 
  onToggleExpertMode?: (id: string) => void;
  windowWidth: number;
}

// 마크다운 텍스트를 일반 텍스트로 변환하는 함수
function stripMarkdown(text: string): string {
  // 코드 블록 처리 (```code``` -> code)
  let plainText = text.replace(/```[\s\S]*?```/g, (match) => {
    return match.replace(/```(?:\w+)?\n([\s\S]*?)```/g, '$1');
  });
  
  // 인라인 코드 처리 (`code` -> code)
  plainText = plainText.replace(/`([^`]+)`/g, '$1');
  
  // 헤더 처리 (# Header -> Header)
  plainText = plainText.replace(/^(#+)\s+(.*)$/gm, '$2');
  
  // 볼드/이탤릭 처리 (**bold** -> bold, *italic* -> italic)
  plainText = plainText.replace(/(\*\*|__)(.*?)\1/g, '$2');
  plainText = plainText.replace(/(\*|_)(.*?)\1/g, '$2');
  
  // 링크 처리 ([text](url) -> text)
  plainText = plainText.replace(/\[([^\]]+)\]\([^)]+\)/g, '$1');
  
  // 이미지 처리 (![alt](url) -> alt)
  plainText = plainText.replace(/!\[([^\]]+)\]\([^)]+\)/g, '$1');
  
  // 목록 처리 (- item -> item, * item -> item, 1. item -> item)
  plainText = plainText.replace(/^\s*[-*]\s+(.*)$/gm, '$1');
  plainText = plainText.replace(/^\s*\d+\.\s+(.*)$/gm, '$1');
  
  // 인용구 처리 (> quote -> quote)
  plainText = plainText.replace(/^\s*>\s+(.*)$/gm, '$1');
  
  // 수평선 제거 (--- or *** or ___ -> 빈줄)
  plainText = plainText.replace(/^\s*([-*_])\1{2,}\s*$/gm, '');
  
  // 테이블 포맷팅 제거 (|---|---| -> 빈줄)
  plainText = plainText.replace(/^\|.*\|$/gm, (match) => {
    if (match.includes('---')) return '';
    return match.replace(/\|/g, ' ').trim();
  });
  
  // 다중 줄바꿈을 하나로 통일
  plainText = plainText.replace(/\n{3,}/g, '\n\n');
  
  return plainText.trim();
}

export function MessageBubble({
  message,
  isExpertMode: individualExpertMode,
  timerState,
  onCopy,
  onToggleExpertMode,
  windowWidth
}: MessageBubbleProps) {
  const isMobile = useIsMobile();
  const messageIdRef = useRef(message.id);
  
  // 클라이언트 측 마운트 상태 확인
  const isClient = useIsClient();
  
  // 앱 전체 사용자 모드 상태 가져오기
  const { mode: userMode } = useUserModeStore();
  const isGlobalExpertMode = isClient && userMode === 'expert';
  
  // 내부적으로 전문가 모드 상태 관리
  const [internalExpertMode, setInternalExpertMode] = useState(false);
  
  // 표시할 전문가 모드 결정 (우선순위: 글로벌 > 개별 > 내부)
  // 글로벌 전문가 모드가 켜져있으면 무조건 전문가 모드 내용 표시
  const isExpertMode = isGlobalExpertMode || (individualExpertMode !== undefined ? individualExpertMode : internalExpertMode);
  
  // 내부적으로 복사 상태 관리 (UI 표시용)
  const [isCopied, setIsCopied] = useState(false);
  
  // isCopied 상태 변화 감지를 위한 useEffect
  useEffect(() => {
    messageIdRef.current = message.id;
  }, [message.id]);
  
  // MessageBubble 컴포넌트의 render 부분에 디버깅 정보 추가
  useEffect(() => {
    // 1초 지연 후 컴포넌트 마운트 로그 출력 (렌더링 문제 확인용)
    const timer = setTimeout(() => {
      if (message.role === 'user') {
        console.log('[MessageBubble] 사용자 메시지 디버깅:', {
          id: message.id,
          role: message.role,
          content: message.content.substring(0, 30),
          isRendered: document.getElementById(`message-${message.id}`) !== null
        });
      }
    }, 1000);
    
    return () => clearTimeout(timer);
  }, [message.id, message.role, message.content]);
  
  // 사용자 메시지 스타일
  const userMessageStyle: React.CSSProperties = {
    backgroundColor: '#3F424A', 
    paddingTop: isMobile ? '8px' : (windowWidth < 768 ? '9px' : '10px'),
    paddingRight: isMobile ? '12px' : (windowWidth < 768 ? '13px' : '14px'),
    paddingLeft: isMobile ? '12px' : (windowWidth < 768 ? '13px' : '14px'),
    paddingBottom: '25px', // 버튼 공간 확보
    borderRadius: isMobile ? '10px' : '12px',
    maxWidth: isMobile ? '95%' : (windowWidth < 768 ? '90%' : '85%'),
    boxShadow: '0 1px 2px rgba(0, 0, 0, 0.2)',
    position: 'relative',
    border: '1px solid #3F424A',
    wordBreak: 'break-word',
    color: 'white'
  };
  
  // AI 메시지 스타일
  const aiMessageStyle: React.CSSProperties = {
    backgroundColor: 'transparent', // 박스 배경 제거
    borderRadius: '0', // 테두리 둥글기 제거
    paddingTop: isMobile ? '8px' : (windowWidth < 768 ? '9px' : '10px'),
    paddingRight: isMobile ? '12px' : (windowWidth < 768 ? '14px' : '15px'),
    paddingLeft: isMobile ? '12px' : (windowWidth < 768 ? '14px' : '15px'),
    paddingBottom: '25px', // 버튼 공간 확보
    marginBottom: isMobile ? '10px' : '12px',
    width: '100%', // 전체 너비 사용
    boxShadow: 'none', // 그림자 제거
    lineHeight: '1.5',
    fontSize: isMobile ? '0.85rem' : (windowWidth < 768 ? '0.87rem' : '0.9rem'),
    wordBreak: 'break-word',
    boxSizing: 'border-box',
    maxWidth: '100%', // 최대 너비 제한
    position: 'relative'
  };
  
  // 상태 메시지 스타일
  const statusMessageStyle: React.CSSProperties = {
    ...aiMessageStyle,
    backgroundColor: 'rgba(240, 240, 240, 0.5)',
    borderRadius: '8px',
    paddingTop: '8px',
    paddingRight: '12px',
    paddingBottom: '8px',
    paddingLeft: '12px',
    marginBottom: '10px'
  };
  
  // 마크다운 스타일
  const markdownStyles = `
    .markdown-content {
      font-size: ${isMobile ? '0.9rem' : (windowWidth < 768 ? '0.95rem' : '1rem')};
      line-height: 1.6;
      max-width: 100%;
      overflow-wrap: break-word;
      word-wrap: break-word;
    }
    .markdown-content p {
      margin-top: 0.5em;
      margin-bottom: 1em;
      white-space: pre-line;
      max-width: 100%;
    }
    .markdown-content ul, .markdown-content ol {
      margin-top: 0.5em;
      margin-bottom: 1em;
      padding-left: 1.5em;
    }

    .markdown-content li p {
      margin-top: 0;
      margin-bottom: 0.25em;
      white-space: pre-line;
    }

    .markdown-content blockquote {
      margin-left: 0;
      padding-left: 1em;
      border-left: 3px solid #ddd;
      color: #555;
      margin-top: 1em;
      margin-bottom: 1em;
      white-space: pre-line;
    }


  `;
  
  // 메시지 타입에 따른 스타일 선택
  const getMessageStyle = () => {
    if (message.role === 'user') return userMessageStyle;
    if (message.role === 'status') return statusMessageStyle;
    return aiMessageStyle;
  };

  // 표시할 메시지 내용 결정
  const getMessageContent = () => {
    if (isExpertMode && message.role === 'assistant' && message.content_expert) {
      return message.content_expert;
    }
    return message.content;
  };

  // 복사할 내용 결정
  const getContentToCopy = () => {
    if (isExpertMode && message.role === 'assistant' && message.content_expert) {
      return message.content_expert;
    }
    return message.content;
  };
  
  // 전문가 모드 토글 핸들러
  const handleToggleExpertMode = () => {
    // 내부 상태 업데이트
    setInternalExpertMode(!internalExpertMode);
    
    // 외부 콜백이 있는 경우 호출
    if (onToggleExpertMode) {
      onToggleExpertMode(message.id);
    }
  };

  // 복사 핸들러
  const handleCopy = () => {
    console.log('MessageBubble: CopyButton 클릭됨, 복사 처리 시작 (ID:', messageIdRef.current, ')');
    
    try {
      // 복사할 내용 결정
      const contentToCopy = getContentToCopy();
      
      // 복사할 내용이 없을 경우 처리
      if (!contentToCopy || contentToCopy.trim() === '') {
        toast.error('복사할 내용이 없습니다.');
        return;
      }
      
      // 마크다운 제거
      const plainTextContent = stripMarkdown(contentToCopy);
      
      // Clipboard API 사용
      if (navigator.clipboard && window.isSecureContext) {
        if (message.role === 'assistant') {
          navigator.clipboard.writeText(contentToCopy + '\n\n(주)인텔리오 - : https://wwww.intellio.kr/');
        } else {
          navigator.clipboard.writeText(contentToCopy);
        }
      } else {
        // Fallback: 텍스트 영역을 생성
        const textArea = document.createElement('textarea');
        textArea.value = message.role === 'assistant' 
          ? plainTextContent + '\n\n(주)인텔리오 - : https://wwww.intellio.kr/'
          : plainTextContent;
        
        textArea.style.position = 'absolute';
        textArea.style.left = '-999999px';
        textArea.style.top = '-999999px';
        document.body.appendChild(textArea);
        
        textArea.focus();
        textArea.select();
        document.execCommand('copy');
        
        document.body.removeChild(textArea);
      }
      
      // UI용 복사 상태 변경 - CopyButton이 자체적으로 처리하므로 여기서는 true만 설정
      setIsCopied(true);
      
      // 메시지 ID를 사용하여 상위 컴포넌트에 복사 완료 알림
      if (onCopy) {
        onCopy(messageIdRef.current);
      }
      
    } catch (error) {
      console.error('MessageBubble: 복사 실패:', error);
      toast.error('복사 중 오류가 발생했습니다.');
    }
  };
  
  return (
    <div
      style={{
        marginBottom: '16px',
        display: 'flex',
        flexDirection: 'column',
        alignItems: message.role === 'user' ? 'flex-end' : 'flex-start',
        width: '100%'
      }}
    >
      <style jsx>{markdownStyles}</style>
      
      <div
        style={{
          display: 'flex',
          flexDirection: 'row',
          alignItems: 'center',
          justifyContent: message.role === 'user' ? 'flex-end' : 'flex-start',
          width: '100%'
        }}
      >
        <div style={getMessageStyle()}>
          {/* 종목 정보 표시 */}
          {message.stockInfo && (
            <div style={{
              fontSize: isMobile ? '14px' : (windowWidth < 768 ? '15px' : '16px'),
              fontWeight: 'bold',
              color: message.role === 'user' ? '#4ECCA3' : '#10A37F',
              marginBottom: isMobile ? '3px' : '4px'
            }}>
              {message.stockInfo.stockName} ({message.stockInfo.stockCode})
            </div>
          )}
          
          <div style={{
            position: 'relative',
          }}>
            {/* 여기서 getMessageContent 함수를 호출하여 적절한 내용을 표시 */}
            {message.role === 'user' ? (
              <div style={{
                whiteSpace: 'pre-wrap',
                fontSize: isMobile ? '0.85rem' : (windowWidth < 768 ? '0.9rem' : '0.95rem'),
                lineHeight: '1.5',
              }}>
                {getMessageContent()}
              </div>
            ) : (
              <div className="markdown-content">
                <ReactMarkdown
                  remarkPlugins={[remarkGfm, remarkBreaks]}
                  components={{
                    // 마크다운 요소에 대한 스타일 및 속성 지정
                    p: ({ node, ...props }) => <p style={{ margin: '8px 0' }} {...props} />,
                    strong: ({ node, ...props }) => <strong style={{ fontWeight: 'bold' }} {...props} />,
                    em: ({ node, ...props }) => <em style={{ fontStyle: 'italic' }} {...props} />,
                    a: ({ node, ...props }) => <a style={{ color: '#10A37F', textDecoration: 'underline' }} target="_blank" rel="noopener noreferrer" {...props} />,
                    h1: ({ node, ...props }) => <h1 style={{ fontSize: '1.5em', margin: '16px 0', fontWeight: 'bold' }} {...props} />,
                    h2: ({ node, ...props }) => <h2 style={{ fontSize: '1.3em', margin: '14px 0', fontWeight: 'bold' }} {...props} />,
                    h3: ({ node, ...props }) => <h3 style={{ fontSize: '1.1em', margin: '12px 0', fontWeight: 'bold' }} {...props} />,
                    ul: ({ node, ...props }) => <ul style={{ paddingLeft: '20px', margin: '8px 0' }} {...props} />,
                    ol: ({ node, ...props }) => <ol style={{ paddingLeft: '20px', margin: '8px 0' }} {...props} />,
                    li: ({ node, ...props }) => <li style={{ margin: '4px 0' }} {...props} />,
                    code: ({ node, inline, className, children, ...props }: any) => (
                      <code
                        className={className}
                        style={{
                          backgroundColor: '#f0f0f0',
                          padding: inline ? '2px 4px' : '8px',
                          borderRadius: '4px',
                          fontFamily: 'monospace',
                          fontSize: '0.9em',
                          display: inline ? 'inline' : 'block',
                          overflowX: 'auto',
                          maxWidth: '100%',
                          whiteSpace: inline ? 'pre' : 'pre-wrap'
                        }}
                        {...props}
                      >
                        {children}
                      </code>
                    ),
                    table: ({ node, ...props }) => (
                      <div style={{ overflowX: 'auto', maxWidth: '100%', margin: '12px 0' }}>
                        <table style={{ borderCollapse: 'collapse', width: '100%' }} {...props} />
                      </div>
                    ),
                    thead: ({ node, ...props }) => <thead style={{ backgroundColor: '#f0f0f0' }} {...props} />,
                    th: ({ node, ...props }) => <th style={{ padding: '8px', border: '1px solid #ddd', textAlign: 'left' }} {...props} />,
                    td: ({ node, ...props }) => <td style={{ padding: '8px', border: '1px solid #ddd' }} {...props} />,
                    blockquote: ({ node, ...props }) => (
                      <blockquote
                        style={{
                          borderLeft: '4px solid #ddd',
                          paddingLeft: '16px',
                          margin: '12px 0',
                          fontStyle: 'italic',
                          color: '#555'
                        }}
                        {...props}
                      />
                    ),
                    hr: ({ node, ...props }) => <hr style={{ border: 'none', borderTop: '1px solid #ddd', margin: '16px 0' }} {...props} />
                  }}
                >
                  {getMessageContent()}
                </ReactMarkdown>
              </div>
            )}
          </div>

          {/* 복사 버튼 - 상태 메시지가 아닌 경우에만 표시 */}
          {message.role !== 'status' && (
            <div
              style={{
                position: 'absolute',
                bottom: '3px',
                right: message.role === 'user' ? '5px' : 'auto',
                left: message.role === 'assistant' ? '5px' : 'auto',
                width: '24px',
                height: '20px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              {/* CopyButton 컴포넌트 사용 */}
              <CopyButton 
                onClick={handleCopy}
                isCopied={isCopied}
                size="sm"
                label=""
                variant={message.role === 'user' ? 'user' : 'assistant'}
              />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// React.memo를 적용하여 props가 변경되지 않으면 리렌더링하지 않도록 최적화
export default React.memo(MessageBubble, (prevProps, nextProps) => {
  // ID가 다르면 무조건 리렌더링
  if (prevProps.message.id !== nextProps.message.id) {
    return false;
  }
  
  // 메시지 내용 변경 시 리렌더링
  if (prevProps.message.content !== nextProps.message.content) {
    return false;
  }
  
  // 전문가 모드 내용 변경 시 리렌더링
  if (prevProps.message.content_expert !== nextProps.message.content_expert) {
    return false;
  }
  
  // 타임스탬프 변경 시 리렌더링
  if (prevProps.message.timestamp !== nextProps.message.timestamp) {
    return false;
  }
  
  // _forceUpdate 항목이 있고 다르면 리렌더링
  if (prevProps.message._forceUpdate !== nextProps.message._forceUpdate) {
    return false;
  }
  
  // 전문가 모드 변경 시 리렌더링
  if (prevProps.isExpertMode !== nextProps.isExpertMode) {
    return false;
  }
  
  // 창 크기 변경 시 리렌더링
  if (prevProps.windowWidth !== nextProps.windowWidth) {
    return false;
  }
  
  // 타이머 상태 변경 시 리렌더링
  if (prevProps.timerState?.[prevProps.message.id] !== nextProps.timerState?.[nextProps.message.id]) {
    return false;
  }
  
  // 그 외의 경우 동일하다고 간주
  return true;
}); 