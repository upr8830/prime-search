import type { NextConfig } from "next";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { parseEnv } from "node:util";

/**
 * The API origin, from the variables the API itself reads (docs/01 §2, docs/07 §1):
 * the shell first, then only PRIME_API_HOST / PRIME_API_PORT from the repo-root .env,
 * then 127.0.0.1:8765. Nothing else in .env reaches the UI or the browser.
 */
function apiOrigin(): string {
  let fromFile: { host?: string; port?: string } = {};
  try {
    const parsed = parseEnv(readFileSync(resolve(process.cwd(), "..", ".env"), "utf-8"));
    fromFile = { host: parsed.PRIME_API_HOST, port: parsed.PRIME_API_PORT };
  } catch {
    // No .env (a reviewer without keys): the defaults below.
  }
  const host = process.env.PRIME_API_HOST || fromFile.host || "127.0.0.1";
  const port = process.env.PRIME_API_PORT || fromFile.port || "8765";
  // 0.0.0.0 is a bind address, not one a browser can reach.
  return `http://${host === "0.0.0.0" ? "127.0.0.1" : host}:${port}`;
}

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
