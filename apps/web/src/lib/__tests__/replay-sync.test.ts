/** Behaviour, not source text.
 *
 * The pairing defect these cover slipped through a full page of
 * source-string assertions: `candidates.slice(0, 2)` and the exemplar
 * fetch both existed, both spelled correctly, and they were about
 * different candidates. Strings cannot catch that; calling the function
 * can.
 */

import { describe, expect, it } from "vitest";

import type { DecisionRun, ReplaySyncView, RunCandidate } from "@/lib/decisions";
import { commonProgress, comparedPair, panelCandidates, sideTime } from "@/lib/replaySync";

function candidate(id: string): RunCandidate {
  return {
    candidate_id: id,
    stack_label: `stack ${id}`,
    local_controller_config: "dwa",
    gates: {},
    cleared_gates: true,
    blocking_gates: [],
    n_distinct_episodes: 30,
    success_rate: 1,
    pooled_p99_latency_ms: 20,
  };
}

function run(
  pair: { recommended_candidate_id: string; runner_up_candidate_id: string } | null,
  candidates: RunCandidate[],
  card: unknown = CARD_WITHOUT_ALTERNATIVE,
): DecisionRun {
  return {
    report: { candidates, decision_card: card, comparison_pair: pair },
    card,
  } as unknown as DecisionRun;
}

/** What an ordinary ranked run's card looks like: `alternative` is null
 *  unless a Pareto analysis ran, so it can never carry the runner-up. */
const CARD_WITHOUT_ALTERNATIVE = {
  recommended: { candidate_id: "winner" },
  alternative: null,
};

const PAIR = { recommended_candidate_id: "winner", runner_up_candidate_id: "runner_up" };

describe("which two candidates the page is about", () => {
  it("takes the pair the statistics used, not the first two in the list", () => {
    // Registration order puts an eliminated candidate first — exactly
    // the case where "the first two" and "the two compared" differ.
    const candidates = [candidate("eliminated"), candidate("runner_up"), candidate("winner")];

    expect(comparedPair(run(PAIR, candidates))).toEqual(["winner", "runner_up"]);
    expect(panelCandidates(run(PAIR, candidates), candidates).map((c) => c.candidate_id)).toEqual([
      "winner",
      "runner_up",
    ]);
  });

  it("puts the winner on the left, whatever order the report used", () => {
    const candidates = [candidate("runner_up"), candidate("winner")];
    expect(panelCandidates(run(PAIR, candidates), candidates)[0].candidate_id).toBe("winner");
  });

  it("has no pair when the run ranked nobody", () => {
    // No recorded pair means no winner — a run that ranked nobody, or
    // one scored before the field existed. Naming one anyway is how
    // "best for A" ends up over a candidate that lost.
    const candidates = [candidate("a"), candidate("b"), candidate("c")];
    expect(comparedPair(run(null, candidates))).toBeNull();
    expect(panelCandidates(run(null, candidates), candidates).map((c) => c.candidate_id)).toEqual([
      "a",
      "b",
    ]);
  });

  it("ignores the card's alternative, which is a different claim", () => {
    // HĐ-12: `alternative` may only be a PARETO_FRONTIER candidate. An
    // ordinary ranked run has none, and a Pareto run can have one that
    // ΔU was never computed against — so the pair never comes from
    // there, even when something is sitting in it.
    const paretoCard = {
      recommended: { candidate_id: "winner" },
      alternative: { candidate_id: "somebody_else" },
    };
    const candidates = [candidate("winner"), candidate("runner_up"), candidate("somebody_else")];

    expect(comparedPair(run(PAIR, candidates, paretoCard))).toEqual(["winner", "runner_up"]);
    expect(comparedPair(run(null, candidates, paretoCard))).toBeNull();
  });

  it("falls back rather than drawing one canvas when the pair is not in the report", () => {
    const candidates = [candidate("a"), candidate("b")];
    expect(panelCandidates(run(PAIR, candidates), candidates).map((c) => c.candidate_id)).toEqual([
      "a",
      "b",
    ]);
  });
});

function view(rows: ReplaySyncView["plan"]["rows"]): ReplaySyncView {
  return {
    episode_context_id: "ctx",
    candidate_a: "winner",
    candidate_b: "runner_up",
    plan: {
      reference: { points: [], quality: "degraded_candidate_path" },
      rows,
      backward_samples_a: 0,
      backward_samples_b: 0,
      warning: "same place is not the same situation",
    },
    divergence: { sustained: null, anchors: [] },
    reference_source_candidate_id: "winner",
    // These fixtures predate E4.3 and are about alignment, not about
    // the running metrics. `null` is what the server sends when the
    // comparison could not be built, so it is the honest default here.
    running: null,
  };
}

const ROWS = [
  { progress_m: 0, time_a: 0, time_b: 0, cross_track_a: 0, cross_track_b: 0 },
  { progress_m: 5, time_a: 5, time_b: 10, cross_track_a: 0, cross_track_b: 0.4 },
  { progress_m: 10, time_a: 10, time_b: null, cross_track_a: 0, cross_track_b: null },
];

describe("where each run is at one arc length", () => {
  it("gives the two panels different timestamps on purpose", () => {
    expect(sideTime(view(ROWS), 5, "a")).toBe(5);
    expect(sideTime(view(ROWS), 5, "b")).toBe(10);
  });

  it("holds the last rung it reached rather than jumping ahead", () => {
    expect(sideTime(view(ROWS), 7, "a")).toBe(5);
  });

  it("draws nothing new for a run that never got there", () => {
    // `null` is "this run stopped short", and inventing a timestamp
    // would put a robot somewhere it never was.
    expect(sideTime(view(ROWS), 10, "b")).toBe(0);
  });

  it("stops the slider where both runs still have ground", () => {
    expect(commonProgress(view(ROWS))).toBe(5);
  });

  it("has nowhere to be before the view arrives", () => {
    expect(sideTime(null, 3, "a")).toBe(0);
  });
});
