/** Data shaping for the F09 charts.
 *
 * Kept apart from the components on purpose. A chart is where a reader is
 * most likely to stop asking questions — the eye accepts a line before
 * the mind checks what it was drawn from — so the joins and the
 * exclusions that decide what the line *is* are plain functions with
 * tests, not logic buried in JSX.
 *
 * The rules all three builders follow:
 *
 * - **A missing value is never plotted as zero.** It is dropped, and the
 *   fact that it was dropped comes back with the series so the panel can
 *   say so. A gap in a line is a gap in the data; a zero is a claim.
 * - **Nothing is joined across incomparable conditions.** The difficulty
 *   curve joins on scenario name, which is exactly the axis difficulty is
 *   measured on; it does not merge results that the leaderboard put in
 *   different groups for any other reason.
 * - **The caveats are part of the return value.** `uncalibrated`,
 *   `stale`, `reportCount` — the panel is not allowed to render a curve
 *   without knowing what is not in it.
 */

import type { AlgorithmAggregate } from "./benchmarkTypes";
import type {
  DifficultyCalibrationSummary,
  DifficultyLabel,
  GeneralizationSummary,
  Leaderboard,
} from "./platformTypes";

/** Series colours, in assignment order.
 *
 * Fixed hexes rather than the theme's `--accent` family: a chart needs
 * several distinguishable series at once, and the theme only defines one
 * accent. These are mid-tone on purpose so they hold contrast against
 * both the light and the dark panel background. */
export const SERIES_COLORS = [
  "#4c9aff",
  "#e0823d",
  "#3fb950",
  "#c678dd",
  "#d29922",
  "#56b6c2",
] as const;

export function seriesColor(index: number): string {
  return SERIES_COLORS[index % SERIES_COLORS.length];
}

// -- difficulty curve -------------------------------------------------

/** One stack's success rate at one measured scenario difficulty. */
export interface DifficultyPoint {
  scenario: string;
  /** `1 - success_rate(pinned baseline)`, the x axis. */
  difficulty: number;
  ci95: [number, number];
  /** Mean success rate over the reports that ran this scenario. */
  successRate: number;
  /** How many accepted reports contributed. Above one, the point is an
   *  average and the reader should know before reading it as a run. */
  reportCount: number;
  episodes: number;
  /** True when the scenario changed after its difficulty was measured. */
  stale: boolean;
}

export interface DifficultySeries {
  algorithm: string;
  points: DifficultyPoint[];
}

export interface DifficultyCurve {
  series: DifficultySeries[];
  /** Scenarios with results but no measured difficulty. They have no x
   *  coordinate, so they are absent from every line — named here because
   *  a curve drawn from half the scenarios is not the whole picture. */
  uncalibrated: string[];
  /** Calibrated scenarios whose definition has since changed. Plotted,
   *  flagged: dropping them would leave a hole that reads as "never
   *  run", which is a different problem. */
  stale: string[];
  calibrationVersion: string | null;
  baselineAlgorithm: string | null;
}

/** Success rate against measured difficulty, one line per stack.
 *
 * The join is scenario name: the leaderboard says how each stack did on a
 * scenario, the calibration says how hard that scenario is for the pinned
 * baseline. Neither half means much alone — a 100% success rate says
 * nothing without knowing whether the scenario was trivial, which is the
 * whole argument for P03.
 */
