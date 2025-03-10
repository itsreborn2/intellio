import './globals.css';
import Script from 'next/script';

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
          <div className="flex-grow">
            {children}
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
