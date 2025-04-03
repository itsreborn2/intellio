/** @type {import('next').NextConfig} */
import path from 'path';
import { fileURLToPath } from 'url';
import dotenv from 'dotenv';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

// .env 파일 로드
dotenv.config({
  path: path.resolve(__dirname, '../.env')
});

const nextConfig = {
  transpilePackages: ['intellio-common'], // common 폴더의 컴포넌트들을 트랜스파일하도록 설정

  compiler: process.env.NODE_ENV === 'production' 
  ? {
      removeConsole: {
        exclude: ['error', 'warn', 'info'],
      },
    } 
  : undefined,

  // React의 Strict Mode 활성화 - 개발 시 잠재적인 문제를 감지하고 더 나은 개발 경험을 제공
  reactStrictMode: true,

  // 도메인 설정
  env: {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL || 'https://intellio.kr/api',
    NEXT_PUBLIC_BASE_URL: process.env.NEXT_PUBLIC_BASE_URL || 'https://intellio.kr',
  },

  // CORS 및 도메인 설정
  async headers() {
    return [
      {
        source: '/:path*',
        headers: [
          { key: 'Access-Control-Allow-Origin', value: 'https://intellio.kr' },
          { key: 'Access-Control-Allow-Methods', value: 'GET,POST,PUT,DELETE,OPTIONS' },
          { key: 'Access-Control-Allow-Headers', value: 'Content-Type, Authorization' },
        ],
      },
    ];
  },

  poweredByHeader: false,
  compress: true,

  experimental: {
    externalDir: true,  // 외부 디렉토리의 컴포넌트 사용 허용
    optimizeCss: true,
    // 메모리 사용량을 줄이기 위한 설정
    workerThreads: false,
    cpus: 1
  },
  
  webpack: (config, { dev, isServer }) => {
    // webpack 경고 메시지 숨기기
    config.infrastructureLogging = {
      level: 'error',
    };
    
    // 불필요한 SWC 바이너리 경고 제거
    config.snapshot = {
      ...config.snapshot,
      managedPaths: [/^(.+?[\\/]node_modules[\\/](?!@next[\\/]))/],
    };

    // 프로덕션 빌드 최적화
    if (!dev && !isServer) {
      Object.assign(config.optimization.splitChunks.cacheGroups, {
        commons: {
          name: 'commons',
          chunks: 'all',
          minChunks: 2,
          reuseExistingChunk: true,
        },
      });
    }
    return config;
  },
};

export default nextConfig;
