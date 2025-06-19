/**
 * PreliminaryChartDisplay.tsx
 * 실시간 기술적 분석 차트를 표시하는 팝업 컴포넌트
 */
'use client';

import React, { useEffect, useState } from 'react';
import { MessageComponentRenderer } from './MessageComponentRenderer';
import { useMediaQuery } from '../hooks/useMediaQuery';

interface PreliminaryChartData {
  components: any[];
  message: string;
  timestamp: number;
  stockCode: string;
  stockName: string;
}

interface PreliminaryChartDisplayProps {
  chartData: PreliminaryChartData;
  onClose?: () => void;
  isCompleted?: boolean;
  onViewFinalReport?: () => void;
}

/**
 * 날짜 형식을 YYYY-MM-DD로 정규화하는 함수
 */
function normalizeDateFormat(dateString: string): string {
  try {
    if (!dateString) return '';
    
    // 이미 YYYY-MM-DD 형식인 경우
    if (/^\d{4}-\d{2}-\d{2}$/.test(dateString)) {
      return dateString;
    }
    
    // ISO 8601 형식인 경우 (2024-06-19T00:00:00+09:00)
    if (dateString.includes('T')) {
      return dateString.split('T')[0];
    }
    
    // Date 객체로 변환 시도
    const date = new Date(dateString);
    if (!isNaN(date.getTime())) {
      return date.toISOString().split('T')[0];
    }
    
    return dateString;
  } catch (error) {
    console.warn('[PreliminaryChartDisplay] 날짜 형식 변환 실패:', dateString, error);
    return dateString;
  }
}

/**
 * 차트 컴포넌트 데이터를 검증하고 정규화하는 함수
 */
function normalizeChartComponent(component: any): any {
  try {
    if (!component || !component.data) {
      return component;
    }
    
    const data = component.data;
    
    // 새로운 표준 구조: 직접 dates 필드가 있는 경우 (technical_indicator_chart, price_chart)
    if (data.dates && Array.isArray(data.dates)) {
      const normalizedDates = data.dates.map((date: any) => 
        normalizeDateFormat(String(date))
      );
      
      // candle_data의 time 필드도 정규화
      let normalizedCandleData = data.candle_data;
      if (data.candle_data && Array.isArray(data.candle_data)) {
        normalizedCandleData = data.candle_data.map((candle: any) => ({
          ...candle,
          time: normalizeDateFormat(String(candle.time))
        }));
      }
      
      return {
        ...component,
        data: {
          ...data,
          dates: normalizedDates,
          candle_data: normalizedCandleData
        }
      };
    }
    
    // 이전 구조 호환성: chart_data가 있는 경우 (하위 호환성)
    if (data.chart_data && data.chart_data.dates) {
      const normalizedDates = data.chart_data.dates.map((date: any) => 
        normalizeDateFormat(String(date))
      );
      
      const normalizedChartData = {
        ...data.chart_data,
        dates: normalizedDates
      };
      
      return {
        ...component,
        data: {
          ...data,
          chart_data: normalizedChartData
        }
      };
    }
    
    return component;
  } catch (error) {
    console.error('[PreliminaryChartDisplay] 컴포넌트 정규화 실패:', error);
    return component;
  }
}

/**
 * 차트 데이터 유효성을 검증하는 함수
 */
function validateChartData(chartData: PreliminaryChartData): {
  isValid: boolean;
  errorMessage?: string;
  stats?: {
    componentCount: number;
    validComponents: number;
    chartComponents: number;
  };
} {
  try {
    if (!chartData) {
      return { isValid: false, errorMessage: '차트 데이터가 없습니다.' };
    }

    if (!chartData.components || !Array.isArray(chartData.components)) {
      return { isValid: false, errorMessage: '차트 컴포넌트 배열이 유효하지 않습니다.' };
    }

    const componentCount = chartData.components.length;
    let validComponents = 0;
    let chartComponents = 0;

    for (const component of chartData.components) {
      if (component && component.type) {
        validComponents++;
        
        if (component.type.includes('chart')) {
          chartComponents++;
          console.log('1')
          // 새로운 표준 구조 검증 (직접 dates 필드)
          if (component.data && component.data.dates) {
            const dates = component.data.dates;
            
            if (!dates || !Array.isArray(dates) || dates.length === 0) {
              console.warn('[PreliminaryChartDisplay] 차트 데이터에 날짜 정보가 없습니다:', component.type);
            }
            
            
          }
          
        }
      }
    }

    const stats = {
      componentCount,
      validComponents,
      chartComponents
    };

    if (validComponents === 0) {
      return { 
        isValid: false, 
        errorMessage: '유효한 컴포넌트가 없습니다.',
        stats
      };
    }

    return { 
      isValid: true,
      stats
    };
  } catch (error) {
    console.error('[PreliminaryChartDisplay] 차트 데이터 검증 중 오류:', error);
    return { 
      isValid: false, 
      errorMessage: '차트 데이터 검증 중 오류가 발생했습니다.'
    };
  }
}