export function buildDifficultyCurve(
  board: Leaderboard | null,
  calibration: DifficultyCalibrationSummary | null,
): DifficultyCurve {
  const labels = new Map<string, DifficultyLabel>(
    (calibration?.scenarios ?? []).map((label) => [label.scenario_name, label]),
  );
  const empty: DifficultyCurve = {
    series: [],
    uncalibrated: [],
    stale: [],
    calibrationVersion: calibration?.calibration_version ?? null,
    baselineAlgorithm: calibration?.baseline?.algorithm ?? null,
  };
  if (!board) return empty;

  // algorithm -> scenario -> the runs of that pair
  const collected = new Map<
    string,
    Map<string, { rates: number[]; episodes: number }>
  >();
  const uncalibrated = new Set<string>();
  const stale = new Set<string>();

  for (const group of board.groups) {
    for (const entry of group.entries) {
      const label = labels.get(entry.scenario_name);
      if (!label) {
        uncalibrated.add(entry.scenario_name);
        continue;
      }
      if (label.stale) stale.add(entry.scenario_name);
      const byScenario = collected.get(entry.algorithm) ?? new Map();
      const bucket = byScenario.get(entry.scenario_name) ?? { rates: [], episodes: 0 };
      bucket.rates.push(entry.success_rate);
      bucket.episodes += entry.episodes;
      byScenario.set(entry.scenario_name, bucket);
      collected.set(entry.algorithm, byScenario);
    }
  }

  const series: DifficultySeries[] = [];
  for (const [algorithm, byScenario] of [...collected.entries()].sort()) {
    const points: DifficultyPoint[] = [];
    for (const [scenario, bucket] of byScenario) {
      const label = labels.get(scenario);
      if (!label) continue;
      points.push({
        scenario,
        difficulty: label.value,
        ci95: label.ci95,
        // Reports are averaged rather than pooled: running one scenario
        // ten times and another once must not make the point mostly the
        // first one.
        successRate: bucket.rates.reduce((sum, rate) => sum + rate, 0) / bucket.rates.length,
        reportCount: bucket.rates.length,
        episodes: bucket.episodes,
        stale: label.stale,
      });
    }
    points.sort((a, b) => a.difficulty - b.difficulty || a.scenario.localeCompare(b.scenario));
    if (points.length > 0) series.push({ algorithm, points });
  }

  return {
    ...empty,
    series,
    uncalibrated: [...uncalibrated].sort(),
    stale: [...stale].sort(),
  };
}

// -- median / IQR / CI95 ----------------------------------------------

/** A metric with the three field names its distribution lives under. */
export interface IntervalMetric {
  /** Stable identity for keying the rendered charts. */
  key: string;
  /** Full translation key of the heading. Reuses the comparison table's
   *  labels so the chart and the table above it cannot end up calling the
   *  same metric two different things. */
  labelKey: string;
  median: keyof AlgorithmAggregate;
  iqr: keyof AlgorithmAggregate;
  ci: keyof AlgorithmAggregate;
  digits: number;
  unit: string;
}

/** The metrics F09 asks for, minus the two that have no distribution.
 *
 * Clearance and latency are aggregated as worst/mean rather than as a
 * median with an interval, so there is nothing to draw an error bar from.
 * They stay in the table; inventing a spread for them here would be the
 * fabrication the whole panel exists to avoid. */
export const INTERVAL_METRICS: IntervalMetric[] = [
  {
    key: "travelTime",
    labelKey: "detail.travelOk",
    median: "median_travel_time_successful",
    iqr: "iqr_travel_time_successful",
    ci: "ci95_travel_time_successful",
    digits: 2,
    unit: "s",
  },
  {
    key: "pathEfficiency",
    labelKey: "detail.efficiency",
    median: "median_path_efficiency_successful",
    iqr: "iqr_path_efficiency_successful",
    ci: "ci95_path_efficiency_successful",
    digits: 3,
    unit: "",
  },
  {
    key: "smoothness",
    labelKey: "detail.smoothness",
    median: "median_smoothness_successful",
    iqr: "iqr_smoothness_successful",
    ci: "ci95_smoothness_successful",
    digits: 3,
    unit: "",
  },
];

/** One bar: the median, with the IQR and the CI95 as error offsets.
 *
 * Recharts reads an `ErrorBar` value as a `[below, above]` pair of
 * distances from the bar's own value, so the bounds are converted here
 * and the absolute numbers kept alongside for the tooltip. */
export interface IntervalRow {
  algorithm: string;
  median: number;
  iqrError: [number, number] | null;
  ciError: [number, number] | null;
  iqr: [number, number] | null;
  ci: [number, number] | null;
}

