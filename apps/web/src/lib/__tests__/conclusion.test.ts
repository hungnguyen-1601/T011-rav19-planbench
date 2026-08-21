/** What the conclusion block may claim.
 *
 * Every case here is about *not overstating*, and none of them is
 * visible in a screenshot — a wrong headline and a right one render
 * identically.
 *
 * The one that matters most: a candidate that failed a gate can carry a
 * higher utility than one that passed, because collisions are excluded
 * from `U_S` by contract (HĐ-6) and no objective reflects a missing
 * observation channel. A single ranked list would put it on top.
 */

import { describe, expect, it } from "vitest";

import type { DecisionCard, DecisionRun, RunCandidate } from "@/lib/decisions";
import {
  collisionGateReason,
  invisibleFailures,
  marginIsConclusive,
  outOf100,
  standings,
  verdictOf,
} from "@/lib/conclusion";

function candidate(overrides: Partial<RunCandidate> = {}): RunCandidate {
  return {
    candidate_id: "cand_a",
    stack_label: "astar+dwa",
    local_controller_config: "dwa_coarse",
    gates: {},
    cleared_gates: true,
    blocking_gates: [],
    n_distinct_episodes: 30,
    success_rate: 1,
    pooled_p99_latency_ms: 7.35,
    decision_utility: 0.8,
    recommendation_eligible: true,
    ...overrides,
  } as RunCandidate;
}

function run(card: Partial<DecisionCard> | null): DecisionRun {
  return { card: card as DecisionCard | null } as DecisionRun;
}

describe("the line no ranking may cross", () => {
  it("keeps a blocked candidate below an eligible one it outscores", () => {
    // The reason this module exists. A stack that collided is excluded
    // at G2 and its collision appears nowhere in the utility, so it can
    // outscore a stack that drove clean. One ranked list would crown it.
    const { eligible, blocked } = standings([
      candidate({ candidate_id: "clean", decision_utility: 0.62 }),
      candidate({
        candidate_id: "collided",
        decision_utility: 0.91,
        cleared_gates: false,
        recommendation_eligible: false,
        blocking_gates: ["G2"],
      }),
    ]);
    expect(eligible.map((entry) => entry.candidateId)).toEqual(["clean"]);
    expect(blocked.map((entry) => entry.candidateId)).toEqual(["collided"]);
  });

  it("ranks by utility inside a group", () => {
    const { eligible } = standings([
      candidate({ candidate_id: "b", decision_utility: 0.5 }),
      candidate({ candidate_id: "a", decision_utility: 0.9 }),
    ]);
    expect(eligible.map((entry) => entry.candidateId)).toEqual(["a", "b"]);
  });

  it("puts an unscored candidate last rather than treating it as zero", () => {
    // "Not measured" is not the worst result; sorting it like one says
    // the run went badly when the run said nothing.
    const { eligible } = standings([
      candidate({ candidate_id: "unscored", decision_utility: null }),
      candidate({ candidate_id: "poor", decision_utility: 0.05 }),
    ]);
    expect(eligible.map((entry) => entry.candidateId)).toEqual(["poor", "unscored"]);
  });

  it("falls back to the gate verdict on a run stored before the flag existed", () => {
    const { eligible, blocked } = standings([
      candidate({ candidate_id: "old", recommendation_eligible: undefined, cleared_gates: false }),
    ]);
    expect(eligible).toHaveLength(0);
    expect(blocked.map((entry) => entry.candidateId)).toEqual(["old"]);
  });
});

describe("the mark out of 100", () => {
  it("keeps one decimal so a real difference does not render as a tie", () => {
    // 0.8774 and 0.8770 both round to 88. ΔU can tell those apart, and
    // an integer mark would say they are the same.
    expect(outOf100(0.8774)).toBe("87.7");
    expect(outOf100(0.877)).toBe("87.7");
    expect(outOf100(0.884)).toBe("88.4");
  });

  it("has no mark for a candidate that was not scored", () => {
    // `0 / 100` reads as the worst possible result rather than an
    // absent one.
    expect(outOf100(null)).toBeNull();
    expect(outOf100(Number.NaN)).toBeNull();
  });

  it("renders the ends of the scale", () => {
    expect(outOf100(0)).toBe("0.0");
    expect(outOf100(1)).toBe("100.0");
  });
});

