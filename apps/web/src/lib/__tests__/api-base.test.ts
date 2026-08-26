/** Where the client sends its requests, and who decides.
 *
 * Three deployments, one constant:
 *
 * - **Docker and `next dev`** set `NEXT_PUBLIC_API_URL` at build time.
 *   That still wins outright, so neither changes.
 * - **The desktop build** cannot: the API picks a free port at startup
 *   and serves the exported UI from the same process, so the only thing
 *   that knows where the backend is, is the address bar.
 *
 * The module is re-imported per case because `API_BASE` is computed once
 * at import — which is the point, but makes every assertion here a
 * question about module evaluation rather than about a function.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const ENV_KEY = "NEXT_PUBLIC_API_URL";
let saved: string | undefined;

beforeEach(() => {
  saved = process.env[ENV_KEY];
  vi.resetModules();
});

afterEach(() => {
  if (saved === undefined) delete process.env[ENV_KEY];
  else process.env[ENV_KEY] = saved;
  vi.unstubAllGlobals();
});

/** Import `api.ts` fresh, with the environment these cases describe. */
async function load(options: { env?: string; origin?: string }) {
  if (options.env === undefined) delete process.env[ENV_KEY];
  else process.env[ENV_KEY] = options.env;
  if (options.origin === undefined) vi.stubGlobal("window", undefined);
  else vi.stubGlobal("window", { location: { origin: options.origin } });
  return import("@/lib/api");
}

describe("API_BASE", () => {
  it("obeys the build-time variable wherever one is set", async () => {
    const { API_BASE } = await load({
      env: "http://localhost:8000",
      origin: "http://127.0.0.1:53412",
    });
    expect(API_BASE).toBe("http://localhost:8000");
  });

  it("falls back to the page's own origin, not a fixed port", async () => {
    /* The desktop case. The API's port is chosen at startup and the
       exported UI is served from the same process, so a literal
       localhost:8000 would address whatever else is on 8000. */
    const { API_BASE } = await load({ origin: "http://127.0.0.1:53412" });
    expect(API_BASE).toBe("http://127.0.0.1:53412");
  });

  it("still has a legal URL while the export is being prerendered", async () => {
    /* Node, no location. Nothing fetches during a prerender; the value
       only has to be something `new URL` accepts. */
    const { API_BASE } = await load({});
    expect(API_BASE).toBe("http://localhost:8000");
    expect(() => new URL(API_BASE)).not.toThrow();
  });
});

describe("wsUrl", () => {
  it("follows the same origin the REST calls use", async () => {
    const { wsUrl } = await load({ origin: "http://127.0.0.1:53412" });
    expect(wsUrl("sim-1")).toBe("ws://127.0.0.1:53412/ws/simulations/sim-1?pace=false");
  });

  it("upgrades to wss when the page is served over https", async () => {
    /* `http` -> `ws` and `https` -> `wss` come out of the same one-line
       replacement; the second is the one nobody tests by hand. */
    const { wsUrl } = await load({ origin: "https://planbench.example" });
    expect(wsUrl("sim-1", true)).toBe(
      "wss://planbench.example/ws/simulations/sim-1?pace=true",
    );
  });
});
