// The API origin, from the variables the API itself reads (docs/01 §2, docs/07 §1).
// Shared by next.config.ts and scripts/gen-types.mjs so the two cannot disagree.
//
// Order: the shell, then only PRIME_API_HOST / PRIME_API_PORT from the repo-root .env,
// then 127.0.0.1:8765. Nothing else in .env is read into the UI or the browser.

import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { parseEnv } from "node:util";

/** @param {string} [cwd] the ui/ directory (the default when run through pnpm) */
export function apiOrigin(cwd = process.cwd()) {
  let fromFile = {};
  try {
    const parsed = parseEnv(readFileSync(resolve(cwd, "..", ".env"), "utf-8"));
    fromFile = { host: parsed.PRIME_API_HOST, port: parsed.PRIME_API_PORT };
  } catch {
    // No .env (a reviewer without keys): the defaults below.
  }
  const host = process.env.PRIME_API_HOST || fromFile.host || "127.0.0.1";
  const port = process.env.PRIME_API_PORT || fromFile.port || "8765";
  // 0.0.0.0 is a bind address, not one a browser can reach.
  return `http://${host === "0.0.0.0" ? "127.0.0.1" : host}:${port}`;
}
