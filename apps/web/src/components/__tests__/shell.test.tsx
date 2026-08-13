/** The shell, rendered.
 *
 * These assert on real HTML from `renderToStaticMarkup` — no jsdom, no
 * testing-library, neither of which is installed. That covers first
 * render, which is where every difference the brief asked about lives:
 * collapsed vs expanded, signed in vs signed out, badge vs no badge,
 * English vs Vietnamese.
 *
 * What it cannot cover is clicking, so the *behaviour* behind each
 * control is tested at the store level instead (see sidebar.test.ts,
 * theme.test.ts). Recorded in docs/KNOWN_LIMITATIONS.md.
 */

import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";

import { EmptyState } from "@/components/EmptyState";
import { Sidebar } from "@/components/Sidebar";
import { StatCard } from "@/components/StatCard";
import { DICTIONARIES, type Locale } from "@/lib/i18n";
import { translate } from "@/lib/i18n";
import type { SessionUser } from "@/lib/auth";

function translator(locale: Locale = "en") {
  return (key: string, vars?: Record<string, string | number>) =>
    translate(DICTIONARIES[locale], DICTIONARIES.en, key, vars);
}

const ALICE: SessionUser = {
  id: "u1",
  nickname: "alice",
  email: "alice@example.com",
  display_name: "Alice Example",
  avatar_url: "",
  is_admin: false,
  needs_nickname: false,
  providers: ["google"],
};

function sidebar(
  overrides: Partial<Parameters<typeof Sidebar>[0]> = {},
  locale: Locale = "en",
): string {
  return renderToStaticMarkup(
    <Sidebar
      pathname="/"
      collapsed={false}
      mobileOpen={false}
      t={translator(locale)}
      user={null}
      onToggleCollapse={() => {}}
      onNavigate={() => {}}
      {...overrides}
    />,
  );
}

describe("Sidebar — expanded", () => {
  it("shows the brand, the tagline and every menu name", () => {
    const html = sidebar();
    expect(html).toContain("PlanBench");
    expect(html).toContain("simulation only");
    for (const label of ["Dashboard", "Maps", "Candidates", "Decisions", "Agent", "Reviews"]) {
      expect(html).toContain(label);
    }
  });

  it("groups the menu into labelled sections", () => {
    /* Grouped by what the reader is *doing*, not by which system
       produced the screen. The previous split put the two flows inside
       one heading, so a replacement sat beside the thing it replaced
       with nothing saying which was which. */
    const html = sidebar();
    expect(html).toContain("What you are doing");
    expect(html).toContain("Materials");
    expect(html).toContain("Being replaced");
  });

  it("says what every entry is for, not just its name", () => {
    /* Twelve names and nothing else left a reader unable to tell that
       Benchmarks and Decisions answer different questions. That was the
       largest cost of running two flows at once, and none of it was in
       the code. */
    const html = sidebar();
    expect(html).toContain("Declare a world to measure on");
    expect(html).toContain("sidebar-desc");
  });

  it("says out loud which pages are being replaced", () => {
    /* One entry is left in that group. `/benchmarks`, `/leaderboard` and
       `/algorithms` were removed in P6, each only after the thing that
       replaced it existed; `/scenarios` stays because the deployment
       form still cannot draw obstacles, so removing it would take away a
       capability rather than move one — and the sidebar says that rather
       than leaving a reader to wonder why one old page survived. */
    const html = sidebar({ user: ALICE });
    expect(html).toContain("Being replaced");
    expect(html).toContain("Kept until the deployment form can draw obstacles");
  });

  it("offers a collapse control", () => {
    expect(sidebar()).toContain('aria-label="Collapse sidebar"');
  });

  it("does not repeat each label as a tooltip", () => {
    // With the label visible, a tooltip saying the same thing is noise
    // and an aria-label saying it is read twice.
    expect(sidebar()).not.toContain('data-tooltip="Maps"');
  });
});

describe("Sidebar — collapsed", () => {
  it("gives every icon a tooltip and an accessible name", () => {
    /* Collapsed, the tooltip is the only surface left, so it carries the
       description too — a rail of icons with nothing but names is what
       the descriptions were added to fix. */
    const html = sidebar({ collapsed: true });
    expect(html).toContain('data-tooltip="Maps — Draw the walls a deployment runs in"');
    expect(html).toContain('aria-label="Maps"');
  });

  it("offers an expand control instead of a collapse one", () => {
    const html = sidebar({ collapsed: true });
    expect(html).toContain('aria-label="Expand sidebar"');
    expect(html).not.toContain('aria-label="Collapse sidebar"');
  });

  it("still renders the labels, for CSS to hide", () => {
    // Kept in the DOM so expanding is a CSS change, not a re-render.
    expect(sidebar({ collapsed: true })).toContain("sidebar-label");
  });
});

