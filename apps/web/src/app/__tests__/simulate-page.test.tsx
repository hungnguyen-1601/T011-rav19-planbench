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

describe("field notes sit in the mark beside the name", () => {
  const PAGE = readFileSync(join(process.cwd(), "src", "app", "simulate", "page.tsx"), "utf8");
  const PICKER = readFileSync(
    join(process.cwd(), "src", "components", "CandidatePicker.tsx"),
    "utf8",
  );
  const setup = PAGE.slice(PAGE.indexOf("simulate-setup-grid"), PAGE.indexOf("simulate-run-actions"));

  it("carries no prose under the controls", () => {
    /* Three paragraphs of grey text under five dropdowns is most of the
       panel's height spent on sentences a reader needs once. The rest of
       the app puts them behind a mark; this row was the exception. */
    expect(setup).not.toContain("<small>");
    expect(PICKER).not.toContain("<small>");
  });

  it("keeps every note that existed, behind its own mark", () => {
    /* Moved, not deleted: each one still names the key it always had. */
    for (const key of ["bench.help.deployment", "bench.help.mission", "bench.seedNote"]) {
      expect(setup).toContain(key);
    }
    for (const key of ["bench.help.global", "bench.help.local"]) {
      expect(PICKER).toContain(key);
    }
    expect(setup.match(/<Hint /g) ?? []).toHaveLength(3);
  });

  it("invents no note for the field that never had one", () => {
    /* Configuration carries no hint text anywhere in the app. Writing
       one so three fields look alike would be copy filling a shape. */
    expect(PICKER).not.toContain("bench.help.config");
    const config = PICKER.slice(PICKER.indexOf("candidates.pick.config"));
    expect(config.slice(0, config.indexOf("</label>"))).not.toContain("<Hint");
  });

  it("labels each mark, so a row of them is not a row of question marks", () => {
    /* `Hint` takes the field's own name as its accessible label. */
    expect(setup).toContain('label={t("bench.deployment")}');
    expect(PICKER).toContain('label={t("candidates.pick.global")}');
  });
});

describe("the conditions say what counts as a pass", () => {
  const PAGE = readFileSync(join(process.cwd(), "src", "app", "simulate", "page.tsx"), "utf8");
  const CSS = readFileSync(join(process.cwd(), "src", "app", "globals.css"), "utf8");
  const conditions = PAGE.slice(
    PAGE.indexOf("deployment-conditions-grid"),
    PAGE.indexOf("deployment-condition-footer"),
  );

  it("carries the gate thresholds, which no other card did", () => {
    /* The other three say what the world *is* — where the robot starts,
       how fast it may go, what traffic is in it. A run that reaches the
       goal is not a run that cleared G3 unless the success floor is on
       screen. */
    for (const key of [
      "success_rate_min",
      "collision_probability_max",
      "no_path_rate_max",
      "clearance_warning_m",
      "stuck_threshold_s",
    ]) {
      expect(conditions).toContain(key);
    }
  });

  it("includes G5's threshold, which lives on the hardware block", () => {
    /* An allocation decision about the target board rather than a limit
       on the mission — and the one number here a reader cannot infer
       from anything else on the page. */
    expect(conditions).toContain("deployment.hardware?.available_ram_mb");
  });

  it("shows a rate as the percentage the gates are argued about", () => {
    /* The contract stores them 0..1 and every screen that discusses
       them says percent. Formatting at each call site is how one
       threshold reads 0.95 here and 95% two screens away. */
    expect(PAGE).toContain("function formatRate(");
    expect(conditions).toContain("formatRate(deployment.constraints?.success_rate_min)");
  });

  it("keeps one decimal, so two thresholds do not print as one", () => {
    /* `no_path_rate_max` defaults to 0.02; rounding to whole percent
       would show 0.02 and 0.024 as the same 2%. */
    expect(PAGE).toContain("(value * 100).toFixed(1)");
  });

  it("substitutes nothing for a field the profile never carried", () => {
    /* A default here would put a threshold on screen that nobody
       declared and the gates were never held to. */
    expect(PAGE).toContain('!Number.isFinite(value)\n    ? "—"');
  });

  it("does not colour the card as a verdict", () => {
    /* Thresholds are neither a good nor a bad reading — they are the
       line a reading will be held to. */
    expect(CSS).toContain("--condition-thresholds: var(--indigo);");
    expect(CSS).not.toContain("--condition-thresholds: var(--ok)");
    expect(CSS).not.toContain("--condition-thresholds: var(--err)");
  });

  it("lets the row hold four cards rather than stranding one", () => {
    /* It was `repeat(3, …)`, which would have dropped the new card onto
       a second row alone with three quarters of the width empty. */
    expect(CSS).toContain("repeat(auto-fit, minmax(210px, 1fr))");
  });
});
