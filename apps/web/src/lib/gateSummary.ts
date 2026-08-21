/** The one-line gate verdict, per candidate and for the field as a whole.
 *
 * Six feasibility gates run **before** anything is scored (HĐ-7), so a
 * candidate that failed one was never ranked at all — it is not a worse
 * choice, it is not a choice. That fact belongs at the top of the
 * candidate's column, not eleven metric rows below it.
 *
 * The summary is the part worth being careful about. It sits on a
 * collapsed `<summary>`, which is exactly the control a reader uses to
 * decide whether the detail is worth opening — so a badge that says
 * `cleared` while one of two candidates is blocked is wrong at the one
 * place where being wrong costs the reader the most. It therefore states
 * a ratio and never borrows one side's verdict for the field.
 */

import type { RunCandidate } from "@/lib/decisions";

/** What a single column head says about its candidate. */
export interface GateVerdictBadge {
  tone: "ok" | "err";
  key: string;
  /** Only the blocked wording uses it; joined here so the component
   *  does not have to know the separator. */
  gates: string;
}

export function gateVerdictBadge(candidate: RunCandidate): GateVerdictBadge {
  const blocking = candidate.blocking_gates ?? [];
  // `cleared_gates` is the platform's verdict and stays the authority.
  // The list is only how the failure is described.
  return candidate.cleared_gates
    ? { tone: "ok", key: "decisions.gates.badge.cleared", gates: "" }
    : { tone: "err", key: "decisions.gates.badge.blocked", gates: blocking.join(", ") };
}

/** What the collapsed detail's summary says about all of them. */
export interface GateSummary {
  tone: "ok" | "err";
  key: string;
  cleared: number;
  blocked: number;
  total: number;
}

/**
 * **A ratio, never one candidate's verdict standing for the field.**
 *
 * Three states rather than two: all clear, some blocked, none clear.
 * Collapsing the middle into either neighbour is what produces a
 * `cleared` badge over a field where somebody was eliminated, or an
 * `all blocked` badge over a run that still has a usable candidate.
 */
export function gateSummary(candidates: readonly RunCandidate[]): GateSummary | null {
  if (candidates.length === 0) return null;
  const cleared = candidates.filter((candidate) => candidate.cleared_gates).length;
  const total = candidates.length;
  const blocked = total - cleared;
  if (blocked === 0) {
    return { tone: "ok", key: "decisions.gates.summary.allCleared", cleared, blocked, total };
  }
  if (cleared === 0) {
    return { tone: "err", key: "decisions.gates.summary.allBlocked", cleared, blocked, total };
  }
  return { tone: "err", key: "decisions.gates.summary.someBlocked", cleared, blocked, total };
}
