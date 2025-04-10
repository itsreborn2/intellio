/**
 * useSwipeGesture.ts
 * 모바일 환경에서 스와이프 제스처를 감지하고 처리하는 커스텀 훅
 */
import { useRef, useEffect, useState, RefObject, TouchEvent } from 'react';
import { useIsMobile } from './useIsMobile';

// 스와이프 방향 정의
export type SwipeDirection = 'left' | 'right' | 'up' | 'down' | null;

// 옵션 인터페이스
interface SwipeOptions {
  threshold?: number;          // 최소 이동 거리 (픽셀)
  timeout?: number;            // 최대 제스처 시간 (밀리초)
  preventDefaultOnSwipe?: boolean; // 스와이프 시 기본 동작 방지 여부
  preventScrollOnSwipe?: boolean;  // 스와이프 시 스크롤 방지 여부
}

// 리턴 타입 정의
interface SwipeGestureHandler {
  swipeDirection: SwipeDirection;
  isSwipeInProgress: boolean;
  bind: {
    onTouchStart: (e: TouchEvent) => void;
    onTouchMove: (e: TouchEvent) => void;
    onTouchEnd: (e: TouchEvent) => void;
  };
}

/**
 * 스와이프 제스처를 감지하는 훅
 * @param ref 제스처를 감지할 요소에 대한 ref 객체
 * @param onSwipe 스와이프 발생 시 호출할 함수
 * @param options 스와이프 감지 설정
 * @returns 스와이프 방향, 진행 상태 및 이벤트 핸들러
 */
export function useSwipeGesture(
  ref: RefObject<HTMLElement>,
  onSwipe?: (direction: SwipeDirection) => void,
  options: SwipeOptions = {}
): SwipeGestureHandler {
  const isMobile = useIsMobile();
  const [swipeDirection, setSwipeDirection] = useState<SwipeDirection>(null);
  const [isSwipeInProgress, setIsSwipeInProgress] = useState<boolean>(false);

  // 옵션 기본값
  const {
    threshold = 50,
    timeout = 500,
    preventDefaultOnSwipe = true,
    preventScrollOnSwipe = false
  } = options;

  // 터치 정보 저장을 위한 ref
  const touchStartRef = useRef({
    x: 0,
    y: 0,
    time: 0
  });

  // 터치 시작 처리
  const handleTouchStart = (e: TouchEvent) => {
    if (!isMobile) return;

    const touch = e.touches[0];
    touchStartRef.current = {
      x: touch.clientX,
      y: touch.clientY,
      time: Date.now()
    };
    
    setIsSwipeInProgress(true);
  };

  // 터치 이동 처리
  const handleTouchMove = (e: TouchEvent) => {
    if (!isMobile || !isSwipeInProgress) return;

    // 스크롤 방지가 활성화되어 있으면 기본 동작 방지
    if (preventScrollOnSwipe) {
      e.preventDefault();
    }
  };

  // 터치 종료 처리
  const handleTouchEnd = (e: TouchEvent) => {
    if (!isMobile || !isSwipeInProgress) return;

    const touch = e.changedTouches[0];
    const endX = touch.clientX;
    const endY = touch.clientY;
    const endTime = Date.now();
    
    const { x: startX, y: startY, time: startTime } = touchStartRef.current;
    
    // 이동 거리 및 시간 계산
    const deltaX = endX - startX;
    const deltaY = endY - startY;
    const elapsedTime = endTime - startTime;
    
    // 너무 오래 걸린 터치는 스와이프로 간주하지 않음
    if (elapsedTime > timeout) {
      setIsSwipeInProgress(false);
      return;
    }
    
    // 이동 거리가 임계값 이상인지 확인
    if (Math.abs(deltaX) >= threshold || Math.abs(deltaY) >= threshold) {
      // 이동 방향 결정 (가로 또는 세로 이동 중 큰 쪽 선택)
      let direction: SwipeDirection = null;
      
      if (Math.abs(deltaX) >= Math.abs(deltaY)) {
        // 가로 방향 스와이프
        direction = deltaX > 0 ? 'right' : 'left';
      } else {
        // 세로 방향 스와이프
        direction = deltaY > 0 ? 'down' : 'up';
      }
      
      // 스와이프 방향 설정
      setSwipeDirection(direction);
      
      // 콜백 함수 호출
      if (onSwipe) {
        onSwipe(direction);
      }
      
      // 필요시 기본 동작 방지
      if (preventDefaultOnSwipe) {
        e.preventDefault();
      }
    }
    
    // 스와이프 진행 상태 초기화
    setIsSwipeInProgress(false);
  };

  // 컴포넌트 언마운트 시 정리
  useEffect(() => {
    return () => {
      setSwipeDirection(null);
      setIsSwipeInProgress(false);
    };
  }, []);

  // 이벤트 핸들러 반환
  return {
    swipeDirection,
    isSwipeInProgress,
    bind: {
      onTouchStart: handleTouchStart,
      onTouchMove: handleTouchMove,
      onTouchEnd: handleTouchEnd
    }
  };
}

export default useSwipeGesture; 