/** The end-of-run comparison rows.
 *
 * What this file defends: that the numbers come from where the platform
 * put them, that "not recorded" never renders as a measurement, and that
 * the highlighting does not name a winner where there is not one. All
 * three are invisible in a screenshot — a wrong cell and a right cell
 * look identical.
 */

import { describe, expect, it } from "vitest";

import type { EpisodeOutcome, RunCandidate } from "@/lib/decisions";
import {
  comparisonRows,
  failureBreakdown,
  leaders,
  medianTravelTime,
  worstClearance,
} from "@/lib/candidateMetrics";

function episode(overrides: Partial<EpisodeOutcome> = {}): EpisodeOutcome {
  return {
    episode_context_id: "ep",
    success: true,
    failure_reason: null,
    collision_count: 0,
    min_clearance: 0.5,
    travel_time_s: 20,
    p99_latency_ms: 8,
    replan_count: 1,
    episode_decision_utility: 0.8,
    ...overrides,
  } as EpisodeOutcome;
}

function candidate(overrides: Partial<RunCandidate> = {}): RunCandidate {
  return {
    candidate_id: "cand",
    stack_label: "astar+dwa",
    local_controller_config: "dwa_coarse",
    gates: {
      G1: { result: "pass", no_path_rate: 0.0, threshold: 0.02 },
      G2: { result: "pass", observed: 0, upper_bound_95: 0.1, n_distinct_episodes: 30 },
      G3: { result: "pass", threshold: 0.95 },
      G4: { result: "pass", p99_ms: 7.35, threshold_ms: 50 },
      G5: { result: "pass", memory_estimate_mb: 8.0, available_ram_mb: 3277 },
      G6: "pass",
    },
    cleared_gates: true,
    blocking_gates: [],
    n_distinct_episodes: 30,
    success_rate: 1,
    pooled_p99_latency_ms: 7.35,
    replan_count: 30,
    episodes: [episode()],
    ...overrides,
  } as RunCandidate;
}

const rowFor = (rows: ReturnType<typeof comparisonRows>, key: string) => {
  const found = rows.find((one) => one.key === key);
  if (!found) throw new Error(`no row ${key}`);
  return found;
};

describe("where the numbers come from", () => {
  const rows = comparisonRows([candidate()]);

  it("reads the collision count off G2 rather than counting episodes again", () => {
    // G2's verdict was decided on its own count. A second count taken
    // from the episode rows could disagree with the gate sitting beside
    // it, and both would render as "collisions".
    expect(rowFor(rows, "collisions").values[0]).toBe(0);
  });

  it("reads the no-path rate off G1 and the memory estimate off G5", () => {
    expect(rowFor(rows, "noPathRate").values[0]).toBe(0);
    expect(rowFor(rows, "memory").values[0]).toBe(8);
  });

  it("carries the deployment's own limit beside the value", () => {
    // "17.89 ms" means nothing without "50 ms". The threshold comes from
    // the gate too, so a deployment declaring a different control rate
    // shows a different limit.
    expect(rowFor(rows, "p99").threshold).toBe("50");
    expect(rowFor(rows, "successRate").threshold).toBe("0.95");
    expect(rowFor(rows, "memory").threshold).toBe("3277");
  });

  it("offers no decision-utility row", () => {
    // The card carries it for the winner only; a mean taken here would
    // be a second scoring path, which is the one thing this layer must
    // not become. ΔU and its interval live on the card.
    expect(rows.map((one) => one.key)).not.toContain("utility");
    expect(rows.map((one) => one.key)).not.toContain("decisionUtility");
  });
});

describe("not recorded is not zero", () => {
  it("renders an em dash where the run kept nothing", () => {
    // A run stored before episode rows existed has no clearance to
    // report. Rendering that as 0.000 m says the robot touched
    // something.
    const bare = candidate({ episodes: undefined, gates: {}, replan_count: undefined });
    const rows = comparisonRows([bare]);
    expect(rowFor(rows, "worstClearance").values[0]).toBeNull();
    expect(rowFor(rows, "worstClearance").text[0]).toBe("—");
    expect(rowFor(rows, "collisions").text[0]).toBe("—");
    expect(rowFor(rows, "replans").text[0]).toBe("—");
  });

  it("still reports a genuine zero as zero", () => {
    // The other half of the pair, so the test above cannot pass by
    // everything rendering as a dash.
    expect(rowFor(comparisonRows([candidate()]), "collisions").text[0]).toBe("0");
  });
});

