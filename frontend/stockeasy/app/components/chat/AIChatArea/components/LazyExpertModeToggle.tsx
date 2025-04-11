/**
 * LazyExpertModeToggle.tsx
 * 지연 로딩을 통한 ExpertModeToggle 컴포넌트 로드
 */
'use client';

import React, { lazy, Suspense } from 'react';

// 지연 로딩을 위한 ExpertModeToggle 컴포넌트 가져오기
const ExpertModeToggle = lazy(() => import('./ExpertModeToggle'));

// Fallback UI 컴포넌트
const ExpertToggleFallback = () => (
  <div 
    style={{
      display: 'flex',
      alignItems: 'center',
      gap: '8px',
      padding: '10px 14px',
      borderRadius: '8px',
      backgroundColor: '#f5f5f5',
      border: '1px solid #ddd',
      cursor: 'pointer',
      minWidth: '120px',
      minHeight: '36px'
    }}
  >
    <div style={{ width: '36px', height: '20px', backgroundColor: '#eee', borderRadius: '10px' }} />
    <div style={{ width: '60px', height: '14px', backgroundColor: '#eee', borderRadius: '4px' }} />
  </div>
);

interface LazyExpertModeToggleProps {
  expertMode: boolean;
  onChange: (enabled: boolean) => void;
}

export function LazyExpertModeToggle({ expertMode, onChange }: LazyExpertModeToggleProps) {
  return (
    <Suspense fallback={<ExpertToggleFallback />}>
      <ExpertModeToggle expertMode={expertMode} onChange={onChange} />
    </Suspense>
  );
}

export default LazyExpertModeToggle; 