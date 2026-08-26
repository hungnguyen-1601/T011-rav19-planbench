/** Which use case gets which stack.
 *
 * The five branches, and the two places the reading can go wrong: a
 * hybrid invented out of missing objectives, and a hybrid claimed where
 * one stack actually leads both halves.
 */

import { describe, expect, it } from "vitest";

import { decisionAdvice } from "@/lib/decisionAdvice";
import type { DecisionRun, RunCandidate } from "@/lib/decisions";

const stack = (
  id: string,
  over: Partial<RunCandidate> & {
    objectives?: { U_R: number; U_S: number; U_E: number; U_C: number } | null;
  } = {},
): RunCandidate =>
  ({
    candidate_id: id,
    stack_label: id,
    local_controller_config: "dwa_coarse",
    cleared_gates: true,
    blocking_gates: [],
    decision_utility: 0.8,
    objectives: { U_R: 1, U_S: 1, U_E: 0.5, U_C: 0.9 },
    ...over,
  }) as unknown as RunCandidate;

const run = (candidates: RunCandidate[], card: unknown = null): DecisionRun =>
  ({ id: "r", ranked: card !== null, card, report: { candidates } }) as unknown as DecisionRun;

describe("what to deploy, by use case", () => {
  it("has no answer for anybody when nobody cleared", () => {
    const advice = decisionAdvice(
      run([
        stack("astar+dwa", { cleared_gates: false, recommendation_eligible: false }),
        stack("rrtstar+dwa", { cleared_gates: false, recommendation_eligible: false }),
      ]),
    );
    expect(advice.kind).toBe("none");
  });

  it("names the sole survivor without calling it a winner", () => {
    /* The distinction is the whole reason this branch exists: one
       deployable stack is not the same claim as one that beat
       something. */
    const advice = decisionAdvice(
      run([
        stack("astar+dwa"),
        stack("rrtstar+dwa", { cleared_gates: false, recommendation_eligible: false }),
      ]),
    );
    expect(advice.kind).toBe("sole");
    if (advice.kind === "sole") expect(advice.sole.label).toContain("astar+dwa");
  });

  it("refuses to route between two stacks nobody can tell apart", () => {
    /* Routing costs two built, tuned and shipped stacks plus a third
       thing that can be wrong. A field the statistics could not
       separate does not buy that. */
    const advice = decisionAdvice(
      run(
        [stack("astar+dwa"), stack("rrtstar+dwa")],
        { status: "NEAR_EQUIVALENT", recommended: { candidate_id: "astar+dwa" }, evidence: {} },
      ),
    );
    expect(advice.kind).toBe("tie");
  });

  it("calls it a single winner when one stack leads both halves", () => {
    /* A hybrid here would recommend operating two stacks to gain
       nothing: there is no half for the second one to be better at. */
    const advice = decisionAdvice(
      run(
        [
          stack("astar+dwa", { objectives: { U_R: 1, U_S: 1, U_E: 0.9, U_C: 0.9 } }),
          stack("rrtstar+dwa", { objectives: { U_R: 0.4, U_S: 0.4, U_E: 0.4, U_C: 0.4 } }),
        ],
        { status: "OK", recommended: { candidate_id: "astar+dwa" }, evidence: {} },
      ),
    );
    expect(advice.kind).toBe("single");
    if (advice.kind === "single") expect(advice.winner.label).toContain("astar+dwa");
  });

  it("splits only when the two halves genuinely disagree", () => {
    /* A leads on what the robot achieved, B on what it spent. This is
       the one shape where routing earns its complexity. */
    const advice = decisionAdvice(
      run(
        [
          stack("astar+dwa", { objectives: { U_R: 1, U_S: 1, U_E: 0.3, U_C: 0.3 } }),
          stack("rrtstar+dwa", { objectives: { U_R: 0.6, U_S: 0.6, U_E: 0.95, U_C: 0.95 } }),
        ],
        { status: "OK", recommended: { candidate_id: "astar+dwa" }, evidence: {} },
      ),
    );
    expect(advice.kind).toBe("hybrid");
    if (advice.kind === "hybrid") {
      expect(advice.quality.label).toContain("astar+dwa");
      expect(advice.realtime.label).toContain("rrtstar+dwa");
    }
  });

  it("does not invent a hybrid from objectives a run never scored", () => {
    /* Runs predating the field carry no objectives. Reading a split out
       of two nulls would recommend operating two stacks on the strength
       of missing data. */
    const advice = decisionAdvice(
      run(
        [
          stack("astar+dwa", { objectives: null, decision_utility: 0.9 }),
          stack("rrtstar+dwa", { objectives: null, decision_utility: 0.4 }),
        ],
        { status: "OK", recommended: { candidate_id: "astar+dwa" }, evidence: {} },
      ),
    );
    expect(advice.kind).toBe("single");
    if (advice.kind === "single") expect(advice.winner.label).toContain("astar+dwa");
  });

  it("tells two candidates of the same stack apart", () => {
    /* Both sides of a local-controller comparison carry the same
       `stack_label`, and only the config says which is which. */
    const advice = decisionAdvice(
      run([
        stack("a", { stack_label: "astar+dwa", local_controller_config: "dwa_fine" }),
        stack("b", {
          stack_label: "astar+dwa",
          local_controller_config: "dwa_coarse",
          cleared_gates: false,
          recommendation_eligible: false,
        }),
      ]),
    );
    expect(advice.kind).toBe("sole");
    if (advice.kind === "sole") expect(advice.sole.label).toBe("astar+dwa · dwa_fine");
  });
});
