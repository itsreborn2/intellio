/**
 * useMediaQuery.ts
 * 미디어 쿼리에 따른 상태 변화를 감지하는 커스텀 훅
 */
'use client';

import { useState, useEffect, useMemo } from 'react';
import { mediaQueries, matchesMedia } from '../utils/mediaQueries';

type MediaQueryKey = keyof typeof mediaQueries;

/**
 * 주어진 미디어 쿼리 키에 대한 미디어 쿼리 일치 여부를 반환하는 훅
 * @param key 미디어 쿼리 키 (xs, sm, md, lg, xl, xxl, mobile, tablet, desktop 등)
 * @returns 미디어 쿼리 일치 여부
 */
export function useMediaQuery(key: MediaQueryKey): boolean {
  // 서버 사이드 렌더링 대응
  const [matches, setMatches] = useState<boolean>(false);
  
  // 미디어 쿼리 문자열 메모이제이션
  const query = useMemo(() => mediaQueries[key], [key]);
  
  useEffect(() => {
    // 서버 사이드 렌더링 환경에서는 실행하지 않음
    if (typeof window === 'undefined') return;
    
    // 초기 상태 설정
    setMatches(matchesMedia(query));
    
    // 미디어 쿼리 리스너 생성
    const mediaQueryList = window.matchMedia(query);
    
    // 변경 이벤트 핸들러
    const handleChange = (event: MediaQueryListEvent) => {
      setMatches(event.matches);
    };
    
    // 이벤트 리스너 등록
    if (mediaQueryList.addEventListener) {
      mediaQueryList.addEventListener('change', handleChange);
    } else {
      // Safari 13.1 이하 버전 대응
      mediaQueryList.addListener(handleChange);
    }
    
    // 컴포넌트 언마운트 시 이벤트 리스너 제거
    return () => {
      if (mediaQueryList.removeEventListener) {
        mediaQueryList.removeEventListener('change', handleChange);
      } else {
        // Safari 13.1 이하 버전 대응
        mediaQueryList.removeListener(handleChange);
      }
    };
  }, [query]);
  
  return matches;
}

/**
 * 여러 미디어 쿼리에 대한 일치 여부를 반환하는 훅
 * @param queries 미디어 쿼리 키 배열
 * @returns 각 미디어 쿼리에 대한 일치 여부를 담은 객체
 */
export function useMediaQueries(queries: MediaQueryKey[]): Record<MediaQueryKey, boolean> {
  const result: Partial<Record<MediaQueryKey, boolean>> = {};
  
  for (const query of queries) {
    // eslint-disable-next-line react-hooks/rules-of-hooks
    result[query] = useMediaQuery(query);
  }
  
  return result as Record<MediaQueryKey, boolean>;
}

/**
 * 현재 뷰포트 타입을 반환하는 훅
 * @returns 뷰포트 타입 (mobile, tablet, desktop)
 */
export function useViewportType(): 'mobile' | 'tablet' | 'desktop' {
  const isMobile = useMediaQuery('mobile');
  const isTablet = useMediaQuery('tablet');
  
  if (isMobile) return 'mobile';
  if (isTablet) return 'tablet';
  return 'desktop';
}

export default useMediaQuery; 