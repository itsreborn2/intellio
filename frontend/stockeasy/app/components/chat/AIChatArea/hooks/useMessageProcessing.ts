/**
 * useMessageProcessing.ts
 * 메시지 처리 로직을 위한 커스텀 훅
 */
import { useCallback, useRef, useState, useEffect } from 'react';
import { toast } from 'sonner';
import { ChatMessage, StockOption, IStructuredChatResponseData, MessageComponent } from '../types';
import { createChatSession, streamChatMessage } from '@/services/api/chat';
import { IChatSession, IChatMessageDetail } from '@/types/api/chat';
import { useTimers } from './useTimers';
import { saveRecentStocksToStorage } from '../utils/stockDataUtils';
import { API_ENDPOINT_STOCKEASY } from '@/services/api/index';
import { v4 as uuidv4 } from 'uuid'; // UUID 라이브러리 가져오기

interface MessageProcessingOptions {
  onQuestionLimitExceeded?: () => void;
  onProcessingStart?: () => void;
  onProcessingComplete?: () => void;
  maxQuestions?: number;
}

// ChatStore 필요한 인터페이스만 정의
interface ChatStoreActions {
  addMessage: (message: IChatMessageDetail) => void;
  updateMessage: (id: string, message: Partial<IChatMessageDetail>) => void;
  removeMessage: (id: string) => void;
  setCurrentSession: (session: IChatSession | null) => void;
  setProcessing: (isProcessing: boolean) => void;
  getMessages: () => any[]; // 실제 타입은 useChatStore의 getUiMessages 반환 타입
}

interface MessageProcessingHook {
  elapsedTime: number;
  sendMessage: (
    inputMessage: string, 
    selectedStock: StockOption | null, 
    recentStocks: StockOption[],
    isFollowUp?: boolean
  ) => Promise<void>;
  saveAsPdf: (sessionId: string, expertMode?: boolean) => Promise<void>;
  isPdfLoading: boolean;
}

/**
 * 메시지 처리 로직을 담당하는 커스텀 훅
 * @param questionCount 현재 질문 횟수
 * @param messageHandlers 메시지 상태 관리를 위한 핸들러 함수들
 * @param currentSession 현재 채팅 세션 정보
 * @param options 설정 옵션
 * @returns 메시지 처리 관련 함수
 */