describe("reductions over the episode column", () => {
  it("takes the worst clearance of the whole run, not the last one", () => {
    const c = candidate({
      episodes: [episode({ min_clearance: 0.5 }), episode({ min_clearance: 0.11 }), episode({ min_clearance: 0.4 })],
    });
    expect(worstClearance(c)).toBeCloseTo(0.11);
  });

  it("uses the median episode time, not the mean", () => {
    // One timeout parked at the deployment's cap drags a mean by tens of
    // seconds, and the number then describes the cap rather than the
    // stack.
    const c = candidate({
      episodes: [episode({ travel_time_s: 20 }), episode({ travel_time_s: 22 }), episode({ travel_time_s: 60 })],
    });
    expect(medianTravelTime(c)).toBe(22);
  });

  it("averages the middle pair on an even count", () => {
    const c = candidate({
      episodes: [episode({ travel_time_s: 10 }), episode({ travel_time_s: 20 })],
    });
    expect(medianTravelTime(c)).toBe(15);
  });

  it("counts only the failures, commonest first", () => {
    const c = candidate({
      episodes: [
        episode({ success: false, failure_reason: "timeout" }),
        episode({ success: true }),
        episode({ success: false, failure_reason: "timeout" }),
        episode({ success: false, failure_reason: "no_path" }),
      ],
    });
    expect(failureBreakdown(c)).toEqual([["timeout", 2], ["no_path", 1]]);
  });
});

describe("who leads a row", () => {
  const rows = (a: Partial<RunCandidate>, b: Partial<RunCandidate>, c?: Partial<RunCandidate>) =>
    comparisonRows([candidate(a), candidate(b), ...(c ? [candidate(c)] : [])]);

  it("gives a lower-is-better row to the smaller number", () => {
    const row = rowFor(rows({ pooled_p99_latency_ms: 7 }, { pooled_p99_latency_ms: 18 }), "p99");
    expect(leaders(row)).toEqual([0]);
  });

  it("gives a higher-is-better row to the larger number", () => {
    const row = rowFor(rows({ success_rate: 0.9 }, { success_rate: 1 }), "successRate");
    expect(leaders(row)).toEqual([1]);
  });

  it("names both when two of three are equally best", () => {
    // With more than two candidates a single winner is sometimes a coin
    // toss rendered as a result.
    const row = rowFor(
      rows({ pooled_p99_latency_ms: 7 }, { pooled_p99_latency_ms: 7 }, { pooled_p99_latency_ms: 18 }),
      "p99",
    );
    expect(leaders(row)).toEqual([0, 1]);
  });

  it("names nobody when everyone ties", () => {
    const row = rowFor(rows({ success_rate: 1 }, { success_rate: 1 }), "successRate");
    expect(leaders(row)).toEqual([]);
  });

  it("names nobody on the replan row", () => {
    // Replanning is already charged in travel time and in latency, and
    // the deployment declares no replan budget. A green cell here would
    // price it twice against a rule nobody wrote down.
    const row = rowFor(rows({ replan_count: 3 }, { replan_count: 30 }), "replans");
    expect(row.direction).toBe("none");
    expect(leaders(row)).toEqual([]);
  });

  it("names nobody when only one candidate recorded the row", () => {
    // "Best of one" is not a comparison.
    const row = rowFor(
      rows({ episodes: [episode({ min_clearance: 0.4 })] }, { episodes: undefined }),
      "worstClearance",
    );
    expect(leaders(row)).toEqual([]);
  });

  it("does not call a winner on floating-point dust", () => {
    const row = rowFor(
      rows({ pooled_p99_latency_ms: 7.3500001 }, { pooled_p99_latency_ms: 7.35 }),
      "p99",
    );
    expect(leaders(row)).toEqual([]);
  });
});

describe("more than two candidates", () => {
  it("produces one value per candidate on every row", () => {
    // The comparison used to draw the first two and drop the rest. Every
    // row has to widen with the run, or a third stack renders as a
    // column of blanks.
    const rows = comparisonRows([candidate(), candidate(), candidate()]);
    for (const row of rows) {
      expect(row.values).toHaveLength(3);
      expect(row.text).toHaveLength(3);
    }
  });

  it("produces no rows at all for no candidates", () => {
    expect(comparisonRows([]).every((row) => row.values.length === 0)).toBe(true);
  });
});
