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
        href: "/candidates",
        labelKey: "nav.candidates",
        icon: "cpu",
        descriptionKey: "nav.desc.candidates",
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
      // `/benchmarks`, `/leaderboard` and `/algorithms` were removed in
      // P6, each after the thing that replaced it existed: candidates and
      // the registry moved to `/candidates`, the catalogue of results to
      // `/decisions`, and watching one episode to `/simulate`. What did
      // *not* move — the difficulty curve, the generalization gap over
      // scenario splits, the split badges — was retired with them on
      // purpose: they are claims across scenarios, and HĐ-1.4 scopes a
      // recommendation to one deployment. See the P6 report.
      //
      // `/scenarios` stays. The deployment form still cannot draw
      // obstacles, so this is the only place to build a scenario with
      // them, and removing it would take away a capability rather than
      // move one.
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
/** Pages whose content is a canvas rather than a column of text.
 *
 * A map editor, a simulator and a deployment form are drawing surfaces:
 * more width is more of the thing the page is for. Everywhere else, a
 * measure that runs the full width of a 1920 monitor is a measure
 * nobody's eye can track back to the start of the next line — which is
 * why `main.content` is capped at all.
 *
 * **The list lives here rather than on the pages.** `AppShell` owns
 * `<main>`; the root layout mounts it above every page, so a page has
 * nothing to pass upward. A named constant is also an edit a reviewer
 * sees, where a class sprinkled through each page would not be.
 */
const WIDE_CONTENT_ROUTES = ["/maps", "/simulate", "/deployments"] as const;

/** Whether this path wants the cap lifted.
 *
 * Matched with `isActive`, not with equality, so `/maps/warehouse_a` is
 * as wide as `/maps` — the editor is the same drawing surface either
 * way, and a detail page that suddenly narrowed would be the odd one.
 */
export function wideContent(pathname: string): boolean {
  return WIDE_CONTENT_ROUTES.some((route) => isActive(pathname, route));
}

/**
 * What one crumb shows, given a name the page supplied for its own.
 *
 * Three conditions, and each rules out a way of renaming the wrong
 * thing:
 *
 * - **the last crumb only.** `/decisions/abc` puts `Decisions` first;
 *   naming that one would relabel a section after one of its records.
 * - **only a crumb with no `href`.** Those are the ones `breadcrumbs()`
 *   could not name — the raw path segment. A crumb that has an `href`
 *   is a known route whose label comes from the dictionary.
 * - **only when a name was actually supplied.** `null` while the page's
 *   fetch is in flight, and the id stands until it lands.
 */
export function crumbLabel(
  crumbs: readonly Crumb[],
  index: number,
  named: string | null,
): { labelKey?: string; label?: string } {
  const crumb = crumbs[index];
  if (crumb.href || index !== crumbs.length - 1 || !named) return crumb;
  return { label: named };
}

export function breadcrumbs(pathname: string): Crumb[] {
  const route = matchRoute(pathname);
  if (!route || route.href === "/") return [];

  const crumbs: Crumb[] = [{ labelKey: route.labelKey, href: route.href }];
  const rest = pathname.slice(route.href.length).replace(/^\/+|\/+$/g, "");
  if (rest) crumbs.push({ label: rest.split("/")[0] });
  return crumbs;
}
