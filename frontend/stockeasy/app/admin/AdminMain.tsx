'use client';

import React, { useState, useEffect } from 'react';
import { parseCookies } from 'nookies';
import dynamic from 'next/dynamic';
import type { Data } from 'plotly.js';
import { SummaryStatCards } from "./components/overview/SummaryStatCard";
import StatCard from "./components/overview/StatCard";
import ChartCard from './components/overview/ChartCard';

import UserTable from './components/user-info/UserTable';
import { TokenServiceCard } from "./components/token-status/TokenServiceCard";
import { TokenSummary } from "./components/token-status/TokenSummary";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
  CardFooter,
} from "intellio-common/components/ui/card";
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "intellio-common/components/ui/tabs";
const DynamicPlot = dynamic(() => import('react-plotly.js'), {
  ssr: false,
  loading: () => <p className="text-center text-muted-foreground">차트 로딩 중...</p>
});

// 목업 데이터 (추후 API 연동 시 대체)
const mockData = {
  totalUsers: 1234,
  monthlyActiveUsers: 876,
  dailyActiveUsers: 152,
  dailyCumulativeRegistrationsData: Array.from({ length: 30 }, (_, i) => {
    const date = new Date();
    date.setDate(date.getDate() - (29 - i));
    const baseCount = 500; 
    const dailyIncrease = Math.floor(Math.random() * 20) + 5; 
    return {
      date: date.toISOString().split('T')[0],
      count: baseCount + (i * dailyIncrease) + Math.floor(Math.random() * i * 5),
    };
  }),
  monthlyCumulativeRegistrationsData: Array.from({ length: 12 }, (_, i) => {
    const monthNames = ['1월', '2월', '3월', '4월', '5월', '6월', '7월', '8월', '9월', '10월', '11월', '12월'];
    const baseCount = 300;
    const monthlyIncrease = Math.floor(Math.random() * 150) + 50;
    return {
      month: monthNames[i],
      count: baseCount + (i * monthlyIncrease) + Math.floor(Math.random() * i * 30),
    };
  }),

  cumulativeRegistrationsData: Array.from({ length: 6 }, (_, i) => ({
    month: `${i + 1}월`,
    count: [120, 190, 310, 450, 620, 830][i],
  })),
  dailyAccessData: Array.from({ length: 30 }, (_, i) => {
    const date = new Date();
    date.setDate(date.getDate() - (29 - i));
    return {
      day: `${date.getMonth() + 1}/${date.getDate()}`,
      users: Math.floor(Math.random() * (200 - 80 + 1)) + 80,
    };
  }),
  monthlyAccessData: Array.from({ length: 12 }, (_, i) => ({
    month: `${i + 1}월`,
    users: Math.floor(Math.random() * (1000 - 300 + 1)) + 300,
  })),
  dailyRegistrationData: Array.from({ length: 30 }, (_, i) => {
    const date = new Date();
    date.setDate(date.getDate() - (29 - i));
    return {
      day: `${date.getMonth() + 1}/${date.getDate()}`,
      count: Math.floor(Math.random() * 30) + 5,
    };
  }),
  monthlyRegistrationData: Array.from({ length: 12 }, (_, i) => ({
    month: `${i + 1}월`,
    count: Math.floor(Math.random() * (500 - 150 + 1)) + 150,
  })),
  aiUsageRatioData: Array.from({ length: 55 }, (_, i) => {
    const date = new Date();
    date.setDate(date.getDate() - (54 - i));
    return {
      date: date.toISOString().split('T')[0],
      ratio: Math.random() * (1.2 - 0.5) + 0.5,
    };
  }),
  newChatSessionsData: Array.from({ length: 55 }, (_, i) => {
    const date = new Date();
    date.setDate(date.getDate() - (54 - i));
    return {
      date: date.toISOString().split('T')[0],
      sessions: Math.floor(Math.random() * (1100 - 100 + 1)) + 100,
    };
  }),
  dailyUserActivityData: Array.from({ length: 55 }, (_, i) => {
    const date = new Date();
    date.setDate(date.getDate() - (54 - i));
    const users = Math.floor(Math.random() * (1200 - 200 + 1)) + 200;
    const activeRatio = Math.random() * (0.25 - 0.05) + 0.05;
    return {
      date: date.toISOString().split('T')[0],
      users: users,
      activeRatio: activeRatio,
    };
  }),
  userRegistrations: [
    { id: 1, name: '홍길동', email: 'hong@example.com', signupDate: '2024-06-16 14:30' },
    { id: 2, name: '김철수', email: 'kim@example.com', signupDate: '2024-06-15 11:25' },
    { id: 3, name: '이영희', email: 'lee@example.com', signupDate: '2024-06-15 09:10' },
    { id: 4, name: '박지성', email: 'park@example.com', signupDate: '2024-06-14 18:45' },
    { id: 5, name: '김연아', email: 'kimyuna@example.com', signupDate: '2024-06-13 21:05' },
  ],
  userRankings: [
    { id: '1', userId: 'user_alpha_7', chatCount: 1250 },
    { id: '2', userId: 'user_beta_23', chatCount: 1100 },
    { id: '3', userId: 'user_gamma_11', chatCount: 980 },
    { id: '4', userId: 'user_delta_5', chatCount: 750 },
    { id: '5', userId: 'user_epsilon_9', chatCount: 600 },
  ],
  summary: {
    totalUsers: 1234,
    monthlyActiveUsers: 876,
    dailyActiveUsers: 152,
    dailyNewUsers: 12,
  }
};

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

