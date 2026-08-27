/** The guide's table of contents — one source, four readers.
 *
 * `generateStaticParams`, the sidebar, the search and prev/next all read
 * this. The alternative was frontmatter in each `.mdx`, which `@next/mdx`
 * does not parse without two more plugins, and which would force the
 * sidebar to import all eleven modules — that is, to pull every article's
 * prose into the landing page — just to learn their titles.
 *
 * **Section ids are written, never derived from the title.** Slugifying a
 * heading gives `#khai-deployment` in Vietnamese and `#declare-a-deployment`
 * in English: two ids for one place, so a link somebody pasted breaks for a
 * reader in the other language. The id is the same in both files; only the
 * title differs. `/guide/gates#g2` therefore means the same thing to
 * everyone.
 */

import type { Locale } from "@/lib/i18n/shared";

/** A string that exists in both languages. Titles only — prose is MDX. */
export type Bilingual = Record<Locale, string>;

export interface GuideSection {
  /** Written by the author, identical across locales. */
  id: string;
  title: Bilingual;
}

/** A group heading on the rail. Not a URL segment: the IA is flat. */
export type GuideGroup = "overview" | "operating" | "results" | "advanced" | "reference";

export interface GuideArticleMeta {
  slug: string;
  group: GuideGroup;
  /** Reading order inside the group, and the order prev/next walks. */
  order: number;
  title: Bilingual;
  /** Anchors inside the article. Pinned against the body by a test. */
  sections: GuideSection[];
  /** Tabs, when the parts genuinely answer one question side by side.
   *
   * Absent for an article read top to bottom. A hidden tab panel is
   * `hidden`, which browser find skips — so a sequence, where the reader
   * has to see that step five exists while reading step two, is never
   * tabbed. */
  tabs?: GuideSection[];
}

export const GUIDE: readonly GuideArticleMeta[] = [
  {
    slug: "overview",
    group: "overview",
    order: 10,
    title: { vi: "Tổng quan", en: "Overview" },
    sections: [
      { id: "he-thong-lam-gi", title: { vi: "Hệ thống làm gì", en: "What this is for" } },
    ],
  },
];

export const GUIDE_SLUGS: readonly string[] = GUIDE.map((article) => article.slug);

export function articleBySlug(slug: string): GuideArticleMeta | undefined {
  return GUIDE.find((article) => article.slug === slug);
}
