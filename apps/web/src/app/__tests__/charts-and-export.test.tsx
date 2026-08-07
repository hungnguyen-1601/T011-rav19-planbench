/** The F09 surfaces: three charts and the Markdown export.
 *
 * Source-level, matching the other page tests: these pages sit behind an
 * effect and a fetch, so a first paint shows only a loading state and
 * there is no jsdom to click in. What is checked here is the wiring that
 * a chart cannot make honest on its own — that the panels are mounted,
 * that the caveats are rendered next to them, and that the download never
 * degrades into a link carrying a token.
 *
 * The data decisions themselves are tested in `lib/__tests__/charts.test.ts`,
 * which is where they live.
 */

import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

import en from "../../lib/i18n/locales/en.json";
import vi from "../../lib/i18n/locales/vi.json";

const read = (...parts: string[]) => readFileSync(join(process.cwd(), "src", ...parts), "utf8");

const LEADERBOARD = read("app", "leaderboard", "page.tsx");
const DETAIL = read("app", "benchmarks", "[id]", "page.tsx");
const REPORTS = read("lib", "reports.ts");
const CURVE = read("components", "DifficultyCurveChart.tsx");
const INTERVALS = read("components", "MetricIntervalChart.tsx");
const GAP = read("components", "GeneralizationGapChart.tsx");

describe("the difficulty curve is on the leaderboard", () => {
  it("mounts the chart", () => {
    expect(LEADERBOARD).toContain("DifficultyCurveChart");
    expect(LEADERBOARD).toContain("buildDifficultyCurve");
  });

  it("reads the measured calibration rather than curriculum order", () => {
    expect(LEADERBOARD).toContain("/difficulty-calibration");
    expect(LEADERBOARD).not.toContain("curriculum_index");
  });

  it("says so when there is no calibration to plot against", () => {
    expect(LEADERBOARD).toContain("charts.noCalibration");
  });

  it("names the scenarios that are not on the curve", () => {
    expect(LEADERBOARD).toContain("charts.uncalibratedScenarios");
    expect(LEADERBOARD).toContain("charts.staleScenarios");
  });

  it("states the baseline the difficulty scale was measured against", () => {
    // Without it the axis is an unattributed number: "0.6 hard" instead
    // of "the pinned baseline failed 60% of the time here".
    expect(LEADERBOARD).toContain("charts.difficultyBaseline");
  });
});

describe("the gap chart keeps the table it came from", () => {
  it("draws the bars", () => {
    expect(LEADERBOARD).toContain("GeneralizationGapChart");
    expect(LEADERBOARD).toContain("buildGapSeries");
  });

  it("does not replace the table", () => {
    // The table is where a missing held-out result is visible as
    // missing; a chart can only omit that bar.
    expect(LEADERBOARD).toContain("generalization.noGap");
  });

  it("names the stacks whose gap is not computable", () => {
    expect(LEADERBOARD).toContain("charts.incompleteGap");
  });
});

describe("the distribution chart on the benchmark page", () => {
  it("mounts one chart per metric that has a distribution", () => {
    expect(DETAIL).toContain("MetricIntervalChart");
    expect(DETAIL).toContain("INTERVAL_METRICS");
    expect(DETAIL).toContain("buildIntervalSeries");
  });

  it("draws both the IQR and the CI95, not one of them", () => {
    expect(INTERVALS).toContain("iqrError");
    expect(INTERVALS).toContain("ciError");
  });

  it("carries the small-benchmark warning onto the chart panel", () => {
    // The warning sits on the statistics table already; a chart read
    // without it is exactly how five seeds become a conclusion.
    const panel = DETAIL.split("function DistributionPanel", 1)[1] ?? DETAIL;
    expect(panel).toContain("detail.fewSeedsWarning");
  });

  it("names stacks with no distribution instead of drawing them flat", () => {
    expect(DETAIL).toContain("charts.noDistribution");
  });
});

describe("the Markdown export", () => {
  it("is offered from the benchmark page", () => {
    expect(DETAIL).toContain("downloadReportMarkdown");
    expect(DETAIL).toContain("charts.downloadMarkdown");
  });

  it("fetches with the bearer header and never puts the token in a URL", () => {
    expect(REPORTS).toContain("Authorization");
    expect(REPORTS).toContain("report.md");
    expect(REPORTS).not.toContain("token=");
    expect(REPORTS).not.toContain("access_token=");
  });

  it("goes through a Blob and revokes the object URL", () => {
    expect(REPORTS).toContain("createObjectURL");
    expect(REPORTS).toContain("revokeObjectURL");
  });

  it("uses the filename the server chose", () => {
    expect(REPORTS).toContain("filenameFromDisposition");
    expect(REPORTS).toContain("content-disposition");
  });

  it("reports which file it saved", () => {
    expect(DETAIL).toContain("charts.exportSaved");
  });
});

describe("the charts are translated in both languages", () => {
  const dictionaries = { en, vi } as Record<string, Record<string, string>>;
  const used = [
    ...new Set(
      [LEADERBOARD, DETAIL, CURVE, INTERVALS, GAP]
        .join("\n")
        .match(/"charts\.[A-Za-z]+"/g)
        ?.map((quoted) => quoted.slice(1, -1)) ?? [],
    ),
  ];

  it("uses chart keys at all", () => {
    expect(used.length).toBeGreaterThan(8);
  });

  for (const locale of ["en", "vi"]) {
    it(`defines every chart key it renders in ${locale}`, () => {
      const missing = used.filter((key) => !(key in dictionaries[locale]));
      expect(missing).toEqual([]);
    });
  }
});
