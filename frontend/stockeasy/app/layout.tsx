import './globals.css';

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
      </head>
      <body>
        <div className="flex flex-col min-h-screen">
          <div className="flex-grow">
            {children}
          </div>
        </div>
      </body>
    </html>
  );
}
