/**
 * useChatSession.ts
 * 채팅 세션 관리 커스텀 훅
 */
'use client';

import { useState, useCallback, useEffect } from 'react';
import { 
  createChatSession, 
  getChatSession,
  getChatMessages,
  deleteChatSession
} from '@/services/api/chat';
import { IChatSession, IChatMessageDetail } from '@/types/api/chat';
import { ChatMessage } from '../types';
import { convertApiMessageToComponentMessage } from '../utils/messageFormatters';

interface ChatSessionHook {
  session: IChatSession | null;
  isLoading: boolean;
  messages: ChatMessage[];
  error: string | null;
  createSession: (sessionName: string) => Promise<IChatSession>;
  loadSession: (sessionId: string) => Promise<void>;
  loadMessages: (sessionId: string) => Promise<ChatMessage[]>;
  deleteSession: (sessionId: string) => Promise<void>;
  clearSession: () => void;
}

/**
 * 채팅 세션 관리 커스텀 훅
 * @returns 채팅 세션 관련 상태 및 함수
 */
export function useChatSession(): ChatSessionHook {
  const [session, setSession] = useState<IChatSession | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [error, setError] = useState<string | null>(null);

  // 세션 생성
  const createSession = useCallback(async (sessionName: string): Promise<IChatSession> => {
    setIsLoading(true);
    setError(null);

    try {
      const newSession = await createChatSession(sessionName);
      setSession(newSession);
      return newSession;
    } catch (err: any) {
      const errorMessage = err?.message || '세션 생성 중 오류가 발생했습니다.';
      setError(errorMessage);
      throw new Error(errorMessage);
    } finally {
      setIsLoading(false);
    }
  }, []);

  // 세션 로드
  const loadSession = useCallback(async (sessionId: string): Promise<void> => {
    setIsLoading(true);
    setError(null);

    try {
      const loadedSession = await getChatSession(sessionId);
      setSession(loadedSession);
    } catch (err: any) {
      const errorMessage = err?.message || '세션 로드 중 오류가 발생했습니다.';
      setError(errorMessage);
      throw new Error(errorMessage);
    } finally {
      setIsLoading(false);
    }
  }, []);

  // 세션 메시지 로드
  const loadMessages = useCallback(async (sessionId: string): Promise<ChatMessage[]> => {
    setIsLoading(true);
    setError(null);

    try {
      const apiMessages = await getChatMessages(sessionId);
      const convertedMessages = apiMessages.map(convertApiMessageToComponentMessage);
      setMessages(convertedMessages);
      return convertedMessages;
    } catch (err: any) {
      const errorMessage = err?.message || '메시지 로드 중 오류가 발생했습니다.';
      setError(errorMessage);
      throw new Error(errorMessage);
    } finally {
      setIsLoading(false);
    }
  }, []);

  // 세션 삭제
  const deleteSession = useCallback(async (sessionId: string): Promise<void> => {
    setIsLoading(true);
    setError(null);

    try {
      await deleteChatSession(sessionId);
      if (session?.id === sessionId) {
        setSession(null);
        setMessages([]);
      }
    } catch (err: any) {
      const errorMessage = err?.message || '세션 삭제 중 오류가 발생했습니다.';
      setError(errorMessage);
      throw new Error(errorMessage);
    } finally {
      setIsLoading(false);
    }
  }, [session]);

  // 세션 클리어
  const clearSession = useCallback(() => {
    setSession(null);
    setMessages([]);
    setError(null);
  }, []);

  // 세션 변경 시 메시지 로드
  useEffect(() => {
    if (session?.id) {
      loadMessages(session.id).catch(console.error);
    }
  }, [session, loadMessages]);

  return {
    session,
    isLoading,
    messages,
    error,
    createSession,
    loadSession,
    loadMessages,
    deleteSession,
    clearSession,
  };
}

export default useChatSession; 