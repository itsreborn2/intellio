'use client';

import React from 'react';
import type { Data } from 'plotly.js';
import { TokenServiceCard } from "./TokenServiceCard";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardFooter,
} from "intellio-common/components/ui/card";
import dynamic from 'next/dynamic';

const DynamicPlot = dynamic(() => import('react-plotly.js'), {
  ssr: false,
  loading: () => <p className="text-center text-muted-foreground">차트 로딩 중...</p>
});

// Data and layout configurations specific to the Token Status tab
const mockTokenUsageData = {
  gemini: {
    daily: 12345, monthly: 345678, dailyChange: 5.2, monthlyChange: -1.5,
    dailyChartData: Array.from({ length: 30 }, (_, i) => ({ day: `Day ${i + 1}`, value: Math.floor(Math.random() * 200) + 50 })),
    monthlyChartData: Array.from({ length: 12 }, (_, i) => ({ month: `${i + 1}월`, value: Math.floor(Math.random() * 500000) + 100000 })),
  },
  tavily: {
    daily: 8765, monthly: 210987, dailyChange: -2.1, monthlyChange: 3.0,
    dailyChartData: Array.from({ length: 30 }, (_, i) => ({ day: `Day ${i + 1}`, value: Math.floor(Math.random() * 150) + 30 })),
    monthlyChartData: Array.from({ length: 12 }, (_, i) => ({ month: `${i + 1}월`, value: Math.floor(Math.random() * 300000) + 50000 })),
  },
  pinecone: {
    daily: 56789, monthly: 1234567, dailyChange: 10.0, monthlyChange: 8.5,
    dailyChartData: Array.from({ length: 30 }, (_, i) => ({ day: `Day ${i + 1}`, value: Math.floor(Math.random() * 700) + 200 })),
    monthlyChartData: Array.from({ length: 12 }, (_, i) => ({ month: `${i + 1}월`, value: Math.floor(Math.random() * 2000000) + 500000 })),
  },
  gcs: {
    daily: 234, monthly: 5678, dailyChange: 0.5, monthlyChange: -0.2,
    dailyChartData: Array.from({ length: 30 }, (_, i) => ({ day: `Day ${i + 1}`, value: Math.floor(Math.random() * 30) + 10 })),
    monthlyChartData: Array.from({ length: 12 }, (_, i) => ({ month: `${i + 1}월`, value: Math.floor(Math.random() * 7000) + 1000 })),
  },
};

const tokenServices = [
  { id: 'gemini', name: 'Gemini', data: mockTokenUsageData.gemini, color: 'oklch(0.63 0.15 258)' },
  { id: 'tavily', name: 'Tavily', data: mockTokenUsageData.tavily, color: 'oklch(0.7 0.15 165)' },
  { id: 'pinecone', name: 'Pinecone', data: mockTokenUsageData.pinecone, color: 'oklch(0.71 0.16 60)' },
  { id: 'gcs', name: 'Google Cloud Storage', data: mockTokenUsageData.gcs, color: 'oklch(0.67 0.16 145)' },
];

const chartLayout = {
  autosize: true,
  margin: { l: 40, r: 50, t: 20, b: 30 },
  paper_bgcolor: 'transparent',
  plot_bgcolor: 'transparent',
  font: {
    color: 'oklch(0.372 0.044 257.287)',
  },
  yaxis: {
    gridcolor: 'rgba(128, 128, 128, 0.1)',
    zerolinecolor: 'rgba(128, 128, 128, 0.1)',
  },
  xaxis: {
    tickangle: 45,
    automargin: true,
    tickfont: { 
      size: 10
    },
    tickformat: '%-m/%-d'
  }
};

const chartConfig = {
  responsive: true,
  displayModeBar: false
};

export default function TokenStatusTab() {
  const totalMonthlyUsage = tokenServices.reduce((acc, service) => acc + service.data.monthly, 0);

  const donutChartLayout = {
    annotations: [
      {
        font: { size: 18, weight: 700 },
        showarrow: false,
        text: `${(totalMonthlyUsage / 1000000).toFixed(1)}M`,
        x: 0.5,
        y: 0.55,
      },
      {
        font: { size: 11, color: 'hsl(var(--muted-foreground))' },
        showarrow: false,
        text: 'Total Monthly',
        x: 0.5,
        y: 0.4,
      },
    ],
    showlegend: false,
    margin: { t: 5, b: 5, l: 5, r: 5 },
    paper_bgcolor: 'transparent',
    plot_bgcolor: 'transparent',
    height: 150,
    width: 150,
  } as any;

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-6 gap-4">
        {tokenServices.map((service) => (
          <Card key={`${service.id}-summary`} className="rounded-[6px] shadow-sm bg-white">
            <CardHeader className="p-4 flex flex-row items-center justify-between space-y-0">
              <CardTitle className="text-sm font-medium">{service.name}</CardTitle>
            </CardHeader>
            <CardContent className="p-4 pt-0">
              <div className="text-xs text-muted-foreground">일간: <span className="font-semibold text-foreground">{service.data.daily.toLocaleString()}</span></div>
              <div className="text-xs text-muted-foreground">월간: <span className="font-semibold text-foreground">{service.data.monthly.toLocaleString()}</span></div>
            </CardContent>
          </Card>
        ))}
        <Card className="rounded-[6px] shadow-sm lg:col-span-2 bg-white">
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

      <Card className="rounded-[6px] bg-white">
        <CardHeader>
          <CardTitle className="text-xl">서비스별 토큰/API 사용 현황</CardTitle>
        </CardHeader>
        <CardContent className="pt-4">
          <div className="grid grid-cols-1 gap-4">
            {tokenServices.map((service) => (
              <TokenServiceCard
                key={service.id}
                service={service}
                DynamicPlot={DynamicPlot}
                chartLayout={chartLayout}
                chartConfig={chartConfig}
              />
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
