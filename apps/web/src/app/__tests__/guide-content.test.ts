/** What every article has to keep true, checked on the files themselves.
 *
 * These are the failures nothing else catches. A link into a heading
 * that no longer exists still renders: the article opens, the first tab
 * shows, and only the person who pasted the link ever finds out. A
 * section added to one language and not the other looks finished in the
 * language its author reads. A sentence naming a role is correct until
 * the day capability packages land and then is wrong in two languages.
 */

import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import { GUIDE, GUIDE_SLUGS, articleBySlug } from "../../../content/guide/manifest";
import { ALL_ROUTES } from "@/lib/navigation";

const CONTENT = join(__dirname, "..", "..", "..", "content", "guide");
const LOCALES = ["vi", "en"] as const;

function articleSource(locale: string, slug: string): string {
  return readFileSync(join(CONTENT, locale, `${slug}.mdx`), "utf-8");
}

function sectionIds(source: string): string[] {
  return [...source.matchAll(/<Section\s+id="([^"]+)"/g)].map((match) => match[1]);
}

/** Every internal link an article makes, however it is written. */
function links(source: string): string[] {
  return [
    ...[...source.matchAll(/\]\((\/[^)\s]+)\)/g)].map((match) => match[1]),
    ...[...source.matchAll(/<AppLink\s+href="([^"]+)"/g)].map((match) => match[1]),
  ];
}

