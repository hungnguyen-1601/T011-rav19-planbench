/** Collapsing the sidebar, and remembering it.
 *
 * The state is a single attribute on `<html>`; the widths are CSS. That
 * split is what lets a remembered collapse apply before React runs, so
 * these tests check the attribute, not a pixel value.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  SIDEBAR_STORAGE_KEY,
  applySidebar,
  sidebarStore,
  toggleSidebar,
} from "@/lib/sidebar";
import { THEME_SCRIPT } from "@/lib/theme";

function stubDom(stored?: string) {
  const store = new Map<string, string>();
  if (stored) store.set(SIDEBAR_STORAGE_KEY, stored);
  const root = { dataset: {} as Record<string, string | undefined> };
  vi.stubGlobal("document", { documentElement: root });
  vi.stubGlobal("window", {
    localStorage: {
      getItem: (key: string) => store.get(key) ?? null,
      setItem: (key: string, value: string) => store.set(key, value),
    },
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
  });
  return { root, store };
}

beforeEach(() => {
  stubDom();
  // The store caches; reset it to the default before each case.
  sidebarStore.set("expanded");
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("collapsing", () => {
  it("starts expanded", () => {
    expect(sidebarStore.get()).toBe("expanded");
  });

  it("toggles to collapsed and back", () => {
    toggleSidebar();
    expect(sidebarStore.get()).toBe("collapsed");
    toggleSidebar();
    expect(sidebarStore.get()).toBe("expanded");
  });

  it("remembers the collapse across a reload", () => {
    const { store } = stubDom();
    sidebarStore.set("collapsed");
    expect(store.get(SIDEBAR_STORAGE_KEY)).toBe("collapsed");
  });
});

describe("the html attribute the CSS keys off", () => {
  it("is set when collapsed", () => {
    const { root } = stubDom();
    applySidebar("collapsed");
    expect(root.dataset.sidebar).toBe("collapsed");
  });

  it("is removed when expanded, rather than set to a falsy string", () => {
    // The CSS selector is [data-sidebar="collapsed"]; an empty attribute
    // would not match, but leaving it behind invites a selector that
    // does.
    const { root } = stubDom();
    applySidebar("collapsed");
    applySidebar("expanded");
    expect(root.dataset.sidebar).toBeUndefined();
  });

  it("follows the store automatically", () => {
    const { root } = stubDom();
    sidebarStore.set("collapsed");
    expect(root.dataset.sidebar).toBe("collapsed");
  });
});

describe("the blocking script and this module agree", () => {
  it("uses the same storage key", () => {
    // theme.ts inlines the key rather than importing it, to keep the
    // critical-path script free of imports. This is the guard.
    expect(THEME_SCRIPT).toContain(JSON.stringify(SIDEBAR_STORAGE_KEY));
  });

  it("writes the same attribute value", () => {
    expect(THEME_SCRIPT).toContain('r.dataset.sidebar="collapsed"');
  });
});