describe("Sidebar — the active page", () => {
  it("marks the current section with aria-current, not colour alone", () => {
    const html = sidebar({ pathname: "/decisions" });
    expect(html).toContain('aria-current="page"');
    // Exactly one page is current.
    expect(html.match(/aria-current="page"/g)).toHaveLength(1);
  });

  it("keeps the section marked on a detail page", () => {
    expect(sidebar({ pathname: "/decisions/ab12" })).toContain('aria-current="page"');
  });

  it("marks the dashboard only on the dashboard", () => {
    // Every path starts with "/", so a prefix test would light up the
    // dashboard everywhere. The marked link must be the Maps one.
    const onMaps = sidebar({ pathname: "/maps" });
    expect(onMaps.match(/aria-current="page"/g)).toHaveLength(1);
    // The one marked link must be Maps, not the dashboard.
    const marked = onMaps.match(/<a[^>]*aria-current="page"[^>]*>/)?.[0] ?? "";
    expect(marked).toContain('href="/maps"');
  });
});

describe("Sidebar — the drawer", () => {
  it("is closed by default", () => {
    expect(sidebar()).toContain('data-open="false"');
  });

  it("is open when asked", () => {
    expect(sidebar({ mobileOpen: true })).toContain('data-open="true"');
  });
});

describe("Sidebar — the account card", () => {
  it("shows nickname and email when signed in", () => {
    const html = sidebar({ user: ALICE });
    expect(html).toContain("alice");
    expect(html).toContain("alice@example.com");
  });

  it("shows no account card at all when signed out", () => {
    // Never a fake one: the brief was explicit about that.
    expect(sidebar()).not.toContain("session-card");
  });

  it("falls back to an initial when there is no avatar picture", () => {
    expect(sidebar({ user: ALICE })).toContain("avatar-placeholder");
  });

  it("uses the provider picture when there is one", () => {
    const html = sidebar({ user: { ...ALICE, avatar_url: "https://example.com/a.png" } });
    expect(html).toContain("https://example.com/a.png");
    // Decorative: the nickname is written beside it.
    expect(html).toContain('alt=""');
  });
});

describe("Sidebar — Vietnamese", () => {
  it("translates every menu name", () => {
    const html = sidebar({}, "vi");
    expect(html).toContain("Tổng quan");
    expect(html).toContain("Bản đồ");
    expect(html).toContain("Quyết định");
    expect(html).not.toContain(">Dashboard<");
  });

  it("translates the collapse control", () => {
    expect(sidebar({}, "vi")).toContain('aria-label="Thu gọn thanh bên"');
  });

  it("leaves the product name alone", () => {
    // "PlanBench" is a name, not a string to translate.
    expect(sidebar({}, "vi")).toContain("PlanBench");
  });
});

describe("StatCard", () => {
  it("shows the number", () => {
    const html = renderToStaticMarkup(
      <StatCard icon="benchmark" label="Total benchmarks" value={7} />,
    );
    expect(html).toContain("7");
    expect(html).toContain("Total benchmarks");
  });

  it("shows zero as zero", () => {
    const html = renderToStaticMarkup(<StatCard icon="benchmark" label="Total" value={0} />);
    expect(html).toContain(">0<");
  });

  it("shows an em dash — never zero — when the figure is unknown", () => {
    const html = renderToStaticMarkup(<StatCard icon="benchmark" label="Total" value={null} />);
    expect(html).toContain("—");
    expect(html).not.toContain(">0<");
  });

  it("shows a skeleton while loading, and no misleading number", () => {
    const html = renderToStaticMarkup(
      <StatCard icon="benchmark" label="Total" value={null} loading />,
    );
    expect(html).toContain("skeleton");
    expect(html).not.toContain("—");
  });

  it("links to the page behind the figure when given one", () => {
    const html = renderToStaticMarkup(
      <StatCard icon="benchmark" label="Total" value={1} href="/benchmarks" />,
    );
    expect(html).toContain('href="/benchmarks"');
  });
});

describe("EmptyState", () => {
  it("says what is missing and what to do about it", () => {
    const html = renderToStaticMarkup(
      <EmptyState
        icon="benchmark"
        title="No benchmarks yet"
        body="Create your first benchmark."
        actionHref="/benchmarks"
        actionLabel="Create benchmark"
      />,
    );
    expect(html).toContain("No benchmarks yet");
    expect(html).toContain("Create your first benchmark.");
    expect(html).toContain('href="/benchmarks"');
    expect(html).toContain("Create benchmark");
  });

  it("works without an action", () => {
    const html = renderToStaticMarkup(<EmptyState title="Nothing to review" />);
    expect(html).toContain("Nothing to review");
    expect(html).not.toContain("quick-action");
  });
});
