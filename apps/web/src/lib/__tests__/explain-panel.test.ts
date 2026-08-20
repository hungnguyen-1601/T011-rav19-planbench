/** The five outcomes, as behaviour.
 *
 * The one that matters: three of them have no paired comparison, and a
 * panel that draws a waterfall for them is decomposing a difference
 * nobody computed.
 */

import { describe, expect, it } from "vitest";

import type { DecisionRun } from "@/lib/decisions";
import { panelPlan, runOutcome } from "@/lib/explainPanel";

function run(overrides: Record<string, unknown>): DecisionRun {
  return {
    ranked: true,
    card: { status: "CLEAR_RECOMMENDATION" },
    report: { sample: {}, candidates: [] },
    ...overrides,
  } as unknown as DecisionRun;
}

describe("what the panel may show", () => {
  it("shows the comparison only where one exists", () => {
    for (const outcome of ["no_survivors", "gate_only"] as const) {
      const plan =
        outcome === "gate_only"
          ? panelPlan(run({ ranked: false, card: null, report: { gate_only_deployment: "x", sample: {} } }))
          : panelPlan(run({ ranked: false, card: null, report: { sample: {} } }));

      expect(plan.outcome).toBe(outcome);
      expect(plan.showWaterfall).toBe(false);
      expect(plan.showClaims).toBe(false);
      expect(plan.showExemplars).toBe(false);
      // The gate table is the entire content of these two — and the
      // traces stay: no ΔU is not no evidence.
      expect(plan.showGateTable).toBe(true);
      expect(plan.showTraceEvidence).toBe(true);
    }
  });

  it("keeps an interrupted run's evidence when it got as far as ranking", () => {
    const plan = panelPlan(
      run({ ranked: true, report: { sample: { interrupted: true } } }),
    );

    expect(plan.outcome).toBe("interrupted");
    expect(plan.showWaterfall).toBe(true);
    expect(plan.caveatKeys).toContain("explain.caveat.fewerEpisodes");
  });

  it("shows no comparison for a run interrupted before it ranked anybody", () => {
    // Both halves of the logic were right and the pair was wrong: the
    // outcome said "interrupted", the interrupted plan switched the
    // waterfall on, and this run never produced a ΔU.
    const plan = panelPlan(
      run({ ranked: false, card: null, report: { sample: { interrupted: true } } }),
    );

    expect(plan.outcome).toBe("interrupted");
    expect(plan.showWaterfall).toBe(false);
    expect(plan.showClaims).toBe(false);
    expect(plan.caveatKeys).toContain("explain.caveat.noComparisonYet");
  });

  it("says a near-equivalent result was decided by the tie-break", () => {
    const plan = panelPlan(run({ card: { status: "NEAR_EQUIVALENT" } }));

    expect(plan.outcome).toBe("near_equivalent");
    expect(plan.caveatKeys).toContain("explain.caveat.insideTheNoise");
    expect(plan.caveatKeys).toContain("explain.caveat.tieBreak");
  });

  it("leads with not-finishing even when nobody survived either", () => {
    const outcome = runOutcome(
      run({ ranked: false, card: null, report: { sample: { interrupted: true }, gate_only_deployment: "x" } }),
    );
    expect(outcome).toBe("interrupted");
  });

  it("every outcome names a headline", () => {
    const plans = [
      panelPlan(run({})),
      panelPlan(run({ card: { status: "NEAR_EQUIVALENT" } })),
      panelPlan(run({ ranked: false, card: null, report: { sample: {} } })),
    ];
    expect(plans.every((plan) => plan.headlineKey.startsWith("explain.headline."))).toBe(true);
  });
});
