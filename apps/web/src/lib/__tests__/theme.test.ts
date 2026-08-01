/** Light, dark, system — and the reason there is no flash.
 *
 * The flash test is the important one. It cannot be done by rendering,
 * because the whole point is what happens *before* React renders, so it
 * is done the only honest way: run the actual inlined script against a
 * fake `<html>` and assert on the attribute it leaves behind.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  THEME_PREFERENCES,
  THEME_SCRIPT,
  THEME_STORAGE_KEY,
  applyTheme,
  resolveTheme,
  themeStore,
  watchSystemTheme,
} from "@/lib/theme";

describe("resolveTheme", () => {
  it("pins light and dark whatever the OS says", () => {
    expect(resolveTheme("light", true)).toBe("light");
    expect(resolveTheme("light", false)).toBe("light");
    expect(resolveTheme("dark", false)).toBe("dark");
    expect(resolveTheme("dark", true)).toBe("dark");
  });

  it("follows the OS for system", () => {
    expect(resolveTheme("system", true)).toBe("dark");
    expect(resolveTheme("system", false)).toBe("light");
  });

  it("offers exactly three preferences", () => {
    expect([...THEME_PREFERENCES]).toEqual(["light", "dark", "system"]);
  });
});

/** A minimal stand-in for the bits of the DOM the script touches. */
function fakeRoot() {
  return { dataset: {} as Record<string, string>, style: {} as Record<string, string> };
}

function stubDom(options: { stored?: string | null; prefersDark: boolean }) {
  const root = fakeRoot();
  const store = new Map<string, string>();
  if (options.stored) store.set(THEME_STORAGE_KEY, options.stored);
  vi.stubGlobal("document", { documentElement: root });
  vi.stubGlobal("window", {
    localStorage: {
      getItem: (key: string) => store.get(key) ?? null,
      setItem: (key: string, value: string) => store.set(key, value),
    },
    matchMedia: (query: string) => ({
      matches: query.includes("dark") ? options.prefersDark : !options.prefersDark,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    }),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
  });
  return root;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("the blocking script — no flash of the wrong theme", () => {
  /** Run the real script string, exactly as the browser would. */
  function runScript(): Record<string, string> {
    // eslint-disable-next-line no-new-func
    new Function(THEME_SCRIPT)();
    return (document.documentElement as unknown as ReturnType<typeof fakeRoot>).dataset;
  }

  it("applies a remembered dark theme before anything renders", () => {
    stubDom({ stored: "dark", prefersDark: false });
    expect(runScript().theme).toBe("dark");
  });

  it("applies a remembered light theme even when the OS is dark", () => {
    // The case that actually flashes: the app defaults to dark, so a
    // light-preferring user is the one who would see it flip.
    stubDom({ stored: "light", prefersDark: true });
    expect(runScript().theme).toBe("light");
  });

  it("resolves system against the OS", () => {
    stubDom({ stored: "system", prefersDark: true });
    expect(runScript().theme).toBe("dark");

    stubDom({ stored: "system", prefersDark: false });
    expect(runScript().theme).toBe("light");
  });

  it("defaults to system when nothing was ever chosen", () => {
    const root = stubDom({ stored: null, prefersDark: false });
    runScript();
    expect(root.dataset.themePref).toBe("system");
    expect(root.dataset.theme).toBe("light");
  });

  it("keeps the raw preference separate from the resolved colour", () => {
    // The switcher shows "System"; the stylesheet needs "dark".
    const root = stubDom({ stored: "system", prefersDark: true });
    runScript();
    expect(root.dataset.themePref).toBe("system");
    expect(root.dataset.theme).toBe("dark");
  });

  it("also restores a collapsed sidebar before first paint", () => {
    const root = stubDom({ stored: "dark", prefersDark: true });
    window.localStorage.setItem("planbench.sidebar", "collapsed");
    runScript();
    expect(root.dataset.sidebar).toBe("collapsed");
  });

  it("leaves the sidebar expanded when that is what was remembered", () => {
    const root = stubDom({ stored: "dark", prefersDark: true });
    window.localStorage.setItem("planbench.sidebar", "expanded");
    runScript();
    expect(root.dataset.sidebar).toBeUndefined();
  });

  it("never throws, even with no storage at all", () => {
    // A throw here leaves the page unstyled, which is worse than the
    // wrong theme.
    vi.stubGlobal("document", { documentElement: fakeRoot() });
    vi.stubGlobal("window", {
      get localStorage(): Storage {
        throw new Error("blocked");
      },
      matchMedia: () => ({ matches: false }),
    });
    expect(() => new Function(THEME_SCRIPT)()).not.toThrow();
  });
});

describe("applyTheme", () => {
  it("stamps the resolved theme, the preference and colour-scheme", () => {
    const root = stubDom({ stored: null, prefersDark: true });
    applyTheme("system");
    expect(root.dataset.theme).toBe("dark");
    expect(root.dataset.themePref).toBe("system");
    // Native widgets — scrollbars, date pickers — follow this.
    expect(root.style.colorScheme).toBe("dark");
  });

  it("overrides the OS when a colour is pinned", () => {
    const root = stubDom({ stored: null, prefersDark: true });
    applyTheme("light");
    expect(root.dataset.theme).toBe("light");
  });
});

describe("the store", () => {
  it("remembers the choice and applies it", () => {
    const root = stubDom({ stored: null, prefersDark: true });
    themeStore.set("light");
    expect(window.localStorage.getItem(THEME_STORAGE_KEY)).toBe("light");
    expect(root.dataset.theme).toBe("light");
    themeStore.set("system");
  });
});

describe("watchSystemTheme", () => {
  it("subscribes to OS changes and unsubscribes cleanly", () => {
    // "System" has to keep meaning system: a laptop that dims at sunset
    // must dim this too, not stay on whatever it was when the tab opened.
    const add = vi.fn();
    const remove = vi.fn();
    vi.stubGlobal("document", { documentElement: fakeRoot() });
    vi.stubGlobal("window", {
      localStorage: { getItem: () => "system", setItem: () => {} },
      matchMedia: () => ({ matches: true, addEventListener: add, removeEventListener: remove }),
    });

    const stop = watchSystemTheme();
    expect(add).toHaveBeenCalledWith("change", expect.any(Function));
    stop();
    expect(remove).toHaveBeenCalledWith("change", expect.any(Function));
  });

  it("is a no-op where matchMedia does not exist", () => {
    vi.stubGlobal("window", {});
    expect(() => watchSystemTheme()()).not.toThrow();
  });
});
