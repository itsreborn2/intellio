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

interface MessageBubbleProps {
  message: ChatMessage;
  isExpertMode?: boolean; // 선택적 속성으로 변경
  timerState?: Record<string, number>;
  onCopy?: (id: string) => void; // 선택적 속성으로 변경 (필요한 경우에만 사용)
  onToggleExpertMode?: (id: string) => void; // 선택적 속성으로 변경
  windowWidth: number;
}

export function MessageBubble({
  message,
  isExpertMode: externalExpertMode,
  timerState,
  onCopy,
  onToggleExpertMode,
  windowWidth
}: MessageBubbleProps) {
  const isMobile = useIsMobile();
  const messageIdRef = useRef(message.id);
  
  // 내부적으로 전문가 모드 상태 관리
  const [internalExpertMode, setInternalExpertMode] = useState(false);
  
  // 외부에서 전달된 isExpertMode가 있으면 사용, 없으면 내부 상태 사용
  const isExpertMode = externalExpertMode !== undefined ? externalExpertMode : internalExpertMode;
  
  // 내부적으로 복사 상태 관리 (UI 표시용)
  const [isCopied, setIsCopied] = useState(false);
  
  // isCopied 상태 변화 감지를 위한 useEffect
  useEffect(() => {
    messageIdRef.current = message.id;
  }, [message.id]);
  
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
    .markdown-content li {
      margin-top: 0;
      margin-bottom: 0;
      line-height: 1.3;
      padding-bottom: 0;
      white-space: normal;
    }
    .markdown-content li p {
      margin-top: 0;
      margin-bottom: 0;
      white-space: pre-line;
    }
    .markdown-content li + li {
      margin-top: 0;
    }
    .markdown-content h1, .markdown-content h2, .markdown-content h3, .markdown-content h4 {
      margin-top: 1.5em;
      margin-bottom: 1em;
      line-height: 1.3;
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
        textArea.value = contentToCopy;
        
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
            overflow: message.role === 'user' ? 'hidden' : 'visible',
            textOverflow: message.role === 'user' ? 'ellipsis' : 'clip',
            wordBreak: 'break-word',
            maxWidth: '100%'
          }}>
            {message.role === 'user' ? (
              // 사용자 메시지는 일반 텍스트로 표시
              <div style={{
                whiteSpace: 'pre-wrap',
                fontSize: isMobile ? '14px' : (windowWidth < 768 ? '15px' : '16px'),
                lineHeight: '1.6',
                letterSpacing: 'normal',
                wordBreak: 'break-word',
                color: 'white'
              }}>
                {message.content}
              </div>
            ) : message.role === 'status' ? (
              // 상태 메시지는 마크다운으로 표시 + 경과 시간
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
                {message.elapsed !== undefined && (
                  <div style={{
                    marginTop: '8px',
                    fontSize: isMobile ? '11px' : '12px',
                    color: 'rgb(170, 170, 170)',
                    textAlign: 'left',
                  }}>
                    {message.elapsedStartTime 
                      ? (timerState?.[message.id] || message.elapsed).toFixed(1)
                      : message.elapsed.toFixed(1)
                    }초
                  </div>
                )}
              </div>
            ) : (
              // AI 응답 메시지는 마크다운으로 표시 (전문가 모드 지원)
              <div className="markdown-content">
                {message.role === 'assistant' && message.content_expert && isExpertMode ? (
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
                    {message.content_expert}
                  </ReactMarkdown>
                ) : (
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
                )}
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

          {/* 전문가 모드 버튼 - 어시스턴트 메시지이고 전문가 모드 내용이 있는 경우에만 표시 */}
          {message.role === 'assistant' && message.content_expert && message.content_expert.trim() !== '' && (
            <div
              style={{
                position: 'absolute',
                bottom: '3px',
                left: '32px', // 복사 버튼 옆에 위치
              }}
            >
              <ExpertModeToggle 
                isExpertMode={isExpertMode} 
                onToggle={handleToggleExpertMode}
                size="sm"
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