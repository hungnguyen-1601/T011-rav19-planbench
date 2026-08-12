/** The navigation model: one list, used by the sidebar, the title and
 *  the breadcrumb.
 *
 * Data rather than JSX so all three read the same source. When they were
 * separate, a renamed page meant three edits and the breadcrumb was
 * always the one that got missed.
 *
 * Labels are translation *keys*, never text: this module is imported by
 * the server render and by tests, neither of which has a locale.
 */

export interface NavItem {
  href: string;
  labelKey: string;
  icon: string;
  /** Hidden from the sidebar but still resolvable for the title. */
  hidden?: boolean;
  /** Requires a session; shown but marked when signed out. */
  session?: boolean;
}

export interface NavSection {
  titleKey: string;
  items: NavItem[];
}

export const NAV_SECTIONS: readonly NavSection[] = [
  {
    titleKey: "nav.section.workspace",
    items: [
      { href: "/", labelKey: "nav.dashboard", icon: "dashboard" },
      { href: "/maps", labelKey: "nav.maps", icon: "map" },
      { href: "/library", labelKey: "nav.library", icon: "library" },
      { href: "/scenarios", labelKey: "nav.scenarios", icon: "map", session: true },
      { href: "/simulate", labelKey: "nav.simulate", icon: "play" },
    ],
  },
  {
    titleKey: "nav.section.results",
    items: [
      { href: "/decisions", labelKey: "nav.decisions", icon: "benchmark" },
      { href: "/benchmarks", labelKey: "nav.benchmarks", icon: "benchmark" },
      { href: "/leaderboard", labelKey: "nav.leaderboard", icon: "trophy" },
      { href: "/algorithms", labelKey: "nav.algorithms", icon: "cpu" },
      { href: "/models", labelKey: "nav.models", icon: "library", session: true },
      { href: "/agent", labelKey: "nav.agent", icon: "sparkles" },
    ],
  },
  {
    titleKey: "nav.section.account",
    items: [
      { href: "/reviews", labelKey: "nav.reviews", icon: "inbox", session: true },
      { href: "/system", labelKey: "nav.system", icon: "info" },
    ],
  },
];

/** Routes that need a title but no sidebar entry. */
const EXTRA_ROUTES: readonly NavItem[] = [
  { href: "/login", labelKey: "nav.login", icon: "user", hidden: true },
  { href: "/welcome", labelKey: "nav.welcome", icon: "user", hidden: true },
  { href: "/auth/callback", labelKey: "nav.login", icon: "user", hidden: true },
];

export const ALL_ROUTES: readonly NavItem[] = [
  ...NAV_SECTIONS.flatMap((section) => section.items),
  ...EXTRA_ROUTES,
];

/**
 * Is `href` the section the user is in?
 *
 * `/` matches only itself — every path starts with a slash, so a prefix
 * test would light up the dashboard on every page.
 */
export function isActive(pathname: string, href: string): boolean {
  if (href === "/") return pathname === "/";
  return pathname === href || pathname.startsWith(`${href}/`);
}

/** The best-matching route for a path, longest match first. */
export function matchRoute(pathname: string): NavItem | undefined {
  return [...ALL_ROUTES]
    .sort((a, b) => b.href.length - a.href.length)
    .find((item) => isActive(pathname, item.href));
}

/** Translation key for the current page's title. */
export function pageTitleKey(pathname: string): string {
  return matchRoute(pathname)?.labelKey ?? "app.name";
}

export interface Crumb {
  labelKey?: string;
  /** Shown verbatim — an id or a name, which must not be translated. */
  label?: string;
  href?: string;
}

/**
 * Breadcrumb for a path.
 *
 * A single trailing segment that is not a known route is treated as a
 * record id (`/benchmarks/ab12`) and shown verbatim: ids, checksums and
 * user-supplied names must never be run through a dictionary.
 */
export function breadcrumbs(pathname: string): Crumb[] {
  const route = matchRoute(pathname);
  if (!route || route.href === "/") return [];

  const crumbs: Crumb[] = [{ labelKey: route.labelKey, href: route.href }];
  const rest = pathname.slice(route.href.length).replace(/^\/+|\/+$/g, "");
  if (rest) crumbs.push({ label: rest.split("/")[0] });
  return crumbs;
}
