/** The session store.
 *
 * These tests exist because of a real bug: the sidebar kept showing
 * "Not signed in" after a successful login. `SessionBar` lives in the
 * root layout, so it mounts once per tab; a one-shot read on mount
 * captured the signed-out state, and client-side navigation never
 * remounted it to correct that.
 *
 * Two properties matter for `useSyncExternalStore` and are covered
 * below: subscribers are notified on every real change, and the
 * snapshot is reference-stable when nothing changed — an unstable
 * snapshot makes React re-render forever.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { Session } from "../auth";

class MemoryStorage implements Storage {
  private items = new Map<string, string>();
  get length(): number {
    return this.items.size;
  }
  clear(): void {
    this.items.clear();
  }
  getItem(key: string): string | null {
    return this.items.get(key) ?? null;
  }
  key(index: number): string | null {
    return [...this.items.keys()][index] ?? null;
  }
  removeItem(key: string): void {
    this.items.delete(key);
  }
  setItem(key: string, value: string): void {
    this.items.set(key, value);
  }
}

const ALICE = {
  id: "user-alice",
  nickname: "alice",
  email: "alice@example.com",
  display_name: "Alice Example",
  avatar_url: "",
  is_admin: false,
  needs_nickname: false,
  providers: ["google"],
};

const SESSION: Session = { token: "token-abc", user: ALICE };

/** A fresh module per test: the store caches at module scope. */
async function freshAuth() {
  vi.resetModules();
  return import("../auth");
}

