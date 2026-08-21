/** The end-of-run numbers a reader compares candidates on.
 *
 * Not the running metrics — those answer "who is ahead right now" while
 * a replay plays. These are what the sweep concluded, one value per
 * candidate, and the question is which stack behaved better.
 *
 * Every value arrives as digits and a unit kept apart, because the grid
 * aligns decimal points across rows and `ms` is wider than `m` is wider
 * than `MB`. Absent values arrive as `null` and are worded by the
 * component.
 *
 * **Almost nothing here is computed.** Where the platform already
 * produced a number, it is read out of the gate payload rather than
 * derived again: G1 carries the no-path rate, G2 the collision count and
 * the 95% bound, G4 the pooled p99, G5 the memory estimate. Recomputing
 * any of them in the browser would be a second definition free to drift
 * from the one the gate verdict was decided on — and the drift would be
 * invisible, because both would render as the same quantity.
 *
 * **Decision utility is deliberately absent.** The card carries it for
 * the winner only, and a mean of `episode_decision_utility` taken here
 * would be exactly that second scoring path. The card's ΔU and its
 * interval are where that comparison lives.
 *
 * Two rows *are* reductions over the episode column, and they are
 * descriptive rather than scored: the worst clearance the run ever
 * reached, and the median episode duration. Neither is a quantity the
 * platform defines elsewhere, so there is nothing for them to disagree
 * with.
 */

import type { EpisodeOutcome, RunCandidate } from "@/lib/decisions";

export type Direction = "higher" | "lower" | "none";

export interface MetricRow {
  /** i18n key under `decisions.compare.`. */
  key: string;
  direction: Direction;
  /** One entry per candidate, in the order given. `null` where this run
   *  did not record it — never 0, which would read as a measurement. */
  values: (number | null)[];
  /** The digits alone, already rounded for display. `null` where the run
   *  did not record the value — the wording for that is translated, so
   *  it belongs to the component and not here.
   *
   *  There is deliberately no field spelling the number and unit
   *  together. One existed while the grid rendered a metric as a single
   *  string; it survived the switch to two lanes as an unread field
   *  whose only distinctive content was the `—` this row's absent case
   *  no longer uses. Two ways to render one value is one too many. */
  numberText: (string | null)[];
  /** `undefined` for a bare count. The cell still renders the slot, so
   *  one unitless row does not shove its number out of the column. */
  unit?: string;
  /** B−A on the display scale, signed, U+2212 for the minus.
   *  `undefined` unless there are exactly two candidates and both
   *  recorded the value. */
  deltaText?: string;
  /** The deployment's own limit, when the gate declared one. */
  threshold?: string;
}

function gateField(candidate: RunCandidate, gate: string, field: string): number | null {
  const verdict = candidate.gates?.[gate];
  if (!verdict || typeof verdict === "string") return null;
  const value = (verdict as Record<string, unknown>)[field];
  return typeof value === "number" ? value : null;
}

function gateText(candidate: RunCandidate | undefined, gate: string, field: string): string | undefined {
  if (!candidate) return undefined;
  const verdict = candidate.gates?.[gate];
  if (!verdict || typeof verdict === "string") return undefined;
  const value = (verdict as Record<string, unknown>)[field];
  return value === null || value === undefined ? undefined : String(value);
}

function episodesOf(candidate: RunCandidate): EpisodeOutcome[] {
  return candidate.episodes ?? [];
}

/** The lowest clearance the candidate ever reached, over the whole run.
 *
 * **Read from the report, not reduced here.** The scoring pass writes
 * `worst_clearance_m` and the export reads the same field, so the page
 * and the file cannot disagree about it.
 *
 * The local reduction survives as a fallback for runs stored before that
 * field existed — those still have the episode rows, and a number the
 * reader can have is better than a dash. `null` when the run kept
 * neither: the run measured clearance and did not keep it, which is not
 * the same as the robot never coming close to anything.
 */
