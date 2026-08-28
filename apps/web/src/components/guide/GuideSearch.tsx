"use client";

/** Find an article, or a heading inside one.
 *
 * The box says **"Find an article or heading"** rather than "Search the
 * guide", and the difference is not modesty: a box that says "search"
 * is read as searching the text, and a reader who types a phrase from
 * the middle of a paragraph and gets nothing concludes the guide does
 * not cover it. Naming the scope is what keeps a true empty result from
 * reading as a false one.
 */

import Link from "next/link";
import { useMemo, useState } from "react";

import { GUIDE } from "../../../content/guide/manifest";
import { useTranslation } from "@/lib/i18n";
import { search, type SearchTarget } from "@/lib/guideSearch";

export function GuideSearch() {
  const { locale, t } = useTranslation();
  const [query, setQuery] = useState("");

  const targets = useMemo<SearchTarget[]>(
    () =>
      GUIDE.flatMap((article) => [
        { href: `/guide/${article.slug}`, title: article.title[locale] },
        ...article.sections.map((section) => ({
          href: `/guide/${article.slug}#${section.id}`,
          title: section.title[locale],
          context: article.title[locale],
        })),
        ...(article.tabs ?? []).map((tab) => ({
          href: `/guide/${article.slug}#${tab.id}`,
          title: tab.title[locale],
          context: article.title[locale],
        })),
      ]),
    [locale],
  );

  const results = query ? search(targets, query) : [];

  return (
    <div className="guide-search">
      <input
        type="search"
        value={query}
        onChange={(event) => setQuery(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === "Escape") setQuery("");
        }}
        placeholder={t("guide.search.placeholder")}
        aria-label={t("guide.search.placeholder")}
      />
      {query ? (
        results.length > 0 ? (
          <ul className="guide-search-results">
            {results.map((result) => (
              <li key={result.href}>
                <Link href={result.href}>
                  {result.title}
                  {result.context ? <span className="muted"> · {result.context}</span> : null}
                </Link>
              </li>
            ))}
          </ul>
        ) : (
          <p className="guide-search-empty muted">{t("guide.search.noMatch")}</p>
        )
      ) : null}
    </div>
  );
}
