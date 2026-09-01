import { fileURLToPath } from "node:url";
import mdx from "@mdx-js/rollup";
import { defineConfig } from "vitest/config";

/** Vitest config.
 *
 * Two things it exists for:
 *
 * - **`jsx: "automatic"`.** `tsconfig.json` says `jsx: "preserve"`, which
 *   is right for Next but leaves esbuild emitting `React.createElement`
 *   against a `React` that was never imported. The automatic runtime is
 *   what Next itself uses.
 * - **the MDX plugin.** Next compiles `.mdx` through its own loader,
 *   which Vitest does not run. Without this, a test that touches the
 *   guide does not fail — it dies while collecting, which reads like a
 *   broken test file rather than a missing transform.
 * - **the `@/` alias**, so tests import components exactly the way the
 *   app does rather than through a parallel set of relative paths.
 *
 * The environment stays Node. There is no jsdom and no testing-library
 * installed, so component assertions go through `renderToStaticMarkup` —
 * real rendered HTML, no browser. That covers first render, which is
 * where the collapsed/expanded and signed-in/signed-out differences
 * live; it does not cover clicking. See docs/reference/KNOWN_LIMITATIONS.md.
 */
export default defineConfig({
  plugins: [mdx()],
  esbuild: { jsx: "automatic" },
  test: {
    // `auth.test.ts` calls `vi.resetModules()` and re-imports the module
    // graph in every case, which is genuinely slow. Alone it never comes
    // near the limit; with the other files competing for workers it
    // occasionally passed 5s and failed as a timeout rather than as an
    // assertion. Nothing about the code is slow — the default is just
    // tight for this shape of test.
    //
    // Raised from 20s when the critique panel landed. The graph each
    // reset re-imports grew, and the suite began failing roughly one run
    // in three — always as a timeout on an assertion that checks two
    // strings, never as a wrong answer. The cost is per-reset transform
    // work, so the ceiling has to track the size of the app rather than
    // the difficulty of the test; when it is hit again the fix is to
    // stop resetting the whole graph, not to keep moving this number.
    testTimeout: 60_000,
  },
  resolve: {
    alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) },
  },
});
