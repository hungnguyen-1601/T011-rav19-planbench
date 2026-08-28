/** The frame's two promises: it is bilingual, and it does not need the
 *  API to be up.
 *
 * Both fail quietly. A key present in one locale renders as English on a
 * Vietnamese screen and looks like a translation nobody got to; a guide
 * that waits on `/health` looks fine on a developer's machine and is
 * blank on the one where somebody is trying to find out what broke.
 */

import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import en from "../../lib/i18n/locales/en.json";
import vi from "../../lib/i18n/locales/vi.json";

const web = join(__dirname, "..", "..", "..");
const read = (relative: string) => readFileSync(join(web, relative), "utf-8");

const SOURCES = [
  "src/app/guide/GuideLanding.tsx",
  "src/app/guide/GuideRail.tsx",
  "src/app/guide/[slug]/GuideArticle.tsx",
  "src/components/guide/GuideSidebar.tsx",
  "src/components/guide/GuideSearch.tsx",
  "src/components/guide/ArticleToc.tsx",
  "src/components/guide/PrevNext.tsx",
  "src/components/guide/AppLink.tsx",
  "src/components/guide/CapabilityNotice.tsx",
];

describe("every string the frame shows exists in both languages (T3)", () => {
  /** `t("…")` with a literal key. Template keys — `guide.group.${g}` —
   *  are checked separately below, since a regex cannot expand them. */
  const literal = (source: string) =>
    [...source.matchAll(/\bt\("([a-zA-Z0-9_.]+)"/g)].map((match) => match[1]);

  it("declares each key in en.json and vi.json alike", () => {
    const missing: string[] = [];
    for (const file of SOURCES) {
      for (const key of literal(read(file))) {
        if (!(key in en)) missing.push(`en: ${key}`);
        if (!(key in vi)) missing.push(`vi: ${key}`);
      }
    }
    expect(missing).toEqual([]);
  });

  it("declares the group headings the rail builds by hand", () => {
    for (const group of ["overview", "operating", "results", "advanced", "reference"]) {
      expect(`guide.group.${group}` in en).toBe(true);
      expect(`guide.group.${group}` in vi).toBe(true);
    }
  });

  it("keeps the two dictionaries the same size", () => {
    /* A key added to one file only is the whole failure mode; comparing
       the sets rather than the counts names which one. */
    expect(Object.keys(en).sort()).toEqual(Object.keys(vi).sort());
  });
});

describe("the guide reads with the API down (T11)", () => {
  const context = read("src/lib/guideContext.ts");

  it("asks for the two facts independently", () => {
    /* `Promise.all` rejects as a unit: one failure would erase the other
       answer as well, so a stopped agent service would also cost the
       version number. */
    expect(context).toContain("Promise.allSettled");
    expect(context).not.toContain("Promise.all(");
  });

  it("has an answer for every field when nothing is known", () => {
    /* Empty string and false, never the strings "unknown" or "error":
       the callers hide a line they have no fact for. */
    expect(context).toContain('const [version, setVersion] = useState("")');
    expect(context).toContain("const [aiReady, setAiReady] = useState(false)");
  });

  it("never blocks the page on the answer", () => {
    /* No throw, and no branch that returns early instead of a context.
       Whatever happens, the hook returns an object and the article
       renders. */
    expect(context).not.toContain("throw");
  });

  it("hides the reader's own line rather than guessing at it", () => {
    /* Signed out is not the same as "not allowed", and a grey "no" to
       somebody who never signed in reads as a refusal. */
    const notice = read("src/components/guide/CapabilityNotice.tsx");
    expect(notice).toContain("if (loading) return null;");
    expect(notice).toContain("if (!signedIn)");
  });

  it("puts the prose's rule and the reader's fact in different files", () => {
    /* The article says a capability is required; this says whether you
       have it. Merging them is how "administrators only" ends up written
       into prose that will be wrong when capability packages land. */
    const notice = read("src/components/guide/CapabilityNotice.tsx");
    expect(notice).toContain("canImportPlugin");
    expect(context).toContain("session?.user.is_admin");
  });
});
