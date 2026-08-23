/** The test bench's episode setup, checked the way this repo can.
 *
 * No jsdom, so what is asserted is the stylesheet rule that decides
 * whether five controls across three fieldsets land on one line — which
 * is the thing that was wrong, and the thing a screenshot would show
 * and a component test would not.
 */

import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";


describe("the episode setup keeps its controls on one line", () => {
  const CSS = readFileSync(join(process.cwd(), "src", "app", "globals.css"), "utf8");
  const rule = CSS.slice(
    CSS.indexOf("label.field.simulate-field,"),
    CSS.indexOf(".simulate-page select,"),
  );

  it("pins the label and the control to their own rows", () => {
    /* `.candidate-picker-field` is a grid whose rows stretched to the
       height of its cell, so the one field with no hint under it —
       Configuration — split the slack between label and select and
       pushed its select below its neighbours', while a two-line hint
       put another one somewhere else again. */
    expect(rule).toContain("grid-template-rows: auto auto 1fr;");
    expect(rule).toContain("align-content: start;");
  });

  it("covers both kinds of field, not one group at a time", () => {
    /* They sit in one row across three fieldsets. A rule for only one
       of them aligns each group with itself and with nothing else. */
    expect(rule).toContain("label.field.simulate-field");
    expect(rule).toContain(".candidate-picker--detailed .candidate-picker-field");
  });

  it("names the element, because a bare class loses to label.field", () => {
    /* `label.field` sets `display: flex` and outranks `.simulate-field`,
       so the template would be written and never applied. */
    expect(CSS).toContain("label.field {");
    expect(rule).not.toMatch(/^\.simulate-field,/m);
  });

  it("gives every control in the panel one height", () => {
    /* Two selects of different heights on one row is the same ragged
       line by another route. */
    expect(CSS).toContain(".simulate-page input[type=\"number\"] { min-height: 38px; }");
  });
});
