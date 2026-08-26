/** What the F09 charts are allowed to draw.
 *
 * The builders are tested rather than the SVG because the SVG is not
 * where the risk is. A chart misleads by including something it should
 * have dropped, dropping something silently, or drawing a missing value
 * as a zero — all three decisions happen here, before recharts sees
 * anything.
 */

import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import {
  buildDifficultyCurve,
  buildGapSeries,
  buildIntervalSeries,
  filenameFromDisposition,
  INTERVAL_METRICS,
  seriesColor,
  SERIES_COLORS,
} from "@/lib/charts";
import type { AlgorithmAggregate } from "@/lib/benchmarkTypes";
import type {
  DifficultyCalibrationSummary,
  DifficultyLabel,
  GeneralizationSummary,
  Leaderboard,
  LeaderboardEntry,
} from "@/lib/platformTypes";

function label(name: string, value: number, extra: Partial<DifficultyLabel> = {}): DifficultyLabel {
  return {
    scenario_name: name,
    value,
    ci95: [Math.max(0, value - 0.1), Math.min(1, value + 0.1)],
    band: "moderate",
    calibration_version: "1.0.0",
    baseline_algorithm: "astar+dwa",
    seed_count: 30,
    adequate: true,
    stale: false,
    ...extra,
  };
}

function calibration(labels: DifficultyLabel[]): DifficultyCalibrationSummary {
  return {
    calibration_version: "1.0.0",
    baseline: {
      algorithm: "astar+dwa",
      algorithm_config: {},
      replanning_enabled: false,
      seeds: [0, 1],
      robot_profile: {},
      benchmark_spec_version: "1",
      protocol_version: "1.0.0",
      git_sha: "abc123",
    },
    scenarios: labels,
    coverage: {
      calibration_version: "1.0.0",
      scenario_count: labels.length,
      min_difficulty: 0,
      max_difficulty: 1,
      spread: 1,
      band_counts: {},
      midrange_count: labels.length,
      uncalibrated: [],
      warnings: [],
    },
    notes: null,
  };
}

function entry(
  algorithm: string,
  scenario: string,
  successRate: number,
  extra: Partial<LeaderboardEntry> = {},
): LeaderboardEntry {
  return {
    algorithm,
    benchmark_id: `${algorithm}-${scenario}`,
    benchmark_name: "b",
    conditions_checksum: `checksum-${scenario}`,
    map_name: "m",
    scenario_name: scenario,
    episodes: 10,
    success_rate: successRate,
    collision_rate: 0,
    mean_travel_time: 10,
    mean_path_efficiency: 1,
    mean_smoothness: 0.1,
    worst_min_clearance: 0.5,
    mean_local_planning_latency: 0.005,
    overall_score: 0.9,
    global_observation_class: "full_static_map",
    local_observation_class: "lidar_only",
    requires_global_path: true,
    ...extra,
  };
}

function board(entries: LeaderboardEntry[]): Leaderboard {
  const groups = new Map<string, LeaderboardEntry[]>();
  for (const item of entries) {
    groups.set(item.conditions_checksum, [...(groups.get(item.conditions_checksum) ?? []), item]);
  }
  return {
    weights: { success: 0.4, safety: 0.3, efficiency: 0.2, smoothness: 0.1 },
    score_formula: "score = …",
    groups: [...groups.entries()].map(([checksum, rows]) => ({
      conditions_checksum: checksum,
      map_name: "m",
      scenario_name: rows[0].scenario_name,
      seeds: [1, 2],
      entries: rows,
      local_observation_class: "lidar_only" as const,
      global_observation_class: "full_static_map" as const,
      cross_observation_class_warning: false,
    })),
  };
}

