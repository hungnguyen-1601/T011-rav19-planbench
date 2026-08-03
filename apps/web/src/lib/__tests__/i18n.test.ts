/** Vietnamese and English, and English as the floor.
 *
 * Two properties the app depends on and cannot see for itself: every key
 * exists in both dictionaries, and a missing one degrades to English
 * rather than to a blank. The first is checked exhaustively here because
 * a screen that renders `dashboard.stats.benchmarks` instead of a label
 * is a bug nobody will notice in review.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  DEFAULT_LOCALE,
  DICTIONARIES,
  LOCALES,
  LOCALE_COOKIE,
  detectLocale,
  localeFromCookie,
  localeStore,
  translate,
} from "@/lib/i18n";

describe("the dictionaries", () => {
  it("offers exactly English and Vietnamese", () => {
    expect([...LOCALES]).toEqual(["en", "vi"]);
  });

  it("has the same keys in both languages", () => {
    const en = Object.keys(DICTIONARIES.en).sort();
    const vi = Object.keys(DICTIONARIES.vi).sort();
    expect(vi).toEqual(en);
  });

  it("has no empty string in either language", () => {
    for (const locale of LOCALES) {
      const blank = Object.entries(DICTIONARIES[locale])
        .filter(([, value]) => value.trim() === "")
        .map(([key]) => key);
      expect(blank).toEqual([]);
    }
  });

  it("keeps every placeholder that English uses", () => {
    // A translation that dropped {count} renders a sentence with a hole
    // in it, and only in the language the reviewer does not read.
    const placeholders = (value: string) => (value.match(/\{(\w+)\}/g) ?? []).sort();
    for (const [key, english] of Object.entries(DICTIONARIES.en)) {
      const vietnamese = DICTIONARIES.vi[key];
      expect(placeholders(vietnamese), `mismatch in ${key}`).toEqual(placeholders(english));
    }
  });

  it("actually translates: most values differ between the languages", () => {
    // Some legitimately match — "PlanBench", "Benchmark", "English". A
    // wholesale copy of en.json into vi.json would not.
    const same = Object.keys(DICTIONARIES.en).filter(
      (key) => DICTIONARIES.en[key] === DICTIONARIES.vi[key],
    );
    expect(same.length).toBeLessThan(Object.keys(DICTIONARIES.en).length * 0.2);
  });
});

describe("translate", () => {
  const en = { greeting: "Hello", count: "{n} items", both: "{a} and {b}" };
  const vi = { greeting: "Xin chào" };

  it("prefers the requested language", () => {
    expect(translate(vi, en, "greeting")).toBe("Xin chào");
  });

  it("falls back to English for a missing key", () => {
    // Half-translated is usable; blank is not.
    expect(translate(vi, en, "count", { n: 3 })).toBe("3 items");
  });

  it("returns the key itself when neither language has it", () => {
    // Ugly on purpose: it should be noticed and fixed, not hidden.
    expect(translate(vi, en, "nope.missing")).toBe("nope.missing");
  });

  it("substitutes every placeholder", () => {
    expect(translate(en, en, "both", { a: "x", b: "y" })).toBe("x and y");
  });

  it("leaves a placeholder alone when no value was given", () => {
    expect(translate(en, en, "both", { a: "x" })).toBe("x and {b}");
  });

  it("accepts numbers as values", () => {
    expect(translate(en, en, "count", { n: 0 })).toBe("0 items");
  });

  it("returns the template untouched when there are no vars", () => {
    expect(translate(en, en, "count")).toBe("{n} items");
  });
});

describe("choosing a language for a first-time visitor", () => {
  it("uses the browser's language when it is one we speak", () => {
    expect(detectLocale(["vi"])).toBe("vi");
    expect(detectLocale(["en"])).toBe("en");
  });

  it("matches a regional variant", () => {
    expect(detectLocale(["vi-VN"])).toBe("vi");
    expect(detectLocale(["en-GB", "fr"])).toBe("en");
  });

  it("is case-insensitive", () => {
    expect(detectLocale(["VI-vn"])).toBe("vi");
  });

  it("takes the first language we speak, not the first listed", () => {
    expect(detectLocale(["fr", "de", "vi"])).toBe("vi");
  });

  it("falls back to English for a language we do not speak", () => {
    expect(detectLocale(["fr-FR"])).toBe(DEFAULT_LOCALE);
  });

  it("falls back to English when the browser says nothing", () => {
    expect(detectLocale(undefined)).toBe(DEFAULT_LOCALE);
    expect(detectLocale([])).toBe(DEFAULT_LOCALE);
  });
});

describe("the cookie the server reads", () => {
  it("accepts a language we speak", () => {
    expect(localeFromCookie("vi")).toBe("vi");
  });

  it("ignores anything else", () => {
    expect(localeFromCookie("klingon")).toBe(DEFAULT_LOCALE);
    expect(localeFromCookie(null)).toBe(DEFAULT_LOCALE);
    expect(localeFromCookie(undefined)).toBe(DEFAULT_LOCALE);
  });
});

describe("remembering the language", () => {
  beforeEach(() => {
    vi.stubGlobal("document", { cookie: "", documentElement: {} as Record<string, string> });
    vi.stubGlobal("window", { addEventListener: vi.fn(), removeEventListener: vi.fn() });
  });

  afterEach(() => {
    localeStore.set(DEFAULT_LOCALE);
    vi.unstubAllGlobals();
  });

  it("writes a cookie, because the server has to read it while rendering", () => {
    localeStore.set("vi");
    expect(document.cookie).toContain(`${LOCALE_COOKIE}=vi`);
  });

  it("updates the lang attribute for screen readers and hyphenation", () => {
    localeStore.set("vi");
    expect(document.documentElement.lang).toBe("vi");
  });
});
