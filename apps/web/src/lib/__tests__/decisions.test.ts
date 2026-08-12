/** The decision-run view model.
 *
 * Everything here guards one property: **a run with no Decision Card is
 * a result, not a failure.** Four of the first five comparisons this
 * platform ran produced no card, and each still answered "who was
 * eliminated where, after how many runs". A UI that flattened those into
 * one "no card" state would recreate the pressure to make every run
 * rankable — the pressure that produced a card bounding a collision
 * probability off a single episode.
 *
 * So the three ways to end up cardless are kept apart, because each asks
 * the reader for a different next action.
 */

import { describe, expect, it } from "vitest";

import {
  coverage,
  gateEvidence,
  gateResult,
  noCardReason,
  type DecisionRun,
} from "../decisions";

function run(overrides: Partial<DecisionRun> = {}): DecisionRun {
  const base: DecisionRun = {
    id: "r1",
    task_profile_id: "open_hall_v2",
    artifact_kind: "comparison",
    experiment_scope: "local_controller_selection",
    contracts_version: "6.5.0",
    created_at: "2026-08-12T10:00:00+00:00",
    created_by: "alice",
    ranked: false,
    recommended_candidate_id: null,
    status: null,
    card: null,
    review_state: "unreviewed",
    reviewed_by: null,
    reviewed_at: null,
    config_state: "not_applicable",
    config_decided_by: null,
    config_decided_at: null,
    report: {
      artifact: "comparison_report",
      identity: {
        task_profile_id: "open_hall_v2",
        experiment_scope: "local_controller_selection",
        sensor_noise: { lidar_range_sigma_m: 0.02, wheel_slip_fraction: 0.02 },
        git_sha: "abc123",
        anchor_config_version: "v1.2",
        created_at: "2026-08-12T10:00:00+00:00",
      },
      sample: {
        n_episodes: 30,
        n_episodes_requested: 30,
        interrupted: false,
        n_min_required: 30,
        episode_context_ids: [],
      },
      candidates: [],
      measurement_environment: { benchmark_host: {}, warning: null },
      decision_card: null,
    },
    ...overrides,
  };
  return base;
}

describe("why a run produced no card", () => {
  it("says nothing about a run that did produce one", () => {
    expect(noCardReason(run({ ranked: true }))).toBeNull();
  });

  it("reports no survivors when everybody cleared out at the gates", () => {
    expect(noCardReason(run())).toBe("no_survivors");
  });

  it("reports a gate-only deployment separately from no survivors", () => {
    /* The two ask for opposite actions: a better candidate fixes one and
       can never fix the other, because there the scale itself collapsed
       (HĐ-8.4). One shared message would send readers the wrong way. */
    const gateOnly = run();
    gateOnly.report.gate_only_deployment = "success_rate: threshold at the ideal";
    expect(noCardReason(gateOnly)).toBe("gate_only");
  });

  it("puts an interrupted run ahead of both", () => {
    /* An interrupted run has not finished being asked the question, so
       "nobody survived" would be a verdict on evidence that is still
       arriving. */
    const interrupted = run();
    interrupted.report.sample.interrupted = true;
    interrupted.report.gate_only_deployment = "success_rate: threshold at the ideal";
    expect(noCardReason(interrupted)).toBe("interrupted");
  });

  it("survives a report that predates these fields", () => {
    const old = run();
    delete (old.report as { gate_only_deployment?: unknown }).gate_only_deployment;
    delete (old.report.sample as { interrupted?: unknown }).interrupted;
    expect(noCardReason(old)).toBe("no_survivors");
  });
});

describe("how much of the requested run this covers", () => {
  it("is one when the run finished", () => {
    expect(coverage(run())).toBe(1);
  });

  it("is the measured fraction when the run was cut short", () => {
    /* B1 stopped at 245 of 300. Rendering "245" alone reads as a
       deliberate 245-episode run, which is a different claim from "the
       machine was taken back at 245". */
    const partial = run();
    partial.report.sample.n_episodes = 245;
    partial.report.sample.n_episodes_requested = 300;
    expect(coverage(partial)).toBeCloseTo(245 / 300, 6);
  });

  it("is undefined — never 1 — when the report does not say what was asked for", () => {
    /* "We do not know" and "covered everything" must not render the
       same, or an older report silently claims completeness. */
    const old = run();
    delete (old.report.sample as { n_episodes_requested?: number }).n_episodes_requested;
    expect(coverage(old)).toBeUndefined();
  });
});

describe("a gate verdict, whichever shape it arrived in", () => {
  it("reads the bare string form", () => {
    /* The wire is genuinely mixed: G1 and G3 serialise as "pass" while
       G2, G4 and G5 serialise as objects. Both are gate verdicts. */
    expect(gateResult("pass")).toBe("pass");
    expect(gateResult("fail")).toBe("fail");
  });

  it("reads the object form", () => {
    expect(gateResult({ result: "fail", observed: 34 })).toBe("fail");
  });

  it("is undefined for a gate the report did not mention", () => {
    /* Not "pass". A gate nobody ran is not a gate that passed. */
    expect(gateResult(undefined)).toBeUndefined();
  });

  it("carries the evidence an object verdict came with", () => {
    const evidence = gateEvidence({
      result: "fail",
      observed: 34,
      n_runs: 245,
      statement: "34 va chạm quan sát trong 245 lần chạy",
    });
    expect(Object.fromEntries(evidence)).toMatchObject({
      observed: "34",
      n_runs: "245",
    });
    expect(evidence.map(([key]) => key)).not.toContain("result");
  });

  it("invents nothing for a bare-string verdict", () => {
    /* "G3: fail" with fabricated numbers beside it is worse than
       "G3: fail" alone. */
    expect(gateEvidence("fail")).toEqual([]);
  });

  it("drops nulls rather than printing 'null' at the reader", () => {
    const evidence = gateEvidence({ result: "fail", upper_bound_95: null, note: null, n_min: 300 });
    expect(evidence.map(([key]) => key)).toEqual(["n_min"]);
  });
});
