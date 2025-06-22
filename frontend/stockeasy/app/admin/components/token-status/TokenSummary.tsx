import React from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardFooter } from 'intellio-common/components/ui/card';
import type { Data, Layout, Config } from 'plotly.js';

// page.tsx로부터 전달받을 props 타입을 정의합니다.
interface ServiceData {
  daily: number;
  monthly: number;
}

interface TokenService {
  id: string;
  name: string;
  data: ServiceData;
  color: string;
}

interface PlotProps {
  data?: Data[];
  layout?: Partial<Layout>;
  config?: Partial<Config>;
  style?: React.CSSProperties;
}

interface TokenSummaryProps {
  tokenServices: TokenService[];
  DynamicPlot: React.ComponentType<PlotProps>;
  donutChartLayout: Partial<Layout>;
  chartConfig: Partial<Config>;
}

export function TokenSummary({ tokenServices, DynamicPlot, donutChartLayout, chartConfig }: TokenSummaryProps) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-6 gap-4">
      {tokenServices.map((service) => (
        <Card key={`${service.id}-summary`} className="rounded-[6px] shadow-sm">
          <CardHeader className="p-4 flex flex-row items-center justify-between space-y-0">
            <CardTitle className="text-sm font-medium">{service.name}</CardTitle>
          </CardHeader>
          <CardContent className="p-4 pt-0">
            <div className="text-xs text-muted-foreground">일간: <span className="font-semibold text-foreground">{service.data.daily.toLocaleString()}</span></div>
            <div className="text-xs text-muted-foreground">월간: <span className="font-semibold text-foreground">{service.data.monthly.toLocaleString()}</span></div>
          </CardContent>
        </Card>
      ))}
      <Card className="rounded-[6px] shadow-sm lg:col-span-2">
        <CardHeader className="p-4 pb-0">
          <CardTitle className="text-sm font-medium">월간 총 사용량 분포</CardTitle>
        </CardHeader>
        <CardContent className="p-0 flex items-center justify-center" style={{ height: '150px' }}>
          <DynamicPlot
            data={[
              {
                values: tokenServices.map(s => s.data.monthly),
                labels: tokenServices.map(s => s.name),
                type: 'pie',
                hole: 0.75,
                marker: {
                  colors: tokenServices.map(s => s.color),
                },
                hoverinfo: 'label+percent',
                textinfo: 'none',
              },
            ]}
            layout={donutChartLayout}
            style={{ width: '150px', height: '150px' }}
            config={chartConfig}
          />
        </CardContent>
        <CardFooter className="p-4 pt-2 flex flex-col items-start text-xs space-y-1">
          {tokenServices.map(service => (
            <div key={`${service.id}-legend`} className="flex items-center w-full">
              <span className="w-2 h-2 rounded-full mr-2" style={{ backgroundColor: service.color }} />
              <span className="text-muted-foreground">{service.name}</span>
              <span className="ml-auto font-medium">{(service.data.monthly / 1000000).toFixed(2)}M</span>
            </div>
          ))}
        </CardFooter>
      </Card>
    </div>
  );
}