export function PreliminaryChartDisplay({ chartData, onClose, isCompleted = true, onViewFinalReport }: PreliminaryChartDisplayProps) {
  const [isVisible, setIsVisible] = useState(false);
  const [isAnimating, setIsAnimating] = useState(false);
  const isMobile = useMediaQuery('mobile');

  useEffect(() => {
    // 컴포넌트 마운트 시 애니메이션 시작
    setIsVisible(true);
    setTimeout(() => setIsAnimating(true), 50);
  }, []);

  const handleClose = () => {
    setIsAnimating(false);
    setTimeout(() => {
      setIsVisible(false);
      onClose?.();
    }, 300);
  };

  // ESC 키로 팝업 닫기
  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        handleClose();
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, []);

  if (!isVisible) return null;

  // 컴포넌트 정규화 제거 - tech agent는 이미 표준 구조로 데이터를 생성함
  const normalizedComponents = chartData.components;

  return (
    <div className={`fixed inset-0 z-50 flex items-center justify-center ${isMobile ? 'p-4' : 'pl-[59px] pr-4 pt-4 pb-4'}`}>
      {/* 배경 오버레이 - 모바일에서는 전체 화면, 데스크톱에서는 사이드바 제외 */}
      <div 
        className={`fixed inset-0 ${isMobile ? '' : 'left-[59px]'} bg-black transition-opacity duration-300 ${
          isAnimating ? 'opacity-50' : 'opacity-0'
        }`}
        onClick={handleClose}
      />

      {/* 팝업 컨테이너 - 모바일에서는 전체 영역, 데스크톱에서는 사이드바 제외 */}
      <div 
        className={`relative bg-white rounded-xl shadow-2xl w-full max-h-[85vh] overflow-hidden transform transition-all duration-300 ${
          isAnimating 
            ? 'scale-100 opacity-100 translate-y-0' 
            : 'scale-95 opacity-0 translate-y-8'
        }`}
        style={{ maxWidth: isMobile ? 'calc(100vw - 2rem)' : 'calc(100vw - 59px - 2rem)' }}
      >
        {/* 헤더 */}
        <div className="border-b border-gray-200 bg-gradient-to-r from-blue-50 to-indigo-50">
          <div className="flex items-center justify-between p-6">
            <div className="flex items-center space-x-3">
              {/* 실시간 배지 */}
              <div className={`px-3 py-1 text-white text-sm font-medium rounded-full flex items-center ${isCompleted ? 'bg-green-500' : 'bg-red-500 animate-pulse'}`}>
                {!isCompleted && (
                  <div className="animate-spin rounded-full h-4 w-4 border-2 border-white border-t-transparent mr-2"></div>
                )}
                {isCompleted ? '완료' : '분석중'}
              </div>
              <div>
                <h2 className="text-xl font-bold text-gray-900">
                  {chartData.stockName} ({chartData.stockCode}) 기술적 분석
                </h2>
                <p className="text-sm text-gray-600 mt-1">
                {isCompleted ? '분석이 완료되었습니다. 최종 문서를 확인해보세요.' : chartData.message}
                </p>
              </div>
            </div>
            
            {isCompleted ? (
            <button
              onClick={handleClose}
              className="px-4 py-2 bg-white text-green-600 hover:bg-gray-50 rounded-lg transition-colors duration-200 font-medium text-sm shadow-sm"
            >
              최종 문서 보러가기
            </button>
            ) : (
            <button
              onClick={handleClose}
              className="p-2 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded-lg transition-all duration-200"
              aria-label="닫기"
            >
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
            )}
          </div>
        </div>

        {/* 컨텐츠 영역 */}
        <div className="p-6 overflow-y-auto max-h-[calc(85vh-200px)]">
          {/* 차트 컴포넌트 렌더링 */}
          <div className="space-y-6">
            {normalizedComponents.map((component, index) => (
              <div 
                key={index} 
                className={
                  component.type?.includes('chart') 
                    ? "chart-container bg-white rounded-lg shadow-sm border border-gray-100 overflow-hidden"
                    : ""
                }
              >
                <MessageComponentRenderer 
                  component={component}
                  isChartPair={false}
                />
              </div>
            ))}
          </div>

          {/* 추가 분석 진행 상태 표시 */}
          <div className={`mt-6 p-4 rounded-lg ${isCompleted ? 'bg-green-50 border border-green-200' : 'bg-blue-50 border border-blue-200'}`}>
            <div className="flex items-center justify-center text-sm">
              {!isCompleted ? (
                <>
                  <div className="animate-spin rounded-full h-4 w-4 border-2 border-blue-500 border-t-transparent mr-3"></div>
                  <span className="text-blue-700 font-medium">나머지 분석을 진행 중입니다. 잠시만 기다려주세요...</span>
                </>
              ) : (
                <>
                  <div className="flex items-center justify-center w-4 h-4 mr-3 bg-green-500 rounded-full">
                    <svg className="w-3 h-3 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                    </svg>
                  </div>
                  <span className="text-green-700 font-medium">모든 분석이 완료되었습니다!</span>
                </>
              )}
            </div>
          </div>
        </div>

        {/* <div className="px-6 py-4 bg-gray-50 border-t border-gray-200">
          <div className="flex justify-end">
            <button
              onClick={handleClose}
              className="px-4 py-2 text-gray-700 bg-white hover:bg-gray-100 border border-gray-300 rounded-lg transition-colors duration-200 font-medium"
            >
              닫기
            </button>
          </div>
        </div> */}
      </div>
    </div>
  );
} 