/** The decision detail page's four tabs.
 *
 * Two registers, because this repo has no jsdom (see `vitest.config.ts`):
 *
 * - **Rendered**, through `renderToStaticMarkup`. `DecisionTabs` is a
 *   presentational component that takes its content as props, so it can
 *   be rendered here with stand-in panels — which is the only reason it
 *   is a component of its own rather than JSX inside a page that
 *   fetches. Rendering it twice with a different `active` is what
 *   "switching tabs changes the panel" means without a click.
 * - **Source-level**, for the page itself, matching the other page
 *   tests: `DecisionDetail` sits behind an effect and a fetch, so a
 *   first paint would only show a loading state.
 *
 * The arrow-key rule lives in `lib/decisionTabs` and is unit-tested
 * here, for the reason the sample rules do: a decision written inside an
 * `onKeyDown` handler is a decision no test in this repo can reach.
 */

import { readFileSync } from "node:fs";
import { join } from "node:path";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import en from "../../lib/i18n/locales/en.json";
import vi from "../../lib/i18n/locales/vi.json";
import { DecisionTabs } from "@/components/DecisionTabs";
import { DECISION_TAB_IDS, tabAfterKey } from "@/lib/decisionTabs";

const APP = join(process.cwd(), "src", "app");
const DETAIL = readFileSync(join(APP, "decisions", "[id]", "DecisionDetail.tsx"), "utf8");
const CSS = readFileSync(join(APP, "globals.css"), "utf8");
const TABS = readFileSync(
  join(process.cwd(), "src", "components", "DecisionTabs.tsx"),
  "utf8",
);

const TAB_LABELS = [
  "decisions.detail.tabs.conclusion",
  "decisions.detail.tabs.episode",
  "decisions.detail.tabs.reasoning",
  "decisions.detail.tabs.more",
];

function render(active: string): string {
  return renderToStaticMarkup(
    <DecisionTabs
      labelKey="decisions.detail.tabs.label"
      active={active}
      onSelect={() => {}}
      tabs={DECISION_TAB_IDS.map((id, index) => ({
        id,
        labelKey: TAB_LABELS[index],
        content: <p>{`panel-body-${id}`}</p>,
      }))}
    />,
  );
}

describe("the page offers exactly four tabs", () => {
  it("names one per group, in the order the page argues in", () => {
    expect(DECISION_TAB_IDS).toEqual(["conclusion", "episode", "reasoning", "more"]);
    const html = render("conclusion");
    expect([...html.matchAll(/role="tab"/g)]).toHaveLength(4);
    expect([...html.matchAll(/role="tabpanel"/g)]).toHaveLength(4);
  });

  it("has a label for every tab in both languages", () => {
    /* The strip's own accessible name counts: a tab list with no name
       is announced as an unlabelled group of four buttons. */
    for (const key of [...TAB_LABELS, "decisions.detail.tabs.label"]) {
      expect(en).toHaveProperty(key);
      expect(vi).toHaveProperty(key);
    }
    expect(Object.keys(en).sort()).toEqual(Object.keys(vi).sort());
  });
});

describe("switching tabs changes which panel is shown", () => {
  it("marks exactly one tab selected and shows exactly one panel", () => {
    const html = render("conclusion");
    expect([...html.matchAll(/aria-selected="true"/g)]).toHaveLength(1);
    /* Three of the four panels carry `hidden`; the fourth does not.
       Counting is the assertion — "the active one is visible" is only
       half of it, and the half that a broken build still satisfies. */
    expect([...html.matchAll(/role="tabpanel"[^>]*hidden/g)]).toHaveLength(3);
  });

  it("moves the visible panel when the active tab changes", () => {
    const first = render("conclusion");
    const third = render("reasoning");
    expect(first).not.toEqual(third);
    /* `hidden` sits after `role="tabpanel"` in the markup, so this
       matches the panel element itself rather than anything inside it. */
    expect(first).toMatch(/id="decision-tabpanel-reasoning"[^>]*hidden/);
    expect(first).not.toMatch(/id="decision-tabpanel-conclusion"[^>]*hidden/);
    expect(third).toMatch(/id="decision-tabpanel-conclusion"[^>]*hidden/);
    expect(third).not.toMatch(/id="decision-tabpanel-reasoning"[^>]*hidden/);
  });

  it("keeps every panel in the tree, so nothing is unmounted on a switch", () => {
    /* The whole reason the inactive panels are hidden rather than
       dropped: the episode viewer holds two fetched traces, a running
       replay and a camera angle, and the advisory panels hold answers
       that cost a model call. A ternary would throw all of that away
       every time the reader looked at something else. */
    const html = render("conclusion");
    for (const id of DECISION_TAB_IDS) {
      expect(html).toContain(`panel-body-${id}`);
    }
    expect(TABS).toContain("hidden={tab.id !== active}");
    expect(TABS).not.toMatch(/tab\.id === active \?[^:]*: null/);
  });
});

