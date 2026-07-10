import { defineConfig } from "vitest/config";
import { fileURLToPath } from "node:url";

/**
 * Vitest config. Existing suites use relative imports, but component modules
 * under test (and their dependencies) use the `@/*` path alias from tsconfig,
 * so mirror it here for resolution. Environment stays the default (node) — the
 * component tests render to static HTML via react-dom/server, no DOM needed.
 */
export default defineConfig({
  resolve: {
    alias: {
      "@": fileURLToPath(new URL(".", import.meta.url)),
    },
  },
});
