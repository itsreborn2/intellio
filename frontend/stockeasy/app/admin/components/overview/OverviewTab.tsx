'use client';

import React, { useState, useEffect, useRef } from 'react';
import type { Data, Layout, Config } from 'plotly.js';

// 분리된 컴포넌트들 임포트
import UserAccumulationChart from './UserAccumulationChart';
import UserRegistrationChart from './UserRegistrationChart';
import UserActivityChart from './UserActivityChart';
import ChatUsageChart from './ChatUsageChart';
import DailyUserActivityChart from './DailyUserActivityChart';
import SummaryCards from './SummaryCards';

// 타입 임포트
import { UserStat } from '@/types/api/user-stats';

// 목업 데이터 - 일별 통계
const MOCK_DAILY_STATS: UserStat[] = [
  { 
    id: 1,
    stat_type: 'DAILY',
    report_at: '2025-06-20', 
    total_users: 1030, 
    new_users: 20, 
    active_users: 120, 
    active_user_percentage: 0.12,
    sessions_per_user: 4.2,
    new_chat_sessions: 87,
    total_chat_sessions: 430,
    created_at: '2025-06-21T00:00:00Z'
  },
  { 
    id: 2,
    stat_type: 'DAILY',
    report_at: '2025-06-21', 
    total_users: 1050, 
    new_users: 20, 
    active_users: 140, 
    active_user_percentage: 0.13,
    sessions_per_user: 3.8,
    new_chat_sessions: 72,
    total_chat_sessions: 460,
    created_at: '2025-06-22T00:00:00Z'
  },
  { 
    id: 3,
    stat_type: 'DAILY',
    report_at: '2025-06-22', 
    total_users: 1080, 
    new_users: 30, 
    active_users: 150, 
    active_user_percentage: 0.14,
    sessions_per_user: 4.5,
    new_chat_sessions: 91,
    total_chat_sessions: 520,
    created_at: '2025-06-23T00:00:00Z'
  },
  { 
    id: 4,
    stat_type: 'DAILY',
    report_at: '2025-06-23', 
    total_users: 1100, 
    new_users: 20, 
    active_users: 170, 
    active_user_percentage: 0.15,
    sessions_per_user: 4.1,
    new_chat_sessions: 105,
    total_chat_sessions: 540,
    created_at: '2025-06-24T00:00:00Z'
  },
  { 
    id: 5,
    stat_type: 'DAILY',
    report_at: '2025-06-24', 
    total_users: 1120, 
    new_users: 20, 
    active_users: 160, 
    active_user_percentage: 0.14,
    sessions_per_user: 3.9,
    new_chat_sessions: 80,
    total_chat_sessions: 510,
    created_at: '2025-06-25T00:00:00Z'
  },
  { 
    id: 6,
    stat_type: 'DAILY',
    report_at: '2025-06-25', 
    total_users: 1150, 
    new_users: 30, 
    active_users: 190, 
    active_user_percentage: 0.17,
    sessions_per_user: 4.6,
    new_chat_sessions: 98,
    total_chat_sessions: 570,
    created_at: '2025-06-26T00:00:00Z'
  }
];

