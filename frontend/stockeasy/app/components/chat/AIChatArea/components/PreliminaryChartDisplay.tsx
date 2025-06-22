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
  stockInfo?: any; // 종목 기본 정보
}

interface PreliminaryChartDisplayProps {
  chartData: PreliminaryChartData;
  onClose?: () => void;
  isCompleted?: boolean;
  onViewFinalReport?: () => void;
}

/**
 * 숫자를 한국 화폐 형식으로 포맷하는 함수
 */
function formatKoreanCurrency(value: string | number | null | undefined): string {
  if (value === null || value === undefined || value === '' || value === '-' || value === '0') {
    return '-';
  }
  
  // 문자열에서 숫자가 아닌 문자 제거 후 파싱
  const cleanValue = typeof value === 'string' ? value.replace(/[^0-9.-]/g, '') : value;
  const numValue = typeof cleanValue === 'string' ? parseFloat(cleanValue) : cleanValue;
  
  if (isNaN(numValue) || numValue === 0) {
    return '-';
  }
  
  // API에서 제공하는 값이 이미 억원 단위인 것으로 보임 (시가총액 "673" = 673억원)
  if (numValue >= 10000) {
    return `${(numValue / 10000).toLocaleString('ko-KR', { maximumFractionDigits: 2, minimumFractionDigits: 2 })}조원`;
  } else {
    return `${numValue.toLocaleString('ko-KR')}억원`;
  }
}

/**
 * 퍼센트 값을 포맷하는 함수
 */
function formatPercent(value: string | number | null | undefined): string {
  if (value === null || value === undefined || value === '' || value === '-' || value === '0') {
    return '-';
  }
  
  const cleanValue = typeof value === 'string' ? value.replace(/[^0-9.-]/g, '') : value;
  const numValue = typeof cleanValue === 'string' ? parseFloat(cleanValue) : cleanValue;
  
  if (isNaN(numValue)) {
    return '-';
  }
  
  return `${numValue.toFixed(2)}%`;
}

/**
 * 일반 숫자를 포맷하는 함수
 */
function formatNumber(value: string | number | null | undefined, suffix: string = '', useAbsoluteValue: boolean = false): string {
  if (value === null || value === undefined || value === '' || value === '-' || value === '0') {
    return '-';
  }
  
  const cleanValue = typeof value === 'string' ? value.replace(/[^0-9.-]/g, '') : value;
  let numValue = typeof cleanValue === 'string' ? parseFloat(cleanValue) : cleanValue;
  
  if (isNaN(numValue)) {
    return '-';
  }
  
  // 절대값 사용 옵션
  if (useAbsoluteValue) {
    numValue = Math.abs(numValue);
  }
  
  return numValue.toLocaleString('ko-KR') + suffix;
}

/**
 * 기업 정보를 표시하는 컴포넌트
 */
