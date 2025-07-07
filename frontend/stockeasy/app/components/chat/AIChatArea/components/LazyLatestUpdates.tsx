/**
 * LazyLatestUpdates.tsx
 * 지연 로딩을 통한 LatestUpdates 컴포넌트 로드
 */
'use client';

import React, { lazy, Suspense } from 'react';
import { StockOption } from '../types';

// 지연 로딩을 위한 LatestUpdates 컴포넌트 가져오기
const LatestUpdates = lazy(() => import('./LatestUpdates'));

// Fallback UI 컴포넌트
const LatestUpdatesFallback = () => (
  <div 
    style={{
      display: 'flex',
      flexDirection: 'column',
      gap: '8px',
      border: '1px solid #ddd',
      borderRadius: '10px',
      padding: '12px',
      backgroundColor: '#ffffff',
      flex: '1',
      width: '100%'
    }}
  >
    <div style={{ 
      fontSize: '13px',
      marginBottom: '8px',
      backgroundColor: '#eee',
      height: '16px',
      width: '120px',
      borderRadius: '4px'
    }} />
    
    <div style={{ display: 'flex', gap: '8px' }}>
      {/* 첫 번째 열 스켈레톤 */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '8px' }}>
        {[1, 2, 3, 4, 5].map(i => (
          <div key={i} style={{
            width: '100%',
            padding: '6px 10px',
            borderRadius: '8px',
            border: '1px solid #eee',
            backgroundColor: '#f9f9f9',
            height: '36px'
          }} />
        ))}
      </div>
      
      {/* 두 번째 열 스켈레톤 */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '8px' }}>
        {[1, 2, 3, 4, 5].map(i => (
          <div key={i + 5} style={{
            width: '100%',
            padding: '6px 10px',
            borderRadius: '8px',
            border: '1px solid #eee',
            backgroundColor: '#f9f9f9',
            height: '36px'
          }} />
        ))}
      </div>
    </div>
  </div>
);

interface PopularStock {
  stock: StockOption;
  rank: number;
}

interface LazyLatestUpdatesProps {
  updatesDaily: PopularStock[];
  updatesWeekly: PopularStock[];
  onSelectUpdate: (stock: StockOption, question: string) => void;
}

export function LazyLatestUpdates({ updatesDaily, updatesWeekly, onSelectUpdate }: LazyLatestUpdatesProps) {
  return (
    <Suspense fallback={<LatestUpdatesFallback />}>
      <LatestUpdates updatesDaily={updatesDaily} updatesWeekly={updatesWeekly} onSelectUpdate={onSelectUpdate} />
    </Suspense>
  );
}

export default LazyLatestUpdates;