// 목업 데이터 - 월별 통계
const MOCK_MONTHLY_STATS: UserStat[] = [
  { 
    id: 101,
    stat_type: 'MONTHLY',
    report_at: '2025-01-01', 
    total_users: 800, 
    new_users: 120, 
    active_users: 350, 
    active_user_percentage: 0.44,
    sessions_per_user: 3.2,
    new_chat_sessions: 210,
    total_chat_sessions: 1120,
    created_at: '2025-02-01T00:00:00Z'
  },
  { 
    id: 102,
    stat_type: 'MONTHLY',
    report_at: '2025-02-01', 
    total_users: 850, 
    new_users: 50, 
    active_users: 370, 
    active_user_percentage: 0.44,
    sessions_per_user: 3.5,
    new_chat_sessions: 240,
    total_chat_sessions: 1295,
    created_at: '2025-03-01T00:00:00Z'
  },
  { 
    id: 103,
    stat_type: 'MONTHLY',
    report_at: '2025-03-01', 
    total_users: 900, 
    new_users: 50, 
    active_users: 390, 
    active_user_percentage: 0.43,
    sessions_per_user: 3.7,
    new_chat_sessions: 280,
    total_chat_sessions: 1443,
    created_at: '2025-04-01T00:00:00Z'
  },
  { 
    id: 104,
    stat_type: 'MONTHLY',
    report_at: '2025-04-01', 
    total_users: 980, 
    new_users: 80, 
    active_users: 420, 
    active_user_percentage: 0.43,
    sessions_per_user: 3.9,
    new_chat_sessions: 310,
    total_chat_sessions: 1638,
    created_at: '2025-05-01T00:00:00Z'
  },
  { 
    id: 105,
    stat_type: 'MONTHLY',
    report_at: '2025-05-01', 
    total_users: 1050, 
    new_users: 70, 
    active_users: 460, 
    active_user_percentage: 0.44,
    sessions_per_user: 4.1,
    new_chat_sessions: 330,
    total_chat_sessions: 1886,
    created_at: '2025-06-01T00:00:00Z'
  },
  { 
    id: 106,
    stat_type: 'MONTHLY',
    report_at: '2025-06-01', 
    total_users: 1150, 
    new_users: 100, 
    active_users: 510, 
    active_user_percentage: 0.44,
    sessions_per_user: 4.4,
    new_chat_sessions: 380,
    total_chat_sessions: 2244,
    created_at: '2025-07-01T00:00:00Z'
  }
];

interface PlotProps {
  data?: Data[];
  layout?: Partial<Layout>;
  config?: Partial<Config>;
  style?: React.CSSProperties;
}

interface OverviewTabProps {
  DynamicPlot: React.ComponentType<PlotProps>;
  chartLayout: Partial<Layout>;
  chartConfig: Partial<Config>;
}

/**
 * OverviewTab 컴포넌트
 * 어드민 대시보드의 개요 탭에 표시되는 사용자 통계 정보와 차트를 관리
 */
