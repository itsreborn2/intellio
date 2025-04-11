/**
 * MessageList.tsx
 * 채팅 메시지 목록을 표시하는 컴포넌트
 */
'use client';

import React, { useRef, useEffect, useCallback, useState, forwardRef, useImperativeHandle } from 'react';
import { ChatMessage } from '../types';
import MessageBubble from './MessageBubble';
import StatusMessage from './StatusMessage';
import { useIsMobile } from '../hooks';

export interface MessageListProps {
  messages: ChatMessage[];
  copyStates: Record<string, boolean>;
  expertMode: Record<string, boolean>;
  timerState: Record<string, number>;
  isInputCentered: boolean;
  isUserSending?: boolean; // 사용자가 직접 메시지를 보냈는지 여부
  onCopy: (id: string) => void;
  onToggleExpertMode: (id: string) => void;
}

export type MessageListRef = {
  scrollToBottom: () => void;
};

export const MessageList = forwardRef<MessageListRef, MessageListProps>((
  {
    messages,
    copyStates,
    expertMode,
    timerState,
    isInputCentered,
    isUserSending = false, // 기본값은 false
    onCopy,
    onToggleExpertMode
  }: MessageListProps,
  ref
) => {
  const isMobile = useIsMobile();
  const messagesTopRef = useRef<HTMLDivElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const messagesContainerRef = useRef<HTMLDivElement>(null);
  const [windowWidth, setWindowWidth] = React.useState<number>(0);
  const prevMessagesLengthRef = useRef<number>(0);
  const prevMessagesIdsRef = useRef<string[]>([]);
  
  // 상태 메시지에 대한 참조 맵 저장
  const statusMessageRefs = useRef<Map<string, HTMLDivElement>>(new Map());
  
  // 최초 로드 여부를 추적하는 ref 추가
  const isInitialLoadRef = useRef<boolean>(true);
  
  // useState로 변경하여 리렌더링이 정확하게 일어나도록 함
  const [isHistoryLoaded, setIsHistoryLoaded] = useState<boolean>(false); 
  const [historyLoadedTime, setHistoryLoadedTime] = useState<number | null>(null);
  
  // 자동 스크롤 활성화 상태 추가
  const [autoScrollEnabled, setAutoScrollEnabled] = useState<boolean>(false);
  const userMessageCountRef = useRef<number>(0);

  // 창 크기 변경 감지
  useEffect(() => {
    // 클라이언트 측에서만 실행
    if (typeof window !== 'undefined') {
      setWindowWidth(window.innerWidth);
      
      const handleResize = () => {
        setWindowWidth(window.innerWidth);
      };
      
      window.addEventListener('resize', handleResize);
      return () => {
        window.removeEventListener('resize', handleResize);
      };
    }
  }, []);

  // 스크롤을 맨 위로 올리는 함수
  const scrollToTop = useCallback(() => {
    if (messagesTopRef.current) {
      messagesTopRef.current.scrollIntoView({ behavior: 'auto' });
      console.log('[MessageList] 스크롤 맨 위로 이동 (scrollIntoView)');
    }
  }, []);
  
  // 스크롤 자동 이동 함수
  const scrollToBottom = useCallback(() => {
    if (messagesEndRef.current && messages.length > 0) {
      // 첫 번째 방법: scrollIntoView 사용
      messagesEndRef.current.scrollIntoView({ behavior: 'smooth' });
      
      // 두 번째 방법: 컨테이너의 scrollTop 설정 (더 확실한 방법)
      if (messagesContainerRef.current) {
        const container = messagesContainerRef.current;
        window.requestAnimationFrame(() => {
          container.scrollTop = container.scrollHeight;
          console.log('[MessageList] 스크롤 강제 이동 (scrollTop 설정):', container.scrollHeight);
          
          // 추가 안정성을 위해 약간의 지연 후 한 번 더 실행
          setTimeout(() => {
            container.scrollTop = container.scrollHeight;
          }, 100);
        });
      }
      
      console.log('[MessageList] 스크롤 맨 아래로 이동 시도 (scrollIntoView)');
    }
  }, [messages]);
  
  // ref를 통해 scrollToBottom 함수 노출
  useImperativeHandle(ref, () => ({
    scrollToBottom
  }), [scrollToBottom]);
  
  // 특정 상태 메시지로 스크롤하는 함수
  const scrollToStatusMessage = useCallback((messageId: string) => {
    const messageRef = statusMessageRefs.current.get(messageId);
    if (messageRef) {
      messageRef.scrollIntoView({ behavior: 'smooth', block: 'center' });
      console.log('[MessageList] 상태 메시지로 스크롤:', messageId);
    } else {
      console.log('[MessageList] 상태 메시지를 찾을 수 없음:', messageId);
      // 상태 메시지를 찾을 수 없으면 맨 아래로 스크롤
      scrollToBottom();
    }
  }, [scrollToBottom]);
  
  // 상태 메시지 스크롤 이벤트 리스너
  useEffect(() => {
    const handleScrollToStatusMessage = (event: CustomEvent) => {
      const messageId = event.detail?.messageId;
      if (messageId) {
        console.log('[MessageList] 상태 메시지 스크롤 이벤트 수신:', messageId);
        scrollToStatusMessage(messageId);
      }
    };
    
    window.addEventListener('scrollToStatusMessage', handleScrollToStatusMessage as EventListener);
    
    return () => {
      window.removeEventListener('scrollToStatusMessage', handleScrollToStatusMessage as EventListener);
    };
  }, [scrollToStatusMessage]);
  
  // 채팅 스크롤을 맨 위로 올리는 이벤트 리스너 추가
  useEffect(() => {
    const handleScrollChatToTop = () => {
      console.log('[MessageList] 스크롤 맨 위로 이벤트 수신');
      // 즉시 실행
      scrollToTop();
      // 렌더링이 완료된 후 한 번 더 실행
      window.requestAnimationFrame(() => {
        scrollToTop();
        // 추가 안정성을 위해 약간의 지연 후 한 번 더 실행
        setTimeout(scrollToTop, 100);
      });
    };
    
    window.addEventListener('scrollChatToTop', handleScrollChatToTop);
    
    return () => {
      window.removeEventListener('scrollChatToTop', handleScrollChatToTop);
    };
  }, [scrollToTop]);
  
  // 스크롤 위치 설정 시도 함수
  const attemptScrollToTop = useCallback(() => {
    // 마지막 히스토리 로드 이후 10초 이내에만 시도
    const now = Date.now();
    if (historyLoadedTime && (now - historyLoadedTime) < 10000) {
      scrollToTop();
    }
  }, [scrollToTop, historyLoadedTime]);
  
  // 채팅 히스토리 로드 감지 - 최초 로드 시에만 실행
  useEffect(() => {
    // 메시지 ID 목록 생성
    const currentMessageIds = messages.map(msg => msg.id);
    const prevMessageIds = prevMessagesIdsRef.current;
    
    // 최초 로드 및 메시지 변경 시에만 실행 (이후 사용자 질문은 무시)
    if (isInitialLoadRef.current && messages.length > 0) {
      console.log('[MessageList] 최초 메시지 로드 감지');
      
      // 최초 로드 후 스크롤 위치 설정
      if (prevMessagesLengthRef.current === 0) {
        console.log('[MessageList] 첫 채팅 내역 로드 감지');
        setIsHistoryLoaded(true);
        setHistoryLoadedTime(Date.now());
        
        // 렌더링이 완료된 후 스크롤을 맨 위로 이동
        window.requestAnimationFrame(() => {
          scrollToTop();
          // 지연 시간을 두고 추가로 시도
          setTimeout(scrollToTop, 300);
        });
      }
      // 완전히 새로운 채팅으로 변경된 경우 (ID가 일치하는 메시지가 하나도 없는 경우)
      else if (prevMessageIds.length > 0 && 
        !currentMessageIds.some(id => prevMessageIds.includes(id))) {
        console.log('[MessageList] 새로운 채팅 내역으로 변경 감지! 메시지 ID 불일치');
        setIsHistoryLoaded(true);
        setHistoryLoadedTime(Date.now());
        
        // 렌더링이 완료된 후 스크롤을 맨 위로 이동
        window.requestAnimationFrame(() => {
          scrollToTop();
          // 지연 시간을 두고 추가로 시도
          setTimeout(scrollToTop, 300);
        });
      }
      
      // 최초 로드 완료 후 플래그 해제
      isInitialLoadRef.current = false;
    }
    
    // 현재 메시지 개수와 ID 목록 저장
    prevMessagesLengthRef.current = messages.length;
    prevMessagesIdsRef.current = currentMessageIds;
  }, [messages, scrollToTop]);

  // 새 메시지 추가 시 스크롤 처리
  useEffect(() => {
    const currentLength = messages.length;
    const prevLength = prevMessagesLengthRef.current;
    
    // 현재 사용자 메시지 수 계산
    const userMessageCount = messages.filter(msg => msg.role === 'user').length;
    
    // 사용자 메시지가 2개 이상이면 자동 스크롤 활성화
    if (userMessageCount >= 2 && !autoScrollEnabled) {
      setAutoScrollEnabled(true);
      console.log('[MessageList] 사용자 메시지 2개 이상 감지, 자동 스크롤 활성화');
    }
    
    // 새 메시지가 추가된 경우
    if (currentLength > prevLength && currentLength > 0) {
      // 최초 로드가 아닌 경우에는 항상 스크롤 처리
      if (!isInitialLoadRef.current) {
        const lastMessage = messages[currentLength - 1];
        
        // 자동 스크롤이 활성화 되었거나 마지막 메시지가 사용자/어시스턴트 메시지인 경우 스크롤
        if (autoScrollEnabled || (lastMessage && (lastMessage.role === 'user' || lastMessage.role === 'assistant'))) {
          console.log('[MessageList] 새 메시지 추가로 스크롤 이동:', lastMessage.role, '(자동 스크롤:', autoScrollEnabled, ')');
          
          // 렌더링이 완료된 후 스크롤 실행
          window.requestAnimationFrame(() => {
            scrollToBottom();
          });
        }
      }
    }
  }, [messages, scrollToBottom, autoScrollEnabled]);

  // 컨테이너 스타일
  const messagesContainerStyle: React.CSSProperties = {
    overflowY: 'auto',
    overflowX: 'hidden',
    paddingTop: isMobile ? '10px' : (windowWidth < 768 ? '15px' : '20px'),
    paddingRight: isMobile ? '5px' : (windowWidth < 768 ? '8px' : '10px'),
    paddingBottom: isInputCentered ? (isMobile ? '10px' : (windowWidth < 768 ? '15px' : '20px')) : (isMobile ? '50px' : '60px'),
    paddingLeft: isMobile ? '5px' : (windowWidth < 768 ? '8px' : '10px'),
    margin: '0 auto',
    border: 'none',
    borderRadius: '0',
    backgroundColor: '#F4F4F4',
    width: isMobile ? '100%' : (windowWidth < 768 ? '95%' : (windowWidth < 1024 ? '85%' : '70%')),
    height: '100%',
    minHeight: 'calc(100% - 60px)',
    boxSizing: 'border-box',
    position: 'relative',
    display: isInputCentered ? 'none' : 'block',
    opacity: 1,
    maxWidth: '100%',
  };

  return (
    <div 
      className="messages-container" 
      ref={messagesContainerRef} 
      style={messagesContainerStyle}
    >
      {/* 스크롤 맨 위로 이동을 위한 참조 지점 */}
      <div ref={messagesTopRef} style={{ height: '1px', width: '100%' }} />
      
      {messages.length === 0 ? (
        <div style={{ 
          textAlign: 'center', 
          color: '#888', 
          padding: '20px 0',
          fontSize: '16px',
          display: 'none' // 안내 텍스트 숨기기
        }}>
          종목을 선택 후 분석을 요청하세요.
        </div>
      ) : (
        // 메시지 목록
        messages.map(message => (
          message.role === 'status' ? (
            <div 
              key={message.id} 
              ref={el => {
                if (el) statusMessageRefs.current.set(message.id, el);
                else statusMessageRefs.current.delete(message.id);
              }}
            >
              <StatusMessage message={message} />
            </div>
          ) : (
            <MessageBubble
              key={message.id}
              message={message}
              isExpertMode={!!expertMode[message.id]}
              timerState={timerState}
              onCopy={onCopy}
              onToggleExpertMode={onToggleExpertMode}
              windowWidth={windowWidth}
            />
          )
        ))
      )}
      
      {/* 스크롤 자동이동을 위한 참조 지점 */}
      <div ref={messagesEndRef} />
    </div>
  );
});

// React.memo를 적용하여 불필요한 리렌더링 방지
export default React.memo(MessageList); 