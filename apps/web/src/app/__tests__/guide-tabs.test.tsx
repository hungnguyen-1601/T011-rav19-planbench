/** A tab that cannot be linked to is a tab whose content is unreachable.
 *
 * The panels not on screen are `hidden`, which removes them from
 * find-in-page and from the accessibility tree. That is the right
 * behaviour and it is also why the address matters: if `#g2` does not
 * open G2, the only way to reach that paragraph is to know it is behind
 * the second tab and click it.
 *
 * What is checked here is the wiring, at source level and through one
 * render. What is **not** checked is whether the selected tab is
 * *visibly* selected in both themes — that is a contrast judgement, it
 * needs a browser, and this suite has neither a DOM nor a screen. It is
 * a review step, named in the plan as its own item rather than folded in
 * here where it would look automated.
 */

import { readFileSync } from "node:fs";
import { join } from "node:path";
import { renderToStaticMarkup } from "react-dom/server";

import { describe, expect, it } from "vitest";

import { DecisionTabs } from "@/components/DecisionTabs";
import { GUIDE } from "../../../content/guide/manifest";

const SOURCE = readFileSync(
  join(process.cwd(), "src", "components", "guide", "GuideTabs.tsx"),
  "utf-8",
);

describe("a tab is addressable (T7a)", () => {
  it("reads the hash on arrival and keeps listening for it", () => {
    /* Both halves are needed: the first answers a reload and a pasted
       link, the second answers a link from elsewhere on the same page,
       which changes the hash without remounting anything. */
    expect(SOURCE).toContain("window.location.hash.slice(1)");
    expect(SOURCE).toContain('window.addEventListener("hashchange", fromHash)');
    expect(SOURCE).toContain('window.removeEventListener("hashchange", fromHash)');
  });

  it("only accepts a hash that names a tab, and otherwise leaves the first", () => {
    /* A stale link should show the article rather than an empty panel. */
    expect(SOURCE).toContain("if (tabs.some((tab) => tab.id === id)) setActive(id)");
    expect(SOURCE).toContain("useState(tabs[0]?.id ?? \"\")");
  });

  it("writes the tab into history so Back walks them", () => {
    expect(SOURCE).toContain("window.history.pushState");
    /* The call, not the word: the docstring names `replaceState` to say
       why it is not used, and a bare substring check would read that
       sentence as the mistake it warns about. */
    expect(SOURCE).not.toContain("history.replaceState");
  });

  it("does not take focus when a hash selects a tab", () => {
    /* Arriving is not asking to be moved. Focus-on-open belongs to a
       search result, which is a deliberate act, and is not wired here —
       so nothing in this component may call focus(). */
    expect(SOURCE).not.toContain(".focus()");
  });
});

describe("the strip a tabbed article renders", () => {
  const gates = GUIDE.find((article) => article.slug === "gates")!;

  it("marks exactly one tab selected and hides the other panels", () => {
    const html = renderToStaticMarkup(
      <DecisionTabs
        tabs={gates.tabs!.map((tab) => ({
          id: tab.id,
          label: tab.title.en,
          content: <p>{tab.id} body</p>,
        }))}
        active="g2"
        onSelect={() => {}}
        label="gates"
      />,
    );
    expect([...html.matchAll(/aria-selected="true"/g)]).toHaveLength(1);
    expect(html).toContain('id="decision-tab-g2"');
    /* Five of six panels hidden — the property that makes an anchor
       inside a panel unreachable, and the reason tabs are used only
       where the tab itself is the anchor. */
    expect([...html.matchAll(/hidden=""/g)]).toHaveLength(gates.tabs!.length - 1);
  });

  it("shows the manifest's text rather than looking it up as a key", () => {
    const html = renderToStaticMarkup(
      <DecisionTabs
        tabs={[{ id: "g1", label: gates.tabs![0].title.vi, content: null }]}
        active="g1"
        onSelect={() => {}}
        label="cong"
      />,
    );
    expect(html).toContain(gates.tabs![0].title.vi);
  });
});