describe("the difficulty curve", () => {
  it("joins results to measured difficulty by scenario", () => {
    const curve = buildDifficultyCurve(
      board([entry("astar+dwa", "open_space", 1), entry("astar+dwa", "doorway", 0.5)]),
      calibration([label("open_space", 0.1), label("doorway", 0.6)]),
    );
    expect(curve.series).toHaveLength(1);
    // Sorted along the axis, or the line doubles back on itself.
    expect(curve.series[0].points.map((point) => point.scenario)).toEqual([
      "open_space",
      "doorway",
    ]);
    expect(curve.series[0].points[1].difficulty).toBe(0.6);
    expect(curve.series[0].points[1].successRate).toBe(0.5);
  });

  it("drops scenarios with no measured difficulty and names them", () => {
    const curve = buildDifficultyCurve(
      board([entry("astar+dwa", "open_space", 1), entry("astar+dwa", "brand_new", 0.2)]),
      calibration([label("open_space", 0.1)]),
    );
    expect(curve.series[0].points.map((point) => point.scenario)).toEqual(["open_space"]);
    // The exclusion is reported, not silent: a curve drawn from half the
    // scenarios is not the whole picture.
    expect(curve.uncalibrated).toEqual(["brand_new"]);
  });

  it("averages repeat runs of a scenario instead of pooling them", () => {
    // Two reports on the same scenario, wildly different episode counts.
    // Pooling would make the point mostly the bigger run.
    const curve = buildDifficultyCurve(
      board([
        entry("astar+dwa", "doorway", 1, {
          benchmark_id: "one",
          conditions_checksum: "c1",
          episodes: 100,
        }),
        entry("astar+dwa", "doorway", 0, {
          benchmark_id: "two",
          conditions_checksum: "c2",
          episodes: 2,
        }),
      ]),
      calibration([label("doorway", 0.6)]),
    );
    const point = curve.series[0].points[0];
    expect(point.successRate).toBe(0.5);
    expect(point.reportCount).toBe(2);
    expect(point.episodes).toBe(102);
  });

  it("plots a stale difficulty but flags it", () => {
    const curve = buildDifficultyCurve(
      board([entry("astar+dwa", "doorway", 0.5)]),
      calibration([label("doorway", 0.6, { stale: true })]),
    );
    expect(curve.series[0].points[0].stale).toBe(true);
    expect(curve.stale).toEqual(["doorway"]);
  });

  it("draws nothing at all without a calibration", () => {
    // The fallback that must never happen: using curriculum order as an
    // axis would produce a chart that looks measured and is not.
    const curve = buildDifficultyCurve(board([entry("astar+dwa", "doorway", 0.5)]), null);
    expect(curve.series).toEqual([]);
    expect(curve.calibrationVersion).toBeNull();
    expect(curve.uncalibrated).toEqual(["doorway"]);
  });

  it("keeps one line per stack", () => {
    const curve = buildDifficultyCurve(
      board([
        entry("astar+dwa", "doorway", 0.5),
        entry("rrtstar+dwa", "doorway", 0.9, { conditions_checksum: "checksum-doorway" }),
      ]),
      calibration([label("doorway", 0.6)]),
    );
    expect(curve.series.map((series) => series.algorithm)).toEqual([
      "astar+dwa",
      "rrtstar+dwa",
    ]);
  });
});

function aggregate(
  algorithm: string,
  extra: Partial<AlgorithmAggregate> = {},
): AlgorithmAggregate {
  return {
    algorithm,
    episodes: 10,
    success_rate: 1,
    collision_rate: 0,
    timeout_rate: 0,
    stuck_rate: 0,
    no_progress_rate: 0,
    no_global_path_rate: 0,
    mean_travel_time_successful: 10,
    mean_trajectory_length_successful: 10,
    mean_path_efficiency_successful: 1,
    mean_smoothness_successful: 0.1,
    mean_min_clearance: 0.5,
    worst_min_clearance: 0.4,
    mean_local_planning_latency: 0.005,
    max_local_planning_latency: 0.008,
    mean_global_planning_time: 0.01,
    median_travel_time_successful: null,
    iqr_travel_time_successful: null,
    ci95_travel_time_successful: null,
    median_path_efficiency_successful: null,
    iqr_path_efficiency_successful: null,
    ci95_path_efficiency_successful: null,
    median_smoothness_successful: null,
    iqr_smoothness_successful: null,
    ci95_smoothness_successful: null,
    ci95_success_rate: null,
    ...extra,
  };
}

const TRAVEL = INTERVAL_METRICS[0];

describe("median, IQR and CI95 bars", () => {
  it("turns bounds into offsets from the median, both ways", () => {
    const series = buildIntervalSeries(
      [
        aggregate("astar+dwa", {
          median_travel_time_successful: 10,
          iqr_travel_time_successful: [8, 13],
          ci95_travel_time_successful: [9, 11],
        }),
      ],
      TRAVEL,
    );
    expect(series.rows[0].iqrError).toEqual([2, 3]);
    expect(series.rows[0].ciError).toEqual([1, 1]);
    // The absolute bounds survive for the tooltip: an offset alone tells
    // the reader nothing they can quote.
    expect(series.rows[0].iqr).toEqual([8, 13]);
  });

  it("omits a stack with no median instead of drawing a zero bar", () => {
    const series = buildIntervalSeries(
      [
        aggregate("astar+dwa", { median_travel_time_successful: 10 }),
        aggregate("never+arrives"),
      ],
      TRAVEL,
    );
    expect(series.rows.map((row) => row.algorithm)).toEqual(["astar+dwa"]);
    // A zero-height bar would read as "it was instant".
    expect(series.missing).toEqual(["never+arrives"]);
  });

  it("keeps a bar whose interval is missing", () => {
    const series = buildIntervalSeries(
      [aggregate("astar+dwa", { median_travel_time_successful: 10 })],
      TRAVEL,
    );
    expect(series.rows).toHaveLength(1);
    expect(series.rows[0].ciError).toBeNull();
    expect(series.rows[0].iqrError).toBeNull();
  });

  it("never draws a whisker pointing backwards", () => {
    // A bound on the wrong side of the median is a data problem; a
    // reversed whisker reads as a rendering bug and hides it.
    const series = buildIntervalSeries(
      [
        aggregate("odd", {
          median_travel_time_successful: 10,
          ci95_travel_time_successful: [12, 14],
        }),
      ],
      TRAVEL,
    );
    expect(series.rows[0].ciError).toEqual([0, 4]);
  });

  it("covers exactly the metrics that have a distribution", () => {
    expect(INTERVAL_METRICS.map((metric) => metric.key)).toEqual([
      "travelTime",
      "pathEfficiency",
      "smoothness",
    ]);
  });
});

