import { fileURLToPath } from "node:url";
import { defineConfig } from "vitest/config";

/** Vitest config.
 *
 * Two things it exists for:
 *
 * - **`jsx: "automatic"`.** `tsconfig.json` says `jsx: "preserve"`, which
 *   is right for Next but leaves esbuild emitting `React.createElement`
 *   against a `React` that was never imported. The automatic runtime is
 *   what Next itself uses.
 * - **the `@/` alias**, so tests import components exactly the way the
 *   app does rather than through a parallel set of relative paths.
 *
 * The environment stays Node. There is no jsdom and no testing-library
 * installed, so component assertions go through `renderToStaticMarkup` —
 * real rendered HTML, no browser. That covers first render, which is
 * where the collapsed/expanded and signed-in/signed-out differences
 * live; it does not cover clicking. See docs/KNOWN_LIMITATIONS.md.
 */
export default defineConfig({
  esbuild: { jsx: "automatic" },
  test: {
    // `auth.test.ts` calls `vi.resetModules()` and re-imports the module
    // graph in every case, which is genuinely slow. Alone it never comes
    // near the limit; with fifteen files competing for workers it
    // occasionally passed 5s and failed as a timeout rather than as an
    // assertion. Nothing about the code is slow — the default is just
    // tight for this shape of test.
    testTimeout: 20_000,
  },
  resolve: {
    alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) },
  },
});
