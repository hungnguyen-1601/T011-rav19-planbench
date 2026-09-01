/** The insights and the bars, rendered.
 *
 * `renderToStaticMarkup` covers first render with no browser, which is
 * where every claim below lives (`docs/reference/KNOWN_LIMITATIONS.md`).
 */

import { readFileSync } from "node:fs";
import { join } from "node:path";

import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { TradeoffInsights } from "@/components/TradeoffInsights";
import type { DecisionRun, RunCandidate } from "@/lib/decisions";

const CSS = readFileSync(join(process.cwd(), "src", "app", "globals.css"), "utf8");
const CONCLUSION = readFileSync(
  join(process.cwd(), "src", "components", "ConclusionPanel.tsx"),
  "utf8",
);

const candidate = (id: string, over: Partial<RunCandidate> = {}): RunCandidate =>
  ({
    candidate_id: id,
    stack_label: id,
    local_controller_config: "dwa_coarse",
    local_observation_class: "lidar_only",
    n_distinct_episodes: 30,
    success_rate: 1,
    pooled_p99_latency_ms: 7.85,
    replan_count: 30,
    cleared_gates: true,
    blocking_gates: [],
    gates: {
      G1: { result: "pass", no_path_rate: 0 },
      G2: { result: "pass", observed: 0, upper_bound_95: 0.1, n_distinct_episodes: 30 },
      G5: { result: "pass", memory_estimate_mb: 8 },
    },
    episodes: [
      { episode_context_id: "e1", success: true, min_clearance: 0.47, travel_time_s: 22.5 },
    ],
    ...over,
  }) as unknown as RunCandidate;

const draw = (candidates: RunCandidate[]) =>
  renderToStaticMarkup(
    <TradeoffInsights run={{ id: "r", report: { candidates } } as unknown as DecisionRun} />,
  );

const sweep = () => [
  candidate("astar+dwa"),
  candidate("rrtstar+dwa", {
    success_rate: 0.633,
    pooled_p99_latency_ms: 17.2,
    episodes: [
      { episode_context_id: "e1", success: false, min_clearance: 0.133, travel_time_s: 40 },
    ],
  } as Partial<RunCandidate>),
];

describe("the panel reads the table for the reader", () => {
  it("states that there is no trade-off rather than rendering nothing", () => {
    const html = draw(sweep());
    expect(html).toContain("No trade-off to weigh");
    expect(html).toContain("astar+dwa");
  });

  it("names the rows each insight was read off", () => {
    /* So a claim is checkable against the table above rather than taken
       on trust. */
    expect(draw(sweep())).toContain("tradeoff-metrics");
  });

  it("draws nothing at all for a single candidate", () => {
    /* Every sentence here is comparative and a one-sided bar chart is a
       ruler with one mark on it. */
    expect(draw([candidate("astar+dwa")])).toBe("");
  });
});

describe("the bars carry their own scale", () => {
  it("says which ruler each bar used", () => {
    /* A normalised bar with no scale beside it is the chart equivalent
       of a percentage with no denominator. */
    const html = draw(sweep());
    expect(html).toContain("tradeoff-scale-note");
    expect(html).toContain("declared limit");
  });

  it("draws no bar for a row with no better end", () => {
    /* `replans` is evidence, not a score. */
    expect(draw(sweep())).not.toContain("Replans across the run</span>");
  });

  it("keeps the leader in its own colour rather than painting it green", () => {
    /* Green is spent on "better number" in the table below. Using it
       here as well would put identity and outcome on one swatch. */
    expect(CSS).toContain(".tradeoff-bar-fill.is-lead");
    expect(CSS).not.toMatch(/\.tradeoff-bar-fill\.is-lead \{[^}]*var\(--ok\)/);
  });
});

describe("the score panel stopped asking the reader to decode letters", () => {
  it("names each objective beside its symbol", () => {
    /* `u_R 1.00 u_S 1.00 u_E 0.57 u_C 0.96` is four hovers on the panel
       that exists to explain the mark above it. */
    expect(CONCLUSION).toContain("conclusion.objectiveName.");
  });

  it("hatches a blocked candidate's bar instead of greying it", () => {
    /* Grey reads as "scored low", and a blocked candidate can hold the
       higher mark — the score never entered into its elimination. */
    expect(CONCLUSION).toContain('standing.eligible ? "" : " is-blocked"');
    expect(CSS).toContain(".conclusion-bar.is-blocked > span");
  });
});