function summary(entries: GeneralizationSummary["entries"]): GeneralizationSummary {
  return {
    entries,
    metrics: [
      { name: "success_rate", higher_is_better: true },
      { name: "median_travel_time_successful", higher_is_better: false },
    ],
    protocol_versions: ["1.0.0"],
    dev_scenarios: ["open_space"],
    holdout_scenarios: ["intersection"],
    unassigned_report_count: 0,
    holdout_usage: [],
    warnings: [],
  };
}

const side = (split: "dev" | "holdout", metrics: Record<string, number>) => ({
  split,
  scenarios: ["s"],
  report_count: 1,
  episodes: 10,
  metrics,
  metric_scenario_counts: {},
  statistically_adequate: true,
});

describe("the generalization gap bars", () => {
  it("reads the sign against the metric's direction", () => {
    const [successRate, travelTime] = buildGapSeries(
      summary([
        {
          algorithm: "astar+dwa",
          dev: side("dev", { success_rate: 0.9, median_travel_time_successful: 10 }),
          holdout: side("holdout", { success_rate: 0.6, median_travel_time_successful: 14 }),
          gap: { success_rate: 0.3, median_travel_time_successful: -4 },
          warnings: [],
        },
      ]),
    );
    // Higher success is better, so scoring higher on dev is a degradation.
    expect(successRate.rows[0].worse).toBe(true);
    // Lower travel time is better, so being slower on held-out (a
    // negative gap) is the same story with the opposite sign.
    expect(travelTime.rows[0].worse).toBe(true);
  });

  it("names a stack missing one side rather than charting it as zero", () => {
    const [successRate] = buildGapSeries(
      summary([
        {
          algorithm: "only+dev",
          dev: side("dev", { success_rate: 0.9 }),
          holdout: null,
          gap: null,
          warnings: [],
        },
      ]),
    );
    expect(successRate.incomplete).toEqual(["only+dev"]);
    expect(successRate.rows[0].holdout).toBeNull();
    expect(successRate.rows[0].gap).toBeNull();
    expect(successRate.rows[0].worse).toBeNull();
  });

  it("drops a stack that has neither side for a metric", () => {
    const [, travelTime] = buildGapSeries(
      summary([
        {
          algorithm: "never+arrives",
          dev: side("dev", { success_rate: 0 }),
          holdout: side("holdout", { success_rate: 0 }),
          gap: { success_rate: 0 },
          warnings: [],
        },
      ]),
    );
    expect(travelTime.rows).toEqual([]);
  });

  it("returns nothing without a summary", () => {
    expect(buildGapSeries(null)).toEqual([]);
  });
});

describe("the download filename", () => {
  it("uses the name the server chose", () => {
    expect(
      filenameFromDisposition('attachment; filename="benchmark-run-abc123.md"', "abc123"),
    ).toBe("benchmark-run-abc123.md");
  });

  it("returns the caller's fallback verbatim when the header cannot be read", () => {
    // It used to append `.md` itself. That was true while Markdown was
    // the only export and became a lie the moment a workbook came down
    // the same pipe: the file saved as `.md` and Excel refused to open
    // it. The extension is the caller's to choose.
    expect(filenameFromDisposition(null, "decision-abc123.xlsx")).toBe("decision-abc123.xlsx");
    expect(filenameFromDisposition("attachment", "decision-abc123.md")).toBe(
      "decision-abc123.md",
    );
  });

  it("never invents an extension of its own", () => {
    expect(filenameFromDisposition(null, "plain-name")).toBe("plain-name");
  });

  it("is reached often, not rarely", () => {
    // A browser withholds `Content-Disposition` from JavaScript across
    // origins unless the server exposes it, and the app and the API sit
    // on different ports — so this path runs on every download until
    // the CORS header is in place.
    const cors = readFileSync(
      join(process.cwd(), "..", "api", "planbench_api", "main.py"),
      "utf8",
    );
    expect(cors).toContain('expose_headers=["Content-Disposition"]');
  });

  it("never lets a server-supplied name carry a path separator", () => {
    expect(
      filenameFromDisposition('attachment; filename="../../etc/passwd"', "abc123"),
    ).not.toContain("/");
  });
});

describe("series colours", () => {
  it("wraps rather than running out", () => {
    expect(seriesColor(0)).toBe(SERIES_COLORS[0]);
    expect(seriesColor(SERIES_COLORS.length)).toBe(SERIES_COLORS[0]);
  });
});
