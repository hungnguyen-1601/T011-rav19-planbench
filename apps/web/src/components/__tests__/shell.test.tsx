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

import { readFileSync } from "node:fs";
import { join } from "node:path";

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
       replaced it existed. `/scenarios` was kept on the same rule — the
       deployment form could not draw obstacles, so removing it would
       have taken a capability away rather than moved one. The form can
       now, which makes retiring it a decision somebody has to take
       rather than a thing to wait for; until then the sidebar says what
       it is instead of implying it is still the only editor. */
    const html = sidebar({ user: ALICE });
    expect(html).toContain("Being replaced");
    expect(html).toContain("The older editor");
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

/* Read once, at module scope, and named `SHEET` rather than `CSS`.
   Declared inside one `describe`, the name is out of scope in the next
   — where `CSS` then resolves to the DOM global instead of failing, so
   the mistake surfaces as `Property 'indexOf' does not exist on type
   'typeof CSS'` rather than as "undefined variable". */
const SHEET = readFileSync(
  join(process.cwd(), "src", "app", "globals.css"),
  "utf8",
).replace(/\r\n/g, "\n");
const SHELL = readFileSync(
  join(process.cwd(), "src", "components", "AppShell.tsx"),
  "utf8",
);

describe("the content column is a measure, not a container", () => {
  it("caps the width and centres what is left", () => {
    /* Without it the comparison table's value columns inflate to 480px
       around a six-character number on a 1920 monitor. */
    const rule = SHEET.slice(SHEET.indexOf("main.content {"), SHEET.indexOf("}", SHEET.indexOf("main.content {")));
    expect(rule).toContain("max-width: 1440px");
    expect(rule).toContain("margin-inline: auto");
  });

  it("gives the drawing surfaces a way out", () => {
    expect(SHEET).toContain("main.content--wide { max-width: none; }");
  });

  it("decides that in the shell, because a page cannot reach this element", () => {
    /* `AppShell` owns `<main>` and the root layout mounts it above every
       page, so there is no prop to hand upward. A class sprinkled
       through each page could not work even if someone tried. */
    expect(SHELL).toContain("wideContent(pathname)");
    expect(SHELL).toContain('"content content--wide" : "content"');
  });

  it("leaves the signed-out shell alone", () => {
    /* `bare-page` sets its own 460px measure and is two classes deep, so
       it still wins — but it is worth pinning, because it is the one
       place `main.content` is not what the reader sees. */
    expect(SHELL).toContain('className="content bare-page"');
    expect(SHEET).toContain("main.content.bare-page {");
  });
});

describe("the top bar is solid", () => {
  const topbar = () => {
    const at = SHEET.indexOf(".topbar {");
    expect(at, "the topbar rule moved").toBeGreaterThan(-1);
    return SHEET.slice(at, SHEET.indexOf("\n}", at)).replace(/\/\*[\s\S]*?\*\//g, "");
  };

  it("paints an opaque background rather than a translucent one", () => {
    /* Twelve per cent of a light background showing through a light page
       is not a glass effect — it is a faint smear of whatever happens to
       be scrolling underneath, which on this app is a table of digits. */
    expect(topbar()).toContain("background: var(--bg)");
    expect(topbar()).not.toContain("color-mix");
  });

  it("does not pay for a compositing layer on a sticky element", () => {
    /* `backdrop-filter` on `position: sticky` is the one place that cost
       lands on every frame of every scroll rather than once. */
    expect(topbar()).toContain("position: sticky");
    expect(topbar()).not.toContain("backdrop-filter");
  });

  it("keeps the border that was doing the separating anyway", () => {
    expect(topbar()).toContain("border-bottom: 1px solid var(--border)");
  });
});

describe("the button scale", () => {
  /* Anchored to the start of a line. Searching for `button {` as a bare
     substring finds `.icon-button {` first, and `button:hover:not(...)`
     finds `.icon-button:hover:not(...)` — so the assertions read a
     neighbouring rule and fail for a reason that has nothing to do with
     what they are checking. */
  const rule = (selector: string) => {
    const at = SHEET.indexOf(`\n${selector} {`);
    expect(at, `${selector} is not declared at the start of a line`).toBeGreaterThan(-1);
    return SHEET.slice(at, SHEET.indexOf("\n}", at)).replace(/\/\*[\s\S]*?\*\//g, "");
  };

  it("sets a floor rather than a fixed height", () => {
    /* 102 buttons, and they are not one shape: icon buttons, pagers,
       playback controls, a 20px id chip, buttons carrying a badge. A
       fixed height does not make the short ones taller — it clips the
       tall ones, and clipping reads as a design choice. */
    expect(rule("button")).toContain("min-height: 32px");
    expect(rule("button")).not.toMatch(/(?<!min-)height: *\d+px/);
  });

  it("tints on hover instead of recolouring the border", () => {
    /* The accent border is what `button.active` uses to say a toggle is
       on. While hover used it too, hover and on were the same picture
       and "what will my next click do" was answerable only from the
       caption. */
    expect(rule("button:hover:not(:disabled)")).toContain("background: var(--hover)");
    expect(rule("button:hover:not(:disabled)")).not.toContain("border-color");
    expect(rule("button.active")).toContain("border-color: var(--accent)");
  });

  it("does not declare a second focus ring", () => {
    /* One already exists, global, with the same outline and offset. A
       duplicate on `button` would be a second place to change it. */
    expect(SHEET).toContain(":focus-visible {");
    expect(SHEET).not.toContain("button:focus-visible {");
  });

  it("keeps the compact controls compact", () => {
    /* Each is a class and so outranks the element-level floor. Pinned
       because the floor landing on them is a silent regression: the id
       chip would become the tallest thing on its line of metadata. */
    expect(rule(".decision-copy-id")).toContain("min-height: 20px");
    expect(rule(".icon-button")).toContain("height: 34px");
  });
});
