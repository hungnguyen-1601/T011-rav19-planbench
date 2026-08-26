/** `/system`, and the version that had to stop being two numbers.
 *
 * The table carried a hand-maintained `FRONTEND_VERSION = "0.1.0"` above
 * the one the API reports. The app ships as a single desktop bundle
 * whose launcher sets the backend's version, so the two could agree only
 * by somebody remembering — and a reader checking either against a
 * release note had no way to know which was the app's.
 *
 * Source-level, like the other page tests: the page sits behind an
 * effect and a fetch, so a first paint would show only "checking".
 */

import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

import en from "../../lib/i18n/locales/en.json";
import vi from "../../lib/i18n/locales/vi.json";

const PAGE = readFileSync(join(process.cwd(), "src", "app", "system", "page.tsx"), "utf8");
/* Comments stripped, because the file explains at length what it no
   longer does — and a test that read the explanation as the thing
   itself would fail on the record of the fix. */
const CODE = PAGE.replace(/\/\*[\s\S]*?\*\//g, "").replace(/^\s*\/\/.*$/gm, "");

describe("one version, from the backend", () => {
  it("has no frontend version constant left to drift", () => {
    expect(CODE).not.toContain("FRONTEND_VERSION");
    /* The literal too: a constant renamed is a constant still
       maintained by hand. */
    expect(CODE).not.toMatch(/"0\.1\.0"/);
  });

  it("names no frontend version string in either locale", () => {
    for (const [locale, dictionary] of [
      ["en", en],
      ["vi", vi],
    ] as const) {
      expect(dictionary, `${locale} still has the key`).not.toHaveProperty(
        "system.frontendVersion",
      );
    }
    expect(CODE).not.toContain("system.frontendVersion");
  });

  it("still shows the version the API reports", () => {
    /* Removing the row is only half the change: what is left has to be
       the version, not nothing. */
    expect(CODE).toContain('t("system.backendVersion")');
    expect(CODE).toContain("health.version");
  });

  it("labels the remaining row as the version, not as one of two", () => {
    /* With a single number on the page, "Backend version" invited the
       question of where the other one went. */
    expect(en["system.backendVersion"]).toBe("Version");
    expect(vi["system.backendVersion"]).toBe("Phiên bản");
  });

  it("has every key it asks for, in both locales", () => {
    const keys = new Set([...CODE.matchAll(/\bt\(\s*"([^"`]+)"/g)].map((match) => match[1]));
    expect(keys.size).toBeGreaterThan(0);
    for (const key of keys) {
      expect(en, `en is missing ${key}`).toHaveProperty(key);
      expect(vi, `vi is missing ${key}`).toHaveProperty(key);
    }
  });
});