function useMessageProcessing(
  questionCount: number = 0,
  messageHandlers: ChatStoreActions,
  currentSession: IChatSession | null = null,
  options: MessageProcessingOptions = {}
): MessageProcessingHook {
  // 옵션 기본값
  const {
    onQuestionLimitExceeded = () => toast.error('오늘의 질문 할당량을 모두 소진하였습니다. 내일 다시 이용해주세요.'),
    onProcessingStart = () => {},
    onProcessingComplete = () => {},
    maxQuestions = 100
  } = options;

  // PDF 로딩 상태
  const [isPdfLoading, setIsPdfLoading] = useState<boolean>(false);

  // 핸들러 함수들 추출
  const { addMessage, updateMessage, removeMessage, setCurrentSession, setProcessing, getMessages } = messageHandlers;
  
  // 타이머 훅 사용
  const { elapsedTime, startTimer, stopTimer } = useTimers();

  // 스트리밍 응답을 위한 AI 메시지 ID 참조
  const assistantMessageId = useRef<string | null>(null);
  
  // 누적 응답 콘텐츠 저장
  const accumulatedContent = useRef<string>('');

  // PDF 저장 함수
  const saveAsPdf = useCallback(async (sessionId: string, expertMode: boolean = false) => {
    if (!sessionId) {
      toast.error('채팅 세션이 없습니다.');
      return;
    }
    
    try {
      setIsPdfLoading(true);
      
      // 백엔드에 PDF 생성 요청 (POST 메서드로 변경하고 expert_mode 전달)
      const response = await fetch(`${API_ENDPOINT_STOCKEASY}/chat/sessions/${sessionId}/save_pdf`, {
        method: 'POST',
        credentials: 'include',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          expert_mode: expertMode  // 전문가/주린이 모드 상태 전달
        })
      });
      
      if (!response.ok) {
        throw new Error(`PDF 생성 요청 실패: ${response.status}`);
      }
      
      const data = await response.json();
      
      // PDF 다운로드 링크 열기
      if (data.download_url) {
        // 새 탭에서 다운로드 링크 열기
        window.open(data.download_url, '_blank');
        toast.success('PDF 파일이 생성되었습니다.');
      } else {
        toast.error('PDF 다운로드 URL이 제공되지 않았습니다.');
      }
    } catch (error) {
      console.error('PDF 생성 중 오류:', error);
      toast.error('PDF 생성 중 오류가 발생했습니다.');
    } finally {
      setIsPdfLoading(false);
    }
  }, []);

  // 메시지 전송 처리 함수
  const sendMessage = useCallback(async (
    inputMessage: string,
    selectedStock: StockOption | null,
    recentStocks: StockOption[],
    isFollowUp: boolean = false
  ) => {
    // 입력값 검증 - 현재 세션이 있으면 종목이 없어도 가능
    if (!inputMessage.trim()) {
      toast.error('메시지를 입력해주세요.');
      return;
    }
    
    // 종목과 세션 모두 없는 경우
    if (!selectedStock && !currentSession) {
      toast.error('종목이 선택되지 않았거나 활성 세션이 없습니다.');
      return;
    }

    // 질문 횟수 제한 체크
    if (questionCount >= maxQuestions) {
      onQuestionLimitExceeded();
      return;
    }

    try {
      // 처리 시작 상태로 변경
      setProcessing(true);
      startTimer();
      onProcessingStart();

      // 채팅 세션 ID 초기화
      let sessionId = currentSession?.id;
      
      // 현재 세션에서 종목 정보 가져오기 (종목이 선택되지 않은 경우)
      const stockInfo = selectedStock ? {
        stockName: selectedStock.stockName || '',
        stockCode: selectedStock.value || ''
      } : currentSession ? {
        stockName: currentSession.stock_name || '',
        stockCode: currentSession.stock_code || ''
      } : {
        stockName: '',
        stockCode: ''
      };

      // 사용자 메시지 추가는 외부에서 이미 수행됨
      // AIChatArea 컴포넌트에서 직접 추가하여 동기화 문제 해결

      // 상태 표시 메시지 추가 (직접 IChatMessageDetail 타입으로 생성)
      const statusId = `status-${uuidv4()}`;
      const statusMessageObj: IChatMessageDetail = {
        id: statusId,
        role: 'status',
        content: '요청을 처리 중입니다...',
        chat_session_id: sessionId || '',
        stock_name: stockInfo.stockName,
        stock_code: stockInfo.stockCode,
        created_at: new Date().toISOString(),
        ok: true,
        status_message: '',
        metadata: {
          isProcessing: true,
          stockInfo,
          elapsed: 0
        }
      };

      // 메시지 목록에 상태 메시지 추가
      console.log('[MessageProcessing] 상태 메시지 추가 전:', statusMessageObj.id);
      addMessage(statusMessageObj);
      console.log('[MessageProcessing] 상태 메시지 추가 후:', statusMessageObj.id);
      
      // 채팅 세션이 없으면 새로 생성
      if (!sessionId) {
        try {
          // 종목이 반드시 있어야 함 (현재 세션이 없는 경우 위에서 이미 체크됨)
          if (!selectedStock) {
            throw new Error('세션이 없는 상태에서 종목이 선택되지 않았습니다.');
          }
          
          // 종목 정보 추출
          const stockName = selectedStock.stockName || '종목명';
          const stockCode = selectedStock.value || selectedStock.stockCode || '000000';
          
          // 종목명(종목코드) : 질문내용 형식으로 세션명 생성
          const session_name = `${stockName}(${stockCode}) : ${inputMessage}`;
          
          // 종목 추가 정보 구성 (현재 StockOption 인터페이스의 필드만 사용)
          const stockInfoData = {
            value: selectedStock.value,
            label: selectedStock.label,
            stockName: selectedStock.stockName,
            stockCode: selectedStock.stockCode,
            display: selectedStock.display
          };
          
          // 세션 생성 요청 (종목 정보 포함)
          const newSession = await createChatSession(
            session_name,
            stockCode,
            stockName,
            stockInfoData
          );
          
          sessionId = newSession.id;
          setCurrentSession(newSession);
          
          console.log('새 채팅 세션 생성:', newSession);
        } catch (error: any) {
          console.error('채팅 세션 생성 실패:', error);
          throw new Error(`채팅 세션 생성 실패: ${error.message || '알 수 없는 오류'}`);
        }
      }

      // 스트리밍 방식으로 메시지 전송
      await streamChatMessage(
        sessionId,
        inputMessage,
        stockInfo.stockCode,
        stockInfo.stockName,
        {
          onStart: () => {
            console.log('[MessageProcessing] 처리 시작:', statusMessageObj.id);
            // 상태 메시지 업데이트
            updateMessage(statusMessageObj.id, { 
              content: '처리를 시작합니다...', 
              metadata: {
                ...statusMessageObj.metadata,
                elapsed: elapsedTime,
                isProcessing: true
              }
            });
          },
          onAgentStart: (data) => {
            console.log('[MessageProcessing] 에이전트 시작 ', data );
            
            // 상태 메시지 업데이트 (에이전트 정보만 변경, 시간은 초기 시작 시간 유지)
            updateMessage(statusMessageObj.id, { 
              content: data.message, 
              metadata: {
                ...statusMessageObj.metadata,
                agent: data.agent,
                isProcessing: true
              }
            });
          },
          onAgentComplete: (data) => {
            console.log('[MessageProcessing] 에이전트 완료 ', data);
            
            // 상태 메시지 업데이트 (에이전트 정보만 변경, 시간은 초기 시작 시간 유지)
            updateMessage(statusMessageObj.id, { 
              content: data.message, 
              metadata: {
                ...statusMessageObj.metadata,
                agent: data.agent,
                isProcessing: true
              }
            });
          },
          onToken: (data) => {
            //console.log('[MessageProcessing] 토큰 msg id :', data.message_id);
            console.log('[MessageProcessing] 토큰 수신:', data.token.substring(0, 20) + '...');
            
            // 어시스턴트 응답 메시지 ID 생성 (없으면)
            if (!assistantMessageId.current) {
              console.log('[MessageProcessing] 토큰 msg id 생성:', data.message_id);
              // UUID를 문자열로 확실하게 변환
              assistantMessageId.current = String(data.message_id);
              accumulatedContent.current = ''; // 누적 콘텐츠 초기화
              
              // 상태 메시지 제거 (첫 번째 토큰이 도착했을 때)
              stopTimer();
              removeMessage(statusMessageObj.id);
              
              // 어시스턴트 메시지 초기 생성 (직접 IChatMessageDetail로 생성)
              const assistantMessageObj: IChatMessageDetail = {
                id: assistantMessageId.current,
                role: 'assistant',
                content: '',  // 빈 내용으로 시작
                chat_session_id: sessionId || '',
                stock_name: stockInfo.stockName,
                stock_code: stockInfo.stockCode,
                created_at: new Date().toISOString(),
                ok: true,
                status_message: '',
                metadata: {
                  stockInfo,
                  isProcessing: true
                }
              };
              
              addMessage(assistantMessageObj);
            }
            
            // 콘텐츠 누적하고 메시지 업데이트
            accumulatedContent.current += data.token;
            console.log('[MessageProcessing] 누적 콘텐츠 길이:', accumulatedContent.current.length);
            
            // React 상태 업데이트를 확실히 트리거하기 위한 처리
            // 새 객체를 생성하여 참조가 변경되도록 함
            const updatedContent = accumulatedContent.current;
            
            // 기존 메시지를 새 콘텐츠로 업데이트
            updateMessage(assistantMessageId.current, {
              content: updatedContent,
              created_at: new Date().toISOString()
            });
          },
          onComplete: (data) => {
            console.log('[MessageProcessing] 처리 완료:', data);
            
            console.log('[MessageProcessing] 어시스턴트 메시지 ID:', assistantMessageId.current);
            // 타이머 중지
            stopTimer();
            
            // 상태 메시지가 아직 존재하는 경우에만 제거 (토큰이 없을 경우)
            try {
              console.log('[MessageProcessing] 상태 메시지 제거 전 ChatContext 메시지 수:', getMessages?.()?.length || 0);
              console.log('[MessageProcessing] 상태 메시지 제거 시도:', statusMessageObj.id);
              
              // 제거 전 ID 문자열이 'status-'로 시작하는지 확인 (안전 검증)
              if (!statusMessageObj.id.startsWith('status-')) {
                console.warn('[MessageProcessing] 경고: 상태 메시지 ID가 올바른 형식이 아닙니다:', statusMessageObj.id);
                throw new Error('상태 메시지 ID 형식 불일치');
              }
              
              // 현재 메시지 목록 저장
              const currentMessages = getMessages?.() || [];
              // 사용자 메시지 수 확인
              const userMessageCount = currentMessages.filter(msg => msg.role === 'user').length;
              
              // 메시지 목록에서 상태 메시지 삭제
              removeMessage(statusMessageObj.id);
              
              // 구조화된 응답 데이터 처리
              const responseData = data as IStructuredChatResponseData;
              const { message_id, components, metadata, timestamp, elapsed } = responseData;
              
              // 스트리밍으로 이미 메시지가 생성되었다면 기존 메시지 업데이트
              if (assistantMessageId.current) {
                console.log('[MessageProcessing] 어시스턴트 메시지 업데이트 시작:', assistantMessageId.current);
                
                // 구조화된 컴포넌트 포함한 업데이트
                updateMessage(assistantMessageId.current, {
                  content: accumulatedContent.current, // 기존 누적된 텍스트 유지
                  metadata: {
                    components: components, // 구조화된 컴포넌트 추가
                    responseId: metadata?.responseId,
                    elapsed: elapsed || 0
                  }
                });
                
                console.log('[MessageProcessing] 어시스턴트 메시지 업데이트 완료:', assistantMessageId.current);
                
                // Zustand 스토어의 메시지도 업데이트
                const currentMessages = getMessages?.() || [];
                const messageToUpdate = currentMessages.find(msg => msg.id === assistantMessageId.current);
                
                if (messageToUpdate) {
                  console.log('[MessageProcessing] 메시지 업데이트 완료 (메시지 수:', getMessages?.()?.length || 0, ')');
                }
              } else {
                // 텍스트 콘텐츠 확인
                let textContent = '';
                console.log('[MessageProcessing] 구조화된 컴포넌트:', components);
                if (components && components.length > 0) {
                  // 첫 번째 텍스트 컴포넌트 내용을 기본 텍스트로 사용
                  const textComponent = components.find(c => c.type === 'paragraph' || c.type === 'heading');
                  if (textComponent) {
                    if (textComponent.type === 'paragraph') {
                      textContent = textComponent.content;
                    } else if (textComponent.type === 'heading') {
                      textContent = textComponent.content;
                    }
                  }
                }
                
                console.log('[MessageProcessing] 어시스턴트 메시지:', textContent);

                // 어시스턴트 메시지 직접 IChatMessageDetail 타입으로 생성
                const assistantMessageObj: IChatMessageDetail = {
                  id: message_id || `assistant-${uuidv4()}`,
                  role: 'assistant',
                  content: textContent,
                  content_expert: data.response_expert,
                  chat_session_id: sessionId || '',
                  stock_name: stockInfo.stockName,
                  stock_code: stockInfo.stockCode,
                  created_at: new Date(timestamp || Date.now()).toISOString(),
                  ok: true,
                  status_message: '',
                  metadata: {
                    stockInfo,
                    responseId: metadata?.responseId,
                    elapsed: elapsed || 0,
                    components: components // 메타데이터에 컴포넌트 추가
                  }
                };
                
                console.log('[MessageProcessing] 어시스턴트 메시지 객체 생성:', assistantMessageObj);

                // 현재 메시지 목록 저장
                const currentChatMessages = getMessages?.() || [];
                console.log('[MessageProcessing] 어시스턴트 메시지 추가 전 메시지 수:', currentChatMessages.length);
                
                // 어시스턴트 메시지 추가
                addMessage(assistantMessageObj);
                
                // 메시지 추가 후 상태 확인
                const updatedChatMessages = getMessages?.() || [];
                console.log('[MessageProcessing] 어시스턴트 메시지 추가 후 메시지 수:', updatedChatMessages.length);

                console.log('[MessageProcessing] 스토어에 스트리밍 없는 메시지 추가:', assistantMessageObj.id);
              }
            
            } catch (error) {
              console.log('[MessageProcessing] 상태 메시지가 이미 제거됨');
            }
            
            // 처리 완료 콜백 호출
            onProcessingComplete();

            // 디버깅 로그 정리 (components 변수 참조 오류 수정)
            console.log('[MessageProcessing] 처리 완료 및 응답 ID:', assistantMessageId.current);
            
            try {
              // 상태 메시지가 제거되었는지 확인 (구조화된 메시지 사용 시)
              const allMessages = getMessages?.() || [];
              const assistantMsg = allMessages.find(msg => msg.id === assistantMessageId.current);
              
              if (assistantMsg) {
                console.log('[MessageProcessing] 최종 메시지 메타데이터:', {
                  id: assistantMessageId.current,
                  componentsCount: assistantMsg.metadata?.components?.length || 0
                });
              }
            } catch (error) {
              console.log('[MessageProcessing] 메시지 검증 중 오류 발생');
            }

            // 스트리밍 완료 후 ChatContext 검증
            const finalContextMessages = getMessages?.() || [];
            console.log('[MessageProcessing] 처리 완료 후 상태 확인:', {
              chatContextCount: finalContextMessages.length,
              chatStoreCount: getMessages?.()?.length || 0
            });
            
            // ChatContext가 비어있고 ChatStore에 메시지가 있으면 복원
            if (finalContextMessages.length === 0 && getMessages?.()?.length > 0) {
              console.log('[MessageProcessing] ChatContext 메시지 복원 필요');
              // 복원 로직 또는 이벤트 발생
            }
          },
          onError: (error) => {
            console.error('[MessageProcessing] 스트리밍 오류:', error);
            
            // 타이머 중지
            stopTimer();
            
            // 상태 메시지를 오류 메시지로 변경
            updateMessage(statusMessageObj.id, {
              content: `오류가 발생했습니다: ${error.message || '알 수 없는 오류'}`,
              metadata: {
                ...statusMessageObj.metadata,
                isProcessing: false
              }
            });
            
            setProcessing(false);
            toast.error(`메시지 처리 중 오류: ${error.message || '알 수 없는 오류'}`);
          }
        },
        isFollowUp  // 후속질문 여부 전달
      );

      // 최근 조회 종목에 추가 (종목이 선택된 경우에만)
      if (selectedStock) {
        const updatedRecentStocks = [
          selectedStock,
          ...recentStocks.filter((s) => s.value !== selectedStock.value)
        ].slice(0, 5);
        
        saveRecentStocksToStorage(updatedRecentStocks);
      }

    } catch (error: any) {
      console.error('[MessageProcessing] 메시지 전송 오류:', error);
      
      // 타이머 중지
      stopTimer();
      
      setProcessing(false);
      toast.error(`메시지 전송 실패: ${error.message || '알 수 없는 오류'}`);
    }
  }, [
    addMessage,
    updateMessage,
    removeMessage,
    currentSession,
    setCurrentSession,
    setProcessing,
    elapsedTime,
    maxQuestions,
    onProcessingComplete,
    onProcessingStart,
    onQuestionLimitExceeded,
    questionCount,
    startTimer,
    stopTimer,
    getMessages
  ]);


  return {
    elapsedTime,
    sendMessage,
    saveAsPdf,
    isPdfLoading
  };
}

// 단일 내보내기 방식으로 수정
export default useMessageProcessing;