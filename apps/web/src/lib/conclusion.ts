/** Which stack to use, and how confident the platform is about saying so.
 *
 * The page ends on a conclusion because that is what a reader came for.
 * Everything this module decides is about *not overstating* it.
 *
 * **The line between the two groups is the whole design.** A candidate
 * that failed a gate was never in the running — and, crucially, its
 * failure may leave no mark on its utility at all. Collisions are
 * excluded from `U_S` on purpose (HĐ-6: letting them lower a score would
 * imply they trade against speed) and no objective reflects a missing
 * observation channel. So a stack that collided can carry a *higher*
 * number than one that did not, and a single ranked list would put it on
 * top with a warning badge nobody reads.
 *
 * Two groups, never interleaved, never sorted against each other. Inside
 * a group the number ranks; across the line it does not compare.
 *
 * **And the highest number is not automatically the recommendation.**
 * `HĐ-10.1` forbids recommending a Pareto-dominated candidate even when
 * it leads on utility, and `NEAR_EQUIVALENT` means the field could not
 * be separated at all. The headline comes from the card's own status,
 * never from `standings[0]`.
 */

import type { DecisionRun, RunCandidate } from "@/lib/decisions";

/** One candidate's standing. `utility` is the platform's own 0–1
 *  `decision_utility`; `outOf100` is only how it is shown. */
export interface Standing {
  candidateId: string;
  label: string;
  config: string;
  utility: number | null;
  objectives: { U_R: number; U_S: number; U_E: number; U_C: number } | null;
  eligible: boolean;
  blockingGates: string[];
}

/** Utility as a mark out of 100.
 *
 * **One decimal, deliberately.** `0.8774` and `0.8770` both round to
 * `88`, and those are two candidates ΔU can tell apart — an integer
 * would render a real difference as a tie. The decimal is not precision
 * theatre; it is the difference between "these are the same" and "these
 * are close", which is the distinction the whole confidence interval
 * exists to make.
 *
 * `null` stays `null`: a candidate that could not be scored has no mark,
 * and `0 / 100` would read as the worst possible result rather than as
 * an absent one.
 */
export function outOf100(utility: number | null): string | null {
  if (utility === null || !Number.isFinite(utility)) return null;
  return (utility * 100).toFixed(1);
}

function standingOf(candidate: RunCandidate): Standing {
  const utility =
    typeof candidate.decision_utility === "number" ? candidate.decision_utility : null;
  return {
    candidateId: candidate.candidate_id,
    label: candidate.stack_label,
    config: candidate.local_controller_config,
    utility,
    objectives: candidate.objectives ?? null,
    // Absent on runs scored before this field existed. Falling back to
    // the gate verdict rather than to `false` keeps those runs reading
    // the way they always did.
    eligible: candidate.recommendation_eligible ?? candidate.cleared_gates,
    blockingGates: candidate.blocking_gates ?? [],
  };
}

/** Highest utility first. Unscored candidates last, in their own order —
 *  "not measured" is not a low score and must not sort like one. */
function byUtility(left: Standing, right: Standing): number {
  if (left.utility === null && right.utility === null) return 0;
  if (left.utility === null) return 1;
  if (right.utility === null) return -1;
  return right.utility - left.utility;
}

/** The field, split at the line no ranking may cross. */
export function standings(candidates: RunCandidate[]): {
  eligible: Standing[];
  blocked: Standing[];
} {
  const all = candidates.map(standingOf);
  return {
    eligible: all.filter((entry) => entry.eligible).sort(byUtility),
    blocked: all.filter((entry) => !entry.eligible).sort(byUtility),
  };
}

/** What the page may claim, taken from the card rather than from the
 *  top of the list.
 *
 * `recommended` is the only kind that names a winner, and it exists only
 * when the platform issued one. The other two are results, not gaps: a
 * field the statistics cannot separate, and a field where fewer than two
 * candidates cleared the gates.
 */
export type Verdict =
  | { kind: "recommended"; candidateId: string; deltaU: number | null; ci: [number, number] | null }
  | { kind: "near-equivalent" }
  | { kind: "no-card" };

