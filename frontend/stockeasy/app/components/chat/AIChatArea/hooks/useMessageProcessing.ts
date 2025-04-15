/**
 * useMessageProcessing.ts
 * 메시지 처리 로직을 위한 커스텀 훅
 */
import { useCallback, useRef, useState } from 'react';
import { toast } from 'sonner';
import { ChatMessage, StockOption } from '../types';
import { createChatSession, streamChatMessage } from '@/services/api/chat';
import { IChatSession } from '@/types/api/chat';
import { useTimers } from './useTimers';
import { saveRecentStocksToStorage } from '../utils/stockDataUtils';
import { API_ENDPOINT_STOCKEASY } from '@/services/api/index';

interface MessageProcessingOptions {
  onQuestionLimitExceeded?: () => void;
  onProcessingStart?: () => void;
  onProcessingComplete?: () => void;
  maxQuestions?: number;
}

// 메시지 처리에 필요한 콜백 함수들 정의
interface MessageHandlers {
  addMessage: (message: ChatMessage) => void;
  updateMessage: (id: string, message: Partial<ChatMessage>) => void;
  removeMessage: (id: string) => void;
  setCurrentSession: (session: IChatSession | null) => void;
  setProcessing: (isProcessing: boolean) => void;
}

interface MessageProcessingHook {
  elapsedTime: number;
  sendMessage: (
    inputMessage: string, 
    selectedStock: StockOption | null, 
    recentStocks: StockOption[]
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
export function useMessageProcessing(
  questionCount: number = 0,
  messageHandlers: MessageHandlers,
  currentSession: IChatSession | null = null,
  options: MessageProcessingOptions = {}
): MessageProcessingHook {
  // 옵션 기본값
  const {
    onQuestionLimitExceeded = () => toast.error('오늘의 질문 할당량을 모두 소진하였습니다. 내일 다시 이용해주세요.'),
    onProcessingStart = () => {},
    onProcessingComplete = () => {},
    maxQuestions = 30
  } = options;

  // PDF 로딩 상태
  const [isPdfLoading, setIsPdfLoading] = useState<boolean>(false);

  // 핸들러 함수들 추출
  const { addMessage, updateMessage, removeMessage, setCurrentSession, setProcessing } = messageHandlers;
  
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
    recentStocks: StockOption[]
  ) => {
    // 입력값 검증
    if (!inputMessage.trim() || !selectedStock) {
      toast.error('메시지 또는 종목이 선택되지 않았습니다.');
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

      // 사용자 메시지 추가
      const userMessageObj: ChatMessage = {
        id: `user-${Date.now()}`,
        role: 'user',
        content: inputMessage,
        timestamp: Date.now(),
        stockInfo: {
          stockName: selectedStock.stockName || '',
          stockCode: selectedStock.value || ''
        }
      };

      // 상태 표시 메시지 추가
      const statusMessageObj: ChatMessage = {
        id: `status-${Date.now()}`,
        role: 'status',
        content: '요청을 처리 중입니다...',
        timestamp: Date.now(),
        isProcessing: true,
        stockInfo: {
          stockName: selectedStock.stockName || '',
          stockCode: selectedStock.value || ''
        }
      };

      // 메시지 목록에 사용자 메시지와 처리 중 상태 메시지 추가
      addMessage(userMessageObj);
      addMessage(statusMessageObj);

      // 채팅 세션이 없으면 새로 생성
      let sessionId = currentSession?.id;

      if (!sessionId) {
        try {
          // 종목명(종목코드) : 질문내용 형식으로 세션명 생성
          const stockName = selectedStock.stockName || '종목명';
          const stockCode = selectedStock.stockCode || '000000';
          const session_name = `${stockName}(${stockCode}) : ${inputMessage}`;
          
          const newSession = await createChatSession(session_name);
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
        selectedStock.value || '',
        selectedStock.stockName || '',
        {
          onStart: () => {
            console.log('[MessageProcessing] 처리 시작:', statusMessageObj.id);
            // 상태 메시지 업데이트
            updateMessage(statusMessageObj.id, { 
              content: '처리를 시작합니다...', 
              elapsed: elapsedTime,
              elapsedStartTime: Date.now(), // 전체 진행 시간 시작점 설정
              isProcessing: true
            });
          },
          onAgentStart: (data) => {
            console.log('[MessageProcessing] 에이전트 시작 ', data );
            
            // 상태 메시지 업데이트 (에이전트 정보만 변경, 시간은 초기 시작 시간 유지)
            updateMessage(statusMessageObj.id, { 
              content: data.message, 
              agent: data.agent,
              isProcessing: true
              // elapsed와 elapsedStartTime은 변경하지 않음 (전체 시간 유지)
            });
          },
          onAgentComplete: (data) => {
            console.log('[MessageProcessing] 에이전트 완료 ', data);
            
            // 상태 메시지 업데이트 (에이전트 정보만 변경, 시간은 초기 시작 시간 유지)
            updateMessage(statusMessageObj.id, { 
              content: data.message, 
              agent: data.agent,
              isProcessing: true
              // elapsed와 elapsedStartTime은 변경하지 않음 (전체 시간 유지)
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
              
              // 어시스턴트 메시지 초기 생성
              const assistantMessageObj: ChatMessage = {
                id: assistantMessageId.current,
                role: 'assistant',
                content: '',  // 빈 내용으로 시작
                timestamp: Date.now(),
                stockInfo: {
                  stockName: selectedStock.stockName || '',
                  stockCode: selectedStock.value || ''
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
              timestamp: Date.now(),
            });
          },
          onComplete: (data) => {
            console.log('[MessageProcessing] 처리 완료:', data);
            
            // 타이머 중지
            stopTimer();
            
            // 상태 메시지가 아직 존재하는 경우에만 제거 (토큰이 없을 경우)
            try {
              removeMessage(statusMessageObj.id);
            } catch (error) {
              console.log('[MessageProcessing] 상태 메시지가 이미 제거됨');
            }
            
            // 스트리밍으로 이미 메시지가 생성되었다면 기존 메시지 업데이트
            if (assistantMessageId.current) {
              updateMessage(assistantMessageId.current, {
                content: data.response,
                content_expert: data.response_expert,
                responseId: data.metadata?.responseId,
                elapsed: data.elapsed || 0,
                _forceUpdate: Math.random() // 리렌더링 강제
              });
              
              // 참조 초기화
              assistantMessageId.current = null;
            } else {
              // 스트리밍 없이 완료된 경우 (혹시 모를 상황 대비)
              const assistantMessageObj: ChatMessage = {
                id: data.message_id || `ai-${Date.now()}`,
                role: 'assistant',
                content: data.response,
                content_expert: data.response_expert,
                timestamp: Date.now(),
                responseId: data.metadata?.responseId,
                elapsed: data.elapsed || 0,
                stockInfo: {
                  stockName: selectedStock.stockName || '',
                  stockCode: selectedStock.value || ''
                }
              };
              
              addMessage(assistantMessageObj);
            }
            
            setProcessing(false);
            
            // 처리 완료 콜백 호출
            onProcessingComplete();
          },
          onError: (error) => {
            console.error('[MessageProcessing] 스트리밍 오류:', error);
            
            // 타이머 중지
            stopTimer();
            
            // 상태 메시지를 오류 메시지로 변경
            updateMessage(statusMessageObj.id, {
              content: `오류가 발생했습니다: ${error.message || '알 수 없는 오류'}`,
              isProcessing: false,
              elapsedStartTime: undefined
            });
            
            setProcessing(false);
            toast.error(`메시지 처리 중 오류: ${error.message || '알 수 없는 오류'}`);
          }
        }
      );

      // 최근 조회 종목에 추가
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
    stopTimer
  ]);

  return {
    elapsedTime,
    sendMessage,
    saveAsPdf,
    isPdfLoading
  };
}

export default useMessageProcessing; 