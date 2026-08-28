import type { NextConfig } from 'next'

function apiOrigin(): string {
  const value = process.env.LINGXILEARN_API_ORIGIN?.trim()
  if (!value && process.env.NODE_ENV !== 'development') {
    throw new Error('LINGXILEARN_API_ORIGIN is required outside development')
  }
  return (value || 'http://127.0.0.1:8000').replace(/\/$/, '')
}

const nextConfig: NextConfig = {
  output: 'standalone',
  poweredByHeader: false,
  images: { unoptimized: true },
  async rewrites() {
    const origin = apiOrigin()
    return [
      { source: '/live', destination: `${origin}/live` },
      { source: '/ready', destination: `${origin}/ready` },
      { source: '/api/:path*', destination: `${origin}/api/:path*` },
      { source: '/auth/:path*', destination: `${origin}/auth/:path*` },
    ]
  },
}

export default nextConfig
