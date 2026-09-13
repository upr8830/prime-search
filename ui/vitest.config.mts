import { fileURLToPath } from "node:url";

import { defineConfig } from "vitest/config";

// Pure logic only (the run reducer, citation parsing): no DOM, no React rendering.
export default defineConfig({
  resolve: { alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) } },
  test: {
    environment: "node",
    include: ["src/**/*.test.ts"],
    passWithNoTests: true,
  },
});
