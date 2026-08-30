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

/** Import `api.ts` fresh, with the environment these cases describe.
 *
 * The window stub carries a `sessionStorage` as well as a location,
 * because the client now reads the session on every request. An empty
 * one is the signed-out case and is all these cases need — what is under
 * test here is the address, not the credential.
 */
async function load(options: { env?: string; origin?: string }) {
  if (options.env === undefined) delete process.env[ENV_KEY];
  else process.env[ENV_KEY] = options.env;
  if (options.origin === undefined) vi.stubGlobal("window", undefined);
  else {
    vi.stubGlobal("window", {
      location: { origin: options.origin },
      sessionStorage: { getItem: () => null, setItem: () => {}, removeItem: () => {} },
      addEventListener: () => {},
      removeEventListener: () => {},
    });
  }
  return import("@/lib/api");
}

/** Answer the ticket request with a fixed ticket. */
function stubTicket(ticket = "tk-1") {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => ({
      ok: true,
      status: 200,
      statusText: "OK",
      json: async () => ({ ticket, expires_in: 60 }),
    })),
  );
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
    stubTicket();
    const { wsUrl } = await load({ origin: "http://127.0.0.1:53412" });
    expect(await wsUrl("sim-1")).toBe(
      "ws://127.0.0.1:53412/ws/simulations/sim-1?pace=false&ticket=tk-1",
    );
  });

  it("upgrades to wss when the page is served over https", async () => {
    /* `http` -> `ws` and `https` -> `wss` come out of the same one-line
       replacement; the second is the one nobody tests by hand. */
    stubTicket();
    const { wsUrl } = await load({ origin: "https://planbench.example" });
    expect(await wsUrl("sim-1", true)).toBe(
      "wss://planbench.example/ws/simulations/sim-1?pace=true&ticket=tk-1",
    );
  });

  it("asks the API for the ticket before building the URL", async () => {
    /* The socket carries a single-use ticket rather than the bearer
       token, because a browser cannot set a header on a WebSocket and a
       token in a query string lands in every log on the path. */
    stubTicket();
    const { wsUrl } = await load({ origin: "http://127.0.0.1:53412" });
    await wsUrl("sim-1");
    const called = vi.mocked(fetch).mock.calls[0];
    expect(called[0]).toBe("http://127.0.0.1:53412/api/v1/ws/tickets");
    expect((called[1] as RequestInit).method).toBe("POST");
  });

  it("escapes the ticket instead of pasting it in", async () => {
    // `token_urlsafe` will not produce one, but the URL is built by
    // concatenation and a value that needed escaping would silently
    // truncate the query string.
    stubTicket("a b&c");
    const { wsUrl } = await load({ origin: "http://127.0.0.1:53412" });
    expect(await wsUrl("sim-1")).toContain("ticket=a%20b%26c");
  });
});
