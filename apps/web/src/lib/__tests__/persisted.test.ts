/** The store behind theme, locale and sidebar.
 *
 * All three remember a choice across a reload, so the machinery is
 * written once — which means one set of tests, and no chance of the
 * sidebar remembering correctly while the theme does not.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { createPersistedStore, readCookie } from "@/lib/persisted";

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

type Colour = "red" | "blue";
const COLOURS: readonly Colour[] = ["red", "blue"];

function makeStore(overrides: Partial<Parameters<typeof createPersistedStore<Colour>>[0]> = {}) {
  return createPersistedStore<Colour>({
    key: "test.colour",
    fallback: "red",
    allowed: COLOURS,
    ...overrides,
  });
}

beforeEach(() => {
  vi.stubGlobal("window", {
    localStorage: new MemoryStorage(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
  });
  vi.stubGlobal("document", { cookie: "" });
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("remembering a choice", () => {
  it("starts at the fallback", () => {
    expect(makeStore().get()).toBe("red");
  });

  it("returns what was set", () => {
    const store = makeStore();
    store.set("blue");
    expect(store.get()).toBe("blue");
  });

  it("writes to localStorage so the blocking script can read it", () => {
    // This is the whole reason the theme does not flash: a script in
    // <head> reads this key before React exists.
    const store = makeStore();
    store.set("blue");
    expect(window.localStorage.getItem("test.colour")).toBe("blue");
  });

  it("reads a value written before this page loaded", () => {
    window.localStorage.setItem("test.colour", "blue");
    expect(makeStore().get()).toBe("blue");
  });

  it("ignores a stored value that is not allowed", () => {
    // A stale key from an older build must not put the UI in a state it
    // has no rendering for.
    window.localStorage.setItem("test.colour", "chartreuse");
    expect(makeStore().get()).toBe("red");
  });

  it("ignores an attempt to set an unknown value", () => {
    const store = makeStore();
    store.set("chartreuse" as Colour);
    expect(store.get()).toBe("red");
  });
});

describe("the cookie backend", () => {
  it("writes a cookie the server can read while rendering", () => {
    // Locale uses this: the server has to know the language *before* it
    // renders, and it cannot see localStorage.
    const store = makeStore({ backend: "cookie" });
    store.set("blue");
    expect(document.cookie).toContain("test.colour=blue");
    expect(document.cookie).toContain("samesite=lax");
  });

  it("reads a value out of a cookie header", () => {
    expect(readCookie("planbench.locale", "other=1; planbench.locale=vi; x=2")).toBe("vi");
  });

  it("returns null for a cookie that is not there", () => {
    expect(readCookie("planbench.locale", "other=1")).toBeNull();
  });

  it("does not touch localStorage", () => {
    const store = makeStore({ backend: "cookie" });
    store.set("blue");
    expect(window.localStorage.getItem("test.colour")).toBeNull();
  });
});

describe("subscribers", () => {
  it("notifies on a change", () => {
    const store = makeStore();
    const seen: string[] = [];
    const stop = store.subscribe(() => seen.push(store.get()));
    store.set("blue");
    expect(seen).toEqual(["blue"]);
    stop();
  });

  it("stays quiet when the value did not actually change", () => {
    // An unstable snapshot makes useSyncExternalStore re-render forever.
    const store = makeStore();
    store.set("blue");
    const seen: string[] = [];
    const stop = store.subscribe(() => seen.push(store.get()));
    store.set("blue");
    expect(seen).toEqual([]);
    stop();
  });

  it("stops notifying after unsubscribe", () => {
    const store = makeStore();
    const seen: string[] = [];
    const stop = store.subscribe(() => seen.push(store.get()));
    stop();
    store.set("blue");
    expect(seen).toEqual([]);
  });

  it("runs onChange so the DOM attribute follows the value", () => {
    const applied: string[] = [];
    const store = makeStore({ onChange: (value) => applied.push(value) });
    store.set("blue");
    expect(applied).toEqual(["blue"]);
  });

  it("listens for storage events only while somebody is subscribed", () => {
    const store = makeStore();
    expect(window.addEventListener).not.toHaveBeenCalled();
    const stop = store.subscribe(() => {});
    expect(window.addEventListener).toHaveBeenCalledWith("storage", expect.any(Function));
    stop();
    expect(window.removeEventListener).toHaveBeenCalledWith("storage", expect.any(Function));
  });
});

describe("when storage is unavailable", () => {
  it("falls back rather than throwing", () => {
    // Safari in private mode throws on localStorage. Losing a
    // preference is acceptable; a blank page is not.
    vi.stubGlobal("window", {
      localStorage: {
        getItem() {
          throw new Error("denied");
        },
        setItem() {
          throw new Error("denied");
        },
      },
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    });
    const store = makeStore();
    expect(store.get()).toBe("red");
    expect(() => store.set("blue")).not.toThrow();
    // The choice still applies for this session, even unremembered.
    expect(store.get()).toBe("blue");
  });
});
