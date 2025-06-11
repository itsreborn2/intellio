/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  compiler: process.env.NODE_ENV === 'production' 
  ? {
      removeConsole: {
        exclude: ['error', 'warn', 'info'],
      },
    } 
  : undefined,
  images: {
    domains: ['lh3.googleusercontent.com'],
  },
  // 페이지 전환 시 스크롤 위치 보존 비활성화 - 항상 맨 위로 스크롤
  scrollRestoration: false,
}

module.exports = nextConfig
