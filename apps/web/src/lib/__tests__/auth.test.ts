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

const SESSION: Session = { token: "token-abc", username: "op-alice", role: "operator" };

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
    auth.saveSession({ ...SESSION, username: "rev-carol", role: "reviewer" });
    expect(auth.loadSession()).not.toBe(before);
    expect(auth.loadSession()?.username).toBe("rev-carol");
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
    expect(JSON.parse(raw)).toEqual({ username: "op-alice", role: "operator" });
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
