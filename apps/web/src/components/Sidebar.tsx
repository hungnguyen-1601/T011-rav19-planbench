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
import {
  NAV_SECTIONS,
  NAV_UTILITY,
  isActive,
  type NavItem,
} from "@/lib/navigation";
import type { SessionUser } from "@/lib/auth";
import type { Translator } from "@/lib/i18n";

/** The entries this reader is offered.
 *
 * An entry naming a capability the reader does not hold is dropped.
 * Cosmetic and stated as such — the API refuses the request either way —
 * but a rail that lists a page whose every control answers 403 is
 * advertising a door most of the people reading it cannot open.
 *
 * Filtered on the capability rather than on a role: the server sends
 * what this account may do, and matching that exactly means the rail
 * cannot drift from it when a capability moves between packages.
 */
function visible(items: readonly NavItem[], user: SessionUser | null): NavItem[] {
  return items.filter(
    (item) => !item.capability || Boolean(user?.capabilities?.includes(item.capability)),
  );
}

/** One row of the rail.
 *
 * Extracted when the utility slot arrived: the guide's entry has to look
 * and behave exactly like every other row — same tooltip rules when
 * collapsed, same `aria-current` — and a second copy of this markup is a
 * second place for those rules to drift.
 */
function NavEntry({
  item,
  collapsed,
  pathname,
  t,
  onNavigate,
}: {
  item: NavItem;
  collapsed: boolean;
  pathname: string;
  t: Translator["t"];
  onNavigate: () => void;
}) {
  const label = t(item.labelKey);
  const description = item.descriptionKey ? t(item.descriptionKey) : null;
  const active = isActive(pathname, item.href);
  return (
    <Link
      key={item.href}
      href={item.href}
      onClick={onNavigate}
      // Collapsed, the tooltip carries the description too —
      // it is the only surface left, and a rail of icons
      // with nothing but names is what the descriptions were
      // added to fix. Expanded, the label is already on
      // screen so repeating it in a tooltip is noise and
      // repeating it in an aria-label is read twice.
      aria-label={collapsed ? label : undefined}
      // Expanded, the description is the link's `title`;
      // collapsed, the tooltip carries both because the
      // label is not on screen either.
      title={collapsed ? undefined : (description ?? undefined)}
      data-tooltip={
        collapsed
          ? description
            ? `${label} - ${description}`
            : label
          : undefined
      }
      data-tooltip-side="right"
      aria-current={active ? "page" : undefined}
    >
      <Icon name={item.icon as IconName} />
      {/* The description moved into `title`. Twelve entries
                    × a sentence each turned the rail into a column of
                    prose whose last item fell below the fold; the
                    sentences are read once and then never again, which
                    is what a tooltip is for. Nothing is lost — the
                    keys and the strings all stay. */}
      <span className="sidebar-label">{label}</span>
      {item.legacy ? (
        <span className="badge muted-badge sidebar-legacy">
          {t("nav.legacy")}
        </span>
      ) : null}
    </Link>
  );
}

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
    <aside
      id="app-sidebar"
      className="sidebar"
      data-open={mobileOpen ? "true" : "false"}
    >
      <div className="sidebar-brand">
        <span className="sidebar-mark" aria-hidden="true">
          <Icon name="benchmark" size={17} />
        </span>
        <div style={{ minWidth: 0 }}>
          {/* No tagline. "AMR/AGV planning benchmark — simulation only"
              is a sentence about the product, read once and then read
              past forever, sitting at the top of the one surface a
              reader uses on every visit. It belongs on `/system`. */}
          <h1>{t("app.name")}</h1>
        </div>
      </div>

      <nav aria-label={t("sidebar.label")}>
        {NAV_SECTIONS.map((section) => {
          const items = visible(section.items, user);
          // A heading is a claim that there is something under it. On a
          // deployment where nobody holds the administrator package,
          // every entry in that section is hidden, and the heading alone
          // would advertise a set with no members.
          if (items.length === 0) return null;
          return (
            <div className="sidebar-section" key={section.titleKey}>
              <p className="sidebar-section-title">{t(section.titleKey)}</p>
              {items.map((item) => (
                <NavEntry
                  key={item.href}
                  item={item}
                  collapsed={collapsed}
                  pathname={pathname}
                  t={t}
                  onNavigate={onNavigate}
                />
              ))}
            </div>
          );
        })}

        {/* No heading. The guide is neither a place to work nor part of
            an account, and a heading is a claim about a set — spending
            one on a single row makes the reader parse a category to
            learn a fact about one entry. A rule says the same thing.

            Outside the loop above, so the rule that hides an empty
            section does not reach it: this row has no capability behind
            it and is never empty. */}
        <div className="sidebar-section sidebar-utility">
          {NAV_UTILITY.map((item) => (
            <NavEntry
              key={item.href}
              item={item}
              collapsed={collapsed}
              pathname={pathname}
              t={t}
              onNavigate={onNavigate}
            />
          ))}
        </div>
      </nav>

      <div className="sidebar-footer">
        {user ? (
          <div className="session-card">
            <Avatar user={user} />
            <div style={{ minWidth: 0 }}>
              <div className="session-name">
                {user.nickname || user.display_name}
              </div>
              {user.email ? (
                <div className="muted session-email">{user.email}</div>
              ) : null}
            </div>
          </div>
        ) : null}

        <button
          type="button"
          className="icon-button sidebar-toggle"
          onClick={onToggleCollapse}
          aria-label={collapsed ? t("sidebar.expand") : t("sidebar.collapse")}
          aria-expanded={!collapsed}
          // The native tooltip, not `data-tooltip`, and the reason is
          // that this button is the one place the custom one could not
          // work. `[data-tooltip-side="right"]::after` is laid out 8px
          // past the button's right edge; the button spans the full
          // content width of `.sidebar`, whose padding is 12px and
          // which is a scroll container (`overflow-y: auto`, so both
          // axes clip). The bubble therefore began 8px into a 12px gap
          // and was cut off 4px later — a hairline of its left border
          // and background against the rail's edge, appearing on hover
          // and reading as a stray frame rather than as a tooltip.
          //
          // The nav links get away with it because they only carry a
          // tooltip while collapsed, where the same clipping applies —
          // see the note in the report; here the button carried one in
          // both states, so the sliver was on every hover.
          //
          // Nothing about keyboard access changes: `aria-label` is
          // still the accessible name and the global `:focus-visible`
          // outline is untouched. As with the links, the tooltip is
          // dropped while expanded, where the label is already on
          // screen.
          title={collapsed ? t("sidebar.expand") : undefined}
        >
          <Icon name={collapsed ? "chevronRight" : "chevronLeft"} />
          <span className="sidebar-label">{t("sidebar.collapse")}</span>
        </button>
      </div>
    </aside>
  );
}
