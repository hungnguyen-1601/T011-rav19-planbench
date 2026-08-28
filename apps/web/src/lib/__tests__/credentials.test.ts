/** Every HTTP client this app has must carry the session token.
 *
 * **Why this file exists.** The web app grew two clients: `authFetch` in
 * `auth.ts` for the newer modules, and `request` in `api.ts`, which
 * predates accounts. While reading was open to anybody, the missing
 * header on the second one was invisible — every call worked. Closing
 * the routes made it visible all at once, as `missing bearer token` on
 * six pages, and by then the change that closed them had already been
 * committed and reviewed.
 *
 * The rule was never written down anywhere a test could check, which is
 * exactly why it was possible to close a door and forget to hand out the
 * key. So this asserts the rule itself rather than one client's
 * behaviour: **a module that calls the API attaches the token**, and a
 * new client added tomorrow fails here rather than in somebody's
 * browser.
 *
 * Source text rather than a rendered request, in the same style as the
 * rest of this suite: there is no jsdom here, and the property worth
 * pinning — "the header is attached" — is visible in the source and
 * survives any refactor that keeps it true.
 */

import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

const LIB = join(process.cwd(), "src", "lib");
const read = (name: string) => readFileSync(join(LIB, name), "utf8");

const API = read("api.ts");
const AUTH = read("auth.ts");
const ORIGIN = read("origin.ts");
const STREAM = read("useEpisodeStream.ts");

describe("both HTTP clients send the token", () => {
  it("attaches it in api.ts, which for a long time did not", () => {
    expect(API).toContain("Authorization: `Bearer ${session.token}`");
  });

  it("attaches it in authFetch, the other client", () => {
    expect(AUTH).toContain("Authorization: `Bearer ${session.token}`");
  });

  it("reads the session per request rather than at module scope", () => {
    /* A token captured when the module first loaded would outlive a
       sign-out: the page would keep sending a credential the server has
       stopped honouring, and the failure would look like a server bug. */
    expect(API).toContain("const session = loadSession();");
    // Inside the request function, not beside the import.
    const body = API.slice(API.indexOf("async function request"));
    expect(body).toContain("const session = loadSession();");
  });

  it("drops a session the server has rejected, in both clients", () => {
    // Otherwise the header still says who you are above a page that can
    // load nothing.
    expect(API).toContain("if (response.status === 401) clearSession();");
    expect(AUTH).toContain("if (response.status === 401) clearSession();");
  });
});

describe("the two clients do not import each other", () => {
  it("keeps the shared origin in a module of its own", () => {
    /* `auth.ts` needs `API_BASE` and `api.ts` needs the session. Had
       both stayed where they were, the two would import each other, and
       which one finishes initialising first would depend on which the
       bundler reached first — with a `const` read in that window being
       `undefined` rather than an error. */
    expect(ORIGIN).toContain("export const API_BASE");
    expect(AUTH).toContain('from "./origin"');
    expect(AUTH).not.toContain('from "./api"');
    expect(API).toContain('from "./auth"');
  });

  it("still lets everything import API_BASE from where it always did", () => {
    // Twenty-odd modules name `@/lib/api` for it. Moving the value is
    // not a reason to touch all of them.
    expect(API).toContain('export { API_BASE } from "./origin";');
  });
});

describe("the replay socket", () => {
  it("asks for a ticket instead of putting a token in the URL", () => {
    /* A browser cannot set a header on a WebSocket. The obvious way out
       — `?token=<jwt>` — writes an hour-long credential into every
       access log and history entry on the path; a ticket is single-use
       and lasts a minute, so a log line that caught it describes
       something already spent. */
    expect(API).toContain('request<Ticket>("/ws/tickets", { method: "POST" })');
    expect(API).toContain("ticket=${encodeURIComponent(ticket)}");
    expect(API).not.toContain("token=${");
  });

  it("mints one per connection rather than reusing it", () => {
    // Redeemed on connect and gone, so a reconnect needs a new one.
    expect(API).toContain("export async function wsUrl(");
  });

  it("does not connect an attempt the caller has abandoned", () => {
    /* The ticket round trip opens a window in which the caller can pick
       another episode or the component can unmount. Without the guard
       the stale ticket still arrives, still opens a socket, and two
       sockets write frames into one piece of state. */
    expect(STREAM).toContain("const attempt = attemptRef.current;");
    expect(STREAM).toContain("if (attempt !== attemptRef.current) return;");
    expect(STREAM).toContain("attemptRef.current += 1;");
  });

  it("shows why the ticket was refused rather than a generic failure", () => {
    // "signed out" and "you cannot run simulations" are different
    // problems, and "WebSocket connection failed" is neither.
    expect(STREAM).toContain("caught instanceof Error ? caught.message");
  });
});
