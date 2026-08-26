/** The blocking script that stamps `<html lang>`.
 *
 * The root layout used to read the locale cookie on the server, which a
 * static export cannot do. This script is the replacement, and the only
 * thing that keeps a Vietnamese user's document from claiming to be
 * English until React hydrates. Run here exactly as the browser runs
 * it — as a string, through `new Function` — because what is being
 * asserted is that the *string* is correct, not that some TypeScript
 * beside it is.
 */

import { readFileSync } from "node:fs";
import { join } from "node:path";

import { afterEach, describe, expect, it, vi } from "vitest";

import { DEFAULT_LOCALE, LOCALE_COOKIE } from "@/lib/i18n/shared";
import { LOCALE_SCRIPT } from "@/lib/locale-script";

/** A `document` with just enough of one for the script. */
function stubDocument(cookie: string): { documentElement: { lang: string } } {
  const documentElement = { lang: "" };
  vi.stubGlobal("document", { cookie, documentElement });
  return { documentElement };
}

function run(cookie: string): string {
  const doc = stubDocument(cookie);
  new Function(LOCALE_SCRIPT)();
  return doc.documentElement.lang;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("LOCALE_SCRIPT", () => {
  it("stamps a remembered Vietnamese before anything paints", () => {
    expect(run(`${LOCALE_COOKIE}=vi`)).toBe("vi");
  });

  it("finds the cookie among others, wherever it sits", () => {
    expect(run(`planbench.theme=dark; ${LOCALE_COOKIE}=vi; other=1`)).toBe("vi");
    expect(run(`${LOCALE_COOKIE}=vi; planbench.theme=dark`)).toBe("vi");
  });

  it("does not mistake a cookie whose name merely ends the same way", () => {
    expect(run(`not.${LOCALE_COOKIE}=vi`)).toBe(DEFAULT_LOCALE);
  });

  it("falls back to the default when nothing is remembered", () => {
    expect(run("")).toBe(DEFAULT_LOCALE);
    expect(run("planbench.theme=dark")).toBe(DEFAULT_LOCALE);
  });

  it("ignores a value that is not a locale this app has", () => {
    /* A cookie is user-editable. `lang="../../etc"` is not a locale. */
    expect(run(`${LOCALE_COOKIE}=fr`)).toBe(DEFAULT_LOCALE);
    expect(run(`${LOCALE_COOKIE}=`)).toBe(DEFAULT_LOCALE);
  });

  it("survives a document that will not answer", () => {
    /* It runs before everything else on the page. Throwing here would
       take the whole document with it, over a language preference. */
    vi.stubGlobal("document", {
      get cookie(): string {
        throw new Error("no");
      },
      documentElement: { lang: "" },
    });
    expect(() => new Function(LOCALE_SCRIPT)()).not.toThrow();
  });

  it("is inlined by the layout, and the layout no longer reads cookies", () => {
    /* Read as source rather than imported: `layout.tsx` is a server
       component with a font loader in it, and importing it here would
       assert on Next's build pipeline rather than on this claim.
       `cookies()` is a dynamic API — one call and the export stops
       building, with an error that names the layout and not the reason. */
    const layout = readFileSync(join(process.cwd(), "src", "app", "layout.tsx"), "utf8");
    expect(layout).toContain("__html: LOCALE_SCRIPT");
    expect(layout).not.toContain("next/headers");
  });
});
