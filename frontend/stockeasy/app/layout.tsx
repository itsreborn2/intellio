import './globals.css';
import Script from 'next/script';
import Sidebar from './components/Sidebar';

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
        <div className="flex flex-col min-h-screen">
          <div className="flex-grow flex">
            {/* 사이드바를 모든 페이지의 공통 레이아웃으로 이동 */}
            <Sidebar />
            {/* 메인 콘텐츠 영역을 정의하고 스타일 적용 */}
            <main className="flex-1 overflow-y-auto"> {/* flex-1로 남은 공간 차지, overflow-y-auto로 내부 스크롤 */}
              {children}
            </main>
          </div>
        </div>
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
