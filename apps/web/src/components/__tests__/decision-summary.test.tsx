/** The summary and the advice, rendered.
 *
 * `renderToStaticMarkup` gives real HTML with no browser, which covers
 * first render — and first render is where every claim below lives
 * (`docs/KNOWN_LIMITATIONS.md`). `useTranslation` reads a context with a
 * default, so the markup comes out in English with no provider.
 */

import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { DecisionAdvice } from "@/components/DecisionAdvice";
import { DecisionSummary } from "@/components/DecisionSummary";
import type { DecisionRun, RunCandidate } from "@/lib/decisions";

const stack = (id: string, over: Partial<RunCandidate> = {}): RunCandidate =>
  ({
    candidate_id: id,
    stack_label: id,
    local_controller_config: "dwa_coarse",
    cleared_gates: true,
    blocking_gates: [],
    decision_utility: 0.877,
    objectives: { U_R: 1, U_S: 1, U_E: 0.57, U_C: 0.96 },
    ...over,
  }) as unknown as RunCandidate;

const blockedStack = () =>
  stack("rrtstar+dwa", {
    cleared_gates: false,
    recommendation_eligible: false,
    blocking_gates: ["G3"],
    decision_utility: 0.313,
    objectives: { U_R: 0, U_S: 0.31, U_E: 0.43, U_C: 0.5 },
  });

const run = (over: Partial<DecisionRun> = {}): DecisionRun =>
  ({
    id: "r",
    ranked: false,
    card: null,
    report: { candidates: [stack("astar+dwa"), blockedStack()] },
    ...over,
  }) as unknown as DecisionRun;

const summary = (value: DecisionRun) => renderToStaticMarkup(<DecisionSummary run={value} />);
const advice = (value: DecisionRun) => renderToStaticMarkup(<DecisionAdvice run={value} />);

describe("the summary states the conclusion once", () => {
  it("puts both marks and the recommendation in the first panel", () => {
    /* They used to be on the sixth screen, below a thirty-episode
       replay. */
    const html = summary(run());
    expect(html).toContain("87.7 / 100");
    expect(html).toContain("31.3 / 100");
    expect(html).toContain("Recommendation");
  });

  it("says one candidate cleared rather than none, on the run where one did", () => {
    /* The sentence the four-copy version got wrong: `astar+dwa` carries
       G1–G6 all pass in the table below this panel. */
    const html = summary(run());
    expect(html).toContain("Only one candidate cleared the gates");
    expect(html).not.toContain("No candidate cleared the gates");
  });

  it("shows a blocked candidate's mark, and shows that the gates removed it", () => {
    /* Hiding the score would suggest it lost on points. It did not — it
       was never in the running, and the mark is how a reader sees that
       the gates and not the score are what removed it. */
    const html = summary(run());
    expect(html).toContain("is-blocked");
    expect(html).toContain("blocked at G3");
  });

  it("renders no bar width for a candidate that was never scored", () => {
    /* `0 / 100` reads as the worst possible result rather than as an
       absent one. */
    const html = summary(
      run({ report: { candidates: [stack("a", { decision_utility: null })] } } as Partial<DecisionRun>),
    );
    expect(html).toContain("not scored");
    expect(html).not.toContain("null / 100");
  });

  it("qualifies a margin whose interval crosses zero", () => {
    /* A ΔU the run cannot demonstrate, printed unqualified, is how a
       coin toss reads as a finding. */
    const carded = run({
      ranked: true,
      card: {
        status: "OK",
        recommended: { candidate_id: "astar+dwa" },
        evidence: { delta_u_mean: 0.02, ci95: [-0.01, 0.05], n_episodes: 30 },
      },
    } as unknown as Partial<DecisionRun>);
    const html = summary(carded);
    expect(html).toContain("decision-recommendation-caveat");
    expect(html).toContain("cannot demonstrate");
  });

  it("keeps the platform's own sentence available", () => {
    const html = summary(
      run({
        report: {
          candidates: [stack("astar+dwa"), blockedStack()],
          why_no_card: "fewer than two candidates cleared",
        },
      } as unknown as Partial<DecisionRun>),
    );
    expect(html).toContain("fewer than two candidates cleared");
  });
});

describe("the advice answers all three use cases, always", () => {
  it("leaves no card empty on a run that recommended nothing", () => {
    const html = advice(run());
    expect(html).toContain("Quality-critical, offline");
    expect(html).toContain("Real-time, edge, low memory");
    expect(html).toContain("Needs both");
    expect(html).toContain("Nothing here");
  });

  it("names the blocking gate rather than saying no candidate", () => {
    /* "rrtstar+dwa, blocked at G3" is a stronger sentence than "no
       candidate" and costs the same room. */
    expect(advice(run())).toContain("G3");
  });

  it("carries a routing rule and its cost when it proposes a hybrid", () => {
    /* "Consider a hybrid approach" with nothing under it is the
       sentence this card exists instead of. */
    const split = run({
      ranked: true,
      card: {
        status: "OK",
        recommended: { candidate_id: "astar+dwa" },
        evidence: { delta_u_mean: 0.2, ci95: [0.1, 0.3], n_episodes: 30 },
      },
      report: {
        candidates: [
          stack("astar+dwa", { objectives: { U_R: 1, U_S: 1, U_E: 0.3, U_C: 0.3 } }),
          stack("rrtstar+dwa", { objectives: { U_R: 0.6, U_S: 0.6, U_E: 0.95, U_C: 0.95 } }),
        ],
      },
    } as unknown as Partial<DecisionRun>);
    const html = advice(split);
    expect(html).toContain("Route between the two");
    expect(html).toContain("predicted clearance");
    expect(html).toContain("cost is real");
  });
});
