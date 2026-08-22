/** The evidence panel's decisions, tested apart from its markup.
 *
 * What these guard: the two ways to have no decomposition are told
 * apart; "the detectors found nothing" is not rendered as "the
 * detectors never ran"; a lattice verdict that rules a component out is
 * a finding rather than a shrug; and the strongest statements are met
 * first.
 */

import { describe, expect, it } from "vitest";

import type {
  ExplanationView,
  PacketLatticeFinding,
  PacketObservation,
  PacketWaterfall,
} from "@/lib/decisions";
import {
  firedSightings,
  missingNotes,
  orderedFindings,
  sightingsState,
  verdictTone,
  waterfallState,
  widestContribution,
} from "@/lib/evidence";

function observation(overrides: Partial<PacketObservation> = {}): PacketObservation {
  return {
    type: "stuck_cluster",
    candidate_id: "cand_a",
    episodes_seen: 0,
    episodes_total: 30,
    typical: {},
    worst_episode_context_id: null,
    ...overrides,
  };
}

function finding(verdict: string, detection_type: string): PacketLatticeFinding {
  return { detection_type, verdict, subject: null, pairs: [], reason: "because" };
}

function waterfall(contributions: number[]): PacketWaterfall {
  return {
    candidate_a: "cand_a",
    candidate_b: "cand_b",
    n_episodes: 30,
    delta_utility_mean: 0.1,
    delta_utility_median: 0.09,
    total_ci95: [0.02, 0.18],
    bars: contributions.map((contribution, index) => ({
      objective: `U_${index}`,
      weight: 0.25,
      delta_objective_mean: contribution * 4,
      contribution,
      ci95: [contribution - 0.01, contribution + 0.01] as [number, number],
    })),
  };
}

describe("why there is no decomposition", () => {
  it("tells a run that ranked nobody from a plan that withholds one", () => {
    // Two different facts. One is "there was no pair"; the other is the
    // panel matrix refusing to draw a pair that exists.
    expect(waterfallState(null, true)).toBe("run-ranked-nobody");
    expect(waterfallState(waterfall([0.1]), false)).toBe("plan-forbids");
  });

  it("says nothing is wrong when one is being drawn", () => {
    expect(waterfallState(waterfall([0.1]), true)).toBe("none");
  });
});

describe("what the sightings section is saying", () => {
  it("separates a clean run from a run nobody could look at", () => {
    // Both render an empty table and they mean opposite things.
    expect(sightingsState([])).toBe("no-traces");
    expect(sightingsState([observation()])).toBe("clean");
  });

  it("reports sightings when a detector fired", () => {
    expect(sightingsState([observation({ episodes_seen: 4 })])).toBe("some");
  });

  it("keeps only the patterns that actually appeared", () => {
    const rows = firedSightings([
      observation({ episodes_seen: 0 }),
      observation({ type: "detour", episodes_seen: 7 }),
    ]);
    expect(rows.map((row) => row.type)).toEqual(["detour"]);
  });
});

describe("lattice verdicts", () => {
  it("does not paint a finding in the same grey as a shrug", () => {
    // "Both stacks do this, so it is not the component" is a result.
    expect(verdictTone("rules_out_component_specific_attribution")).toBe("warn");
    expect(verdictTone("insufficient_contrast")).toBe("muted-badge");
    expect(verdictTone("supports_component_specific_attribution")).toBe("ok");
  });

  it("falls back quietly for a verdict this build has not seen", () => {
    expect(verdictTone("something_added_later")).toBe("muted-badge");
  });

  it("puts the statements before the refusals", () => {
    const ordered = orderedFindings([
      finding("insufficient_contrast", "detour"),
      finding("supports_component_specific_attribution", "latency_spike"),
      finding("rules_out_component_specific_attribution", "stuck_cluster"),
      finding("interaction_not_isolated", "oscillation"),
    ]);
    expect(ordered.map((item) => item.detection_type)).toEqual([
      "latency_spike",
      "stuck_cluster",
      "oscillation",
      "detour",
    ]);
  });

  it("breaks ties by detection type so the order is stable", () => {
    const ordered = orderedFindings([
      finding("insufficient_contrast", "oscillation"),
      finding("insufficient_contrast", "detour"),
    ]);
    expect(ordered.map((item) => item.detection_type)).toEqual(["detour", "oscillation"]);
  });

  it("does not mutate what it was given", () => {
    const input = [
      finding("insufficient_contrast", "detour"),
      finding("supports_component_specific_attribution", "latency_spike"),
    ];
    orderedFindings(input);
    expect(input[0].detection_type).toBe("detour");
  });
});

describe("what could not be built", () => {
  it("labels a skipped episode apart from a missing part", () => {
    const view = {
      omissions: ["representative_episodes: no per-episode utility"],
      skipped_episodes: ["cand_a/ep-009: trace has no samples"],
    } as ExplanationView;
    expect(missingNotes(view)).toEqual([
      { note: "representative_episodes: no per-episode utility", kind: "omission" },
      { note: "cand_a/ep-009: trace has no samples", kind: "skipped" },
    ]);
  });
});

describe("bar scaling", () => {
  it("never divides by zero when every bar is flat", () => {
    expect(widestContribution(waterfall([0, 0, 0]))).toBeGreaterThan(0);
  });

  it("scales by the widest bar in either direction", () => {
    expect(widestContribution(waterfall([0.02, -0.31, 0.05]))).toBeCloseTo(0.31);
  });
});
