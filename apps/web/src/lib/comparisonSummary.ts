/** One sentence counting what the highlighting already says.
 *
 * Ten rows of tinted and untinted cells carry a pattern nobody reads off
 * ten rows. The sentence states it: who leads on how many, and how many
 * were level.
 *
 * **It is a count, not a second judgement.** Every number comes from
 * `leaders()` — the same function that decides which cell gets tinted —
 * so the sentence and the table cannot disagree. Nothing here re-reads a
 * value or applies a threshold of its own.
 */

import { type MetricRow, leaders } from "@/lib/candidateMetrics";

export interface ComparisonSummary {
  /** Rows where one side leads, per candidate index. */
  wins: number[];
  ties: number;
  /** Rows that counted at all. `wins` and `ties` sum to this. */
  total: number;
}

/**
 * `null` when the sentence would not be true of the table.
 *
 * **Only for exactly two candidates.** "A leads on four, B on two" has
 * no room for C, and rewriting it to list three would be a different
 * sentence rather than the same one with a number changed.
 *
 * **Rows that measured nothing are excluded, not counted as ties.** A
 * tie is a comparison that came out level; a row where one side recorded
 * nothing was never compared. Folding the second into the first inflates
 * the agreement between two stacks with a row that says nothing about
 * either — and it is the shape of claim this page exists to avoid.
 *
 * **Rows with no direction are excluded too.** `replans` is evidence
 * rather than a score: it is already charged in travel time and in
 * latency, and no deployment declares a replan budget. Counting it would
 * let a candidate "lead" on a row the table deliberately marks nobody on.
 */
export function comparisonSummary(
  rows: readonly MetricRow[],
  candidateCount: number,
): ComparisonSummary | null {
  if (candidateCount !== 2) return null;

  const wins = new Array<number>(candidateCount).fill(0);
  let ties = 0;
  let total = 0;

  for (const row of rows) {
    if (row.direction === "none") continue;
    // Every candidate has to have recorded it, or there was no
    // comparison to have an outcome.
    if (row.values.some((value) => value === null)) continue;
    total += 1;
    const ahead = leaders(row);
    // `leaders` returns nothing when every side is level — which, past
    // the check above, can only mean a genuine tie.
    if (ahead.length === 0) ties += 1;
    else for (const index of ahead) wins[index] += 1;
  }

  // Nothing was comparable: a sentence saying "leads on 0 of 0" is worse
  // than no sentence.
  if (total === 0) return null;
  return { wins, ties, total };
}
