/** The mark that carries a field's explanation.
 *
 * The property that matters most here is the one that is easy to lose
 * when text moves into a tooltip: **the sentence is still in the
 * markup**. A hint that exists only while a mouse hovers is one that a
 * screen reader, a keyboard user and the locale-coverage guard cannot
 * reach — and this text is the difference between a number somebody
 * understands and one they guessed at.
 *
 * No DOM here, so hovering is not exercised; what a pointer does is on
 * the manual checklist. First render, and the accessible name, are.
 */

import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { Hint } from "@/components/Hint";

describe("the mark", () => {
  it("renders as something small and pointable", () => {
    const html = renderToStaticMarkup(<Hint text="One full cycle of the route." />);
    expect(html).toContain("hint-mark");
    expect(html).toContain(">?<");
  });

  it("carries the whole sentence as its accessible name", () => {
    /* Not a decoration: without this the text is mouse-only, which is
       where it was before this component existed and the reason it
       needed one. */
    const html = renderToStaticMarkup(<Hint text="One full cycle of the route." />);
    expect(html).toContain('aria-label="One full cycle of the route."');
  });

  it("names the field the sentence is about when given one", () => {
    /* "Seconds of head start" read aloud on its own is an answer with
       no question attached. */
    const html = renderToStaticMarkup(<Hint text="Seconds of head start." label="Seed head start" />);
    expect(html).toContain('aria-label="Seed head start: Seconds of head start."');
  });

  it("can be reached by keyboard", () => {
    const html = renderToStaticMarkup(<Hint text="Anything." />);
    expect(html).toContain('tabindex="0"');
    expect(html).toContain('role="button"');
  });

  it("shows no bubble until it is pointed at", () => {
    /* The whole point of the change: the explanations are off the page
       until asked for. A bubble in the initial markup would be the
       paragraph again, in a box. */
    const html = renderToStaticMarkup(<Hint text="Anything." />);
    expect(html).not.toContain('role="tooltip"');
    expect(html).not.toContain("hint-bubble");
  });
});
