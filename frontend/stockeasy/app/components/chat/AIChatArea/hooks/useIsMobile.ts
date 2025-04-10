/**
 * useIsMobile.ts
 * 모바일 환경 감지를 위한 커스텀 훅
 */
import { useState, useEffect } from 'react';

/**
 * 모바일 환경인지 감지하는 훅
 * @param breakpoint 모바일로 간주할 최대 너비(픽셀), 기본값 768px
 * @returns 모바일 환경 여부(boolean)
 */
export function useIsMobile(breakpoint: number = 768) {
  const [isMobile, setIsMobile] = useState<boolean>(false);

  useEffect(() => {
    // 초기 상태 설정
    const checkIsMobile = () => {
      setIsMobile(window.innerWidth < breakpoint);
    };

    // 컴포넌트 마운트 시 초기 체크
    checkIsMobile();

    // 화면 크기 변경 이벤트 리스너 등록
    window.addEventListener('resize', checkIsMobile);

    // 컴포넌트 언마운트 시 이벤트 리스너 제거
    return () => window.removeEventListener('resize', checkIsMobile);
  }, [breakpoint]);

  return isMobile;
}

export default useIsMobile; 