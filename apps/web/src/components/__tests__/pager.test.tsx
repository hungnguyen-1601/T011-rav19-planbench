/** The pager both list pages draw.
 *
 * Rendered through `renderToStaticMarkup`, the way every component test
 * in this repo works — there is no jsdom (see `vitest.config.ts`), so
 * what is checked is the markup at each position rather than a click.
 * For a control whose whole job is "which of my two buttons is dead
 * right now", that is the interesting half.
 */

import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import en from "../../lib/i18n/locales/en.json";
import vi from "../../lib/i18n/locales/vi.json";
import { Pager } from "@/components/Pager";

function render(page: number, pageCount: number): string {
  return renderToStaticMarkup(
    <Pager
      page={page}
      pageCount={pageCount}
      onPage={() => {}}
      labelKey="decisions.list.pager.label"
    />,
  );
}

describe("where the reader is", () => {
  it("counts pages from one on screen, though the state is 0-based", () => {
    /* "Page 0 of 4" is a thing only the code believes. */
    expect(render(0, 4)).toContain("Page 1 of 4");
    expect(render(3, 4)).toContain("Page 4 of 4");
  });

  it("says the position out loud when it changes", () => {
    /* Pressing "next" changes a table the reader may not be looking at;
       without a live region the only feedback is visual. */
    expect(render(1, 4)).toContain('aria-live="polite"');
  });
});

describe("the ends of the list", () => {
  it("disables 'previous' on the first page and nothing else", () => {
    const html = render(0, 4);
    expect([...html.matchAll(/disabled/g)]).toHaveLength(1);
    /* The first button in source order is "previous", so a disabled
       attribute before the position marker is that one. */
    expect(html.slice(0, html.indexOf("pager-position"))).toContain("disabled");
  });

  it("disables 'next' on the last page and nothing else", () => {
    const html = render(3, 4);
    expect([...html.matchAll(/disabled/g)]).toHaveLength(1);
    expect(html.slice(html.indexOf("pager-position"))).toContain("disabled");
  });

  it("leaves both live in the middle", () => {
    expect([...render(1, 4).matchAll(/disabled/g)]).toHaveLength(0);
  });

  it("clamps a page number past either end rather than enabling a dead step", () => {
    /* Belt and braces: the hook clamps too, but a pager handed a stale
       page must not offer a step off the list. */
    expect([...render(9, 4).matchAll(/disabled/g)]).toHaveLength(1);
    expect(render(9, 4).slice(render(9, 4).indexOf("pager-position"))).toContain("disabled");
  });
});

describe("what a screen reader hears", () => {
  it("gives the strip a name, so it is not just two unlabelled buttons", () => {
    expect(render(1, 4)).toContain('aria-label="Comparison run pages"');
  });

  it("labels the steps with words, and hides the arrows", () => {
    /* A bare `‹` is announced as "left single quotation mark", or as
       nothing at all. It is decoration beside a real word — and the
       word is on screen too, for anybody who has not used this app
       before. */
    const html = render(1, 4);
    expect(html).toContain("Previous");
    expect(html).toContain("Next");
    expect(html).toMatch(/aria-hidden="true">‹/);
    expect(html).toMatch(/aria-hidden="true">›/);
  });

  it("has every string it needs in both languages", () => {
    for (const key of [
      "pager.previous",
      "pager.next",
      "pager.pageOf",
      "decisions.list.pager.label",
      "deployments.pager.label",
    ]) {
      expect(en).toHaveProperty(key);
      expect(vi).toHaveProperty(key);
    }
  });
});

describe("a list that fits on one page", () => {
  it("draws nothing at all", () => {
    /* A pair of permanently dead buttons under a seven-row table says
       "there is more" when there is not. */
    expect(render(0, 1)).toBe("");
    expect(render(0, 0)).toBe("");
  });
});