export function worstClearance(candidate: RunCandidate): number | null {
  if (typeof candidate.worst_clearance_m === "number") return candidate.worst_clearance_m;
  const values = episodesOf(candidate)
    .map((one) => one.min_clearance)
    .filter((value) => Number.isFinite(value));
  return values.length > 0 ? Math.min(...values) : null;
}

/** Median episode duration.
 *
 * Also read from the report where present. The median has a real choice
 * in it — which way an even count rounds — and two implementations can
 * make it differently; the platform's is the one that counts.
 *
 * The median rather than the mean: one timeout parked at the
 * deployment's cap drags a mean by tens of seconds, and the number then
 * says more about the cap than about the stack.
 */
export function medianTravelTime(candidate: RunCandidate): number | null {
  if (typeof candidate.median_travel_time_s === "number") {
    return candidate.median_travel_time_s;
  }
  const values = episodesOf(candidate)
    .map((one) => one.travel_time_s)
    .filter((value) => Number.isFinite(value))
    .sort((left, right) => left - right);
  if (values.length === 0) return null;
  const middle = Math.floor(values.length / 2);
  return values.length % 2 === 1 ? values[middle] : (values[middle - 1] + values[middle]) / 2;
}

/** How the failed episodes failed, commonest first. Only the reasons
 *  that actually occurred — a table of zeroes reads as a checklist. */
export function failureBreakdown(candidate: RunCandidate): [string, number][] {
  const counts = new Map<string, number>();
  for (const one of episodesOf(candidate)) {
    if (one.success) continue;
    const reason = one.failure_reason ?? "unknown";
    counts.set(reason, (counts.get(reason) ?? 0) + 1);
  }
  return [...counts.entries()].sort((left, right) => right[1] - left[1]);
}

/** A quantity's number and its unit, kept apart at the source.
 *
 * **The unit has to be a separate field, not something parsed back out
 * of the rendered string.** The grid aligns decimal points across rows,
 * which needs the unit in a column of its own; `ms` is wider than `m` is
 * wider than `MB`, so right-aligning `17.89 ms` against `0.470 m` still
 * leaves the decimals ragged. And splitting `text` on a space to
 * recover the parts would be exactly the string-parsing this module
 * exists to make unnecessary — it would also silently produce
 * `17.89 ms ms` the first time a caller rendered both.
 *
 * `text` stays, unchanged, spelling both together. Older callers read
 * it, and a formatter that had two ways to produce one string would be
 * two things to keep in step.
 */
interface Format {
  /** The digits alone. */
  number: (value: number) => string;
  /** Empty for a bare count, which has no unit to print. */
  unit: string;
  /** How a *difference* in this quantity reads. Not always the unit: a
   *  gap between two percentages is percentage points, and calling it
   *  `%` would say the gap was a proportion of a proportion. */
  deltaUnit?: string;
}

const percent: Format = {
  number: (value) => (value * 100).toFixed(1),
  unit: "%",
  deltaUnit: "pp",
};
const ms: Format = { number: (value) => value.toFixed(2), unit: "ms" };
const seconds: Format = { number: (value) => value.toFixed(1), unit: "s" };
const metres: Format = { number: (value) => value.toFixed(3), unit: "m" };
const megabytes: Format = { number: (value) => value.toFixed(1), unit: "MB" };
const count: Format = { number: (value) => String(Math.round(value)), unit: "" };

/** The B−A difference, formatted on the display scale.
 *
 * A rate is stored as `0.7` and shown as `70.0 %`, so a raw difference
 * of `0.02` has to print as `+2.0 pp` — printing `+0.02` beside two
 * numbers reading `70.0 %` and `72.0 %` is a third scale on one row.
 *
 * Signed always, with U+2212 for the minus: the hyphen-minus is
 * narrower than the digits beside it and breaks the tabular column the
 * rest of this file works to keep.
 */
