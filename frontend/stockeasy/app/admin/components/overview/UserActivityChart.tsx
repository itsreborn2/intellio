'use client';

import React from 'react';
import type { Data, Layout, Config } from 'plotly.js';
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "intellio-common/components/ui/card";
import { UserStat } from '@/types/api/user-stats';

interface PlotProps {
  data?: Data[];
  layout?: Partial<Layout>;
  config?: Partial<Config>;
  style?: React.CSSProperties;
}

interface UserActivityChartProps {
  DynamicPlot: React.ComponentType<PlotProps>;
  chartLayout: Partial<Layout>;
  chartConfig: Partial<Config>;
  dailyStats: UserStat[];
  monthlyStats: UserStat[];
}

/**
 * 접속 현황을 보여주는 차트 컴포넌트
 * 일별/월별 활성 사용자 수를 바 차트로 표시
 */
export default function UserActivityChart({ 
  DynamicPlot, 
  chartLayout, 
  chartConfig,
  dailyStats,
  monthlyStats 
}: UserActivityChartProps) {
  // 일별 데이터 준비
  const dailyDates = dailyStats.map(stat => stat.report_at);
  const dailyActiveUsers = dailyStats.map(stat => stat.active_users);

  // 월별 데이터 준비
  const monthlyLabels = monthlyStats.map(stat => {
    const date = new Date(stat.report_at);
    return `${date.getFullYear()}-${date.getMonth() + 1}`;
  });
  const monthlyActiveUsers = monthlyStats.map(stat => stat.active_users);

  return (
    <Card className="rounded-[6px] bg-white">
      <CardHeader>
        <CardTitle>접속 현황</CardTitle>
      </CardHeader>
      <CardContent className="grid grid-cols-10 gap-4 px-0 pb-0">
        <div className="col-span-7">
          <h3 className="font-semibold mb-1 text-center text-sm">최근 30일</h3>
          <div style={{ height: '300px' }}>
            <DynamicPlot
              data={[
                {
                  x: dailyDates,
                  y: dailyActiveUsers,
                  type: 'bar' as const,
                  marker: { color: 'oklch(0.7 0.15 150)', cornerradius: 6 } as any,
                },
              ]}
              layout={chartLayout}
              style={{ width: '100%', height: '100%' }}
              config={chartConfig}
            />
          </div>
        </div>
        <div className="col-span-3">
          <h3 className="font-semibold mb-1 text-center text-sm">월별</h3>
          <div style={{ height: '300px' }}>
            <DynamicPlot
              data={[
                {
                  x: monthlyLabels,
                  y: monthlyActiveUsers,
                  type: 'bar' as const,
                  marker: { color: 'oklch(0.6 0.18 150)', cornerradius: 6 } as any,
                },
              ]}
              layout={chartLayout}
              style={{ width: '100%', height: '100%' }}
              config={chartConfig}
            />
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
