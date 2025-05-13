import "./globals.css"
import { Inter } from "next/font/google"
import type React from "react"
import MouseMoveEffect from "@/components/ui/mouse-move-effect"

const inter = Inter({ subsets: ["latin"] })

import type { Metadata } from "next"
export const metadata: Metadata = {
  title: "Intellio - AI",
  description: "인텔리오(Intellio) AI 기반 문서관리, 주식정보 솔루션. 닥이지(DocEasy), 스탁이지(StockEasy)",
  icons: [
    { rel: "icon", url: "/favicon.ico", sizes: "any" },
    { rel: "apple-touch-icon", url: "/apple-touch-icon.png" }
  ],
  openGraph: {
    title: "Intellio - AI",
    description: "인텔리오(Intellio) AI 기반 문서관리, 주식정보 솔루션. 닥이지(DocEasy), 스탁이지(StockEasy)",
    images: [
      {
        url: "https://intellio.kr/og-image.jpg",
      }
    ],
  }
}


export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en" className="dark">
      <head>
        <link rel="icon" href="/favicon.ico" sizes="any" />
        <link rel="icon" type="image/png" sizes="32x32" href="/favicon-32x32.png" />
        <link rel="icon" type="image/png" sizes="16x16" href="/favicon-16x16.png" />
        <link rel="apple-touch-icon" sizes="180x180" href="/apple-icon.png" />
        <link rel="manifest" href="/site.webmanifest" />
      </head>
      <body className={`${inter.className} bg-background text-foreground antialiased`}>
        <MouseMoveEffect />
        {children}
      </body>
    </html>
  )
}

