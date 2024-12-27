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
