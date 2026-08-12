import type { NextConfig } from "next";

/**
 * Static export.
 *
 * Every byte the learner sees comes from the API at runtime, so there is
 * nothing for a Node server to render. Exporting to static files lets FastAPI
 * serve the whole app from one process on one port — the fewest things that
 * have to be right for someone to see it work. The compose file still runs a
 * separate web container when you want the two scaled independently.
 */
const nextConfig: NextConfig = {
  output: "export",
  trailingSlash: true,
  // Keep production checks isolated from a concurrently running dev server.
  distDir: process.env.NEXT_DIST_DIR ?? ".next",
  images: { unoptimized: true },
  env: {
    NEXT_PUBLIC_API_BASE: process.env.NEXT_PUBLIC_API_BASE ?? "",
    NEXT_PUBLIC_LOGTO_ENDPOINT: process.env.NEXT_PUBLIC_LOGTO_ENDPOINT ?? "",
    NEXT_PUBLIC_LOGTO_APP_ID: process.env.NEXT_PUBLIC_LOGTO_APP_ID ?? "",
    NEXT_PUBLIC_LOGTO_RESOURCE: process.env.NEXT_PUBLIC_LOGTO_RESOURCE ?? "",
    NEXT_PUBLIC_LOGTO_REDIRECT_URI: process.env.NEXT_PUBLIC_LOGTO_REDIRECT_URI ?? "",
    NEXT_PUBLIC_LINGXI_IDENTITY_ISSUER: process.env.NEXT_PUBLIC_LINGXI_IDENTITY_ISSUER ?? "",
    NEXT_PUBLIC_LINGXI_IDENTITY_CLIENT_ID: process.env.NEXT_PUBLIC_LINGXI_IDENTITY_CLIENT_ID ?? "",
    NEXT_PUBLIC_LINGXI_IDENTITY_RESOURCE: process.env.NEXT_PUBLIC_LINGXI_IDENTITY_RESOURCE ?? "",
    NEXT_PUBLIC_LINGXI_IDENTITY_REDIRECT_URI: process.env.NEXT_PUBLIC_LINGXI_IDENTITY_REDIRECT_URI ?? "",
    NEXT_PUBLIC_LINGXI_IDENTITY_SCOPE: process.env.NEXT_PUBLIC_LINGXI_IDENTITY_SCOPE ?? "openid profile",
  },
};

export default nextConfig;