function deltaText(format: Format, values: (number | null)[]): string | undefined {
  if (values.length !== 2) return undefined;
  const [first, second] = values;
  // One side missing means there is no difference to state — not a
  // difference of zero.
  if (first === null || second === null) return undefined;
  const unit = format.deltaUnit ?? format.unit;
  const scaled = format.number(second - first);
  // Sign only a real difference. `+0.00 ms` claims a direction the
  // measurement does not have, and a value just under zero would round
  // to `−0.00` — a minus sign on nothing.
  const signed =
    Number(scaled) === 0
      ? scaled.replace("-", "")
      : scaled.startsWith("-")
        ? `−${scaled.slice(1)}`
        : `+${scaled}`;
  return unit ? `${signed} ${unit}` : signed;
}

function row(
  key: string,
  direction: Direction,
  candidates: RunCandidate[],
  read: (candidate: RunCandidate) => number | null,
  format: Format,
  threshold?: string,
): MetricRow {
  const values = candidates.map(read);
  return {
    key,
    direction,
    values,
    // `null`, not a dash: "did not record it" and "measured zero" are
    // opposite readings, and one glyph served both. The component says
    // which in words — the wording is translated, and this module has no
    // dictionary.
    numberText: values.map((value) => (value === null ? null : format.number(value))),
    unit: format.unit || undefined,
    deltaText: deltaText(format, values),
    threshold,
  };
}

/** Every end-of-run comparison row, for any number of candidates. */
export function comparisonRows(candidates: RunCandidate[]): MetricRow[] {
  const first = candidates[0];
  return [
    row("successRate", "higher", candidates, (c) => c.success_rate, percent,
      gateText(first, "G3", "threshold")),
    row("collisions", "lower", candidates, (c) => gateField(c, "G2", "observed"), count),
    row("collisionBound", "lower", candidates,
      (c) => gateField(c, "G2", "upper_bound_95"), percent),
    row("noPathRate", "lower", candidates, (c) => gateField(c, "G1", "no_path_rate"), percent,
      gateText(first, "G1", "threshold")),
    row("worstClearance", "higher", candidates, worstClearance, metres),
    row("medianTravel", "lower", candidates, medianTravelTime, seconds),
    row("p99", "lower", candidates, (c) => c.pooled_p99_latency_ms, ms,
      gateText(first, "G4", "threshold_ms")),
    row("memory", "lower", candidates, (c) => gateField(c, "G5", "memory_estimate_mb"),
      megabytes, gateText(first, "G5", "available_ram_mb")),
    row("distinctEpisodes", "higher", candidates, (c) => c.n_distinct_episodes, count),
    // **No direction.** Replanning is already charged in travel time and
    // in latency, and the deployment declares no replan budget; marking
    // a winner here would price it twice and invent a rule nobody wrote
    // down. Shown because it is evidence about behaviour.
    row("replans", "none", candidates, (c) => c.replan_count ?? null, count),
  ];
}

/** Differences below this share of the row's scale are not called. */
const TIE_TOLERANCE = 1e-3;

/** Which candidates lead a row, as indices into `values`.
 *
 * A *set*, not a winner: with three candidates two can be equally best,
 * and picking one of them would be a coin toss rendered as a result.
 *
 * Empty when the row has no direction, when fewer than two candidates
 * recorded it, and when every one of them ties — a row where nobody is
 * ahead should not paint somebody green.
 */
export function leaders(row: MetricRow): number[] {
  if (row.direction === "none") return [];
  const known = row.values
    .map((value, index) => ({ value, index }))
    .filter((entry): entry is { value: number; index: number } => entry.value !== null);
  if (known.length < 2) return [];
  const best = known.reduce((carry, entry) =>
    (row.direction === "higher" ? entry.value > carry.value : entry.value < carry.value)
      ? entry
      : carry,
  );
  const scale = Math.max(...known.map((entry) => Math.abs(entry.value)), 1);
  const winners = known.filter(
    (entry) => Math.abs(entry.value - best.value) <= TIE_TOLERANCE * scale,
  );
  return winners.length === known.length ? [] : winners.map((entry) => entry.index);
}
