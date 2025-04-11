import { apiFetch, API_ENDPOINT_STOCKEASY } from './index';
import { 
  IChatRequest, 
  IChatResponse, 
  IChatSessionCreateRequest, 
  IChatSession,
  IChatMessageCreateRequest,
  IChatMessageDetail,
  IChatSessionListResponse,
  IChatMessageListResponse
} from '@/types/api/chat';



/**
 * 새 채팅 세션을 생성합니다.
 * @param title 세션 제목 (기본값: "새 채팅")
 * @returns 생성된 채팅 세션 정보
 */
export const createChatSession = async (
  title: string = "새 채팅"
): Promise<IChatSession> => {
  const request: IChatSessionCreateRequest = {
    title
  };

  const response = await apiFetch(`${API_ENDPOINT_STOCKEASY}/chat/sessions`, {
    method: 'POST',
    body: JSON.stringify(request)
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || '채팅 세션 생성에 실패했습니다.');
  }

  return response.json();
};

/**
 * 사용자의 채팅 세션 목록을 조회합니다.
 * @param isActive 활성화 상태 필터 (선택)
 * @returns 채팅 세션 목록
 */
export const getChatSessions = async (
  isActive?: boolean
): Promise<IChatSessionListResponse> => {
  const queryParams = isActive !== undefined ? `?is_active=${isActive}` : '';
  const response = await apiFetch(`${API_ENDPOINT_STOCKEASY}/chat/sessions${queryParams}`);

  if (!response.ok) {
    throw new Error('채팅 세션 목록을 가져오는데 실패했습니다.');
  }

  return response.json();
};

/**
 * 채팅 세션 메시지를 생성합니다.
 * @param sessionId 채팅 세션 ID
 * @param message 메시지 내용
 * @param stockCode 종목 코드
 * @param stockName 종목 이름
 * @returns 생성된 메시지 정보
 */
export const createChatMessage = async (
  sessionId: string,
  message: string,
  stockCode: string,
  stockName: string
): Promise<IChatMessageDetail> => {
  const request: IChatMessageCreateRequest = {
    message,
    stock_code: stockCode,
    stock_name: stockName
  };

  const response = await apiFetch(`${API_ENDPOINT_STOCKEASY}/chat/sessions/${sessionId}/messages`, {
    method: 'POST',
    body: JSON.stringify(request)
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || '메시지 생성에 실패했습니다.');
  }

  return response.json();
};

/**
 * AI 채팅 메시지를 전송합니다.
 * @param stockCode 주식 코드
 * @param stockName 주식 이름
 * @param message 전송할 메시지
 * @param chatSessionId 채팅 세션 ID (선택)
 * @returns 응답 데이터
 */
export const sendChatMessage = async (
  stockCode: string, 
  stockName: string,
  message: string,
  chatSessionId?: string
): Promise<IChatResponse> => {
  const request: IChatRequest = {
    message: message,
    stock_code: stockCode,
    stock_name: stockName,
    chat_session_id: chatSessionId
  };

  const response = await apiFetch(`${API_ENDPOINT_STOCKEASY}/user_question`, {
    method: 'POST',
    body: JSON.stringify(request)
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || '메시지 전송에 실패했습니다.');
  }

  return response.json();
};

/**
 * 채팅 기록을 가져옵니다.
 * @param stockCode 주식 코드
 * @returns 채팅 기록
 */
export const getChatHistory = async (stockCode: string): Promise<IChatResponse[]> => {
  const response = await apiFetch(
    `${API_ENDPOINT_STOCKEASY}/chat/history?stock_code=${stockCode}`
  );

  if (!response.ok) {
    throw new Error('채팅 기록을 가져오는데 실패했습니다.');
  }

  return response.json();
};

/**
 * 채팅 세션의 메시지 목록을 조회합니다.
 * @param sessionId 채팅 세션 ID
 * @param limit 페이지당 항목 수 (선택)
 * @param offset 페이지 오프셋 (선택)
 * @returns 메시지 목록
 */
export const getChatMessages = async (
  sessionId: string,
  limit: number = 100,
  offset: number = 0
): Promise<IChatMessageListResponse> => {
  const response = await apiFetch(
    `${API_ENDPOINT_STOCKEASY}/chat/sessions/${sessionId}/messages?limit=${limit}&offset=${offset}`
  );

  if (!response.ok) {
    throw new Error('채팅 메시지를 가져오는데 실패했습니다.');
  }

  return response.json();
};

/**
 * 스트리밍 방식으로 채팅 메시지를 전송하고 실시간 응답을 수신합니다.
 * @param sessionId 채팅 세션 ID
 * @param message 메시지 내용
 * @param stockCode 종목 코드
 * @param stockName 종목명
 * @param callbacks 콜백 함수들
 */