export interface IntervalSeries {
  rows: IntervalRow[];
  /** Stacks with no median for this metric — normally because they never
   *  reached the goal. Named rather than drawn as zero-height bars. */
  missing: string[];
}

function bounds(value: unknown): [number, number] | null {
  return Array.isArray(value) && value.length === 2 &&
    typeof value[0] === "number" &&
    typeof value[1] === "number"
    ? [value[0], value[1]]
    : null;
}

export function buildIntervalSeries(
  aggregates: AlgorithmAggregate[],
  metric: IntervalMetric,
): IntervalSeries {
  const rows: IntervalRow[] = [];
  const missing: string[] = [];
  for (const aggregate of aggregates) {
    const median = aggregate[metric.median];
    if (typeof median !== "number") {
      missing.push(aggregate.algorithm);
      continue;
    }
    const iqr = bounds(aggregate[metric.iqr]);
    const ci = bounds(aggregate[metric.ci]);
    rows.push({
      algorithm: aggregate.algorithm,
      median,
      iqr,
      ci,
      // Clamped at zero: a bound on the wrong side of the median would
      // otherwise draw a whisker pointing backwards, which reads as a
      // rendering bug rather than as the data problem it is.
      iqrError: iqr ? [Math.max(0, median - iqr[0]), Math.max(0, iqr[1] - median)] : null,
      ciError: ci ? [Math.max(0, median - ci[0]), Math.max(0, ci[1] - median)] : null,
    });
  }
  return { rows, missing };
}

// -- generalization gap -----------------------------------------------

export interface GapRow {
  algorithm: string;
  dev: number | null;
  holdout: number | null;
  gap: number | null;
  /** True when the gap is a degradation on held-out scenarios, given the
   *  metric's direction. Null when there is no gap to judge. */
  worse: boolean | null;
}

export interface GapSeries {
  metric: string;
  higherIsBetter: boolean;
  rows: GapRow[];
  /** Stacks missing one side entirely. Their bar is absent, not zero:
   *  "we never ran it on held-out" is not "it scored nothing there". */
  incomplete: string[];
}

/** Dev against held-out, one chart's worth of bars per metric. */
export function buildGapSeries(summary: GeneralizationSummary | null): GapSeries[] {
  if (!summary) return [];
  return summary.metrics.map((metric) => {
    const rows: GapRow[] = [];
    const incomplete: string[] = [];
    for (const entry of summary.entries) {
      const dev = entry.dev?.metrics[metric.name] ?? null;
      const holdout = entry.holdout?.metrics[metric.name] ?? null;
      const gap = entry.gap?.[metric.name] ?? null;
      if (dev === null || holdout === null) incomplete.push(entry.algorithm);
      if (dev === null && holdout === null) continue;
      rows.push({
        algorithm: entry.algorithm,
        dev,
        holdout,
        gap,
        worse: gap === null ? null : metric.higher_is_better ? gap > 0 : gap < 0,
      });
    }
    return { metric: metric.name, higherIsBetter: metric.higher_is_better, rows, incomplete };
  });
}

// -- download ---------------------------------------------------------

/** Filename the server asked for, or a fallback built from the id.
 *
 * `Content-Disposition` is parsed rather than guessed because the server
 * owns the name — it is the side that knows the benchmark's name and has
 * already made it safe. The fallback exists for the case where a proxy
 * strips the header. */
export function filenameFromDisposition(header: string | null, fallback: string): string {
  const quoted = header?.match(/filename\*?=(?:UTF-8'')?"?([^";]+)"?/i);
  const name = quoted?.[1]?.trim();
  // **The caller supplies the whole fallback, extension included.** This
  // used to append `.md` itself, which was true while Markdown was the
  // only export and became a lie the moment a workbook could come down
  // the same pipe — the file saved as `.md` and Excel refused it.
  //
  // The fallback is not rare, either: a browser withholds
  // `Content-Disposition` from JavaScript across origins unless the
  // server exposes it, and the app and the API sit on different ports.
  if (!name) return fallback;
  // Never let a server-supplied name walk out of the download folder.
  return name.replace(/[\\/]/g, "-");
}
