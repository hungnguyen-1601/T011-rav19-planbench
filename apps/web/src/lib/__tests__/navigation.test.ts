/** The nav model: what is active, what the page is called, breadcrumbs.
 *
 * One list feeds the sidebar, the top-bar title and the breadcrumb. If
 * they disagree the reader is told two different things about where they
 * are, so the agreement is what is tested here.
 */

import { describe, expect, it } from "vitest";

import { hasIcon } from "@/components/Icon";
import {
  ALL_ROUTES,
  NAV_SECTIONS,
  breadcrumbs,
  crumbLabel,
  isActive,
  matchRoute,
  pageTitleKey,
  wideContent,
} from "@/lib/navigation";
import { DICTIONARIES } from "@/lib/i18n";

describe("the model itself", () => {
  it("labels every route with a key that exists in both languages", () => {
    for (const item of ALL_ROUTES) {
      expect(DICTIONARIES.en[item.labelKey], item.href).toBeTruthy();
      expect(DICTIONARIES.vi[item.labelKey], item.href).toBeTruthy();
    }
  });

  it("titles every section with a key that exists", () => {
    for (const section of NAV_SECTIONS) {
      expect(DICTIONARIES.en[section.titleKey]).toBeTruthy();
      expect(DICTIONARIES.vi[section.titleKey]).toBeTruthy();
    }
  });

  it("names only icons that can actually be drawn", () => {
    // A typo here renders an empty <svg>, which looks like a CSS bug.
    for (const item of ALL_ROUTES) {
      expect(hasIcon(item.icon), `${item.href} -> ${item.icon}`).toBe(true);
    }
  });

  it("has no duplicate hrefs", () => {
    const hrefs = ALL_ROUTES.map((item) => item.href);
    expect(new Set(hrefs).size).toBe(hrefs.length);
  });
});

describe("isActive", () => {
  it("matches the exact page", () => {
    expect(isActive("/decisions", "/decisions")).toBe(true);
  });

  it("matches a child page", () => {
    expect(isActive("/decisions/ab12", "/decisions")).toBe(true);
  });

  it("does not match a different section", () => {
    expect(isActive("/leaderboard", "/decisions")).toBe(false);
  });

  it("does not match a section that merely shares a prefix", () => {
    expect(isActive("/benchmarks-archive", "/decisions")).toBe(false);
  });

  it("treats the dashboard as exact-only", () => {
    // Every path starts with "/", so a prefix test would light up the
    // dashboard on every page in the app.
    expect(isActive("/", "/")).toBe(true);
    expect(isActive("/maps", "/")).toBe(false);
  });
});

describe("the page title", () => {
  it("names the current section", () => {
    expect(pageTitleKey("/decisions")).toBe("nav.decisions");
    expect(pageTitleKey("/reviews")).toBe("nav.reviews");
    expect(pageTitleKey("/")).toBe("nav.dashboard");
  });

  it("keeps the section's name on a detail page", () => {
    expect(pageTitleKey("/decisions/ab12")).toBe("nav.decisions");
  });

  it("names routes that have no sidebar entry", () => {
    expect(pageTitleKey("/login")).toBe("nav.login");
    expect(pageTitleKey("/welcome")).toBe("nav.welcome");
  });

  it("falls back to the app name for an unknown path", () => {
    expect(pageTitleKey("/nowhere")).toBe("app.name");
  });

  it("prefers the longest match", () => {
    // "/auth/callback" must not resolve through some shorter route.
    expect(matchRoute("/auth/callback")?.href).toBe("/auth/callback");
  });
});

describe("breadcrumbs", () => {
  it("is empty on the dashboard, which is the root", () => {
    expect(breadcrumbs("/")).toEqual([]);
  });

  it("is a single crumb on a section page", () => {
    expect(breadcrumbs("/decisions")).toEqual([
      { labelKey: "nav.decisions", href: "/decisions" },
    ]);
  });

  it("shows a record id verbatim, never translated", () => {
    // Ids, checksums and user-supplied names must never be run through
    // a dictionary.
    expect(breadcrumbs("/decisions/ab12cd34")).toEqual([
      { labelKey: "nav.decisions", href: "/decisions" },
      { label: "ab12cd34" },
    ]);
  });

  it("shows only the first extra segment", () => {
    expect(breadcrumbs("/maps/xyz/edit")).toEqual([
      { labelKey: "nav.maps", href: "/maps" },
      { label: "xyz" },
    ]);
  });

  it("is empty for a path that matches nothing", () => {
    expect(breadcrumbs("/nowhere/at/all")).toEqual([]);
  });
});

