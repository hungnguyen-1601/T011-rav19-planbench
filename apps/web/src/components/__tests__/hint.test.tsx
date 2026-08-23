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
 *
 * The focus ring is read out of the stylesheet rather than measured. A
 * rule that switches the ring off is a plain fact about the file, and
 * reading the file is the only way this repository can catch it before
 * somebody tabs into the page and finds nothing there.
 */

import { readFileSync } from "node:fs";
import { join } from "node:path";

import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { Hint, hintKeyAction } from "@/components/Hint";

const CSS = readFileSync(join(process.cwd(), "src", "app", "globals.css"), "utf8")
  .split("\r\n")
  .join("\n");

const SOURCE = readFileSync(join(process.cwd(), "src", "components", "Hint.tsx"), "utf8");

/** One JSX handler as written, from its prop name to the `}}` that ends
 *  it. What a handler *does* needs a DOM; that it still contains the one
 *  call holding a call site upright does not. */
function handler(prop: string): string {
  const start = SOURCE.indexOf(`${prop}={`);
  if (start < 0) throw new Error(`no ${prop} on the mark`);
  const body = SOURCE.slice(start, SOURCE.indexOf("}}", start));
  /* Every handler here calls `preventDefault`, so a slice that overran
     into the next one would pass on its neighbour's call and report a
     guard that is no longer there. */
  if (/\bon[A-Z]\w*=\{/.test(body.slice(prop.length))) {
    throw new Error(`${prop} slice ran past the end of the handler`);
  }
  return body;
}

/** One rule as written, from its selector to the closing brace. */
function rule(selector: string): string {
  const start = CSS.indexOf(`\n${selector} {`);
  if (start < 0) throw new Error(`no rule for ${selector} in globals.css`);
  return CSS.slice(start, CSS.indexOf("}", start));
}

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

  it("shows the keyboard where it landed", () => {
    /* tabindex only decides that focus can land here; it says nothing
       about whether anyone can see that it did. This rule used to be
       shared with :hover, so an `outline: none` written for the mouse
       reached the keyboard too and left a 15px circle whose entire
       focus signal was a 1px border changing colour. */
    const focus = rule(".hint-mark:focus-visible");
    expect(focus).toMatch(/outline:\s*2px solid/);
    expect(focus).not.toMatch(/outline:\s*none/);
    expect(CSS).not.toContain([".hint-mark:hover,", ".hint-mark:focus-visible {"].join("\n"));
  });

  it("is still a circle while it is focused", () => {
    /* The global :focus-visible rule sets border-radius: 4px, matches
       this element, and is declared later at equal specificity — so the
       mark squares off unless this rule restates the circle. */
    expect(rule(".hint-mark:focus-visible")).toMatch(/border-radius:\s*50%/);
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

describe("what the keys do", () => {
  /* `role="button"` is a promise to a screen reader that Enter and Space
     work. The mark kept that promise for neither until the toggle
     existed, which is a worse failure than having no role at all: the
     user is told there is something to press. */

  it("treats Enter and Space as the press", () => {
    expect(hintKeyAction("Enter")).toBe("toggle");
    expect(hintKeyAction(" ")).toBe("toggle");
  });

  it("keeps Escape as the way out", () => {
    /* Distinct from toggle on purpose: Escape closes, and closing
       something already closed is not the same as opening it. */
    expect(hintKeyAction("Escape")).toBe("close");
  });

  it("leaves every other key to the browser", () => {
    /* Tab above all — swallowing it would trap focus on the mark. */
    for (const key of ["Tab", "a", "ArrowDown", "Shift", "Spacebar"]) {
      expect(hintKeyAction(key)).toBe("ignore");
    }
  });
});

describe("the two calls holding a call site upright", () => {
  /* Neither can be exercised without a DOM, and neither is decoration:
     each is load-bearing for somewhere the mark is actually used. */

  it("stops Space from scrolling the page", () => {
    expect(handler("onKeyDown")).toContain("event.preventDefault()");
  });

  it("stops a click from reaching the label that owns an input", () => {
    /* At `DeploymentForm` and `TrafficEditor` the mark renders inside a
       `<label>` wrapping a checkbox or a number box. A click that gets
       to the label activates that control, so pointing at the
       explanation would toggle the setting being explained. */
    expect(handler("onClick")).toContain("event.preventDefault()");
  });
});
