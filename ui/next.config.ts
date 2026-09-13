import type { NextConfig } from "next";

import { apiOrigin } from "./api-origin.mjs";

const API_ORIGIN = apiOrigin();

const nextConfig: NextConfig = {
  // The event stream connects to the API directly: a dev rewrite can buffer a streamed
  // response, and the API's CORS allows this dev server (docs/11). REST goes via /api.
  env: { NEXT_PUBLIC_PRIME_API_ORIGIN: API_ORIGIN },
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${API_ORIGIN}/:path*` }];
  },
};

export default nextConfig;
