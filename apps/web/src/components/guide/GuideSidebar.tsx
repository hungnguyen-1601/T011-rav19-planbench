"use client";

/** The guide's own rail: every article, grouped, with the open one marked.
 *
 * A second rail rather than more entries on the app's: the app's rail
 * names places to *work*, and eleven articles under one of them would
 * bury the four pages somebody uses every day. This one only exists on
 * `/guide`, where every entry is the thing the reader came for.
 *
 * Titles come from the manifest rather than the dictionary — they are
 * content, and content is bilingual in the file that holds it.
 */

import Link from "next/link";

import { GUIDE, type GuideGroup } from "../../../content/guide/manifest";
import { useTranslation } from "@/lib/i18n";

/** Group order is reading order: what the system is, then how to run it,
 *  then how to read what it says, then the things most readers never
 *  need. */
const GROUPS: readonly GuideGroup[] = [
  "overview",
  "operating",
  "results",
  "advanced",
  "reference",
];

export function GuideSidebar({ slug }: { slug: string | null }) {
  const { locale, t } = useTranslation();
  return (
    <nav className="guide-rail" aria-label={t("guide.rail")}>
      {GROUPS.map((group) => {
        const articles = GUIDE.filter(
          (article) => article.group === group,
        ).sort((a, b) => a.order - b.order);
        if (articles.length === 0) return null;
        return (
          <div key={group} className="guide-rail-group">
            <h2 className="guide-rail-title">{t(`guide.group.${group}`)}</h2>
            <ul>
              {articles.map((article) => (
                <li key={article.slug}>
                  <Link
                    href={`/guide/${article.slug}`}
                    aria-current={article.slug === slug ? "page" : undefined}
                  >
                    {article.title[locale]}
                  </Link>
                </li>
              ))}
            </ul>
          </div>
        );
      })}
    </nav>
  );
}
