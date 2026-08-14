import type { NextConfig } from 'next'

const nextConfig: NextConfig = {
  output: 'standalone',
  trailingSlash: false,
  poweredByHeader: false,
  images: { unoptimized: true },
  turbopack: { root: import.meta.dirname },
  // The imported upstream graph includes server-only Sim modules which are
  // intentionally inert in Lingxi. The dedicated frontend tsconfig performs
  // the source-closure parse check; Next must still emit the standalone app.
  typescript: { ignoreBuildErrors: true },
  experimental: {
    turbopackFileSystemCacheForDev: true,
    turbopackFileSystemCacheForBuild: false,
    useTypeScriptCli: true,
  },
  async rewrites() {
    const origin =
      process.env.LINGXILEARN_API_ORIGIN ||
      (process.env.NODE_ENV === 'development' ? 'http://127.0.0.1:8000' : undefined)
    if (!origin) return []
    const base = origin.replace(/\/$/, '')
    return [
      { source: '/api/:path*', destination: `${base}/api/:path*` },
      { source: '/auth/:path*', destination: `${base}/auth/:path*` },
      { source: '/api/v1/:path*', destination: `${base}/api/v1/:path*` },
    ]
  },
}

export default nextConfig
