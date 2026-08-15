/** The dashboard page itself, and the card that is no longer on it.
 *
 * The brief asked for the big "BACKEND — version 0.1.0 at
 * http://localhost:8000" card to go: it told an ordinary user nothing
 * they could act on, and told a stranger where the API lives. It is easy
 * to remove and just as easy to reintroduce, so this asserts on the
 * *source* that it is gone and that the base URL is not printed on any
 * page except /system.
 *
 * Source-level rather than rendered, because the page is a client
 * component whose whole body is behind an effect and a fetch — asserting
 * on its first paint would assert on a loading state.
 */

import { readFileSync, readdirSync, statSync } from "node:fs";
import { join, sep } from "node:path";
import { describe, expect, it } from "vitest";

const APP = join(process.cwd(), "src", "app");

function pageFiles(directory: string): string[] {
  const found: string[] = [];
  for (const entry of readdirSync(directory)) {
    const full = join(directory, entry);
    if (statSync(full).isDirectory()) {
      if (entry !== "__tests__") found.push(...pageFiles(full));
    } else if (entry === "page.tsx") {
      found.push(full);
    }
  }
  return found;
}

/** A page's path as a route, whatever the OS spells it with.
 *
 * `join` gives `src\app\system\page.tsx` on Windows, and comparing that
 * against a hand-written `/system/page.tsx` fails for a reason that has
 * nothing to do with the claim being tested. This test was red on
 * Windows from the day it was written.
 */
function asRoute(file: string): string {
  return file.replace(APP, "").split(sep).join("/");
}

const DASHBOARD = readFileSync(join(APP, "page.tsx"), "utf8");

describe("the BACKEND card is gone", () => {
  it("no longer prints the API base URL on the dashboard", () => {
    expect(DASHBOARD).not.toContain("API_BASE");
  });

  it("no longer prints a version on the dashboard", () => {
    expect(DASHBOARD).not.toMatch(/health\.version|\bversion\b\s*\{/);
  });

  it("does not fetch health just to show a version", () => {
    // Connectivity is still checked — via loadDashboard — but the result
    // is one dot and two words, not a card.
    expect(DASHBOARD).not.toContain("api.health()");
  });
});

describe("the API base URL appears on exactly one page", () => {
  it("is only referenced by /system", () => {
    const offenders = pageFiles(APP)
      .filter((file) => readFileSync(file, "utf8").includes("API_BASE"))
      .map(asRoute);
    expect(offenders).toEqual(["/system/page.tsx"]);
  });

  it("is hidden there in production", () => {
    const system = readFileSync(join(APP, "system", "page.tsx"), "utf8");
    expect(system).toContain("IS_DEVELOPMENT");
    expect(system).toContain("system.hiddenInProduction");
  });
});

describe("the dashboard shows something worth looking at", () => {
  it("has a stat card for each thing worth counting", () => {
    for (const key of [
      "dashboard.stats.decisions",
      "dashboard.stats.accepted",
      "dashboard.stats.pendingReviews",
      "dashboard.stats.scenarios",
      "dashboard.stats.candidates",
      "dashboard.stats.simulations",
    ]) {
      expect(DASHBOARD).toContain(key);
    }
  });

  it("has quick actions", () => {
    expect(DASHBOARD).toContain("QuickActions");
  });

  it("has recent activity and pending reviews", () => {
    expect(DASHBOARD).toContain("dashboard.recentDecisions");
    expect(DASHBOARD).toContain("dashboard.recentSimulations");
    expect(DASHBOARD).toContain("dashboard.pendingRequests");
  });

  it("has an empty state for each of them", () => {
    expect(DASHBOARD).toContain("dashboard.empty.decisions.title");
    expect(DASHBOARD).toContain("dashboard.empty.simulations.title");
    expect(DASHBOARD).toContain("dashboard.empty.reviews.title");
  });

  it("has a small system status rather than a card", () => {
    expect(DASHBOARD).toContain("SystemStatus");
  });

  it("tells a signed-out visitor to sign in, without faking an account", () => {
    expect(DASHBOARD).toContain("dashboard.empty.signedOut.title");
  });
});

describe("no page hardcodes English where a key belongs", () => {
  /** Every page goes through the shell, and the shell is translated. */
  it("uses the translator on every page", () => {
    const untranslated = pageFiles(APP)
      .filter((file) => !readFileSync(file, "utf8").includes("useTranslation"))
      .map((file) => file.replace(APP, ""));
    expect(untranslated).toEqual([]);
  });
});