export function verdictOf(run: DecisionRun): Verdict {
  const card = run.card;
  if (!card || !card.recommended?.candidate_id) return { kind: "no-card" };
  if (card.status === "NEAR_EQUIVALENT") return { kind: "near-equivalent" };
  const evidence = card.evidence;
  return {
    kind: "recommended",
    candidateId: card.recommended.candidate_id,
    deltaU: typeof evidence?.delta_u_mean === "number" ? evidence.delta_u_mean : null,
    ci: Array.isArray(evidence?.ci95) && evidence.ci95.length === 2 ? evidence.ci95 : null,
  };
}

/** What the header badge says about the run as a whole.
 *
 * **Three states, because `ranked` is two.** `ranked` is `card !== null`
 * — its own docstring asks whether the run *supported* a recommendation,
 * which is weaker than issuing one. Two of the six carded runs stored
 * when this was written are `NEAR_EQUIVALENT`: they have a card, and it
 * names no winner because the field could not be separated. Labelling
 * those "Recommendation issued" states the opposite of the finding, and
 * it does so in the one place a reader glances at before scrolling.
 *
 * The tone follows the same split the page keeps elsewhere: a run that
 * named a stack is a result to act on; the other two are results to read
 * rather than failures, so neither takes an error colour.
 */
export function runBadge(run: DecisionRun): { key: string; tone: string } {
  switch (verdictOf(run).kind) {
    case "recommended":
      return { key: "decisions.detail.badge.recommended", tone: "ok" };
    case "near-equivalent":
      return { key: "decisions.detail.badge.nearEquivalent", tone: "muted-badge" };
    default:
      return { key: "decisions.detail.badge.noCard", tone: "muted-badge" };
  }
}

/** Whether an interval straddles zero — "ahead, but not measurably".
 *
 * Rendered rather than hidden: a margin whose interval includes zero is
 * consistent with the two being equal, and printing the mean alone turns
 * that into a result.
 */
export function marginIsConclusive(ci: [number, number] | null): boolean {
  if (!ci) return false;
  return ci[0] > 0 || ci[1] < 0;
}

/** Gates whose failure leaves no trace in the utility — measured, not assumed.
 *
 * **G2 is two different failures wearing one label.** It fails when a
 * collision was observed, and it fails when too few *distinct* episodes
 * ran to bound the risk at all. Those are opposite messages: one says
 * the stack hit something, the other says nobody looked long enough to
 * know. A run measured on 2026-08-21 had both candidates "blocked: G2"
 * with **zero collisions observed** — 5 distinct episodes against a
 * required 30.
 *
 * The distinction decides whether the utility can be trusted. A
 * collision is excluded from `U_S` by contract (HĐ-6), so a candidate
 * that hit something carries a mark that cannot see it. A sample too
 * small leaves the mark intact — there is simply not enough of it.
 *
 * G6 is always invisible: no objective reflects an observation channel
 * the deployment does not provide.
 */
export function invisibleFailures(standing: Standing, gates?: Record<string, unknown>): string[] {
  const found: string[] = [];
  for (const gate of standing.blockingGates) {
    if (gate === "G6") {
      found.push(gate);
      continue;
    }
    if (gate !== "G2") continue;
    // Only a real collision hides from the mark. Read from the gate's
    // own payload rather than inferred from the verdict, because the
    // verdict is the thing that conflates the two.
    const verdict = gates?.[gate];
    const observed =
      verdict && typeof verdict === "object"
        ? (verdict as Record<string, unknown>).observed
        : undefined;
    if (typeof observed !== "number" || observed > 0) found.push(gate);
  }
  return found;
}

/** Why G2 refused, in the two forms it actually takes.
 *
 * `null` when G2 is not among the blocking gates.
 */
export function collisionGateReason(
  standing: Standing,
  gates?: Record<string, unknown>,
): "collided" | "sample-too-small" | null {
  if (!standing.blockingGates.includes("G2")) return null;
  const verdict = gates?.G2;
  if (!verdict || typeof verdict !== "object") return "collided";
  const observed = (verdict as Record<string, unknown>).observed;
  return typeof observed === "number" && observed === 0 ? "sample-too-small" : "collided";
}
