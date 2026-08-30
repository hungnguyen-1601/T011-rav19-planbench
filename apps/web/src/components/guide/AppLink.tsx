"use client";

/** A link out of the guide and into the screen being described.
 *
 * Written as `<AppLink href="/deployments" />` with no text: the label
 * is the app's own name for that page, read from the navigation model,
 * so renaming a page renames every mention of it in both languages at
 * once. Passing text here would create a second name for the same
 * screen — which is the thing the reader then has to reconcile.
 */

import Link from "next/link";

import { matchRoute } from "@/lib/navigation";
import { useTranslation } from "@/lib/i18n";

export function AppLink({ href }: { href: string }) {
  const { t } = useTranslation();
  const route = matchRoute(href);
  return (
    <Link className="guide-applink" href={href}>
      {t("guide.openIn", { page: route ? t(route.labelKey) : href })}
    </Link>
  );
}
