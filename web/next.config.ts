import type { NextConfig } from 'next'

const nextConfig: NextConfig = {
  // Static export is required by the production LingxiLearn web-build stage,
  // but Next middleware and the dev server are incompatible with export mode.
  // Keep the mode explicit so the bind-mounted development container runs the
  // current host source instead of failing during startup.
  output: process.env.NEXT_STATIC_EXPORT === '1' ? 'export' : undefined,
  trailingSlash: true,
  poweredByHeader: false,
  images: { unoptimized: true },
  turbopack: { root: import.meta.dirname },
  typescript: { ignoreBuildErrors: false },
  experimental: {
    turbopackFileSystemCacheForDev: true,
    turbopackFileSystemCacheForBuild: false,
    useTypeScriptCli: true,
  },
}

export default nextConfig
