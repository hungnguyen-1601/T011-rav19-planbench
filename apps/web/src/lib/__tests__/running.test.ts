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
  isRulerArtefact,
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

describe("when a candidate's own path is the ruler", () => {
  // A run recorded before the planning-input sidecar has no plan to
  // project onto, so E2 falls back to one candidate's driven path. That
  // candidate's progress then equals its distance driven at every
  // sample, and `path_efficiency` — the ratio of the two — reads 1.000
  // however badly it drove. Measured on a real 19-08 run: 1.000 against
  // the other stack's 0.860.
  const efficiency = rowFor("path_efficiency");

  it("marks the reference candidate's efficiency as an artefact", () => {
    expect(isRulerArtefact(efficiency, "a", "a")).toBe(true);
    expect(isRulerArtefact(efficiency, "b", "a")).toBe(false);
  });

  it("marks nothing when the reference was a recorded plan", () => {
    expect(isRulerArtefact(efficiency, "a", null)).toBe(false);
    expect(isRulerArtefact(efficiency, "b", null)).toBe(false);
  });

  it("leaves the other metrics alone", () => {
    // Only efficiency is defined as progress over distance driven. The
    // ruler does not make elapsed time or clearance unmeasurable.
    expect(isRulerArtefact(rowFor("elapsed_s"), "a", "a")).toBe(false);
    expect(isRulerArtefact(rowFor("safety_margin"), "a", "a")).toBe(false);
  });

  it("declares no winner on a row the ruler cannot lose", () => {
    // The whole point. Without this the panel awards a green 1.000 to
    // whichever candidate happened to be passed to the view first — a
    // result on a comparison that was never made.
    const ruled = sample({ path_efficiency: 1 });
    const other = sample({ path_efficiency: 0.86 });
    expect(leader(efficiency, ruled, other, "a")).toBeNull();
    expect(leader(efficiency, other, ruled, "b")).toBeNull();
  });

  it("still calls that row when the reference was a real plan", () => {
    // Otherwise the fix would suppress the metric everywhere and the
    // test above would pass by the column being dead.
    const ruled = sample({ path_efficiency: 1 });
    const other = sample({ path_efficiency: 0.86 });
    expect(leader(efficiency, ruled, other, null)).toBe("a");
  });

  it("still calls the other rows on a ruled run", () => {
    expect(leader(rowFor("elapsed_s"), sample({ elapsed_s: 8 }), sample({ elapsed_s: 12 }), "a"))
      .toBe("a");
  });
});
