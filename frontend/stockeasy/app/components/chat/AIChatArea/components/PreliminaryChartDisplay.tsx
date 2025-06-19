/**
 * PreliminaryChartDisplay.tsx
 * 실시간 기술적 분석 차트를 표시하는 컴포넌트
 */
'use client';

import React from 'react';
import { MessageComponentRenderer } from './MessageComponentRenderer';

interface PreliminaryChartData {
  components: any[];
  message: string;
  timestamp: number;
  stockCode: string;
  stockName: string;
}

interface PreliminaryChartDisplayProps {
  chartData: PreliminaryChartData;
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

export function PreliminaryChartDisplay({ chartData }: PreliminaryChartDisplayProps) {
  // 디버깅을 위한 데이터 로깅
  
  // 차트 데이터 유효성 검증
  // const validation = validateChartData(chartData);
  
  // if (!validation.isValid) {
  //   console.warn('[PreliminaryChartDisplay] 차트 데이터 검증 실패:', validation.errorMessage);
  //   return (
  //     <div className="preliminary-chart-container relative">
  //       <div className="text-slate-600 text-sm p-4 bg-yellow-50 border border-yellow-200 rounded">
  //         ⚠️ {validation.errorMessage || '차트 데이터가 유효하지 않습니다.'} 다시 시도해주세요.
  //       </div>
  //     </div>
  //   );
  // }


  // 컴포넌트 정규화 제거 - tech agent는 이미 표준 구조로 데이터를 생성함
  // const normalizedComponents = chartData.components.map(normalizeChartComponent);
  const normalizedComponents = chartData.components; // 직접 전달

  return (
    <div className="preliminary-chart-container relative">
      {/* 실시간 배지 */}
      <div className="absolute top-4 right-4 flex items-center space-x-2">
        <div className="realtime-badge">
          실시간
        </div>
      </div>

      {/* 로딩 애니메이션 */}
      <div className="flex items-center mb-4">
        <div className="loading-dots mr-3">
          <span></span>
          <span></span>
          <span></span>
        </div>
        <span className="text-slate-700 font-medium text-sm">차트가 준비되었습니다. 추가 분석을 진행하고 있습니다...</span>
      </div>

      {/* 메시지 표시 */}
      <div className="mb-4">
        <p className="text-slate-700 text-sm">{chartData.message}</p>
      </div>

      {/* 차트 컴포넌트 렌더링 */}
      <div className="space-y-4">
        {normalizedComponents.map((component, index) => (
          <div key={index} className="chart-container">
            <MessageComponentRenderer 
              component={component}
              isChartPair={true}
            />
          </div>
        ))}
      </div>

      {/* 추가 분석 진행 상태 표시 */}
      <div className="status-message mt-4">
        <div className="flex items-center text-sm">
          <div className="animate-spin rounded-full h-3 w-3 border border-blue-500 border-t-transparent mr-2"></div>
          <span>나머지 분석을 진행 중입니다. 잠시만 기다려주세요...</span>
        </div>
      </div>

    </div>
  );
} 