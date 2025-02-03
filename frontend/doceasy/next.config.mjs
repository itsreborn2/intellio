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

  // React의 Strict Mode 활성화 - 개발 시 잠재적인 문제를 감지하고 더 나은 개발 경험을 제공
  reactStrictMode: true,

  experimental: {
    externalDir: true,  // 외부 디렉토리의 컴포넌트 사용 허용
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