describe("the tab strip is reachable from the keyboard", () => {
  it("wires the roles and relationships a tab list needs", () => {
    const html = render("episode");
    expect(html).toContain('role="tablist"');
    expect(html).toContain('aria-controls="decision-tabpanel-episode"');
    expect(html).toContain('aria-labelledby="decision-tab-episode"');
    /* Roving tab order: one stop for the strip, not four. */
    expect([...html.matchAll(/tabindex="0"/g)]).toHaveLength(1);
    expect([...html.matchAll(/tabindex="-1"/g)]).toHaveLength(3);
  });

  it("moves left and right, wrapping at both ends", () => {
    expect(tabAfterKey("ArrowRight", 0, 4)).toBe(1);
    expect(tabAfterKey("ArrowRight", 3, 4)).toBe(0);
    expect(tabAfterKey("ArrowLeft", 0, 4)).toBe(3);
    expect(tabAfterKey("ArrowLeft", 2, 4)).toBe(1);
    expect(tabAfterKey("Home", 2, 4)).toBe(0);
    expect(tabAfterKey("End", 0, 4)).toBe(3);
  });

  it("leaves every other key alone", () => {
    /* Returning a number for `Tab` or `a` would steal the key from the
       browser and from anything typed into a panel below. */
    for (const key of ["Tab", "Enter", " ", "a", "ArrowUp", "ArrowDown"]) {
      expect(tabAfterKey(key, 1, 4)).toBeNull();
    }
    expect(tabAfterKey("ArrowRight", 0, 0)).toBeNull();
  });

  it("keeps a focus ring on the tabs", () => {
    /* The active tab is drawn with a negative `margin-bottom`, which
       pulls an outline under the strip's border — so this one is stated
       rather than left to the page-wide rule. */
    expect(CSS).toContain(".decision-tab:focus-visible");
    expect(CSS).toMatch(/\.decision-tab:focus-visible \{[^}]*outline: 2px solid var\(--accent\)/);
  });

  it("never gives the panels an author `display`, which would beat `hidden`", () => {
    /* `[hidden] { display: none }` is a UA rule, and any author
       `display` on the same element wins it — all four panels would
       render at once. */
    const panel = CSS.slice(CSS.indexOf(".decision-tabpanel"));
    expect(panel).toContain(".decision-tabpanel[hidden] { display: none; }");
    expect(CSS).not.toMatch(/\.decision-tabpanel \{[^}]*display:/);
  });
});

