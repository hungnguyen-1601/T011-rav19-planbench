/** What to deploy, answered by use case rather than by run.
 *
 * **The page used to answer a question nobody arrives with.** "Did this
 * run issue a recommendation" is a fact about the run; "which of these
 * do I put on the robot" is what the reader came for, and on a run that
 * issued no card the page said only that it had not — which is true and
 * is not an answer. A blocked run still has an answer: *nothing here is
 * deployable, and here is why for each use case.* An empty panel says
 * less than that sentence and takes more room to say it.
 *
 * **Five outcomes.** Two are decided by counting who cleared the gates,
 * which is a hard fact; the other three by where the objectives split,
 * which is a reading of numbers the platform already scored.
 *
 * - `none` — nobody cleared. No use case has a candidate.
 * - `sole` — exactly one cleared. It is the only deployable stack, and
 *   deliberately *not* called a winner: nothing was left to beat.
 * - `tie` — two or more cleared and the statistics cannot separate them.
 * - `single` — one candidate leads both halves of the objective set.
 * - `hybrid` — one leads on quality, another on cost. This is the only
 *   outcome where routing between two stacks is worth its complexity.
 *
 * **Why the objectives split two-and-two.** `U_R` and `U_S` are what the
 * robot achieved — reached the goal, kept its distance. `U_E` and `U_C`
 * are what it spent getting there — time, and compute. A deployment that
 * cares about the first pair is the offline, quality-critical one; a
 * deployment that cares about the second is the edge one with a latency
 * budget and 8 MB to work in. That is the same cut the recommendation
 * cards make, so the advice and the scores cannot disagree about which
 * half a candidate won.
 */

import { type Standing, standings, verdictOf } from "@/lib/conclusion";
import type { DecisionRun, RunCandidate } from "@/lib/decisions";

export interface AdviceParty {
  candidateId: string;
  /** Stack and config together: both sides of a controller comparison
   *  carry the same stack, and only the config tells them apart. */
  label: string;
}

export type DecisionAdvice =
  | { kind: "none" }
  | { kind: "sole"; sole: AdviceParty }
  | { kind: "tie"; parties: AdviceParty[] }
  | { kind: "single"; winner: AdviceParty }
  | { kind: "hybrid"; quality: AdviceParty; realtime: AdviceParty };

const party = (standing: Standing): AdviceParty => ({
  candidateId: standing.candidateId,
  label: `${standing.label} · ${standing.config}`,
});

/** What the robot achieved, against what it spent achieving it. */
const achieved = (standing: Standing): number | null =>
  standing.objectives ? standing.objectives.U_R + standing.objectives.U_S : null;
const spent = (standing: Standing): number | null =>
  standing.objectives ? standing.objectives.U_E + standing.objectives.U_C : null;

export function decisionAdvice(run: DecisionRun): DecisionAdvice {
  const candidates: RunCandidate[] = run.report?.candidates ?? [];
  const { eligible } = standings(candidates);

  if (eligible.length === 0) return { kind: "none" };
  if (eligible.length === 1) return { kind: "sole", sole: party(eligible[0]) };

  // A field the statistics could not separate is a result, not a gap,
  // and routing traffic between two stacks nobody can tell apart buys
  // complexity for nothing.
  if (verdictOf(run).kind === "near-equivalent") {
    return { kind: "tie", parties: eligible.map(party) };
  }

  // `standings` sorts by utility, so `eligible[0]` is the highest-scoring
  // candidate that cleared. That is the fallback whenever the split
  // cannot be read — a run scored before `objectives` existed carries
  // none, and inventing a hybrid from missing numbers would recommend
  // running two stacks on the strength of two nulls.
  const best = party(eligible[0]);
  const scored = eligible.filter((entry) => entry.objectives !== null);
  if (scored.length < 2) return { kind: "single", winner: best };

  const byAchieved = [...scored].sort((l, r) => (achieved(r) ?? 0) - (achieved(l) ?? 0));
  const bySpent = [...scored].sort((l, r) => (spent(r) ?? 0) - (spent(l) ?? 0));
  const quality = byAchieved[0];
  const realtime = bySpent[0];

  if (quality.candidateId === realtime.candidateId) {
    return { kind: "single", winner: party(quality) };
  }
  return { kind: "hybrid", quality: party(quality), realtime: party(realtime) };
}
