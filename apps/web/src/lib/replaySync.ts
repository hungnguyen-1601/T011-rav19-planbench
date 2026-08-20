/** Which two candidates a comparison page is about, and where each run
 *  is at a given arc length.
 *
 * Extracted from the page so it can be *tested as behaviour*. The page
 * itself is only assertable as source text in this suite (no jsdom, no
 * testing-library — see `vitest.config.ts`), and the defect that
 * motivated this file went straight through those assertions: the page
 * showed `candidates.slice(0, 2)` while the exemplar recipe ran on a
 * different pair, and every string a source-text test looked for was
 * present in both versions.
 */

import type { DecisionRun, ReplaySyncView, RunCandidate } from "./decisions";

/** The recommendation and the candidate ΔU was computed against.
 *
 * **From `report.comparison_pair`, which the scoring run writes.** Not
 * from the card: `alternative` there may only name a PARETO_FRONTIER
 * candidate (HĐ-12), so it is null on every run without a Pareto
 * analysis, and when it is set it can be a different candidate from the
 * runner-up. Reading it — as an earlier version of this function did —
 * sent ordinary ranked runs back to registration order and, where it
 * did answer, could name a candidate the statistics never compared.
 *
 * `null` when the run records no pair: a run that ranked nobody has no
 * winner, and so does a run scored before the field existed.
 */
export function comparedPair(run: DecisionRun): [string, string] | null {
  const pair = run.report?.comparison_pair;
  const winner = pair?.recommended_candidate_id ?? "";
  const runnerUp = pair?.runner_up_candidate_id ?? "";
  if (!winner || !runnerUp || winner === runnerUp) return null;
  return [winner, runnerUp];
}

/** The two candidates to draw, winner first.
 *
 * Falls back to the first two entries only when the run has no card —
 * a comparison that ranked nobody still has two canvases worth showing,
 * and there is no winner to get the order wrong.
 */
export function panelCandidates(run: DecisionRun, candidates: RunCandidate[]): RunCandidate[] {
  const pair = comparedPair(run);
  if (!pair) return candidates.slice(0, 2);
  const byId = new Map(candidates.map((candidate) => [candidate.candidate_id, candidate]));
  const ordered = pair.map((id) => byId.get(id)).filter((c): c is RunCandidate => Boolean(c));
  return ordered.length === 2 ? ordered : candidates.slice(0, 2);
}

/** How far both runs got. Past this the panels are not comparable, so
 *  the slider stops there rather than showing one robot alone. */
export function commonProgress(view: ReplaySyncView): number {
  const both = view.plan.rows.filter((row) => row.time_a !== null && row.time_b !== null);
  return both.length > 0 ? both[both.length - 1].progress_m : 0;
}

/** The timestamp one side had reached at this arc length.
 *
 * The two sides deliberately return *different* timestamps for the same
 * progress — that is the whole difference between the alignments, and
 * the reason the warning travels with the rows.
 */
export function sideTime(
  view: ReplaySyncView | null,
  progress: number,
  side: "a" | "b",
): number {
  if (!view || view.plan.rows.length === 0) return 0;
  let chosen = view.plan.rows[0];
  for (const row of view.plan.rows) {
    if (row.progress_m > progress) break;
    chosen = row;
  }
  const stamp = side === "a" ? chosen.time_a : chosen.time_b;
  return stamp ?? 0;
}

/** The arc length one side had reached at this timestamp — `sideTime`
 *  backwards.
 *
 * Needed because the two alignments measure the scrubber in different
 * units. Clicking the latency chart hands back a *time* on one
 * candidate's own clock, and in progress alignment the shared scrubber
 * is in metres, so the click has to be converted before it can be
 * applied to both panels. Doing that arithmetic at the call site would
 * put a second, informal copy of the rows' meaning in the page.
 *
 * Matched to `sideTime`'s convention — the last rung at or before the
 * value asked for, no interpolation — so time → progress → time returns
 * where it started rather than creeping by a rung each round trip.
 *
 * Clamped to the last rung *both* runs reached, which is the range the
 * progress scrubber actually has: a click at 50 s on a run whose partner
 * stopped at 22 s would otherwise return a position the slider cannot
 * hold.
 */
export function sideProgress(
  view: ReplaySyncView | null,
  seconds: number,
  side: "a" | "b",
): number {
  if (!view || view.plan.rows.length === 0) return 0;
  const limit = commonProgress(view);
  let chosen = 0;
  for (const row of view.plan.rows) {
    const stamp = side === "a" ? row.time_a : row.time_b;
    // A null is "this run never got this far", not "it was here at
    // t=0"; treating it as zero would drag the scrubber back to the
    // start whenever the slower run's rows ran out.
    if (stamp === null) continue;
    if (stamp > seconds) break;
    chosen = row.progress_m;
  }
  return Math.min(chosen, limit);
}
