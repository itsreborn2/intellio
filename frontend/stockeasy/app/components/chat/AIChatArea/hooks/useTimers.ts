/**
 * useTimers.ts
 * 경과 시간 표시를 위한 타이머 관리 커스텀 훅
 */
import { useState, useRef, useEffect, useCallback } from 'react';
import { ChatMessage } from '../types';

/**
 * 채팅 메시지의 경과 시간 관리를 위한 커스텀 훅
 * @returns 타이머 관련 상태 및 함수들
 */
export function useTimers() {
  const [elapsedTime, setElapsedTime] = useState<number>(0);
  const [timerState, setTimerState] = useState<Record<string, number>>({});
  const timerRef = useRef<NodeJS.Timeout | null>(null);
  
  // 전체 타이머 시작
  const startTimer = useCallback(() => {
    // 이미 실행 중인 타이머가 있으면 정리
    if (timerRef.current) {
      clearInterval(timerRef.current);
    }
    
    // 타이머 초기화
    setElapsedTime(0);
    
    // 새 타이머 시작
    timerRef.current = setInterval(() => {
      setElapsedTime(prev => prev + 1);
    }, 1000);
  }, []);
  
  // 전체 타이머 정지
  const stopTimer = useCallback(() => {
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
    setElapsedTime(0);
  }, []);
  
  // 특정 메시지들의 경과 시간 관리
  useEffect(() => {
    return () => {
      // 컴포넌트 언마운트 시 타이머 정리
      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
    };
  }, []);
  
  // 메시지별 타이머 업데이트 함수
  const updateMessageTimers = useCallback((messages: ChatMessage[]) => {
    // 활성 타이머가 있는 메시지만 필터링
    const messagesWithElapsed = messages.filter(
      msg => msg.elapsed !== undefined && msg.elapsedStartTime !== undefined
    );
    
    if (messagesWithElapsed.length === 0) return;
    
    // 각 메시지의 타이머 상태 업데이트
    const intervalId = setInterval(() => {
      const newTimerState: Record<string, number> = {};
      let hasRunningTimer = false;
      
      messagesWithElapsed.forEach(msg => {
        if (msg.elapsedStartTime) {
          const currentElapsed = Date.now() - msg.elapsedStartTime;
          newTimerState[msg.id] = msg.elapsed! + (currentElapsed / 1000);
          hasRunningTimer = true;
        }
      });
      
      if (hasRunningTimer) {
        setTimerState(newTimerState);
      } else {
        clearInterval(intervalId);
      }
    }, 100);
    
    // 이전 인터벌 정리를 위한 함수 반환
    return () => clearInterval(intervalId);
  }, []);
  
  return {
    elapsedTime,
    timerState,
    startTimer,
    stopTimer,
    updateMessageTimers
  };
}

export default useTimers; 