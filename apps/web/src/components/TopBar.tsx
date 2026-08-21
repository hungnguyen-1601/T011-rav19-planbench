"use client";

/** The bar above every page: where you are, and the controls that apply
 *  everywhere.
 *
 * Deliberately one row of 34px controls — the brief asked for it not to
 * eat the screen, and a page title plus four buttons does not need two.
 *
 * The hamburger only exists below 900px (CSS decides, via `.mobile-only`)
 * because above that the sidebar is always present and a button to
 * reveal it would do nothing.
 */

import Link from "next/link";

import { Icon } from "./Icon";
import { LanguageSwitcher } from "./LanguageSwitcher";
import { NotificationButton } from "./NotificationButton";
import { ThemeSwitcher } from "./ThemeSwitcher";
import { UserMenu } from "./UserMenu";
import type { SessionUser } from "@/lib/auth";
import type { Translator } from "@/lib/i18n";
import { useCrumbOverride } from "@/lib/crumbOverride";
import { crumbLabel } from "@/lib/navigation";
import { breadcrumbs, pageTitleKey } from "@/lib/navigation";

export function TopBar({
  pathname,
  t,
  user,
  pendingReviews,
  onOpenSidebar,
}: {
  pathname: string;
  t: Translator["t"];
  user: SessionUser | null;
  pendingReviews: number;
  onOpenSidebar: () => void;
}) {
  const crumbs = breadcrumbs(pathname);
  // A page may name its own last crumb — `/decisions/20750b0d9dbe` is
  // the `sudden_stop_v5` comparison, which the path cannot know and the
  // page fetched. Only the last crumb, and only when it is the raw
  // segment `breadcrumbs()` could not name.
  const named = useCrumbOverride();

  return (
    <header className="topbar">
      <button
        type="button"
        className="icon-button mobile-only"
        onClick={onOpenSidebar}
        aria-label={t("sidebar.open")}
        aria-controls="app-sidebar"
      >
        <Icon name="menu" />
      </button>

      <div className="topbar-title">
        <h2>{t(pageTitleKey(pathname))}</h2>
        {crumbs.length > 1 ? (
          <nav className="breadcrumb" aria-label="Breadcrumb">
            {crumbs.map((crumb, index) => (
              <span key={`${crumb.href ?? crumb.label}-${index}`}>
                {index > 0 ? <span aria-hidden="true">/ </span> : null}
                {crumb.href ? (
                  <Link href={crumb.href}>{crumb.labelKey ? t(crumb.labelKey) : crumb.label}</Link>
                ) : (
                  // Ids and names are shown verbatim — never translated.
                  // A page-supplied name *replaces* the id rather than
                  // translating it; the two are different claims, and
                  // the fallback is still the id. Which crumb may be
                  // replaced is decided in `crumbLabel`.
                  <span>{crumbLabel(crumbs, index, named).label}</span>
                )}
              </span>
            ))}
          </nav>
        ) : null}
      </div>

      <div className="topbar-actions">
        <LanguageSwitcher />
        <ThemeSwitcher />
        {user ? <NotificationButton pending={pendingReviews} /> : null}
        <UserMenu user={user} />
      </div>
    </header>
  );
}
