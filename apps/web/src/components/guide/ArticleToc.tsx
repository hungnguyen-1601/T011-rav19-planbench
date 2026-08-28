"use client";

/** The open article's own sections, as links.
 *
 * Built from the manifest rather than from the rendered DOM. Walking the
 * headings would work and would tie the contents to whether the article
 * has finished loading — this way the outline is there while the chunk
 * is still arriving, and a test can hold the manifest and the file to
 * each other.
 */

import type { GuideArticleMeta } from "../../../content/guide/manifest";
import { useTranslation } from "@/lib/i18n";

export function ArticleToc({ article }: { article: GuideArticleMeta }) {
  const { locale, t } = useTranslation();
  if (article.sections.length < 2) return null;
  return (
    <nav className="guide-toc" aria-label={t("guide.toc")}>
      <h2>{t("guide.toc")}</h2>
      <ul>
        {article.sections.map((section) => (
          <li key={section.id}>
            <a href={`#${section.id}`}>{section.title[locale]}</a>
          </li>
        ))}
      </ul>
    </nav>
  );
}
