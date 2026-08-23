/** The counting sentence, and the four ways of counting it wrongly.
 *
 * It restates the tinting, so the one thing it must never do is disagree
 * with the cells above it.
 */

import { describe, expect, it } from "vitest";

import { comparisonSummary } from "@/lib/comparisonSummary";
import { type MetricRow, comparisonRows, leaders } from "@/lib/candidateMetrics";
import type { RunCandidate } from "@/lib/decisions";

const row = (over: Partial<MetricRow>): MetricRow => ({
  key: "k",
  direction: "higher",
  values: [1, 2],
  numberText: ["1", "2"],
  ...over,
});

const candidate = (over: Partial<RunCandidate> = {}): RunCandidate =>
  ({
    candidate_id: "c",
    stack_label: "astar+dwa",
    local_controller_config: "dwa_coarse",
    n_distinct_episodes: 30,
    success_rate: 1,
    pooled_p99_latency_ms: 7.85,
    replan_count: 30,
    cleared_gates: true,
    blocking_gates: [],
    gates: { G2: { result: "pass", observed: 0, upper_bound_95: 0.1, n_distinct_episodes: 30 } },
    ...over,
  }) as unknown as RunCandidate;

describe("what the sentence counts", () => {
  it("credits the leader of each decided row", () => {
    const summary = comparisonSummary(
      [row({ values: [1, 2] }), row({ values: [5, 4] }), row({ values: [1, 2] })],
      2,
    );
    expect(summary).toEqual({ wins: [1, 2], ties: 0, total: 3 });
  });

  it("counts a genuine tie as a tie", () => {
    expect(comparisonSummary([row({ values: [3, 3] })], 2)).toEqual({
      wins: [0, 0],
      ties: 1,
      total: 1,
    });
  });

  it("does not count an unmeasured row as a tie", () => {
    /* A tie is a comparison that came out level. A row where one side
       recorded nothing was never compared, and folding it into the ties
       inflates the agreement between two stacks using a row that says
       nothing about either. */
    const summary = comparisonSummary([row({ values: [1, 2] }), row({ values: [1, null] })], 2);
    expect(summary).toEqual({ wins: [0, 1], ties: 0, total: 1 });
  });

  it("does not count a row the table marks nobody on", () => {
    /* `replans` has no direction: it is already charged in travel time
       and in latency, and no deployment declares a replan budget.
       Counting it would let a candidate lead a row the table
       deliberately leaves unmarked. */
    const summary = comparisonSummary(
      [row({ values: [1, 2] }), row({ direction: "none", values: [30, 242] })],
      2,
    );
    expect(summary?.total).toBe(1);
  });

  it("keeps wins and ties adding up to the rows it counted", () => {
    const summary = comparisonSummary(
      [
        row({ values: [1, 2] }),
        row({ values: [2, 2] }),
        row({ values: [null, 2] }),
        row({ direction: "none", values: [1, 2] }),
      ],
      2,
    )!;
    expect(summary.wins[0] + summary.wins[1] + summary.ties).toBe(summary.total);
  });
});

describe("when there is no sentence to write", () => {
  it("says nothing for one candidate or for three", () => {
    /* "A leads on four, B on two" has no room for C, and listing three
       would be a different sentence rather than the same one with a
       number changed. */
    for (const count of [1, 3, 4]) {
      expect(comparisonSummary([row({})], count)).toBeNull();
    }
  });

  it("says nothing when nothing was comparable", () => {
    /* "leads on 0 of 0" is worse than no sentence at all. */
    expect(comparisonSummary([row({ values: [null, null] })], 2)).toBeNull();
    expect(comparisonSummary([row({ direction: "none" })], 2)).toBeNull();
    expect(comparisonSummary([], 2)).toBeNull();
  });
});

describe("against the table it summarises", () => {
  it("agrees with the cells the grid tints", () => {
    /* The sentence and the tinting come from one `leaders()`. This walks
       the real rows and checks the totals match the marks. */
    const rows = comparisonRows([
      candidate({ candidate_id: "a", success_rate: 1, pooled_p99_latency_ms: 7.85 }),
      candidate({ candidate_id: "b", success_rate: 0.633, pooled_p99_latency_ms: 17.2 }),
    ]);
    const summary = comparisonSummary(rows, 2)!;
    const tinted = rows.filter((r) => leaders(r).length > 0);
    expect(summary.wins[0] + summary.wins[1]).toBe(tinted.length);
    expect(summary.total).toBeGreaterThan(0);
  });
});
