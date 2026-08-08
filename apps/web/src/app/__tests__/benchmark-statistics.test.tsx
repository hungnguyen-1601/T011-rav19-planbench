/** The benchmark detail page's statistics surface (P04).
 *
 * What has to hold: the table's headline numbers are medians, the
 * spread is reachable rather than dropped, a p-value never appears
 * without its paired seed count beside it, and a small benchmark says so
 * instead of letting a "significant" verdict stand on five seeds.
 *
 * Source-level, matching the other page tests: this page's body sits
 * behind an effect and a fetch, so a first paint shows a loading state.
 */

import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

import en from "../../lib/i18n/locales/en.json";
import vi from "../../lib/i18n/locales/vi.json";

const PAGE = readFileSync(
  join(process.cwd(), "src", "app", "benchmarks", "[id]", "page.tsx"),
  "utf8",
);

describe("the comparison table quotes medians", () => {
  it("uses the median fields, not the means, for the three skewed metrics", () => {
    expect(PAGE).toContain("median_travel_time_successful");
    expect(PAGE).toContain("median_path_efficiency_successful");
    expect(PAGE).toContain("median_smoothness_successful");
  });

  it("no longer prints the deprecated means in those cells", () => {
    expect(PAGE).not.toContain("mean_travel_time_successful");
    expect(PAGE).not.toContain("mean_path_efficiency_successful");
    expect(PAGE).not.toContain("mean_smoothness_successful");
  });

  it("keeps the spread reachable instead of dropping it", () => {
    expect(PAGE).toContain("iqr_travel_time_successful");
    expect(PAGE).toContain("ci95_travel_time_successful");
    expect(PAGE).toContain("ci95_success_rate");
  });
});

describe("a p-value never travels alone", () => {
  it("shows the paired seed count in the same row", () => {
    expect(PAGE).toContain("paired_seed_count");
    expect(PAGE).toContain("p_value");
  });

  it("shows the effect size, not only the p-value", () => {
    expect(PAGE).toContain("effect_size");
  });

  it("renders each comparison's own warning", () => {
    expect(PAGE).toContain("comparison.warning");
  });
});

describe("a small benchmark cannot claim a result", () => {
  it("warns when the seed count is inadequate", () => {
    expect(PAGE).toContain("statistically_adequate");
    expect(PAGE).toContain("detail.fewSeedsWarning");
  });

  it("requires an adequate seed count before calling a difference found", () => {
    expect(PAGE).toContain("comparison.significant && report.statistically_adequate");
  });

  it("says no test was run rather than printing a blank", () => {
    expect(PAGE).toContain("detail.noTest");
  });
});

describe("both locales carry the new strings", () => {
  const keys = [
    "detail.medianHint",
    "detail.statistics",
    "detail.statisticsHint",
    "detail.pairedSeeds",
    "detail.effectSize",
    "detail.effectSizeHint",
    "detail.fewSeedsWarning",
    "detail.noStrongClaim",
    "detail.noTest",
    "detail.noConclusion",
  ];

  it.each(keys)("%s is translated in English and Vietnamese", (key) => {
    expect((en as Record<string, string>)[key]).toBeTruthy();
    expect((vi as Record<string, string>)[key]).toBeTruthy();
  });

  it("keeps the seed placeholder in both warnings", () => {
    expect(en["detail.fewSeedsWarning"]).toContain("{seeds}");
    expect(vi["detail.fewSeedsWarning"]).toContain("{seeds}");
  });

  it("does not leave the Vietnamese caveat as the English one", () => {
    expect(vi["detail.noStrongClaim"]).not.toEqual(en["detail.noStrongClaim"]);
  });
});
