"use client";

/** Where the reader goes when they finish this one.
 *
 * The order is the manifest's, across group boundaries: the guide has a
 * reading order and somebody working through it should not have to
 * return to the rail to find out what follows. Both ends are absent
 * rather than disabled — a dead control that looks live is worse than no
 * control.
 */

import Link from "next/link";

import { GUIDE } from "../../../content/guide/manifest";
import { useTranslation } from "@/lib/i18n";

const ORDERED = [...GUIDE].sort((a, b) => a.order - b.order);

export function PrevNext({ slug }: { slug: string }) {
  const { locale, t } = useTranslation();
  const index = ORDERED.findIndex((article) => article.slug === slug);
  if (index < 0) return null;
  const previous = ORDERED[index - 1];
  const next = ORDERED[index + 1];
  if (!previous && !next) return null;
  return (
    <nav className="guide-prevnext" aria-label={t("guide.prevNext")}>
      {previous ? (
        <Link href={`/guide/${previous.slug}`} className="guide-prev">
          <span>{t("guide.prev")}</span>
          <strong>{previous.title[locale]}</strong>
        </Link>
      ) : (
        <span />
      )}
      {next ? (
        <Link href={`/guide/${next.slug}`} className="guide-next">
          <span>{t("guide.next")}</span>
          <strong>{next.title[locale]}</strong>
        </Link>
      ) : null}
    </nav>
  );
}
