// frontend/stockeasy/app/admin/crm/components/TokenServiceCard.tsx
'use client';

import React from 'react';
import type { Data, Layout, Config } from 'plotly.js';
import { Card, CardContent, CardHeader, CardTitle } from "intellio-common/components/ui/card";

// 공통 차트 레이아웃 및 설정을 page.tsx에서 가져오거나 여기서 다시 정의해야 합니다.
// 우선 간단하게 props로 받는다고 가정하고, 나중에 page.tsx에서 전달하도록 수정합니다.
// 또는 page.tsx에서 chartLayout과 chartConfig를 export하여 여기서 import 할 수도 있습니다.

interface TokenServiceData {
  daily: number;
  monthly: number;
  dailyChange: number;
  monthlyChange: number;
  dailyChartData: Array<{ day: string; value: number }>;
  monthlyChartData: Array<{ month: string; value: number }>;
}

interface TokenService {
  id: string;
  name: string;
  data: TokenServiceData;
  color: string; // 서비스별 색상
}

interface PlotProps {
  data?: Data[];
  layout?: Partial<Layout>;
  config?: Partial<Config>;
  style?: React.CSSProperties;
}

interface TokenServiceCardProps {
  service: TokenService;
  DynamicPlot: React.ComponentType<PlotProps>;
  chartLayout: Partial<Layout>;
  chartConfig: Partial<Config>;
}

export function TokenServiceCard({ service, DynamicPlot, chartLayout, chartConfig }: TokenServiceCardProps) {
  return (
    <Card key={service.id} className="rounded-[6px] shadow-sm">
      <CardHeader className="pb-2 pt-4">
        <CardTitle className="text-lg font-medium">{service.name}</CardTitle>
      </CardHeader>
      <CardContent className="pb-4">
        <div className="grid grid-cols-1 lg:grid-cols-10 gap-4">
          {/* Daily Section (7 parts) */}
          <div className="lg:col-span-7 space-y-4">
            {/* Daily Stats */}
            <div>
              <p className="text-xs text-muted-foreground uppercase tracking-wider">일간 사용량</p>
              <p className="text-2xl font-semibold">{service.data.daily.toLocaleString()}</p>
              <p className={`text-xs ${service.data.dailyChange >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                {service.data.dailyChange >= 0 ? '+' : ''}{service.data.dailyChange.toFixed(1)}% from yesterday
              </p>
            </div>
            {/* Daily Chart */}
            <div>
              <h4 className="text-sm font-medium mb-2 text-center text-muted-foreground">일간 사용량 추이</h4>
              <div style={{ height: '200px' }}>
                <DynamicPlot
                  data={[
                    {
                      x: service.data.dailyChartData.map(d => d.day),
                      y: service.data.dailyChartData.map(d => d.value),
                      type: 'bar' as const,
                      marker: { color: service.color, cornerradius: 6 } as any,
                    },
                  ]}
                  layout={{ ...chartLayout, yaxis: { ...chartLayout.yaxis, autorange: true }, xaxis: { ...chartLayout.xaxis, type: 'category', tickfont: {size: 8} } }}
                  style={{ width: '100%', height: '100%' }}
                  config={chartConfig}
                />
              </div>
            </div>
          </div>

          {/* Monthly Section (3 parts) */}
          <div className="lg:col-span-3 space-y-4">
            {/* Monthly Stats */}
            <div>
              <p className="text-xs text-muted-foreground uppercase tracking-wider">월간 사용량</p>
              <p className="text-2xl font-semibold">{service.data.monthly.toLocaleString()}</p>
              <p className={`text-xs ${service.data.monthlyChange >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                {service.data.monthlyChange >= 0 ? '+' : ''}{service.data.monthlyChange.toFixed(1)}% from last month
              </p>
            </div>
            {/* Monthly Chart */}
            <div>
              <h4 className="text-sm font-medium mb-2 text-center text-muted-foreground">월간 사용량 추이</h4>
              <div style={{ height: '200px' }}>
                <DynamicPlot
                  data={[
                    {
                      x: service.data.monthlyChartData.map(d => d.month),
                      y: service.data.monthlyChartData.map(d => d.value),
                      type: 'bar' as const,
                      marker: { color: service.color, cornerradius: 6 } as any,
                    },
                  ]}
                  layout={{ ...chartLayout, yaxis: { ...chartLayout.yaxis, autorange: true }, xaxis: { ...chartLayout.xaxis, type: 'category', tickfont: {size: 8} } }}
                  style={{ width: '100%', height: '100%' }}
                  config={chartConfig}
                />
              </div>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
