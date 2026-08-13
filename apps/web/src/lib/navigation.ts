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
  /** One line saying what this page is *for*.
   *
   * Added when the sidebar was regrouped: twelve entries with nothing
   * but names left a reader unable to tell that `Benchmarks` and
   * `Decisions` answer different questions, or that `Scenarios` and
   * `Deployments` describe the same thing twice. That was the largest
   * cost of running two flows side by side and none of it was in the
   * code.
   *
   * Optional in the type and required by a test: the routes with no
   * sidebar entry (`/login`, `/welcome`) have nothing to describe.
   */
  descriptionKey?: string;
  /** Hidden from the sidebar but still resolvable for the title. */
  hidden?: boolean;
  /** Requires a session; shown but marked when signed out. */
  session?: boolean;
}

export interface NavSection {
  titleKey: string;
  items: NavItem[];
}

/** Grouped by **what the reader is doing**, not by which system produced
 *  the screen.
 *
 * The previous grouping (Workspace / Results / Account) split by where a
 * page came from, so the two flows ended up interleaved inside one
 * heading — `Deployments` and `Decisions` sitting between `Benchmarks`
 * and `Leaderboard`, with nothing saying which was replacing which.
 *
 * `nav.section.retiring` is deliberately visible rather than tidied
 * away. Those pages still work and are still the only way to do some
 * things; saying so is more use to a reader than a sidebar that quietly
 * lists a replacement beside the thing it replaces.
 */
export const NAV_SECTIONS: readonly NavSection[] = [
  {
    titleKey: "nav.section.doing",
    items: [
      {
        href: "/",
        labelKey: "nav.dashboard",
        icon: "dashboard",
        descriptionKey: "nav.desc.dashboard",
      },
      {
        href: "/deployments",
        labelKey: "nav.deployments",
        icon: "map",
        descriptionKey: "nav.desc.deployments",
      },
      {
        href: "/simulate",
        labelKey: "nav.simulate",
        icon: "play",
        descriptionKey: "nav.desc.simulate",
      },
      {
        href: "/decisions",
        labelKey: "nav.decisions",
        icon: "benchmark",
        descriptionKey: "nav.desc.decisions",
      },
    ],
  },
  {
    titleKey: "nav.section.materials",
    items: [
      { href: "/maps", labelKey: "nav.maps", icon: "map", descriptionKey: "nav.desc.maps" },
      {
        href: "/library",
        labelKey: "nav.library",
        icon: "library",
        descriptionKey: "nav.desc.library",
      },
      {
        href: "/algorithms",
        labelKey: "nav.algorithms",
        icon: "cpu",
        descriptionKey: "nav.desc.algorithms",
      },
      {
        href: "/models",
        labelKey: "nav.models",
        icon: "library",
        session: true,
        descriptionKey: "nav.desc.models",
      },
    ],
  },
  {
    titleKey: "nav.section.retiring",
    items: [
      {
        href: "/benchmarks",
        labelKey: "nav.benchmarks",
        icon: "benchmark",
        descriptionKey: "nav.desc.benchmarks",
      },
      {
        href: "/leaderboard",
        labelKey: "nav.leaderboard",
        icon: "trophy",
        descriptionKey: "nav.desc.leaderboard",
      },
      {
        href: "/scenarios",
        labelKey: "nav.scenarios",
        icon: "map",
        session: true,
        descriptionKey: "nav.desc.scenarios",
      },
    ],
  },
  {
    titleKey: "nav.section.account",
    items: [
      { href: "/agent", labelKey: "nav.agent", icon: "sparkles", descriptionKey: "nav.desc.agent" },
      {
        href: "/reviews",
        labelKey: "nav.reviews",
        icon: "inbox",
        session: true,
        descriptionKey: "nav.desc.reviews",
      },
      { href: "/system", labelKey: "nav.system", icon: "info", descriptionKey: "nav.desc.system" },
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
