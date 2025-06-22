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
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: 'http://localhost:8000/api/:path*',
      },
    ];
  },
}

const path = require('path');

nextConfig.webpack = (config) => {
  config.resolve.alias['intellio-common'] = path.join(__dirname, '../common');
  return config;
};

module.exports = nextConfig;
