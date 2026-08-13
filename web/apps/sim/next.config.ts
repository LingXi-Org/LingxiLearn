import path from 'node:path'
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
  turbopack: { root: path.join(import.meta.dirname, '../..') },
  transpilePackages: ['@sim/emcn', '@sim/workflow-renderer', '@sim/workflow-types'],
  // The upstream monorepo intentionally contains server-only Sim modules that
  // are quarantined from this static LingxiGraph browser entrypoint. The
  // frontend tsconfig is checked explicitly by CI/build scripts; letting Next
  // invoke the monorepo-wide default config here would type-check those
  // excluded server modules again.
  typescript: { ignoreBuildErrors: true },
  experimental: {
    turbopackFileSystemCacheForDev: true,
    turbopackFileSystemCacheForBuild: false,
    useTypeScriptCli: true,
  },
}

export default nextConfig
