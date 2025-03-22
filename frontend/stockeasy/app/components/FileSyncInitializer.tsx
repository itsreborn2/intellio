'use client';

import { useEffect } from 'react';

/**
 * 파일 동기화를 위한 클라이언트 컴포넌트
 * 페이지 로드 시 파일 동기화 API를 자동으로 호출합니다.
 */
export default function FileSyncInitializer() {
  useEffect(() => {
    // 페이지 로드 시 파일 동기화 API 호출
    const syncFiles = async () => {
      try {
        console.log('파일 동기화 시작...');
        const response = await fetch('/api/file-sync');
        const data = await response.json();
        console.log('파일 동기화 결과:', data);
      } catch (error) {
        console.error('파일 동기화 중 오류 발생:', error);
      }
    };
    
    syncFiles();
  }, []);
  
  return null;
}
