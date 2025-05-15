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
 * 널 문자를 제거하는 유틸리티 함수
 * @param str 처리할 문자열
 * @returns 널 문자가 제거된 문자열
 */
const removeNullCharacters = (str: string): string => {
  if (!str) return str;
  // 널 문자(\u0000)를 모두 제거
  return str.replace(/\0/g, '');
};

/**
 * JSON 문자열에서 널 문자를 제거
 * @param jsonStr JSON 문자열
 * @returns 널 문자가 제거된 JSON 문자열
 */
const sanitizeJsonString = (jsonStr: string): string => {
  if (!jsonStr) return jsonStr;
  return removeNullCharacters(jsonStr);
};

/**
 * 새 채팅 세션을 생성합니다.
 * @param title 세션 제목 (기본값: "새 채팅")
 * @param stock_code 종목 코드 (선택)
 * @param stock_name 종목명 (선택)
 * @param stock_info 종목 관련 추가 정보 (선택)
 * @returns 생성된 채팅 세션 정보
 */
export const createChatSession = async (
  title: string = "새 채팅",
  stock_code?: string,
  stock_name?: string,
  stock_info?: any
): Promise<IChatSession> => {
  const request: IChatSessionCreateRequest = {
    title,
    stock_code,
    stock_name,
    stock_info
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
 * @param isFollowUp 팔로우업 여부
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
    onToken?: (data: { token: string, timestamp: number, message_id: string }) => void,
    onComplete?: (data: any) => void,
    onError?: (error: any) => void,
    onNavigate?: (url: string) => void
  },
  isFollowUp: boolean = false
) => {
  try {
    console.log('[STREAM_CHAT] 스트리밍 시작');
    
    // 요청 데이터 구성
    const requestData = {
      message: message,
      stock_code: stockCode,
      stock_name: stockName,
      is_follow_up: isFollowUp
    }
    
    // 세션 ID가 있으면 브라우저 URL을 /chat/${sessionId}로 변경
    if (sessionId && callbacks.onNavigate) {
      callbacks.onNavigate(`/chat/${sessionId}`);
    }
    
    // SSE 스트리밍 응답 처리
    // URL 형식 유지하면서 브라우저 URL은 /chat/${sessionId}로 표시
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
            
            if (jsonStr === '[DONE]' || jsonStr.trim() === '') {
              //console.log('[STREAM_CHAT] 스트리밍 완료 신호 수신');
              continue;
            }
            
            // 중복된 'data:' 접두사 처리
            let fixedJsonStr = jsonStr;
            // 'data:' 접두사가 다시 있으면 추가로 제거
            if (fixedJsonStr.startsWith('data:')) {
              fixedJsonStr = fixedJsonStr.substring(5).trim();
              console.log('[STREAM_CHAT] 중복된 데이터 접두사 발견, 재처리:', fixedJsonStr);
            }
            
            // 널 문자 제거
            fixedJsonStr = sanitizeJsonString(fixedJsonStr);
            
            try {
              const data = JSON.parse(fixedJsonStr);
              //console.log(`[STREAM_CHAT] 이벤트 수신: ${data.event}`);
              
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
                  
                case 'token':
                  //console.log('[STREAM_CHAT] 토큰 수신:', data.data?.token)
                  // 토큰 이벤트 처리 추가
                  const tokenData = {
                    token: data.data?.token ? removeNullCharacters(data.data.token) : '',
                    timestamp: data.data?.timestamp,
                    message_id: data.data?.message_id
                  }
                  callbacks.onToken?.(tokenData)
                  break
                  
                case 'complete':
                  console.log('[STREAM_CHAT] 처리 완료:', data.data)
                  callbacks.onComplete?.(data.data)
                  break
                  
                case 'error':
                  console.error('[STREAM_CHAT] 처리 중 오류:', data.data)
                  callbacks.onError?.(data.data)
                  break
                  
                default:
                  console.log('[STREAM_CHAT] 알 수 없는 이벤트:', data)
              }
            } catch (err) {
              console.error('[STREAM_CHAT] 비표준 SSE 데이터 파싱 오류:', err, '원본 라인:', line)
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