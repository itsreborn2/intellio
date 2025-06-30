'use client';

import React from 'react';
import { 
  Card, 
  CardContent, 
  CardHeader, 
  CardTitle,
  CardDescription 
} from "intellio-common/components/ui/card";
import { cn } from "intellio-common/lib/utils";
import { UserStat } from '@/types/api/user-stats';

// 변화 유형에 따른 텍스트 색상 매핑
const changeColor = {
  increase: 'text-red-500',  // 상승은 빨간색 (한국 주식 시장 관례)
  decrease: 'text-blue-500', // 하락은 파란색
  neutral: 'text-gray-500',  // 변동 없음은 회색
};

// 요약 통계 카드 컴포넌트 속성 정의
interface SummaryStatCardProps {
  title: string;            // 카드 제목
  value: string | number;   // 현재 표시할 값
  previousValue?: string | number; // 전일 표시할 값 (선택적)
  description?: string;     // 추가 설명
  change?: string;          // 변화량 표시 (예: '+15%')
  type?: 'increase' | 'decrease' | 'neutral'; // 변화 유형
  cardClassName?: string;   // 추가 클래스명
}

/**
 * 요약 통계 카드 컴포넌트
 * 대시보드에서 주요 지표를 간결하게 표시하는 카드 컴포넌트
 */
function SummaryStatCard({
  title,
  value,
  previousValue,
  description,
  change,
  type = 'neutral',
  cardClassName,
}: SummaryStatCardProps) {
  // 현재 값과 이전 값이 모두 숫자일 경우 변화율 계산
  const calculateChangeRate = () => {
    if (previousValue !== undefined && typeof previousValue === 'number' && typeof value === 'number' && previousValue !== 0) {
      const diff = value - previousValue;
      const changeRate = (diff / previousValue) * 100;
      
      // 변화율에 따라 타입 결정
      let calculatedType: 'increase' | 'decrease' | 'neutral' = 'neutral';
      if (changeRate > 0) calculatedType = 'increase';
      else if (changeRate < 0) calculatedType = 'decrease';
      
      return {
        diff,
        changeRate: changeRate.toFixed(1),
        calculatedType
      };
    }
    return null;
  };
  
  // 변화율 계산
  const changeInfo = calculateChangeRate();
  const displayType = changeInfo ? changeInfo.calculatedType : type;
  const displayChange = change || (changeInfo ? `${changeInfo.changeRate}%` : undefined);
  
  return (
    <Card className={cn("rounded-[6px] bg-white", cardClassName)}>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="text-sm font-medium">{title}</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="p-6 pt-0">
          <div className="text-2xl font-bold">{value}</div>
          {previousValue !== undefined && (
            <div className="text-xs text-gray-500 mt-1">
              전일: {typeof previousValue === 'number' ? previousValue.toLocaleString() : previousValue}
            </div>
          )}
          {displayChange && (
            <p className={`text-xs ${changeColor[displayType]} mt-1`}>
              {displayType === 'increase' ? '+' : ''}{displayChange}
            </p>
          )}
          {description && (
            <CardDescription className="text-xs mt-1">{description}</CardDescription>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

interface SummaryCardsProps {
  dailyStats: UserStat[];
  monthlyStats: UserStat[];
}

/**
 * 사용자 통계 요약 카드 컴포넌트
 * 전체 사용자 수, 일일 가입자 수, 활성 사용자 수 표시
 */
export default function SummaryCards({ dailyStats, monthlyStats }: SummaryCardsProps) {
  // 최신 데이터 가져오기 (마지막 항목)
  const latestDailyStats = dailyStats.length > 0 ? dailyStats[dailyStats.length - 1] : null;
  const latestMonthlyStats = monthlyStats.length > 0 ? monthlyStats[monthlyStats.length - 1] : null;
  
  // 전일 데이터 가져오기 (최신 데이터의 이전 항목)
  const previousDailyStats = dailyStats.length > 1 ? dailyStats[dailyStats.length - 2] : null;
  const previousMonthlyStats = monthlyStats.length > 1 ? monthlyStats[monthlyStats.length - 2] : null;
  
  // 현재 표시할 값들
  const totalUsers = latestDailyStats?.total_users || 0;
  const newUsers = latestDailyStats?.new_users || 0;
  const activeUsers = latestDailyStats?.active_users || 0;
  const monthlyActiveUsers = latestMonthlyStats?.active_users || 0;
  
  // 전일 표시할 값들
  const previousTotalUsers = previousDailyStats?.total_users;
  const previousNewUsers = previousDailyStats?.new_users;
  const previousActiveUsers = previousDailyStats?.active_users;
  const previousMonthlyActiveUsers = previousMonthlyStats?.active_users;

  // 각 통계의 타입 계산 (전일 대비 데이터가 있는 경우)
  const calculateType = (current: number, previous?: number): 'increase' | 'decrease' | 'neutral' => {
    if (!previous) return 'neutral';
    if (current > previous) return 'increase';
    if (current < previous) return 'decrease';
    return 'neutral';
  };

  return (
    <div className="grid gap-4 grid-cols-1 md:grid-cols-2 lg:grid-cols-4">
      <SummaryStatCard 
        title="전체 사용자 수"
        value={totalUsers.toLocaleString()}
        previousValue={previousTotalUsers?.toLocaleString()}
        type={calculateType(totalUsers, previousTotalUsers)}
      />
      <SummaryStatCard
        title="일일 가입자 수"
        value={newUsers.toLocaleString()}
        previousValue={previousNewUsers?.toLocaleString()}
        type={calculateType(newUsers, previousNewUsers)}
      />
      <SummaryStatCard
        title="일일 활성 사용자 수"
        value={activeUsers.toLocaleString()}
        previousValue={previousActiveUsers?.toLocaleString()}
        type={calculateType(activeUsers, previousActiveUsers)}
      />
      <SummaryStatCard
        title="월간 활성 사용자 수"
        value={monthlyActiveUsers.toLocaleString()}
        previousValue={previousMonthlyActiveUsers?.toLocaleString()}
        type={calculateType(monthlyActiveUsers, previousMonthlyActiveUsers)}
      />
    </div>
  );
}
