/** The three or four things worth saying about ten rows of numbers.
 *
 * **A table is not a reading of itself.** Ten metrics against two
 * candidates is eighty digits, and the page asked every reader to do the
 * same diff by eye and arrive at the same three sentences. Most of them
 * did not: they read the two rows they already cared about and scrolled
 * on, which is how a latency win hides a clearance loss.
 *
 * **Every insight names its own numbers.** "A is more accurate but B is
 * faster" is a shape, not a finding — the reader cannot check it, and it
 * stays true-sounding after the data changes underneath it. Each rule
 * here returns the metric keys and the figures it read, so the sentence
 * on screen is checkable against the row above it.
 *
 * **Silence is a claim too.** On a run where one candidate leads
 * everything, the honest insight is that there is no trade-off — and
 * rendering nothing there leaves the reader to work out for themselves
 * whether the table is one-sided or they missed something.
 */

import { type MetricRow, leaders } from "@/lib/candidateMetrics";

/** What the robot achieved, against what it spent achieving it. The same
 *  cut `decisionAdvice` makes over the objectives, made here over the
 *  metrics those objectives are scored from — so an insight saying "A
 *  leads on quality" and a card recommending A for quality-critical work
 *  are reading the same split rather than two similar-looking ones. */
const ACHIEVED = new Set(["successRate", "collisions", "collisionBound", "noPathRate", "worstClearance"]);
const SPENT = new Set(["medianTravel", "p99", "memory"]);

export type TradeoffKind = "tradeoff" | "sweep" | "unmeasured" | "atLimit";

export interface Tradeoff {
  kind: TradeoffKind;
  /** Which candidate the sentence is about, as an index, where it is
   *  about one. `null` for the insights that are about the run. */
  side: number | null;
  /** The rows this was read off. Rendered as the metric names, so a
   *  reader can look up every claim. */
  metrics: string[];
  /** Counts the sentence needs. Kept as strings because that is what the
   *  translator takes, and formatting a count is not this file's job. */
  vars: Record<string, string>;
}

/** Was this row a comparison at all? The same two conditions
 *  `comparisonSummary` and the winner column use: a row with no
 *  direction was never scored, and a row where a side recorded nothing
 *  was never compared. */
const comparable = (row: MetricRow): boolean =>
  row.direction !== "none" && row.values.every((value) => value !== null);

export function tradeoffs(rows: readonly MetricRow[], candidateCount: number): Tradeoff[] {
  if (candidateCount !== 2) return [];

  const scored = rows.filter(comparable);
  const wonBy = (index: number, group: Set<string>) =>
    scored.filter((row) => group.has(row.key) && leaders(row).includes(index));

  const found: Tradeoff[] = [];

  // 1. The trade-off itself: one side ahead on what the robot achieved,
  //    the other on what it spent. This is the only shape where a
  //    deployment's own priorities change the answer, so it leads.
  for (const side of [0, 1]) {
    const other = side === 0 ? 1 : 0;
    const mine = wonBy(side, ACHIEVED);
    const theirs = wonBy(other, SPENT);
    if (mine.length > 0 && theirs.length > 0) {
      found.push({
        kind: "tradeoff",
        side,
        metrics: [...mine.map((row) => row.key), ...theirs.map((row) => row.key)],
        vars: { achieved: String(mine.length), spent: String(theirs.length) },
      });
      break;
    }
  }

  // 2. No trade-off at all. Said out loud rather than left as an absence
  //    — a reader cannot tell a one-sided table from one they misread.
  if (found.length === 0) {
    for (const side of [0, 1]) {
      const mine = scored.filter((row) => leaders(row).includes(side));
      const theirs = scored.filter((row) => leaders(row).includes(side === 0 ? 1 : 0));
      if (mine.length > 0 && theirs.length === 0) {
        found.push({
          kind: "sweep",
          side,
          metrics: mine.map((row) => row.key),
          vars: { won: String(mine.length), total: String(scored.length) },
        });
        break;
      }
    }
  }

  // 3. What the run did not measure. A comparison resting on six rows
  //    where the reader can see ten is a narrower claim than it looks.
  const unmeasured = rows.filter((row) => row.direction !== "none" && !comparable(row));
  if (unmeasured.length > 0) {
    found.push({
      kind: "unmeasured",
      side: null,
      metrics: unmeasured.map((row) => row.key),
      vars: { count: String(unmeasured.length), scored: String(scored.length) },
    });
  }

  // 4. A row where the winner is still against the deployment's own
  //    limit. Winning a metric and clearing its budget are different
  //    facts, and the delta column shows only the first.
  const atLimit = scored.filter((row) => row.threshold !== undefined && leaders(row).length === 0);
  if (atLimit.length > 0) {
    found.push({
      kind: "atLimit",
      side: null,
      metrics: atLimit.map((row) => row.key),
      vars: { count: String(atLimit.length) },
    });
  }

  // Five is where a list stops being read. The first two are the reading
  // of the table and always come first when they exist.
  return found.slice(0, 5);
}
