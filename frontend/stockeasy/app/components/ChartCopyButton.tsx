'use client'

import React, { useState } from 'react';
import { ChartCopyButtonProps, copyChartAsImage } from '../utils/chartCopyUtils';
import { ClipboardCopy } from 'lucide-react'; // ClipboardCopy 아이콘 import

/**
 * 차트 복사 버튼 컴포넌트
 * 차트를 이미지로 복사하는 기능을 제공하는 재사용 가능한 버튼
 * @param props 버튼 속성 (차트 참조, 차트 이름, 옵션, 클래스명, 버튼 텍스트)
 */
export const ChartCopyButton: React.FC<ChartCopyButtonProps> = ({
  chartRef,
  chartName,
  options,
  className = '',
  buttonText = '이미지복사',
  updateDateText,
  onStartCapture,
  onEndCapture,
}) => {
  const [isLoading, setIsLoading] = useState(false);
  const [showSuccess, setShowSuccess] = useState(false);

  // 이미지 복사 핸들러
  const handleCopyImage = async () => {
    setIsLoading(true);
    // 캡처(복사) 시작 시 콜백 호출
    if (onStartCapture) onStartCapture();
    try {
      await copyChartAsImage(chartRef, chartName, options, updateDateText);
    } catch (error) {
      console.error('차트 이미지 복사 중 오류 발생:', error);
      alert('차트 이미지 복사에 실패했습니다. 콘솔을 확인해주세요.');
    } finally {
      setTimeout(() => {
        setIsLoading(false);
        setShowSuccess(true);
        setTimeout(() => setShowSuccess(false), 2000);
      }, 500);
      // 캡처(복사) 종료 시 콜백 호출(성공/실패 모두)
      if (onEndCapture) onEndCapture();
    }
  };

  // 버튼 스타일
  const buttonStyle = {
    fontSize: 'clamp(0.6rem, 0.7vw, 0.7rem)',
    padding: 'clamp(0.15rem, 0.2vw, 0.25rem) clamp(0.3rem, 0.4vw, 0.5rem)',
  };

  return (
    <button
      onClick={handleCopyImage}
      className={`chart-copy-btn text-gray-700 text-xs px-2 py-1 rounded ${isLoading ? 'opacity-50 cursor-not-allowed' : 'hover:opacity-80'} bg-[#D8EFE9] ${className}`}

      type="button"
      aria-label={`${chartName} 이미지로 복사`}
      disabled={isLoading}
      style={buttonStyle}
    >
      {isLoading ? '생성 중...' : showSuccess ? '복사 완료!' : <ClipboardCopy className="h-3.5 w-3.5" />}
    </button>
  );
};

export default ChartCopyButton;
