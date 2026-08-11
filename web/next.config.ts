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
  images: { unoptimized: true },
  env: {
    NEXT_PUBLIC_API_BASE: process.env.NEXT_PUBLIC_API_BASE ?? "",
  },
};

export default nextConfig;
