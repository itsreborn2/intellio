import type { Metadata } from "next"
import "./globals.css"

// 메타데이터 설정
export const metadata: Metadata = {
  title: "Intellio",
  description: "Intellio - Your AI Assistant",
}

// 레이아웃 컴포넌트
export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  )
}
