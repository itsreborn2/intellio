/** @type {import('next').NextConfig} */
const nextConfig = {
  async rewrites() {
    return [
      {
        source: '/api/v1/:path*',
        destination: 'http://localhost:8000/api/v1/:path*',
      },
    ];
  },
  // React의 Strict Mode 활성화 - 개발 시 잠재적인 문제를 감지하고 더 나은 개발 경험을 제공
  reactStrictMode: true,
  webpack: (config, { isServer }) => {
    // webpack 경고 메시지 숨기기
    config.infrastructureLogging = {
      level: 'error',
    };
    
    // 불필요한 SWC 바이너리 경고 제거
    config.snapshot = {
      ...config.snapshot,
      managedPaths: [/^(.+?[\\/]node_modules[\\/](?!@next[\\/]))/],
    };

    return config;
  },
};

export default nextConfig;
