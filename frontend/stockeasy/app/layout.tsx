import './globals.css';
import Script from 'next/script';
import Sidebar from './components/Sidebar';
import ConditionalFooter from './components/ConditionalFooter';
import { Toaster } from 'sonner';
import Header from './components/Header'; // Header 컴포넌트 import 추가

import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "StockEasy - AI 기반 주식정보 솔루션",
  description: "스탁이지(StockEasy) AI 기반 주식정보 솔루션. 인텔리오(Intellio), 닥이지(DocEasy)",
  icons: {
    icon: "/favicon.ico",
    apple: {
      url: "/apple-icon.png",
      sizes: "180x180",
    },
  },
  openGraph: {
    title: "StockEasy - AI 기반 주식정보 솔루션",
    description: "스탁이지(StockEasy) AI 기반 주식정보 솔루션. 인텔리오(Intellio), 닥이지(DocEasy)",
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
        {/* 토스트 알림 컴포넌트 */}
        <Toaster position="bottom-center" richColors closeButton />
        
        {/* 사이드바는 fixed 포지션으로 설정되어 있으므로 여기서는 사이드바만 배치 */}
        <Sidebar />
        {/* 헤더는 fixed 포지션으로 설정 */}
        <Header /> 
        
        {/* 메인 콘텐츠는 fixed 포지션으로 변경하고, 헤더 높이만큼 상단 여백 적용 */}
        {/* overflow-auto를 추가하여 메인 콘텐츠 내부에서 스크롤 발생 */}
        <main className="fixed top-[44px] bottom-0 right-0 left-0 md:left-[59px] overflow-auto">
          <div className="content-container">
            {children}
          </div>
          <ConditionalFooter />
        </main>
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