describe("no article links at something that is not there (T1)", () => {
  it("names only slugs the manifest has", () => {
    const broken: string[] = [];
    for (const locale of LOCALES) {
      for (const slug of GUIDE_SLUGS) {
        for (const href of links(articleSource(locale, slug))) {
          const guide = /^\/guide\/([^#/]+)/.exec(href);
          if (guide && !GUIDE_SLUGS.includes(guide[1])) broken.push(`${locale}/${slug}: ${href}`);
        }
      }
    }
    expect(broken).toEqual([]);
  });

  it("names only anchors the target article declares", () => {
    /* The quiet one. `/guide/gates#g-2` opens the article and shows the
       first tab, so the page looks right and the link is still wrong. */
    const broken: string[] = [];
    for (const locale of LOCALES) {
      for (const slug of GUIDE_SLUGS) {
        for (const href of links(articleSource(locale, slug))) {
          const match = /^\/guide\/([^#/]+)#(.+)$/.exec(href);
          if (!match) continue;
          const target = articleBySlug(match[1]);
          const anchors = [...(target?.sections ?? []), ...(target?.tabs ?? [])].map((s) => s.id);
          if (!anchors.includes(match[2])) broken.push(`${locale}/${slug}: ${href}`);
        }
      }
    }
    expect(broken).toEqual([]);
  });

  it("names only app routes that exist", () => {
    const known = new Set(ALL_ROUTES.map((route) => route.href));
    const broken: string[] = [];
    for (const locale of LOCALES) {
      for (const slug of GUIDE_SLUGS) {
        for (const href of links(articleSource(locale, slug))) {
          if (href.startsWith("/guide")) continue;
          if (!known.has(href.split("#")[0])) broken.push(`${locale}/${slug}: ${href}`);
        }
      }
    }
    expect(broken).toEqual([]);
  });

  it("links to the same places in both languages", () => {
    /* A link added while writing one language and forgotten in the
       other is a reader in that language never learning the page
       exists. */
    for (const slug of GUIDE_SLUGS) {
      expect(links(articleSource("vi", slug)).sort()).toEqual(
        links(articleSource("en", slug)).sort(),
      );
    }
  });
});

describe("the two languages stay the same guide (T2)", () => {
  it("has the same files on both sides", () => {
    const files = (locale: string) => readdirSync(join(CONTENT, locale)).sort();
    expect(files("vi")).toEqual(files("en"));
    expect(files("vi")).toEqual(GUIDE_SLUGS.map((slug) => `${slug}.mdx`).sort());
  });

  it("has the same section ids, in the same order, in both", () => {
    for (const slug of GUIDE_SLUGS) {
      expect(sectionIds(articleSource("vi", slug))).toEqual(
        sectionIds(articleSource("en", slug)),
      );
    }
  });
});

describe("the manifest and the prose describe one article (T5)", () => {
  it("declares every section the file has, and no others", () => {
    for (const article of GUIDE) {
      for (const locale of LOCALES) {
        expect(sectionIds(articleSource(locale, article.slug))).toEqual(
          article.sections.map((section) => section.id),
        );
      }
    }
  });

  it("writes each section exactly once", () => {
    /* Two `<Section id="x">` in one file makes `#x` mean two places and
       the outline link land on whichever the browser sees first. */
    for (const article of GUIDE) {
      for (const locale of LOCALES) {
        const ids = sectionIds(articleSource(locale, article.slug));
        expect(new Set(ids).size).toBe(ids.length);
      }
    }
  });

  it("gives a tabbed article one panel per declared tab", () => {
    for (const article of GUIDE) {
      if (!article.tabs) continue;
      for (const locale of LOCALES) {
        const source = articleSource(locale, article.slug);
        expect(source).toContain(`<GuideTabs slug="${article.slug}">`);
        /* Panels are positional — the nth child is the nth tab — so a
           count that disagrees silently shifts every panel after it. */
        const panels = [...source.matchAll(/^<div>$/gm)].length;
        expect(panels).toBe(article.tabs.length);
      }
    }
  });
});

describe("no article states a permission in its own words (T4)", () => {
  it("names capabilities, never roles", () => {
    /* `is_admin` is what the server checks *today*. An article saying
       "administrators only" is true today, false when capability
       packages land, and wrong in two languages at once. The rule
       belongs to prose; who satisfies it belongs to a component that
       reads the session. */
    const forbidden = [/is_admin/, /chỉ admin/i, /admin only/i, /administrators only/i, /quản trị viên mới/i];
    const offences: string[] = [];
    for (const locale of LOCALES) {
      for (const slug of GUIDE_SLUGS) {
        const source = articleSource(locale, slug);
        for (const pattern of forbidden) {
          if (pattern.test(source)) offences.push(`${locale}/${slug}: ${pattern}`);
        }
      }
    }
    expect(offences).toEqual([]);
  });
});

describe("the two operating articles do not become one (T10)", () => {
  /* `operation` says what to do and in what order; `pages` says what a
     screen holds. Left unguarded they converge: a step grows a table of
     fields, a screen grows a sentence about what to do next, and the
     reader ends up with two half-answers that have to be reconciled.

     Only half of this is checkable. That one article does not *repeat*
     another is a judgement, and pretending a test settles it would be
     worse than saying so — that half is a review item. What a test can
     hold is the shape: every step hands off exactly once, and the
     reference never narrates a sequence. */

  it("gives every step exactly one hand-off into the screen reference", () => {
    for (const locale of LOCALES) {
      const source = articleSource(locale, "operation");
      const steps = source.split(/<Section\s+id="/).slice(1);
      expect(steps).toHaveLength(articleBySlug("operation")!.sections.length);
      for (const step of steps) {
        const handoffs = [...step.matchAll(/\]\(\/guide\/pages#[^)]+\)/g)];
        expect(handoffs).toHaveLength(1);
      }
    }
  });

  it("keeps process narration out of the screen reference", () => {
    /* "First…", "next step" — a reference read by somebody who jumped
       straight to one screen must not assume they arrived in order. */
    const narration = [/trước tiên/i, /tiếp theo/i, /bước tiếp/i, /\bfirst,/i, /\bnext step\b/i];
    const offences: string[] = [];
    for (const locale of LOCALES) {
      const source = articleSource(locale, "pages");
      for (const pattern of narration) {
        if (pattern.test(source)) offences.push(`${locale}/pages: ${pattern}`);
      }
    }
    expect(offences).toEqual([]);
  });
});
