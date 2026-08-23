/** The gate verdict on the head, and the ratio on the collapsed summary.
 *
 * The case this file exists for is the middle one. A field where one of
 * two candidates was eliminated is neither "cleared" nor "all blocked",
 * and the badge saying so sits on the control a reader uses to decide
 * whether to open the detail at all — so getting it wrong there is
 * getting it wrong at the point of maximum cost.
 */

import { describe, expect, it } from "vitest";

import { gateSummary, gateVerdictBadge } from "@/lib/gateSummary";
import type { RunCandidate } from "@/lib/decisions";

const candidate = (over: Partial<RunCandidate> = {}): RunCandidate =>
  ({
    candidate_id: "c",
    stack_label: "astar+dwa",
    local_controller_config: "dwa_coarse",
    n_distinct_episodes: 30,
    success_rate: 1,
    cleared_gates: true,
    blocking_gates: [],
    ...over,
  }) as RunCandidate;

const blocked = (...gates: string[]) =>
  candidate({ cleared_gates: false, blocking_gates: gates });

describe("the badge on a column head", () => {
  it("says cleared for a candidate through every gate", () => {
    expect(gateVerdictBadge(candidate())).toEqual({
      tone: "ok",
      key: "decisions.gates.badge.cleared",
      gates: "",
    });
  });

  it("names the gates that blocked it", () => {
    expect(gateVerdictBadge(blocked("G3"))).toEqual({
      tone: "err",
      key: "decisions.gates.badge.blocked",
      gates: "G3",
    });
    expect(gateVerdictBadge(blocked("G2", "G3")).gates).toBe("G2, G3");
  });

  it("keeps the platform's verdict as the authority", () => {
    /* An empty blocking list on a candidate the platform marked failed
       still reads as blocked. The list describes the failure; it does
       not decide whether there was one. */
    const odd = candidate({ cleared_gates: false, blocking_gates: [] });
    expect(gateVerdictBadge(odd).tone).toBe("err");
  });
});

describe("the summary over the whole field", () => {
  it("says nothing when there is no field", () => {
    expect(gateSummary([])).toBeNull();
  });

  it("reports all cleared", () => {
    const summary = gateSummary([candidate(), candidate()]);
    expect(summary).toMatchObject({
      tone: "ok",
      key: "decisions.gates.summary.allCleared",
      cleared: 2,
      blocked: 0,
      total: 2,
    });
  });

  it("never says cleared when one of two was eliminated", () => {
    /* The badge sits on the control that decides whether the detail is
       opened. Borrowing the surviving candidate's verdict for the field
       is wrong exactly where it costs the reader the most. */
    const summary = gateSummary([candidate(), blocked("G3")]);
    expect(summary?.key).toBe("decisions.gates.summary.someBlocked");
    expect(summary?.tone).toBe("err");
    expect(summary).toMatchObject({ cleared: 1, blocked: 1, total: 2 });
  });

  it("distinguishes some-blocked from all-blocked", () => {
    /* Collapsing these two loses the difference between a run with a
       usable candidate and a run with none. */
    expect(gateSummary([blocked("G3"), blocked("G2")])?.key).toBe(
      "decisions.gates.summary.allBlocked",
    );
  });

  it("counts correctly past two candidates", () => {
    const summary = gateSummary([candidate(), candidate(), blocked("G4")]);
    expect(summary).toMatchObject({
      key: "decisions.gates.summary.someBlocked",
      cleared: 2,
      blocked: 1,
      total: 3,
    });
  });

  it("keeps cleared and blocked adding up to the field", () => {
    for (const field of [
      [candidate()],
      [candidate(), blocked("G1")],
      [blocked("G1"), blocked("G2"), candidate()],
    ]) {
      const summary = gateSummary(field)!;
      expect(summary.cleared + summary.blocked).toBe(summary.total);
      expect(summary.total).toBe(field.length);
    }
  });
});
