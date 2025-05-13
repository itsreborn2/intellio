import { AppProvider } from '@/contexts/AppContext'
import '@/styles/globals.css'
import ClientLayout from './ClientLayout'

// metadata 파일에서 가져오기
import { metadata } from './metadata'
export { metadata }

export default function RootLayout({
  children
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="ko">
      <head>
        <link rel="shortcut icon" href="/favicon.ico" />
        <link rel="icon" type="image/x-icon" href="/favicon.ico" />
        <link rel="apple-touch-icon" sizes="180x180" href="/apple-touch-icon.png" />
      </head>
      <body className="bg-background text-foreground">
        <AppProvider>
          <ClientLayout>
            {children}
          </ClientLayout>
        </AppProvider>
      </body>
    </html>
  )
}
