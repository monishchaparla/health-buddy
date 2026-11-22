import type { NextConfig } from "next";

const API = process.env.HEALTHBUDDY_API_URL ?? "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  // Same-origin proxy so the API's HTTP-only session cookie works without CORS.
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${API}/:path*` }];
  },
};

export default nextConfig;