export default function OverviewTab({ 
  DynamicPlot, 
  chartLayout, 
  chartConfig 
}: OverviewTabProps) {
  const [dailyStats, setDailyStats] = useState<UserStat[]>([]);
  const [monthlyStats, setMonthlyStats] = useState<UserStat[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isError, setIsError] = useState(false);
  const isMounted = useRef(true); // 컴포넌트 마운트 상태 관리
  
  useEffect(() => {
    const fetchData = async () => {
      if (!isMounted.current) return;
      
      try {
        setIsLoading(true);
        setIsError(false);
        
        // API 요청 블록 - DB에서 실제 데이터를 가져옴
        // API의 기본 URL 가져오기
        let API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || '';
        
        // API_BASE_URL이 이미 /api로 끝나는지 확인하고 중복 방지
        if (API_BASE_URL && API_BASE_URL.endsWith('/api')) {
          API_BASE_URL = API_BASE_URL.substring(0, API_BASE_URL.length - 4); // '/api' 제거
        }
        
        if (API_BASE_URL) {
          try {
            const dailyUrl = `${API_BASE_URL}/api/v1/stats/users/?stat_type=DAILY`;
            console.log('실제 API 요청 URL (일일):', dailyUrl);
            
            // 일일 통계 데이터 가져오기
            const dailyResponse = await fetch(dailyUrl);
            
            if (!dailyResponse.ok) {
              throw new Error(`일일 통계 API 오류: ${dailyResponse.status} - ${await dailyResponse.text()}`);
            }
            
            const dailyDataResponse = await dailyResponse.json();
            console.log('일일 통계 응답 받음:', dailyDataResponse);
            
            // 월간 통계 데이터 가져오기
            const monthlyUrl = `${API_BASE_URL}/api/v1/stats/users/?stat_type=MONTHLY`;
            console.log('실제 API 요청 URL (월간):', monthlyUrl);
            const monthlyResponse = await fetch(monthlyUrl);
            
            if (!monthlyResponse.ok) {
              throw new Error(`월간 통계 API 오류: ${monthlyResponse.status} - ${await monthlyResponse.text()}`);
            }
            
            const monthlyDataResponse = await monthlyResponse.json();
            console.log('월간 통계 응답 받음:', monthlyDataResponse);
            
            const dailyData = dailyDataResponse.data;
            const monthlyData = monthlyDataResponse.data;

            // API에서 가져온 데이터로 상태 업데이트
            if (dailyDataResponse.success && Array.isArray(dailyData) && dailyData.length > 0) {
              setDailyStats(dailyData);
              console.log('일일 통계 데이터 적용 완료:', dailyData.length);
            } else {
              console.warn('반환된 일일 통계 데이터가 없거나 유효하지 않음, 목업 데이터 사용');
              setDailyStats([...MOCK_DAILY_STATS]);
            }
            
            if (monthlyDataResponse.success && Array.isArray(monthlyData) && monthlyData.length > 0) {
              setMonthlyStats(monthlyData);
              console.log('월간 통계 데이터 적용 완료:', monthlyData.length);
            } else {
              console.warn('반환된 월간 통계 데이터가 없거나 유효하지 않음, 목업 데이터 사용');
              setMonthlyStats([...MOCK_MONTHLY_STATS]);
            }
            
            // API 가 성공적으로 처리되면 여기서 반환
            return;
          } catch (error) {
            console.error('API 호출 실패:', error);
            // API 연결 실패 로그
          }
        } else {
          console.warn('API_BASE_URL이 없어 API 요청을 실패했습니다. 환경 변수를 확인하세요.');
        }
        
        // API 요청 실패 시 목업 데이터 사용 (폴백)
        console.log('API 요청 실패로 목업 데이터를 사용합니다:', { 
          dailyMockLength: MOCK_DAILY_STATS.length, 
          monthlyMockLength: MOCK_MONTHLY_STATS.length 
        });
        
        setDailyStats([...MOCK_DAILY_STATS]);
        setMonthlyStats([...MOCK_MONTHLY_STATS]);
      } catch (error) {
        console.error('데이터 처리 중 오류 발생:', error);
        setIsError(true);
        setDailyStats([]);
        setMonthlyStats([]);
      } finally {
        setIsLoading(false);
      }
    };
    
    fetchData();
  }, []);

  
  // 로딩 중 표시
  if (isLoading) {
    return <div className="p-8 text-center">통계 데이터를 불러오는 중...</div>;
  }

  // 오류 표시
  if (isError) {
    return <div className="p-8 text-center text-red-500">통계 데이터를 불러오는 데 실패했습니다.</div>;
  }

  // 데이터가 없을 경우 표시
  if (dailyStats.length === 0 || monthlyStats.length === 0) {
    return <div className="p-8 text-center">사용 가능한 통계 데이터가 없습니다.</div>;
  }

  return (
    <div className="space-y-6">
      {/* 요약 통계 카드 */}
      <SummaryCards 
        dailyStats={dailyStats} 
        monthlyStats={monthlyStats} 
      />

      {/* 누적 가입자 현황 차트 */}
      <UserAccumulationChart 
        DynamicPlot={DynamicPlot} 
        chartLayout={chartLayout} 
        chartConfig={chartConfig} 
        dailyStats={dailyStats} 
        monthlyStats={monthlyStats} 
      />

      {/* 가입자 현황 차트 */}
      <UserRegistrationChart 
        DynamicPlot={DynamicPlot} 
        chartLayout={chartLayout} 
        chartConfig={chartConfig} 
        dailyStats={dailyStats} 
        monthlyStats={monthlyStats} 
      />

      {/* 접속 현황 차트 */}
      <UserActivityChart 
        DynamicPlot={DynamicPlot} 
        chartLayout={chartLayout} 
        chartConfig={chartConfig} 
        dailyStats={dailyStats} 
        monthlyStats={monthlyStats} 
      />

      {/* 채팅 현황 차트 */}
      <ChatUsageChart 
        DynamicPlot={DynamicPlot} 
        chartLayout={chartLayout} 
        chartConfig={chartConfig} 
        dailyStats={dailyStats}
      />

      {/* 일일 사용자 활동 차트 */}
      <DailyUserActivityChart 
        DynamicPlot={DynamicPlot} 
        chartLayout={chartLayout} 
        chartConfig={chartConfig} 
        dailyStats={dailyStats}
      />
    </div>
  );
}