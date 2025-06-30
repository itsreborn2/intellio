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

interface DailyUserActivityChartProps {
  DynamicPlot: React.ComponentType<PlotProps>;
  chartLayout: Partial<Layout>;
  chartConfig: Partial<Config>;
  dailyStats: UserStat[];
}

/**
 * 일일 사용자 활동을 보여주는 차트 컴포넌트
 * 오늘 사용자와 활성 사용자 비율을 복합 차트로 표시
 */
export default function DailyUserActivityChart({ 
  DynamicPlot, 
  chartLayout, 
  chartConfig,
  dailyStats 
}: DailyUserActivityChartProps) {
  // 데이터 준비
  const dates = dailyStats.map(stat => stat.report_at);
  const activeUsers = dailyStats.map(stat => stat.active_users);
  
  // 활성 사용자 비율 계산 (total_users가 0인 경우 방지)
  const activeUserPercentage = dailyStats.map(stat => {
    if (stat.total_users === 0) return 0;
    const percentage = (stat.active_user_percentage || 0);
    return percentage; // 이미 백분율이므로 그대로 사용
  });

  return (
    <Card className="rounded-[6px] bg-white">
      <CardHeader>
        <CardTitle>일일 사용자 활동</CardTitle>
      </CardHeader>
      <CardContent className="px-0 pb-0">
        <div style={{ height: '350px' }}>
          <DynamicPlot
            data={[
              {
                x: dates,
                y: activeUsers,
                type: 'bar' as const,
                name: '오늘 사용자(좌)',
                marker: { color: 'rgb(66, 133, 244)', cornerradius: 6 } as any,
                yaxis: 'y1',
              },
              {
                x: dates,
                y: activeUserPercentage,
                type: 'bar' as const,
                name: '활성 사용자 비율(우)',
                marker: { color: 'rgb(244, 117, 106)', cornerradius: 6 } as any,
                yaxis: 'y2',
              },
            ]}
            layout={{
              ...chartLayout,
              xaxis: {
                ...chartLayout.xaxis,
                type: 'date',
              },
              yaxis: {
                ...chartLayout.yaxis,
                title: '오늘 사용자 수',
              },
              yaxis2: {
                title: '활성 사용자 비율',
                overlaying: 'y',
                side: 'right',
                tickformat: '.0%',
                showgrid: false,
                zeroline: false,
                rangemode: 'tozero',
                color: chartLayout.font?.color,
              },
              barmode: 'group',
              legend: {
                x: 0.5,
                xanchor: 'center',
                y: 1.15, 
                yanchor: 'bottom',
                orientation: 'h',
                bgcolor: 'rgba(255,255,255,0.5)',
                bordercolor: 'rgba(0,0,0,0.1)',
                borderwidth: 1
              },
              bargap: 0.15,
              bargroupgap: 0.1
            }}
            style={{ width: '100%', height: '100%' }}
            config={chartConfig}
          />
        </div>
      </CardContent>
    </Card>
  );
}
