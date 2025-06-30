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

interface UserRegistrationChartProps {
  DynamicPlot: React.ComponentType<PlotProps>;
  chartLayout: Partial<Layout>;
  chartConfig: Partial<Config>;
  dailyStats: UserStat[];
  monthlyStats: UserStat[];
}

/**
 * 가입자 현황을 보여주는 차트 컴포넌트
 * 일별/월별 신규 가입자 수를 바 차트로 표시
 */
export default function UserRegistrationChart({ 
  DynamicPlot, 
  chartLayout, 
  chartConfig,
  dailyStats,
  monthlyStats 
}: UserRegistrationChartProps) {
  // 일별 데이터 준비
  const dailyDates = dailyStats.map(stat => stat.report_at);
  const dailyNewUsers = dailyStats.map(stat => stat.new_users);

  // 월별 데이터 준비
  const monthlyLabels = monthlyStats.map(stat => {
    const date = new Date(stat.report_at);
    return `${date.getFullYear()}-${date.getMonth() + 1}`;
  });
  const monthlyNewUsers = monthlyStats.map(stat => stat.new_users);

  return (
    <Card className="rounded-[6px] bg-white">
      <CardHeader>
        <CardTitle>가입자 현황</CardTitle>
      </CardHeader>
      <CardContent className="grid grid-cols-10 gap-4 px-0 pb-0">
        <div className="col-span-7">
          <h3 className="font-semibold mb-1 text-center text-sm">최근 30일</h3>
          <div style={{ height: '300px' }}>
            <DynamicPlot
              data={[
                {
                  x: dailyDates,
                  y: dailyNewUsers,
                  type: 'bar' as const,
                  marker: { color: 'oklch(0.75 0.10 257)', cornerradius: 6 } as any,
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
                  y: monthlyNewUsers,
                  type: 'bar' as const,
                  marker: { color: 'oklch(0.65 0.12 257)', cornerradius: 6 } as any,
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
