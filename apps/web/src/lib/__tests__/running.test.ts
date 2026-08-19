/** The running comparison's presentation rules.
 *
 * The direction table is the reason this file exists. Highlighting "the
 * bigger number" is right for `safety_margin` and wrong for `elapsed_s`,
 * and both cells render identically — the mistake is invisible in a
 * screenshot and would tell a reader the slower run was the safer one.
 */

import { describe, expect, it } from "vitest";

import type { RunningPoint, RunningSample } from "@/lib/decisions";
import {
  PROGRESS_CLOCK,
  TIME_CLOCK,
  compositeCaveat,
  leader,
  rowAt,
} from "@/lib/running";

function sample(overrides: Partial<RunningSample> = {}): RunningSample {
  return {
    progress_fraction: 0.5,
    progress_rate: 0.8,
    elapsed_s: 10,
    safety_margin: 1.5,
    exposure_s: 0,
    compute_budget: 0.4,
    path_efficiency: 0.9,
    replans: 0,
    ...overrides,
  };
}

function point(progress: number, overrides: Partial<RunningPoint> = {}): RunningPoint {
  return {
    progress_m: progress,
    a: sample(),
    b: sample(),
    partial_advantage: 0,
    partial_objectives: ["U_S", "U_E"],
    ...overrides,
  };
}

function rowFor(key: keyof RunningSample) {
  const found = [...PROGRESS_CLOCK, ...TIME_CLOCK].find((row) => row.key === key);
  if (!found) throw new Error(`${key} is on neither clock`);
  return found;
}

describe("which direction is better", () => {
  it("gives the win to the faster run, not the larger number", () => {
    const row = rowFor("elapsed_s");
    expect(leader(row, sample({ elapsed_s: 8 }), sample({ elapsed_s: 12 }))).toBe("a");
  });

  it("gives the win to the run with more clearance", () => {
    const row = rowFor("safety_margin");
    expect(leader(row, sample({ safety_margin: 1.1 }), sample({ safety_margin: 2.4 }))).toBe("b");
  });

  it("treats a cheaper compute budget as better", () => {
    const row = rowFor("compute_budget");
    expect(leader(row, sample({ compute_budget: 0.3 }), sample({ compute_budget: 0.9 }))).toBe("a");
  });

  it("treats fewer replans as better", () => {
    const row = rowFor("replans");
    expect(leader(row, sample({ replans: 3 }), sample({ replans: 1 }))).toBe("b");
  });

  it("declares no winner when the two are the same", () => {
    expect(leader(rowFor("elapsed_s"), sample(), sample())).toBeNull();
  });

  it("does not call a winner on floating-point dust", () => {
    // A table where nobody ever ties teaches the reader to ignore it.
    const row = rowFor("path_efficiency");
    expect(leader(row, sample({ path_efficiency: 0.9 }), sample({ path_efficiency: 0.9000001 })))
      .toBeNull();
  });

  it("still calls a small but real difference on a small quantity", () => {
    // The tolerance scales, so 0.01 on a 0.9 ratio is a call, not dust.
    const row = rowFor("path_efficiency");
    expect(leader(row, sample({ path_efficiency: 0.91 }), sample({ path_efficiency: 0.9 })))
      .toBe("a");
  });
});

describe("the two clocks stay apart", () => {
  it("puts every metric on exactly one clock", () => {
    const keys = [...PROGRESS_CLOCK, ...TIME_CLOCK].map((row) => row.key);
    expect(new Set(keys).size).toBe(keys.length);
  });

  it("keeps worst-clearance off the equal-time clock", () => {
    // At one instant the two robots are in different parts of the map,
    // so their worst clearances are not about the same stretch of it.
    expect(TIME_CLOCK.map((row) => row.key)).not.toContain("safety_margin");
    expect(PROGRESS_CLOCK.map((row) => row.key)).toContain("safety_margin");
  });

  it("carries no planner-specific counter", () => {
    // A* expands nodes, RRT* grows a tree, a learned policy does
    // neither. A column only one of them can fill is a column that
    // reads as a zero for the others.
    const keys = [...PROGRESS_CLOCK, ...TIME_CLOCK].map((row) => String(row.key));
    for (const banned of ["expanded_nodes", "tree_size", "samples", "iterations"]) {
      expect(keys).not.toContain(banned);
    }
  });
});

describe("which rung is on screen", () => {
  const ladder = [point(2), point(4), point(6)];

  it("shows the last rung reached, not the next one coming", () => {
    expect(rowAt(ladder, 5)?.progress_m).toBe(4);
  });

  it("shows a rung the moment it is reached", () => {
    expect(rowAt(ladder, 4)?.progress_m).toBe(4);
  });

  it("shows nothing before the ladder starts", () => {
    expect(rowAt(ladder, 1)).toBeNull();
  });

  it("holds the last rung past the end", () => {
    expect(rowAt(ladder, 99)?.progress_m).toBe(6);
  });

  it("shows nothing for a comparison that has no rungs", () => {
    expect(rowAt([], 3)).toBeNull();
  });
});

describe("the composite never stands unqualified", () => {
  it("marks a two-objective composite as partial", () => {
    expect(compositeCaveat(point(2))).toBe("running.composite.partial");
  });

  it("would drop the caveat only if all four objectives were in it", () => {
    // Guards the branch rather than the constant: if a later change
    // makes U_R computable on a prefix, this is where the caveat stops.
    const full = point(2, { partial_objectives: ["U_S", "U_E", "U_R", "U_C"] });
    expect(compositeCaveat(full)).toBe("running.composite.full");
  });
});
