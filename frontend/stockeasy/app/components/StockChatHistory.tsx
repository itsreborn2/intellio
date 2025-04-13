'use client'

import { useState, useEffect } from 'react'
import axios from 'axios'
import { apiFetch, API_ENDPOINT_STOCKEASY } from 'services/api/index';
import { Clock, X, Loader2, ChevronRight } from 'lucide-react'
import { IHistoryItem } from '@/types'
import { useChatStore } from '@/stores/chatStore'
import { IChatMessageDetail, IChatSession } from '@/types/api/chat'

interface StockChatHistoryProps {
  isHistoryPanelOpen: boolean
  toggleHistoryPanel: () => void
  isMobile: boolean
  style?: React.CSSProperties
}

// 백엔드 API에서 반환하는 채팅 메시지 타입
interface IChatMessage {
  id: string
  chat_session_id: string
  role: string
  content: string
  metadata?: any
  created_at: string
  updated_at: string
}

// 백엔드 채팅 세션 응답 타입
interface IChatSessionListResponse {
  ok: boolean
  status_message: string
  sessions: IChatSession[]
  total: number
}

export default function StockChatHistory({
  isHistoryPanelOpen,
  toggleHistoryPanel,
  isMobile,
  style
}: StockChatHistoryProps) {
  const [historyItems, setHistoryItems] = useState<IHistoryItem[]>([]) // 히스토리 아이템
  const [isLoading, setIsLoading] = useState(false) // 로딩 상태
  const [isLoadingAnalysis, setIsLoadingAnalysis] = useState(false) // 분석 결과 로딩 상태
  const [userId, setUserId] = useState<string | null>(null) // 사용자 ID
  const [chatSessions, setChatSessions] = useState<IChatSession[]>([]) // 채팅 세션 목록
  const [isLoadingChatSessions, setIsLoadingChatSessions] = useState(false) // 채팅 세션 로딩 상태
  
  // Zustand 스토어 사용
  const loadChatSession = useChatStore(state => state.loadChatSession)

  // 쿠키에서 사용자 정보 가져오기
  const getUserInfoFromCookie = () => {
    try {
      // 쿠키 문자열 파싱
      const cookies = document.cookie.split(';').reduce((acc, cookie) => {
        const [key, value] = cookie.trim().split('=');
        acc[key.trim()] = value;
        return acc;
      }, {} as Record<string, string>);

      // user 쿠키가 있는지 확인
      if (cookies.user) {
        // 쿠키 값 디코딩 및 JSON 파싱
        let jsonString = decodeURIComponent(cookies.user);
        
        // 이중 따옴표로 감싸진 JSON 문자열인 경우 처리
        if (jsonString.startsWith('"') && jsonString.endsWith('"')) {
          jsonString = jsonString.slice(1, -1).replace(/\\"/g, '"');
        }
        
        // JSON 파싱하여 사용자 정보 추출
        const userInfo = JSON.parse(jsonString);
        
        // 사용자 ID 설정
        if (userInfo.id) {
          console.log('[히스토리 패널] 사용자 ID 쿠키에서 로드:', userInfo.id);
          setUserId(userInfo.id);
          return userInfo.id;
        }
      }
      return null;
    } catch (error) {
      console.error('[히스토리 패널] 사용자 정보 파싱 오류:', error);
      return null;
    }
  };

  // 채팅 세션 목록 가져오기
  const fetchChatSessions = async () => {
    // userId가 없을 경우 쿠키에서 다시 시도
    const currentUserId = userId || getUserInfoFromCookie();
    if (!currentUserId) {
      console.log('[히스토리 패널] 사용자 ID가 없어 채팅 세션을 가져올 수 없습니다.');
      return;
    }
    
    setIsLoadingChatSessions(true);
    try {
      // 백엔드 API 호출
      const response = await axios.get<IChatSessionListResponse>(
        `${API_ENDPOINT_STOCKEASY}/chat/sessions`,
        { withCredentials: true }
      );
      
      if (response.data.ok && Array.isArray(response.data.sessions)) {
        setChatSessions(response.data.sessions);
        console.log('[히스토리 패널] 채팅 세션 로딩 완료', response.data.sessions.length);
      }
    } catch (error) {
      console.error('[히스토리 패널] 채팅 세션 가져오기 오류:', error);
    } finally {
      setIsLoadingChatSessions(false);
    }
  };
  
  // 채팅 세션 선택 처리
  const handleChatSessionSelect = async (session: IChatSession) => {
    console.log('[히스토리 패널] 채팅 세션 선택:', session.id);
    try {
      // 세션에 속한 메시지 가져오기
      const response = await axios.get(`${API_ENDPOINT_STOCKEASY}/chat/sessions/${session.id}/messages`, { withCredentials: true });
      
      if (response.data.ok && Array.isArray(response.data.messages)) {
        console.log('[히스토리 패널] 채팅 메시지 로드 성공', response.data.messages.length);
        
        // Zustand 스토어를 사용하여 메시지 저장 및 UI 업데이트
        loadChatSession(session.id, session.title, response.data.messages);
        
        // 모바일 환경에서는 히스토리 패널 닫기
        if (isMobile) {
          toggleHistoryPanel();
        }
      }
    } catch (error) {
      console.error('[히스토리 패널] 채팅 메시지 로드 오류:', error);
    }
  };
  
  // 히스토리 아이템 추가 함수
  const addHistoryItem = (stockName: string, stockCode: string | undefined, prompt: string) => {
    // userId가 없을 경우 쿠키에서 다시 시도
    const currentUserId = userId || getUserInfoFromCookie();
    if (!currentUserId) {
      console.error('[히스토리 패널] 사용자 ID가 없어 히스토리를 추가할 수 없습니다.');
      return;
    }
    
    console.log('[히스토리 패널] 새 아이템 추가:', { stockName, stockCode, prompt });
    
    const newItem: IHistoryItem = {
      id: Date.now().toString(),
      stockName,
      stockCode,
      prompt,
      timestamp: Date.now(),
      userId: currentUserId
    };
    
    // 새 아이템을 배열 맨 앞에 추가 (최신 항목이 맨 위에 표시)
    setHistoryItems(prev => [newItem, ...prev.slice(0, 19)]); // 최대 20개 항목 유지
    
    // 서버에 히스토리 저장
    saveHistoryToServer(newItem);
  };
  
  // 서버에 히스토리 저장
  const saveHistoryToServer = async (item: IHistoryItem) => {
    console.log('[히스토리 패널] 서버에 히스토리 저장 시작:', item.id);
    try {
      await axios.post('/api/user-history', item);
      console.log('[히스토리 패널] 서버에 히스토리 저장 완료:', item.id);
    } catch (error) {
      console.error('[히스토리 패널] 히스토리 저장 오류:', error);
    }
  };
  
  // 히스토리 분석 결과 불러오기
  const loadHistoryAnalysis = async (item: IHistoryItem) => {
    if (!item.responseId) {
      console.error('[히스토리 패널] 분석 결과 ID가 없습니다');
      return;
    }
    
    console.log('[히스토리 패널] 선택된 아이템:', item);
    setIsLoadingAnalysis(true);
    try {
      // 분석 결과 불러오기 API 호출
      const response = await axios.get(`/api/analysis-result?responseId=${item.responseId}`);
      
      if (response.data && response.data.result) {
        console.log('[히스토리 패널] 분석 결과 로드 성공');
        // 분석 결과를 AIChatArea 컴포넌트에 전달하기 위한 이벤트 발생
        const event = new CustomEvent('loadHistoryAnalysis', {
          detail: {
            stockName: item.stockName,
            stockCode: item.stockCode,
            prompt: item.prompt,
            result: response.data.result,
            responseId: item.responseId
          }
        });
        window.dispatchEvent(event);
        
        // 모바일 환경에서는 히스토리 패널 닫기
        if (isMobile) {
          console.log('[히스토리 패널] 모바일 환경에서 패널 닫기');
          toggleHistoryPanel();
        }
      }
    } catch (error) {
      console.error('[히스토리 패널] 분석 결과 불러오기 오류:', error);
    } finally {
      setIsLoadingAnalysis(false);
    }
  };
  
  // 컴포넌트 마운트 시 쿠키에서 사용자 ID 가져오기
  useEffect(() => {
    const id = getUserInfoFromCookie();
    if (id) {
      setUserId(id);
    }
  }, []);
  
  // 히스토리 패널이 열릴 때마다 쿠키에서 사용자 ID 확인 후 채팅 세션 가져오기
  useEffect(() => {
    if (isHistoryPanelOpen) {
      // 사용자 ID가 없다면 쿠키에서 다시 시도
      if (!userId) {
        const id = getUserInfoFromCookie();
        if (id) {
          setUserId(id);
        }
      }
      
      // 채팅 세션 목록 가져오기 (userId가 있으면 즉시, 없으면 getUserInfoFromCookie 내에서 설정된 후)
      fetchChatSessions();
    }
  }, [isHistoryPanelOpen, userId]);
  
  // 패널 상태 변경 로깅
  useEffect(() => {
    if (isHistoryPanelOpen) {
      //console.log('[히스토리 패널] 열림 - 애니메이션 시작')
    } else {
      //console.log('[히스토리 패널] 닫힘')
    }
  }, [isHistoryPanelOpen]);
  
  // 전역 이벤트 리스너 설정 - 종목 선택 및 프롬프트 입력 감지
  useEffect(() => {
    // 커스텀 이벤트 리스너 추가
    const handleStockPrompt = (e: CustomEvent) => {
      const { stockName, stockCode, prompt, responseId } = e.detail;
      console.log('[히스토리 패널] 새 종목 프롬프트 감지:', { stockName, stockCode, prompt });
      if (stockName && prompt) {
        addHistoryItem(stockName, stockCode, prompt);
      }
    };
    
    console.log('[히스토리 패널] 이벤트 리스너 등록: stockPromptSubmitted');
    // 이벤트 리스너 등록
    window.addEventListener('stockPromptSubmitted', handleStockPrompt as EventListener);
    
    // 컴포넌트 언마운트 시 이벤트 리스너 제거
    return () => {
      console.log('[히스토리 패널] 이벤트 리스너 제거: stockPromptSubmitted');
      window.removeEventListener('stockPromptSubmitted', handleStockPrompt as EventListener);
    }
  }, [userId]); // userId가 변경될 때마다 이벤트 리스너 재설정

  return (
    <div 
      className={`fixed left-[59px] top-0 h-full overflow-hidden`}
      style={{
        position: 'fixed', 
        top: 0,
        height: '100vh',
        width: isHistoryPanelOpen ? '280px' : '0',
        transform: isHistoryPanelOpen ? 'translateX(0)' : 'translateX(-30px)',
        opacity: isHistoryPanelOpen ? 1 : 0,
        transition: isHistoryPanelOpen 
          ? 'width 0.35s cubic-bezier(0.25, 1, 0.5, 1), transform 0.35s cubic-bezier(0.25, 1, 0.5, 1), opacity 0.25s ease-in-out' 
          : 'width 0.4s cubic-bezier(0.4, 0, 0.2, 1), transform 0.4s cubic-bezier(0.4, 0, 0.2, 1), opacity 0.3s ease-in-out',
        pointerEvents: isHistoryPanelOpen ? 'auto' : 'none',
        transformOrigin: 'left center',
        boxShadow: isHistoryPanelOpen ? '4px 0 12px rgba(0, 0, 0, 0.2)' : 'none',
        zIndex: 20, 
        clipPath: isHistoryPanelOpen ? 'inset(0 0 0 0)' : 'inset(0 0 0 100%)', 
        visibility: isHistoryPanelOpen ? 'visible' : 'hidden', 
        backgroundColor: '#282A2E', 
        borderRight: '1px solid #1e2022',
        ...style
      }}
      onClick={(e) => {
        console.log('[히스토리 패널] 패널 영역 클릭')
        e.stopPropagation() 
      }}
    >
      <div className="flex flex-col h-full">
        {/* 헤더 영역 - 애니메이션 추가 */}
        <div 
          className="flex items-center justify-between p-3 border-b border-[#1e2022]"
          style={{
            opacity: isHistoryPanelOpen ? 1 : 0,
            transform: isHistoryPanelOpen ? 'translateX(0)' : 'translateX(-10px)',
            transition: isHistoryPanelOpen
              ? 'opacity 0.3s ease-out 0.1s, transform 0.3s ease-out 0.1s'
              : 'opacity 0.25s ease-in, transform 0.25s ease-in'
          }}
        >
          <div className="flex items-center justify-between w-full">
            <div className="flex items-center">
              <Clock className="w-4 h-4 mr-2 text-[#ececf1]" />
              <h3 className="text-sm font-medium text-[#ececf1]">최근 채팅 내역</h3>
            </div>
            <button 
              className="p-1 rounded-full hover:bg-[#3e4044]"
              onClick={(e) => {
                console.log('[히스토리 패널] 닫기 버튼 클릭')
                e.stopPropagation() 
                toggleHistoryPanel()
              }}
            >
              <X className="w-4 h-4 text-[#ececf1]" />
            </button>
          </div>
        </div>
        
        {/* 콘텐츠 영역 - 애니메이션 추가 */}
        <div 
          className="flex-1 overflow-y-auto p-2 text-[#ececf1]"
          style={{
            opacity: isHistoryPanelOpen ? 1 : 0,
            transform: isHistoryPanelOpen ? 'translateX(0)' : 'translateX(-15px)',
            transition: isHistoryPanelOpen
              ? 'opacity 0.3s ease-out 0.15s, transform 0.3s ease-out 0.15s'
              : 'opacity 0.2s ease-in, transform 0.2s ease-in'
          }}
        >
          {/* 채팅 세션 섹션 */}
          <div className="mt-4 flex-1">
            <h3 className="text-sm font-semibold text-gray-400 px-2">채팅 히스토리</h3>
            {isLoadingChatSessions ? (
              <div className="flex justify-center items-center h-32">
                <Loader2 className="h-6 w-6 animate-spin text-gray-400" />
              </div>
            ) : chatSessions.length > 0 ? (
              <div className="mt-2 space-y-1 overflow-y-auto pr-1">
                {chatSessions.map((session) => (
                  <button
                    key={session.id}
                    className="p-2 rounded border border-[#1e2022] hover:bg-[#3e4044] cursor-pointer transition-colors"
                    onClick={() => handleChatSessionSelect(session)}
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-medium text-[#ececf1]">{session.title}</span>
                      <span className="text-[10px] text-[#a0a0a0]">
                        {new Date(session.created_at || Date.now()).toLocaleDateString()}
                      </span>
                    </div>
                  </button>
                ))}
              </div>
            ) : (
              <div className="p-2 text-xs text-[#a0a0a0] text-center">
                채팅 세션이 없습니다
              </div>
            )}
          </div>

          {/* 히스토리 섹션 */}
          {isLoading ? (
            <div className="flex items-center justify-center h-20">
              <Loader2 className="w-8 h-8 mb-2 animate-spin" />
              <p>히스토리 불러오는 중...</p>
            </div>
          ) : historyItems.length > 0 ? (
            <div className="space-y-2">
              {historyItems.map((item) => (
                <div 
                  key={item.id} 
                  className="p-2 rounded border border-[#1e2022] hover:bg-[#3e4044] cursor-pointer transition-colors"
                  onClick={() => {
                    console.log('[히스토리 패널] 히스토리 아이템 클릭:', item.id)
                    if (item.responseId) {
                      loadHistoryAnalysis(item)
                    } else {
                      console.log('[히스토리 패널] 응답 ID가 없어 로드할 수 없음')
                    }
                  }}
                >
                  <div className="flex items-center justify-between mb-1">
                    <div className="flex items-center">
                      <span className="text-xs font-semibold text-[#ececf1]">{item.stockName}</span>
                      {item.stockCode && (
                        <span className="text-xs text-[#a0a0a0] ml-1">({item.stockCode})</span>
                      )}
                    </div>
                    <span className="text-[10px] text-[#a0a0a0]">
                      {new Date(item.timestamp).toLocaleDateString()}
                    </span>
                  </div>
                  <p className="text-xs text-[#ececf1] line-clamp-2 break-all">{item.prompt}</p>
                </div>
              ))}
            </div>
          ) : (
            <></>
          )}
        </div>
      </div>
    </div>
  )
} 