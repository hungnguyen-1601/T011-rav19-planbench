"use client";

/** The navigation rail — and, below 900px, the drawer.
 *
 * Purely presentational: pathname, collapsed state and the session all
 * arrive as props. That is not ceremony — it is what lets the component
 * be rendered and asserted on in a test without a router, a store or a
 * DOM, which is the only way the collapsed/expanded difference gets
 * checked at all.
 *
 * The *widths* are not here either. They live in CSS keyed off
 * `<html data-sidebar>`, so a remembered collapse applies before React
 * runs. This component contributes the labels, the tooltips and the
 * `aria-current` — the things CSS cannot know.
 */

import Link from "next/link";

import { Avatar } from "./Avatar";
import { Icon, type IconName } from "./Icon";
import { NAV_SECTIONS, isActive } from "@/lib/navigation";
import type { SessionUser } from "@/lib/auth";
import type { Translator } from "@/lib/i18n";

export function Sidebar({
  pathname,
  collapsed,
  mobileOpen,
  t,
  user,
  onToggleCollapse,
  onNavigate,
}: {
  pathname: string;
  collapsed: boolean;
  mobileOpen: boolean;
  t: Translator["t"];
  user: SessionUser | null;
  onToggleCollapse: () => void;
  /** Called on every link click, so the drawer can close itself. */
  onNavigate: () => void;
}) {
  return (
    <aside id="app-sidebar" className="sidebar" data-open={mobileOpen ? "true" : "false"}>
      <div className="sidebar-brand">
        <span className="sidebar-mark" aria-hidden="true">
          <Icon name="benchmark" size={17} />
        </span>
        <div style={{ minWidth: 0 }}>
          <h1>{t("app.name")}</h1>
          <p className="tagline">{t("app.tagline")}</p>
        </div>
      </div>

      <nav aria-label={t("sidebar.label")}>
        {NAV_SECTIONS.map((section) => (
          <div className="sidebar-section" key={section.titleKey}>
            <p className="sidebar-section-title">{t(section.titleKey)}</p>
            {section.items.map((item) => {
              const label = t(item.labelKey);
              const active = isActive(pathname, item.href);
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  onClick={onNavigate}
                  // Only when collapsed: with the label visible, a
                  // tooltip repeating it is noise, and an aria-label
                  // duplicating it is read twice.
                  aria-label={collapsed ? label : undefined}
                  data-tooltip={collapsed ? label : undefined}
                  data-tooltip-side="right"
                  aria-current={active ? "page" : undefined}
                >
                  <Icon name={item.icon as IconName} />
                  <span className="sidebar-label">{label}</span>
                </Link>
              );
            })}
          </div>
        ))}
      </nav>

      <div className="sidebar-footer">
        {user ? (
          <div className="session-card">
            <Avatar user={user} />
            <div style={{ minWidth: 0 }}>
              <div className="session-name">{user.nickname || user.display_name}</div>
              {user.email ? <div className="muted session-email">{user.email}</div> : null}
            </div>
          </div>
        ) : null}

        <button
          type="button"
          className="icon-button sidebar-toggle"
          onClick={onToggleCollapse}
          aria-label={collapsed ? t("sidebar.expand") : t("sidebar.collapse")}
          aria-expanded={!collapsed}
          data-tooltip={collapsed ? t("sidebar.expand") : t("sidebar.collapse")}
          data-tooltip-side="right"
        >
          <Icon name={collapsed ? "chevronRight" : "chevronLeft"} />
          <span className="sidebar-label">{t("sidebar.collapse")}</span>
        </button>
      </div>
    </aside>
  );
}