export default function AdminMain() {
  
  const [isAuthorized, setIsAuthorized] = useState<boolean>(false);

  const getCurrentUserEmail = (): string | null => {
    if (typeof window !== 'undefined') { 
      const cookies = parseCookies();
      const userCookie = cookies.user;
      if (userCookie) {
        try {
          const parsedUser = JSON.parse(userCookie);
          if (parsedUser && parsedUser.email) {
            return parsedUser.email;
          }
          console.warn('Auth Check - User data in cookie does not contain an email.');
          return null;
        } catch (error) {
          console.error('Auth Check - Failed to parse user cookie:', error);
          return null;
        }
      }
      return null;
    }
    return null;
  };

  useEffect(() => {
    const adminIdsEnv = process.env.NEXT_PUBLIC_ADMIN_IDS;
    let parsedAdminIds: string[] = [];

    if (adminIdsEnv) {
      try {
        const tempParsed = JSON.parse(adminIdsEnv);
        if (Array.isArray(tempParsed) && tempParsed.every(id => typeof id === 'string')) {
          parsedAdminIds = tempParsed;
        } else {
          console.error('Auth Check - NEXT_PUBLIC_ADMIN_IDS is not a valid array of strings. It should be a JSON array of strings. Treating as empty.');
        }
      } catch (error) {
        console.error("Error parsing NEXT_PUBLIC_ADMIN_IDS from .env. It should be a JSON array of strings. Treating as empty.", error);
      }
    } else {
      console.warn('Auth Check - NEXT_PUBLIC_ADMIN_IDS environment variable is not set. Access will be denied unless email is in an empty list (which is impossible).');
    }

    const currentUserEmail = getCurrentUserEmail();
    const isUserAdmin = !!(currentUserEmail && parsedAdminIds.includes(currentUserEmail));
    
    setIsAuthorized(isUserAdmin);
  }, []);

  if (!isAuthorized) {
    return (
      <div className="flex flex-col justify-center items-center h-screen">
        <h1 className="text-2xl font-bold mb-4">접근 권한이 없습니다.</h1>
        <p className="text-lg">이 페이지는 관리자만 접근할 수 있습니다.</p>
      </div>
    );
  }

  const totalDailyUsage = tokenServices.reduce((acc, service) => acc + service.data.daily, 0);
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
  const summaryStats = [
    {
      id: "totalUsers",
      title: "총 가입자 수",
      value: mockData.summary.totalUsers.toLocaleString(),
      description: "+20.1% from last month",
    },
    {
      id: "dailyNewUsers",
      title: "일일 가입자 수",
      value: mockData.summary.dailyNewUsers.toLocaleString(),
      description: "+3.1% from yesterday",
    },
    {
      id: "monthlyActiveUsers",
      title: "월간 활성 사용자 (MAU)",
      value: mockData.summary.monthlyActiveUsers.toLocaleString(),
      description: "+15.2% from last month",
    },
    {
      id: "dailyActiveUsers",
      title: "일일 활성 사용자 (DAU)",
      value: mockData.summary.dailyActiveUsers.toLocaleString(),
      description: "+5.2% from yesterday",
    },
  ];

  return (
    <div className="flex-1 space-y-4 p-4 md:p-8 pt-6">
      <Tabs defaultValue="overview" className="space-y-4">
        <div className="flex items-center justify-between space-y-2">
          <h2 className="text-3xl font-bold tracking-tight text-oklch-0.372-0.044-257.287">Dashboard</h2>
        </div>
        <TabsList>
          <TabsTrigger value="overview">기본 현황</TabsTrigger>
          <TabsTrigger value="user-info">회원정보</TabsTrigger>
          <TabsTrigger value="token-status">토큰 현황</TabsTrigger>
        </TabsList>
        <TabsContent value="overview" className="space-y-4">
          <SummaryStatCards stats={summaryStats} />

          <div className="grid gap-4">
            <Card className="rounded-[6px] bg-white">
              <CardHeader>
                <CardTitle>누적 가입자 현황</CardTitle>
              </CardHeader>
              <CardContent className="grid grid-cols-10 gap-4">
                <div className="col-span-7">
                  <h3 className="font-semibold mb-2 text-center text-sm">일별</h3>
                  <div style={{ height: '280px' }}>
                    <DynamicPlot
                      data={[
                        {
                          x: mockData.dailyCumulativeRegistrationsData.map(d => d.date),
                          y: mockData.dailyCumulativeRegistrationsData.map(d => d.count),
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
                  <h3 className="font-semibold mb-2 text-center text-sm">월별</h3>
                  <div style={{ height: '280px' }}>
                    <DynamicPlot
                      data={[
                        {
                          x: mockData.monthlyCumulativeRegistrationsData.map(d => d.month),
                          y: mockData.monthlyCumulativeRegistrationsData.map(d => d.count),
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
          </div>

          <div className="grid gap-4">
            <Card className="rounded-[6px] bg-white">
              <CardHeader>
                <CardTitle>가입자 현황</CardTitle>
              </CardHeader>
              <CardContent className="grid grid-cols-10 gap-4">
                <div className="col-span-7">
                  <h3 className="font-semibold mb-2 text-center text-sm">최근 30일</h3>
                  <div style={{ height: '300px' }}>
                    <DynamicPlot
                      data={[
                        {
                          x: mockData.dailyRegistrationData.map(d => d.day),
                          y: mockData.dailyRegistrationData.map(d => d.count),
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
                  <h3 className="font-semibold mb-2 text-center text-sm">월별</h3>
                  <div style={{ height: '300px' }}>
                    <DynamicPlot
                      data={[
                        {
                          x: mockData.monthlyRegistrationData.map(d => d.month),
                          y: mockData.monthlyRegistrationData.map(d => d.count),
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
          </div>

          <div className="grid gap-4">
            <Card className="rounded-[6px] bg-white">
              <CardHeader>
                <CardTitle>접속 현황</CardTitle>
              </CardHeader>
              <CardContent className="grid grid-cols-10 gap-4">
                <div className="col-span-7">
                  <h3 className="font-semibold mb-2 text-center text-sm">최근 30일</h3>
                  <div style={{ height: '300px' }}>
                    <DynamicPlot
                      data={[
                        {
                          x: mockData.dailyAccessData.map(d => d.day),
                          y: mockData.dailyAccessData.map(d => d.users),
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
                  <h3 className="font-semibold mb-2 text-center text-sm">월별</h3>
                  <div style={{ height: '300px' }}>
                    <DynamicPlot
                      data={[
                        {
                          x: mockData.monthlyAccessData.map(d => d.month),
                          y: mockData.monthlyAccessData.map(d => d.users),
                          type: 'bar' as const,
                          marker: { color: 'oklch(0.6 0.17 150)', cornerradius: 6 } as any,
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
          </div>

          <div className="grid gap-4">
            <Card className="rounded-[6px] bg-white">
              <CardHeader>
                <CardTitle>채팅 현황</CardTitle>
              </CardHeader>
              <CardContent className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                <div>
                  <h3 className="font-semibold mb-2 text-center text-sm">AI 어시스턴트 이용 비율</h3>
                  <div style={{ height: '300px' }}>
                    <DynamicPlot
                      data={[
                        {
                          x: mockData.aiUsageRatioData.map(d => d.date),
                          y: mockData.aiUsageRatioData.map(d => d.ratio),
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
                  <h3 className="font-semibold mb-2 text-center text-sm">신규 채팅 세션</h3>
                  <div style={{ height: '300px' }}>
                    <DynamicPlot
                      data={[
                        {
                          x: mockData.newChatSessionsData.map(d => d.date),
                          y: mockData.newChatSessionsData.map(d => d.sessions),
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
          </div>

          <div className="grid gap-4">
            <Card className="rounded-[6px] bg-white">
              <CardHeader>
                <CardTitle>일일 사용자 활동</CardTitle>
              </CardHeader>
              <CardContent>
                <div style={{ height: '350px' }}>
                  <DynamicPlot
                    data={[
                      {
                        x: mockData.dailyUserActivityData.map(d => d.date),
                        y: mockData.dailyUserActivityData.map(d => d.users),
                        type: 'bar' as const,
                        name: '오늘 사용자(좌)',
                        marker: { color: 'rgb(66, 133, 244)', cornerradius: 6 } as any,
                        yaxis: 'y1',
                      },
                      {
                        x: mockData.dailyUserActivityData.map(d => d.date),
                        y: mockData.dailyUserActivityData.map(d => d.activeRatio),
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
                        color: chartLayout.font.color,
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
          </div>
        </TabsContent>
      <TabsContent value="user-info" className="space-y-4">
        <div className="grid grid-cols-1 gap-4">
          <div className="lg:col-span-12">
            <Card className="rounded-[6px] shadow-sm bg-white">
              <CardHeader>
                <CardTitle>전체 회원 검색</CardTitle>
              </CardHeader>
              <CardContent>
                <UserTable />
              </CardContent>
            </Card>
          </div>
        </div>
      </TabsContent>
      <TabsContent value="token-status" className="space-y-4">
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
      </TabsContent>
    </Tabs>
  </div>
  );
}
