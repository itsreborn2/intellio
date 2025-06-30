'use client';

import React, { useState, useEffect } from 'react';
import { parseCookies } from 'nookies';
import dynamic from 'next/dynamic';
import type { Layout, Config } from 'plotly.js';

import UserInfoTab from './components/user-info/UserInfoTab';
import TokenStatusTab from './components/token-status/TokenStatusTab';
import OverviewTab from './components/overview/OverviewTab';

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

const chartLayout: Partial<Layout> = {
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

const chartConfig: Partial<Config> = {
  responsive: true,
  displayModeBar: false
};

export default function AdminPage() {
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
          <OverviewTab 
            DynamicPlot={DynamicPlot}
            chartLayout={chartLayout}
            chartConfig={chartConfig}
          />
        </TabsContent>
        <TabsContent value="user-info">
          <UserInfoTab />
        </TabsContent>
        <TabsContent value="token-status" className="space-y-4">
          <TokenStatusTab />
        </TabsContent>
      </Tabs>
    </div>
  );
}