beforeEach(() => {
  vi.stubGlobal("window", {
    sessionStorage: new MemoryStorage(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
  });
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("reading the session", () => {
  it("reports no session before anyone signs in", async () => {
    const auth = await freshAuth();
    expect(auth.loadSession()).toBeNull();
  });

  it("returns the session after saving one", async () => {
    const auth = await freshAuth();
    auth.saveSession(SESSION);
    expect(auth.loadSession()).toEqual(SESSION);
  });

  it("returns a stable reference while nothing changes", async () => {
    // useSyncExternalStore compares snapshots by identity; rebuilding
    // the object on every read would loop forever.
    const auth = await freshAuth();
    auth.saveSession(SESSION);
    expect(auth.loadSession()).toBe(auth.loadSession());
  });

  it("returns a new reference once the session changes", async () => {
    const auth = await freshAuth();
    auth.saveSession(SESSION);
    const before = auth.loadSession();
    auth.saveSession({ ...SESSION, user: { ...ALICE, id: "user-bob", nickname: "bob" } });
    expect(auth.loadSession()).not.toBe(before);
    expect(auth.loadSession()?.user.nickname).toBe("bob");
  });

  it("notices a nickname change on the same account", async () => {
    // The sidebar shows it, so a rename has to propagate without a
    // fresh sign-in.
    const auth = await freshAuth();
    auth.saveSession(SESSION);
    auth.updateSessionUser({ ...ALICE, nickname: "alice-v2" });
    expect(auth.loadSession()?.user.nickname).toBe("alice-v2");
    expect(auth.loadSession()?.token).toBe(SESSION.token);
  });

  it("ignores a profile update when nobody is signed in", async () => {
    const auth = await freshAuth();
    auth.updateSessionUser(ALICE);
    expect(auth.loadSession()).toBeNull();
  });

  it("treats a stored account with no id as no session", async () => {
    // An id is the only thing the app uses to identify anyone; without
    // it the record is unusable, not partially usable.
    const auth = await freshAuth();
    window.sessionStorage.setItem("planbench.token", "token-abc");
    window.sessionStorage.setItem("planbench.user", JSON.stringify({ nickname: "alice" }));
    expect(auth.loadSession()).toBeNull();
  });

  it("fills in defaults for a record written by an older build", async () => {
    const auth = await freshAuth();
    window.sessionStorage.setItem("planbench.token", "token-abc");
    window.sessionStorage.setItem("planbench.user", JSON.stringify({ id: "u1", nickname: "alice" }));
    const session = auth.loadSession();
    expect(session?.user.providers).toEqual([]);
    expect(session?.user.is_admin).toBe(false);
    expect(session?.user.needs_nickname).toBe(false);
  });

  it("marks an account with no nickname as needing one", async () => {
    const auth = await freshAuth();
    window.sessionStorage.setItem("planbench.token", "token-abc");
    window.sessionStorage.setItem("planbench.user", JSON.stringify({ id: "u1" }));
    expect(auth.loadSession()?.user.needs_nickname).toBe(true);
  });

  it("clears the session on sign out", async () => {
    const auth = await freshAuth();
    auth.saveSession(SESSION);
    auth.clearSession();
    expect(auth.loadSession()).toBeNull();
  });

  it("treats a corrupted user record as no session", async () => {
    const auth = await freshAuth();
    window.sessionStorage.setItem("planbench.token", "token-abc");
    window.sessionStorage.setItem("planbench.user", "{not json");
    expect(auth.loadSession()).toBeNull();
  });

  it("treats a token with no user record as no session", async () => {
    const auth = await freshAuth();
    window.sessionStorage.setItem("planbench.token", "token-abc");
    expect(auth.loadSession()).toBeNull();
  });

  it("keeps the token out of the user record", async () => {
    // One place owns the token; duplicating it invites the two copies
    // to disagree.
    const auth = await freshAuth();
    auth.saveSession(SESSION);
    const raw = window.sessionStorage.getItem("planbench.user") ?? "";
    expect(raw).not.toContain(SESSION.token);
    expect(JSON.parse(raw)).toEqual(ALICE);
  });

  it("stores nothing belonging to the identity provider", async () => {
    // The browser holds a PlanBench token and a profile. No provider
    // access token, no client id, no secret ever reaches it.
    const auth = await freshAuth();
    auth.saveSession(SESSION);
    const everything = JSON.stringify([
      window.sessionStorage.getItem("planbench.token"),
      window.sessionStorage.getItem("planbench.user"),
    ]).toLowerCase();
    for (const forbidden of ["client_secret", "client_id", "refresh_token", "access_token"]) {
      expect(everything).not.toContain(forbidden);
    }
  });
});

describe("subscribers", () => {
  it("notifies when a session appears — the bug this fixes", async () => {
    const auth = await freshAuth();
    const seen: (Session | null)[] = [];
    const unsubscribe = auth.subscribeToSession(() => seen.push(auth.loadSession()));

    auth.saveSession(SESSION);

    expect(seen).toEqual([SESSION]);
    unsubscribe();
  });

  it("notifies on sign out", async () => {
    const auth = await freshAuth();
    auth.saveSession(SESSION);
    const seen: (Session | null)[] = [];
    const unsubscribe = auth.subscribeToSession(() => seen.push(auth.loadSession()));

    auth.clearSession();

    expect(seen).toEqual([null]);
    unsubscribe();
  });

  it("stays quiet when the same session is saved again", async () => {
    // Re-saving an identical session must not churn every subscriber.
    const auth = await freshAuth();
    const seen: unknown[] = [];
    const unsubscribe = auth.subscribeToSession(() => seen.push(auth.loadSession()));

    auth.saveSession(SESSION);
    auth.saveSession({ ...SESSION });

    expect(seen).toHaveLength(1);
    unsubscribe();
  });

  it("notifies every subscriber", async () => {
    // The sidebar and the current page both watch the same store.
    const auth = await freshAuth();
    let sidebar = 0;
    let page = 0;
    const stopSidebar = auth.subscribeToSession(() => (sidebar += 1));
    const stopPage = auth.subscribeToSession(() => (page += 1));

    auth.saveSession(SESSION);

    expect([sidebar, page]).toEqual([1, 1]);
    stopSidebar();
    stopPage();
  });

  it("stops notifying after unsubscribe", async () => {
    const auth = await freshAuth();
    const seen: unknown[] = [];
    const unsubscribe = auth.subscribeToSession(() => seen.push(1));
    unsubscribe();

    auth.saveSession(SESSION);

    expect(seen).toEqual([]);
  });

  it("listens for storage events only while someone is subscribed", async () => {
    // A duplicated tab shares this sessionStorage and can sign out
    // independently; the listener is attached lazily and removed again.
    const auth = await freshAuth();
    expect(window.addEventListener).not.toHaveBeenCalled();

    const unsubscribe = auth.subscribeToSession(() => {});
    expect(window.addEventListener).toHaveBeenCalledWith("storage", expect.any(Function));

    unsubscribe();
    expect(window.removeEventListener).toHaveBeenCalledWith("storage", expect.any(Function));
  });
});
