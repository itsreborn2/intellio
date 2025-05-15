'use client';

import React from 'react';

interface LoadingSpinnerProps {
  size?: 'sm' | 'md' | 'lg';
  message?: string;
}

/**
 * 애플리케이션 전체에서 사용할 수 있는 로딩 스피너 컴포넌트
 * 
 * @param size - 스피너 크기: 'sm'(작음), 'md'(중간), 'lg'(큼), 기본값은 'md'
 * @param message - 스피너 아래에 표시할 메시지, 기본값은 '데이터를 불러오는 중...'
 */
export default function LoadingSpinner({ 
  size = 'md', 
  message = '데이터를 불러오는 중...' 
}: LoadingSpinnerProps) {
  // 크기에 따른 스타일 결정
  const sizeClasses = {
    sm: 'h-6 w-6 border-2',
    md: 'h-10 w-10 border-4',
    lg: 'h-14 w-14 border-[6px]'
  };

  // 텍스트 크기 결정
  const textClasses = {
    sm: 'text-xs',
    md: 'text-sm',
    lg: 'text-base'
  };

  return (
    <div className="h-full flex items-center justify-center">
      <div className="relative">
        <div className={`animate-spin rounded-full ${sizeClasses[size]} border-t-transparent border-r-transparent border-l-transparent border-b-blue-500 mb-2 mx-auto`}></div>
        {message && (
          <span className={`block ${textClasses[size]} text-gray-600 text-center`}>
            {message}
          </span>
        )}
      </div>
    </div>
  );
}
