import './globals.css';
import Script from 'next/script';
import Sidebar from './components/Sidebar';
import ConditionalFooter from './components/ConditionalFooter';
import { Toaster } from 'react-hot-toast';
// ClientFooter 임포트 제거

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="ko"> 
      <head>
        <meta name="viewport" content="width=device-width, initial-scale=1.0" />
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
        <Toaster position="bottom-center" />
        
        {/* 사이드바는 fixed 포지션으로 설정되어 있으므로 여기서는 사이드바만 배치 */}
        <Sidebar />
        
        {/* 메인 콘텐츠는 데스크탑에서만 사이드바 너비만큼 왼쪽 여백을 가짐, 모바일에서는 전체 너비 사용 */}
        <main className="min-h-screen overflow-x-hidden w-full ml-0 md:ml-[59px] md:w-[calc(100%-59px)]">
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