describe("what the page may claim", () => {
  it("takes the winner from the card, never from the top of the list", () => {
    // `HĐ-10.1` refuses a Pareto-dominated candidate even when it leads
    // on utility, so `standings[0]` is not the recommendation.
    const verdict = verdictOf(
      run({
        status: "CLEAR_RECOMMENDATION",
        recommended: { candidate_id: "winner", stack: "astar+dwa", params_ref: null },
        evidence: { delta_u_mean: 0.039, ci95: [0.0365, 0.0418] } as DecisionCard["evidence"],
      }),
    );
    expect(verdict).toMatchObject({ kind: "recommended", candidateId: "winner" });
  });

  it("never names a winner when the field could not be separated", () => {
    const verdict = verdictOf(
      run({
        status: "NEAR_EQUIVALENT",
        recommended: { candidate_id: "a", stack: "astar+dwa", params_ref: null },
      }),
    );
    expect(verdict.kind).toBe("near-equivalent");
  });

  it("reads a run with no card as a result, not as a gap", () => {
    expect(verdictOf(run(null)).kind).toBe("no-card");
  });
});

describe("whether the margin says anything", () => {
  it("calls an interval clear of zero conclusive", () => {
    expect(marginIsConclusive([0.0365, 0.0418])).toBe(true);
    expect(marginIsConclusive([-0.04, -0.01])).toBe(true);
  });

  it("refuses one that straddles zero", () => {
    // Consistent with the two being equal. Printing the mean alone
    // turns that into a result.
    expect(marginIsConclusive([-0.002, 0.006])).toBe(false);
    expect(marginIsConclusive(null)).toBe(false);
  });
});

describe("the failures the number cannot see", () => {
  const blockedBy = (gates: string[], payload?: Record<string, unknown>) =>
    standings([
      candidate({
        cleared_gates: false,
        recommendation_eligible: false,
        blocking_gates: gates,
      }),
    ]).blocked[0];

  it("names G6, which no objective reflects", () => {
    expect(invisibleFailures(blockedBy(["G6"]))).toEqual(["G6"]);
  });

  it("says nothing for failures the objectives do carry", () => {
    // G3 lands in U_R and G4 in U_C, so the mark already moved for them.
    expect(invisibleFailures(blockedBy(["G3", "G4"]))).toEqual([]);
  });

  it("treats a G2 collision as invisible to the mark", () => {
    // Collisions are excluded from U_S by contract, so this candidate's
    // mark cannot see the thing that disqualified it.
    const gates = { G2: { result: "fail", observed: 2, n_distinct_episodes: 30 } };
    expect(invisibleFailures(blockedBy(["G2"]), gates)).toEqual(["G2"]);
  });

  it("does not flag a G2 that failed for sample size", () => {
    // Measured on a real run 2026-08-21: both candidates "blocked: G2"
    // with **zero collisions** — 5 distinct episodes against 30
    // required. Nothing hid from the mark; there is just not enough of
    // it. Flagging this the same way would tell a reader the stack hit
    // something.
    const gates = { G2: { result: "fail", observed: 0, n_distinct_episodes: 5, n_min: 30 } };
    expect(invisibleFailures(blockedBy(["G2"]), gates)).toEqual([]);
  });

  it("assumes the worse reading when the gate payload is missing", () => {
    // An old run carrying a bare "fail" cannot be shown to be the safe
    // case, and guessing the safe one is the guess that misleads.
    expect(invisibleFailures(blockedBy(["G2"]))).toEqual(["G2"]);
  });
});

describe("which of the two G2 failures happened", () => {
  const blockedBy = (gates: string[], payload?: Record<string, unknown>) => ({
    standing: standings([
      candidate({ cleared_gates: false, recommendation_eligible: false, blocking_gates: gates }),
    ]).blocked[0],
    payload,
  });

  it("tells a collision from a sample that was too small", () => {
    // Opposite messages under one label: "it hit something" versus
    // "nobody looked long enough to know".
    const collided = blockedBy(["G2"], { G2: { observed: 1 } });
    const thin = blockedBy(["G2"], { G2: { observed: 0, n_distinct_episodes: 5, n_min: 30 } });
    expect(collisionGateReason(collided.standing, collided.payload)).toBe("collided");
    expect(collisionGateReason(thin.standing, thin.payload)).toBe("sample-too-small");
  });

  it("says nothing when G2 is not what blocked it", () => {
    const other = blockedBy(["G4"], { G2: { observed: 0 } });
    expect(collisionGateReason(other.standing, other.payload)).toBeNull();
  });
});
