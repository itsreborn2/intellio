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
  isMobile
}: StockChatHistoryProps) {
  const [historyItems, setHistoryItems] = useState<IHistoryItem[]>([]) // 히스토리 아이템
  const [isLoading, setIsLoading] = useState(false) // 로딩 상태
  const [isLoadingAnalysis, setIsLoadingAnalysis] = useState(false) // 분석 결과 로딩 상태
  const [userId, setUserId] = useState<string | null>(null) // 사용자 ID
  const [chatSessions, setChatSessions] = useState<IChatSession[]>([]) // 채팅 세션 목록
  const [isLoadingChatSessions, setIsLoadingChatSessions] = useState(false) // 채팅 세션 로딩 상태
  
  // Zustand 스토어 사용
  const loadChatSession = useChatStore(state => state.loadChatSession)

  // 채팅 세션 목록 가져오기
  const fetchChatSessions = async () => {
    if (!userId) return
    
    setIsLoadingChatSessions(true)
    try {
      // 백엔드 API 호출
      const response = await axios.get<IChatSessionListResponse>(
        `${API_ENDPOINT_STOCKEASY}/chat/sessions`,
        { withCredentials: true }
      )
      
      if (response.data.ok && Array.isArray(response.data.sessions)) {
        setChatSessions(response.data.sessions)
        console.log('[히스토리 패널] 채팅 세션 로딩 완료', response.data.sessions.length)
      }
    } catch (error) {
      console.error('[히스토리 패널] 채팅 세션 가져오기 오류:', error)
    } finally {
      setIsLoadingChatSessions(false)
    }
  }
  
  // 채팅 세션 선택 처리
  const handleChatSessionSelect = async (session: IChatSession) => {
    console.log('[히스토리 패널] 채팅 세션 선택:', session.id)
    try {
      // 세션에 속한 메시지 가져오기
      const response = await axios.get(`${API_ENDPOINT_STOCKEASY}/chat/sessions/${session.id}/messages`, { withCredentials: true })
      
      if (response.data.ok && Array.isArray(response.data.messages)) {
        console.log('[히스토리 패널] 채팅 메시지 로드 성공', response.data.messages.length)
        
        // Zustand 스토어를 사용하여 메시지 저장 및 UI 업데이트
        loadChatSession(session.id, session.title, response.data.messages)
        
        // 모바일 환경에서는 히스토리 패널 닫기
        if (isMobile) {
          toggleHistoryPanel()
        }
      }
    } catch (error) {
      console.error('[히스토리 패널] 채팅 메시지 로드 오류:', error)
    }
  }
  
  // 히스토리 아이템 추가 함수
  const addHistoryItem = (stockName: string, stockCode: string | undefined, prompt: string) => {
    if (!userId) return
    
    console.log('[히스토리 패널] 새 아이템 추가:', { stockName, stockCode, prompt })
    
    const newItem: IHistoryItem = {
      id: Date.now().toString(),
      stockName,
      stockCode,
      prompt,
      timestamp: Date.now(),
      userId
    }
    
    // 새 아이템을 배열 맨 앞에 추가 (최신 항목이 맨 위에 표시)
    setHistoryItems(prev => [newItem, ...prev.slice(0, 19)]) // 최대 20개 항목 유지
    
    // 서버에 히스토리 저장
    saveHistoryToServer(newItem)
  }
  
  // 서버에 히스토리 저장
  const saveHistoryToServer = async (item: IHistoryItem) => {
    console.log('[히스토리 패널] 서버에 히스토리 저장 시작:', item.id)
    try {
      await axios.post('/api/user-history', item)
      console.log('[히스토리 패널] 서버에 히스토리 저장 완료:', item.id)
    } catch (error) {
      console.error('[히스토리 패널] 히스토리 저장 오류:', error)
    }
  }
  
  // 히스토리 분석 결과 불러오기
  const loadHistoryAnalysis = async (item: IHistoryItem) => {
    if (!item.responseId) {
      console.error('[히스토리 패널] 분석 결과 ID가 없습니다')
      return
    }
    
    console.log('[히스토리 패널] 선택된 아이템:', item)
    setIsLoadingAnalysis(true)
    try {
      // 분석 결과 불러오기 API 호출
      const response = await axios.get(`/api/analysis-result?responseId=${item.responseId}`)
      
      if (response.data && response.data.result) {
        console.log('[히스토리 패널] 분석 결과 로드 성공')
        // 분석 결과를 AIChatArea 컴포넌트에 전달하기 위한 이벤트 발생
        const event = new CustomEvent('loadHistoryAnalysis', {
          detail: {
            stockName: item.stockName,
            stockCode: item.stockCode,
            prompt: item.prompt,
            result: response.data.result,
            responseId: item.responseId
          }
        })
        window.dispatchEvent(event)
        
        // 모바일 환경에서는 히스토리 패널 닫기
        if (isMobile) {
          console.log('[히스토리 패널] 모바일 환경에서 패널 닫기')
          toggleHistoryPanel()
        }
      }
    } catch (error) {
      console.error('[히스토리 패널] 분석 결과 불러오기 오류:', error)
    } finally {
      setIsLoadingAnalysis(false)
    }
  }
  
  // 사용자 ID 가져오기
  useEffect(() => {
    console.log('[히스토리 패널] 사용자 ID 조회 시작')
    // 로컬 스토리지에서 사용자 ID 가져오기
    const storedUserId = localStorage.getItem('userId')
    if (storedUserId) {
      console.log('[히스토리 패널] 기존 사용자 ID 사용:', storedUserId)
      setUserId(storedUserId)
    } else {
      // 새 사용자 ID 생성 (실제로는 로그인 시스템에서 가져와야 함)
      const newUserId = `user_${Date.now()}`
      console.log('[히스토리 패널] 새 사용자 ID 생성:', newUserId)
      localStorage.setItem('userId', newUserId)
      setUserId(newUserId)
    }
  }, [])
  
  // 사용자 ID가 있을 때 히스토리 가져오기
  useEffect(() => {
    if (userId && isHistoryPanelOpen) {
      // 채팅 세션 목록도 함께 가져오기
      fetchChatSessions()
    }
  }, [userId, isHistoryPanelOpen])
  
  // 패널 상태 변경 로깅
  useEffect(() => {
    if (isHistoryPanelOpen) {
      //console.log('[히스토리 패널] 열림 - 애니메이션 시작')
    } else {
      //console.log('[히스토리 패널] 닫힘')
    }
  }, [isHistoryPanelOpen])
  
  // 전역 이벤트 리스너 설정 - 종목 선택 및 프롬프트 입력 감지
  useEffect(() => {
    // 커스텀 이벤트 리스너 추가
    const handleStockPrompt = (e: CustomEvent) => {
      const { stockName, stockCode, prompt, responseId } = e.detail
      console.log('[히스토리 패널] 새 종목 프롬프트 감지:', { stockName, stockCode, prompt })
      if (stockName && prompt) {
        addHistoryItem(stockName, stockCode, prompt)
      }
    }
    
    console.log('[히스토리 패널] 이벤트 리스너 등록: stockPromptSubmitted')
    // 이벤트 리스너 등록
    window.addEventListener('stockPromptSubmitted', handleStockPrompt as EventListener)
    
    // 컴포넌트 언마운트 시 이벤트 리스너 제거
    return () => {
      console.log('[히스토리 패널] 이벤트 리스너 제거: stockPromptSubmitted')
      window.removeEventListener('stockPromptSubmitted', handleStockPrompt as EventListener)
    }
  }, [userId]) // userId가 변경될 때마다 이벤트 리스너 재설정

  return (
    <div 
      className={`fixed left-[59px] top-0 h-full overflow-hidden`}
      style={{ 
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
        zIndex: 20, // 항상 높은 z-index를 유지하여 애니메이션이 완료될 때까지 보이게 함
        clipPath: isHistoryPanelOpen ? 'inset(0 0 0 0)' : 'inset(0 0 0 100%)', // 열리고 닫힐 때 클립 효과 추가
        visibility: isHistoryPanelOpen ? 'visible' : 'hidden', // 애니메이션 완료 후 숨김
        backgroundColor: '#282A2E', // 사이드바와 동일한 배경색
        borderRight: '1px solid #1e2022' // 사이드바와 동일한 테두리 색상
      }}
      onClick={(e) => {
        console.log('[히스토리 패널] 패널 영역 클릭')
        e.stopPropagation() // 패널 내부 클릭 시 이벤트 전파 중단하여 패널이 닫히지 않도록 함
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
                e.stopPropagation() // 이벤트 전파 중단하여 외부 클릭 이벤트 방지
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
          <div className="mb-4">
            <h4 className="text-xs font-medium text-[#a0a0a0] mb-2">채팅 내역</h4>
            
            {isLoadingChatSessions ? (
              <div className="flex items-center justify-center py-2">
                <Loader2 className="w-4 h-4 animate-spin mr-2 text-[#a0a0a0]" />
                <span className="text-xs text-[#a0a0a0]">채팅 내역을 확인 중...</span>
              </div>
            ) : chatSessions.length > 0 ? (
              <div className="space-y-2">
                {chatSessions.map((session) => (
                  <div 
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
                  </div>
                ))}
              </div>
            ) : (
              <div className="p-2 text-xs text-[#a0a0a0] text-center">
                채팅 세션이 없습니다
              </div>
            )}
          </div>
          
          <div className="h-px bg-[#1e2022] my-3"></div>
          
          {/* 히스토리 섹션 */}
          <h4 className="text-xs font-medium text-[#a0a0a0] mb-2">검색 히스토리</h4>
          
          {isLoading ? (
            <div className="flex flex-col items-center justify-center h-24 text-[#ececf1] text-sm">
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
            <div className="flex flex-col items-center justify-center h-24 text-[#ececf1] text-sm">
              <Clock className="w-8 h-8 mb-2 opacity-50 text-[#ececf1]" />
              <p>아직 저장된 히스토리가 없습니다</p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
} 