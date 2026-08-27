import type { NextConfig } from 'next'

const nextConfig: NextConfig = {
  output: 'standalone',
  trailingSlash: false,
  poweredByHeader: false,
  images: { unoptimized: true },
  turbopack: { root: import.meta.dirname },
  experimental: {
    turbopackFileSystemCacheForDev: true,
    turbopackFileSystemCacheForBuild: false,
    useTypeScriptCli: true,
  },
  async headers() {
    return [
      {
        source: '/landing/contact/:path*',
        headers: [
          {
            key: 'Cache-Control',
            value: 'public, max-age=31536000, immutable',
          },
        ],
      },
    ]
  },
  async rewrites() {
    const origin =
      process.env.LINGXILEARN_API_ORIGIN ||
      (process.env.NODE_ENV === 'development' ? 'http://127.0.0.1:8000' : undefined)
    if (!origin) return []
    const base = origin.replace(/\/$/, '')
    return [
      { source: '/live', destination: `${base}/live` },
      { source: '/ready', destination: `${base}/ready` },
      { source: '/api/:path*', destination: `${base}/api/:path*` },
      { source: '/auth/:path*', destination: `${base}/auth/:path*` },
      { source: '/api/v1/:path*', destination: `${base}/api/v1/:path*` },
    ]
  },
}

export default nextConfig
