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

interface ChatUsageChartProps {
  DynamicPlot: React.ComponentType<PlotProps>;
  chartLayout: Partial<Layout>;
  chartConfig: Partial<Config>;
  dailyStats: UserStat[];
}

/**
 * 채팅 현황을 보여주는 차트 컴포넌트
 * AI 어시스턴트 이용 비율과 신규 채팅 세션 정보를 표시
 */
export default function ChatUsageChart({ 
  DynamicPlot, 
  chartLayout, 
  chartConfig,
  dailyStats 
}: ChatUsageChartProps) {
  // 데이터 준비
  const dates = dailyStats.map(stat => stat.report_at);
  
  // 사용자 당 세션 수 계산
  const sessionsPerUser = dailyStats.map(stat => stat.sessions_per_user || 0);
  
  // 신규 채팅 세션
  const newChatSessions = dailyStats.map(stat => stat.new_chat_sessions);

  return (
    <Card className="rounded-[6px] bg-white">
      <CardHeader>
        <CardTitle>채팅 현황</CardTitle>
      </CardHeader>
      <CardContent className="grid grid-cols-1 lg:grid-cols-2 gap-4 px-0 pb-0">
        <div>
          <h3 className="font-semibold mb-1 text-center text-sm">AI 어시스턴트 이용 비율</h3>
          <div style={{ height: '300px' }}>
            <DynamicPlot
              data={[
                {
                  x: dates,
                  y: sessionsPerUser,
                  type: 'bar' as const,
                  marker: { color: 'rgb(66, 133, 244)', cornerradius: 6 } as any,
                },
              ]}
              layout={{ ...chartLayout, xaxis: { ...chartLayout.xaxis, type: 'date' }, yaxis: { ...chartLayout.yaxis, tickformat: '.2f' } }}
              style={{ width: '100%', height: '100%' }}
              config={chartConfig}
            />
          </div>
        </div>
        <div>
          <h3 className="font-semibold mb-1 text-center text-sm">신규 채팅 세션</h3>
          <div style={{ height: '300px' }}>
            <DynamicPlot
              data={[
                {
                  x: dates,
                  y: newChatSessions,
                  type: 'bar' as const,
                  marker: { color: 'rgb(255, 183, 77)', cornerradius: 6 } as any,
                },
              ]}
              layout={{ ...chartLayout, xaxis: { ...chartLayout.xaxis, type: 'date' } }}
              style={{ width: '100%', height: '100%' }}
              config={chartConfig}
            />
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
