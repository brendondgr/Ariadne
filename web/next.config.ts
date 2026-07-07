import type { NextConfig } from "next";
import path from "node:path";
import { fileURLToPath } from "node:url";

// The FastAPI service the front end proxies to. app.py runs it on this port;
// override with API_PORT (or API_ORIGIN for a fully-qualified host).
const API_ORIGIN = process.env.API_ORIGIN ?? `http://127.0.0.1:${process.env.API_PORT ?? "16501"}`;

const nextConfig: NextConfig = {
  reactStrictMode: true,
  // Pin the workspace root to web/ so a stray lockfile elsewhere on the machine
  // can't make Turbopack infer the wrong root directory.
  turbopack: {
    root: path.dirname(fileURLToPath(import.meta.url)),
  },
  // Same-origin proxy: the browser calls /api/* and Next forwards to FastAPI,
  // so there is no CORS surface and the client needs no absolute URLs.
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${API_ORIGIN}/api/:path*` }];
  },
};

export default nextConfig;