describe("a page naming its own last crumb", () => {
  const path = breadcrumbs("/decisions/20750b0d9dbe");

  it("leaves breadcrumbs() itself untouched", () => {
    /* The pure function stays the one place that decides what a *path*
       means, and it still shows an unknown segment verbatim. The name
       arrives from the page, not from a dictionary. */
    expect(path).toHaveLength(2);
    expect(path[1]).toEqual({ label: "20750b0d9dbe" });
  });

  it("replaces the id when a name was supplied", () => {
    expect(crumbLabel(path, 1, "sudden_stop_v5")).toEqual({ label: "sudden_stop_v5" });
  });

  it("leaves the id standing while the page has no name yet", () => {
    /* `null` during the fetch. The crumb must say something, and the id
       is what the path supports. */
    expect(crumbLabel(path, 1, null)).toEqual({ label: "20750b0d9dbe" });
  });

  it("never renames a crumb that is a known route", () => {
    /* `Decisions` is the section. Naming it after one of its records is
       the mistake this condition exists to prevent — and it is the one a
       reader would misread as navigation. */
    expect(crumbLabel(path, 0, "sudden_stop_v5")).toBe(path[0]);
    expect(crumbLabel(path, 0, "sudden_stop_v5").labelKey).toBeTruthy();
  });

  it("never renames anything but the last crumb", () => {
    const three = [...path, { label: "extra" }];
    expect(crumbLabel(three, 1, "sudden_stop_v5")).toEqual({ label: "20750b0d9dbe" });
    expect(crumbLabel(three, 2, "sudden_stop_v5")).toEqual({ label: "sudden_stop_v5" });
  });

  it("treats an empty name as no name", () => {
    /* An empty crumb is worse than an id: it looks like the breadcrumb
       broke. */
    expect(crumbLabel(path, 1, "")).toEqual({ label: "20750b0d9dbe" });
  });
});

describe("which pages get the width cap lifted", () => {
  it("lifts it for the drawing surfaces", () => {
    /* A map editor, the simulator and the deployment form: there more
       width is more of the thing the page is for. */
    for (const path of ["/maps", "/simulate", "/deployments"]) {
      expect(wideContent(path), path).toBe(true);
    }
  });

  it("lifts it for their record pages too", () => {
    /* `/maps/warehouse_a` is the same drawing surface as `/maps`. A
       detail page that suddenly narrowed would be the odd one out, and
       matching on equality rather than prefix is how that happens. */
    expect(wideContent("/maps/warehouse_a")).toBe(true);
    expect(wideContent("/deployments/sudden_stop_v5")).toBe(true);
  });

  it("keeps the cap everywhere text is read", () => {
    /* A line running the full width of a 1920 monitor is a line the eye
       cannot track back to the start of the next one. */
    for (const path of ["/", "/decisions", "/decisions/20750b0d9dbe", "/system", "/agent", "/library"]) {
      expect(wideContent(path), path).toBe(false);
    }
  });

  it("does not match a route that merely starts with the same letters", () => {
    /* `startsWith` without the separator would make `/mapsomething`
       wide. `isActive` handles that; this pins it. */
    expect(wideContent("/mapsomething")).toBe(false);
    expect(wideContent("/simulate-archive")).toBe(false);
  });

  it("names every wide route in the navigation model", () => {
    /* A path nobody can reach would be a rule nobody can see is dead. */
    const hrefs = new Set(ALL_ROUTES.map((route) => route.href));
    for (const path of ["/maps", "/simulate", "/deployments"]) {
      expect(hrefs.has(path), path).toBe(true);
    }
  });
});