function StockInfoDisplay({ stockInfo }: { stockInfo: any }) {
  
  if (!stockInfo) {
    console.log('[StockInfoDisplay] stockInfo가 null 또는 undefined입니다.');
    return null;
  }


  return (
    <div className="mb-6 bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
      {/* 헤더 */}
      <div className="bg-gradient-to-r from-blue-50 to-indigo-50 px-6 py-4 border-b border-gray-100">
        <h3 className="text-lg font-bold text-gray-800 flex items-center">
          <div className="w-2 h-2 bg-blue-500 rounded-full mr-3"></div>
          기업 정보
          <span className="text-xs text-gray-500 ml-2 font-normal">(최근 결산 기준)</span>
        </h3>
      </div>

      <div className="p-6 space-y-6">
        {/* 기본 정보 */}
        <div>
          <h4 className="text-sm font-semibold text-gray-700 mb-3 uppercase tracking-wide">기본 정보</h4>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="bg-gray-50 rounded-lg p-3">
              <div className="text-xs text-gray-500 mb-1">시장</div>
              <div className="font-semibold text-gray-900">{stockInfo.market || '-'}</div>
            </div>
            <div className="bg-gray-50 rounded-lg p-3">
              <div className="text-xs text-gray-500 mb-1">시가총액</div>
              <div className="font-semibold text-green-600">{formatKoreanCurrency(stockInfo.mac)}</div>
            </div>
            <div className="bg-gray-50 rounded-lg p-3">
              <div className="text-xs text-gray-500 mb-1">250일 최고</div>
              <div className="font-semibold text-red-600">{formatNumber(stockInfo['250hgst'], '원')}</div>
            </div>
            <div className="bg-gray-50 rounded-lg p-3">
              <div className="text-xs text-gray-500 mb-1">250일 최저</div>
              <div className="font-semibold text-blue-600">{formatNumber(stockInfo['250lwst'], '원', true)}</div>
            </div>
          </div>
        </div>

        {/* 재무 지표 */}
        <div>
          <h4 className="text-sm font-semibold text-gray-700 mb-3 uppercase tracking-wide">재무 지표</h4>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
            <div className="bg-gradient-to-br from-purple-50 to-purple-100 rounded-lg p-3 border border-purple-200">
              <div className="text-xs text-purple-600 mb-1 font-medium">PER</div>
              <div className="font-bold text-purple-800">{formatNumber(stockInfo.per, '배')}</div>
            </div>
            <div className="bg-gradient-to-br from-indigo-50 to-indigo-100 rounded-lg p-3 border border-indigo-200">
              <div className="text-xs text-indigo-600 mb-1 font-medium">PBR</div>
              <div className="font-bold text-indigo-800">{formatNumber(stockInfo.pbr, '배')}</div>
            </div>
            <div className="bg-gradient-to-br from-emerald-50 to-emerald-100 rounded-lg p-3 border border-emerald-200">
              <div className="text-xs text-emerald-600 mb-1 font-medium">ROE</div>
              <div className="font-bold text-emerald-800">{formatPercent(stockInfo.roe)}</div>
            </div>
            <div className="bg-gradient-to-br from-amber-50 to-amber-100 rounded-lg p-3 border border-amber-200">
              <div className="text-xs text-amber-600 mb-1 font-medium">EPS</div>
              <div className="font-bold text-amber-800">{formatNumber(stockInfo.eps, '원')}</div>
            </div>
            <div className="bg-gradient-to-br from-rose-50 to-rose-100 rounded-lg p-3 border border-rose-200">
              <div className="text-xs text-rose-600 mb-1 font-medium">BPS</div>
              <div className="font-bold text-rose-800">{formatNumber(stockInfo.bps, '원')}</div>
            </div>
          </div>
        </div>

        {/* 실적 정보 */}
        <div>
          <h4 className="text-sm font-semibold text-gray-700 mb-3 uppercase tracking-wide">실적 정보</h4>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="bg-gradient-to-r from-blue-500 to-blue-600 rounded-lg p-4 text-white">
              <div className="text-xs opacity-90 mb-1">매출액</div>
              <div className="font-bold text-lg">{formatKoreanCurrency(stockInfo.sale_amt)}</div>
            </div>
            <div className="bg-gradient-to-r from-green-500 to-green-600 rounded-lg p-4 text-white">
              <div className="text-xs opacity-90 mb-1">영업이익</div>
              <div className="font-bold text-lg">{formatKoreanCurrency(stockInfo.bus_pro)}</div>
            </div>
            <div className="bg-gradient-to-r from-purple-500 to-purple-600 rounded-lg p-4 text-white">
              <div className="text-xs opacity-90 mb-1">당기순이익</div>
              <div className="font-bold text-lg">{formatKoreanCurrency(stockInfo.cup_nga)}</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
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

      {/* 팝업 컨테이너 - 채팅영역보다 조금 큰 너비로 제한 */}
      <div 
        className={`relative bg-white rounded-xl shadow-2xl w-full max-w-5xl max-h-[85vh] overflow-hidden transform transition-all duration-300 ${
          isAnimating 
            ? 'scale-100 opacity-100 translate-y-0' 
            : 'scale-95 opacity-0 translate-y-8'
        }`}
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
          {/* 기업 정보 표시 */}
          <StockInfoDisplay stockInfo={chartData.stockInfo} />
          
          {/* 구분선 */}
          <div className="flex items-center my-8">
            <div className="flex-1 h-px bg-gradient-to-r from-transparent via-gray-300 to-transparent"></div>
            <div className="px-4 py-2 bg-gradient-to-r from-blue-50 to-indigo-50 rounded-full border border-blue-200">
              <span className="text-sm font-semibold text-blue-700 flex items-center">
                <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                </svg>
                기술적 분석 차트
              </span>
            </div>
            <div className="flex-1 h-px bg-gradient-to-r from-transparent via-gray-300 to-transparent"></div>
          </div>
          
          {/* 차트 컴포넌트 렌더링 */}
          <div className="space-y-8">
            {normalizedComponents.map((component, index) => {
              const isChart = component.type?.includes('chart');
              const chartTypeMap: Record<string, string> = {
                'price_chart': '주가 차트',
                'technical_indicator_chart': '기술적 지표 차트',
                'volume_chart': '거래량 차트'
              };
              
              const chartTitle = isChart ? chartTypeMap[component.type] || '차트' : '';
              
              return (
                <div 
                  key={index} 
                  className={`relative ${
                    isChart 
                      ? "bg-white rounded-xl shadow-md border border-gray-200 overflow-hidden hover:shadow-lg transition-shadow duration-200"
                      : "bg-gray-50 rounded-lg border border-gray-100 p-4"
                  }`}
                >
                  {/* 차트 타입별 헤더 */}
                  {isChart && (
                    <div className="bg-gradient-to-r from-slate-50 to-slate-100 px-6 py-3 border-b border-gray-200">
                      <div className="flex items-center justify-between">
                        <h4 className="text-lg font-semibold text-gray-800 flex items-center">
                          <div className={`w-3 h-3 rounded-full mr-3 ${
                            component.type === 'price_chart' ? 'bg-blue-500' :
                            component.type === 'technical_indicator_chart' ? 'bg-purple-500' :
                            'bg-green-500'
                          }`}></div>
                          {chartTitle}
                        </h4>
                        <div className="text-xs text-gray-500 bg-white px-2 py-1 rounded-full border">
                          {index + 1} / {normalizedComponents.length}
                        </div>
                      </div>
                    </div>
                  )}
                  
                                     {/* 차트 내용 */}
                   <div className={isChart ? "" : "p-4"}>
                     <MessageComponentRenderer 
                       component={component}
                       isChartPair={false}
                     />
                   </div>
                  
                  {/* 차트 간 구분선 (마지막 차트 제외) */}
                  {isChart && index < normalizedComponents.length - 1 && (
                    <div className="absolute -bottom-4 left-1/2 transform -translate-x-1/2 w-20 h-px bg-gradient-to-r from-transparent via-gray-300 to-transparent"></div>
                  )}
                </div>
              );
            })}
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