"use client";

import React, { useEffect, useState, useRef } from 'react';
import Chart2 from './MarketMonitorChart/Chart2';
import Chart3 from './MarketMonitorChart/Chart3';
import { TableCopyButton } from '@/app/components/TableCopyButton';

export default function MarketMonitor() {
  const [updateDate, setUpdateDate] = useState<string>('');
  const headerContainerRef = useRef<HTMLDivElement>(null);
  
  // 업데이트 날짜 로드
  useEffect(() => {
    async function loadUpdateDate() {
      try {
        // marketmonitor.csv 파일에서 마지막 수정 날짜 가져오기
        const cacheFilePath = '/requestfile/trend-following/marketmonitor.csv';
        
        // 헤더만 가져와서 Last-Modified 확인
        const response = await fetch(cacheFilePath, { cache: 'no-store' });
        
        if (!response.ok) {
          console.error(`marketmonitor.csv 파일 로드 실패: ${response.status}`);
          return;
        }
        
        // 응답 헤더에서 Last-Modified 값 추출
        const lastModified = response.headers.get('Last-Modified');
        
        if (lastModified) {
          // Last-Modified 헤더에서 날짜와 시간 추출하여 포맷팅
          const modifiedDate = new Date(lastModified);
          const month = modifiedDate.getMonth() + 1; // getMonth()는 0부터 시작하므로 1 더함
          const day = modifiedDate.getDate();
          const hours = modifiedDate.getHours();
          const minutes = modifiedDate.getMinutes();
          
          // M/DD HH:MM 형식으로 포맷팅
          const formattedDate = `${month}/${day.toString().padStart(2, '0')} ${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}`;
          setUpdateDate(formattedDate);
        } else {
          // Last-Modified 헤더가 없는 경우 현재 날짜/시간 사용
          const now = new Date();
          const month = now.getMonth() + 1;
          const day = now.getDate();
          const hours = now.getHours();
          const minutes = now.getMinutes();
          
          const formattedDate = `${month}/${day.toString().padStart(2, '0')} ${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}`;
          setUpdateDate(formattedDate);
          console.warn('marketmonitor.csv 파일의 Last-Modified 헤더를 찾을 수 없어 현재 시간을 사용합니다.');
        }
      } catch (e) {
        console.error('업데이트 날짜 로드 실패:', e);
      }
    }
    loadUpdateDate();
  }, []);
  return (
    <div className="bg-white rounded border border-gray-100 px-2 md:px-4 py-3 md:py-4">
      <div ref={headerContainerRef} className="flex flex-col sm:flex-row justify-between items-start sm:items-center mb-3">
        <h3 className="text-lg font-semibold mb-1 sm:mb-0" style={{ color: 'var(--primary-text-color, var(--primary-text-color-fallback))' }}>시장 지표</h3>
        {updateDate && (
          <span className="text-xs sm:mr-2" style={{ fontSize: 'clamp(0.7rem, 0.7vw, 0.7rem)', color: 'var(--text-muted-color, var(--text-muted-color-fallback))' }}>
            updated {updateDate}
          </span>
        )}
      </div>
      
      <div className="space-y-6">
        {/* 두 번째 차트: KOSPI vs 20일선 하락비율 및 200일선 하락비율 */}
        <div className="bg-white rounded border border-gray-200 p-3 md:p-4 shadow-sm">
          <h3 className="text-sm font-medium text-gray-700 mb-2">KOSPI 지수와 20일선/200일선 하락비율</h3>
          <div className="h-[300px]">
            <Chart2 />
          </div>
        </div>
        
        {/* 세 번째 차트: KOSPI vs 52주 신고가/신저가 비율 */}
        <div className="bg-white rounded border border-gray-200 p-3 md:p-4 shadow-sm">
          <h3 className="text-sm font-medium text-gray-700 mb-2">KOSPI 지수와 52주 신고가/신저가 비율</h3>
          <div className="h-[300px]">
            <Chart3 />
          </div>
        </div>
      </div>
    </div>
  );
}
