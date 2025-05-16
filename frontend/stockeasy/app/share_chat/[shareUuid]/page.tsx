'use client';

import { useEffect, useState, useRef, useMemo } from 'react';
import { useParams } from 'next/navigation';
import { useChatShare } from '@/services/api/useChatShare';
import { MessageBubble } from '@/app/components/chat/AIChatArea/components/MessageBubble';
import { ChatMessage } from '@/app/components/chat/AIChatArea/types';

// 로딩 스피너 컴포넌트 내부 정의
function LoadingSpinner({ size = "lg" }: { size?: "sm" | "md" | "lg" }) {
  const sizeClasses = {
    sm: "h-4 w-4 border-2",
    md: "h-8 w-8 border-2",
    lg: "h-12 w-12 border-4"
  };
  
  return (
    <div
      className={`animate-spin rounded-full border-t-blue-500 border-r-transparent border-b-blue-500 border-l-transparent ${sizeClasses[size]}`}
    />
  );
}

export default function SharedChatPage() {
  const params = useParams();
  const shareUuid = params.shareUuid as string;
  const { getSharedChat } = useChatShare();
  
  const [session, setSession] = useState<any>(null);
  const [messages, setMessages] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [windowWidth, setWindowWidth] = useState<number>(typeof window !== 'undefined' ? window.innerWidth : 1200);
  
  // 중복 요청 및 데이터 로드 상태 추적
  const isRequestInProgress = useRef(false);
  const dataLoaded = useRef(false);
  
  // 메시지 처리를 위한 상태
  const [processedMessages, setProcessedMessages] = useState<ChatMessage[]>([]);
  const [copyStates, setCopyStates] = useState<Record<string, boolean>>({});
  const [expertMode, setExpertMode] = useState<Record<string, boolean>>({});
  
  // 메시지 처리 함수 (중복 제거 및 종목 정보 설정)
  const processMessages = useMemo(() => (msgs: any[]) => {
    console.log('[processMessages] 처리 시작, 메시지 수:', msgs.length);
    
    // 사용자 메시지에 종목 정보 적용 및 중복 제거
    const uniqueIds = new Set();
    
    // 중요: Map을 이용해 처리된 메시지를 추적 (참조 문제 방지)
    const processed: ChatMessage[] = [];
    
    msgs.forEach(msg => {
      // ID가 이미 있으면 중복 메시지이므로 제외
      if (uniqueIds.has(msg.id)) return;
      uniqueIds.add(msg.id);
      
      // 디버깅: 원본 메시지 구조 확인
      console.log(`[원본 메시지] ID: ${msg.id}, 역할: ${msg.role}`, {
        stock_code: msg.stock_code,
        stock_name: msg.stock_name,
        content: msg.content?.substring(0, 20) + '...'
      });
      
      // 기본 메시지 객체 생성
      const processedMsg: ChatMessage = {
        id: msg.id,
        role: msg.role as 'user' | 'assistant' | 'status',
        content: msg.content || '',
        content_expert: msg.content_expert,
        timestamp: new Date(msg.created_at || Date.now()).getTime(),
        components: msg.components || []
      };
      
      // 사용자 메시지인 경우에만 stockInfo 추가
      if (msg.role === 'user') {
        // 중요: 종목명과 종목코드를 명시적으로 변수에 저장
        const stockName = msg.stock_name || session?.stock_name || '';
        const stockCode = msg.stock_code || session?.stock_code || '';
        
        console.log(`[종목 정보 추출] ID: ${msg.id}`, {
          원본_종목명: msg.stock_name,
          원본_종목코드: msg.stock_code,
          세션_종목명: session?.stock_name,
          세션_종목코드: session?.stock_code,
          최종_종목명: stockName,
          최종_종목코드: stockCode
        });
        
        // 중요: stockName 또는 stockCode가 있는 경우에만 stockInfo 추가
        if (stockName || stockCode) {
          // stockInfo 객체를 명시적으로 생성 (인터페이스와 일치)
          processedMsg.stockInfo = {
            stockName, // stockName 먼저 (인터페이스 순서)
            stockCode
          };
          
          // 디버깅: 생성된 stockInfo 객체 확인
          console.log(`[stockInfo 생성됨] ID: ${msg.id}`, processedMsg.stockInfo);
        }
      }
      
      // 배열에 추가 (push 사용)
      processed.push(processedMsg);
    });
    
    console.log('[processMessages] 처리 완료, 결과 메시지 수:', processed.length);
    return processed;
  }, [session]);
  
  // 창 크기 이벤트 리스너
  useEffect(() => {
    const handleResize = () => {
      setWindowWidth(window.innerWidth);
    };
    
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);
  
  // 데이터 로딩
  useEffect(() => {
    if (isRequestInProgress.current || dataLoaded.current) {
      return;
    }
    
    const fetchSharedChat = async () => {
      try {
        isRequestInProgress.current = true;
        setIsLoading(true);
        setError(null);
        
        const data = await getSharedChat(shareUuid);
        console.log("[API 응답] 공유된 채팅 데이터:", {
          세션_정보: data.session ? {
            title: data.session.title,
            stock_code: data.session.stock_code,
            stock_name: data.session.stock_name
          } : null,
          메시지_수: data.messages?.length || 0
        });
        
        setSession(data.session);
        setMessages(data.messages || []);
        
        dataLoaded.current = true;
      } catch (err) {
        console.error('공유 채팅 로드 실패:', err);
        setError('공유된 채팅을 불러오는데 실패했습니다.');
      } finally {
        setIsLoading(false);
        isRequestInProgress.current = false;
      }
    };
    
    if (shareUuid) {
      fetchSharedChat();
    }
    
    return () => {
      isRequestInProgress.current = false;
    };
  }, [shareUuid, getSharedChat]);
  
  // 메시지 처리 (중복 제거, 형식 변환)
  useEffect(() => {
    if (messages.length > 0) {
      console.log('[메시지 처리 시작] 원본 메시지 수:', messages.length);
      
      // 중요: processMessages 함수 결과를 바로 변수에 할당
      const processed = processMessages(messages);
      
      // 사용자 메시지 디버깅
      const userMessages = processed.filter(msg => msg.role === 'user');
      console.log(`[사용자 메시지 개수] 총 ${userMessages.length}개`);
      
      userMessages.forEach(msg => {
        console.log(`[사용자 메시지] ID: ${msg.id}`, {
          내용: msg.content?.substring(0, 20) + '...',
          종목정보: msg.stockInfo 
            ? `stockName: "${msg.stockInfo.stockName}", stockCode: "${msg.stockInfo.stockCode}"`
            : '없음'
        });
      });
      
      // 최종 상태 업데이트 전에 마지막 검증
      console.log('[최종 검증] processedMessages 배열:', 
        processed.map(msg => ({
          id: msg.id,
          role: msg.role,
          hasStockInfo: !!msg.stockInfo,
          stockInfo: msg.stockInfo
        }))
      );
      
      // 상태 업데이트
      setProcessedMessages(processed);
      
      // 메시지 ID 기반으로 초기 상태 설정
      const initialCopyStates: Record<string, boolean> = {};
      const initialExpertMode: Record<string, boolean> = {};
      
      processed.forEach(msg => {
        initialCopyStates[msg.id] = false;
        initialExpertMode[msg.id] = false;
      });
      
      setCopyStates(initialCopyStates);
      setExpertMode(initialExpertMode);
      
      console.log('[메시지 처리 완료]');
    }
  }, [messages, processMessages]);
  
  // 복사 핸들러
  const handleCopy = (id: string) => {
    setCopyStates(prev => ({
      ...prev,
      [id]: true
    }));
    
    // 잠시 후 복사 상태 초기화
    setTimeout(() => {
      setCopyStates(prev => ({
        ...prev,
        [id]: false
      }));
    }, 2000);
  };
  
  // 전문가 모드 토글 핸들러
  const handleToggleExpertMode = (id: string) => {
    setExpertMode(prev => ({
      ...prev,
      [id]: !prev[id]
    }));
  };
  
  if (isLoading) {
    return (
      <div className="flex justify-center items-center min-h-screen">
        <LoadingSpinner size="lg" />
      </div>
    );
  }
  
  if (error) {
    return (
      <div className="flex justify-center items-center min-h-screen">
        <div className="p-4 rounded-md bg-red-50 text-red-600">
          {error}
        </div>
      </div>
    );
  }
  
  // 렌더링 직전 디버깅 로그
  console.log('[렌더링 직전] 처리된 메시지:', 
    processedMessages.map(msg => ({
      id: msg.id, 
      role: msg.role,
      hasStockInfo: !!msg.stockInfo,
      stockInfoDetails: msg.stockInfo
    }))
  );
  
  return (
    <div className="flex-1 p-0 sm:p-2 md:p-4 overflow-auto w-full">
      <div className="w-full max-w-[800px] mx-auto px-0 sm:px-2">
        <div className="messages-container" style={{
          overflow: 'hidden auto',
          padding: '20px 10px 60px',
          margin: '0px auto',
          border: 'none',
          borderRadius: '0px',
          backgroundColor: 'rgb(244, 244, 244)',
          boxSizing: 'border-box',
          width: '100%',
          height: '100%',
          minHeight: 'calc(100% - 60px)'
        }}>
          {processedMessages.length === 0 ? (
            <div className="flex h-full items-center justify-center py-8">
              <p className="text-center text-gray-500">메시지가 없습니다.</p>
            </div>
          ) : (
            <div className="space-y-4 my-4">
              {processedMessages.map((message) => {
                // 렌더링 직전 각 메시지 검증
                if (message.role === 'user') {
                  console.log(`[메시지 렌더링] ID: ${message.id}, stockInfo:`, message.stockInfo);
                }
                
                return (
                  <MessageBubble
                    key={message.id}
                    message={message}
                    windowWidth={windowWidth}
                    isExpertMode={expertMode[message.id]}
                    onCopy={() => handleCopy(message.id)}
                    onToggleExpertMode={() => handleToggleExpertMode(message.id)}
                    timerState={{}}
                  />
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
} 