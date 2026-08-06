/** The dev/held-out surface (P05).
 *
 * What has to hold in the UI: a held-out scenario says so *before* the
 * benchmark is created, a stored result carries the split it ran under,
 * an unassigned scenario is labelled rather than shown as dev, and a
 * one-sided generalization gap prints "not computable" instead of a
 * zero.
 *
 * Source-level, matching the other page tests: these pages sit behind an
 * effect and a fetch, so a first paint shows only a loading state.
 */

import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

import en from "../../lib/i18n/locales/en.json";
import vi from "../../lib/i18n/locales/vi.json";

const read = (...parts: string[]) => readFileSync(join(process.cwd(), "src", ...parts), "utf8");

const BADGE = read("components", "SplitBadge.tsx");
const CREATE = read("app", "benchmarks", "page.tsx");
const DETAIL = read("app", "benchmarks", "[id]", "page.tsx");
const LIBRARY = read("app", "library", "page.tsx");
const LEADERBOARD = read("app", "leaderboard", "page.tsx");

describe("the split badge distinguishes all three states", () => {
  it("styles held out as a warning, not as a neutral label", () => {
    expect(BADGE).toContain("holdout: \"badge warn\"");
  });

  it("labels unassigned rather than rendering it as empty or as dev", () => {
    expect(BADGE).toContain("unassigned:");
    expect(BADGE).toContain("protocol.unassignedHint");
  });
});

describe("the library shows where each scenario sits", () => {
  it("renders the split beside the scenario name", () => {
    expect(LIBRARY).toContain("SplitBadge");
    expect(LIBRARY).toContain("entry.split");
    expect(LIBRARY).toContain("entry.split_notes");
  });

  it("explains what the column means", () => {
    expect(LIBRARY).toContain("protocol.splitHint");
  });
});

describe("a held-out scenario warns before the run, not after", () => {
  it("resolves the split of the selected scenario", () => {
    expect(CREATE).toContain("/scenario-protocol");
    expect(CREATE).toContain("selectedSplit");
  });

  it("shows the warning only for held-out scenarios", () => {
    expect(CREATE).toContain('selectedSplit === "holdout"');
    expect(CREATE).toContain("protocol.holdoutWarning");
  });

  it("does not disable creation — a held-out set exists to be used once", () => {
    expect(CREATE).not.toContain('disabled={selectedSplit === "holdout"');
  });
});

describe("a stored report carries the split it ran under", () => {
  it("shows the snapshotted split and protocol version", () => {
    expect(DETAIL).toContain("results.report.scenario_split");
    expect(DETAIL).toContain("results.report.protocol_version");
  });

  it("says outright when a result came from a held-out scenario", () => {
    expect(DETAIL).toContain("protocol.holdoutBenchmarkNotice");
  });

  it("says an unassigned result is excluded from the gap", () => {
    expect(DETAIL).toContain("protocol.unassignedBenchmarkNotice");
  });
});

describe("the generalization gap admits what it cannot compute", () => {
  it("prints a placeholder rather than a zero when a side is missing", () => {
    expect(LEADERBOARD).toContain("generalization.noGap");
    expect(LEADERBOARD).toContain("gap === undefined");
  });

  it("reads the metric direction from the backend instead of assuming it", () => {
    expect(LEADERBOARD).toContain("metric.higher_is_better");
  });

  it("surfaces the per-stack warnings, not just the numbers", () => {
    expect(LEADERBOARD).toContain("entry.warnings");
    expect(LEADERBOARD).toContain("summary.warnings");
  });

  it("shows how often held-out scenarios have been consulted", () => {
    expect(LEADERBOARD).toContain("holdout_usage");
    expect(LEADERBOARD).toContain("generalization.holdoutUsageHint");
  });
});

describe("both locales carry the new strings", () => {
  const keys = [
    "protocol.split",
    "protocol.dev",
    "protocol.holdout",
    "protocol.unassigned",
    "protocol.splitHint",
    "protocol.unassignedHint",
    "protocol.version",
    "protocol.holdoutWarning",
    "protocol.holdoutBenchmarkNotice",
    "protocol.unassignedBenchmarkNotice",
    "generalization.title",
    "generalization.hint",
    "generalization.gap",
    "generalization.noGap",
    "generalization.holdoutUsage",
    "generalization.holdoutUsageHint",
  ];

  it.each(keys)("%s is translated in English and Vietnamese", (key) => {
    expect((en as Record<string, string>)[key]).toBeTruthy();
    expect((vi as Record<string, string>)[key]).toBeTruthy();
  });

  it("keeps the scenario placeholder in the held-out warning", () => {
    expect(en["protocol.holdoutWarning"]).toContain("{scenario}");
    expect(vi["protocol.holdoutWarning"]).toContain("{scenario}");
  });

  it("does not leave the Vietnamese explanation as the English one", () => {
    expect(vi["protocol.splitHint"]).not.toEqual(en["protocol.splitHint"]);
    expect(vi["generalization.hint"]).not.toEqual(en["generalization.hint"]);
  });
});
