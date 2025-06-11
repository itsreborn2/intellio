import "./globals.css"
import { Inter } from "next/font/google"
import type React from "react"
import type { Metadata } from "next"
import MouseMoveEffect from "@/components/ui/mouse-move-effect"
import Navbar from "@/components/navbar"

const inter = Inter({ subsets: ["latin"] })

export const metadata: Metadata = {
  title: "스탁이지 - 인텔리오",
  description: "주식 전용 AI 어시스턴트 스탁이지, 당신의 투자 리서치 시간을 줄여줍니다.",
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en" className="dark h-full">
      <body className={`${inter.className} bg-background text-foreground antialiased h-full flex flex-col min-h-screen`}>
        <MouseMoveEffect />
        <Navbar />
        <main className="flex-1">
          {children}
        </main>
      </body>
    </html>
  )
}

