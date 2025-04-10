/**
 * mediaQueries.ts
 * 반응형 레이아웃을 위한 미디어 쿼리 관련 상수 및 유틸리티
 */

/**
 * 화면 크기별 브레이크포인트 정의
 */
export const breakpoints = {
  xs: 480,
  sm: 640,
  md: 768,
  lg: 1024,
  xl: 1280,
  xxl: 1536
};

/**
 * 미디어 쿼리 문자열 생성 유틸리티
 */
export const mediaQueries = {
  xs: `(max-width: ${breakpoints.xs}px)`,
  sm: `(max-width: ${breakpoints.sm}px)`,
  md: `(max-width: ${breakpoints.md}px)`,
  lg: `(max-width: ${breakpoints.lg}px)`,
  xl: `(max-width: ${breakpoints.xl}px)`,
  xxl: `(max-width: ${breakpoints.xxl}px)`,
  mobile: `(max-width: ${breakpoints.md - 1}px)`,
  tablet: `(min-width: ${breakpoints.md}px) and (max-width: ${breakpoints.lg - 1}px)`,
  desktop: `(min-width: ${breakpoints.lg}px)`,
  portrait: '(orientation: portrait)',
  landscape: '(orientation: landscape)',
  darkMode: '(prefers-color-scheme: dark)',
  lightMode: '(prefers-color-scheme: light)'
};

/**
 * 뷰포트 크기 확인 유틸리티 함수
 * @returns 현재 뷰포트 크기에 대한 정보
 */
export function getViewportInfo(): {
  isMobile: boolean;
  isTablet: boolean;
  isDesktop: boolean;
  isPortrait: boolean;
  isLandscape: boolean;
} {
  if (typeof window === 'undefined') {
    return {
      isMobile: false,
      isTablet: false,
      isDesktop: true,
      isPortrait: false,
      isLandscape: true
    };
  }
  
  const width = window.innerWidth;
  const height = window.innerHeight;
  
  return {
    isMobile: width < breakpoints.md,
    isTablet: width >= breakpoints.md && width < breakpoints.lg,
    isDesktop: width >= breakpoints.lg,
    isPortrait: height > width,
    isLandscape: width >= height
  };
}

/**
 * 특정 미디어 쿼리 조건을 확인하는 함수
 * @param queryString 미디어 쿼리 문자열
 * @returns 미디어 쿼리 조건 충족 여부
 */
export function matchesMedia(queryString: string): boolean {
  if (typeof window === 'undefined') {
    return false;
  }
  
  return window.matchMedia(queryString).matches;
}

/**
 * 현재 화면 크기에 따른 안전한 여백 값 계산
 * @returns 화면 크기별 여백 값 (px)
 */
export function getSafePadding(): {
  horizontal: number;
  vertical: number;
} {
  const { isMobile, isTablet } = getViewportInfo();
  
  return {
    horizontal: isMobile ? 16 : isTablet ? 24 : 32,
    vertical: isMobile ? 12 : isTablet ? 20 : 28
  };
}

export default {
  breakpoints,
  mediaQueries,
  getViewportInfo,
  matchesMedia,
  getSafePadding
}; 