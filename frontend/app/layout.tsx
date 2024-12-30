"use client"

import { Header } from '@/components/common/Header'
import { Sidebar } from '@/components/common/Sidebar'
import { AppProvider } from '@/contexts/AppContext'
import '@/styles/globals.css'

export const metadata = {
  title: 'DocEasy',
  description: '문서 분석 및 추출 서비스',
}

export default function RootLayout({
  children
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <head>
        <title>DocEasy</title>
      </head>
      <body className="bg-background text-foreground">
        <AppProvider>
          <div className="flex h-screen overflow-hidden bg-background">
            {/* 사이드바 */}
            <Sidebar className="fixed left-0 top-0 h-full z-50" />
            
            {/* 메인 컨테이너 */}
            <div className="flex-1 ml-[250px]">
              {/* 헤더 */}
              <Header className="fixed top-0 right-0 left-[250px] h-[56px] z-40 bg-background border-b" />
              
              {/* 메인 콘텐츠 영역 */}
              <main className="fixed top-[56px] right-0 left-[250px] bottom-0 overflow-hidden">
                {children}
              </main>
            </div>
          </div>
        </AppProvider>
      </body>
    </html>
  )
}
