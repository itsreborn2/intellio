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

interface UserAccumulationChartProps {
  DynamicPlot: React.ComponentType<PlotProps>;
  chartLayout: Partial<Layout>;
  chartConfig: Partial<Config>;
  dailyStats: UserStat[];
  monthlyStats: UserStat[];
}

/**
 * 누적 가입자 현황을 보여주는 차트 컴포넌트
 * 일별/월별 차트를 함께 표시
 */
export default function UserAccumulationChart({ 
  DynamicPlot, 
  chartLayout, 
  chartConfig,
  dailyStats,
  monthlyStats
}: UserAccumulationChartProps) {
  // 일별 데이터 준비
  const dailyDates = dailyStats.map(stat => stat.report_at);
  const dailyUsers = dailyStats.map(stat => stat.total_users);

  // 월별 데이터 준비
  const monthlyLabels = monthlyStats.map(stat => {
    const date = new Date(stat.report_at);
    return `${date.getFullYear()}-${date.getMonth() + 1}`;
  });
  const monthlyUsers = monthlyStats.map(stat => stat.total_users);

  return (
    <Card className="rounded-[6px] bg-white">
      <CardHeader>
        <CardTitle>누적 가입자 현황</CardTitle>
      </CardHeader>
      <CardContent className="grid grid-cols-10 gap-4 px-0 pb-0">
        <div className="col-span-7">
          <h3 className="font-semibold mb-1 text-center text-sm">일별</h3>
          <div style={{ height: '300px' }}>
            <DynamicPlot
              data={[
                {
                  x: dailyDates,
                  y: dailyUsers,
                  type: 'line' as Data['type'],
                  name: '누적 가입자 수',
                  line: { color: 'rgba(75, 192, 192, 1)' },
                  fill: 'tozeroy',
                  fillcolor: 'rgba(75, 192, 192, 0.2)',
                },
              ]}
              layout={{
                ...chartLayout,
                xaxis: {
                  ...chartLayout.xaxis,
                  type: 'date',
                  tickformat: '%m/%d',
                }
              }}
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
                  y: monthlyUsers,
                  type: 'line' as Data['type'],
                  name: '월별 누적 가입자',
                  line: { color: 'rgba(153, 102, 255, 1)' }, 
                  fill: 'tozeroy',
                  fillcolor: 'rgba(153, 102, 255, 0.2)',
                },
              ]}
              layout={{
                ...chartLayout,
                xaxis: {
                  ...chartLayout.xaxis,
                  type: 'category',
                }
              }}
              style={{ width: '100%', height: '100%' }}
              config={chartConfig}
            />
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
