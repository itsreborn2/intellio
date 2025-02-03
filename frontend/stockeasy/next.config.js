/** @type {import('next').NextConfig} */
const nextConfig = {
  experimental: {
    externalDir: true,  // 외부 디렉토리의 컴포넌트 사용 허용
  },
  reactStrictMode: true,
  transpilePackages: ['common-ui'],  // common 디렉토리의 컴포넌트를 트랜스파일
}

module.exports = nextConfig
