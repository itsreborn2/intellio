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
}

module.exports = nextConfig
