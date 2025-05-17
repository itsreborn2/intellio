'use client';

import { useEffect, useState, useRef, useMemo } from 'react';
import { useParams } from 'next/navigation';
import { useChatShare } from '@/services/api/useChatShare';
import { MessageBubble } from '@/app/components/chat/AIChatArea/components/MessageBubble';
import { ChatMessage } from '@/app/components/chat/AIChatArea/types';

// 로컬 스토리지 캐시 데이터 인터페이스
interface ICachedSharedChat {
  session: any;
  messages: any[];
  expiresAt: number;
}

// 로컬 스토리지 키 생성 유틸리티
const getLocalStorageKey = (uuid: string) => `sharedChat_${uuid}`;

// 로컬 스토리지 만료 시간 (1일)
const CACHE_EXPIRATION_MS = 24 * 60 * 60 * 1000; // 1일
//const CACHE_EXPIRATION_MS = 1 * 60 * 1000; // 1분

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
        
        // console.log(`[종목 정보 추출] ID: ${msg.id}`, {
        //   원본_종목명: msg.stock_name,
        //   원본_종목코드: msg.stock_code,
        //   세션_종목명: session?.stock_name,
        //   세션_종목코드: session?.stock_code,
        //   최종_종목명: stockName,
        //   최종_종목코드: stockCode
        // });
        
        // 중요: stockName 또는 stockCode가 있는 경우에만 stockInfo 추가
        if (stockName || stockCode) {
          // stockInfo 객체를 명시적으로 생성 (인터페이스와 일치)
          processedMsg.stockInfo = {
            stockName, // stockName 먼저 (인터페이스 순서)
            stockCode
          };
          
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

    const loadChatData = async () => {
      isRequestInProgress.current = true;
      setIsLoading(true);
      setError(null);

      // --- 모든 만료된 및 오래된 sharedChat 캐시 정리 ---
      try {
        console.log("[캐시 정리 시작] 만료/오래된 sharedChat_ 항목들을 확인합니다.");
        const MAX_CACHED_ITEMS = 50; // 예: 최대 50개 항목 유지
        let allSharedItems: { key: string, data: ICachedSharedChat }[] = [];

        // 1. 로컬스토리지에서 모든 sharedChat_ 아이템 수집
        for (let i = 0; i < localStorage.length; i++) {
          const key = localStorage.key(i);
          if (key && key.startsWith('sharedChat_')) {
            const cachedDataString = localStorage.getItem(key);
            if (cachedDataString) {
              try {
                const cachedData: ICachedSharedChat = JSON.parse(cachedDataString);
                allSharedItems.push({ key, data: cachedData });
              } catch (e) {
                // 파싱 실패한 데이터는 유효하지 않거나 손상된 데이터로 간주하고 즉시 삭제
                console.warn(`[캐시 정리 오류] ${key} 파싱 실패, 즉시 삭제:`, e);
                localStorage.removeItem(key); // 손상된 아이템 즉시 제거
              }
            }
          }
        }

        // 2. 만료된 항목 필터링 및 삭제
        const unexpiredItems: { key: string, data: ICachedSharedChat }[] = [];
        let itemsActuallyRemovedCount = 0;

        allSharedItems.forEach(item => {
          if (item.data.expiresAt <= Date.now()) {
            localStorage.removeItem(item.key);
            console.log(`[캐시 만료 삭제] ${item.key} (만료일: ${new Date(item.data.expiresAt).toISOString()})`);
            itemsActuallyRemovedCount++;
          } else {
            unexpiredItems.push(item);
          }
        });

        if (itemsActuallyRemovedCount > 0) {
            console.log(`[캐시 정리] 총 ${itemsActuallyRemovedCount}개의 만료된 항목이 삭제되었습니다.`);
        }

        // 3. 만료되지 않은 항목이 최대 개수를 초과하면, 가장 오래된 항목(expiresAt이 가장 빠른) 삭제
        if (unexpiredItems.length > MAX_CACHED_ITEMS) {
          console.log(`[캐시 정리] 만료되지 않은 항목(${unexpiredItems.length}개)이 최대치(${MAX_CACHED_ITEMS}개)를 초과. 오래된 항목 삭제 시작.`);
          // expiresAt 기준으로 오름차순 정렬 (가장 빨리 만료될 = 가장 오래된)
          unexpiredItems.sort((a, b) => a.data.expiresAt - b.data.expiresAt);
          
          const itemsToPurgeCount = unexpiredItems.length - MAX_CACHED_ITEMS;
          for (let i = 0; i < itemsToPurgeCount; i++) {
            const itemToPurge = unexpiredItems[i];
            localStorage.removeItem(itemToPurge.key);
            console.log(`[캐시 정리 - 용량 초과] 오래된 항목 삭제: ${itemToPurge.key} (만료 예정: ${new Date(itemToPurge.data.expiresAt).toISOString()})`);
            itemsActuallyRemovedCount++;
          }
          console.log(`[캐시 정리] 용량 관리를 위해 추가로 ${itemsToPurgeCount}개의 오래된 항목이 삭제되었습니다.`);
        }
        
        if (itemsActuallyRemovedCount > 0) {
             console.log(`[캐시 정리 완료] 총 ${itemsActuallyRemovedCount}개의 항목이 삭제 처리되었습니다.`);
        } else {
            console.log("[캐시 정리 완료] 삭제할 만료/오래된 항목 없음.");
        }

      } catch (e) {
        console.error("캐시 정리 중 오류 발생:", e);
      }
      // --- 정리 로직 끝 ---

      const localStorageKey = getLocalStorageKey(shareUuid);

      // 1. 로컬 스토리지에서 캐시된 데이터 확인
      try {
        const cachedDataString = localStorage.getItem(localStorageKey);
        if (cachedDataString) {
          const cachedData: ICachedSharedChat = JSON.parse(cachedDataString);
          if (cachedData.expiresAt > Date.now()) {
            console.log("[캐시 사용] 로컬 스토리지에서 데이터 로드:", cachedData);
            setSession(cachedData.session);
            setMessages(cachedData.messages || []);
            dataLoaded.current = true;
            setIsLoading(false);
            isRequestInProgress.current = false;
            return; // 캐시된 데이터 사용 시 여기서 종료
          } else {
            console.log("[캐시 만료] 로컬 스토리지 데이터 삭제:", localStorageKey);
            localStorage.removeItem(localStorageKey);
          }
        }
      } catch (e) {
        console.error("로컬 스토리지 읽기 오류:", e);
        // 오류 발생 시 캐시 사용하지 않고 계속 진행
      }

      // 2. 캐시 없거나 만료 시 백엔드에서 데이터 가져오기
      try {
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

        // 3. 가져온 데이터를 로컬 스토리지에 저장
        try {
          const cacheToStore: ICachedSharedChat = {
            session: data.session,
            messages: data.messages || [],
            expiresAt: Date.now() + CACHE_EXPIRATION_MS,
          };
          localStorage.setItem(localStorageKey, JSON.stringify(cacheToStore));
          console.log("[캐시 저장] 로컬 스토리지에 데이터 저장:", localStorageKey, cacheToStore);
        } catch (e) {
          console.error("로컬 스토리지 쓰기 오류:", e);
        }
        
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
      loadChatData();
    }
    
    return () => {
      // 컴포넌트 언마운트 시 isRequestInProgress.current를 false로 설정할 필요는
      // 이 로직에서는 크게 중요하지 않으나, 복잡한 상황을 대비해 유지할 수 있습니다.
      // isRequestInProgress.current = false; 
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
  

  return (
    <div className="flex-1 p-0 sm:p-2 md:p-4 w-full">
      {/* Fixed banner for shared report notification */}


      {/* Main content area with padding to offset the fixed banner */}
      <div className="w-full max-w-[800px] mx-auto px-0 sm:px-2 pt-4">
       <div className="mb-3 p-3 text-center text-green-700 bg-green-50 border border-green-600 rounded-md">
         공유된 보고서입니다.
       </div>
        {processedMessages.length === 0 ? (
          <div className="flex h-full items-center justify-center py-8">
            <p className="text-center text-gray-500">메시지가 없습니다.</p>
          </div>
        ) : (
          <div className="space-y-4 my-4">
            {processedMessages.map((message) => {
              
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
  );
} 