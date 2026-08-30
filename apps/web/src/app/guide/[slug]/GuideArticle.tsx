"use client";

/** The article body: pick the module for the reader's language, render it.
 *
 * Client, and deliberately thin. The route above is a server component
 * because `generateStaticParams` has to be — the export needs the list of
 * pages at build time. The language, though, lives in a cookie the static
 * export has no request to read, so choosing between `vi` and `en` can
 * only happen here.
 *
 * Switching language does **not** navigate. The slug is language-neutral
 * and section ids are identical across both files, so the URL and the
 * hash a reader is standing on stay exactly where they were; only the
 * module changes.
 *
 * It sits beside the route rather than in `components/` because that is
 * how a thin server page states it delegates its text: the page has no
 * strings of its own, and the check that every page is translated reads
 * a co-located `./Component` as the page's answer.
 */

import { useTranslation } from "@/lib/i18n";
import { GUIDE_MODULES } from "../../../../content/guide/modules";

export function GuideArticle({ slug }: { slug: string }) {
  const { locale } = useTranslation();
  const modules = GUIDE_MODULES[locale] as Record<string, React.ComponentType>;
  const Article = modules[slug];
  if (!Article) return null;
  return (
    <article className="guide-article">
      <Article />
    </article>
  );
}
