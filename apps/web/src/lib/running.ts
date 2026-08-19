/** The running comparison's presentation rules, decided apart from markup.
 *
 * Two things here are worth being wrong about, and neither is visible in
 * a screenshot.
 *
 * **Which direction is better.** `safety_margin` rewards a larger
 * number and `elapsed_s` rewards a smaller one. A table that highlighted
 * "the bigger value" would paint the slower run as the winner on half
 * its rows, and every cell would still look right.
 *
 * **Which clock a row belongs to.** At one instant the two robots are at
 * different places on the task, so "worst clearance at equal time"
 * compares two different parts of the map. The server splits its metrics
 * into the two clocks; this file carries that split into the table
 * rather than flattening it into one list of eight numbers.
 */

import type { RunningPoint, RunningSample } from "@/lib/decisions";

/** Which way is better, per metric. */
export type Direction = "higher" | "lower";

export interface MetricRow {
  key: keyof RunningSample;
  direction: Direction;
  /** Decimal places. `replans` is a count and gets none. */
  digits: number;
  /** The unit shown after the number; empty for a ratio. */
  unit: string;
}

/** Metrics that mean something when both runs are read at the same
 *  *progress*: they describe how the same stretch of task was done. */
export const PROGRESS_CLOCK: MetricRow[] = [
  { key: "elapsed_s", direction: "lower", digits: 1, unit: "s" },
  { key: "safety_margin", direction: "higher", digits: 2, unit: "r" },
  { key: "exposure_s", direction: "lower", digits: 1, unit: "s" },
  { key: "path_efficiency", direction: "higher", digits: 2, unit: "" },
];

/** Metrics that mean something when both runs are read at the same
 *  *time*: they describe who is ahead. Shown on a progress-aligned
 *  table too, but labelled, because a reader comparing
 *  `progress_fraction` at equal progress is comparing two numbers that
 *  are equal by construction. */
export const TIME_CLOCK: MetricRow[] = [
  { key: "progress_fraction", direction: "higher", digits: 3, unit: "" },
  { key: "progress_rate", direction: "higher", digits: 2, unit: "m/s" },
  { key: "compute_budget", direction: "lower", digits: 2, unit: "×T" },
  { key: "replans", direction: "lower", digits: 0, unit: "" },
];

/** Differences below this fraction of the pair's scale are not called.
 *
 * Without it every row has a winner, including rows where the two runs
 * differ in the sixth decimal — and a table where nobody ever ties
 * teaches a reader to ignore the highlighting.
 */
const TIE_TOLERANCE = 1e-3;

/** Who is doing better on one metric. `null` is a genuine tie.
 *
 * Scaled rather than absolute: a 0.01 s difference in `elapsed_s` and a
 * 0.01 difference in `path_efficiency` are not the same size of claim,
 * and a fixed epsilon would call one and miss the other.
 */
export function leader(row: MetricRow, a: RunningSample, b: RunningSample): "a" | "b" | null {
  const left = Number(a[row.key]);
  const right = Number(b[row.key]);
  const scale = Math.max(Math.abs(left), Math.abs(right), 1);
  if (Math.abs(left - right) <= TIE_TOLERANCE * scale) return null;
  const leftWins = row.direction === "higher" ? left > right : left < right;
  return leftWins ? "a" : "b";
}

/** The rung to show for a scrub position, in metres of progress.
 *
 * The **last rung reached**, not the nearest: showing a rung the robot
 * has not got to yet would report a future the reader is not looking
 * at. `null` before the first rung — the ladder does not start at zero
 * when both runs began part-way along the reference line.
 *
 * Assumes the rows arrive ascending by `progress_m`, which is how the
 * server builds the ladder.
 */
export function rowAt(rows: RunningPoint[], progress: number): RunningPoint | null {
  let current: RunningPoint | null = null;
  for (const row of rows) {
    if (row.progress_m > progress) break;
    current = row;
  }
  return current;
}

/** Whether the composite may stand as the episode's answer.
 *
 * It may not. `partial_advantage` covers the objectives that are defined
 * on a prefix — two of four — and it measures efficiency against the
 * replay's reference line rather than against `L_ref`. At the end of the
 * episode the panel hands over to the stored `episode_decision_utility`,
 * which is the real number over all four. This returns the caveat's key
 * so the panel cannot render the composite without it.
 */
export function compositeCaveat(point: RunningPoint): string {
  return point.partial_objectives.length >= 4
    ? "running.composite.full"
    : "running.composite.partial";
}
