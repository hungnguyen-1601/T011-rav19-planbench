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

import { CONDITION_GROUPS, describeCondition } from "@/lib/benchConditions";


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
  const CSS = readFileSync(join(process.cwd(), "src", "app", "globals.css"), "utf8");
  /* The rows moved out of the page and into a table when four cards
     became seven, so what used to be asserted against a slice of JSX is
     asserted against the inventory itself. `bench-conditions.test.ts`
     is the other half: it checks that inventory against the pydantic
     schemas, which is the check a slice of JSX could never carry. */
  const paths = CONDITION_GROUPS.flatMap((group) => group.fields.map((field) => field.path));

  it("carries the gate thresholds, which no other card did", () => {
    /* The other cards say what the world *is* — where the robot starts,
       how fast it may go, what traffic is in it. A run that reaches the
       goal is not a run that cleared G3 unless the success floor is on
       screen. */
    for (const field of [
      "success_rate_min",
      "collision_probability_max",
      "no_path_rate_max",
      "clearance_warning_m",
      "stuck_threshold_s",
      "cost_per_mission_max",
    ]) {
      expect(paths).toContain(`constraints.${field}`);
    }
  });

  it("includes G5's threshold, which lives on the hardware block", () => {
    /* An allocation decision about the target board rather than a limit
       on the mission. It sits with the board now rather than with the
       thresholds: total minus the breakdown leaves available, and that
       arithmetic is only checkable if the six numbers are on one card. */
    const robot = CONDITION_GROUPS.find((group) => group.tone === "robot");
    expect(robot?.fields.map((field) => field.path)).toContain("hardware.available_ram_mb");
  });

  it("shows a rate as the percentage the gates are argued about", () => {
    /* The contract stores them 0..1 and every screen that discusses
       them says percent. One formatter for all of them is how a
       threshold avoids reading 0.95 here and 95% two screens away. */
    const rate = CONDITION_GROUPS.flatMap((group) => group.fields).find(
      (field) => field.path === "constraints.success_rate_min",
    );
    expect(rate?.kind).toBe("rate");
    expect(describeCondition(rate!, 0.95, (key) => key)).toEqual({
      state: "value",
      text: "95.0 %",
    });
  });

  it("substitutes nothing for a field the profile never carried", () => {
    /* A default here would put a threshold on screen that nobody
       declared and the gates were never held to — and a `0` would be
       worse, because it reads as a number somebody chose. */
    const stuck = CONDITION_GROUPS.flatMap((group) => group.fields).find(
      (field) => field.path === "constraints.stuck_threshold_s",
    );
    expect(describeCondition(stuck!, undefined, (key) => key)).toEqual({ state: "undeclared" });
  });

  it("does not colour the card as a verdict", () => {
    /* Thresholds are neither a good nor a bad reading — they are the
       line a reading will be held to. */
    expect(CSS).toContain("--condition-thresholds: var(--indigo);");
    expect(CSS).not.toContain("--condition-thresholds: var(--ok)");
    expect(CSS).not.toContain("--condition-thresholds: var(--err)");
  });

  it("lays the cards out in columns, so the seventh is not stranded", () => {
    /* It was `repeat(3, …)`, then an auto-fit grid that held four. A
       grid lays a fixed number of tracks, so seven cards across six put
       one alone on a second row with five sixths of the width empty.
       Multi-column has no tracks to leave empty, and balances cards
       whose row counts differ by ten. */
    const rule = CSS.slice(
      CSS.indexOf(".deployment-conditions-grid {"),
      CSS.indexOf(".deployment-condition-list {"),
    );
    expect(rule).toContain("columns: 260px 4;");
    expect(rule).toContain("break-inside: avoid;");
  });

  it("gives an undeclared value a mark of its own", () => {
    /* Filled chip for `Off`, outline for absent. Without the difference
       a reader cannot tell a decision from a silence. */
    expect(CSS).toContain(".condition-status.is-unset {");
    expect(CSS).toContain(".condition-status.is-off { color: var(--muted)");
  });
});

describe("the canvas follows the plan as it is replanned", () => {
  const PAGE = readFileSync(join(process.cwd(), "src", "app", "simulate", "page.tsx"), "utf8");
  const STREAM = readFileSync(
    join(process.cwd(), "src", "lib", "useEpisodeStream.ts"),
    "utf8",
  );
  const CANVAS = readFileSync(join(process.cwd(), "src", "components", "MapCanvas.tsx"), "utf8");

  it("keeps every route the socket sent, not just the opening one", () => {
    /* The socket used to send `plan_path` at `start` and nothing after
       it, so a replanning episode drew its first route for the whole
       run — a dashed line sitting still while the robot drove somewhere
       else. */
    expect(STREAM).toContain("setPlanRoutes(message.plans ?? [])");
    expect(STREAM).toContain("planRoutes,");
  });

  it("draws the route in force at the playhead", () => {
    expect(PAGE).toContain("const currentRoute = useMemo(");
    expect(PAGE).toContain("route.from_time > now");
    expect(PAGE).toContain("plannedPath={currentRoute?.points ??");
  });

  it("changes colour at every replan", () => {
    /* With one colour for all of them a reader scrubbing the timeline
       cannot tell "the plan bent" from "the plan was thrown away and a
       new one drawn", and only the second is a replan. Shared with the
       decisions canvas so an attempt is the same colour on both. */
    expect(PAGE).toContain("plannedRouteColour(currentRoute.attempt)");
    expect(CANVAS).toContain("plannedPathColour");
  });

  it("falls back to the opening plan rather than drawing nothing", () => {
    /* A server that predates the field, and an episode whose replans
       could not be placed, both arrive with no routes — and the first
       plan is still true of the run. */
    expect(PAGE).toContain("stream.planPath.length > 0 ? stream.planPath : plan?.path");
  });

  it("drops the line for a refused attempt instead of keeping the last", () => {
    /* A refused replan has no route. Holding the previous one on screen
       would say the planner still had a plan it had just lost. */
    expect(PAGE).toContain("current.points.length > 0 ? current : null");
  });

  it("leaves the plan blue where no caller colours it", () => {
    /* Every other screen draws one plan and has nothing to distinguish
       it from. */
    expect(CANVAS).toContain("plannedPathColour ?? COLOR.plan");
  });
});
