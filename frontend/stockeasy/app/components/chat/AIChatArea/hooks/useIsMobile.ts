/**
 * useIsMobile.ts
 * 모바일 환경 감지를 위한 커스텀 훅 (개발자 도구 모바일 시뮬레이션 대응 강화)
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
      // 1. 화면 너비로 모바일 여부 확인
      const isMobileByWidth = window.innerWidth < breakpoint;
      
      // 2. 개발자 도구의 모바일 시뮬레이션 모드 감지 (User-Agent 문자열 확인)
      const userAgent = navigator.userAgent.toLowerCase();
      const mobileKeywords = ['android', 'iphone', 'ipad', 'ipod', 'mobile', 'tablet'];
      const isMobileDevice = mobileKeywords.some(keyword => userAgent.includes(keyword));
      
      // 3. 개발자 도구의 모바일 시뮬레이션 모드 감지 (터치 이벤트 지원 여부)
      const hasTouchSupport = 'ontouchstart' in window || navigator.maxTouchPoints > 0;
      
      // 4. 화면 방향 API 지원 여부 확인 (대부분의 모바일 기기에서 지원)
      const hasOrientationSupport = typeof window.orientation !== 'undefined' || 
                                   window.matchMedia("(orientation: portrait)").matches ||
                                   window.matchMedia("(orientation: landscape)").matches;
      
      // 개발자 도구 모바일 시뮬레이션 감지를 위한 추가 검사
      const isDevToolsMobileSimulation = 
        // Chrome 개발자 도구의 모바일 시뮬레이션은 보통 특정 User-Agent를 설정함
        (userAgent.includes('chrome') && hasTouchSupport && isMobileByWidth) ||
        // 또는 navigator.userAgentData를 통해 모바일 여부 확인 (지원되는 브라우저에서)
        // @ts-ignore - userAgentData는 최신 브라우저에만 있음
        (navigator.userAgentData?.mobile === true);
      
      // 최종 판단: 화면 너비가 모바일 크기이거나, 모바일 기기이거나, 개발자 도구 시뮬레이션인 경우
      setIsMobile(isMobileByWidth || isMobileDevice || isDevToolsMobileSimulation);
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