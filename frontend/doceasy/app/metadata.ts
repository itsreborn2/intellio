import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "닥이지",
  description: "AI 기반 문서관리 솔루션",
  icons: {
    icon: "/favicon.ico",
    apple: {
      url: "/apple-icon.png",
      sizes: "180x180",
    },
  },
  openGraph: {
    title: "닥이지",
    description: "AI 기반 문서관리 솔루션",
    images: [
      {
        url: "https://doceasy.intellio.kr/og_doceasy.jpg",
        width: 1200,
        height: 630,
        alt: "닥이지 - AI 기반 문서관리 솔루션",
      }
    ],
  }
};
