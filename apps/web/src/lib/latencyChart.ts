/** What the planner-latency chart plots, decided apart from the SVG.
 *
 * The shape is the easy half. The decisions worth being wrong about are
 * the scale and the gaps, and neither is visible in a screenshot:
 *
 * **A tick with no planning is not a tick that took zero milliseconds.**
 * The column carries 0 where the planner did not run, and a polyline
 * through those zeros dives to the axis between replans — drawing a
 * sawtooth that looks like wildly varying latency when the truth is
 * "nothing happened here". Those points break the line instead.
 *
 * **The vertical scale has to survive four orders of magnitude.** A
 * healthy run sits at 3–11 ms against a 50 ms budget; a stuck one peaked
 * at 3032 ms. The axis therefore always includes the budget, so a run
 * with headroom shows the line low and the threshold above it, and a run
 * that blew through shows the reverse. No log trickery: a reader who has
 * to remember the axis is logarithmic will misread the one chart that
 * matters.
 *
 * **The chart draws only as far as the replay has got, and its scale
 * knows only what it has seen.** Taking the maximum over the whole
 * episode would be stable and would also give the ending away — the
 * axis topping out at 3000 ms announces a spike several seconds before
 * it happens. So the vertical extent is a *running* maximum. It only
 * ever grows, which is what keeps the shape from jittering: a scale
 * free to shrink would redraw the whole line every time a peak scrolled
 * out of relevance.
 *
 * The horizontal extent is the opposite — fixed to the full episode
 * from the first frame. A time axis that grew with the playhead would
 * hold the line at full width and squash its shape as it went, which
 * reads as the planner getting steadier when nothing changed.
 */

/** One unbroken run of samples. A gap ends a segment. */
export interface LatencySegment {
  points: { t: number; ms: number }[];
}

export interface LatencyPlot {
  segments: LatencySegment[];
  /** Seconds; the horizontal extent. */
  tMax: number;
  /** Milliseconds; the vertical extent, always at or above the budget. */
  msMax: number;
  /** G4's threshold in milliseconds. */
  budgetMs: number;
  /** True when something crossed the budget **in the part drawn so
   *  far**. Live, like the rest of the chart: a badge that lit up for a
   *  spike ten seconds ahead would be reporting the future. */
  breached: boolean;
}

/** Headroom above the tallest thing drawn, so a peak is not clipped by
 *  the frame and mistaken for a plateau. */
const HEADROOM = 1.08;

export function latencyPlot(
  times: readonly number[],
  latencies: readonly number[],
  controlPeriodS: number,
  /** Last trace row to draw. Omitted means the whole episode — used by
   *  nothing on the decision page, where the chart is a live reading,
   *  and kept for a caller that wants the finished shape. */
  upto?: number,
  /** Least value the time axis may end at, in seconds.
   *
   * **Two charts drawn side by side are read as one comparison.** Each
   * one scaled to its own episode gives a 22.0 s run and a 38.8 s run
   * exactly the same width, and the reader takes the two for the same
   * length — the slower candidate's chart looks no busier, only
   * steeper. Passing the pair's longer duration here leaves the shorter
   * episode ending part-way across its frame, which is the fact.
   *
   * Omitted means this chart stands alone and scales to itself. */
  tFloorS?: number,
): LatencyPlot | null {
  const budgetMs = controlPeriodS * 1000;
  const count = Math.min(times.length, latencies.length);
  if (count === 0) return null;
  const last = upto === undefined ? count - 1 : Math.max(0, Math.min(upto, count - 1));

  const segments: LatencySegment[] = [];
  let current: { t: number; ms: number }[] = [];
  let peak = 0;

  for (let index = 0; index <= last; index += 1) {
    const ms = latencies[index];
    // `> 0` rather than `!= null`: the column stores 0 for "the planner
    // did not run", and that is a gap, not a measurement.
    if (Number.isFinite(ms) && ms > 0) {
      current.push({ t: times[index], ms });
      peak = Math.max(peak, ms);
    } else if (current.length > 0) {
      segments.push({ points: current });
      current = [];
    }
  }
  if (current.length > 0) segments.push({ points: current });
  if (segments.length === 0) return null;

  return {
    segments,
    // The whole episode, not the part drawn: a time axis that grew with
    // the playhead would squash the shape as it went.
    tMax: Math.max(times[count - 1] ?? 0, tFloorS ?? 0, 1e-6),
    // A running maximum over what has been drawn, and never below the
    // budget. Scaling to the data alone would drop the threshold off
    // the top of a healthy run; scaling to the whole episode would give
    // away a spike that has not happened yet.
    msMax: Math.max(peak, budgetMs) * HEADROOM,
    budgetMs,
    breached: peak > budgetMs,
  };
}


/** Where the playhead sits, 0–1 across the chart. `null` outside. */
export function playheadFraction(plot: LatencyPlot, timeS: number): number | null {
  if (!Number.isFinite(timeS) || timeS < 0 || timeS > plot.tMax) return null;
  return timeS / plot.tMax;
}

/** The chart's box, in viewBox units.
 *
 * Here rather than in the component because two things depend on these
 * numbers agreeing: where the line is drawn, and where a click lands.
 * A second copy of the padding would put every seek off by 44 units of
 * viewBox — a couple of seconds on a short episode — and the chart would
 * still look right, because the line and the playhead would both be
 * drawn from the copy the component held.
 */
export const CHART = {
  width: 600,
  height: 120,
  padLeft: 44,
  padRight: 8,
  padTop: 10,
  padBottom: 18,
} as const;

export const PLOT_WIDTH = CHART.width - CHART.padLeft - CHART.padRight;
export const PLOT_HEIGHT = CHART.height - CHART.padTop - CHART.padBottom;

/** The episode time under a click, given where it landed across the
 *  rendered chart (0 at the left edge of the element, 1 at the right).
 *
 * Clamped to the episode rather than returning something outside it: the
 * axis labels and the padding are part of the target, and a click on the
 * "0 s" label should seek to the start, not to a negative time the
 * scrubber would reject.
 */
export function timeAtFraction(plot: LatencyPlot, fractionOfWidth: number): number {
  const x = fractionOfWidth * CHART.width;
  const withinPlot = (x - CHART.padLeft) / PLOT_WIDTH;
  return Math.max(0, Math.min(1, withinPlot)) * plot.tMax;
}
