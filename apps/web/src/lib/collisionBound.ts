/** What the collision-probability cell may claim, and on what sample.
 *
 * **The number alone is unreadable, and the explanation was in a
 * tooltip.** `≤ 10.0%` looks like a measurement of the robot. It is not:
 * it is `3/N` under the simulated scenario distribution, so a *lower*
 * number means a larger evidence base rather than a safer stack. Two
 * runs of the same stack differing only in length produce different
 * bounds. Putting that behind a hover left the cell saying the opposite
 * of what it means to anyone who did not hover.
 *
 * Two things move out of the tooltip and into the cell: the denominator
 * the bound was computed on, and — when there is no bound — the reason.
 */

import type { RunCandidate } from "@/lib/decisions";

export type CollisionBound =
  /** Zero collisions, so the rule of three applies and gives a bound. */
  | { kind: "bound"; bound: number; observed: number; distinct: number }
  /** Collisions were seen. The rule of three is for zero-event data
   *  only, so the platform publishes no bound (`gates.py:199`). */
  | { kind: "notApplicable"; observed: number; distinct: number }
  /** No G2 payload — an old run that predates the field. */
  | { kind: "unknown" };

/**
 * **`n_distinct_episodes`, never `n_runs`.**
 *
 * The payload carries both counts on purpose, and the gate's own comment
 * says why: printing the row count "is what produced a card claiming
 * 3.0% from one episode driven a hundred times". The rule of three
 * assumes independent draws; a replayed episode is not one. A stored run
 * shows exactly this — 30 rows, one distinct episode, a bound of 3.0 —
 * and quoting `0 / 30` beside it would claim thirty independent samples
 * where there was one.
 *
 * That run is also why nothing here clamps the bound to 100%. `3/1` is
 * 300%, which is vacuous as a probability and looks like a rendering
 * fault — but it is what one distinct episode supports, and the
 * denominator printed next to it says so at a glance. Clamping would
 * turn an obviously useless bound into a plausible-looking one.
 */
export function collisionBoundCell(candidate: RunCandidate): CollisionBound {
  const g2 = candidate.gates?.G2;
  if (!g2 || typeof g2 === "string") return { kind: "unknown" };
  const payload = g2 as Record<string, unknown>;

  const observed = numberOr(payload.observed, null);
  const distinct = numberOr(
    payload.n_distinct_episodes,
    // The candidate's own count is the same quantity by a different
    // route. `n_runs` is not — it is the row count, and using it is the
    // mistake this function exists to make impossible.
    numberOr(candidate.n_distinct_episodes, null),
  );
  if (observed === null || distinct === null) return { kind: "unknown" };

  const bound = numberOr(payload.upper_bound_95, null);
  // Keyed on the bound's absence, not on `observed > 0`: the platform
  // decides when a bound may be quoted, and reproducing that rule here
  // would be a second place for it to be decided.
  return bound === null
    ? { kind: "notApplicable", observed, distinct }
    : { kind: "bound", bound, observed, distinct };
}

function numberOr(value: unknown, fallback: number | null): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : fallback;
}
