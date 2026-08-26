/** The tab strip, rendered.
 *
 * One property here matters more than the rest and is invisible from
 * the outside: an inactive panel is *hidden*, not removed. React
 * discards the state of anything it unmounts, and the deployment form
 * keeps real state in its controls — the last non-zero amplitude of
 * each noise source, so unticking and re-ticking gives back what was
 * typed. Rebuilding that on every tab change loses an edited figure to
 * a stray click on another tab, which is the kind of small loss that
 * costs a re-measurement to notice.
 */

import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { Tabs, type TabDefinition } from "@/components/Tabs";

type Id = "one" | "two" | "three";

const TABS: TabDefinition<Id>[] = [
  { id: "one", label: "First", content: <p>content of one</p> },
  { id: "two", label: "Second", content: <p>content of two</p> },
  { id: "three", label: "Third", content: <p>content of three</p> },
];

function render(overrides: Partial<Parameters<typeof Tabs<Id>>[0]> = {}): string {
  return renderToStaticMarkup(
    <Tabs
      tabs={TABS}
      active="one"
      onSelect={() => {}}
      idPrefix="test"
      ariaLabel="Test settings"
      {...overrides}
    />,
  );
}

describe("the strip", () => {
  it("offers every tab", () => {
    const html = render();
    for (const label of ["First", "Second", "Third"]) expect(html).toContain(label);
  });

  it("marks exactly one as selected", () => {
    const html = render();
    expect(html.match(/aria-selected="true"/g) ?? []).toHaveLength(1);
    expect(html).toMatch(/id="test-tab-one"[^>]*aria-selected="true"/);
  });

  it("wires each tab to the panel it controls", () => {
    const html = render();
    expect(html).toContain('aria-controls="test-panel-two"');
    expect(html).toContain('id="test-panel-two"');
    expect(html).toContain('aria-labelledby="test-tab-two"');
  });

  it("names the strip, so a screen reader can say what it switches", () => {
    expect(render()).toContain('aria-label="Test settings"');
  });
});

describe("the panels", () => {
  it("keeps every panel mounted, hiding the ones not chosen", () => {
    /* The load-bearing assertion. Were these unmounted, a control's
       local state — a remembered noise amplitude, a chosen vehicle —
       would be rebuilt from scratch each time somebody looked at
       another tab. */
    const html = render();
    for (const text of ["content of one", "content of two", "content of three"]) {
      expect(html).toContain(text);
    }
  });

  it("hides exactly the ones that are not active", () => {
    const html = render({ active: "two" });
    expect(html).toMatch(/id="test-panel-one"[^>]*hidden/);
    expect(html).toMatch(/id="test-panel-three"[^>]*hidden/);
    expect(html).not.toMatch(/id="test-panel-two"[^>]*hidden/);
  });
});

describe("the badges", () => {
  it("shows a count on a tab that has refusals waiting", () => {
    /* A tab is a place to hide things, and a blocked filing with no
       visible reason is what the whole error-addressing scheme exists
       to prevent. */
    const html = render({
      tabs: TABS.map((tab) =>
        tab.id === "two" ? { ...tab, badge: 3, badgeLabel: "3 refused by the server" } : tab,
      ),
    });
    expect(html).toContain(">3</span>");
    expect(html).toContain('aria-label="3 refused by the server"');
  });

  it("shows nothing at all when a tab is clean", () => {
    /* Zero is not a small badge, it is the absence of one — a grey `0`
       beside every heading reads as a control rather than as calm. */
    const html = render({ tabs: TABS.map((tab) => ({ ...tab, badge: 0 })) });
    expect(html).not.toContain("badge err");
  });
});