export const streamChatMessage = async (
  sessionId: string,
  message: string,
  stockCode: string,
  stockName: string,
  callbacks: {
    onStart?: () => void,
    onAgentStatus?: (data: any) => void,
    onAgentStart?: (data: any) => void,
    onAgentComplete?: (data: any) => void,
    onComplete?: (data: any) => void,
    onError?: (error: any) => void
  }
) => {
  try {
    console.log('[STREAM_CHAT] 스트리밍 시작');
    
    // 요청 데이터 구성
    const requestData = {
      message: message,
      stock_code: stockCode,
      stock_name: stockName
    }
    
    // SSE 스트리밍 응답 처리
    const response = await apiFetch(`${API_ENDPOINT_STOCKEASY}/chat/sessions/${sessionId}/messages/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'text/event-stream'
      },
      body: JSON.stringify(requestData)
    })
    
    if (!response.ok) {
      const errorText = await response.text()
      throw new Error(`메시지 전송 실패: ${errorText}`)
    }
    
    // ReadableStream을 사용하여 SSE 처리
    const reader = response.body?.getReader()
    const decoder = new TextDecoder('utf-8')
    
    if (!reader) {
      throw new Error('응답 스트림을 읽을 수 없습니다.')
    }
    
    let buffer = ''
    
    // 응답 스트림 처리
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      
      // 데이터 디코딩
      buffer += decoder.decode(value, { stream: true })
      
      // 라인 분리
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''
      
      // 각 라인 처리
      for (const line of lines) {
        if (line.trim() === '') continue
        
        try {
          //console.log('[STREAM_CHAT] 수신된 라인:', line);
          
          // ping 메시지 처리
          if (line.startsWith(': ping')) {
            console.log('[STREAM_CHAT] 핑 메시지 수신, 무시합니다:', line);
            continue;
          }
          
          // SSE 형식 확인 (data: 로 시작하는지)
          if (line.startsWith('data:')) {
            // 'data:' 접두사 제거 후 JSON 파싱
            const jsonStr = line.substring(5).trim();
            //console.log('[STREAM_CHAT] 파싱할 JSON:', jsonStr);
            
            if (jsonStr === '[DONE]' || jsonStr === '') {
              console.log('[STREAM_CHAT] 스트리밍 완료 신호 수신');
              continue;
            }
            
            const data = JSON.parse(jsonStr);
            
            // 이벤트 유형에 따른 처리
            switch (data.event) {
              case 'start':
                console.log('[STREAM_CHAT] 처리 시작:', data.data)
                callbacks.onStart?.()
                break
                
              case 'agent_status':
                //console.log('[STREAM_CHAT] 에이전트 상태 변경:', data.data)
                callbacks.onAgentStatus?.(data.data)
                break
                
              case 'agent_start':
                //console.log('[STREAM_CHAT] 에이전트 처리 시작:', data.data)
                callbacks.onAgentStart?.(data.data)
                break
                
              case 'agent_complete':
                //console.log('[STREAM_CHAT] 에이전트 처리 완료:', data.data)
                callbacks.onAgentComplete?.(data.data)
                break
                
              case 'complete':
                //console.log('[STREAM_CHAT] 처리 완료:', data.data)
                callbacks.onComplete?.(data.data)
                break
                
              case 'error':
                console.error('[STREAM_CHAT] 처리 중 오류:', data.data)
                callbacks.onError?.(data.data)
                break
                
              default:
                console.log('[STREAM_CHAT] 알 수 없는 이벤트:', data)
            }
          } else {
            // 'data:' 접두사가 없는 경우 그대로 파싱 시도
            console.log('[STREAM_CHAT] 비표준 SSE 형식:', line);
            const data = JSON.parse(line);
            console.log('[STREAM_CHAT] 비표준 데이터 처리:', data);
            
            // 이벤트 정보가 있는 경우에만 처리
            if (data.event) {
              switch (data.event) {
                case 'start':
                  callbacks.onStart?.()
                  break
                case 'agent_status':
                  callbacks.onAgentStatus?.(data.data)
                  break
                case 'agent_start':
                  callbacks.onAgentStart?.(data.data)
                  break
                case 'agent_complete':
                  callbacks.onAgentComplete?.(data.data)
                  break
                case 'complete':
                  callbacks.onComplete?.(data.data)
                  break
                case 'error':
                  callbacks.onError?.(data.data)
                  break
              }
            }
          }
        } catch (err) {
          console.error('[STREAM_CHAT] SSE 데이터 파싱 오류:', err, '원본 라인:', line)
        }
      }
    }
    
    console.log('[STREAM_CHAT] 스트리밍 종료');
  } catch (error) {
    console.error('[STREAM_CHAT] 스트리밍 메시지 처리 중 오류:', error)
    callbacks.onError?.(error)
  }
}

/**
 * 특정 채팅 세션을 조회합니다.
 * @param sessionId 채팅 세션 ID
 * @returns 채팅 세션 정보
 */
export const getChatSession = async (
  sessionId: string
): Promise<IChatSession> => {
  const response = await apiFetch(`${API_ENDPOINT_STOCKEASY}/chat/sessions/${sessionId}`);

  if (!response.ok) {
    throw new Error('채팅 세션을 가져오는데 실패했습니다.');
  }

  return response.json();
};

/**
 * 채팅 세션을 삭제합니다.
 * @param sessionId 삭제할 채팅 세션 ID
 * @returns 성공 여부
 */
export const deleteChatSession = async (
  sessionId: string
): Promise<boolean> => {
  const response = await apiFetch(`${API_ENDPOINT_STOCKEASY}/chat/sessions/${sessionId}`, {
    method: 'DELETE',
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || '채팅 세션 삭제에 실패했습니다.');
  }

  return true;
}; 