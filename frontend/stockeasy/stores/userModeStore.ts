import { create } from 'zustand';
import { useEffect } from 'react';

type UserMode = 'beginner' | 'expert';

interface UserModeState {
  mode: UserMode;
  setMode: (mode: UserMode) => void;
  isClient: boolean;
  setIsClient: (isClient: boolean) => void;
}

// 로컬 스토리지에서 초기 모드 가져오기 함수
const getInitialMode = (): UserMode => {
  if (typeof window === 'undefined') return 'beginner';
  
  try {
    const storedMode = localStorage.getItem('user_mode');
    return (storedMode as UserMode) || 'beginner';
  } catch (error) {
    console.error('로컬 스토리지 접근 중 오류:', error);
    return 'beginner';
  }
};

export const useUserModeStore = create<UserModeState>((set) => ({
  // 서버 사이드 렌더링 시 기본값으로 초기화
  mode: 'beginner',
  isClient: false,
  
  // 클라이언트 상태 설정 함수
  setIsClient: (isClient: boolean) => {
    if (isClient) {
      try {
        // 클라이언트에서 마운트될 때 로컬 스토리지에서 실제 모드 가져오기
        const mode = getInitialMode();
        set({ isClient, mode });
      } catch (error) {
        console.error('클라이언트 상태 설정 중 오류:', error);
        set({ isClient });
      }
    } else {
      set({ isClient });
    }
  },
  
  // 모드 설정 함수
  setMode: (mode: UserMode) => {
    set({ mode });
    
    // 로컬 스토리지에 모드 저장 (클라이언트에서만 실행)
    if (typeof window !== 'undefined') {
      try {
        localStorage.setItem('user_mode', mode);
        
        // 모드 변경 이벤트 발생
        const event = new CustomEvent('userModeChange', {
          detail: { mode }
        });
        window.dispatchEvent(event);
      } catch (error) {
        console.error('모드 저장 중 오류:', error);
      }
    }
  },
}));

// 클라이언트 사이드 마운트 상태를 확인하는 훅
export function useIsClient() {
  const { isClient, setIsClient } = useUserModeStore();
  
  // 명시적인 useEffect 사용
  useEffect(() => {
    // 초기 마운트 시 한 번만 실행
    if (!isClient) {
      // 약간의 지연시간을 두어 안정적으로 처리
      const timer = setTimeout(() => {
        setIsClient(true);
      }, 10);
      
      // 클린업 함수
      return () => clearTimeout(timer);
    }
  }, [isClient, setIsClient]);
  
  return isClient;
} 