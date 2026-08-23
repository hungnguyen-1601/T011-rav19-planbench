/** The measured-difficulty surface (P03).
 *
 * What has to hold in the UI: a difficulty never appears without its
 * interval and its baseline, an uncalibrated scenario says "not
 * measured" instead of borrowing the curriculum position, a scale that
 * has gone stale or was measured on too few seeds says so, and the
 * coverage warnings are shown rather than being left in a log.
 *
 * Source-level, matching the other page tests: the page sits behind an
 * effect and a fetch, so a first paint shows only a loading state.
 */

import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

import en from "../../lib/i18n/locales/en.json";
import vi from "../../lib/i18n/locales/vi.json";

const read = (...parts: string[]) => readFileSync(join(process.cwd(), "src", ...parts), "utf8");

const BADGE = read("components", "DifficultyBadge.tsx");
const LIBRARY = read("app", "library", "page.tsx");
const TYPES = read("lib", "platformTypes.ts");

describe("a difficulty is never shown as a bare number", () => {
  it("prints the confidence interval beside the value", () => {
    expect(BADGE).toContain("difficulty.ci");
    expect(BADGE).toContain("ci95");
  });

  it("names the baseline and calibration version that produced it", () => {
    expect(BADGE).toContain("difficulty.baselineHint");
    expect(BADGE).toContain("baseline_algorithm");
    expect(BADGE).toContain("calibration_version");
  });

  it("bands it without hiding the number", () => {
    expect(BADGE).toContain("difficulty.band.");
    expect(BADGE).toContain("value.toFixed(2)");
  });

  it("keeps 'never solved' visually apart from 'hard'", () => {
    expect(BADGE).toContain('unsolved: "badge err"');
    expect(BADGE).toContain('hard: "badge warn"');
  });
});

describe("an uncalibrated scenario says so", () => {
  it("renders 'not measured' rather than an empty cell", () => {
    expect(BADGE).toContain("difficulty.uncalibrated");
    expect(BADGE).toContain("if (!difficulty)");
  });

  it("explains that the curriculum position is not a substitute", () => {
    expect(en["difficulty.uncalibratedHint"]).toContain("curriculum position");
    expect(vi["difficulty.uncalibratedHint"]).toContain("curriculum");
  });
});

describe("caveats travel with the measurement", () => {
  it("flags a difficulty measured on a scenario that has since changed", () => {
    expect(BADGE).toContain("difficulty.stale");
    expect(BADGE).toContain("difficulty.staleHint");
  });

  it("flags a difficulty measured over too few seeds", () => {
    expect(BADGE).toContain("difficulty.provisional");
    expect(BADGE).toContain("adequate");
  });
});

describe("the library no longer carries the difficulty scale", () => {
  /* **The measurements are real; the place was wrong.** A difficulty is
     a property of one baseline stack on one calibration run, and the
     calibration panel existed to say which run. Both are facts about the
     benchmark protocol, and this table is read to find out what a
     scenario *does* — a question neither of them answers. The column and
     its panel were also the two widest things on the row.

     `DifficultyBadge` and the endpoint behind it are untouched: what
     went is one page's use of them. */

  it("shows no difficulty column", () => {
    expect(LIBRARY).not.toContain("DifficultyBadge");
    expect(LIBRARY).not.toContain("entry.difficulty");
    expect(LIBRARY).not.toContain("difficulty.hint");
  });

  it("no longer fetches or renders the calibration summary", () => {
    /* Fetching it to draw nothing would be a request per page load for a
       panel that is gone. */
    expect(LIBRARY).not.toContain("/difficulty-calibration");
    expect(LIBRARY).not.toContain("difficulty.calibrationMeta");
    expect(LIBRARY).not.toContain("coverage.warnings");
  });

  it("keeps the curriculum position, which is about the scenario", () => {
    /* Where an entry sits in the teaching order is a property of the
       entry itself, not of a baseline that was run against it. */
    expect(LIBRARY).toContain("library.curriculum");
    expect(LIBRARY).toContain("entry.curriculum_index");
  });
});

describe("the types keep difficulty optional at every level", () => {
  it("allows a library entry with no difficulty", () => {
    expect(TYPES).toContain("difficulty: DifficultyLabel | null");
  });

  it("allows a summary with no calibration at all", () => {
    expect(TYPES).toContain("calibration_version: string | null");
    expect(TYPES).toContain("baseline: DifficultyBaseline | null");
  });
});

describe("both locales carry the new strings", () => {
  const keys = [
    "library.curriculum",
    "library.curriculumHint",
    "library.difficulty",
    "difficulty.hint",
    "difficulty.uncalibrated",
    "difficulty.uncalibratedHint",
    "difficulty.ci",
    "difficulty.band.easy",
    "difficulty.band.moderate",
    "difficulty.band.hard",
    "difficulty.band.unsolved",
    "difficulty.baselineHint",
    "difficulty.provisional",
    "difficulty.provisionalBadge",
    "difficulty.stale",
    "difficulty.staleHint",
    "difficulty.calibrationTitle",
    "difficulty.calibrationMeta",
    "difficulty.replanningOn",
    "difficulty.replanningOff",
    "difficulty.range",
  ];

  it.each(keys)("%s is translated in English and Vietnamese", (key) => {
    expect((en as Record<string, string>)[key]).toBeTruthy();
    expect((vi as Record<string, string>)[key]).toBeTruthy();
  });

  it("keeps every placeholder in both languages", () => {
    for (const placeholder of ["{algorithm}", "{seeds}", "{version}"]) {
      expect(en["difficulty.baselineHint"]).toContain(placeholder);
      expect(vi["difficulty.baselineHint"]).toContain(placeholder);
    }
    for (const placeholder of ["{min}", "{max}", "{spread}", "{count}"]) {
      expect(en["difficulty.range"]).toContain(placeholder);
      expect(vi["difficulty.range"]).toContain(placeholder);
    }
  });

  it("does not leave the Vietnamese explanation as the English one", () => {
    expect(vi["difficulty.hint"]).not.toEqual(en["difficulty.hint"]);
    expect(vi["difficulty.uncalibratedHint"]).not.toEqual(en["difficulty.uncalibratedHint"]);
  });
});