describe("which panels sit in which tab", () => {
  it("opens on the conclusion, not on the evidence", () => {
    /* A reader arrives for what the run concluded. Any other default
       makes them find it. */
    expect(DETAIL).toContain('active={tab}');
    const lib = readFileSync(join(process.cwd(), "src", "lib", "decisionTabs.ts"), "utf8");
    expect(lib).toContain('fallback: "conclusion"');
  });

  it("groups the conclusion, the advice and the comparison together", () => {
    const tab = DETAIL.slice(
      DETAIL.indexOf('id: "conclusion"'),
      DETAIL.indexOf('id: "episode"'),
    );
    expect(tab).toContain("<DecisionSummary run={run} />");
    expect(tab).toContain("<DecisionAdvice run={run} />");
    expect(tab).toContain("<CandidateComparison run={run} />");
  });

  it("gives the replay a tab of its own", () => {
    const tab = DETAIL.slice(
      DETAIL.indexOf('id: "episode"'),
      DETAIL.indexOf('id: "reasoning"'),
    );
    expect(tab).toContain("<TracePanel run={run} />");
  });

  it("keeps the headline with the evidence it qualifies", () => {
    const tab = DETAIL.slice(
      DETAIL.indexOf('id: "reasoning"'),
      DETAIL.indexOf('id: "more"'),
    );
    expect(tab).toContain("<ExplanationHeader run={run} />");
    expect(tab).toContain("<EvidencePanel run={run} />");
  });

  it("leaves the sample notice outside the strip, above all four", () => {
    /* "This run was stopped before it finished" qualifies every number
       in every tab, so it cannot be filed under one of them. */
    const notice = DETAIL.indexOf("<SampleNotice run={run} />");
    expect(notice).toBeGreaterThan(-1);
    expect(notice).toBeLessThan(DETAIL.indexOf("<DecisionTabs"));
  });

  it("puts everything else in the last tab, and drops nothing", () => {
    const tab = DETAIL.slice(DETAIL.indexOf('id: "more"'));
    for (const panel of [
      "<TradeoffInsights run={run} />",
      "<ConclusionPanel run={run} />",
      "<CardPanel run={run} />",
      "<CritiquePanel runId={run.id} />",
      "<OutcomePanel runId={run.id} />",
      "<AdvicePanel runId={run.id} />",
      "<ReportAdvicePanel runId={run.id} />",
      "<HumanActs run={run} onDone={refresh} />",
    ]) {
      expect(tab).toContain(panel);
    }
  });

  it("renders each panel exactly once", () => {
    /* A panel duplicated across two tabs is two copies of one fetch and
       two answers to the same question. */
    for (const panel of ["<TracePanel", "<EvidencePanel", "<HumanActs", "<DecisionSummary"]) {
      expect([...DETAIL.matchAll(new RegExp(panel, "g"))]).toHaveLength(1);
    }
  });
});

describe("the open tab survives a reload", () => {
  it("remembers it the way the theme and the sidebar are remembered", () => {
    const lib = readFileSync(join(process.cwd(), "src", "lib", "decisionTabs.ts"), "utf8");
    expect(lib).toContain("createPersistedStore");
    expect(lib).toContain('backend: "local"');
    /* Same prefix as `planbench.theme` and `planbench.sidebar`: one
       namespace in a store the whole origin shares. */
    expect(lib).toContain('"planbench.decision-tab"');
  });
});

describe("a tab label arrives as a key or as text, never as either", () => {
  const SOURCE = readFileSync(
    join(process.cwd(), "src", "components", "DecisionTabs.tsx"),
    "utf8",
  );

  it("keeps the two apart as fields rather than as one string", () => {
    /* `string | string` compiles and says nothing: handed "G1", the
       component cannot tell a key it must look up from text already in
       the reader's language. The guide's tab titles come from a manifest
       holding both languages, so there is no key to pass. */
    expect(SOURCE).toContain("labelKey: string; label?: never");
    expect(SOURCE).toContain("label: string; labelKey?: never");
  });

  it("resolves a key and passes text through untouched", () => {
    /* Running text through `t()` would look up a dictionary entry named
       "G1", miss, and fall back — printing the same thing by accident on
       the day it works and something else the day a key of that name is
       added. */
    expect(SOURCE).toContain("source.label !== undefined ? source.label : t(source.labelKey)");
  });

  it("still lets every existing caller pass a key alone", () => {
    /* The point of widening rather than renaming: four call sites, none
       of them touched. */
    for (const caller of [
      join("src", "app", "decisions", "page.tsx"),
      join("src", "app", "decisions", "[id]", "DecisionDetail.tsx"),
      join("src", "app", "deployments", "page.tsx"),
    ]) {
      expect(readFileSync(join(process.cwd(), caller), "utf8")).toContain("labelKey=");
    }
  });
});
