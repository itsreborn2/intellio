import './globals.css';
import Script from 'next/script';
import Sidebar from './components/Sidebar';
import ConditionalFooter from './components/ConditionalFooter';
import { Toaster } from 'sonner';
import Header from './components/Header'; // Header 컴포넌트 import 추가
import AppClientLayout from './components/AppClientLayout'; // 클라이언트 레이아웃 컴포넌트

import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "StockEasy - AI 기반 주식정보 솔루션",
  description: "스탁이지(StockEasy) AI 기반 주식정보 솔루션. 인텔리오(Intellio), 닥이지(DocEasy). 추세추종/RS순위/RS랭크/ETF섹터/밸류 솔루션 제공. 당일 주도주, 당일 주도섹터",
  icons: {
    icon: "/favicon.ico",
    apple: {
      url: "/apple-icon.png",
      sizes: "180x180",
    },
  },
  openGraph: {
    title: "StockEasy - AI 기반 주식정보 솔루션",
    description: "스탁이지(StockEasy) AI 기반 주식정보 솔루션. 인텔리오(Intellio), 닥이지(DocEasy). 추세추종/RS순위/RS랭크/ETF섹터/밸류 솔루션 제공. 당일 주도주, 당일 주도섹터",
    images: [
      {
        url: "https://stockeasy.intellio.kr/og_stockeasy.jpg",
      }
    ],
  }
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="ko"> 
      <head>
        <meta name="viewport" content="width=device-width, initial-scale=1.0" />
        <link rel="shortcut icon" href="/favicon.ico" />
        <link rel="icon" type="image/x-icon" href="/favicon.ico" />
        <link rel="apple-touch-icon" sizes="180x180" href="/apple-touch-icon.png" />
        <link href="//spoqa.github.io/spoqa-han-sans/css/SpoqaHanSansNeo.css" rel="stylesheet" type="text/css" />
        {/* 페이지 로드 시 스크롤 위치를 최상단으로 설정하는 인라인 스크립트 */}
        <script dangerouslySetInnerHTML={{
          __html: `
            window.onload = function() {
              window.scrollTo(0, 0);
            };
            if (document.readyState === 'complete') {
              window.scrollTo(0, 0);
            }
          `
        }} />
      </head>
      <body>
        <AppClientLayout>{children}</AppClientLayout>
        {/* 페이지 로드 후 스크롤 위치를 최상단으로 설정하는 스크립트 */}
        <Script id="reset-scroll" strategy="afterInteractive">
          {`
            window.scrollTo(0, 0);
            setTimeout(function() {
              window.scrollTo(0, 0);
            }, 100);
          `}
        </Script>
      </body>
    </html>
  );
}
